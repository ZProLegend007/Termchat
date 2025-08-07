#!/usr/bin/env python3
"""
Termchat - Cross-platform Python terminal client for real-time chat
Connects to termchat-backend via HTTPS WebSocket on port 443
"""

import asyncio
import websockets
import json
import sys
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input, RichLog, Static, Label
from textual.binding import Binding
from textual.screen import Screen
from rich.markup import escape

# User colors for cycling through usernames
USER_COLORS = [
    "red", "green", "yellow", "magenta", 
    "cyan", "bright_red", "bright_yellow", 
    "bright_magenta", "bright_cyan"
]

# ASCII Art for TERMCHAT
TERMCHAT_ASCII = """
████████ ███████ ██████  ███    ███  ██████ ██   ██  █████  ████████ 
   ██    ██      ██   ██ ████  ████ ██      ██   ██ ██   ██    ██    
   ██    █████   ██████  ██ ████ ██ ██      ███████ ███████    ██    
   ██    ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██    ██    
   ██    ███████ ██   ██ ██      ██  ██████ ██   ██ ██   ██    ██    
"""


class SplashScreen(Screen):
    """ASCII Art splash screen shown for 2 seconds"""
    
    CSS = """
    SplashScreen {
        align: center middle;
        background: black;
        color: #00ff00;
    }
    
    #splash {
        width: auto;
        height: auto;
        content-align: center middle;
        text-style: bold;
        color: #00ff00;
    }
    """

    def compose(self) -> ComposeResult:
        yield Static(TERMCHAT_ASCII, id="splash")

    def on_mount(self):
        # Auto-advance to connection dialog after 2 seconds
        self.set_timer(2.0, self.show_connection)

    def show_connection(self):
        self.app.push_screen("connection")


class ConnectionScreen(Screen):
    """Modal screen for connection details"""
    
    def __init__(self):
        super().__init__()
        self.connecting = False
    
    CSS = """
    ConnectionScreen {
        align: center middle;
        background: black;
    }
    
    #dialog {
        width: 80;
        height: 25;
        border: solid #00ff00;
        background: black;
        color: white;
    }
    
    #title {
        dock: top;
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: #00ff00;
        background: black;
        padding: 1 0;
    }
    
    #form {
        layout: vertical;
        height: auto;
        margin: 2;
        padding: 2;
    }
    
    .form-row {
        height: 3;
        layout: horizontal;
        margin-bottom: 1;
    }
    
    .label {
        width: 15;
        content-align: right middle;
        margin-right: 2;
        color: #cccccc;
        text-style: bold;
    }
    
    .input {
        width: 35;
        height: 1;
        background: #111111;
        color: white;
        border: solid #333333;
    }
    
    .input:focus {
        border: solid #00ff00;
        background: #001100;
    }
    
    #buttons {
        dock: bottom;
        layout: horizontal;
        height: 2;
        align: center middle;
        background: black;
        padding: 0;
    }
    
    #status_label {
        width: 40;
        content-align: center middle;
        color: yellow;
        text-style: bold;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("tab", "focus_next", "Next Field"),
        Binding("shift+tab", "focus_previous", "Previous Field"),
        Binding("enter", "connect", "Connect"),
    ]

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("TERMCHAT Connection", id="title")
            with Vertical(id="form"):
                with Container(classes="form-row"):
                    yield Label("Username:", classes="label")
                    yield Input(placeholder="Enter username", id="username_input", classes="input")
                with Container(classes="form-row"):
                    yield Label("Chat name:", classes="label")
                    yield Input(placeholder="Enter chat name", id="chatname_input", classes="input")
                with Container(classes="form-row"):
                    yield Label("Password:", classes="label")
                    yield Input(placeholder="Enter password", password=True, id="password_input", classes="input")
                # Status label for connection feedback
                with Container(classes="form-row"):
                    yield Label("", id="status_label", classes="label")
            with Container(id="buttons"):
                pass  # Removed command hints as requested

    def on_mount(self):
        self.query_one("#username_input").focus()
    
    async def on_input_submitted(self, event: Input.Submitted):
        """Handle Enter key in any input field - navigate to next or connect"""
        if event.input.id == "username_input":
            self.query_one("#chatname_input").focus()
        elif event.input.id == "chatname_input":
            self.query_one("#password_input").focus()
        elif event.input.id == "password_input":
            await self.action_connect()

    async def action_connect(self):
        if self.connecting:
            return  # Already connecting
            
        username = self.query_one("#username_input").value.strip()
        chat_name = self.query_one("#chatname_input").value.strip()
        password = self.query_one("#password_input").value.strip()
        
        # Only check for forbidden username, no empty field warnings
        if username.lower() == "server":
            self.app.notify("Username 'server' is forbidden!", severity="error")
            self.query_one("#username_input").focus()
            return
        
        # Use defaults if fields are empty
        if not username:
            username = "guest"
        if not chat_name:
            chat_name = "general"
        if not password:
            password = "default"
        
        # Show connecting status
        self.connecting = True
        status_label = self.query_one("#status_label")
        status_label.update("[yellow]Connecting...[/yellow]")
        
        # Attempt connection first
        try:
            await self.test_connection(username, chat_name, password)
            # If successful, start the chat
            self.app.start_chat(username, chat_name, password)
        except Exception as e:
            # Connection failed, show error and reset
            self.connecting = False
            status_label.update(f"[red]Connection failed: {str(e)}[/red]")
            self.app.notify(f"Could not connect to server: {str(e)}", severity="error")

    async def test_connection(self, username: str, chat_name: str, password: str):
        """Test connection to server before proceeding to chat"""
        import ssl
        ssl_context = ssl.create_default_context()
        
        try:
            # Test connection
            test_ws = await websockets.connect(
                self.app.server_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=5,
                max_size=2**20,
                max_queue=32
            )
            
            # Send test auth message
            auth_message = {
                "type": "join",
                "username": username,
                "chatname": chat_name,
                "password": password
            }
            
            await test_ws.send(json.dumps(auth_message))
            
            # Wait for response (with timeout)
            try:
                response = await asyncio.wait_for(test_ws.recv(), timeout=5.0)
                data = json.loads(response)
                
                # Check if join was successful
                if data.get("type") == "join" and data.get("username") == username:
                    await test_ws.close()
                    return True
                elif data.get("type") == "error":
                    await test_ws.close()
                    raise Exception(data.get("message", "Unknown error"))
                else:
                    await test_ws.close()
                    raise Exception("Unexpected server response")
                    
            except asyncio.TimeoutError:
                await test_ws.close()
                raise Exception("Server response timeout")
            except Exception as e:
                await test_ws.close()
                raise e
                
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 403:
                raise Exception("Server is currently disabled or unavailable")
            else:
                raise Exception(f"Server rejected connection: HTTP {e.status_code}")
        except OSError as e:
            if "Name or service not known" in str(e):
                raise Exception("Cannot resolve server address")
            elif "Connection refused" in str(e):
                raise Exception("Server is not responding")
            else:
                raise Exception(f"Network error: {str(e)}")
        except Exception as e:
            if "server rejected WebSocket connection" in str(e):
                if "403" in str(e):
                    raise Exception("Server is currently disabled or unavailable")
                else:
                    raise Exception("Server rejected connection")
            else:
                raise Exception(f"Connection failed: {str(e)}")

    def action_quit(self):
        self.app.exit()


class ChatScreen(Screen):
    """Main chat screen"""
    
    CSS = """
    ChatScreen {
        layout: vertical;
        background: black;
        color: white;
    }
    
    #header {
        dock: top;
        height: 3;
        background: black;
        color: #00ff00;
        content-align: center middle;
        text-style: bold;
        border-bottom: solid #00ff00;
        padding: 1 0;
    }
    
    #messages_container {
        height: 1fr;
        border: thin #00ff00;
        margin: 0;
        background: black;
    }
    
    #messages {
        height: 1fr;
        scrollbar-gutter: stable;
        border: none;
        background: black;
        color: white;
        padding: 1;
    }
    
    #input_container {
        dock: bottom;
        height: 4;
        border: thin #00ff00;
        margin: 0 0 1 0;
        background: black;
    }
    
    #input_prompt {
        dock: left;
        width: 16;
        content-align: right middle;
        color: #00ff00;
        background: black;
        text-style: bold;
        padding-right: 1;
    }
    
    #message_input {
        width: 1fr;
        border: none;
        background: black;
        color: white;
        margin: 1;
    }
    
    #message_input:focus {
        background: #001100;
        border: solid #333333;
    }
    
    #footer {
        dock: bottom;
        height: 2;
        background: black;
        color: #666666;
        content-align: center middle;
        text-style: italic;
        border-top: solid #333333;
        padding: 0;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]

    def __init__(self, username: str, chat_name: str, password: str):
        super().__init__()
        self.username = username
        self.chat_name = chat_name
        self.password = password

    def compose(self) -> ComposeResult:
        yield Label(f"TERMCHAT - Connecting to '{self.chat_name}'...", id="header")
        with Container(id="messages_container"):
            yield RichLog(id="messages", highlight=True, markup=True)
        with Container(id="input_container"):
            yield Label("Enter message:", id="input_prompt")
            yield Input(placeholder="Type your message here...", id="message_input")
        yield Label("[bold #00ff00]Commands:[/bold #00ff00] /quit, /exit, /q to quit • [bold #00ff00]Ctrl+C[/bold #00ff00] to force quit", id="footer")

    async def on_mount(self):
        """Initialize the chat screen"""
        # Start connection to server
        await self.connect_to_server()

    async def on_input_submitted(self, event: Input.Submitted):
        """Handle user message input"""
        if event.input.id != "message_input":
            return
            
        user_message = event.value.strip()
        event.input.clear()
        
        if not user_message:
            return
            
        # Handle quit commands
        if user_message.lower() in ['/quit', '/exit', '/q']:
            await self.app.action_quit()
            return
        
        # Send message to server
        await self.send_message(user_message)

    def action_quit(self):
        self.app.action_quit()

    async def connect_to_server(self):
        """Establish WebSocket connection to the backend"""
        messages_log = self.query_one("#messages", RichLog)
        
        try:
            # Create SSL context with proper settings
            import ssl
            ssl_context = ssl.create_default_context()
            
            self.app.websocket = await websockets.connect(
                self.app.server_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
                max_size=2**20,  # 1MB max message size
                max_queue=32     # Max queued messages
            )
            
            # Send authentication message
            auth_message = {
                "type": "join",
                "username": self.username,
                "chatname": self.chat_name,
                "password": self.password
            }
            
            await self.app.websocket.send(json.dumps(auth_message))
            
            # Start listening for messages
            asyncio.create_task(self.listen_for_messages())
            
        except websockets.exceptions.InvalidStatusCode as e:
            if e.status_code == 403:
                error_msg = "Server is currently disabled or unavailable"
            else:
                error_msg = f"Server rejected connection: HTTP {e.status_code}"
            messages_log.write(f"[bold red]{error_msg}[/bold red]")
            self.app.notify(error_msg, severity="error")
            self.app.pop_screen()
        except OSError as e:
            if "Name or service not known" in str(e):
                error_msg = "Cannot resolve server address"
            elif "Connection refused" in str(e):
                error_msg = "Server is not responding"
            else:
                error_msg = f"Network error: {str(e)}"
            messages_log.write(f"[bold red]{error_msg}[/bold red]")
            self.app.notify(error_msg, severity="error")
            self.app.pop_screen()
        except Exception as e:
            if "server rejected WebSocket connection" in str(e) and "403" in str(e):
                error_msg = "Server is currently disabled or unavailable"
            else:
                error_msg = f"Failed to connect to server: {e}"
            messages_log.write(f"[bold red]{error_msg}[/bold red]")
            self.app.notify(error_msg, severity="error")
            self.app.pop_screen()

    async def listen_for_messages(self):
        """Listen for incoming messages from the server"""
        messages_log = self.query_one("#messages", RichLog)
        
        try:
            async for message in self.app.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    messages_log.write(f"[bold red]Received invalid JSON: {escape(message[:100])}...[/bold red]")
                except Exception as e:
                    messages_log.write(f"[bold red]Error processing message: {e}[/bold red]")
        except websockets.exceptions.ConnectionClosed:
            messages_log.write("[bold yellow]Connection to server lost.[/bold yellow]")
            self.app.connected = False
            self.query_one("#header").update("TERMCHAT - Disconnected")
            self.app.notify("Connection lost", severity="warning")
        except websockets.exceptions.ConnectionClosedError as e:
            messages_log.write(f"[bold yellow]Connection closed: {e}[/bold yellow]")
            self.app.connected = False
            self.query_one("#header").update("TERMCHAT - Connection Closed")
        except Exception as e:
            messages_log.write(f"[bold red]Error receiving messages: {e}[/bold red]")
            self.app.connected = False

    async def handle_message(self, data):
        """Handle different types of messages from the server"""
        messages_log = self.query_one("#messages", RichLog)
        message_type = data.get("type", "")
        
        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            user_color = self.app.get_user_color(username)
            messages_log.write(f"[{user_color}][{username}]:[/{user_color}] {escape(message)}")
        
        elif message_type == "join":
            username = data.get("username", "Unknown")
            # If it's our own join message, it means successful connection
            if username == self.username:
                self.app.connected = True
                self.query_one("#header").update(f"TERMCHAT - Connected to '{self.chat_name}'")
                messages_log.write("[bold bright_blue][Server]:[/bold bright_blue] Connected successfully")
                messages_log.write(f"[bold #00ff00]Successfully joined chat '{self.chat_name}'[/bold #00ff00]")
                # Focus the input field after successful connection
                self.query_one("#message_input").focus()
            else:
                messages_log.write(f"[bold #00ff00]A wild {username} has appeared.[/bold #00ff00]")
        
        elif message_type == "leave":
            username = data.get("username", "Unknown")
            messages_log.write(f"[bold #00ff00]{username} has left the chat.[/bold #00ff00]")
        
        elif message_type == "error":
            error_message = data.get("message", "Unknown error")
            messages_log.write(f"[bold red]Error: {escape(error_message)}[/bold red]")
            # If connection failed, go back to connection screen
            if not self.app.connected:
                self.app.notify(f"Connection failed: {error_message}", severity="error")
                self.app.pop_screen()  # Return to connection screen
        
        elif message_type == "auth_failed":
            error_message = data.get("message", "Authentication failed")
            messages_log.write(f"[bold red]Authentication failed: {escape(error_message)}[/bold red]")
            self.app.notify(f"Authentication failed: {error_message}", severity="error")
            # Go back to connection screen
            self.app.pop_screen()

    async def send_message(self, user_message: str):
        """Send message to server"""
        if self.app.websocket and self.app.connected:
            try:
                message_data = {
                    "type": "message",
                    "content": user_message
                }
                await self.app.websocket.send(json.dumps(message_data))
            except websockets.exceptions.ConnectionClosed:
                messages_log = self.query_one("#messages", RichLog)
                messages_log.write("[bold red]Cannot send message: Connection closed[/bold red]")
                self.app.connected = False
                self.query_one("#header").update("TERMCHAT - Disconnected")
            except Exception as e:
                messages_log = self.query_one("#messages", RichLog)
                messages_log.write(f"[bold red]Error sending message: {e}[/bold red]")
        else:
            messages_log = self.query_one("#messages", RichLog)
            messages_log.write("[bold yellow]Not connected to server. Cannot send message.[/bold yellow]")


class TermchatApp(App):
    """Main Termchat application using proper screen management"""

    SCREENS = {
        "splash": SplashScreen,
        "connection": ConnectionScreen,
    }
    
    def __init__(self):
        super().__init__()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.user_colors: dict = {}  # Maps usernames to colors
        self.color_index: int = 0    # For cycling through colors
        self.connected: bool = False
        
        # Backend server URL (HTTPS WebSocket on port 443)
        self.server_url = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net"

    def on_mount(self):
        """Start with the splash screen"""
        self.push_screen("splash")

    def start_chat(self, username: str, chat_name: str, password: str):
        """Start the chat with the given credentials"""
        chat_screen = ChatScreen(username, chat_name, password)
        self.push_screen(chat_screen)

    def get_user_color(self, username: str) -> str:
        """Get or assign a color for a username"""
        if username.lower() == "server":
            return "bold bright_blue"
        
        if username not in self.user_colors:
            self.user_colors[username] = USER_COLORS[self.color_index % len(USER_COLORS)]
            self.color_index += 1
        
        return self.user_colors[username]

    async def action_quit(self):
        """Quit the application"""
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        self.exit()


async def main():
    """Entry point for the application"""
    app = TermchatApp()
    await app.run_async()


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