"""
NephroScan - Application Runner
Starts the Flask app (API + SPA) and opens it in the browser.
"""

import subprocess
import sys
import time
import webbrowser
from pathlib import Path

URL = "http://127.0.0.1:5000"


def main():
    frontend_dir = Path(__file__).parent / "Frontend"

    print("=" * 50)
    print("  NephroScan - CKD Clinical Diagnosis System")
    print("=" * 50)
    print(f"\nStarting Flask server at {URL} ...")

    flask_process = subprocess.Popen([sys.executable, "app.py"], cwd=frontend_dir)

    time.sleep(5)
    webbrowser.open(URL)
    print("\nPress Ctrl+C to stop the server...")

    try:
        flask_process.wait()
    except KeyboardInterrupt:
        print("\nShutting down server...")
        flask_process.terminate()
        print("Server stopped.")


if __name__ == "__main__":
    main()
