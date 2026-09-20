FROM python:3.11-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8501
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 CMD python -c "import urllib.request; urllib.request.urlopen(\"http://127.0.0.1:8501/_stcore/health\", timeout=3)"
CMD ["streamlit","run","app.py","--server.address=0.0.0.0","--server.port=8501","--server.headless=true"]
