# Use an official, lightweight Python 3.11 image as a starting point
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Copy the requirements file into the container first
COPY requirements.txt .

# Install the Python dependencies listed in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of your application's code into the container
COPY . .

# The command to run your application using Gunicorn, a production-ready server
# This version correctly uses the $PORT variable provided by Railway.
# We also keep the increased timeout to handle long-running analyses.
CMD ["gunicorn", "--bind", "0.0.0.0:$PORT", "--timeout", "120", "app:app"]
