#!/usr/bin/env bash
set -e

echo "================================================================="
echo "  Starting InfraSight Service (Simulated Environment)"
echo "================================================================="

# Initialize SQLite database schema
python -c "from backend.storage import init_db; init_db()"

# Start FastAPI backend in background on internal port
echo "[*] Launching FastAPI backend on 0.0.0.0:${BACKEND_PORT:-8000}..."
uvicorn backend.main:app --host 0.0.0.0 --port "${BACKEND_PORT:-8000}" &
BACKEND_PID=$!

# Wait for backend health check
echo "[*] Waiting for backend to become healthy..."
for i in $(seq 1 30); do
    if curl -s "http://127.0.0.1:${BACKEND_PORT:-8000}/health" | grep -q "ok"; then
        echo "[+] Backend healthy!"
        break
    fi
    sleep 1
done

# Start Streamlit frontend on public port (default 7860 for Hugging Face Spaces)
FRONTEND_PORT=${PORT:-7860}
echo "[*] Launching Streamlit frontend on 0.0.0.0:${FRONTEND_PORT}..."
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT:-8000}" streamlit run frontend/app.py \
    --server.port "${FRONTEND_PORT}" \
    --server.address 0.0.0.0 \
    --server.headless true \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false &
FRONTEND_PID=$!

# Handle shutdown signals gracefully
trap "kill -TERM $BACKEND_PID $FRONTEND_PID 2>/dev/null" SIGTERM SIGINT

wait -n
