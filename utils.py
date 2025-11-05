# utils.py
import logging
import os
from dotenv import load_dotenv

load_dotenv()

def setup_logging(name="genai_sql_agent"):
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logger = logging.getLogger(name)
    logger.setLevel(level)
    if not logger.handlers:
        fmt = '%(asctime)s | %(levelname)s | %(name)s | %(message)s'
        ch = logging.StreamHandler()
        ch.setFormatter(logging.Formatter(fmt))
        logger.addHandler(ch)

        # file handler
        fh = logging.FileHandler("genai_sql_agent.log")
        fh.setFormatter(logging.Formatter(fmt))
        logger.addHandler(fh)
    return logger

logger = setup_logging()

def get_env(key, default=None):
    val = os.getenv(key, default)
    return val
