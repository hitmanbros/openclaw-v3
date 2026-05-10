FROM python:3.12-slim

WORKDIR /app

# Install git (needed for GitHub operations)
RUN apt-get update && apt-get install -y --no-install-recommends \
    git \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY openclaw/ ./openclaw/
COPY agents/ ./agents/
COPY config.yaml .

# Create data directory
RUN mkdir -p /data/projects

# Run as non-root
USER 1000:1000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health')" || exit 1

EXPOSE 8080

CMD ["python", "-m", "openclaw"]
