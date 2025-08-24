#!/bin/bash
# Exit immediately if a command exits with a non-zero status
set -e

# Ensure PORT is set (Railway automatically provides it)
if [ -z "$PORT" ]; then
  echo "Error: PORT is not set."
  exit 1
fi

# Print debug info
echo "🚀 Starting Flask app with Gunicorn on port: $PORT"

# Start Gunicorn server
exec gunicorn \
  --worker-class gevent \
  --workers 1 \
  --threads 8 \
  --timeout 120 \
  --bind 0.0.0.0:$PORT \
  app:app
