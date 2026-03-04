#!/usr/bin/env python3
"""
Startup script for DeployPulse
Handles environment setup and starts the FastAPI server
Works on Windows, macOS, and Linux
"""

import os
import sys
import subprocess
import webbrowser
import time
from pathlib import Path

def find_python_executable():
    """Find the correct python executable to use"""
    # Try python3 first (preferred on Unix systems)
    try:
        result = subprocess.run(['python3', '--version'], capture_output=True)
        if result.returncode == 0:
            return 'python3'
    except FileNotFoundError:
        pass
    
    # Fall back to python
    try:
        result = subprocess.run(['python', '--version'], capture_output=True)
        if result.returncode == 0:
            return 'python'
    except FileNotFoundError:
        pass
    
    return None

def check_python_version():
    """Ensure Python 3.8+ is being used"""
    if sys.version_info < (3, 8):
        print(f"ERROR: Python 3.8+ required. Current: {sys.version}")
        sys.exit(1)
    print(f"✓ Python version: {sys.version_info.major}.{sys.version_info.minor}")

def find_and_use_python():
    """Find the correct Python executable"""
    python_exe = find_python_executable()
    if not python_exe:
        print("ERROR: Python 3.8+ not found in PATH")
        print("Please install Python 3.8 or higher from https://python.org")
        sys.exit(1)
    return python_exe

def setup_virtual_environment(python_exe):
    """Create and activate virtual environment if it doesn't exist"""
    venv_path = Path("venv")
    
    if not venv_path.exists():
        print("\nCreating virtual environment...")
        try:
            subprocess.check_call([python_exe, "-m", "venv", str(venv_path)])
            print("✓ Virtual environment created")
        except subprocess.CalledProcessError as e:
            print(f"ERROR: Failed to create virtual environment: {e}")
            sys.exit(1)
        except Exception as e:
            print(f"ERROR: Unexpected error creating venv: {e}")
            sys.exit(1)
    else:
        print("✓ Virtual environment already exists")
    
    # Get the python executable inside the venv
    if sys.platform == "win32":
        venv_python = str(venv_path / "Scripts" / "python.exe")
    else:
        venv_python = str(venv_path / "bin" / "python")
    
    return venv_python

def install_requirements(python_exe):
    """Install packages from requirements.txt"""
    print("\nInstalling dependencies...")
    try:
        subprocess.check_call([python_exe, "-m", "pip", "install", "-q", "-r", "requirements.txt"])
        print("✓ Dependencies installed")
    except subprocess.CalledProcessError as e:
        print(f"ERROR: Failed to install dependencies: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Unexpected error installing dependencies: {e}")
        sys.exit(1)

def verify_project_structure():
    """Verify required directories exist"""
    required_dirs = ["database", "logs", "static"]
    for dir_name in required_dirs:
        Path(dir_name).mkdir(exist_ok=True)
    print(f"✓ Project structure verified")

def check_env_file():
    """Check if .env file exists with required variables"""
    if not Path(".env").exists():
        print("\n" + "=" * 50)
        print("ERROR: .env file not found!")
        print("=" * 50)
        print("\nPlease create a .env file in the project root directory.")
        print("\nRequired variables:")
        print("  NEW_RELIC_API_KEY=your_api_key")
        print("  NEW_RELIC_ACCOUNT_ID=your_account_id")
        print("\nSteps:")
        print("  1. Create a .env file in the current directory")
        print("  2. Add your API keys to the .env file")
        print("  3. Run the following command to start the application:")
        print(f"     python3 run.py")
        print("\n" + "=" * 50)
        sys.exit(1)
    else:
        print("✓ .env file found")

def open_browser(url):
    """Open browser to the application"""
    time.sleep(2)  # Give server time to start
    try:
        webbrowser.open(url)
        print(f"\n✓ Browser opened: {url}")
    except Exception as e:
        print(f"\nNote: Could not auto-open browser. Visit {url} manually")

def start_server(python_exe):
    """Start FastAPI server with uvicorn"""
    print("\nStarting FastAPI server...")
    print("-" * 50)
    
    try:
        # Open browser in background thread
        import threading
        browser_thread = threading.Thread(target=open_browser, args=("http://localhost:8000",), daemon=True)
        browser_thread.start()
        
        # Start the server
        subprocess.run([python_exe, "-m", "uvicorn", "app:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])
    except KeyboardInterrupt:
        print("\n\n" + "-" * 50)
        print("Server stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"ERROR: Failed to start server: {e}")
        sys.exit(1)

def main():
    """Main startup sequence"""
    print("\n" + "=" * 50)
    print("  DeployPulse - Release Impact Report Generator")
    print("=" * 50)
    
    # Find correct Python executable
    python_exe = find_and_use_python()
    
    # Run startup checks
    check_python_version()
    verify_project_structure()
    check_env_file()
    
    # Setup virtual environment
    venv_python = setup_virtual_environment(python_exe)
    
    # Install dependencies in virtual environment
    install_requirements(venv_python)
    
    print("\n" + "-" * 50)
    print("Starting application...")
    print("-" * 50)
    
    start_server(venv_python)

if __name__ == "__main__":
    main()
