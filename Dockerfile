# Use an official, lightweight Python 3.11 image
FROM python:3.11-slim

# System deps: certs for HTTPS, and clean up apt cache
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates curl \
  && rm -rf /var/lib/apt/lists/*

# Python runtime hygiene
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

# Workdir
WORKDIR /app

# Install deps first (better layer caching)
COPY requirements.txt .
RUN python -m pip install --upgrade pip \
  && pip install --no-cache-dir --prefer-binary -r requirements.txt

# Copy the rest of the app
COPY . .

# Create a non-root user and switch
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Railway provides PORT
EXPOSE 8080

# Healthcheck (Railway also has its own, but this helps Docker/local)
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD curl -fsS http://127.0.0.1:${PORT:-8080}/ || exit 1

# Gunicorn: 1 worker + 2 threads keeps memory low; 60s timeout is sane on PaaS
# Bind to Railway's PORT (fallback to 8080 for local dev)
CMD gunicorn app:app \
  --bind 0.0.0.0:${PORT:-8080} \
  --workers 1 \
  --threads 2 \
  --timeout 60 \
  --keep-alive 15
