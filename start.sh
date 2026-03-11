#!/bin/bash
set -e

# Kill any background processes if script is killed
trap "kill 0" SIGINT

echo "Starting ERP Agent System..."

# Start FastAPI backend in the background
echo "Starting Backend (FastAPI)..."
cd "ERP-agentic-AI-review2"
# assuming uvicorn is available via the virtual environment
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

# Start Vite frontend in the background
echo "Starting Frontend (Vite)..."
cd "../project 2"
npm run dev -- --host 127.0.0.1 --port 5173 &
FRONTEND_PID=$!

echo "Both systems started!"
echo "Backend running on http://127.0.0.1:8000"
echo "Frontend running on http://127.0.0.1:5173"
echo "Press Ctrl+C to stop both servers."

# Wait for background processes
wait $BACKEND_PID $FRONTEND_PID
