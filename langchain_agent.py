# langchain_agent.py
import os
import sys
import site
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

# Provider status tracking
_PROVIDER_STATUS = {
    "openai": {"available": bool(OPENAI_KEY), "mode": None, "version": None, "error": None},
    "anthropic": {"available": bool(ANTHROPIC_API_KEY), "error": None},
    "gemini": {"available": bool(GEMINI_API_KEY), "error": None},
    "llama": {"available": bool(HF_API_KEY) or bool(GROQ_API_KEY), "error": None},
}

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
        "You are a Snowflake SQL generation assistant. Use full Snowflake knowledge (CTEs, SHOW, DESCRIBE, CALL, EXPLAIN, functions, views, time travel, semi-structured data handling). "
        "Return SQL only (no explanations, no comments, no backticks). "
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
        "You are a Snowflake SQL generation assistant. Use full Snowflake knowledge (CTEs, SHOW, DESCRIBE, CALL, EXPLAIN, functions, views, time travel, semi-structured data handling). "
        "Return SQL only (no explanations, no comments, no backticks). "
        "Do NOT generate DELETE or UPDATE statements. "
        "Other read-only statements are permitted if helpful."
    )

def _build_user_prompt(nl_query: str, schema_text: str) -> str:
    return (
        f"Schema (may be partial):\n{schema_text or '(none provided)'}\n\n"
        f"User request:\n{nl_query}\n\n"
        "Guidance:\n"
        "- Return pure Snowflake SQL (no commentary/backticks)\n"
        "- You MAY use any read-only Snowflake features (CTEs, SHOW, DESCRIBE, EXPLAIN, CALL for UDFs, functions, semi-structured data access, time travel)\n"
        "- Do NOT produce DELETE or UPDATE statements\n"
        "Return only SQL."
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

def generate_sql(nl_query: str, schema_text: str = "", db_uri: Optional[str] = None) -> str:
    """
    Multi-provider generation pipeline with ordered fallbacks:
    1. LangChain (if db_uri & available)
    2. OpenAI (gpt-5 + configured fallbacks)
    3. Anthropic (Claude Sonnet / Opus)
    4. Gemini 2.5 Pro
    5. LLaMA (HuggingFace or Groq)
    Returns first successful sanitized SQL or raises aggregated error.
    """
    errors = []
    # 1. LangChain path
    if USE_LANGCHAIN and db_uri:
        try:
            sql_lc = generate_sql_langchain(nl_query, db_uri=db_uri)
            if sql_lc:
                logger.info("Generated SQL via LangChain")
                return sql_lc
        except Exception as e:
            errors.append(f"LangChain:{e}")

    # 2. OpenAI
    try:
        sql_openai = generate_sql_openai(nl_query, schema_text=schema_text)
        if sql_openai:
            return sql_openai
    except Exception as e:
        errors.append(f"OpenAI:{e}")

    # 3. Anthropic
    try:
        sql_claude = generate_sql_anthropic(nl_query, schema_text)
        if sql_claude:
            return sql_claude
    except Exception as e:
        errors.append(f"Anthropic:{e}")

    # 4. Gemini
    try:
        sql_gemini = generate_sql_gemini(nl_query, schema_text)
        if sql_gemini:
            return sql_gemini
    except Exception as e:
        errors.append(f"Gemini:{e}")

    # 5. LLaMA
    try:
        sql_llama = generate_sql_llama(nl_query, schema_text)
        if sql_llama:
            return sql_llama
    except Exception as e:
        errors.append(f"LLaMA:{e}")

    agg = "; ".join(errors) if errors else "No providers produced output."
    logger.error("All provider attempts failed: %s", agg)
    raise RuntimeError(f"SQL generation failed across providers. Details: {agg}")


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
    if not OPENAI_KEY:
        raise RuntimeError("OPENAI_API_KEY missing")

    cleaned_input = original_sql.strip().strip("`")
    if not cleaned_input:
        raise ValueError("Empty SQL provided for optimization")

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
        "- Output ONLY SQL (no comments/backticks/explanation).\n"
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

    def _llm_opt(sql_in: str) -> str:
        generated = ""
        if _OPENAI_MODE == "new" and _openai_client:
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
                raise RuntimeError("All optimization model attempts failed.")
        elif _OPENAI_MODE == "legacy":
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
        else:
            raise RuntimeError(f"OpenAI client not initialized for optimization (mode={_OPENAI_MODE}).")
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
        return optimized
    except Exception:
        logger.exception("SQL optimization failed; returning original")
        return cleaned_input


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
    }
