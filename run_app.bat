@echo off
REM NephroScan startup script - starts the Flask app (API + SPA)

echo ========================================
echo   NephroScan - CKD Clinical Diagnosis System
echo ========================================
echo.

if exist "ckdenv\Scripts\activate.bat" (
    echo Activating virtual environment...
    call ckdenv\Scripts\activate.bat
) else (
    echo Warning: Virtual environment not found. Using system Python.
)

echo.
echo Starting Flask server at http://127.0.0.1:5000 ...
start "NephroScan" cmd /k "cd /d %~dp0Frontend && python app.py"

timeout /t 5 /nobreak >nul
start http://127.0.0.1:5000

echo.
echo Press any key to exit this window...
pause >nul
