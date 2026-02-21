"""
CKD Prediction System - Application Runner
Starts both Flask API and Streamlit frontend
"""

import subprocess
import sys
import time
import webbrowser
import os
from pathlib import Path

def main():
    """Start both Flask API and Streamlit frontend"""
    
    # Get the project root directory
    project_root = Path(__file__).parent
    frontend_dir = project_root / "Frontend"
    
    print("=" * 50)
    print("  CKD Clinical Diagnosis System")
    print("=" * 50)
    print()
    
    # Change to Frontend directory
    os.chdir(frontend_dir)
    
    print("Starting Flask API server...")
    
    # Start Flask API
    flask_process = subprocess.Popen(
        [sys.executable, "app.py"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    
    # Wait for Flask to initialize
    time.sleep(3)
    
    print("Starting Streamlit frontend...")
    
    # Start Streamlit
    streamlit_process = subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "streamlit_app.py", "--server.port", "8501"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        creationflags=subprocess.CREATE_NEW_CONSOLE if sys.platform == "win32" else 0
    )
    
    print()
    print("=" * 50)
    print("  Servers are starting...")
    print("=" * 50)
    print()
    print("  Flask API:     http://127.0.0.1:5000")
    print("  Streamlit UI:  http://127.0.0.1:8501")
    print()
    print("  Login Credentials:")
    print("  Username: admin")
    print("  Password: admin123")
    print()
    print("=" * 50)
    
    # Wait and open browser
    time.sleep(5)
    webbrowser.open("http://127.0.0.1:8501")
    
    print("\nPress Ctrl+C to stop both servers...")
    
    try:
        # Keep running until interrupted
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down servers...")
        flask_process.terminate()
        streamlit_process.terminate()
        print("Servers stopped.")


if __name__ == "__main__":
    main()
