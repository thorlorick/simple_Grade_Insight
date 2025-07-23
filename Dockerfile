# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Set work directory
WORKDIR /app

# Install system dependencies required for psycopg2 and compilation
# REMOVE Caddy-specific installation commands from here.
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    # Removed Caddy-related installations (curl, gnupg, caddy apt-get install)
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker cache
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY app/ .

# Create non-root user for security
RUN useradd --create-home --shell /bin/bash app \
    && chown -R app:app /app

# Switch to non-root user
USER app

# Expose port 8081 for internal communication within the Docker network.
# This port will be accessed by the Caddy service.
EXPOSE 8081

# Health check for your Uvicorn application.
# It should check Uvicorn's internal port.
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://127.0.0.1:8081/')" || exit 1

# Command to run ONLY your Uvicorn application.
# Bind Uvicorn to 0.0.0.0 to make it accessible from other containers in the Docker network.
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8081"]
