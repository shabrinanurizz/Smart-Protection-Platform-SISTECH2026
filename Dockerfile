# =====================================================================
# Dockerfile — Smart Protection Platform
# =====================================================================
# Build:  docker build -t spp-api .
# Run:    docker run -p 8000:8000 -v $(pwd)/model_registry:/app/model_registry \
#           -v $(pwd)/data:/app/data -v $(pwd)/config.yaml:/app/config.yaml spp-api
# =====================================================================

FROM python:3.13-slim

# Metadata
LABEL org.opencontainers.image.title="Smart Protection Platform"
LABEL org.opencontainers.image.description="API serving for crime risk prediction & safe commute"

# Set working directory
WORKDIR /app

# Install system dependencies (hanya yang diperlukan)
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements dan install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy seluruh project
COPY . .

# Buat directory yang diperlukan
RUN mkdir -p logs

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=60s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health')" || exit 1

# Jalankan server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
