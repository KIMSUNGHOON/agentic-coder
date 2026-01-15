# Agentic 2.0 Production Dockerfile
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Install system dependencies
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN useradd -m -u 1000 agentic && \
    chown -R agentic:agentic /app

# Copy requirements
COPY --chown=agentic:agentic requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY --chown=agentic:agentic . .

# Create necessary directories
RUN mkdir -p /app/logs /app/data /app/workspace && \
    chown -R agentic:agentic /app/logs /app/data /app/workspace

# Switch to non-root user
USER agentic

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "from production import HealthChecker; import asyncio; checker = HealthChecker(); print(asyncio.run(checker.check_all()))"

# Expose ports
EXPOSE 8080

# Default command
CMD ["python", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
