# --platform=linux/amd64 ensures consistent behaviour on Mac (arm64), Windows, and Linux (amd64)
FROM --platform=linux/amd64 docker-local.artifactory.platform.manulife.io/gwam-docker/gwam-python:3.10-v1.0.2

# Set working directory in container
WORKDIR /app

# Set environment variables
# These prevent Python from writing pyc files and buffering stdout/stderr
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Copy requirements.txt and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy entire application to container
COPY . .

# Create necessary directories for runtime
RUN mkdir -p /app/database /app/logs

# Ensure the app user (if exists) can write to these directories
# Try to make them world-writable as fallback
RUN chmod -R a+w /app/database /app/logs || true

# Expose port 8000 (FastAPI default port)
EXPOSE 8000

# Health check (optional but recommended)
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8000/api/health')" || exit 1

# Run the application with uvicorn
CMD ["python", "-m", "uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
