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
from typing import Optional


class TermchatClient:
    def __init__(self):
        self.websocket: Optional[websockets.WebSocketServerProtocol] = None
        self.username: str = ""
        self.chat_name: str = ""
        self.password: str = ""
        self.running: bool = True
        
        # Backend server URL (HTTPS WebSocket on port 443)
        self.server_url = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net:443"
    
    def setup_signal_handlers(self):
        """Set up signal handlers for clean exit"""
        def signal_handler(signum, frame):
            print("\nExiting Termchat...")
            self.running = False
        
        signal.signal(signal.SIGINT, signal_handler)
        if hasattr(signal, 'SIGTERM'):
            signal.signal(signal.SIGTERM, signal_handler)
    
    def get_user_input(self):
        """Prompt user for connection details"""
        try:
            self.username = input("Enter username: ").strip()
            if not self.username:
                print("Username cannot be empty!")
                return False
            
            self.chat_name = input("Enter chat name: ").strip()
            if not self.chat_name:
                print("Chat name cannot be empty!")
                return False
            
            self.password = input("Enter password: ").strip()
            if not self.password:
                print("Password cannot be empty!")
                return False
            
            return True
        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            return False
    
    async def connect_to_server(self):
        """Establish WebSocket connection to the backend"""
        try:
            print(f"Connecting to {self.server_url}...")
            self.websocket = await websockets.connect(
                self.server_url,
                ssl=True,  # Enable SSL for HTTPS
                ping_interval=30,
                ping_timeout=10
            )
            print("Connected to Termchat server!")
            return True
        except Exception as e:
            print(f"Failed to connect to server: {e}")
            return False
    
    async def authenticate(self):
        """Send authentication message to server"""
        auth_message = {
            "type": "auth",
            "username": self.username,
            "chat_name": self.chat_name,
            "password": self.password
        }
        
        try:
            await self.websocket.send(json.dumps(auth_message))
            return True
        except Exception as e:
            print(f"Authentication failed: {e}")
            return False
    
    async def listen_for_messages(self):
        """Listen for incoming messages from the server"""
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    print(f"Received invalid message: {message}")
        except websockets.exceptions.ConnectionClosed:
            print("Connection to server lost.")
        except Exception as e:
            print(f"Error receiving messages: {e}")
    
    async def handle_message(self, data):
        """Handle different types of messages from the server"""
        message_type = data.get("type", "")
        
        if message_type == "chat":
            username = data.get("username", "Unknown")
            message = data.get("message", "")
            print(f"[{username}]: {message}")
        
        elif message_type == "user_joined":
            username = data.get("username", "Unknown")
            print(f"A wild {username} has appeared.")
        
        elif message_type == "user_left":
            username = data.get("username", "Unknown")
            print(f"{username} has left the chat.")
        
        elif message_type == "error":
            error_message = data.get("message", "Unknown error")
            print(f"Error: {error_message}")
        
        elif message_type == "auth_success":
            print(f"Successfully joined chat '{self.chat_name}'")
        
        elif message_type == "auth_failed":
            error_message = data.get("message", "Authentication failed")
            print(f"Authentication failed: {error_message}")
            self.running = False
    
    async def send_user_input(self):
        """Handle user input for sending messages"""
        try:
            while self.running:
                try:
                    # Use asyncio to get user input without blocking
                    user_message = await asyncio.get_event_loop().run_in_executor(
                        None, input, ""
                    )
                    
                    if not self.running:
                        break
                    
                    user_message = user_message.strip()
                    if user_message:
                        if user_message.lower() in ['/quit', '/exit', '/q']:
                            self.running = False
                            break
                        
                        message_data = {
                            "type": "chat",
                            "message": user_message
                        }
                        
                        await self.websocket.send(json.dumps(message_data))
                
                except (KeyboardInterrupt, EOFError):
                    self.running = False
                    break
                except Exception as e:
                    if self.running:
                        print(f"Error sending message: {e}")
        
        except Exception as e:
            print(f"Input handling error: {e}")
    
    async def run(self):
        """Main client loop"""
        self.setup_signal_handlers()
        
        print("=== Termchat Client ===")
        print("Cross-platform terminal chat client")
        print("Commands: /quit, /exit, /q to exit")
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
                self.send_user_input()
            )
        except Exception as e:
            print(f"Runtime error: {e}")
        finally:
            if self.websocket:
                await self.websocket.close()
            print("Disconnected from Termchat server.")


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