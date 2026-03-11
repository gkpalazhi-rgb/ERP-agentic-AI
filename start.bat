@echo off
echo Starting ERP Agent System...

echo Starting Backend (FastAPI)...
start "ERP Backend" cmd /c "call .venv\Scripts\activate && uvicorn app.main:app --reload --host 127.0.0.1 --port 8000"

echo Starting Frontend (Vite)...
cd frontend
start "ERP Frontend" cmd /c "npm run dev"

echo Both systems started in new windows!
echo Backend running on http://127.0.0.1:8000
echo Frontend running on http://localhost:5173
pause
