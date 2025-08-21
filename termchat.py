#!/usr/bin/env python3

# Termchat - Cross-platform Python terminal client for real-time chat
# Connects to termchat-backend via HTTPS WebSocket on port 443

import asyncio
import websockets
import json
import sys
import certifi
import ssl
from typing import Optional
from textual.app import App, ComposeResult
from textual.containers import Container, Vertical
from textual.widgets import Input, RichLog, Static, Label
from textual.binding import Binding
from textual.screen import Screen
from rich.markup import escape
import os
import platform
import subprocess
import shlex
import aiohttp


def is_in_terminal():
    # Heuristically check if we're running in a real terminal.
    return sys.stdin.isatty()

def launch_new_terminal():
    # Attempt to launch a new terminal window running this script.
    script_path = os.path.abspath(__file__)

    if platform.system() == "Windows":
        python = shlex.quote(sys.executable)
        if script_path.lower().endswith(".py"):
            cmd = f'start cmd /k {python} "{script_path}"'
        else:
            cmd = f'start cmd /k "{script_path}"'
        os.system(cmd)
        sys.exit(0)

    elif platform.system() == "Darwin":
        python = shlex.quote(sys.executable)
        # Set bounds for the window (pixels)
        left, top = 100, 100
        right, bottom = left + 912, top + 520
    
        # Launch the script in Terminal, reusing the same window if one already exists.
        # If no Terminal windows exist, this creates one and sets bounds.
        applescript = f'''
        tell application "Terminal"
            activate
            if (count of windows) = 0 then
                -- no windows: create a new window and run the command
                set theResult to do script "{python} {script_path}"
                delay 0.12
                try
                    set bounds of front window to {{{left}, {top}, {right}, {bottom}}}
                end try
            else
                -- there is an existing window: run in the front window (creates a new tab in that window)
                do script "{python} {script_path}" in front window
            end if
        end tell
        '''
        cmd = f'osascript -e {shlex.quote(applescript)}'
        os.system(cmd)
        sys.exit(0)

    elif platform.system() == "Linux":
        python = shlex.quote(sys.executable)
        terminals = [
            f'gnome-terminal -- {python} "{script_path}"',
            f'konsole -e {python} "{script_path}"',
            f'xfce4-terminal -e "{python} {script_path}"',
            f'xterm -e {python} "{script_path}"'
        ]
        for term in terminals:
            try:
                subprocess.Popen(term, shell=True)
                sys.exit(0)
            except Exception:
                continue
        print("No supported terminal emulator found. Please run this script from a terminal.")
        sys.exit(1)
    else:
        print("Unsupported OS.")
        sys.exit(1)
        
async def get_general_count(server_url: str) -> int:
    # Converts wss://... to https://... and gets /general-count using certifi-backed SSL.
    http_host = server_url.replace("wss://", "https://").split("/")[2]
    endpoint = f"https://{http_host}/general-count"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        async with aiohttp.ClientSession(connector=connector) as session:
            async with session.get(endpoint, timeout=3) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("userCount", 0)
    except Exception:
        pass
    return 0

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
    # ASCII Art splash screen shown with a slide-up + fade-in animation
    
    CSS = """
    SplashScreen {
        align: center middle;
        background: black;
        color: #87CEEB;
    }
    
    #splash {
        width: auto;
        height: auto;
        content-align: center middle;
        text-style: bold;
        color: #87CEEB;
    }
    """

    def compose(self) -> ComposeResult:
        # Create the Static so we can animate it in on_mount.
        yield Static(TERMCHAT_ASCII, id="splash")

    def on_mount(self):
        # Start the splash animation asynchronously and advance when done.
        asyncio.create_task(self._animate_and_advance())

    async def _animate_and_advance(self):
        # Animate the splash logo: slide up from below and fade in with a strong ease-out.
        # After the animation completes we wait a short moment then move to the connection screen.
        
        # Strong ease-out function (exponential) for a noticeable fast-then-slow effect
        def ease_out_expo(t: float) -> float:
            if t >= 1.0:
                return 1.0
            return 1 - pow(2, -20 * t)

        # 60fps animation parameters
        duration = 1.2
        target_fps = 60
        frame_time = 1.0 / target_fps
        total_frames = int(duration * target_fps)
        start_offset_y = 25  # start a few rows lower (slides up to 0)
        
        try:
            splash = self.query_one("#splash", Static)
            
            # Initialize starting position and color fade
            splash.styles.opacity = 0.0
            splash.styles.offset = (0, start_offset_y)
            splash.styles.color = "#000000"  # Start black for color fade
            
            self.refresh()
            await asyncio.sleep(0.016)
            
            # 60fps animation loop - slide up AND color fade
            for i in range(total_frames + 1):
                t = i / total_frames
                eased = ease_out_expo(t)
                
                # Slide animation
                y = int(start_offset_y * (1 - eased))
                opacity = float(eased)
                
                # Color fade animation (black to cyan)
                r = int(135 * eased)  # #87CEEB = 135, 206, 235
                g = int(206 * eased)
                b = int(235 * eased)
                color = f"#{r:02x}{g:02x}{b:02x}"
                
                # Apply all animations
                splash.styles.offset = (0, y)
                splash.styles.opacity = opacity
                splash.styles.color = color
                
                splash.refresh()
                await asyncio.sleep(frame_time)

            # Ensure final exact values
            splash.styles.offset = (0, 0)
            splash.styles.opacity = 1.0
            splash.styles.color = "#87CEEB"
            splash.refresh()
            
        except Exception:
            await asyncio.sleep(duration)

        await asyncio.sleep(0.25)
        self.show_connection()

    def show_connection(self):
        self.app.push_screen("connection")


class ConnectionScreen(Screen):
    # Modal screen for connection details 
    
    def __init__(self):
        super().__init__()
        self.connecting = False
        self.general_count = None
        
    CSS = """
    ConnectionScreen {
        align: center middle;
        background: black;
    }
    
    #dialog {
        width: 80;
        height: 25;
        border: solid #87CEEB;
        background: black;
        color: white;
    }
    #title {
        dock: top;
        width: 100%;
        content-align: center middle;
        text-style: bold;
        color: #87CEEB;
        background: black;
        padding: 1 0;
    }
    #indicator_row {
        layout: horizontal;
        width: 100%;
        align: center middle;
        margin-bottom: 1;
    }
    #indicator_light {
        width: 2;
        content-align: center middle;
    }
    #indicator_text {
        margin-left: 1;
        color: white;
    }

    #hint_row {
        width: 100%;
        content-align: center middle;
        margin-top: 2;
    }
    #form {
        layout: vertical;
        height: auto;
        margin: 2;
        padding: 1;
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
        height: 3;
        color: white;
        border: solid #333333;
    }
    .input:focus {
        border: solid #87CEEB;
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
            with Container(id="indicator_row"):
                yield Static("●", id="indicator_light")
                yield Label("Checking server...", id="indicator_text")
            yield Container(
                Label(
                    "       Keep the [#cccccc]chat name[/#cccccc] and [#cccccc]password[/#cccccc] blank to join the [#90ee90]general chat[/#90ee90]",
                    markup=True
                ),
                id="hint_row"
            )
            with Container(id="form"):
                with Container(classes="form-row"):
                    yield Label("Username:", classes="label")
                    yield Input(placeholder="Enter username", id="username_input", classes="input")
                with Container(classes="form-row"):
                    yield Label("Chat name:", classes="label")
                    yield Input(placeholder="Enter chat name", id="chatname_input", classes="input")
                with Container(classes="form-row"):
                    yield Label("Password:", classes="label")
                    yield Input(placeholder="Enter password", password=True, id="password_input", classes="input")
                with Container(classes="form-row"):
                    yield Label("", id="status_label", classes="label")
        yield Label("", id="general_count_label")

    def on_mount(self):
        self.query_one("#username_input").focus()
        self.set_timer(0.1, self.check_server_status)
        asyncio.create_task(self.update_general_count())

    async def update_general_count(self):
        count = await get_general_count(self.app.server_url)
        self.general_count = count
        label = self.query_one("#general_count_label")
        label.update(f"[#90ee90]{count}[/#90ee90] user/s in general chat")

    async def check_server_status(self):
    # Foolproof: check server reachability using a certifi-backed SSL context
        try:
            import websockets  # keep local import if desired
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            # short timeout/ping to keep this check fast
            ws = await websockets.connect(self.app.server_url, ssl=ssl_context, ping_timeout=2)
            await ws.close()
            self.server_available = True
        except Exception:
            self.server_available = False
        self.update_indicator()

    def update_indicator(self):
        indicator_light = self.query_one("#indicator_light")
        indicator_text = self.query_one("#indicator_text")
        if self.server_available:
            indicator_light.update("●")
            indicator_light.styles.color = "#00ff00"
            indicator_text.update("Server available")
            indicator_text.styles.color = "#00ff00"
        else:
            indicator_light.update("●")
            indicator_light.styles.color = "#ff0000"
            indicator_text.update("Server unavailable")
            indicator_text.styles.color = "#ff0000"
    
    async def on_input_submitted(self, event: Input.Submitted):
        # Handle Enter key in any input field - navigate to next or connect
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
        
        # Start the chat directly - no separate test connection to avoid duplicate join/leave notifications
        try:
            self.app.start_chat(username, chat_name, password)
        except Exception as e:
            # Connection failed, show error and reset
            self.connecting = False
            status_label.update(f"[red]Connection failed: {str(e)}[/red]")
            self.app.notify(f"Could not connect to server: {str(e)}", severity="error")


    def action_quit(self):
        self.app.exit()


class ChatScreen(Screen):
    # Main chat screen
    
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
        color: #87CEEB;
        content-align: center middle;
        text-style: bold;
        padding: 1 0;
    }
    
    #messages_container {
        height: 1fr;
        border: solid #87CEEB;
        margin: 0;
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
        height: 5;
        border: solid #87CEEB;
        margin: 0 0 1 0;
        padding: 1;
        content-align: center middle;
    }
    
    #message_input {
        width: 1fr;
        height: 3;
        border: none;
        background: black;
        color: white;
        content-align: center middle;
    }
    
    #message_input:focus {
        border: none;
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
            yield Input(placeholder="Type your message here...", id="message_input")

    async def on_mount(self):
        # Initialize the chat screen
        # Start connection to server
        await self.connect_to_server()
        input_widget = self.query_one("#message_input")
        input_widget.can_focus = True
        input_widget.focus()

    async def on_input_submitted(self, event: Input.Submitted):
        # Handle user message input
        if event.input.id != "message_input":
            return
            
        user_message = event.value.strip()
        event.input.clear()

        if not user_message:
            return
        
        # Handle clear command
        if user_message.lower() in ['/clear','/c']:
            messages_log = self.query_one("#messages", RichLog)
            messages_log.clear()
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
        # Establish WebSocket connection to the backend
        messages_log = self.query_one("#messages", RichLog)
        
        try:
            # Create SSL context with proper settings
            import ssl
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())
            
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
            
            # Wait for join confirmation before considering connection complete
            try:
                while True:
                    response = await asyncio.wait_for(self.app.websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    
                    if data.get("type") == "join" and data.get("username") == self.username:
                        # Join successful - set connected state
                        self.app.connected = True
                        self.query_one("#header").update(f"TERMCHAT - Connected to server:'{self.chat_name}'")
                        messages_log.write(f"[bold #87CEEB]Successfully joined chat '{self.chat_name}'[/bold #87CEEB]")
                        # Focus the input field after successful connection
                        self.query_one("#message_input").focus()
                        break
                    elif data.get("type") == "message":
                        # Handle server messages during connection
                        username = data.get("username", "Unknown")
                        message = data.get("content", "")
                        
                        if username == "Server":
                            messages_log.write(f"[bold #87CEEB]Server:[/bold #87CEEB] {escape(message)}")
                        else:
                            user_color = self.app.get_user_color(username)
                            messages_log.write(f"[{user_color}]\\[{escape(username)}]:[/{user_color}] {escape(message)}")
                    elif data.get("type") == "error":
                        error_message = data.get("message", "Connection failed")
                        raise Exception(error_message)
                        
            except asyncio.TimeoutError:
                raise Exception("Server response timeout - no join confirmation received")
            
            # Start listening for messages after successful join
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
        # Listen for incoming messages from the server
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
        # Handle different types of messages from the server
        messages_log = self.query_one("#messages", RichLog)
        message_type = data.get("type", "")
        
        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            
            # Display messages with proper formatting - show ALL messages including own
            if username == "Server":
                messages_log.write(f"[bold #87CEEB]Server:[/bold #87CEEB] {escape(message)}")
            else:
                user_color = self.app.get_user_color(username)
                messages_log.write(f"[{user_color}]\\[{escape(username)}]:[/{user_color}] {escape(message)}")
        
        elif message_type == "join":
            username = data.get("username", "Unknown")
            # Handle other users joining - server doesn't send join notifications back to joining user
            if username and username != self.username:
                messages_log.write(f"[bold #87CEEB]A wild {escape(username)} has appeared.[/bold #87CEEB]")
        
        elif message_type == "leave":
            username = data.get("username", "Unknown") 
            # Show leave notifications for all users
            if username and username != self.username:
                messages_log.write(f"[bold #87CEEB]{escape(username)} has left the chat.[/bold #87CEEB]")
        
        elif message_type == "colourshift":
            # Handle theme color change
            new_color = data.get("color", "#87CEEB")
            await self.change_theme_color(new_color)
            # messages_log.write(f"[bold {new_color}]Theme color changed to {new_color}[/bold {new_color}]")
        
        elif message_type == "bgshift":
            messages_log = self.query_one("#messages", RichLog)
            messages_log.clear()
            bg_color = data.get("color", "#000000")
            await self.change_background_color(bg_color)

        elif message_type == "chatclear":
            messages_log = self.query_one("#messages", RichLog)
            messages_log.clear()

        elif message_type == "kicked":
            kicked_message = data.get("message", "You have been kicked :)")
            messages_log = self.query_one("#messages", RichLog)
            messages_log.clear()
            messages_log.write(f"[bold #FF0000]{kicked_message}[/bold #FF0000]")
            await asyncio.sleep(5)
            await self.app.action_quit()
            return
        
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
        # Send message to server
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

async def change_theme_color(self, new_color: str):
    # Change the theme color of the interface with smooth transition
    duration = 0.3  # seconds
    target_fps = 60
    frame_time = 1.0 / target_fps
    total_frames = int(duration * target_fps)
    
    # Get current color (default to current theme color)
    current_color = self.app.theme_color
    
    # Parse colors to RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (135, 206, 235)  # Default cyan fallback
    
    def rgb_to_hex(r, g, b):
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
    
    start_rgb = hex_to_rgb(current_color)
    end_rgb = hex_to_rgb(new_color)
    
    try:
        # Get references to elements
        header = self.query_one("#header")
        messages_container = self.query_one("#messages_container")
        input_container = self.query_one("#input_container")
        
        # Animate the color transition with linear interpolation
        for i in range(total_frames + 1):
            t = i / total_frames
            
            # Linear interpolation of RGB values
            r = start_rgb[0] + (end_rgb[0] - start_rgb[0]) * t
            g = start_rgb[1] + (end_rgb[1] - start_rgb[1]) * t
            b = start_rgb[2] + (end_rgb[2] - start_rgb[2]) * t
            
            current_color = rgb_to_hex(r, g, b)
            
            # Apply the color to all theme elements
            header.styles.color = current_color
            messages_container.styles.border = ("solid", current_color)
            input_container.styles.border = ("solid", current_color)
            
            # Refresh the display
            header.refresh()
            messages_container.refresh()
            input_container.refresh()
            
            await asyncio.sleep(frame_time)
        
        # Ensure final exact color
        header.styles.color = new_color
        messages_container.styles.border = ("solid", new_color)
        input_container.styles.border = ("solid", new_color)
        
        # Store the new color in the app for future use
        self.app.theme_color = new_color
        
    except Exception:
        # Fallback to instant change if animation fails
        header = self.query_one("#header")
        messages_container = self.query_one("#messages_container")
        input_container = self.query_one("#input_container")
        
        header.styles.color = new_color
        messages_container.styles.border = ("solid", new_color)
        input_container.styles.border = ("solid", new_color)
        
        self.app.theme_color = new_color

async def change_background_color(self, bg_color: str):
    # Change the background color of the entire chat interface with smooth transition
    duration = 0.6  # seconds
    target_fps = 60
    frame_time = 1.0 / target_fps
    total_frames = int(duration * target_fps)
    
    # Get current background color (default to black)
    current_bg = getattr(self.app, 'background_color', '#000000')
    
    # Parse colors to RGB
    def hex_to_rgb(hex_color):
        hex_color = hex_color.lstrip('#')
        if len(hex_color) == 6:
            return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))
        return (0, 0, 0)  # Default black fallback
    
    def rgb_to_hex(r, g, b):
        return f"#{int(r):02x}{int(g):02x}{int(b):02x}"
    
    def darken_color(r, g, b, factor=0.7):
        # Make color darker by multiplying by factor
        return (r * factor, g * factor, b * factor)
    
    def scrollbar_color(r, g, b, factor=0.5):
        # Make color much darker for scrollbar
        return (r * factor, g * factor, b * factor)
    
    start_rgb = hex_to_rgb(current_bg)
    end_rgb = hex_to_rgb(bg_color)
    
    # Calculate darker versions for scrollbars and input areas
    start_dark_rgb = darken_color(*start_rgb)
    end_dark_rgb = darken_color(*end_rgb)
    
    # Calculate scrollbar colors (even darker)
    start_scrollbar_rgb = scrollbar_color(*start_rgb)
    end_scrollbar_rgb = scrollbar_color(*end_rgb)
    
    # Ease-out function for smooth transition
    def ease_out_cubic(t):
        return 1 - pow(1 - t, 3)
    
    try:
        # Get references to elements
        header = self.query_one("#header")
        messages_container = self.query_one("#messages_container")
        messages = self.query_one("#messages")
        input_container = self.query_one("#input_container")
        message_input = self.query_one("#message_input")
        
        # Animate the background color transition
        for i in range(total_frames + 1):
            t = i / total_frames
            eased = ease_out_cubic(t)
            
            # Interpolate main background RGB values
            r = start_rgb[0] + (end_rgb[0] - start_rgb[0]) * eased
            g = start_rgb[1] + (end_rgb[1] - start_rgb[1]) * eased
            b = start_rgb[2] + (end_rgb[2] - start_rgb[2]) * eased
            
            # Interpolate darker background RGB values
            dark_r = start_dark_rgb[0] + (end_dark_rgb[0] - start_dark_rgb[0]) * eased
            dark_g = start_dark_rgb[1] + (end_dark_rgb[1] - start_dark_rgb[1]) * eased
            dark_b = start_dark_rgb[2] + (end_dark_rgb[2] - start_dark_rgb[2]) * eased
            
            current_bg = rgb_to_hex(r, g, b)
            current_dark = rgb_to_hex(dark_r, dark_g, dark_b)
            
            # Apply the main background color
            self.styles.background = current_bg
            header.styles.background = current_bg
            messages_container.styles.background = current_bg
            messages.styles.background = current_bg
            input_container.styles.background = current_bg
            
            # Apply darker background to input area
            message_input.styles.background = current_dark
            
            # Apply scrollbar colors to messages widget
            messages.styles.scrollbar_background = current_dark
            messages.styles.scrollbar_color = current_scrollbar
            
            # Refresh all elements
            self.refresh()
            header.refresh()
            messages_container.refresh()
            messages.refresh()
            input_container.refresh()
            message_input.refresh()
            
            await asyncio.sleep(frame_time)
        
        # Ensure final exact colors
        dark_final = rgb_to_hex(*darken_color(*end_rgb))
        scrollbar_final = rgb_to_hex(*scrollbar_color(*end_rgb))
        
        self.styles.background = bg_color
        header.styles.background = bg_color
        messages_container.styles.background = bg_color
        messages.styles.background = bg_color
        input_container.styles.background = bg_color
        message_input.styles.background = dark_final
        
        # Set final scrollbar colors
        messages.styles.scrollbar_background = dark_final
        messages.styles.scrollbar_color = scrollbar_final
        
        # Store the new color in the app for future use
        self.app.background_color = bg_color
        
    except Exception:
        # Fallback to instant change if animation fails
        dark_bg = rgb_to_hex(*darken_color(*end_rgb))
        
        self.styles.background = bg_color
        header = self.query_one("#header")
        header.styles.background = bg_color
        messages_container = self.query_one("#messages_container")
        messages_container.styles.background = bg_color
        messages = self.query_one("#messages")
        messages.styles.background = bg_color
        input_container = self.query_one("#input_container")
        input_container.styles.background = bg_color
        message_input = self.query_one("#message_input")
        message_input.styles.background = dark_bg
        
        self.app.background_color = bg_color

class TermchatApp(App):
    # Main Termchat application using proper screen management

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
        self.theme_color: str = "#87CEEB"  # Current theme color
        
        # Backend server URL (HTTPS WebSocket on port 443)
        self.server_url = "wss://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net"

    def on_mount(self):
        # Start with the splash screen
        self.push_screen("splash")

    def start_chat(self, username: str, chat_name: str, password: str):
        # Start the chat with the given credentials
        chat_screen = ChatScreen(username, chat_name, password)
        self.push_screen(chat_screen)

    def get_user_color(self, username: str) -> str:
        # Get or assign a color for a username
        if username.lower() == "server":
            return "bold #87CEEB"
        
        if username not in self.user_colors:
            self.user_colors[username] = USER_COLORS[self.color_index % len(USER_COLORS)]
            self.color_index += 1
        
        return self.user_colors[username]

    async def action_quit(self):
        # Quit the application
        if self.websocket:
            try:
                await self.websocket.close()
            except:
                pass
        self.exit()


async def main():
    # Entry point for the application
    app = TermchatApp()
    await app.run_async()

if __name__ == "__main__":
    try:
        # Ensure asyncio compatibility across platforms
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        # Relaunch in terminal if not already in one
        if not is_in_terminal():
            launch_new_terminal()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as e:
        print(f"Application error: {e}")
        sys.exit(1)
