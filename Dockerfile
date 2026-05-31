# ============================================================
# SolidWorks Plagiarism Checker — Docker Image
# ============================================================
# Runs the web app only (no SolidWorks COM API in containers).
# Uses OLE metadata fallback for file analysis.
#
# Build:  docker build -t sw-plagiarism-checker .
# Run:    docker run -p 8000:8000 sw-plagiarism-checker
# ============================================================

FROM python:3.12-slim

LABEL maintainer="siyad23"
LABEL description="SolidWorks Plagiarism Checker Web App"

# System deps
RUN apt-get update && \
    apt-get install -y --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY pyproject.toml README.md ./
COPY src/ ./src/
COPY cli/ ./cli/
COPY web/ ./web/

RUN pip install --no-cache-dir -e ".[web]"

# Create directories
RUN mkdir -p /app/web/uploads /app/web/reports

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/')" || exit 1

# Run
CMD ["uvicorn", "web.app:app", "--host", "0.0.0.0", "--port", "8000"]
