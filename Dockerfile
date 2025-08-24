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

# Expose the port that Gunicorn will run on. Railway will detect this.
EXPOSE 8000

# The command to run your application using Gunicorn, a production-ready server
# We increase the timeout to 120 seconds to handle long-running analyses.
CMD ["gunicorn", "--bind", "0.0.0.0:8000", "--timeout", "120", "app:app"]
