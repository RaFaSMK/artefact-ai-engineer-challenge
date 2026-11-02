# Mantém src/ em /app: Settings resolve dados e interface a partir desse caminho.
FROM python:3.12-slim AS app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

COPY requirements-lock.txt ./
RUN python -m pip install --no-cache-dir -r requirements-lock.txt

COPY pyproject.toml ./
COPY src/ ./src/
COPY web/ ./web/
COPY data/ ./data/
RUN python -m pip install --no-cache-dir --no-deps -e . \
    && useradd --create-home --uid 10001 emporio \
    && mkdir runtime \
    && chown emporio:emporio runtime

USER emporio
EXPOSE 8765
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).close()"

# 0.0.0.0 é necessário dentro do contêiner; Compose publica só no loopback do host.
CMD ["python", "-m", "uvicorn", "emporio.api:create_app", "--factory", "--host", "0.0.0.0", "--port", "8765"]

FROM app AS test
COPY tests/ ./tests/
CMD ["python", "-m", "pytest", "-q", "-p", "no:cacheprovider"]

FROM app AS runtime
