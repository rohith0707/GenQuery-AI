# snowflake_client.py
import pandas as pd
import snowflake.connector
from snowflake.connector.errors import ProgrammingError, DatabaseError, InterfaceError, OperationalError, HttpError
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type
from utils import get_env, logger
import difflib  # for suggesting closest table names when object not found

# Collect Snowflake parameters once (reloaded at import)
SF_PARAMS = dict(
    user=get_env("SNOWFLAKE_USER"),
    password=get_env("SNOWFLAKE_PASSWORD"),
    account=get_env("SNOWFLAKE_ACCOUNT"),
    warehouse=get_env("SNOWFLAKE_WAREHOUSE"),
    database=get_env("SNOWFLAKE_DATABASE"),
    schema=get_env("SNOWFLAKE_SCHEMA"),
    role=get_env("SNOWFLAKE_ROLE"),
)
MAX_ROWS = int(get_env("MAX_QUERY_ROWS", "5000"))

PLACEHOLDER_STRINGS = {
    "SNOWFLAKE_ACCOUNT": ["your_account_region", "xyz123.region"],
    "SNOWFLAKE_USER": ["readonly_user"],
    "SNOWFLAKE_PASSWORD": ["your_password"],
}

def validate_snowflake_config() -> None:
    """
    Validate env configuration early and raise a descriptive error for the UI.
    """
    missing = [k for k, v in SF_PARAMS.items() if k in ("user", "password", "account") and (v is None or v == "")]
    if missing:
        raise ValueError(
            "Missing required Snowflake environment variables: "
            + ", ".join(missing)
        )

    placeholder_hits = []
    for env_name, substrings in PLACEHOLDER_STRINGS.items():
        val = get_env(env_name)
        if val is not None:
            for s in substrings:
                if val.strip() == s:
                    placeholder_hits.append(env_name)

    if placeholder_hits:
        raise ValueError(
            "Snowflake configuration still contains placeholder values for: "
            + ", ".join(placeholder_hits)
            + ". Please update your .env with real credentials."
        )

    acct = SF_PARAMS.get("account", "")
    # Basic heuristic: Snowflake account usually pattern orgname-account_locator.region.cloud
    if "your_account_region" in acct:
        raise ValueError(
            "SNOWFLAKE_ACCOUNT is set to a placeholder (your_account_region). "
            "Replace with your real account locator (e.g. abcd-xy12345.ap-south-1)."
        )

def get_connection():
    """
    Establish a Snowflake connection after validating configuration.
    """
    validate_snowflake_config()
    logger.info(
        "Opening Snowflake connection user=%s db=%s schema=%s",
        SF_PARAMS.get("user"),
        SF_PARAMS.get("database"),
        SF_PARAMS.get("schema"),
    )
    return snowflake.connector.connect(
        user=SF_PARAMS["user"],
        password=SF_PARAMS["password"],
        account=SF_PARAMS["account"],
        warehouse=SF_PARAMS.get("warehouse"),
        database=SF_PARAMS.get("database"),
        schema=SF_PARAMS.get("schema"),
        role=SF_PARAMS.get("role"),
        client_session_keep_alive=True,
    )

def _enhance_error(e: Exception) -> Exception:
    """
    Map low-level connector exceptions to clearer guidance for UI.
    Adds smart hints for common issues (missing table/object).
    """
    base_msg = str(e)

    # Account unreachable
    if isinstance(e, HttpError) and "404 Not Found" in base_msg:
        return RuntimeError(
            "Snowflake account not reachable (HTTP 404). "
            "Verify SNOWFLAKE_ACCOUNT value (format often 'orgname-account_locator.region')."
        )

    # Missing object / not authorized (ProgrammingError 002003)
    if isinstance(e, ProgrammingError) and ("002003" in base_msg or "does not exist" in base_msg):
        # Attempt to extract object name
        missing_obj = None
        if "Object '" in base_msg:
            try:
                missing_obj = base_msg.split("Object '", 1)[1].split("'", 1)[0]
            except Exception:
                missing_obj = None

        # Try to fetch existing table names for suggestions
        suggestions = ""
        try:
            conn = get_connection()
            with conn.cursor() as cs:
                db = SF_PARAMS.get("database")
                sch = SF_PARAMS.get("schema")
                filters = []
                if db:
                    filters.append(f"table_catalog = '{db}'")
                if sch:
                    filters.append(f"table_schema = '{sch}'")
                where_clause = " WHERE " + " AND ".join(filters) if filters else ""
                cs.execute(
                    "SELECT DISTINCT table_name FROM information_schema.tables"
                    f"{where_clause} ORDER BY 1 LIMIT 200"
                )
                table_rows = [r[0] for r in cs.fetchall()]
            try:
                conn.close()
            except Exception:
                pass
            if missing_obj and table_rows:
                close = difflib.get_close_matches(missing_obj, table_rows, n=5, cutoff=0.55)
                if close:
                    suggestions = f" Similar existing tables: {', '.join(close)}."
                elif table_rows:
                    # Show first few tables if no close matches
                    suggestions = f" Available tables include: {', '.join(table_rows[:8])}..."
        except Exception:
            # Silent – we keep original message if introspection fails
            pass

        hint_parts = [
            "Snowflake object not found or not authorized.",
            f"Original error: {base_msg}",
        ]
        if missing_obj:
            hint_parts.append(
                f"Check spelling, database/schema context, or privileges for '{missing_obj}'."
            )
        if suggestions:
            hint_parts.append(suggestions.strip())
        hint_parts.append("Ensure DATABASE and SCHEMA env variables match target location.")
        return RuntimeError(" ".join(hint_parts))

    if isinstance(e, ProgrammingError):
        return RuntimeError(f"Snowflake programming error: {base_msg}")
    if isinstance(e, OperationalError):
        return RuntimeError(f"Operational error: {base_msg}")
    if isinstance(e, InterfaceError):
        return RuntimeError(f"Interface error: {base_msg}")
    if isinstance(e, DatabaseError):
        return RuntimeError(f"Database error: {base_msg}")
    if isinstance(e, ValueError):
        return e  # Already user-friendly

    return RuntimeError(f"Snowflake query failed: {base_msg}")

@retry(wait=wait_exponential(min=1, max=8), stop=stop_after_attempt(2), retry=retry_if_exception_type(Exception))
def run_query(sql: str, fetch_limit: int = MAX_ROWS) -> pd.DataFrame:
    """
    Execute a read-only query with limited rows and enhanced diagnostics.
    """
    logger.info("Executing SQL (start): %s", sql[:300].replace("\n", " "))
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cs:
            cs.execute(sql)
            cols = [c[0] for c in cs.description] if cs.description else []
            rows = cs.fetchmany(fetch_limit)
            df = pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame()
            logger.info("Query executed; rows=%d", len(df))
            return df
    except Exception as e:
        enhanced = _enhance_error(e)
        logger.exception("Snowflake query failed: %s", enhanced)
        raise enhanced
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def run_query_with_timing(sql: str, fetch_limit: int = MAX_ROWS) -> tuple[pd.DataFrame, float]:
    """
    Execute a query and return both the DataFrame and execution time in seconds.
    Returns: (DataFrame, execution_time_seconds)
    """
    import time
    logger.info("Executing SQL with timing (start): %s", sql[:300].replace("\n", " "))
    conn = None
    try:
        conn = get_connection()
        with conn.cursor() as cs:
            start_time = time.time()
            cs.execute(sql)
            execution_time = time.time() - start_time
            
            cols = [c[0] for c in cs.description] if cs.description else []
            rows = cs.fetchmany(fetch_limit)
            df = pd.DataFrame(rows, columns=cols) if cols else pd.DataFrame()
            logger.info("Query executed; rows=%d, time=%.3fs", len(df), execution_time)
            return df, execution_time
    except Exception as e:
        enhanced = _enhance_error(e)
        logger.exception("Snowflake query failed: %s", enhanced)
        raise enhanced
    finally:
        if conn:
            try:
                conn.close()
            except Exception:
                pass


def get_schema_overview(max_tables: int = 40, max_cols_per_table: int = 40) -> str:
    """
    Build a schema hint string by introspecting INFORMATION_SCHEMA.COLUMNS.

    Returns multiline string like:
        table_a(id, created_at, amount, status)
        table_b(user_id, region, channel)

    Limits applied to avoid huge payloads.
    """
    try:
        conn = get_connection()
        with conn.cursor() as cs:
            # Pull columns for current database + schema (if provided)
            db = SF_PARAMS.get("database")
            sch = SF_PARAMS.get("schema")
            filters = []
            if db:
                filters.append(f"table_catalog = '{db}'")
            if sch:
                filters.append(f"table_schema = '{sch}'")
            where_clause = " WHERE " + " AND ".join(filters) if filters else ""
            sql = (
                "SELECT table_name, column_name "
                "FROM information_schema.columns"
                f"{where_clause} "
                "ORDER BY table_name, ordinal_position"
            )
            cs.execute(sql)
            rows = cs.fetchall()
        # Build mapping
        mapping = {}
        for tbl, col in rows:
            if tbl not in mapping:
                if len(mapping) >= max_tables:
                    continue
                mapping[tbl] = []
            if len(mapping[tbl]) < max_cols_per_table:
                mapping[tbl].append(col)

        lines = [f"{t}({', '.join(cols)})" for t, cols in mapping.items()]
        overview = "\n".join(lines)
        logger.info("Schema overview built; tables=%d", len(mapping))
        return overview if overview else "(no tables discovered)"
    except Exception as e:
        enhanced = _enhance_error(e)
        raise RuntimeError(f"Failed to load schema overview: {enhanced}")
