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
        # Query the splash widget
        try:
            splash = self.query_one("#splash", Static)
        except Exception:
            # Fallback: if widget isn't present, just advance
            self.show_connection()
            return

        # Strong ease-out function (exponential) for a noticeable fast-then-slow effect
        def ease_out_expo(t: float) -> float:
            if t >= 1.0:
                return 1.0
            # 1 - 2^(-10t) gives a very noticeable ease out
            return 1 - pow(2, -20 * t)

        # Animation parameters
        duration = 1.2   # seconds (long enough to notice)
        frames = 70       # smoothness
        start_offset_y =  50  # start a few rows lower (slides up to 0)
        
        # Try to use styles.offset and styles.opacity; if unavailable, skip animation gracefully.
        use_styles = True
        try:
            # initialize
            splash.styles.opacity = 0.0
            splash.styles.offset = (0, start_offset_y)
        except Exception:
            use_styles = False

        if use_styles:
            for i in range(frames + 1):
                t = i / frames
                eased = ease_out_expo(t)
                y = int(start_offset_y * (1 - eased))
                opacity = float(eased)
                try:
                    splash.styles.offset = (0, y)
                    splash.styles.opacity = opacity
                except Exception:
                    # If styles stop working mid-animation, break out and finalize.
                    break
                await asyncio.sleep(duration / frames)

            # Ensure final exact values
            try:
                splash.styles.offset = (0, 0)
                splash.styles.opacity = 1.0
            except Exception:
                pass
        else:
            # Fallback: simple timed pause so the splash is visible, without animation.
            await asyncio.sleep(duration)

        # Short pause so the user sees the final state, then advance to connection screen.
        await asyncio.sleep(0.25)
        self.show_connection()

    def show_connection(self):
        self.app.push_screen("connection")


class ConnectionScreen(Screen):
    # Modal screen for connection details - uses dialog.animate and pushes ChatScreen.
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
    #indicator_light { width: 2; content-align: center middle; }
    #indicator_text { margin-left: 1; color: white; }
    #hint_row { width: 100%; content-align: center middle; margin-top: 2; }
    #form { layout: vertical; height: auto; margin: 2; padding: 1; }
    .form-row { height: 3; layout: horizontal; margin-bottom: 1; }
    .label { width: 15; content-align: right middle; margin-right: 2; color: #cccccc; text-style: bold; }
    .input { width: 35; height: 3; color: white; border: solid #333333; }
    .input:focus { border: solid #87CEEB; }
    #status_label { width: 40; content-align: center middle; color: yellow; text-style: bold; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("escape", "quit", "Quit"),
        Binding("tab", "focus_next", "Next Field"),
        Binding("shift+tab", "focus_previous", "Previous Field"),
        Binding("enter", "connect", "Connect"),
    ]

    def __init__(self):
        super().__init__()
        self.connecting = False
        self.general_count = None

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("TERMCHAT Connection", id="title")
            with Container(id="indicator_row"):
                yield Static("●", id="indicator_light")
                yield Label("Checking server...", id="indicator_text")
            yield Container(
                Label(
                    "       Keep the [#cccccc]chat name[/#cccccc] and [#cccccc]password[/#cccccc] blank to join the [#90ee90]general chat[/#90ee90]",
                    markup=True,
                ),
                id="hint_row",
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
        try:
            import websockets
            ssl_context = ssl.create_default_context(cafile=certifi.where())
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
        if event.input.id == "username_input":
            self.query_one("#chatname_input").focus()
        elif event.input.id == "chatname_input":
            self.query_one("#password_input").focus()
        elif event.input.id == "password_input":
            await self.action_connect()

    async def action_connect(self):
        # Robust: use widget.animate only (no direct .styles writes) and rely on ChatScreen to animate itself on mount.
        if self.connecting:
            return
        self.connecting = True

        username = self.query_one("#username_input").value.strip()
        chat_name = self.query_one("#chatname_input").value.strip()
        password = self.query_one("#password_input").value.strip()

        if username.lower() == "server":
            self.app.notify("Username 'server' is forbidden!", severity="error")
            self.query_one("#username_input").focus()
            self.connecting = False
            return

        if not username:
            username = "guest"
        if not chat_name:
            chat_name = "general"
        if not password:
            password = "default"

        dialog = self.query_one("#dialog")
        dialog_anim = getattr(dialog, "animate", None)
        if dialog_anim is not None:
            try:
                # fade dialog out quickly for immediate feedback
                await dialog.animate("opacity", 0.0, duration=0.18)
            except Exception:
                # fall back to short pause
                await asyncio.sleep(0.18)
        else:
            await asyncio.sleep(0.18)

        # Push the ChatScreen which contains its own mount animation
        chat_screen = ChatScreen(username, chat_name, password)
        self.app.push_screen(chat_screen)

        # small yield so framework schedules mount handlers
        await asyncio.sleep(0.02)

        self.connecting = False

    def action_quit(self):
        self.app.exit()


class ChatScreen(Screen):
    # Main chat screen — the root container is initially hidden via CSS and then animated on mount.
    CSS = """
    ChatScreen {
        layout: vertical;
        background: black;
        color: white;
    }

    /* start hidden so on_mount can animate to visible without writing to .styles */
    #root {
        width: 100%;
        height: 100%;
        opacity: 0.0;
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
        # Everything wrapped in #root so we can animate that widget's opacity.
        with Container(id="root"):
            yield Label(f"TERMCHAT - Connecting to '{self.chat_name}'...", id="header")
            with Container(id="messages_container"):
                yield RichLog(id="messages", highlight=True, markup=True)
            with Container(id="input_container"):
                yield Input(placeholder="Type your message here...", id="message_input")

    async def on_mount(self):
        # Start connection in background so mount and animation are not blocked.
        asyncio.create_task(self.connect_to_server())

        # Attempt to animate the #root container's opacity from 0 -> 1 using widget.animate.
        # This avoids direct .styles writes that can raise in some Textual versions.
        try:
            root = self.query_one("#root")
        except Exception:
            root = None

        if root is not None:
            anim = getattr(root, "animate", None)
            if anim is not None:
                try:
                    # visible fade-in (duration tuned to be noticeable)
                    await root.animate("opacity", 1.0, duration=0.45)
                except Exception:
                    # fallback small pause if animate isn't available or fails
                    await asyncio.sleep(0.45)
            else:
                await asyncio.sleep(0.45)

        # Ensure input exists and can receive focus
        try:
            input_widget = self.query_one("#message_input")
            input_widget.can_focus = True
            input_widget.focus()
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id != "message_input":
            return
        user_message = event.value.strip()
        event.input.clear()
        if not user_message:
            return
        if user_message.lower() in ['/clear','/c']:
            messages_log = self.query_one("#messages", RichLog)
            messages_log.clear()
            return
        if user_message.lower() in ['/quit', '/exit', '/q']:
            await self.app.action_quit()
            return
        await self.send_message(user_message)

    def action_quit(self):
        self.app.action_quit()

    # keep your existing networking methods (connect_to_server, listen_for_messages, handle_message, send_message, etc.)
    async def connect_to_server(self):
        messages_log = self.query_one("#messages", RichLog)
        try:
            import ssl
            import certifi
            ssl_context = ssl.create_default_context(cafile=certifi.where())

            self.app.websocket = await websockets.connect(
                self.app.server_url,
                ssl=ssl_context,
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
                max_size=2**20,
                max_queue=32
            )

            auth_message = {
                "type": "join",
                "username": self.username,
                "chatname": self.chat_name,
                "password": self.password
            }
            await self.app.websocket.send(json.dumps(auth_message))

            try:
                while True:
                    response = await asyncio.wait_for(self.app.websocket.recv(), timeout=10.0)
                    data = json.loads(response)
                    if data.get("type") == "join" and data.get("username") == self.username:
                        self.app.connected = True
                        self.query_one("#header").update(f"TERMCHAT - Connected to server:'{self.chat_name}'")
                        messages_log.write(f"[bold #87CEEB]Successfully joined chat '{self.chat_name}'[/bold #87CEEB]")
                        try:
                            self.query_one("#message_input").focus()
                        except Exception:
                            pass
                        break
                    elif data.get("type") == "message":
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

            asyncio.create_task(self.listen_for_messages())

        except Exception as e:
            try:
                messages_log.write(f"[bold red]Failed to connect: {e}[/bold red]")
            except Exception:
                pass
            self.app.notify(f"Connection failed: {e}", severity="error")
            try:
                self.app.pop_screen()
            except Exception:
                pass

    async def listen_for_messages(self):
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
            try:
                self.query_one("#header").update("TERMCHAT - Disconnected")
            except Exception:
                pass
            self.app.notify("Connection lost", severity="warning")
        except Exception as e:
            messages_log.write(f"[bold red]Error receiving messages: {e}[/bold red]")
            self.app.connected = False

    async def handle_message(self, data):
        messages_log = self.query_one("#messages", RichLog)
        message_type = data.get("type", "")
        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            if username == "Server":
                messages_log.write(f"[bold #87CEEB]Server:[/bold #87CEEB] {escape(message)}")
            else:
                user_color = self.app.get_user_color(username)
                messages_log.write(f"[{user_color}]\\[{escape(username)}]:[/{user_color}] {escape(message)}")

    async def send_message(self, user_message: str):
        if self.app.websocket and self.app.connected:
            try:
                message_data = {"type": "message", "content": user_message}
                await self.app.websocket.send(json.dumps(message_data))
            except Exception as e:
                messages_log = self.query_one("#messages", RichLog)
                messages_log.write(f"[bold red]Error sending message: {e}[/bold red]")
                self.app.connected = False
                try:
                    self.query_one("#header").update("TERMCHAT - Disconnected")
                except Exception:
                    pass
        else:
            messages_log = self.query_one("#messages", RichLog)
            messages_log.write("[bold yellow]Not connected to server. Cannot send message.[/bold yellow]")

    async def change_theme_color(self, new_color: str):
        # Change the theme color of the interface
        # Update the header widget style
        header = self.query_one("#header")
        header.styles.color = new_color
        
        # Update message container border
        messages_container = self.query_one("#messages_container")
        messages_container.styles.border = ("solid", new_color)
        
        # Update input container border  
        input_container = self.query_one("#input_container")
        input_container.styles.border = ("solid", new_color)
        
        # Store the new color in the app for future use
        self.app.theme_color = new_color

    async def change_background_color(self, bg_color: str):
        # Change the background color of the entire chat interface
        # Apply to root container and message boxes
        self.styles.background = bg_color
        header = self.query_one("#header")
        header.styles.background = bg_color
        messages_container = self.query_one("#messages_container")
        messages_container.styles.background = bg_color
        messages = self.query_one("#messages")
        messages.styles.background = bg_color
        input_container = self.query_one("#input_container")
        input_container.styles.background = bg_color
        # Optionally, store for later reference
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
