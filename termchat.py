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
    
    CSS = """
    ConnectionScreen {
        align: center middle;
        background: black;
    }
    
    #dialog {
        width: 60;
        height: 20;
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
        margin: 1;
        padding: 1;
    }
    
    .form-row {
        height: 4;
        layout: horizontal;
        margin-bottom: 1;
        margin-top: 1;
    }
    
    .label {
        width: 12;
        content-align: right middle;
        margin-right: 1;
        color: #cccccc;
        text-style: bold;
    }
    
    .input {
        width: 1fr;
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
        height: 3;
        align: center middle;
        background: black;
        padding: 1 0;
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
            with Container(id="buttons"):
                yield Static("[bold #00ff00]Tab[/bold #00ff00]: Navigate • [bold #00ff00]Enter[/bold #00ff00]: Connect • [bold #00ff00]Ctrl+C[/bold #00ff00]: Quit")

    def on_mount(self):
        self.query_one("#username_input").focus()
    
    async def on_input_submitted(self, event: Input.Submitted):
        """Handle Enter key in any input field"""
        self.action_connect()

    def action_connect(self):
        username = self.query_one("#username_input").value.strip()
        chat_name = self.query_one("#chatname_input").value.strip()
        password = self.query_one("#password_input").value.strip()
        
        if not username:
            self.app.notify("Username cannot be empty!", severity="error")
            self.query_one("#username_input").focus()
            return
        if username.lower() == "server":
            self.app.notify("Username 'server' is forbidden!", severity="error")
            self.query_one("#username_input").focus()
            return
        if not chat_name:
            self.app.notify("Chat name cannot be empty!", severity="error")  
            self.query_one("#chatname_input").focus()
            return
        if not password:
            self.app.notify("Password cannot be empty!", severity="error")
            self.query_one("#password_input").focus()
            return
        
        # Start the chat with these credentials
        self.app.start_chat(username, chat_name, password)

    def action_quit(self):
        self.app.exit()


class ChatScreen(Screen):
    """Main chat screen"""
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
        border: solid #00ff00;
        margin: 1;
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
        border: solid #00ff00;
        margin: 0 1 1 1;
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
        await self.app.connect_to_server(self.username, self.chat_name, self.password)

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
        await self.app.send_message(user_message)

    def action_quit(self):
        self.app.action_quit()


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

    async def connect_to_server(self, username: str, chat_name: str, password: str):
        """Establish WebSocket connection to the backend"""
        messages_log = self.query_one("#messages", RichLog)
        
        try:
            # Create SSL context with proper settings
            import ssl
            ssl_context = ssl.create_default_context()
            
            self.websocket = await websockets.connect(
                self.server_url,
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
                "username": username,
                "chatname": chat_name,
                "password": password
            }
            
            await self.websocket.send(json.dumps(auth_message))
            
            # Start listening for messages
            asyncio.create_task(self.listen_for_messages())
            
        except websockets.exceptions.InvalidURI:
            messages_log.write("[bold red]Error: Invalid server URL[/bold red]")
            self.notify("Invalid server URL", severity="error")
        except websockets.exceptions.ConnectionClosed:
            messages_log.write("[bold red]Error: Connection was closed by server[/bold red]") 
            self.notify("Connection closed by server", severity="error")
        except OSError as e:
            messages_log.write(f"[bold red]Network error: {e}[/bold red]")
            self.notify(f"Network error: {e}", severity="error")
        except Exception as e:
            messages_log.write(f"[bold red]Failed to connect to server: {e}[/bold red]")
            self.notify(f"Connection failed: {e}", severity="error")

    def get_user_color(self, username: str) -> str:
        """Get or assign a color for a username"""
        if username.lower() == "server":
            return "bold bright_blue"
        
        if username not in self.user_colors:
            self.user_colors[username] = USER_COLORS[self.color_index % len(USER_COLORS)]
            self.color_index += 1
        
        return self.user_colors[username]

    async def listen_for_messages(self):
        """Listen for incoming messages from the server"""
        messages_log = self.query_one("#messages", RichLog)
        
        try:
            async for message in self.websocket:
                try:
                    data = json.loads(message)
                    await self.handle_message(data)
                except json.JSONDecodeError:
                    messages_log.write(f"[bold red]Received invalid JSON: {escape(message[:100])}...[/bold red]")
                except Exception as e:
                    messages_log.write(f"[bold red]Error processing message: {e}[/bold red]")
        except websockets.exceptions.ConnectionClosed:
            messages_log.write("[bold yellow]Connection to server lost.[/bold yellow]")
            self.connected = False
            self.query_one("#header").update("TERMCHAT - Disconnected")
            self.notify("Connection lost", severity="warning")
        except websockets.exceptions.ConnectionClosedError as e:
            messages_log.write(f"[bold yellow]Connection closed: {e}[/bold yellow]")
            self.connected = False
            self.query_one("#header").update("TERMCHAT - Connection Closed")
        except Exception as e:
            messages_log.write(f"[bold red]Error receiving messages: {e}[/bold red]")
            self.connected = False

    async def handle_message(self, data):
        """Handle different types of messages from the server"""
        messages_log = self.query_one("#messages", RichLog)
        message_type = data.get("type", "")
        
        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            user_color = self.get_user_color(username)
            messages_log.write(f"[{user_color}][{username}]:[/{user_color}] {escape(message)}")
        
        elif message_type == "join":
            username = data.get("username", "Unknown")
            messages_log.write(f"[bold #00ff00]A wild {username} has appeared.[/bold #00ff00]")
        
        elif message_type == "leave":
            username = data.get("username", "Unknown")
            messages_log.write(f"[bold #00ff00]{username} has left the chat.[/bold #00ff00]")
        
        elif message_type == "error":
            error_message = data.get("message", "Unknown error")
            messages_log.write(f"[bold red]Error: {escape(error_message)}[/bold red]")
        
        elif message_type == "auth_success":
            self.connected = True
            chat_name = self.screen.chat_name if hasattr(self.screen, 'chat_name') else "Unknown"
            self.query_one("#header").update(f"TERMCHAT - Connected to '{chat_name}'")
            messages_log.write("[bold bright_blue][Server]:[/bold bright_blue] Connected successfully")
            messages_log.write(f"[bold #00ff00]Successfully joined chat '{chat_name}'[/bold #00ff00]")
            # Focus the input field after successful connection
            self.query_one("#message_input").focus()
        
        elif message_type == "auth_failed":
            error_message = data.get("message", "Authentication failed")
            messages_log.write(f"[bold red]Authentication failed: {escape(error_message)}[/bold red]")
            self.notify(f"Authentication failed: {error_message}", severity="error")

    async def send_message(self, user_message: str):
        """Send message to server"""
        if self.websocket and self.connected:
            try:
                message_data = {
                    "type": "message",
                    "content": user_message
                }
                await self.websocket.send(json.dumps(message_data))
            except websockets.exceptions.ConnectionClosed:
                messages_log = self.query_one("#messages", RichLog)
                messages_log.write("[bold red]Cannot send message: Connection closed[/bold red]")
                self.connected = False
                self.query_one("#header").update("TERMCHAT - Disconnected")
            except Exception as e:
                messages_log = self.query_one("#messages", RichLog)
                messages_log.write(f"[bold red]Error sending message: {e}[/bold red]")
        else:
            messages_log = self.query_one("#messages", RichLog)
            messages_log.write("[bold yellow]Not connected to server. Cannot send message.[/bold yellow]")

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