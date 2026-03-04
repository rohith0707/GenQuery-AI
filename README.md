# GenQuery-AI — Generative SQL Intelligence

A production-ready Streamlit application that translates natural language questions into optimized Snowflake SQL queries using **8 LLM providers** — including fully free, local options (Ollama, LM Studio) — with RAG-powered learning, feedback telemetry, and an admin analytics dashboard.

## 🌟 Features

### Core Capabilities
- **Natural Language to SQL**: Ask analytical questions in plain English, get Snowflake-optimized SQL
- **Multi-LLM Support**: OpenAI, Anthropic Claude, Google Gemini, LLaMA (HF/Groq), Together AI, Ollama (local), LM Studio (local) — with automatic fallback
- **RAG Engine**: Vector-based schema indexing, semantic query caching, few-shot example retrieval, and conversation memory via ChromaDB
- **Query Optimization**: AI-powered optimization to reduce query complexity and execution time
- **Safe Read-Only Execution**: Automatic validation ensures only SELECT/WITH queries are executed
- **Intelligent Schema Introspection**: Automatic database schema discovery (up to 60 tables, 50 columns each)
- **Interactive Data Visualization**: Built-in charts (Bar, Line, Area, Time Series, Heatmaps, Custom Builder)
- **Feedback & Telemetry**: Thumbs-up/down ratings, query logging with provider/latency tracking (SQLite-backed)
- **Admin Dashboard**: Real-time query telemetry, feedback analytics, and system health monitoring
- **Streaming SQL Generation**: Real-time token-by-token display for Ollama and compatible providers
- **Query History**: Track and review recent queries with execution statistics
- **Error Recovery**: Smart table name suggestion and automatic query regeneration on failures

### Security Features
- DDL/DML operation blocking (CREATE, DROP, INSERT, UPDATE, DELETE, ALTER)
- SQL injection prevention through sanitization
- Read-only Snowflake role enforcement
- Environment variable protection

## 🚀 Quick Start

### Prerequisites
- Python 3.8+
- Snowflake account with read-only access
- OpenAI API key
- Git

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/rohith0707/GenQuery-AI.git
cd GenQuery-AI
```

2. **Create virtual environment**
```bash
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

3. **Install dependencies**
```bash
pip install -r requirements.txt
```

4. **Configure environment variables**
Create a `.env` file in the project root:
```env
# ── LLM Providers (at least one required) ──────────────────
# Paid / Cloud
OPENAI_API_KEY=sk-your-openai-api-key-here
ANTHROPIC_API_KEY=your-anthropic-key          # Claude models
GEMINI_API_KEY=your-google-gemini-key         # or GOOGLE_API_KEY
HF_API_KEY=your-huggingface-key               # LLaMA via HuggingFace
GROQ_API_KEY=your-groq-key                    # LLaMA via Groq
TOGETHER_API_KEY=your-together-key            # Free $25 credits at together.ai

# Free & Local (no key needed — just run the server)
OLLAMA_BASE_URL=http://localhost:11434        # default
LMSTUDIO_BASE_URL=http://localhost:1234       # default

# ── Snowflake Configuration ─────────────────────────────────
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
SNOWFLAKE_ACCOUNT=orgname-account.region
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=your_database
SNOWFLAKE_SCHEMA=your_schema
SNOWFLAKE_ROLE=READ_ONLY_ROLE

# ── RAG Engine (optional) ──────────────────────────────────
RAG_ENABLED=true
RAG_EMBEDDING_MODEL=text-embedding-3-small    # or sentence-transformers fallback
RAG_CACHE_THRESHOLD=0.90
RAG_SCHEMA_TOP_K=5
RAG_FEW_SHOT_TOP_K=3

# ── Query Limits ────────────────────────────────────────────
MAX_QUERY_ROWS=5000
```

5. **Run the application**
```bash
streamlit run app.py
```

The application will open in your browser at `http://localhost:8501`

## 🎥 Project Demo
Click below to watch the video demo 👇  
[![AI SQL Generation Agent Demo](https://img.shields.io/badge/Watch%20Demo-Click%20Here-blue?style=for-the-badge)](https://github.com/rohith0707/GenQuery-AI/blob/main/AI%20SQL%20Generation%20Agent.mp4)



## 📖 Usage Guide

### Main SQL Generation Interface

1. **Enter your question** in natural language:
   - "Total revenue by region for Q2 2024"
   - "Top 10 customers by lifetime value"
   - "Monthly order count trend last 12 months"

2. **Add schema context** (optional but recommended):
   ```
   orders(id, customer_id, amount, created_at)
   customers(id, region, channel, lifetime_value)
   ```

3. **Click "🚀 Generate & Run"**

4. **Review results** in three tabs:
   - **SQL**: Generated query with copy button
   - **Data**: Results table with CSV download
   - **Visualization**: Interactive charts

### Query Optimization Feature

Access via the **🛠 Query Optimization** button in the sidebar.

**Purpose**: Optimize existing complex Snowflake queries to reduce execution time and improve performance.

**How to use**:
1. Click the Query Optimization button in the sidebar
2. Paste your complex SQL query into the text area
3. Click "⚙️ Optimize"
4. Review the side-by-side comparison
5. Check structural metrics (lines, JOINs, CTEs, etc.)
6. Copy the optimized query for use

**Optimization Techniques**:
- Removes unused CTEs
- Pushes WHERE filters earlier
- Removes redundant DISTINCT/ORDER BY
- Converts subqueries to QUALIFY for window functions
- Applies Snowflake-specific best practices

For detailed information, see [`QUERY_OPTIMIZATION_GUIDE.md`](QUERY_OPTIMIZATION_GUIDE.md).

## 🏗️ Architecture

### Project Structure
```
GenQuery-AI/
├── app.py                          # Main Streamlit application
├── langchain_agent.py              # Multi-LLM SQL generation & optimization
├── rag_engine.py                   # RAG pipeline (ChromaDB vector store)
├── snowflake_client.py             # Snowflake connection & execution
├── sql_validator.py                # Safety validation & sanitization
├── feedback_store.py               # SQLite telemetry & feedback logging
├── utils.py                        # Utilities & logging
├── ui_styles.py                    # CSS styling
├── design_tokens.py                # Design system tokens
├── reset_app.py                    # Session state reset utility
├── test_app.py                     # Integration tests
├── pages/
│   ├── Landing.py                  # Animated landing page
│   ├── Query_Optimization.py       # Query optimization page
│   └── Admin_Dashboard.py          # Telemetry & analytics dashboard
├── ui/
│   └── components.py               # Reusable UI components
├── rag_store/                      # ChromaDB persistent vector store
├── ARCHITECTURE.md                 # System architecture documentation
├── requirements.txt                # Python dependencies
├── .env                            # Environment configuration (not committed)
├── .gitignore                      # Git ignore rules
└── README.md                       # This file
```

### Technology Stack
- **Frontend**: Streamlit, Altair (visualizations)
- **Backend**: Python 3.8+
- **Database**: Snowflake (query execution), SQLite (telemetry & feedback)
- **Vector Store**: ChromaDB (persistent, local) for RAG pipeline
- **Embeddings**: OpenAI `text-embedding-3-small` (primary), `sentence-transformers/all-MiniLM-L6-v2` (fallback)
- **AI/ML — 8 LLM Providers**:
  - **Paid / Cloud**: OpenAI, Anthropic Claude, Google Gemini, LLaMA (HF/Groq), Together AI
  - **Free & Local**: Ollama, LM Studio
- **Libraries**: 
  - LangChain + langchain-community + langchain-openai (SQL generation)
  - anthropic, google-generativeai, huggingface-hub, groq (multi-provider)
  - chromadb, sentence-transformers (RAG & embeddings)
  - pandas (data manipulation)
  - sqlparse (SQL parsing)
  - tenacity (retry logic)

### Key Components

#### 1. Multi-LLM SQL Generation ([`langchain_agent.py`](langchain_agent.py))
- **8 providers** with automatic fallback chain
- **Streaming generation** — real-time token display for Ollama and compatible providers
- **In-memory SQL cache** (TTL=1h, max 200 entries) with SHA1 keying
- **Ollama optimizations** — model auto-selection, background warmup, speed-tuned defaults
- **Provider health tracking** — status dict with per-provider availability

#### 2. RAG Engine ([`rag_engine.py`](rag_engine.py))
- **Vector schema indexing** — embeds table metadata into ChromaDB for intelligent retrieval
- **Semantic query caching** — avoids redundant LLM calls for similar questions (configurable threshold)
- **Few-shot example retrieval** — provides in-context learning examples from the vector store
- **Conversation memory** — enables multi-turn query refinement
- **Dual embedding support** — OpenAI primary, sentence-transformers fallback

#### 3. Query Optimization ([`langchain_agent.py`](langchain_agent.py))
- LLM-based semantic rewriting
- Heuristic optimizations for common patterns
- Safety validation of optimized output
- Fallback to original query if optimization fails

#### 4. Snowflake Client ([`snowflake_client.py`](snowflake_client.py))
- Connection pooling with keep-alive
- Enhanced error messages with table suggestions
- Schema introspection for up to 60 tables, 50 columns each
- Rich schema export for RAG indexing (`get_rich_schema_for_rag()`)
- Automatic retry logic with exponential backoff

#### 5. Feedback & Telemetry ([`feedback_store.py`](feedback_store.py))
- SQLite-backed query logging (provider, latency, row count, cache hits)
- User feedback capture (thumbs-up/down paired to NL→SQL)
- Aggregated statistics API for the admin dashboard
- WAL mode for concurrent write safety

#### 6. Safety Validation ([`sql_validator.py`](sql_validator.py))
- Comment removal
- Multi-statement blocking
- DDL/DML keyword detection
- SELECT/WITH whitelist enforcement

#### 7. UI Components ([`ui/components.py`](ui/components.py))
- Dark/Light mode support
- Responsive design
- Interactive charts (8+ types)
- Copy-to-clipboard functionality
- Query history tracking

#### 8. Pages
- **Landing Page** ([`pages/Landing.py`](pages/Landing.py)) — Animated hero with gradient background, particle effects, and navigation
- **Query Optimization** ([`pages/Query_Optimization.py`](pages/Query_Optimization.py)) — Side-by-side SQL comparison with structural metrics
- **Admin Dashboard** ([`pages/Admin_Dashboard.py`](pages/Admin_Dashboard.py)) — Real-time telemetry, feedback analytics, system health, auto-refresh

## 🎨 UI Features

### Design System
- Modern gradient backgrounds (customizable for dark/light modes)
- Consistent color palette with accent colors
- Focus states and elevation tokens
- Smooth animations and transitions

### Visualization Options
1. **Bar Chart**: Categorical vs. Numeric comparisons
2. **Line Chart**: Trends over categories
3. **Area Chart**: Cumulative trends
4. **Time Series**: Temporal data analysis
5. **Correlation Heatmap**: Multi-variable relationships
6. **Custom Builder**: Flexible chart configuration

### Dark Mode
Toggle in the sidebar for comfortable viewing in different lighting conditions.

## 🔒 Security Best Practices

1. **Read-Only Role**: Use a Snowflake role with only SELECT permissions
2. **Environment Variables**: Never commit `.env` file to version control
3. **API Key Rotation**: Regularly rotate OpenAI API keys
4. **Query Limits**: Configure `MAX_QUERY_ROWS` to prevent resource exhaustion
5. **Network Security**: Use Snowflake IP allowlists in production
6. **Audit Logging**: Monitor `genai_sql_agent.log` for suspicious activity

## 📊 Example Queries

### Revenue Analysis
```
Natural Language: "Show total revenue by region for Q2 2024"

Generated SQL:
SELECT 
    c.region,
    SUM(o.amount) as total_revenue
FROM orders o
JOIN customers c ON o.customer_id = c.id
WHERE o.created_at BETWEEN '2024-04-01' AND '2024-06-30'
GROUP BY c.region
ORDER BY total_revenue DESC
```

### Customer Insights
```
Natural Language: "Top 10 customers by lifetime value"

Generated SQL:
SELECT 
    customer_id,
    lifetime_value
FROM customers
ORDER BY lifetime_value DESC
LIMIT 10
```

### Trend Analysis
```
Natural Language: "Monthly order count trend last 12 months"

Generated SQL:
SELECT 
    DATE_TRUNC('month', created_at) as month,
    COUNT(*) as order_count
FROM orders
WHERE created_at >= DATEADD(month, -12, CURRENT_DATE)
GROUP BY month
ORDER BY month
```

## 🔧 Configuration

### LLM Providers
The application supports **8 providers** with automatic fallback:

| Provider | Type | Key / Config |
|----------|------|--------------|
| OpenAI (GPT-4o-mini) | Paid / Cloud | `OPENAI_API_KEY` |
| Anthropic (Claude) | Paid / Cloud | `ANTHROPIC_API_KEY` |
| Google Gemini | Paid / Cloud | `GEMINI_API_KEY` |
| LLaMA (HuggingFace) | Paid / Cloud | `HF_API_KEY` |
| LLaMA (Groq) | Paid / Cloud | `GROQ_API_KEY` |
| Together AI | Free credits | `TOGETHER_API_KEY` |
| Ollama | Free & Local | `OLLAMA_BASE_URL` (default: localhost:11434) |
| LM Studio | Free & Local | `LMSTUDIO_BASE_URL` (default: localhost:1234) |

**No API key at all?** Install [Ollama](https://ollama.com) → `ollama pull codellama` — fully local, zero cost.

### Snowflake Connection
Configure in `.env`:
- **Account**: Format `orgname-account.region` (e.g., `myorg-xy12345.us-east-1`)
- **Warehouse**: Computational resources (e.g., `COMPUTE_WH`)
- **Database/Schema**: Target data location
- **Role**: Use read-only role for safety

### Query Limits
- `MAX_QUERY_ROWS`: Maximum rows to fetch (default: 5000)
- Prevents memory issues with large result sets

## 🐛 Troubleshooting

### "OPENAI_API_KEY not set" / "All provider attempts failed"
- You need **at least one** LLM provider configured
- Easiest free option: install [Ollama](https://ollama.com) and run `ollama pull codellama`
- Or add any API key (`OPENAI_API_KEY`, `TOGETHER_API_KEY`, etc.) to `.env`
- Restart the application after updating `.env`

### "Snowflake account not reachable"
- Check `SNOWFLAKE_ACCOUNT` format (should include region)
- Verify network connectivity
- Confirm account is active and accessible

### "Object not found" errors
- Check `SNOWFLAKE_DATABASE` and `SNOWFLAKE_SCHEMA` settings
- Verify user has SELECT permission on target tables
- Review suggested table names in error message

### "Dangerous keyword detected"
- Query contains DDL/DML operations
- Use only SELECT or WITH statements
- Remove CREATE, DROP, INSERT, UPDATE, DELETE, ALTER

### Poor query quality
- Add schema context in sidebar
- Use more specific natural language
- Review and refine generated SQL manually
- Try rephrasing your question

## 📝 Development

### Running Tests
```bash
# Install dev dependencies
pip install pytest pytest-cov

# Run tests (when available)
pytest tests/
```

### Code Style
- Follow PEP 8 guidelines
- Use type hints where applicable
- Add docstrings to functions
- Keep functions focused and modular

### Logging
Application logs are written to `genai_sql_agent.log`:
- INFO: General operational messages
- WARNING: Recoverable issues
- ERROR: Failed operations
- DEBUG: Detailed diagnostic information

### Adding New Features
1. Create feature branch
2. Update relevant modules
3. Add documentation
4. Test thoroughly
5. Update README.md

## 🚧 Known Limitations

1. **No Write Operations**: Only SELECT/WITH queries supported
2. **Schema Discovery Limits**: Maximum 60 tables, 50 columns per table
3. **No Query Cost Estimation**: Cannot predict Snowflake compute costs
4. **LLM Variability**: Results may vary between runs
5. **No Multi-Database Joins**: Limited to single database/schema context

## 🗺️ Roadmap

- [x] ~~Multi-LLM provider support~~ ✅
- [x] ~~Feedback & telemetry system~~ ✅
- [x] ~~Admin analytics dashboard~~ ✅
- [x] ~~RAG-powered learning from past queries~~ ✅
- [x] ~~Streaming SQL generation~~ ✅
- [ ] Query execution plan visualization
- [ ] Saved query templates
- [ ] Multi-database support
- [ ] Query performance benchmarking
- [ ] User authentication and authorization
- [ ] Query scheduling and automation
- [ ] Advanced chart customization
- [ ] Export to various formats (Excel, JSON, Parquet)

## 📄 License

[Add your license information here]

## 🤝 Contributing

Contributions are welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Submit a pull request

## 📞 Support

For issues, questions, or feature requests:
- Check existing documentation
- Review `genai_sql_agent.log` for errors
- Open an issue on GitHub
- Contact the development team

## 📚 Additional Documentation

- [`ARCHITECTURE.md`](ARCHITECTURE.md) - System architecture documentation

---

**Built for safe analytical exploration. Add governance, lineage & audit before productionization.**

**Version**: 2.0  
**Last Updated**: 2026-03-04
