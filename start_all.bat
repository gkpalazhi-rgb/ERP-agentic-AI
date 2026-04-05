@echo off
echo ============================================
echo   Starting ERP Agent - All Services
echo ============================================
echo.


:: Start FastAPI backend with Uvicorn
echo [2/3] Starting Uvicorn backend...
start "Uvicorn Backend" cmd /k "cd /d %~dp0 && .venv\Scripts\activate && uvicorn app.main:app --reload"

:: Start Frontend dev server
echo [3/3] Starting Frontend dev server...
start "Frontend Dev" cmd /k "cd /d %~dp0frontend && npm run dev"

echo.
echo ============================================
echo   All services launched in separate windows!
echo ============================================
echo.
echo   - Backend:  Running in "Uvicorn Backend" window
echo   - Frontend: Running in "Frontend Dev" window
echo.
echo   Opening frontend in browser in 5 seconds...
timeout /t 5 /nobreak >nul
start "" "msedge" http://localhost:5173
echo   Browser opened!
echo.
echo   Close this window or press any key to exit.
pause >nul
