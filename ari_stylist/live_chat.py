#!/usr/bin/env python3
"""
Interactive AI Stylist Chat Client

This script provides a command-line interface to interact with the AI Stylist API
with proper session and user tracking to maintain conversation history.
"""

import requests
import json
import os
import uuid
import sys
from datetime import datetime

# Configuration
API_URL = "http://localhost:8000"  # Update with your server URL
CONFIG_FILE = "stylist_config.json"

def save_config(config):
    """Save configuration to file"""
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f, indent=2)

def load_config():
    """Load configuration from file"""
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except json.JSONDecodeError:
            print("Error loading config file. Creating new config.")
    
    # Default config
    return {
        "known_users": {},
        "default_user_id": None,
        "last_session": None
    }

def generate_user_id():
    """Generate a new user ID"""
    return str(uuid.uuid4())

def send_message(message, user_id, session_id=None):
    """Send a message to the AI Stylist API"""
    payload = {
        "message": message,
        "user_id": user_id
    }
    
    if session_id:
        payload["session_id"] = session_id
    
    try:
        response = requests.post(f"{API_URL}/chat", json=payload)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        print(f"Connection Error: {e}")
        return None

def get_session_info(session_id):
    """Get information about a session"""
    try:
        response = requests.get(f"{API_URL}/session/{session_id}")
        if response.status_code == 200:
            return response.json()
        else:
            print(f"API Error: {response.status_code} - {response.text}")
            return None
    except requests.RequestException as e:
        print(f"Connection Error: {e}")
        return None

def print_help():
    """Print help information"""
    print("\nCommand options:")
    print("  /help    - Show this help message")
    print("  /quit    - Exit the program")
    print("  /session - Show current session information")
    print("  /users   - Show known users")
    print("  /switch  - Switch to a different user")
    print("  /new     - Create a new session")
    print("  /clear   - Clear the screen")

def main():
    """Main program loop"""
    print("=" * 50)
    print("AI Stylist Interactive Chat Client")
    print("=" * 50)
    
    # Load configuration
    config = load_config()
    
    # Handle user selection
    if config["known_users"]:
        print("\nKnown users:")
        for i, (user_id, user_info) in enumerate(config["known_users"].items(), 1):
            last_used = user_info.get("last_used", "Unknown")
            name = user_info.get("name", "Unnamed")
            print(f"  {i}. {name} ({user_id[:8]}...) - Last used: {last_used}")
        
        print("\nOptions:")
        print("  n. Create a new user")
        
        choice = input("\nSelect a user or create a new one (number or 'n'): ").strip().lower()
        
        if choice == 'n':
            # Create a new user
            user_id = generate_user_id()
            name = input("Enter a name for this user: ").strip()
            if not name:
                name = f"User-{user_id[:6]}"
                
            config["known_users"][user_id] = {
                "name": name,
                "created_at": datetime.now().isoformat(),
                "last_used": datetime.now().isoformat(),
                "sessions": []
            }
            print(f"Created new user: {name} ({user_id})")
        else:
            try:
                index = int(choice) - 1
                user_ids = list(config["known_users"].keys())
                if 0 <= index < len(user_ids):
                    user_id = user_ids[index]
                    config["known_users"][user_id]["last_used"] = datetime.now().isoformat()
                    print(f"Selected user: {config['known_users'][user_id]['name']} ({user_id})")
                else:
                    print("Invalid selection. Creating a new user.")
                    user_id = generate_user_id()
                    name = f"User-{user_id[:6]}"
                    config["known_users"][user_id] = {
                        "name": name,
                        "created_at": datetime.now().isoformat(),
                        "last_used": datetime.now().isoformat(),
                        "sessions": []
                    }
                    print(f"Created new user: {name} ({user_id})")
            except (ValueError, IndexError):
                print("Invalid selection. Creating a new user.")
                user_id = generate_user_id()
                name = f"User-{user_id[:6]}"
                config["known_users"][user_id] = {
                    "name": name,
                    "created_at": datetime.now().isoformat(),
                    "last_used": datetime.now().isoformat(),
                    "sessions": []
                }
                print(f"Created new user: {name} ({user_id})")
    else:
        print("No existing users found. Creating a new user.")
        user_id = generate_user_id()
        name = input("Enter a name for this user: ").strip()
        if not name:
            name = f"User-{user_id[:6]}"
            
        config["known_users"][user_id] = {
            "name": name,
            "created_at": datetime.now().isoformat(),
            "last_used": datetime.now().isoformat(),
            "sessions": []
        }
        print(f"Created new user: {name} ({user_id})")
    
    # Set as default user
    config["default_user_id"] = user_id
    
    # Check for existing sessions
    user_info = config["known_users"][user_id]
    session_id = None
    
    if user_info.get("sessions"):
        print("\nExisting sessions:")
        for i, session in enumerate(user_info["sessions"], 1):
            last_active = session.get("last_active", "Unknown")
            print(f"  {i}. Session {session['id'][:8]}... - Last active: {last_active}")
        
        print("\nOptions:")
        print("  n. Create a new session")
        
        choice = input("\nSelect a session or create a new one (number or 'n'): ").strip().lower()
        
        if choice == 'n':
            # Will create a new session below
            pass
        else:
            try:
                index = int(choice) - 1
                if 0 <= index < len(user_info["sessions"]):
                    session_id = user_info["sessions"][index]["id"]
                    session_info = get_session_info(session_id)
                    
                    if session_info and session_info.get("exists", False):
                        print(f"Resumed session: {session_id}")
                    else:
                        print(f"Session {session_id} no longer exists on server. Creating a new session.")
                        session_id = None
                else:
                    print("Invalid selection. Creating a new session.")
            except (ValueError, IndexError):
                print("Invalid selection. Creating a new session.")
    
    # Start a new session if needed
    if not session_id:
        print("\nStarting a new conversation session...")
        # The first message will create a new session
        response = send_message("Hello Ari, I'm here for some fashion advice.", user_id)
        
        if response:
            session_id = response["session_id"]
            print(f"Created new session: {session_id}")
            
            # Update session in user info
            user_sessions = user_info.get("sessions", [])
            user_sessions.append({
                "id": session_id,
                "created_at": datetime.now().isoformat(),
                "last_active": datetime.now().isoformat()
            })
            user_info["sessions"] = user_sessions
            
            # Display first message
            print("\nAI Stylist:", response["response"])
        else:
            print("Failed to create a new session. Exiting.")
            sys.exit(1)
    
    # Save configuration
    save_config(config)
    
    # Main conversation loop
    print("\nType '/help' for available commands.")
    while True:
        try:
            user_input = input("\nYou: ").strip()
            
            # Handle commands
            if user_input.lower() == '/quit':
                print("Goodbye!")
                break
            elif user_input.lower() == '/help':
                print_help()
                continue
            elif user_input.lower() == '/session':
                session_info = get_session_info(session_id)
                if session_info:
                    print("\nSession Information:")
                    print(f"  Session ID: {session_info['session_id']}")
                    print(f"  User ID: {session_info.get('user_id', 'Unknown')}")
                    print(f"  Messages: {session_info.get('message_count', 0)}")
                    print(f"  Start time: {session_info.get('start_time', 'Unknown')}")
                    
                    # Show last few messages
                    if session_info.get('last_messages'):
                        print("\nRecent messages:")
                        for msg in session_info['last_messages']:
                            sender = "You" if msg['sender'] == 'user' else "AI Stylist"
                            content = msg['content']
                            # Truncate long messages
                            if len(content) > 100:
                                content = content[:97] + "..."
                            print(f"  {sender}: {content}")
                continue
            elif user_input.lower() == '/users':
                print("\nKnown users:")
                for i, (uid, info) in enumerate(config["known_users"].items(), 1):
                    name = info.get("name", "Unnamed")
                    last_used = info.get("last_used", "Unknown")
                    print(f"  {i}. {name} ({uid[:8]}...) - Last used: {last_used}")
                continue
            elif user_input.lower() == '/switch':
                # Save current config before switching
                save_config(config)
                
                print("\nKnown users:")
                for i, (uid, info) in enumerate(config["known_users"].items(), 1):
                    name = info.get("name", "Unnamed")
                    print(f"  {i}. {name} ({uid[:8]}...)")
                
                print("  n. Create a new user")
                
                choice = input("\nSelect a user or create a new one (number or 'n'): ").strip().lower()
                
                if choice == 'n':
                    # Create a new user
                    new_user_id = generate_user_id()
                    name = input("Enter a name for this user: ").strip()
                    if not name:
                        name = f"User-{new_user_id[:6]}"
                        
                    config["known_users"][new_user_id] = {
                        "name": name,
                        "created_at": datetime.now().isoformat(),
                        "last_used": datetime.now().isoformat(),
                        "sessions": []
                    }
                    print(f"Created new user: {name} ({new_user_id})")
                    user_id = new_user_id
                    session_id = None
                else:
                    try:
                        index = int(choice) - 1
                        user_ids = list(config["known_users"].keys())
                        if 0 <= index < len(user_ids):
                            user_id = user_ids[index]
                            config["known_users"][user_id]["last_used"] = datetime.now().isoformat()
                            print(f"Switched to user: {config['known_users'][user_id]['name']} ({user_id})")
                            
                            # Ask which session to use
                            user_info = config["known_users"][user_id]
                            if user_info.get("sessions"):
                                print("\nExisting sessions:")
                                for i, session in enumerate(user_info["sessions"], 1):
                                    last_active = session.get("last_active", "Unknown")
                                    print(f"  {i}. Session {session['id'][:8]}... - Last active: {last_active}")
                                
                                print("  n. Create a new session")
                                
                                session_choice = input("\nSelect a session or create a new one (number or 'n'): ").strip().lower()
                                
                                if session_choice == 'n':
                                    session_id = None
                                else:
                                    try:
                                        index = int(session_choice) - 1
                                        if 0 <= index < len(user_info["sessions"]):
                                            session_id = user_info["sessions"][index]["id"]
                                            session_info = get_session_info(session_id)
                                            
                                            if session_info and session_info.get("exists", False):
                                                print(f"Resumed session: {session_id}")
                                            else:
                                                print(f"Session {session_id} no longer exists on server. Creating a new session.")
                                                session_id = None
                                        else:
                                            print("Invalid selection. Creating a new session.")
                                            session_id = None
                                    except (ValueError, IndexError):
                                        print("Invalid selection. Creating a new session.")
                                        session_id = None
                            else:
                                print("No existing sessions. Creating a new one.")
                                session_id = None
                        else:
                            print("Invalid selection. No change.")
                            continue
                    except (ValueError, IndexError):
                        print("Invalid selection. No change.")
                        continue
                
                # Create a new session if needed
                if not session_id:
                    print("\nStarting a new conversation session...")
                    response = send_message("Hello Ari, I'm here for some fashion advice.", user_id)
                    
                    if response:
                        session_id = response["session_id"]
                        print(f"Created new session: {session_id}")
                        
                        # Update session in user info
                        user_info = config["known_users"][user_id]
                        user_sessions = user_info.get("sessions", [])
                        user_sessions.append({
                            "id": session_id,
                            "created_at": datetime.now().isoformat(),
                            "last_active": datetime.now().isoformat()
                        })
                        user_info["sessions"] = user_sessions
                        
                        # Display first message
                        print("\nAI Stylist:", response["response"])
                    else:
                        print("Failed to create a new session. No change.")
                        continue
                
                # Update default user
                config["default_user_id"] = user_id
                save_config(config)
                continue
            elif user_input.lower() == '/new':
                print("\nStarting a new conversation session...")
                response = send_message("Hello Ari, I'm here for some fashion advice.", user_id)
                
                if response:
                    session_id = response["session_id"]
                    print(f"Created new session: {session_id}")
                    
                    # Update session in user info
                    user_info = config["known_users"][user_id]
                    user_sessions = user_info.get("sessions", [])
                    user_sessions.append({
                        "id": session_id,
                        "created_at": datetime.now().isoformat(),
                        "last_active": datetime.now().isoformat()
                    })
                    user_info["sessions"] = user_sessions
                    
                    # Display first message
                    print("\nAI Stylist:", response["response"])
                    
                    # Save configuration
                    save_config(config)
                else:
                    print("Failed to create a new session.")
                continue
            elif user_input.lower() == '/clear':
                # Clear the screen
                os.system('cls' if os.name == 'nt' else 'clear')
                print("AI Stylist Chat - Type '/help' for commands")
                continue
            
            # Send regular message
            response = send_message(user_input, user_id, session_id)
            
            if response:
                print("\nAI Stylist:", response["response"])
                
                # Update session information
                user_info = config["known_users"][user_id]
                for session in user_info.get("sessions", []):
                    if session["id"] == session_id:
                        session["last_active"] = datetime.now().isoformat()
                        break
                
                # Save configuration periodically
                save_config(config)
            else:
                print("Failed to get response from AI Stylist.")
        
        except KeyboardInterrupt:
            print("\nExiting...")
            break
        except Exception as e:
            print(f"Error: {e}")
    
    # Final save
    save_config(config)
    print("Configuration saved. Goodbye!")

if __name__ == "__main__":
    main()
