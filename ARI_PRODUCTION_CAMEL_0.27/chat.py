#!/usr/bin/env python3
"""
ARI Fashion Stylist - Quick Chat Launcher
Simple launcher for the terminal chat interface.
"""

import os
import sys
import subprocess

def main():
    """Launch the ARI terminal chat interface."""
    
    print("🚀 Launching ARI Fashion Stylist Terminal Chat...")
    print()
    
    # Change to script directory and set Python path
    script_dir = os.path.dirname(os.path.abspath(__file__))
    os.chdir(script_dir)
    
    # Add current directory to Python path for imports
    if script_dir not in sys.path:
        sys.path.insert(0, script_dir)
    
    try:
        # Try to install rich if needed
        try:
            import rich
        except ImportError:
            print("📦 Installing rich for beautiful terminal interface...")
            subprocess.run([sys.executable, "-m", "pip", "install", "rich"], check=True)
        
        # Run the chat terminal
        from chat_terminal import main as chat_main
        import asyncio
        asyncio.run(chat_main())
        
    except KeyboardInterrupt:
        print("\n\n👋 Goodbye!")
    except Exception as e:
        print(f"❌ Error launching chat: {e}")
        print("\nTroubleshooting:")
        print("1. Make sure you're in the ARI project directory")
        print("2. Check if Redis, Neo4j, and Qdrant services are running")
        print("3. Verify environment variables are set")

if __name__ == "__main__":
    main()