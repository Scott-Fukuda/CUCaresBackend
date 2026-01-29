FROM python:3.11-slim

WORKDIR /app

# Copy everything from build context (parent directory)
COPY . /app/

# Debug: show directory structure
RUN echo "=== /app contents ===" && ls -la /app/ && \
    echo "=== Looking for requirements.txt files ===" && \
    find /app -name "requirements.txt" -type f

# Install dependencies from the main requirements.txt (in root)
RUN pip install --no-cache-dir -r /app/requirements.txt

# Verify app.py exists
RUN ls -la /app/app.py || (echo "ERROR: app.py not found!" && exit 1)

CMD ["gunicorn", "app:app", "--bind", "0.0.0.0:8080", "--workers", "1"]