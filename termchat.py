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
import queue
from typing import Optional

# ANSI Color codes and cursor controls
class Colors:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    
    # Regular colors
    RED = '\033[31m'
    GREEN = '\033[32m'
    YELLOW = '\033[33m'
    BLUE = '\033[34m'
    MAGENTA = '\033[35m'
    CYAN = '\033[36m'
    WHITE = '\033[37m'
    
    # Bright colors
    BRIGHT_RED = '\033[91m'
    BRIGHT_GREEN = '\033[92m'
    BRIGHT_YELLOW = '\033[93m'
    BRIGHT_BLUE = '\033[94m'
    BRIGHT_MAGENTA = '\033[95m'
    BRIGHT_CYAN = '\033[96m'
    BRIGHT_WHITE = '\033[97m'

# ANSI escape codes for cursor control
class Cursor:
    HIDE = '\033[?25l'        # Hide cursor
    SHOW = '\033[?25h'        # Show cursor
    SAVE_POS = '\033[s'       # Save cursor position
    RESTORE_POS = '\033[u'    # Restore cursor position
    
    @staticmethod
    def move_to(row, col):
        """Move cursor to specific position (1-indexed)"""
        return f'\033[{row};{col}H'
    
    @staticmethod
    def move_to_bottom():
        """Move cursor to bottom of terminal"""
        return '\033[999;1H'  # Move to row 999 (terminal will clamp to actual bottom)
    
    @staticmethod
    def clear_line():
        """Clear entire current line"""
        return '\033[2K'
    
    @staticmethod
    def clear_to_end():
        """Clear from cursor to end of line"""
        return '\033[K'

# ASCII Art for TERMCHAT
TERMCHAT_ASCII = """
████████ ███████ ██████  ███    ███  ██████ ██   ██  █████  ████████ 
   ██    ██      ██   ██ ████  ████ ██      ██   ██ ██   ██    ██    
   ██    █████   ██████  ██ ████ ██ ██      ███████ ███████    ██    
   ██    ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██    ██    
   ██    ███████ ██   ██ ██      ██  ██████ ██   ██ ██   ██    ██    
"""

# User colors for cycling
USER_COLORS = [
    Colors.RED, Colors.GREEN, Colors.YELLOW, Colors.MAGENTA, 
    Colors.CYAN, Colors.BRIGHT_RED, Colors.BRIGHT_YELLOW, 
    Colors.BRIGHT_MAGENTA, Colors.BRIGHT_CYAN
]

# Global progress animation control
_progress_running = False
_progress_thread = None

def clear_terminal():
    """Clear the terminal screen"""
    os.system('cls' if os.name == 'nt' else 'clear')

def progress(message):
    """Start background spinner with frames and bright blue color"""
    global _progress_running, _progress_thread
    
    _progress_running = True
    frames = ['▱▱▱▱▱▱▱▱▱▱', '▰▱▱▱▱▱▱▱▱▱', '▰▰▱▱▱▱▱▱▱▱', '▰▰▰▱▱▱▱▱▱▱', 
              '▰▰▰▰▱▱▱▱▱▱', '▰▰▰▰▰▱▱▱▱▱', '▰▰▰▰▰▰▱▱▱▱', '▰▰▰▰▰▰▰▱▱▱',
              '▰▰▰▰▰▰▰▰▱▱', '▰▰▰▰▰▰▰▰▰▱', '▰▰▰▰▰▰▰▰▰▰']
    
    def animate():
        frame_idx = 0
        while _progress_running:
            frame = frames[frame_idx % len(frames)]
            print(f'\r{Colors.BRIGHT_BLUE}[{frame}] {message}{Colors.RESET}', end='', flush=True)
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
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.username: str = ""
        self.chat_name: str = ""
        self.password: str = ""
        self.running: bool = True
        self.user_colors: dict = {}  # Maps usernames to colors
        self.color_index: int = 0    # For cycling through colors
        self.terminal_height: int = 24  # Default height, will be updated
        self.terminal_width: int = 80   # Default width, will be updated
        self.messages: list = []  # Store chat messages
        self.input_queue: queue.Queue = queue.Queue()  # Thread-safe message queue
        self.display_lock = threading.Lock()  # Ensure thread-safe display
        self.input_line_shown: bool = False  # Track if input line is currently shown
        
        # Backend server URL (HTTPS WebSocket on port 443)
        self.server_url = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net"
    
    def update_terminal_size(self):
        """Update terminal dimensions"""
        if hasattr(os, 'get_terminal_size'):
            size = os.get_terminal_size()
            self.terminal_height = size.lines
            self.terminal_width = size.columns
        else:
            self.terminal_height = 24
            self.terminal_width = 80
    
    def display_message_in_chat_area(self, message):
        """Display a message in the chat area (above the input line) with proper terminal positioning"""
        with self.display_lock:
            self.update_terminal_size()
            
            # Hide cursor for clean display
            print(Cursor.HIDE, end='', flush=True)
            
            # If input line is shown, clear it first
            if self.input_line_shown:
                # Move to bottom line and clear it
                print(Cursor.move_to_bottom(), end='')
                print(Cursor.clear_line(), end='', flush=True)
            
            # Move cursor up one line from bottom to display the message
            print(f'\033[{self.terminal_height-1};1H', end='')
            
            # Display the message and scroll the terminal
            print(message)
            
            # Show the input line again at the bottom
            self.show_input_prompt()
    
    def show_input_prompt(self):
        """Show the input prompt at the bottom of the terminal"""
        # Move to absolute bottom line
        print(Cursor.move_to_bottom(), end='')
        print(Cursor.clear_line(), end='')
        print(f"{Colors.CYAN}Enter message: {Colors.RESET}", end='', flush=True)
        
        # Show cursor for input
        print(Cursor.SHOW, end='', flush=True)
        self.input_line_shown = True
    
    def hide_input_prompt(self):
        """Hide the input prompt temporarily"""
        if self.input_line_shown:
            print(Cursor.HIDE, end='', flush=True)
            print(Cursor.move_to_bottom(), end='')
            print(Cursor.clear_line(), end='', flush=True)
            self.input_line_shown = False
    
    def setup_signal_handlers(self):
        """Set up signal handlers for clean exit"""
        def signal_handler(signum, frame):
            # Clean up cursor state
            print(Cursor.SHOW, end='', flush=True)  # Show cursor
            print(f"\n{Colors.BRIGHT_GREEN}Exiting Termchat...{Colors.RESET}")
            self.running = False
            # Immediate exit on Ctrl-C
            os._exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def get_user_color(self, username: str) -> str:
        """Get or assign a color for a username"""
        if username == "server":
            return f"{Colors.BOLD}{Colors.BRIGHT_BLUE}"
        
        if username not in self.user_colors:
            self.user_colors[username] = USER_COLORS[self.color_index % len(USER_COLORS)]
            self.color_index += 1
        
        return self.user_colors[username]
    
    def get_user_input(self):
        """Prompt user for connection details"""
        try:
            self.username = input("Enter username: ").strip()
            if not self.username:
                print(f"{Colors.RED}Username cannot be empty!{Colors.RESET}")
                return False
            
            if self.username.lower() == "server":
                print(f"{Colors.RED}Username 'server' is forbidden!{Colors.RESET}")
                return False
            
            self.chat_name = input("Enter chat name: ").strip()
            if not self.chat_name:
                print(f"{Colors.RED}Chat name cannot be empty!{Colors.RESET}")
                return False
            
            self.password = input("Enter password: ").strip()
            if not self.password:
                print(f"{Colors.RED}Password cannot be empty!{Colors.RESET}")
                return False
            
            return True
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Colors.BRIGHT_GREEN}Exiting...{Colors.RESET}")
            return False
    
    async def connect_to_server(self):
        """Establish WebSocket connection to the backend"""
        try:
            progress("Connecting...")
            self.websocket = await websockets.connect(
                self.server_url,
                ssl=True,  # Enable SSL for HTTPS
                ping_interval=30,
                ping_timeout=10
            )
            end_progress()
            clear_terminal()
            print(f"{Colors.BRIGHT_GREEN}Connected to Termchat server!{Colors.RESET}")
            return True
        except Exception as e:
            end_progress()
            print(f"{Colors.RED}Failed to connect to server: {e}{Colors.RESET}")
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
            print(f"{Colors.RED}Authentication failed: {e}{Colors.RESET}")
            return False
    
    def display_header_bar(self):
        """Display blue header bar when connected"""
        terminal_width = os.get_terminal_size().columns if hasattr(os, 'get_terminal_size') else 80
        print(f"{Colors.BOLD}{Colors.BRIGHT_BLUE}{'=' * terminal_width}{Colors.RESET}")
        print()
    
    async def listen_for_messages(self):
        """Listen for incoming messages from the server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    print(f"{Colors.RED}Received invalid message: {message}{Colors.RESET}")
        except websockets.exceptions.ConnectionClosed:
            print(f"{Colors.BRIGHT_GREEN}Connection to server lost.{Colors.RESET}")
        except Exception as e:
            print(f"{Colors.RED}Error receiving messages: {e}{Colors.RESET}")
    
    async def handle_message(self, data):
        """Handle different types of messages from the server"""
        message_type = data.get("type", "")
        
        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            user_color = self.get_user_color(username)
            self.display_message_in_chat_area(f"{user_color}[{username}]:{Colors.RESET} {message}")
        
        elif message_type == "join":
            username = data.get("username", "Unknown")
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}A wild {username} has appeared.{Colors.RESET}")
        
        elif message_type == "leave":
            username = data.get("username", "Unknown")
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}{username} has left the chat.{Colors.RESET}")
        
        elif message_type == "error":
            error_message = data.get("message", "Unknown error")
            self.display_message_in_chat_area(f"{Colors.RED}Error: {error_message}{Colors.RESET}")
        
        elif message_type == "auth_success":
            # Clear terminal and show header bar after successful authentication
            clear_terminal()
            self.update_terminal_size()
            self.display_header_bar()
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}[Server]: Connected successfully{Colors.RESET}")
            self.display_message_in_chat_area(f"{Colors.BRIGHT_GREEN}Successfully joined chat '{self.chat_name}'{Colors.RESET}")
        
        elif message_type == "auth_failed":
            error_message = data.get("message", "Authentication failed")
            print(f"{Colors.RED}Authentication failed: {error_message}{Colors.RESET}")
            self.running = False
    
    def input_thread(self):
        """Handle user input in a separate thread with fixed bottom input"""
        try:
            # Show initial input prompt
            self.show_input_prompt()
            
            while self.running:
                try:
                    # Get user input (this will be on the bottom line)
                    user_message = input().strip()
                    
                    if not self.running:
                        break
                    
                    # Hide the input line after getting input
                    self.hide_input_prompt()
                    
                    if user_message:
                        if user_message.lower() in ['/quit', '/exit', '/q']:
                            self.running = False
                            self.input_queue.put({"type": "quit"})
                            break
                        
                        # Add message to queue for processing
                        self.input_queue.put({"type": "message", "content": user_message})
                    
                    # Show input prompt again for next input
                    if self.running:
                        self.show_input_prompt()
                
                except (KeyboardInterrupt, EOFError):
                    self.running = False
                    self.input_queue.put({"type": "quit"})
                    break
                except Exception as e:
                    if self.running:
                        print(f"{Colors.RED}Input error: {e}{Colors.RESET}")
        
        except Exception as e:
            print(f"{Colors.RED}Input thread error: {e}{Colors.RESET}")
    
    async def process_user_input(self):
        """Process user input from the queue"""
        try:
            while self.running:
                try:
                    # Check for user input (non-blocking)
                    try:
                        input_data = self.input_queue.get_nowait()
                    except queue.Empty:
                        await asyncio.sleep(0.1)  # Brief pause to prevent busy waiting
                        continue
                    
                    if input_data["type"] == "quit":
                        print(f"\n{Colors.BRIGHT_GREEN}Exiting Termchat...{Colors.RESET}")
                        self.running = False
                        if self.websocket:
                            await self.websocket.close()
                        return
                    
                    elif input_data["type"] == "message":
                        message_data = {
                            "type": "message",
                            "content": input_data["content"]
                        }
                        await self.websocket.send(json.dumps(message_data))
                
                except Exception as e:
                    if self.running:
                        self.display_message_in_chat_area(f"{Colors.RED}Error processing input: {e}{Colors.RESET}")
        
        except Exception as e:
            self.display_message_in_chat_area(f"{Colors.RED}Input processing error: {e}{Colors.RESET}")
    
    async def send_user_input(self):
        """Start input thread and process input queue"""
        # Start the input thread
        input_thread = threading.Thread(target=self.input_thread, daemon=True)
        input_thread.start()
        
        # Process input from the queue
        await self.process_user_input()
    
    async def run(self):
        """Main client loop"""
        self.setup_signal_handlers()
        
        # Clear terminal and show ASCII art
        clear_terminal()
        print(f"{Colors.BRIGHT_BLUE}{TERMCHAT_ASCII}{Colors.RESET}")
        print(f"{Colors.BRIGHT_WHITE}Cross-platform terminal chat client{Colors.RESET}")
        print(f"{Colors.YELLOW}Commands: /quit, /exit, /q to exit{Colors.RESET}")
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
            print(f"{Colors.RED}Runtime error: {e}{Colors.RESET}")
        finally:
            self.running = False
            if self.websocket:
                await self.websocket.close()
            print(f"{Colors.BRIGHT_GREEN}Disconnected from Termchat server.{Colors.RESET}")


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