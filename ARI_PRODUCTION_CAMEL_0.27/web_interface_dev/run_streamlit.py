#!/usr/bin/env python3
"""
Launch script for AIStylist Streamlit Web Interface
"""

import os
import sys
import subprocess
from pathlib import Path

def main():
    """Launch the Streamlit application"""
    # Ensure we're in the right directory
    script_dir = Path(__file__).parent
    os.chdir(script_dir)
    
    # Check if .env exists
    env_file = script_dir / ".env"
    if not env_file.exists():
        print(" .env file not found!")
        print("Please ensure the .env file is present in the project directory")
        return 1
    
    print(" Starting AIStylist Multi-Agent Web Interface...")
    print(f"Working directory: {script_dir}")
    print("The interface will open in your browser at http://localhost:8501")
    print("")
    print("Features:")
    print("   Chat with ARI Fashion AI")
    print("   See agent thinking processes")
    print("   Real-time ML intelligence")
    print("   Product recommendations")
    print("")
    
    try:
        # Launch Streamlit
        cmd = [
            sys.executable, "-m", "streamlit", "run", "streamlit_simple.py",
            "--server.port", "8503",
            "--server.address", "0.0.0.0",
            "--theme.base", "light"
        ]
        
        subprocess.run(cmd, check=True)
        
    except subprocess.CalledProcessError as e:
        print(f" Error launching Streamlit: {e}")
        return 1
    except KeyboardInterrupt:
        print("\n👋 AIStylist web interface stopped")
        return 0

if __name__ == "__main__":
    sys.exit(main())