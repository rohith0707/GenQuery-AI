# rag_engine.py
"""
RAG (Retrieval-Augmented Generation) Engine for GenQuery-AI

Implements a full RAG pipeline with:
  1. Vector-based schema indexing — embeds table metadata for intelligent retrieval
  2. Semantic query caching — avoids redundant LLM calls for similar questions
  3. Few-shot example retrieval — provides in-context learning examples
  4. Conversation memory — enables multi-turn query refinement

Architecture:
  User Query
       │
       ▼ (embed)
  ┌────┴─────────────────────────────────────────────────┐
  │               Parallel Vector Retrieval               │
  │  ┌───────────────┐  ┌────────────┐  ┌────────────┐  │
  │  │ Schema Index   │  │ Query Cache │  │ Few-Shot DB│  │
  │  │ (ChromaDB)     │  │ (ChromaDB)  │  │ (ChromaDB) │  │
  │  └───────┬───────┘  └─────┬──────┘  └─────┬──────┘  │
  └──────────┼────────────────┼────────────────┼─────────┘
             │                │                │
             ▼                ▼                ▼
       Top-K tables     Cache hit?       Top-K examples
             │                │                │
             └────────────────┼────────────────┘
                              ▼
                    ┌─────────────────────┐
                    │  RAG Context Object  │
                    │  (assembled context) │
                    └──────────┬──────────┘
                               ▼
                    ┌─────────────────────┐
                    │ Augmented LLM Prompt │
                    │ schema + examples +  │
                    │ conversation history │
                    └─────────────────────┘

Vector Store: ChromaDB (persistent, local)
Embeddings:   OpenAI text-embedding-3-small (primary)
              sentence-transformers all-MiniLM-L6-v2 (fallback)
"""

import os
import json
import time
import hashlib
from typing import Optional, List, Dict, Tuple, Any
from pathlib import Path
from dataclasses import dataclass, field
from utils import get_env, logger

# ---------------------------------------------------------------------------
# Configuration (overridable via environment variables)
# ---------------------------------------------------------------------------
RAG_PERSIST_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rag_store")
EMBEDDING_MODEL = get_env("RAG_EMBEDDING_MODEL", "text-embedding-3-small")
CACHE_SIMILARITY_THRESHOLD = float(get_env("RAG_CACHE_THRESHOLD", "0.90"))
SCHEMA_TOP_K = int(get_env("RAG_SCHEMA_TOP_K", "8"))
FEW_SHOT_TOP_K = int(get_env("RAG_FEW_SHOT_TOP_K", "3"))
RAG_ENABLED = get_env("RAG_ENABLED", "true").lower() in ("1", "true", "yes")
OPENAI_KEY = get_env("OPENAI_API_KEY")


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------
@dataclass
class TableSchema:
    """Structured representation of a database table for embedding."""
    table_name: str
    columns: List[Dict[str, str]]  # [{"name": "id", "type": "NUMBER", "nullable": "YES"}]
    description: str = ""
    database: str = ""
    schema: str = ""

    def to_compact_str(self) -> str:
        """Compact format: orders(id INT, customer_id INT, amount DECIMAL)"""
        cols = ", ".join(
            f"{c['name']} {c.get('type', '')}".strip() for c in self.columns
        )
        return f"{self.table_name}({cols})"

    def to_embedding_text(self) -> str:
        """Rich text for embedding — includes types and nullability."""
        cols_detail = "; ".join(
            f"{c['name']} ({c.get('type', '')}"
            + (", nullable" if c.get("nullable") == "YES" else ", not null")
            + ")"
            for c in self.columns
        )
        desc = f" Description: {self.description}" if self.description else ""
        return f"Table: {self.table_name}. Columns: {cols_detail}.{desc}"


@dataclass
class RAGContext:
    """Assembled retrieval context passed to the LLM prompt builder."""
    relevant_tables: List[str] = field(default_factory=list)
    few_shot_examples: List[Dict[str, str]] = field(default_factory=list)
    cached_sql: Optional[str] = None
    cache_confidence: float = 0.0
    conversation_history: List[Dict[str, str]] = field(default_factory=list)
    retrieval_time_ms: float = 0.0


# ---------------------------------------------------------------------------
# Embedding Provider (dual-mode: OpenAI primary, local fallback)
# ---------------------------------------------------------------------------
class EmbeddingProvider:
    """
    Abstraction over embedding backends.
      Primary   → OpenAI text-embedding-3-small (fast, high quality)
      Fallback  → sentence-transformers all-MiniLM-L6-v2 (free, local)
      Default   → ChromaDB built-in (if neither available)
    """

    def __init__(self):
        self._ef = None
        self._mode = "none"
        self._initialize()

    def _initialize(self):
        # --- OpenAI path ---
        if OPENAI_KEY:
            try:
                import chromadb.utils.embedding_functions as ef

                self._ef = ef.OpenAIEmbeddingFunction(
                    api_key=OPENAI_KEY,
                    model_name=EMBEDDING_MODEL,
                )
                self._mode = "openai"
                logger.info("RAG embeddings: OpenAI (%s)", EMBEDDING_MODEL)
                return
            except Exception as e:
                logger.warning("RAG: OpenAI embedding init failed (%s); trying local.", e)

        # --- Sentence-Transformers path ---
        try:
            import chromadb.utils.embedding_functions as ef

            self._ef = ef.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            self._mode = "local"
            logger.info("RAG embeddings: sentence-transformers (all-MiniLM-L6-v2)")
            return
        except Exception as e:
            logger.warning("RAG: Local embedding init failed (%s); using default.", e)

        # --- ChromaDB default ---
        self._mode = "default"
        logger.info("RAG embeddings: ChromaDB default")

    def get_embedding_function(self):
        return self._ef  # None → ChromaDB uses its own default

    @property
    def mode(self) -> str:
        return self._mode


# ---------------------------------------------------------------------------
# Schema Index — vector store of table metadata
# ---------------------------------------------------------------------------
class SchemaIndex:
    """
    Embeds each table's description (name + columns + types) into ChromaDB.
    At query time, retrieves the Top-K most relevant tables via cosine similarity
    instead of dumping the entire schema into the prompt.
    """

    def __init__(self, collection):
        self._collection = collection
        self._indexed_ids: set = set()

    def index_tables(self, tables: List[TableSchema]) -> int:
        """Upsert table schemas into the vector store. Returns count indexed."""
        if not tables:
            return 0

        documents, metadatas, ids = [], [], []
        for t in tables:
            doc_id = hashlib.md5(
                f"{t.database}.{t.schema}.{t.table_name}".encode()
            ).hexdigest()
            if doc_id in self._indexed_ids:
                continue
            documents.append(t.to_embedding_text())
            metadatas.append({
                "table_name": t.table_name,
                "database": t.database,
                "schema": t.schema,
                "column_count": len(t.columns),
                "compact": t.to_compact_str(),
            })
            ids.append(doc_id)
            self._indexed_ids.add(doc_id)

        if not documents:
            return 0

        # Batch upsert
        batch_size = 100
        total = 0
        for i in range(0, len(documents), batch_size):
            self._collection.upsert(
                documents=documents[i : i + batch_size],
                metadatas=metadatas[i : i + batch_size],
                ids=ids[i : i + batch_size],
            )
            total += len(documents[i : i + batch_size])

        logger.info("RAG SchemaIndex: indexed %d tables (total: %d)", total, len(self._indexed_ids))
        return total

    def retrieve(self, query: str, top_k: int = SCHEMA_TOP_K) -> List[Dict[str, Any]]:
        """Return Top-K tables most relevant to the natural-language query."""
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            include=["metadatas", "distances"],
        )

        tables = []
        if results and results["metadatas"] and results["metadatas"][0]:
            for meta, dist in zip(results["metadatas"][0], results["distances"][0]):
                tables.append({
                    "table_name": meta.get("table_name", ""),
                    "compact_schema": meta.get("compact", ""),
                    "distance": dist,
                    "relevance": round(1.0 - dist, 4),
                })
        return tables

    @property
    def count(self) -> int:
        return self._collection.count()


# ---------------------------------------------------------------------------
# Semantic Query Cache
# ---------------------------------------------------------------------------
class QueryCache:
    """
    Stores (question → SQL) pairs as embeddings.
    On new query, if cosine similarity ≥ threshold → return cached SQL directly,
    completely bypassing LLM generation (saving latency + API cost).
    """

    def __init__(self, collection, threshold: float = CACHE_SIMILARITY_THRESHOLD):
        self._collection = collection
        self._threshold = threshold

    def cache(self, question: str, sql: str, success: bool = True,
              row_count: int = 0, provider: str = "") -> None:
        doc_id = hashlib.md5(f"{question}:{sql}".encode()).hexdigest()
        self._collection.upsert(
            documents=[question],
            metadatas=[{
                "sql": sql,
                "success": str(success),
                "row_count": row_count,
                "provider": provider,
                "timestamp": time.time(),
            }],
            ids=[doc_id],
        )
        logger.debug("RAG cache: stored (id=%s, rows=%d)", doc_id[:8], row_count)

    def find_similar(self, question: str) -> Optional[Tuple[str, float]]:
        """Return (cached_sql, confidence) if a near-duplicate exists, else None."""
        if self._collection.count() == 0:
            return None

        results = self._collection.query(
            query_texts=[question],
            n_results=1,
            include=["metadatas", "distances"],
        )

        if (results and results["metadatas"] and results["metadatas"][0]
                and results["distances"] and results["distances"][0]):
            distance = results["distances"][0][0]
            similarity = 1.0 - distance
            meta = results["metadatas"][0][0]

            if similarity >= self._threshold and meta.get("success") == "True":
                logger.info("RAG cache HIT (sim=%.3f ≥ %.2f)", similarity, self._threshold)
                return meta.get("sql", ""), similarity
            else:
                logger.debug("RAG cache MISS (sim=%.3f < %.2f)", similarity, self._threshold)
        return None

    def get_similar(self, question: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """Top-K past queries for few-shot augmentation (even below cache threshold)."""
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[question],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        out = []
        if results and results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            ):
                out.append({
                    "question": doc,
                    "sql": meta.get("sql", ""),
                    "similarity": round(1.0 - dist, 4),
                    "row_count": meta.get("row_count", 0),
                })
        return out

    @property
    def count(self) -> int:
        return self._collection.count()


# ---------------------------------------------------------------------------
# Few-Shot Example Store (seed + runtime-extensible)
# ---------------------------------------------------------------------------

# Pre-loaded examples covering common analytical SQL patterns
_SEED_EXAMPLES = [
    {
        "q": "Total revenue by region",
        "sql": "SELECT c.region, SUM(o.amount) AS total_revenue "
               "FROM orders o JOIN customers c ON c.id = o.customer_id "
               "GROUP BY c.region ORDER BY total_revenue DESC",
        "cat": "aggregation",
    },
    {
        "q": "Top 10 customers by lifetime value",
        "sql": "SELECT id, region, channel, lifetime_value "
               "FROM customers ORDER BY lifetime_value DESC LIMIT 10",
        "cat": "ranking",
    },
    {
        "q": "Monthly order count trend for the last 12 months",
        "sql": "SELECT DATE_TRUNC('month', created_at) AS month, COUNT(*) AS order_count "
               "FROM orders WHERE created_at >= DATEADD(month, -12, CURRENT_DATE) "
               "GROUP BY month ORDER BY month",
        "cat": "time_series",
    },
    {
        "q": "Average order value by customer channel",
        "sql": "SELECT c.channel, AVG(o.amount) AS avg_order_value, COUNT(o.id) AS order_count "
               "FROM orders o JOIN customers c ON c.id = o.customer_id "
               "GROUP BY c.channel ORDER BY avg_order_value DESC",
        "cat": "aggregation",
    },
    {
        "q": "Customers who placed more than 5 orders last month",
        "sql": "SELECT c.id, c.region, COUNT(o.id) AS order_count, SUM(o.amount) AS total_spent "
               "FROM customers c JOIN orders o ON o.customer_id = c.id "
               "WHERE o.created_at >= DATEADD(month, -1, CURRENT_DATE) "
               "GROUP BY c.id, c.region HAVING COUNT(o.id) > 5 ORDER BY order_count DESC",
        "cat": "having",
    },
    {
        "q": "Running total of revenue over time",
        "sql": "SELECT created_at::DATE AS order_date, amount, "
               "SUM(amount) OVER (ORDER BY created_at::DATE "
               "ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS running_total "
               "FROM orders ORDER BY order_date",
        "cat": "window_function",
    },
    {
        "q": "Rank customers by total spend within each region",
        "sql": "SELECT c.id, c.region, SUM(o.amount) AS total_spend, "
               "RANK() OVER (PARTITION BY c.region ORDER BY SUM(o.amount) DESC) AS region_rank "
               "FROM orders o JOIN customers c ON c.id = o.customer_id "
               "GROUP BY c.id, c.region QUALIFY region_rank <= 10",
        "cat": "window_qualify",
    },
    {
        "q": "Year-over-year revenue comparison",
        "sql": "WITH yearly AS ("
               "SELECT YEAR(created_at) AS yr, SUM(amount) AS revenue FROM orders GROUP BY yr"
               ") SELECT curr.yr, curr.revenue AS current_revenue, prev.revenue AS prev_revenue, "
               "ROUND((curr.revenue - prev.revenue) / NULLIF(prev.revenue, 0) * 100, 2) AS yoy_pct "
               "FROM yearly curr LEFT JOIN yearly prev ON curr.yr = prev.yr + 1 ORDER BY curr.yr",
        "cat": "cte_yoy",
    },
    {
        "q": "Revenue by region for Q2 2024",
        "sql": "SELECT c.region, SUM(o.amount) AS revenue "
               "FROM orders o JOIN customers c ON c.id = o.customer_id "
               "WHERE o.created_at >= '2024-04-01' AND o.created_at < '2024-07-01' "
               "GROUP BY c.region ORDER BY revenue DESC",
        "cat": "date_filter",
    },
    {
        "q": "New customer acquisition by month",
        "sql": "WITH first_order AS ("
               "SELECT customer_id, MIN(created_at) AS first_date FROM orders GROUP BY customer_id"
               ") SELECT DATE_TRUNC('month', first_date) AS month, COUNT(*) AS new_customers "
               "FROM first_order GROUP BY month ORDER BY month",
        "cat": "cte_acquisition",
    },
    {
        "q": "Customer retention rate month over month",
        "sql": "WITH monthly AS ("
               "SELECT customer_id, DATE_TRUNC('month', created_at) AS month "
               "FROM orders GROUP BY customer_id, month"
               "), retention AS ("
               "SELECT curr.month, COUNT(DISTINCT curr.customer_id) AS active, "
               "COUNT(DISTINCT prev.customer_id) AS retained "
               "FROM monthly curr LEFT JOIN monthly prev "
               "ON curr.customer_id = prev.customer_id "
               "AND curr.month = DATEADD(month, 1, prev.month) GROUP BY curr.month"
               ") SELECT month, active, retained, "
               "ROUND(retained * 100.0 / NULLIF(active, 0), 2) AS retention_pct "
               "FROM retention ORDER BY month",
        "cat": "cte_retention",
    },
    {
        "q": "Show all tables in the database",
        "sql": "SHOW TABLES",
        "cat": "metadata",
    },
    {
        "q": "Describe the orders table",
        "sql": "DESCRIBE TABLE orders",
        "cat": "metadata",
    },
]


class FewShotStore:
    """
    Vector index of curated (question, SQL) examples.
    At query time, retrieves the most similar examples to inject
    as few-shot demonstrations in the LLM prompt.
    """

    def __init__(self, collection):
        self._collection = collection
        self._seeded = False

    def seed(self, examples: Optional[List[Dict]] = None) -> int:
        """Load seed examples (idempotent — skips if already populated)."""
        if self._seeded and self._collection.count() > 0:
            return 0

        examples = examples or _SEED_EXAMPLES
        documents, metadatas, ids = [], [], []

        for ex in examples:
            doc_id = hashlib.md5(f"fs:{ex['q']}".encode()).hexdigest()
            documents.append(ex["q"])
            metadatas.append({"sql": ex["sql"], "category": ex.get("cat", "")})
            ids.append(doc_id)

        if documents:
            self._collection.upsert(documents=documents, metadatas=metadatas, ids=ids)

        self._seeded = True
        logger.info("RAG FewShotStore: seeded %d examples", len(documents))
        return len(documents)

    def retrieve(self, query: str, top_k: int = FEW_SHOT_TOP_K) -> List[Dict[str, str]]:
        """Return Top-K most similar pre-loaded examples."""
        if self._collection.count() == 0:
            return []

        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count()),
            include=["documents", "metadatas", "distances"],
        )

        out = []
        if results and results["documents"] and results["documents"][0]:
            for doc, meta, dist in zip(
                results["documents"][0], results["metadatas"][0], results["distances"][0]
            ):
                sim = round(1.0 - dist, 3)
                if sim > 0.25:  # minimum relevance threshold
                    out.append({
                        "question": doc,
                        "sql": meta.get("sql", ""),
                        "category": meta.get("category", ""),
                        "similarity": sim,
                    })
        return out

    def add(self, question: str, sql: str, category: str = "user") -> None:
        """Dynamically add a new example at runtime."""
        doc_id = hashlib.md5(f"fs:{question}".encode()).hexdigest()
        self._collection.upsert(
            documents=[question],
            metadatas=[{"sql": sql, "category": category}],
            ids=[doc_id],
        )

    @property
    def count(self) -> int:
        return self._collection.count()


# ---------------------------------------------------------------------------
# Conversation Memory (multi-turn context)
# ---------------------------------------------------------------------------
class ConversationMemory:
    """
    Short-term in-memory store of recent (question, SQL) pairs.
    Enables multi-turn queries like 'now filter that by region = APAC'.
    Not persisted across server restarts (intentional — sessions are ephemeral).
    """

    def __init__(self, max_turns: int = 5):
        self._history: List[Dict[str, str]] = []
        self._max_turns = max_turns

    def add(self, question: str, sql: str) -> None:
        self._history.append({"question": question, "sql": sql})
        if len(self._history) > self._max_turns:
            self._history = self._history[-self._max_turns :]

    def get_history(self) -> List[Dict[str, str]]:
        return list(self._history)

    def clear(self) -> None:
        self._history.clear()

    @property
    def turn_count(self) -> int:
        return len(self._history)


# ---------------------------------------------------------------------------
# RAG Engine — Central Orchestrator
# ---------------------------------------------------------------------------
class RAGEngine:
    """
    Ties all RAG components together. Singleton lifecycle:
      1. initialize() — creates ChromaDB client + collections
      2. index_schema(tables) — embeds table metadata
      3. build_rag_context(query) — retrieves relevant context
      4. cache_successful_query() — learns from successful executions
    """

    def __init__(self):
        self._initialized = False
        self._embedding: Optional[EmbeddingProvider] = None
        self._schema_idx: Optional[SchemaIndex] = None
        self._query_cache: Optional[QueryCache] = None
        self._few_shot: Optional[FewShotStore] = None
        self._conv_memory: Optional[ConversationMemory] = None
        self._client = None
        self._init_time: Optional[float] = None

    # ---- Lifecycle ----

    def initialize(self) -> bool:
        """Initialize ChromaDB, embedding provider, and all collections."""
        if self._initialized:
            return True

        if not RAG_ENABLED:
            logger.info("RAG disabled via RAG_ENABLED=false")
            return False

        try:
            import chromadb
            from chromadb.config import Settings

            Path(RAG_PERSIST_DIR).mkdir(parents=True, exist_ok=True)

            self._embedding = EmbeddingProvider()
            ef = self._embedding.get_embedding_function()

            self._client = chromadb.PersistentClient(
                path=RAG_PERSIST_DIR,
                settings=Settings(anonymized_telemetry=False),
            )

            # Shared kwargs for all collections
            col_kw = {}
            if ef is not None:
                col_kw["embedding_function"] = ef

            self._schema_idx = SchemaIndex(
                self._client.get_or_create_collection(
                    name="schema_metadata",
                    metadata={"hnsw:space": "cosine"},
                    **col_kw,
                )
            )
            self._query_cache = QueryCache(
                self._client.get_or_create_collection(
                    name="query_cache",
                    metadata={"hnsw:space": "cosine"},
                    **col_kw,
                )
            )
            self._few_shot = FewShotStore(
                self._client.get_or_create_collection(
                    name="few_shot_examples",
                    metadata={"hnsw:space": "cosine"},
                    **col_kw,
                )
            )
            self._conv_memory = ConversationMemory()

            # Seed few-shot examples
            self._few_shot.seed()

            self._initialized = True
            self._init_time = time.time()
            logger.info(
                "RAG Engine ready (embedding=%s, persist=%s, few_shot=%d)",
                self._embedding.mode,
                RAG_PERSIST_DIR,
                self._few_shot.count,
            )
            return True

        except ImportError:
            logger.warning(
                "RAG: chromadb not installed. "
                "Install with: pip install chromadb sentence-transformers"
            )
            return False
        except Exception as e:
            logger.exception("RAG initialization failed: %s", e)
            return False

    @property
    def is_initialized(self) -> bool:
        return self._initialized

    # ---- Schema Indexing ----

    def index_schema(self, tables: List[TableSchema]) -> int:
        if not self._initialized or not self._schema_idx:
            return 0
        try:
            return self._schema_idx.index_tables(tables)
        except Exception as e:
            logger.warning("RAG schema indexing error: %s", e)
            return 0

    # ---- Query Caching ----

    def cache_successful_query(self, question: str, sql: str,
                               row_count: int = 0, provider: str = "") -> None:
        if not self._initialized or not self._query_cache:
            return
        try:
            self._query_cache.cache(
                question=question, sql=sql, success=True,
                row_count=row_count, provider=provider,
            )
            # Also add to few-shot store so future similar queries benefit
            if self._few_shot:
                self._few_shot.add(question, sql, category="learned")
        except Exception as e:
            logger.warning("RAG caching error: %s", e)

    # ---- Conversation Memory ----

    def add_conversation_turn(self, question: str, sql: str) -> None:
        if self._conv_memory:
            self._conv_memory.add(question, sql)

    def clear_conversation(self) -> None:
        if self._conv_memory:
            self._conv_memory.clear()

    # ---- Core RAG Retrieval ----

    def build_rag_context(self, question: str, schema_text: str = "") -> RAGContext:
        """
        Core retrieval pipeline. Queries all vector stores and assembles
        a unified RAGContext object for prompt augmentation.

        Returns immediately-usable context with:
          - cached_sql (if semantic cache hit)
          - relevant_tables (Top-K from schema index)
          - few_shot_examples (similar past patterns)
          - conversation_history (multi-turn memory)
        """
        ctx = RAGContext()
        if not self._initialized:
            return ctx

        start = time.time()

        try:
            # 1. Semantic cache check (fastest path — skip LLM entirely)
            cache_hit = self._query_cache.find_similar(question)
            if cache_hit:
                ctx.cached_sql, ctx.cache_confidence = cache_hit

            # 2. Retrieve relevant tables from schema vector index
            if self._schema_idx and self._schema_idx.count > 0:
                tables = self._schema_idx.retrieve(question)
                ctx.relevant_tables = [
                    t["compact_schema"] for t in tables if t.get("compact_schema")
                ]

            # 3. Few-shot examples from curated + learned store
            if self._few_shot and self._few_shot.count > 0:
                examples = self._few_shot.retrieve(question)
                ctx.few_shot_examples = [
                    {"question": ex["question"], "sql": ex["sql"]}
                    for ex in examples
                ]

            # 4. Also pull similar past queries (complementary to few-shot)
            if self._query_cache and self._query_cache.count > 0 and not ctx.cached_sql:
                similar = self._query_cache.get_similar(question, top_k=2)
                for sq in similar:
                    if sq.get("similarity", 0) > 0.45:
                        # Avoid duplicates
                        existing_sqls = {e["sql"] for e in ctx.few_shot_examples}
                        if sq["sql"] not in existing_sqls:
                            ctx.few_shot_examples.append({
                                "question": sq["question"],
                                "sql": sq["sql"],
                            })

            # 5. Conversation history for multi-turn context
            if self._conv_memory and self._conv_memory.turn_count > 0:
                ctx.conversation_history = self._conv_memory.get_history()

        except Exception as e:
            logger.warning("RAG context retrieval error: %s", e)

        ctx.retrieval_time_ms = round((time.time() - start) * 1000, 1)
        logger.info(
            "RAG context: cache=%s, tables=%d, examples=%d, history=%d, time=%.1fms",
            "HIT" if ctx.cached_sql else "MISS",
            len(ctx.relevant_tables),
            len(ctx.few_shot_examples),
            len(ctx.conversation_history),
            ctx.retrieval_time_ms,
        )
        return ctx

    # ---- Status / Observability ----

    def get_status(self) -> Dict[str, Any]:
        if not self._initialized:
            return {"initialized": False, "enabled": RAG_ENABLED}
        return {
            "initialized": True,
            "enabled": RAG_ENABLED,
            "embedding_mode": self._embedding.mode if self._embedding else "none",
            "schema_count": self._schema_idx.count if self._schema_idx else 0,
            "cache_count": self._query_cache.count if self._query_cache else 0,
            "few_shot_count": self._few_shot.count if self._few_shot else 0,
            "conversation_turns": self._conv_memory.turn_count if self._conv_memory else 0,
            "persist_dir": RAG_PERSIST_DIR,
        }


# ---------------------------------------------------------------------------
# Module-level Singleton + Public API
# ---------------------------------------------------------------------------
_rag_engine: Optional[RAGEngine] = None


def get_rag_engine() -> RAGEngine:
    """Get or create the singleton RAG engine instance."""
    global _rag_engine
    if _rag_engine is None:
        _rag_engine = RAGEngine()
    return _rag_engine


def initialize_rag(schema_tables: Optional[List[TableSchema]] = None) -> RAGEngine:
    """Initialize the RAG engine and optionally index schema tables."""
    engine = get_rag_engine()
    if not engine.is_initialized:
        engine.initialize()
    if schema_tables and engine.is_initialized:
        engine.index_schema(schema_tables)
    return engine


def build_rag_augmented_prompt(
    nl_query: str,
    rag_context: RAGContext,
    base_schema_text: str = "",
) -> str:
    """
    Build an enriched context string that replaces the basic schema_text
    parameter in provider prompt construction.

    This function produces ONLY the schema/context portion.
    The user question and generation guidelines are added by each
    provider function (generate_sql_openai, etc.) — NOT here.
    """
    sections = []

    # Section 1: Vector-retrieved relevant tables
    if rag_context.relevant_tables:
        sections.append("--- Retrieved Relevant Tables (via semantic search) ---")
        for t in rag_context.relevant_tables:
            sections.append(t)

    # Section 2: Base schema (supplement, may overlap with retrieved tables)
    if base_schema_text:
        sections.append("\n--- Additional Schema Context ---")
        sections.append(base_schema_text)

    # Section 3: Few-shot examples (retrieved via similarity)
    if rag_context.few_shot_examples:
        sections.append("\n--- Similar Query Patterns (use as reference) ---")
        for i, ex in enumerate(rag_context.few_shot_examples[: FEW_SHOT_TOP_K], 1):
            sections.append(f"Pattern {i}:")
            sections.append(f"  Question: {ex['question']}")
            sections.append(f"  SQL: {ex['sql']}")

    # Section 4: Conversation history for multi-turn support
    if rag_context.conversation_history:
        sections.append("\n--- Conversation History (modify previous SQL if user references it) ---")
        for turn in rag_context.conversation_history[-3:]:
            sections.append(f"  Previous Q: {turn['question']}")
            sections.append(f"  Previous SQL: {turn['sql']}")

    return "\n".join(sections) if sections else base_schema_text
