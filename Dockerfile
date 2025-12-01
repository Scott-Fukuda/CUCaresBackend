# # Use official Python image
# FROM python:3.11-slim

# # Prevent Python from buffering logs
# ENV PYTHONUNBUFFERED=1
# ENV PYTHONPATH=/app

# # Create working directory
# WORKDIR /app

# # Install system deps
# RUN apt-get update && apt-get install -y \
#     build-essential \
#     libpq-dev \
#     && rm -rf /var/lib/apt/lists/*

# # Copy and install dependencies
# COPY requirements.txt .
# RUN pip install --no-cache-dir -r requirements.txt

# # Copy ALL files from context root
# COPY . /app/

# # Verify what was copied
# RUN ls -la /app/ && echo "---" && ls -la /app/worker/ && echo "---" && ls -la /app/*.py

# # Start Celery worker
# CMD ["celery", "-A", "worker.tasks", "worker", "--loglevel=INFO"]

# Use a Python base image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Copy your code
COPY . /app

# Install dependencies
RUN python -m pip install --no-cache-dir -r requirements.txt

# Set the start command for Fly.io
CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1"]

