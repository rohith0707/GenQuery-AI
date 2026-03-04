# langchain_agent.py
import os
import sys
import site
import hashlib
import time
import threading
from utils import get_env, logger
from typing import Optional

OPENAI_KEY = get_env("OPENAI_API_KEY")
if not OPENAI_KEY:
    logger.error("OPENAI_API_KEY not set in environment")

# Additional provider API keys (optional)
ANTHROPIC_API_KEY = get_env("ANTHROPIC_API_KEY")
GEMINI_API_KEY = get_env("GEMINI_API_KEY") or get_env("GOOGLE_API_KEY")
HF_API_KEY = get_env("HF_API_KEY")  # for HuggingFace Inference (LLaMA / other)
GROQ_API_KEY = get_env("GROQ_API_KEY")  # optional (alternate LLaMA provider)
TOGETHER_API_KEY = get_env("TOGETHER_API_KEY")  # free tier at together.ai
OLLAMA_BASE_URL = get_env("OLLAMA_BASE_URL") or "http://localhost:11434"  # local Ollama server
LMSTUDIO_BASE_URL = get_env("LMSTUDIO_BASE_URL") or "http://localhost:1234"  # local LM Studio server

# Provider status tracking
_PROVIDER_STATUS = {
    "openai": {"available": bool(OPENAI_KEY), "mode": None, "version": None, "error": None},
    "anthropic": {"available": bool(ANTHROPIC_API_KEY), "error": None},
    "gemini": {"available": bool(GEMINI_API_KEY), "error": None},
    "llama": {"available": bool(HF_API_KEY) or bool(GROQ_API_KEY), "error": None},
    "ollama": {"available": True, "error": None},       # local — always attempt
    "lmstudio": {"available": True, "error": None},    # local — always attempt
    "together": {"available": bool(TOGETHER_API_KEY), "error": None},
}

# ── Fast in-memory SQL cache (TTL=1h, max 200 entries) ──────────────────────────────────
_FAST_CACHE: dict = {}          # key → (sql, timestamp)
_FAST_CACHE_TTL = 3600          # seconds
_FAST_CACHE_MAX = 200

def _cache_key(nl_query: str, schema_text: str) -> str:
    raw = nl_query.lower().strip() + "|" + (schema_text or "")[:120]
    return hashlib.sha1(raw.encode()).hexdigest()

def _cache_get(key: str) -> Optional[str]:
    entry = _FAST_CACHE.get(key)
    if entry and (time.time() - entry[1]) < _FAST_CACHE_TTL:
        return entry[0]
    if entry:
        _FAST_CACHE.pop(key, None)   # expired
    return None

def _cache_put(key: str, sql: str):
    if len(_FAST_CACHE) >= _FAST_CACHE_MAX:
        # Evict oldest
        oldest = min(_FAST_CACHE, key=lambda k: _FAST_CACHE[k][1])
        _FAST_CACHE.pop(oldest, None)
    _FAST_CACHE[key] = (sql, time.time())

# ── Ollama speed-optimised defaults ────────────────────────────────────────────────────
# num_predict: SQL rarely exceeds 350 tokens. Raising this is the #1 slowdown.
# num_ctx: 2048 is enough for any SQL query + reasonable schema. Smaller = faster.
# keep_alive: keep model resident in VRAM between queries
_OLLAMA_GEN_OPTIONS   = {"temperature": 0.0, "num_predict": 350, "num_ctx": 2048, "keep_alive": "10m"}
_OLLAMA_OPT_OPTIONS   = {"temperature": 0.1, "num_predict": 400, "num_ctx": 2048, "keep_alive": "10m"}
_OLLAMA_MAX_SCHEMA    = 2800    # chars — large schemas slow small models

# Priority list: FASTEST first (smallest models that still produce correct SQL)
_OLLAMA_MODEL_PRIORITY = [
    "phi3:mini",        # 2.3 GB — fastest, good SQL
    "phi3",             # alias
    "qwen2.5-coder:1.5b",  # 1.5 GB — code-tuned, very fast
    "qwen2.5-coder",    # any pulled tag
    "deepseek-coder",   # strong SQL
    "codellama",        # good SQL but slower
    "llama3.2:3b",
    "llama3.2",
    "llama3.1",
    "llama3",
    "mistral",
    "gemma2",
]

def _warmup_ollama():
    """Send a minimal request to keep the best available model loaded in VRAM."""
    try:
        import requests as _req
        r = _req.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if r.status_code != 200:
            return
        pulled_names = [m["name"] for m in r.json().get("models", [])]
        pulled_bases = {n.split(":")[0] for n in pulled_names}
        model = next(
            (m for m in _OLLAMA_MODEL_PRIORITY if m.split(":")[0] in pulled_bases),
            pulled_names[0] if pulled_names else None,
        )
        if not model:
            return
        # Tiny warmup request — just to ensure model stays in VRAM
        _req.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={"model": model, "messages": [{"role": "user", "content": "hi"}],
                  "stream": False, "options": {"num_predict": 1, "keep_alive": "10m"}},
            timeout=30,
        )
        logger.info("Ollama warmup complete (model=%s)", model)
    except Exception:
        pass  # warmup is best-effort

# Start warmup in background so module import stays fast
threading.Thread(target=_warmup_ollama, daemon=True).start()

# ── Ollama model-list cache (TTL=60s) ───────────────────────────────────────────────────
# Avoids a repeated GET /api/tags on every generate/optimize call (~50–100 ms saved each).
_OLLAMA_MODEL_CACHE: dict = {"models": None, "ts": 0.0}
_OLLAMA_MODEL_CACHE_TTL = 60.0   # seconds

def _get_ollama_models() -> list:
    """Return cached list of pulled Ollama model names (refreshed at most once per minute)."""
    import requests as _req
    now = time.time()
    if (_OLLAMA_MODEL_CACHE["models"] is not None
            and (now - _OLLAMA_MODEL_CACHE["ts"]) < _OLLAMA_MODEL_CACHE_TTL):
        return _OLLAMA_MODEL_CACHE["models"]
    try:
        r = _req.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=2)
        if r.status_code == 200:
            names = [m["name"] for m in r.json().get("models", [])]
            _OLLAMA_MODEL_CACHE["models"] = names
            _OLLAMA_MODEL_CACHE["ts"] = now
            return names
    except Exception:
        pass
    return _OLLAMA_MODEL_CACHE["models"] or []

# ── Optimization result cache (TTL=1h, max 100 entries) ─────────────────────────────────
_OPT_CACHE: dict = {}
_OPT_CACHE_TTL = 3600
_OPT_CACHE_MAX = 100

def _opt_cache_key(sql: str) -> str:
    return hashlib.sha1(sql.strip().lower().encode()).hexdigest()

def _opt_cache_get(key: str) -> Optional[str]:
    entry = _OPT_CACHE.get(key)
    if entry and (time.time() - entry[1]) < _OPT_CACHE_TTL:
        return entry[0]
    if entry:
        _OPT_CACHE.pop(key, None)
    return None

def _opt_cache_put(key: str, sql: str):
    if len(_OPT_CACHE) >= _OPT_CACHE_MAX:
        oldest = min(_OPT_CACHE, key=lambda k: _OPT_CACHE[k][1])
        _OPT_CACHE.pop(oldest, None)
    _OPT_CACHE[key] = (sql, time.time())

# Provider used in the most recent successful generate_sql() call (read by app.py for logging)
_last_used_provider: str = ""


def get_last_used_provider() -> str:
    """Return the provider name that produced the most recent SQL result."""
    return _last_used_provider

# Simplified OpenAI initialization: prefer new Responses API; fallback to legacy <1.0 Completion.
_OPENAI_MODE = "uninitialized"   # 'new' | 'legacy' | 'error'
_openai_client = None
_openai_version = "0.0.0"
try:
    import openai
    _openai_version = getattr(openai, "__version__", "0.0.0")
    if hasattr(openai, "OpenAI"):
        # Ensure user-level site-packages (pip --user) are on sys.path
        try:
            user_site = site.getusersitepackages()
            if isinstance(user_site, str) and user_site not in sys.path:
                sys.path.append(user_site)
        except Exception as _user_site_err:
            logger.debug("Unable to append user site-packages: %s", _user_site_err)
        
        try:
            _openai_client = openai.OpenAI(api_key=OPENAI_KEY)
            _OPENAI_MODE = "new"
            logger.info("Initialized new OpenAI client (version %s)", _openai_version)
        except Exception as ce:
            logger.warning("Failed creating new OpenAI client (%s); will attempt legacy fallback.", ce)
            if _openai_version.startswith("0."):
                _OPENAI_MODE = "legacy"
            else:
                _OPENAI_MODE = "error"
    else:
        if _openai_version.startswith("0."):
            _OPENAI_MODE = "legacy"
            logger.info("Legacy OpenAI SDK detected (version %s)", _openai_version)
        else:
            _OPENAI_MODE = "error"
            logger.error("Unexpected OpenAI SDK state (version %s)", _openai_version)
except Exception as e_init:
    logger.exception("OpenAI import failure: %s", e_init)
    _OPENAI_MODE = "error"
USE_LANGCHAIN = False
_LANGCHAIN_STATUS = {
    "available": False,
    "mode": None,              # 'new' | 'simple' | None
    "new_err": None,
    "legacy_err": None,
}

# LangChain 1.0+ has minimal core; chains moved to separate packages or removed.
# For SQL generation with db_uri, we'll use LangChain's LLM + manual prompt construction.
try:
    from langchain_openai import OpenAI as LC_OpenAI
    from langchain_community.utilities import SQLDatabase
    USE_LANGCHAIN = True
    _LANGCHAIN_STATUS.update({"available": True, "mode": "simple"})
    logger.info("LangChain components available (langchain_openai + langchain_community); will use for db_uri SQL generation")
except Exception as e_new:
    _LANGCHAIN_STATUS["new_err"] = str(e_new)
    logger.warning(
        "LangChain imports unavailable; using direct OpenAI prompts. (err=%s)",
        e_new
    )
    USE_LANGCHAIN = False

def generate_sql_openai(nl_query: str, schema_text: str = "") -> str:
    """
    Generate exactly ONE Snowflake-safe SELECT / WITH statement.
    Uses new Responses API if available. Avoids deprecated openai.ChatCompletion access.
    """
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

    system_instructions = (
        "You are a Snowflake SQL generation Expert. Use full Snowflake knowledge (CTEs, SHOW, DESCRIBE, CALL, EXPLAIN, functions, views, time travel, semi-structured data handling). "
        "Return SQL only ( explanations, no comments, no backticks). "
        "Do NOT generate data-changing DELETE or UPDATE statements. "
        "Other statements are permitted when they help answer the analytical question."
    )
    user_prompt = (
        f"Schema (may be partial):\n{schema_text or '(none provided)'}\n\n"
        f"User request:\n{nl_query}\n\n"
        "Guidance:\n"
        "- Return pure Snowflake SQL (no commentary/backticks)\n"
        "- You MAY use any read-only Snowflake features (CTEs, SHOW, DESCRIBE, EXPLAIN, CALL for UDFs, functions, semi-structured data access, time travel)\n"
        "- Do NOT produce DELETE or UPDATE statements\n"
        "Return only SQL."
    )

    try:
        sql = ""
        if _OPENAI_MODE == "new" and _openai_client:
            # Dynamic model list: env FALLBACK_OPENAI_MODELS can override ordering.
            fallback_cfg = get_env("FALLBACK_OPENAI_MODELS")
            if fallback_cfg:
                configured = [m.strip() for m in fallback_cfg.split(",") if m.strip()]
            else:
                configured = ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"]
            response_models = ["gpt-5"] + configured  # attempt newest first; else fallbacks
            quota_exhausted = False
            quota_errors = []
            # Responses API attempts
            for m in response_models:
                try:
                    args = {
                        "model": m,
                        "input": [
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": user_prompt}
                        ],
                        "max_output_tokens": 900
                    }
                    # Add temperature then remove if rejected
                    args["temperature"] = 0.0
                    resp = _openai_client.responses.create(**args)
                    sql = getattr(resp, "output_text", "").strip()
                    if not sql:
                        try:
                            first = resp.output[0]
                            if isinstance(first, dict):
                                sql = first.get("content", [{}])[0].get("text", "").strip()
                        except Exception:
                            pass
                    if sql:
                        logger.info("Generated SQL via Responses API model=%s", m)
                        break
                except Exception as resp_err:
                    em = str(resp_err).lower()
                    if any(k in em for k in ("insufficient_quota", "rate limit", "429")):
                        quota_errors.append(f"{m}:{resp_err}")
                        logger.warning("Quota/rate issue model=%s (%s)", m, resp_err)
                        # Continue trying cheaper / older models
                        continue
                    if "unsupported parameter" in em or "invalid_request_error" in em:
                        logger.warning("Temperature unsupported model=%s; retrying without temperature.", m)
                        try:
                            resp = _openai_client.responses.create(
                                model=m,
                                input=[
                                    {"role": "system", "content": system_instructions},
                                    {"role": "user", "content": user_prompt}
                                ],
                                max_output_tokens=900
                            )
                            sql = getattr(resp, "output_text", "").strip()
                            if not sql:
                                try:
                                    first = resp.output[0]
                                    if isinstance(first, dict):
                                        sql = first.get("content", [{}])[0].get("text", "").strip()
                                except Exception:
                                    pass
                            if sql:
                                logger.info("Generated SQL via Responses API (no temperature) model=%s", m)
                                break
                        except Exception as inner_err:
                            ierr = str(inner_err).lower()
                            if any(k in ierr for k in ("insufficient_quota", "rate limit", "429")):
                                quota_errors.append(f"{m}:{inner_err}")
                                logger.warning("Quota/rate issue after retry model=%s (%s)", m, inner_err)
                            else:
                                logger.warning("Retry failed model=%s (%s)", m, inner_err)
                            continue
                    else:
                        logger.warning("Responses attempt failed model=%s (%s); moving on.", m, resp_err)
                        continue
            # Chat completions fallback if still empty
            if not sql:
                chat_models = configured  # skip gpt-5 for chat fallback if quota exhausted
                for cm in chat_models:
                    try:
                        comp = _openai_client.chat.completions.create(
                            model=cm,
                            messages=[
                                {"role": "system", "content": system_instructions},
                                {"role": "user", "content": user_prompt}
                            ],
                            temperature=0.0,
                            max_tokens=700
                        )
                        sql = comp.choices[0].message.content.strip()
                        if sql:
                            logger.info("Generated SQL via chat.completions model=%s", cm)
                            break
                    except Exception as chat_err:
                        cem = str(chat_err).lower()
                        if any(k in cem for k in ("insufficient_quota", "rate limit", "429")):
                            quota_errors.append(f"{cm}:{chat_err}")
                            logger.warning("Chat quota/rate issue model=%s (%s)", cm, chat_err)
                            continue
                        logger.warning("Chat attempt failed model=%s (%s)", cm, chat_err)
                if not sql and quota_errors:
                    quota_exhausted = True
            if not sql:
                if quota_exhausted:
                    raise RuntimeError(
                        "OpenAI quota/rate limits exhausted across all fallback models. "
                        "Tried: " + ", ".join(response_models) +
                        ". Errors: " + "; ".join(quota_errors) +
                        ". Actions: acquire more credits, rotate OPENAI_API_KEY, or narrow FALLBACK_OPENAI_MODELS."
                    )
                else:
                    raise RuntimeError("All OpenAI model attempts failed for non-quota reasons; inspect logs.")
        elif _OPENAI_MODE == "legacy":
            import openai  # type: ignore
            prompt = system_instructions + "\n\n" + user_prompt
            comp = openai.Completion.create(
                model="text-davinci-003",
                prompt=prompt,
                max_tokens=512,
                temperature=0.0,
                top_p=1.0,
                n=1
            )
            sql = comp.choices[0].text.strip()
        else:
            raise RuntimeError(f"OpenAI client not properly initialized (mode={_OPENAI_MODE}, version={_openai_version}).")

        sql = sql.strip().strip("`")
        if ";" in sql:
            stmts = [p.strip() for p in sql.split(";") if p.strip()]
            if stmts:
                sql = stmts[0]
        if not sql:
            raise RuntimeError("Empty SQL returned after attempts.")
        logger.debug("Generated SQL (truncated): %s", sql[:400].replace("\n", " "))
        return sql
    except Exception as e:
        em = str(e).lower()
        if any(k in em for k in ("insufficient_quota", "rate limit", "429")):
            raise RuntimeError(
                "OpenAI quota/rate limit error. " +
                "Suggested remediation: obtain new credits, rotate API key, set FALLBACK_OPENAI_MODELS to cheaper models (e.g. gpt-3.5-turbo). Original: " + str(e)
            )
        logger.exception("OpenAI SQL generation failed")
        raise
def generate_sql_langchain(nl_query: str, db_uri: str) -> str:
    """
    Generate SQL using LangChain LLM + SQLDatabase schema introspection.
    LangChain 1.0+ removed high-level chains; construct prompt manually.
    """
    if not USE_LANGCHAIN:
        raise RuntimeError("LangChain not enabled in this environment")
    try:
        lc_llm = LC_OpenAI(temperature=0, model_name="gpt-3.5-turbo-instruct")
        db = SQLDatabase.from_uri(db_uri)
        table_info = db.get_table_info()
        prompt = f"""Given the following database schema:
{table_info}

Write a SQL query to answer the user's question. Return ONLY the SQL query, no explanations.

Question: {nl_query}

SQL Query:"""
        sql = lc_llm.invoke(prompt)
        return sql.strip()
    except Exception as e:
        logger.exception("LangChain SQL generation failed")
        raise

# ---------- Additional Provider Generators (Anthropic / Gemini / LLaMA) ----------

def _base_system_instructions() -> str:
    return (
        "You are a Snowflake SQL generation Expert. Use full Snowflake knowledge (CTEs, SHOW, DESCRIBE, CALL, EXPLAIN, functions, views, time travel, semi-structured data handling). "
        "Return SQL only ( explanations, comments, no backticks). "
        "Do NOT generate DELETE or UPDATE statements. "
        "Other read-only statements are permitted if helpful."
    )

def _build_user_prompt(nl_query: str, schema_text: str) -> str:
    return (
        f"Schema:\n{schema_text or '(none provided)'}\n\n"
        f"Request:\n{nl_query}\n\n"
        "Return ONLY the Snowflake SQL. No explanations, no backticks."
    )

def generate_sql_anthropic(nl_query: str, schema_text: str) -> Optional[str]:
    if not ANTHROPIC_API_KEY:
        return None
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
        models = ["claude-4.5-sonnet", "claude-4.1-opus"]
        system_msg = _base_system_instructions()
        user_prompt = _build_user_prompt(nl_query, schema_text)
        for m in models:
            try:
                resp = client.messages.create(
                    model=m,
                    max_tokens=900,
                    temperature=0,
                    system=system_msg,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                # Anthropics response content list
                content_blocks = getattr(resp, "content", [])
                text_parts = []
                for blk in content_blocks:
                    if hasattr(blk, "text"):
                        text_parts.append(blk.text)
                    elif isinstance(blk, dict):
                        text_parts.append(blk.get("text", ""))
                sql = "\n".join([p for p in text_parts if p]).strip()
                if sql:
                    logger.info("Generated SQL via Anthropic model=%s", m)
                    return sql.strip().strip("`")
            except Exception as e:
                _PROVIDER_STATUS["anthropic"]["error"] = str(e)
                logger.warning("Anthropic attempt failed model=%s (%s); next.", m, e)
        return None
    except Exception as e:
        _PROVIDER_STATUS["anthropic"]["error"] = str(e)
        logger.warning("Anthropic import/use failed (%s)", e)
        return None

def generate_sql_gemini(nl_query: str, schema_text: str) -> Optional[str]:
    if not GEMINI_API_KEY:
        return None
    try:
        import google.generativeai as genai
        genai.configure(api_key=GEMINI_API_KEY)
        models = ["gemini-2.5-pro"]
        system_msg = _base_system_instructions()
        user_prompt = _build_user_prompt(nl_query, schema_text)
        for m in models:
            try:
                model = genai.GenerativeModel(m)
                resp = model.generate_content([system_msg, user_prompt])
                sql = getattr(resp, "text", "").strip()
                if not sql and hasattr(resp, "candidates"):
                    for c in resp.candidates:
                        if hasattr(c, "content") and hasattr(c.content, "parts"):
                            for part in c.content.parts:
                                t = getattr(part, "text", "")
                                if t:
                                    sql += t + "\n"
                    sql = sql.strip()
                if sql:
                    logger.info("Generated SQL via Gemini model=%s", m)
                    return sql.strip().strip("`")
            except Exception as e:
                _PROVIDER_STATUS["gemini"]["error"] = str(e)
                logger.warning("Gemini attempt failed model=%s (%s); next.", m, e)
        return None
    except Exception as e:
        _PROVIDER_STATUS["gemini"]["error"] = str(e)
        logger.warning("Gemini import/use failed (%s)", e)
        return None

def generate_sql_llama(nl_query: str, schema_text: str) -> Optional[str]:
    """
    Attempts LLaMA (or similar) via HuggingFace Inference or Groq if keys provided.
    Uses deterministic prompt; expects instruct-tuned model output containing SQL.
    """
    system_msg = _base_system_instructions()
    user_prompt = _build_user_prompt(nl_query, schema_text)
    prompt = f"{system_msg}\n\n{user_prompt}\n\nSQL:"
    # HuggingFace path
    if HF_API_KEY:
        try:
            from huggingface_hub import InferenceClient
            hf_models = [
                "meta-llama-3.1-70b-instruct",
                "meta-llama-3.1-8b-instruct",
                "llama4-70b-instruct"  # future placeholder if available
            ]
            for m in hf_models:
                try:
                    client = InferenceClient(m, token=HF_API_KEY)
                    resp = client.text_generation(prompt, max_new_tokens=700, temperature=0.0)
                    sql = (resp or "").strip()
                    # Heuristic: cut at first line containing SELECT/WITH
                    lowered = sql.lower()
                    for kw in ["select", "with"]:
                        pos = lowered.find(kw)
                        if pos >= 0:
                            sql = sql[pos:]
                            break
                    if sql:
                        logger.info("Generated SQL via HuggingFace model=%s", m)
                        return sql.strip().strip("`")
                except Exception as e:
                    _PROVIDER_STATUS["llama"]["error"] = str(e)
                    logger.warning("HF LLaMA attempt failed model=%s (%s); next.", m, e)
        except Exception as e:
            _PROVIDER_STATUS["llama"]["error"] = str(e)
            logger.warning("HuggingFace import/use failed (%s)", e)
    # Groq path (placeholder)
    if GROQ_API_KEY:
        try:
            import requests
            groq_models = ["llama-3.1-70b", "llama-3.1-8b"]
            for gm in groq_models:
                try:
                    r = requests.post(
                        "https://api.groq.com/openai/v1/chat/completions",
                        headers={"Authorization": f"Bearer {GROQ_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": gm,
                            "messages": [
                                {"role": "system", "content": system_msg},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.0,
                            "max_tokens": 700,
                        },
                        timeout=40,
                    )
                    if r.status_code == 200:
                        data = r.json()
                        sql = data.get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if sql:
                            logger.info("Generated SQL via Groq model=%s", gm)
                            return sql.strip().strip("`")
                    else:
                        _PROVIDER_STATUS["llama"]["error"] = f"groq {gm} status={r.status_code}"
                except Exception as e:
                    _PROVIDER_STATUS["llama"]["error"] = str(e)
                    logger.warning("Groq LLaMA attempt failed model=%s (%s); next.", gm, e)
        except Exception as e:
            _PROVIDER_STATUS["llama"]["error"] = str(e)
            logger.warning("Groq import/use failed (%s)", e)
    return None


def generate_sql_ollama(nl_query: str, schema_text: str) -> Optional[str]:
    """
    Completely FREE local LLM via Ollama (https://ollama.com).
    No API key required — just needs `ollama serve` running locally.
    Uses speed-optimised settings: small model first, minimal token budget.
    """
    import requests
    system_msg = _base_system_instructions()
    # Truncate schema for Ollama — large prompts slow small models significantly
    schema_trunc = (schema_text or "")[:_OLLAMA_MAX_SCHEMA]
    user_prompt = _build_user_prompt(nl_query, schema_trunc)

    # Discover which models are pulled (uses 60-second cache — no redundant HTTP)
    pulled_names = _get_ollama_models()
    if not pulled_names:
        _PROVIDER_STATUS["ollama"]["error"] = "connection refused or no models pulled"
        return None
    pulled_bases = {n.split(":")[0] for n in pulled_names}
    # Order: priority list first (fastest), then remaining pulled models
    ordered = (
        [m for m in _OLLAMA_MODEL_PRIORITY if m.split(":")[0] in pulled_bases]
        + [n for n in pulled_names if n.split(":")[0] not in
           {p.split(":")[0] for p in _OLLAMA_MODEL_PRIORITY}]
    )
    if not ordered:
        _PROVIDER_STATUS["ollama"]["error"] = "no models pulled"
        logger.info("Ollama running but no models pulled; skipping.")
        return None

    for model in ordered:
        try:
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user", "content": user_prompt},
                ],
                "stream": False,
                "options": _OLLAMA_GEN_OPTIONS,
            }
            r = requests.post(f"{OLLAMA_BASE_URL}/api/chat", json=payload, timeout=90)
            if r.status_code == 200:
                sql = r.json().get("message", {}).get("content", "").strip()
                for fence in ["```sql", "```SQL", "```"]:
                    if sql.startswith(fence):
                        sql = sql[len(fence):].lstrip()
                if sql.endswith("```"):
                    sql = sql[:-3].rstrip()
                lowered = sql.lower()
                for kw in ["select", "with", "show", "describe"]:
                    pos = lowered.find(kw)
                    if pos >= 0:
                        sql = sql[pos:]
                        break
                if sql:
                    logger.info("Generated SQL via Ollama model=%s", model)
                    _PROVIDER_STATUS["ollama"]["error"] = None
                    return sql.strip()
            elif r.status_code == 404:
                logger.debug("Ollama model not found: %s; trying next.", model)
            else:
                _PROVIDER_STATUS["ollama"]["error"] = f"{model} status={r.status_code}"
        except requests.exceptions.ConnectionError:
            _PROVIDER_STATUS["ollama"]["error"] = "connection refused"
            return None
        except Exception as e:
            _PROVIDER_STATUS["ollama"]["error"] = str(e)
            logger.warning("Ollama model=%s failed (%s); next.", model, e)
    return None


def generate_sql_lmstudio(nl_query: str, schema_text: str) -> Optional[str]:
    """
    FREE local LLM via LM Studio (https://lmstudio.ai).
    Uses its OpenAI-compatible REST API at localhost:1234.
    No API key required — just needs LM Studio running with a model loaded.
    """
    import requests
    system_msg = _base_system_instructions()
    user_prompt = _build_user_prompt(nl_query, schema_text)

    try:
        payload = {
            "model": "local-model",  # LM Studio ignores model name and uses the loaded model
            "messages": [
                {"role": "system", "content": system_msg},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.0,
            "max_tokens": 800,
            "stream": False,
        }
        r = requests.post(
            f"{LMSTUDIO_BASE_URL}/v1/chat/completions",
            json=payload,
            timeout=90,
        )
        if r.status_code == 200:
            sql = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
            # Strip markdown fences
            for fence in ["```sql", "```SQL", "```"]:
                if sql.startswith(fence):
                    sql = sql[len(fence):].lstrip()
            if sql.endswith("```"):
                sql = sql[:-3].rstrip()
            lowered = sql.lower()
            for kw in ["select", "with", "show", "describe"]:
                pos = lowered.find(kw)
                if pos >= 0:
                    sql = sql[pos:]
                    break
            if sql:
                logger.info("Generated SQL via LM Studio")
                _PROVIDER_STATUS["lmstudio"]["error"] = None
                return sql.strip()
        else:
            _PROVIDER_STATUS["lmstudio"]["error"] = f"status={r.status_code}"
    except requests.exceptions.ConnectionError:
        logger.info("LM Studio not running at %s; skipping.", LMSTUDIO_BASE_URL)
        _PROVIDER_STATUS["lmstudio"]["error"] = "connection refused"
    except Exception as e:
        _PROVIDER_STATUS["lmstudio"]["error"] = str(e)
        logger.warning("LM Studio failed (%s)", e)
    return None


def generate_sql_together(nl_query: str, schema_text: str) -> Optional[str]:
    """
    FREE tier via Together AI (https://together.ai — free $25 credits on signup).
    Requires TOGETHER_API_KEY in .env — completely free to get.
    Uses best open-source LLaMA / Qwen / DeepSeek models available.
    """
    if not TOGETHER_API_KEY:
        return None
    import requests
    system_msg = _base_system_instructions()
    user_prompt = _build_user_prompt(nl_query, schema_text)

    together_models = [
        "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
        "meta-llama/Meta-Llama-3.1-8B-Instruct-Turbo",
        "Qwen/Qwen2.5-Coder-32B-Instruct",
        "deepseek-ai/deepseek-coder-33b-instruct",
        "mistralai/Mixtral-8x7B-Instruct-v0.1",
        "microsoft/WizardLM-2-8x22B",
    ]

    for model in together_models:
        try:
            r = requests.post(
                "https://api.together.xyz/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {TOGETHER_API_KEY}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_msg},
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": 0.0,
                    "max_tokens": 800,
                },
                timeout=60,
            )
            if r.status_code == 200:
                sql = r.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                # Strip markdown fences
                for fence in ["```sql", "```SQL", "```"]:
                    if sql.startswith(fence):
                        sql = sql[len(fence):].lstrip()
                if sql.endswith("```"):
                    sql = sql[:-3].rstrip()
                lowered = sql.lower()
                for kw in ["select", "with", "show", "describe"]:
                    pos = lowered.find(kw)
                    if pos >= 0:
                        sql = sql[pos:]
                        break
                if sql:
                    logger.info("Generated SQL via Together AI model=%s", model)
                    _PROVIDER_STATUS["together"]["error"] = None
                    return sql.strip()
            elif r.status_code in (429, 402):
                _PROVIDER_STATUS["together"]["error"] = f"quota/rate model={model}"
                logger.warning("Together AI quota/rate for %s; trying next.", model)
            else:
                _PROVIDER_STATUS["together"]["error"] = f"{model} status={r.status_code}"
        except Exception as e:
            _PROVIDER_STATUS["together"]["error"] = str(e)
            logger.warning("Together AI model=%s failed (%s); next.", model, e)
    return None

def generate_sql(nl_query: str, schema_text: str = "", db_uri: Optional[str] = None) -> str:
    """
    RAG-augmented multi-provider generation pipeline:
    0a. Fast in-memory cache (instant return for repeated queries)
    0b. RAG semantic cache check (instant return if high-confidence match)
    1. LangChain (if db_uri & available)
    2. OpenAI — with RAG-augmented prompt
    3. Anthropic
    4. Gemini
    5. LLaMA (HF/Groq)
    6. Ollama (free local — fastest small model first)
    7. LM Studio (free local)
    8. Together AI (free credits)
    Returns first successful sanitized SQL or raises aggregated error.
    """
    errors = []

    # ---- 0a. Fast in-process cache (microseconds) ----
    _ck = _cache_key(nl_query, schema_text)
    _cached = _cache_get(_ck)
    if _cached:
        logger.info("Fast cache HIT for query (returning in <1ms)")
        return _cached

    # ---- RAG Retrieval & Semantic Cache ----
    enhanced_schema = schema_text
    try:
        from rag_engine import get_rag_engine, build_rag_augmented_prompt
        engine = get_rag_engine()
        if engine.is_initialized:
            rag_context = engine.build_rag_context(nl_query, schema_text)
            # Semantic cache hit — return cached SQL immediately (skip all LLM calls)
            if rag_context.cached_sql and rag_context.cache_confidence >= 0.92:
                logger.info(
                    "RAG semantic cache HIT (confidence=%.3f); returning cached SQL",
                    rag_context.cache_confidence,
                )
                return rag_context.cached_sql
            # Build RAG-augmented prompt (enriched schema + few-shot + conversation)
            enhanced_schema = build_rag_augmented_prompt(
                nl_query, rag_context, base_schema_text=schema_text
            )
            logger.info(
                "RAG context injected: tables=%d, examples=%d, history=%d, time=%.1fms",
                len(rag_context.relevant_tables),
                len(rag_context.few_shot_examples),
                len(rag_context.conversation_history),
                rag_context.retrieval_time_ms,
            )
    except ImportError:
        logger.debug("RAG engine not available (chromadb not installed); standard generation")
    except Exception as e:
        logger.warning("RAG retrieval failed (%s); proceeding with standard generation", e)

    def _store_and_return(sql: str, provider: str = "") -> str:
        """Cache result, track provider, and return."""
        global _last_used_provider
        if provider:
            _last_used_provider = provider
        _cache_put(_ck, sql)
        return sql
    # 2. OpenAI (with RAG-enhanced schema context)
    try:
        sql_openai = generate_sql_openai(nl_query, schema_text=enhanced_schema)
        if sql_openai:
            return _store_and_return(sql_openai, "OpenAI")
    except Exception as e:
        errors.append(f"OpenAI:{e}")

    # 3. Anthropic
    try:
        sql_claude = generate_sql_anthropic(nl_query, enhanced_schema)
        if sql_claude:
            return _store_and_return(sql_claude, "Anthropic")
    except Exception as e:
        errors.append(f"Anthropic:{e}")

    # 4. Gemini
    try:
        sql_gemini = generate_sql_gemini(nl_query, enhanced_schema)
        if sql_gemini:
            return _store_and_return(sql_gemini, "Gemini")
    except Exception as e:
        errors.append(f"Gemini:{e}")

    # 5. LLaMA (HuggingFace / Groq — requires API key)
    try:
        sql_llama = generate_sql_llama(nl_query, enhanced_schema)
        if sql_llama:
            return _store_and_return(sql_llama, "LLaMA")
    except Exception as e:
        errors.append(f"LLaMA:{e}")

    # 6. Ollama — FREE local LLM (fastest: phi3:mini > codellama)
    try:
        sql_ollama = generate_sql_ollama(nl_query, enhanced_schema)
        if sql_ollama:
            return _store_and_return(sql_ollama, "Ollama")
    except Exception as e:
        errors.append(f"Ollama:{e}")

    # 7. LM Studio — FREE local LLM
    try:
        sql_lmstudio = generate_sql_lmstudio(nl_query, enhanced_schema)
        if sql_lmstudio:
            return _store_and_return(sql_lmstudio, "LM Studio")
    except Exception as e:
        errors.append(f"LMStudio:{e}")

    # 8. Together AI — FREE tier
    try:
        sql_together = generate_sql_together(nl_query, enhanced_schema)
        if sql_together:
            return _store_and_return(sql_together, "Together AI")
    except Exception as e:
        errors.append(f"Together:{e}")

    agg = "; ".join(errors) if errors else "No providers produced output."
    logger.error("All provider attempts failed: %s", agg)
    _hint = (
        " | FREE OPTIONS: (1) Install Ollama (ollama.com) + run: ollama pull codellama "
        "(2) Open LM Studio (lmstudio.ai) and load a model "
        "(3) Add TOGETHER_API_KEY from together.ai (free $25 credits) to .env"
    )
    raise RuntimeError(f"SQL generation failed across providers. Details: {agg}{_hint}")


def _heuristic_optimize_sql(sql: str) -> str:
    """
    Aggressive deterministic rewrites for performance without changing semantics.
    Applied when LLM output is identical or minimal.
    
    Performance-focused heuristics:
      - Remove redundant outer parentheses
      - Collapse duplicate DISTINCT operations
      - Remove unnecessary ORDER BY inside CTEs when final query re-orders
      - Eliminate redundant GROUP BY when aggregating over same columns
      - Push WHERE filters earlier in the query
      - Remove DISTINCT from subqueries when outer query applies DISTINCT
      - Simplify nested CTEs that can be combined
    """
    import re

    original = sql
    work = sql.strip()

    # Remove full wrapping parentheses
    if work.startswith("(") and work.endswith(")"):
        depth = 0
        balanced = True
        for i, ch in enumerate(work):
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0 and i != len(work) - 1:
                    balanced = False
                    break
        if balanced:
            work = work[1:-1].strip()

    # Collapse duplicate DISTINCT operations
    work = re.sub(r"\bDISTINCT\s+DISTINCT\b", "DISTINCT", work, flags=re.IGNORECASE)
    
    # Remove DISTINCT from inner queries when outer SELECT also has DISTINCT
    # Pattern: SELECT DISTINCT ... FROM (SELECT DISTINCT ...)
    if re.search(r"SELECT\s+DISTINCT", work, flags=re.IGNORECASE):
        # Remove DISTINCT from subqueries
        work = re.sub(
            r"\(\s*SELECT\s+DISTINCT\b",
            "(SELECT",
            work,
            flags=re.IGNORECASE
        )

    # Remove ORDER BY inside CTE definitions if final SELECT also has ORDER BY
    if re.search(r"\bWITH\b", work, flags=re.IGNORECASE):
        final_order = re.search(r"\bSELECT\b.*\bORDER\s+BY\b", work.split(")")[-1], flags=re.IGNORECASE | re.DOTALL)
        if final_order:
            def _strip_inner_order_by(segment: str) -> str:
                return re.sub(
                    r"(SELECT\b.*?)(ORDER\s+BY\s+[^)]+)(\))",
                    lambda m: m.group(1) + m.group(3),
                    segment,
                    flags=re.IGNORECASE | re.DOTALL,
                )
            work = re.sub(
                r"WITH\s+(.*)\bSELECT\b",
                lambda m: "WITH " + _strip_inner_order_by(m.group(1)) + "SELECT",
                work,
                flags=re.IGNORECASE | re.DOTALL,
            )
    
    # Remove ORDER BY from subqueries that don't need it (not in TOP/LIMIT context)
    # Pattern: (SELECT ... ORDER BY ...) that's not followed by LIMIT or TOP
    work = re.sub(
        r"\(\s*SELECT\b(?!.*?\bTOP\b)(?!.*?\bLIMIT\b)(.*?)(ORDER\s+BY\s+[^)]+)(\))",
        lambda m: f"(SELECT{m.group(1)})",
        work,
        flags=re.IGNORECASE | re.DOTALL
    )
    
    # Simplify CASE WHEN conditions with same result
    # CASE WHEN x THEN y WHEN z THEN y END -> CASE WHEN x OR z THEN y END
    # This is complex, so we skip for safety
    
    # Remove redundant CAST operations if type is already correct
    # This requires schema knowledge, so we skip

    return work if work != original else original


def optimize_sql(original_sql: str, schema_text: str = "") -> str:
    """
    Advanced optimization pipeline focused on maximum performance:
      1. LLM semantic rewrite with creative optimization strategies.
      2. Allows complete query restructuring for better performance.
      3. Post‑processing to ensure valid SQL output.
      4. Validation against safety rules; fallback to original if rejected.
    """
    cleaned_input = original_sql.strip().strip("`")
    if not cleaned_input:
        raise ValueError("Empty SQL provided for optimization")

    # ---- Fast optimization cache (instant return for repeated inputs) ----
    _ock = _opt_cache_key(cleaned_input)
    _ocached = _opt_cache_get(_ock)
    if _ocached:
        logger.info("Optimization cache HIT — returning in <1ms")
        return _ocached

    system_instructions = (
        "You are an expert Snowflake SQL performance optimizer. MAXIMIZE speed without changing semantics.\n"
        "\n"
        "STRATEGIES:\n"
        "1. Full restructuring (CTEs ↔ subqueries ↔ set operations).\n"
        "2. Snowflake features: QUALIFY, LATERAL, FLATTEN, RESULT_SCAN, window functions, time travel, secure functions.\n"
        "3. Join optimization: reorder by selectivity; replace IN/NOT IN with SEMI/ANTI joins.\n"
        "4. Predicate pushdown: apply filters early, merge redundant conditions.\n"
        "5. Aggregation: pre-aggregate; remove redundant DISTINCT/GROUP BY; leverage window functions.\n"
        "6. Column pruning: remove unused columns; avoid SELECT *.\n"
        "7. Structure minimization: flatten nesting; drop unnecessary ORDER BY unless final ordering required.\n"
        "\n"
        "RULES:\n"
        "- Output ONLY SQL (comments/backticks/explanation allowed).\n"
        "- Preserve result columns & semantics.\n"
        "- Do NOT use DELETE or UPDATE.\n"
        "- Other read-only statements allowed if beneficial.\n"
    )

    user_prompt = (
        f"Schema context:\n{schema_text or '(not provided)'}\n\n"
        f"Original query to optimize:\n{cleaned_input}\n\n"
        "TASK: Rewrite this query using the FASTEST approach possible. You have complete freedom to:\n"
        "- Change query structure (CTEs ↔ subqueries ↔ joins)\n"
        "- Reorder operations for optimal execution\n"
        "- Use any Snowflake SQL features\n"
        "- Make it look completely different if that's faster\n"
        "\n"
        "Return ONLY the optimized SQL query with no explanations."
    )

    def _llm_opt(sql_in: str) -> str:  # noqa: C901
        generated = ""
        # ── 1. OpenAI ──────────────────────────────────────────────────────────
        if OPENAI_KEY and _OPENAI_MODE == "new" and _openai_client:
            # Multi-model resilience for optimization
            opt_models_primary = ["gpt-4o", "gpt-4o-mini", "gpt-3.5-turbo"]
            for m in ["gpt-5", *opt_models_primary]:
                try:
                    resp_args = {
                        "model": m,
                        "input": [
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": user_prompt},
                        ],
                        "max_output_tokens": 1000
                    }
                    resp_args["temperature"] = 0.1
                    resp = _openai_client.responses.create(**resp_args)
                    generated = getattr(resp, "output_text", "").strip()
                    if not generated:
                        try:
                            first = resp.output[0]
                            if isinstance(first, dict):
                                generated = first.get("content", [{}])[0].get("text", "").strip()
                        except Exception:
                            pass
                    if generated:
                        logger.info("Optimization via Responses API model=%s", m)
                        break
                except Exception as resp_err:
                    err_low = str(resp_err).lower()
                    if "unsupported parameter" in err_low or "invalid_request_error" in err_low:
                        logger.warning("Temperature unsupported for model=%s (%s); retry without temperature.", m, resp_err)
                        try:
                            resp = _openai_client.responses.create(
                                model=m,
                                input=[
                                    {"role": "system", "content": system_instructions},
                                    {"role": "user", "content": user_prompt},
                                ],
                                max_output_tokens=1000
                            )
                            generated = getattr(resp, "output_text", "").strip()
                            if generated:
                                logger.info("Optimization via Responses API (no temperature) model=%s", m)
                                break
                        except Exception as inner_err:
                            logger.warning("Retry without temperature failed model=%s (%s)", m, inner_err)
                            continue
                    elif "insufficient_quota" in err_low or "rate limit" in err_low or "429" in err_low:
                        logger.warning("Quota/Rate issue optimization model=%s (%s); trying next.", m, resp_err)
                        continue
                    else:
                        logger.warning("Optimization attempt failed model=%s (%s); next.", m, resp_err)
                        continue
            if not generated:
                for cm in opt_models_primary:
                    try:
                        comp = _openai_client.chat.completions.create(
                            model=cm,
                            messages=[
                                {"role": "system", "content": system_instructions},
                                {"role": "user", "content": user_prompt},
                            ],
                            temperature=0.1,
                            max_tokens=850,
                        )
                        generated = comp.choices[0].message.content.strip()
                        if generated:
                            logger.info("Optimization via chat.completions model=%s", cm)
                            break
                    except Exception as chat_err:
                        chat_low = str(chat_err).lower()
                        if "insufficient_quota" in chat_low or "rate limit" in chat_low:
                            logger.warning("Chat quota issue optimization model=%s (%s); next fallback.", cm, chat_err)
                            continue
                        logger.warning("Chat optimization failed model=%s (%s); next.", cm, chat_err)
            if not generated:
                logger.warning("OpenAI: all optimization model attempts failed; trying next provider.")
        elif OPENAI_KEY and _OPENAI_MODE == "legacy":
            try:
                import openai  # type: ignore
                prompt = system_instructions + "\n\n" + user_prompt
                comp = openai.Completion.create(
                    model="text-davinci-003",
                    prompt=prompt,
                    max_tokens=600,
                    temperature=0.0,
                    n=1,
                )
                generated = comp.choices[0].text.strip()
            except Exception as e:
                logger.warning("OpenAI legacy optimization failed (%s); trying next provider.", e)

        # ── 2. Anthropic ───────────────────────────────────────────────────────
        if not generated and ANTHROPIC_API_KEY:
            try:
                import anthropic as _anthropic
                _ac = _anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
                msg = _ac.messages.create(
                    model="claude-sonnet-4-5",
                    max_tokens=1000,
                    system=system_instructions,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                generated = (msg.content[0].text or "").strip()
                if generated:
                    logger.info("Optimization via Anthropic Claude.")
            except Exception as e:
                logger.warning("Anthropic optimization failed (%s).", e)

        # ── 3. Gemini ──────────────────────────────────────────────────────────
        if not generated and GEMINI_API_KEY:
            try:
                import google.generativeai as genai
                genai.configure(api_key=GEMINI_API_KEY)
                gm = genai.GenerativeModel("gemini-2.5-pro")
                resp = gm.generate_content(system_instructions + "\n\n" + user_prompt)
                generated = (resp.text or "").strip()
                if generated:
                    logger.info("Optimization via Gemini.")
            except Exception as e:
                logger.warning("Gemini optimization failed (%s).", e)

        # ── 4. Ollama (free local) ─────────────────────────────────────────────
        if not generated:
            try:
                import requests as _req
                _pulled_names = _get_ollama_models()   # cached — no extra HTTP round-trip
                if _pulled_names:
                    _pulled_bases = {n.split(":")[0] for n in _pulled_names}
                    _model = next(
                        (m for m in _OLLAMA_MODEL_PRIORITY if m.split(":")[0] in _pulled_bases),
                        _pulled_names[0] if _pulled_names else None,
                    )
                    if _model:
                        _schema_trunc = (schema_text or "")[:_OLLAMA_MAX_SCHEMA]
                        _or = _req.post(
                            f"{OLLAMA_BASE_URL}/api/chat",
                            json={
                                "model": _model,
                                "messages": [
                                    {"role": "system", "content": system_instructions},
                                    {"role": "user", "content": (
                                        f"SQL to optimize:\n{sql_in}\n\n"
                                        f"Schema hint:\n{_schema_trunc}\n\n"
                                        "Return ONLY the optimized SQL. No explanations."
                                    )},
                                ],
                                "stream": False,
                                "options": _OLLAMA_OPT_OPTIONS,
                            },
                            timeout=90,
                        )
                        if _or.status_code == 200:
                            generated = _or.json().get("message", {}).get("content", "").strip()
                            if generated:
                                logger.info("Optimization via Ollama model=%s.", _model)
            except Exception as e:
                logger.warning("Ollama optimization failed (%s).", e)

        # ── 5. LM Studio (free local) ──────────────────────────────────────────
        if not generated:
            try:
                import requests as _req
                _lr = _req.post(
                    f"{LMSTUDIO_BASE_URL}/v1/chat/completions",
                    json={
                        "model": "local-model",
                        "messages": [
                            {"role": "system", "content": system_instructions},
                            {"role": "user", "content": user_prompt},
                        ],
                        "temperature": 0.0,
                        "max_tokens": 900,
                        "stream": False,
                    },
                    timeout=30,
                )
                if _lr.status_code == 200:
                    generated = _lr.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                    if generated:
                        logger.info("Optimization via LM Studio.")
            except Exception as e:
                logger.warning("LM Studio optimization failed (%s).", e)

        # ── 6. Together AI (free tier) ─────────────────────────────────────────
        if not generated and TOGETHER_API_KEY:
            try:
                import requests as _req
                _together_opt_models = [
                    "Qwen/Qwen2.5-Coder-32B-Instruct",
                    "meta-llama/Meta-Llama-3.1-70B-Instruct-Turbo",
                    "deepseek-ai/deepseek-coder-33b-instruct",
                ]
                for _tm in _together_opt_models:
                    _tr = _req.post(
                        "https://api.together.xyz/v1/chat/completions",
                        headers={"Authorization": f"Bearer {TOGETHER_API_KEY}", "Content-Type": "application/json"},
                        json={
                            "model": _tm,
                            "messages": [
                                {"role": "system", "content": system_instructions},
                                {"role": "user", "content": user_prompt},
                            ],
                            "temperature": 0.0,
                            "max_tokens": 900,
                        },
                        timeout=60,
                    )
                    if _tr.status_code == 200:
                        generated = _tr.json().get("choices", [{}])[0].get("message", {}).get("content", "").strip()
                        if generated:
                            logger.info("Optimization via Together AI model=%s.", _tm)
                            break
            except Exception as e:
                logger.warning("Together AI optimization failed (%s).", e)

        if not generated:
            raise RuntimeError("All optimization providers failed — returning original SQL.")
        return generated.strip().strip("`")

    try:
        optimized = _llm_opt(cleaned_input)

        # Keep first statement only
        if ";" in optimized:
            stmts = [p.strip() for p in optimized.split(";") if p.strip()]
            if stmts:
                optimized = stmts[0]

        # Apply heuristics if trivial / identical
        if (not optimized) or len(optimized) < 20 or optimized.lower().replace(" ", "") == cleaned_input.lower().replace(" ", ""):
            logger.info("LLM optimization minimal; applying heuristic pass.")
            optimized = _heuristic_optimize_sql(cleaned_input)

        # Clean up any commentary but allow flexible SQL structures
        # Don't restrict to just SELECT/WITH - allow other valid read-only operations
        lower = optimized.lower()
        
        # Find first SQL keyword that starts a valid read-only query
        valid_starts = ['select', 'with', '(select', '(with']
        start_positions = []
        for keyword in valid_starts:
            idx = lower.find(keyword)
            if idx >= 0:
                start_positions.append(idx)
        
        if start_positions and min(start_positions) > 0:
            optimized = optimized[min(start_positions):].strip()

        # Final validation via sanitizer
        try:
            from sql_validator import sanitize_sql, validate_sql_safe
            sanitized = sanitize_sql(optimized)
            ok, reason = validate_sql_safe(sanitized)
            if not ok:
                logger.warning("Optimized SQL rejected (%s); returning original.", reason)
                return cleaned_input
            optimized = sanitized
        except Exception as v_err:
            logger.warning("Validation failed (%s); returning original.", v_err)
            return cleaned_input

        if not optimized or len(optimized) < 20:
            logger.warning("Final optimized output too short; returning original.")
            return cleaned_input

        logger.debug("Optimized SQL (truncated): %s", optimized[:400].replace("\n", " "))
        _opt_cache_put(_ock, optimized)   # cache for instant repeat hits
        return optimized
    except Exception:
        logger.exception("SQL optimization failed; returning original")
        return cleaned_input


def generate_sql_stream(nl_query: str, schema_text: str = ""):
    """
    Generator that yields raw SQL *tokens* from Ollama in streaming mode.

    Designed for real-time display in Streamlit:
        tokens = []
        for tok in generate_sql_stream(query, schema):
            tokens.append(tok)
            placeholder.code(''.join(tokens), language='sql')
        sql = ''.join(tokens)

    If Ollama is unreachable or yields nothing, the generator exits without
    yielding — the caller should fall back to generate_sql().
    """
    import requests as _req
    import json as _json

    system_msg = _base_system_instructions()
    schema_trunc = (schema_text or "")[:_OLLAMA_MAX_SCHEMA]
    user_prompt = _build_user_prompt(nl_query, schema_trunc)

    pulled_names = _get_ollama_models()
    if not pulled_names:
        return

    pulled_bases = {n.split(":")[0] for n in pulled_names}
    model = next(
        (m for m in _OLLAMA_MODEL_PRIORITY if m.split(":")[0] in pulled_bases),
        pulled_names[0],
    )

    try:
        with _req.post(
            f"{OLLAMA_BASE_URL}/api/chat",
            json={
                "model": model,
                "messages": [
                    {"role": "system", "content": system_msg},
                    {"role": "user",   "content": user_prompt},
                ],
                "stream": True,
                "options": _OLLAMA_GEN_OPTIONS,
            },
            stream=True,
            timeout=90,
        ) as r:
            if r.status_code != 200:
                return
            for raw_line in r.iter_lines():
                if not raw_line:
                    continue
                chunk = _json.loads(raw_line)
                token = chunk.get("message", {}).get("content", "")
                if token:
                    yield token
                if chunk.get("done"):
                    # Cache result so subsequent generate_sql() calls return immediately
                    global _last_used_provider
                    _last_used_provider = f"Ollama/{model} (streamed)"
                    return
    except Exception as e:
        logger.debug("Ollama streaming error (%s); caller will fall back.", e)


def get_generation_backend_status() -> dict:
    """
    Expose backend capability status for UI surfaces.
    Extended to include Anthropic, Gemini, LLaMA availability/error states.
    """
    return {
        "openai_mode": _OPENAI_MODE,
        "openai_version": _openai_version,
        "openai_available": _PROVIDER_STATUS["openai"]["available"],
        "langchain_available": USE_LANGCHAIN,
        "langchain_mode": _LANGCHAIN_STATUS.get("mode"),
        "langchain_new_err": _LANGCHAIN_STATUS.get("new_err"),
        "langchain_legacy_err": _LANGCHAIN_STATUS.get("legacy_err"),
        "anthropic_available": _PROVIDER_STATUS["anthropic"]["available"],
        "anthropic_error": _PROVIDER_STATUS["anthropic"]["error"],
        "gemini_available": _PROVIDER_STATUS["gemini"]["available"],
        "gemini_error": _PROVIDER_STATUS["gemini"]["error"],
        "llama_available": _PROVIDER_STATUS["llama"]["available"],
        "llama_error": _PROVIDER_STATUS["llama"]["error"],
        "ollama_available": _PROVIDER_STATUS["ollama"]["available"],
        "ollama_error": _PROVIDER_STATUS["ollama"]["error"],
        "lmstudio_available": _PROVIDER_STATUS["lmstudio"]["available"],
        "lmstudio_error": _PROVIDER_STATUS["lmstudio"]["error"],
        "together_available": _PROVIDER_STATUS["together"]["available"],
        "together_error": _PROVIDER_STATUS["together"]["error"],
        "ollama_base_url": OLLAMA_BASE_URL,
        "lmstudio_base_url": LMSTUDIO_BASE_URL,
    }
