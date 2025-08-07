#!/usr/bin/env python3
"""
Termchat - Cross-platform Python terminal client for real-time chat
Connects to termchat-backend via HTTPS WebSocket on port 443
"""

import asyncio
import websockets
import json
import signal
import sys
import os
import time
import threading
from typing import Optional

# ANSI Color codes - Only GREEN and BLACK as required
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Only use GREEN and BLACK colors as required
    GREEN = '\033[32m'
    BRIGHT_GREEN = '\033[92m'

# ASCII Art for TERMCHAT
TERMCHAT_ASCII = """
████████ ███████ ██████  ███    ███  ██████ ██   ██  █████  ████████ 
   ██    ██      ██   ██ ████  ████ ██      ██   ██ ██   ██    ██    
   ██    █████   ██████  ██ ████ ██ ██      ███████ ███████    ██    
   ██    ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██    ██    
   ██    ███████ ██   ██ ██      ██  ██████ ██   ██ ██   ██    ██    
"""

# Global progress animation control
_progress_running = False
_progress_thread = None

def clear_terminal():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def progress(message):
    """Start background spinner with frames and green color"""
    global _progress_running, _progress_thread
    
    _progress_running = True
    frames = ['▱▱▱▱▱▱▱▱▱▱', '▰▱▱▱▱▱▱▱▱▱', '▰▰▱▱▱▱▱▱▱▱', '▰▰▰▱▱▱▱▱▱▱', 
              '▰▰▰▰▱▱▱▱▱▱', '▰▰▰▰▰▱▱▱▱▱', '▰▰▰▰▰▰▱▱▱▱', '▰▰▰▰▰▰▰▱▱▱',
              '▰▰▰▰▰▰▰▰▱▱', '▰▰▰▰▰▰▰▰▰▱', '▰▰▰▰▰▰▰▰▰▰']
    
    def animate():
        frame_idx = 0
        while _progress_running:
            frame = frames[frame_idx % len(frames)]
            print(f'\r{Colors.BRIGHT_GREEN}[{frame}] {message}{Colors.RESET}', end='', flush=True)
            frame_idx += 1
            time.sleep(0.1)
    
    _progress_thread = threading.Thread(target=animate, daemon=True)
    _progress_thread.start()

def end_progress():
    """Clean up progress animation and restore cursor"""
    global _progress_running, _progress_thread
    
    _progress_running = False
    if _progress_thread:
        _progress_thread.join(timeout=0.2)
    print('\r' + ' ' * 80, end='\r', flush=True)  # Clear the line


class TermchatClient:
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.username: str = ""
        self.chat_name: str = ""
        self.password: str = ""
        self.running: bool = True
        self.messages: list = []  # Store chat messages
        
        # Backend server URL (HTTPS WebSocket on port 443)
        self.server_url = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net"
    
    def display_message_in_chat_area(self, message):
        """Display a message in the chat area (above the input line)"""
        # Add message to history
        self.messages.append(message)
        
        # Print the message without clearing the input prompt
        print(message)
        
        # Add spacing before next message
        print()
    
    def setup_signal_handlers(self):
        """Set up signal handlers for clean exit"""
        def signal_handler(signum, frame):
            print(f"\n{Colors.BRIGHT_GREEN}Exiting Termchat...{Colors.RESET}")
            self.running = False
            # Immediate exit on Ctrl-C
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def get_user_input(self):
        """Prompt user for connection details"""
        try:
            print(f"{Colors.BRIGHT_GREEN}╔═══════════════════════════════════════╗{Colors.RESET}")
            print(f"{Colors.BRIGHT_GREEN}║           TERMCHAT LOGIN              ║{Colors.RESET}")
            print(f"{Colors.BRIGHT_GREEN}╚═══════════════════════════════════════╝{Colors.RESET}")
            print()
            
            self.username = input(f"{Colors.GREEN}Enter username: {Colors.RESET}").strip()
            if not self.username:
                print(f"{Colors.GREEN}Username cannot be empty!{Colors.RESET}")
                return False
            
            if self.username.lower() == "server":
                print(f"{Colors.GREEN}Username 'server' is forbidden!{Colors.RESET}")
                return False
            
            self.chat_name = input(f"{Colors.GREEN}Enter chat name: {Colors.RESET}").strip()
            if not self.chat_name:
                print(f"{Colors.GREEN}Chat name cannot be empty!{Colors.RESET}")
                return False
            
            self.password = input(f"{Colors.GREEN}Enter password: {Colors.RESET}").strip()
            if not self.password:
                print(f"{Colors.GREEN}Password cannot be empty!{Colors.RESET}")
                return False
            
            return True
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.BRIGHT_GREEN}Exiting...{Colors.RESET}")
            return False
    
    async def connect_to_server(self):
        """Establish WebSocket connection to the backend"""
        try:
            progress("Connecting to server...")
            self.websocket = await websockets.connect(
                self.server_url,
                ssl=True,  # Enable SSL for HTTPS
                ping_interval=30,
                ping_timeout=10
            )
            end_progress()
            clear_terminal()
            return True
        except Exception as e:
            end_progress()
            print(f"{Colors.GREEN}Failed to connect to server: {e}{Colors.RESET}")
            return False
    
    async def authenticate(self):
        """Send authentication message to server"""
        auth_message = {
            "type": "join",
            "username": self.username,
            "chatname": self.chat_name,
            "password": self.password
        }
        
        try:
            await self.websocket.send(json.dumps(auth_message))
            return True
        except Exception as e:
            print(f"{Colors.GREEN}Authentication failed: {e}{Colors.RESET}")
            return False
    
    def display_header_bar(self):
        """Display green header bar when connected"""
        terminal_width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
        print(f"{Colors.BOLD}{Colors.BRIGHT_GREEN}{'=' * terminal_width}{Colors.RESET}")
        print()
    
    async def listen_for_messages(self):
        """Listen for incoming messages from the server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    # Only show real server messages, no fake output
                    pass
        except websockets.exceptions.ConnectionClosed:
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}Connection to server lost.{Colors.RESET}")
        except Exception as e:
            # Only show real server errors
            pass
    
    async def handle_message(self, data):
        """Handle different types of messages from the server"""
        message_type = data.get("type", "")
        
        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            self.display_message_in_chat_area(f"{Colors.GREEN}[{username}]:{Colors.RESET} {message}")
        
        elif message_type == "join":
            username = data.get("username", "Unknown")
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}A wild {username} has appeared.{Colors.RESET}")
        
        elif message_type == "leave":
            username = data.get("username", "Unknown")
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}{username} has left the chat.{Colors.RESET}")
        
        elif message_type == "error":
            error_message = data.get("message", "Unknown error")
            self.display_message_in_chat_area(f"{Colors.GREEN}Error: {error_message}{Colors.RESET}")
        
        elif message_type == "auth_success":
            # Clear terminal and show header bar after successful authentication
            clear_terminal()
            self.display_header_bar()
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}[Server]: Connected successfully{Colors.RESET}")
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}Successfully joined chat '{self.chat_name}'{Colors.RESET}")
        
        elif message_type == "auth_failed":
            error_message = data.get("message", "Authentication failed")
            print(f"{Colors.GREEN}Authentication failed: {error_message}{Colors.RESET}")
            self.running = False
    
    async def send_user_input(self):
        """Handle user input for sending messages"""
        try:
            while self.running:
                try:
                    # Use asyncio to get user input without blocking
                    user_message = await asyncio.get_event_loop().run_in_executor(
                        None, input, f"{Colors.GREEN}Enter message: {Colors.RESET}"
                    )
                    
                    if not self.running:
                        break
                    
                    user_message = user_message.strip()
                    if user_message:
                        if user_message.lower() in ['/quit', '/exit', '/q']:
                            print(f"{Colors.BRIGHT_GREEN}Exiting Termchat...{Colors.RESET}")
                            self.running = False
                            if self.websocket:
                                await self.websocket.close()
                            return
                        
                        # Send the message without clearing the input line
                        message_data = {
                            "type": "message",
                            "content": user_message
                        }
                        
                        await self.websocket.send(json.dumps(message_data))
                
                except (KeyboardInterrupt, EOFError):
                    print(f"\n{Colors.BRIGHT_GREEN}Exiting Termchat...{Colors.RESET}")
                    self.running = False
                    if self.websocket:
                        await self.websocket.close()
                    return
                except Exception as e:
                    if self.running:
                        # Only show real server errors, no fake messages
                        pass
        
        except Exception as e:
            # Only show real server errors
            pass
    
    async def run(self):
        """Main client loop"""
        self.setup_signal_handlers()
        
        # Clear terminal and show ASCII art
        clear_terminal()
        print(f"{Colors.BRIGHT_GREEN}{TERMCHAT_ASCII}{Colors.RESET}")
        print(f"{Colors.GREEN}Cross-platform terminal chat client{Colors.RESET}")
        print(f"{Colors.GREEN}Commands: /quit, /exit, /q to exit{Colors.RESET}")
        print()
        
        # Get user input
        if not self.get_user_input():
            return
        
        # Connect to server
        if not await self.connect_to_server():
            return
        
        # Authenticate
        if not await self.authenticate():
            return
        
        try:
            # Start listening for messages and handling user input concurrently
            await asyncio.gather(
                self.listen_for_messages(),
                self.send_user_input(),
                return_exceptions=True
            )
        except Exception as e:
            # Only show real server errors
            pass
        finally:
            self.running = False
            if self.websocket:
                await self.websocket.close()


async def main():
    """Entry point for the application"""
    client = TermchatClient()
    await client.run()


if __name__ == "__main__":
    try:
        # Ensure asyncio compatibility across platforms
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)