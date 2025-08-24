#!/bin/bash
# Exit immediately if a command exits with a non-zero status.
set -e

# Print the port the app will run on for debugging purposes
echo "STARTING SERVER ON PORT: $PORT"

# Start the Gunicorn server
# This command is more robust for production environments
exec gunicorn --worker-class gevent --workers 1 --threads 8 --timeout 120 --bind 0.0.0.0:$PORT app:app
