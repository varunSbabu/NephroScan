@echo off
REM CKD Prediction System Startup Script
REM This script starts both the Flask API and Streamlit frontend

echo ========================================
echo   CKD Clinical Diagnosis System
echo ========================================
echo.

REM Check if virtual environment exists
if exist "ckdenv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ckdenv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found. Using system Python.
)

echo.
echo Starting Flask API server...
echo.

REM Start Flask API in background
start "Flask API" cmd /k "cd /d %~dp0Frontend && python app.py"

REM Wait for Flask to start
timeout /t 3 /nobreak >nul

echo Starting Streamlit frontend...
echo.

REM Start Streamlit frontend
start "Streamlit Frontend" cmd /k "cd /d %~dp0Frontend && streamlit run streamlit_app.py --server.port 8501"

echo.
echo ========================================
echo   Both servers are starting...
echo ========================================
echo.
echo   Flask API:     http://127.0.0.1:5000
echo   Streamlit UI:  http://127.0.0.1:8501
echo.
echo   Login Credentials:
echo   Username: admin
echo   Password: admin123
echo.
echo ========================================

REM Open browser after a short delay
timeout /t 5 /nobreak >nul
start http://127.0.0.1:8501

echo.
echo Press any key to exit this window...
pause >nul
