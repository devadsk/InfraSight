# InfraSight - Production Container Image (Simulated Environment)
FROM python:3.11-slim

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    BACKEND_PORT=8000 \
    STREAMLIT_SERVER_HEADLESS=true

# Install curl for container health check
RUN apt-get update && apt-get install -y --no-install-recommends curl bash && rm -rf /var/lib/apt/lists/*

# Install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user with UID 1000 for Hugging Face Spaces compatibility
RUN useradd -m -u 1000 user

# Copy application source code
COPY --chown=user:user . .

# Ensure runtime directories exist and have proper permissions for user 1000
RUN mkdir -p data/images/uploads eval/cache/meta_api eval/replay docs/screenshots && \
    chown -R user:user /app && \
    chmod -R 775 /app/data /app/eval

# Ensure script execution permissions
RUN chmod +x scripts/start.sh

# Switch to non-root user
USER user

# Expose unified ports (7860 for HF Spaces / Streamlit)
EXPOSE 7860 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://127.0.0.1:8000/health || exit 1

ENTRYPOINT ["/bin/bash", "scripts/start.sh"]
