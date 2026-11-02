#!/usr/bin/env python3

# Termchat - Cross-platform Python terminal client for real-time chat
# Connects to termchat-backend via HTTPS WebSocket on port 443

import asyncio
import json
import os
import platform
import shlex
import ssl
import subprocess
import sys
import time
from typing import Optional

import aiohttp
import certifi
import websockets
from rich.markup import escape
from textual import events
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container
from textual.screen import Screen
from textual.widgets import Input, Label, RichLog, Static

IOS_MODE = "-ios" in sys.argv


def is_in_terminal():
    return sys.stdin.isatty()


def launch_new_terminal():
    script_path = os.path.abspath(__file__)
    ios_argument = " -ios" if IOS_MODE else ""

    if platform.system() == "Windows":
        python = shlex.quote(sys.executable)
        cmd = f'start cmd /k {python} "{script_path}"{ios_argument}'
        os.system(cmd)
        sys.exit(0)

    if platform.system() == "Darwin":
        python = shlex.quote(sys.executable)
        applescript = f'''
        tell application "Terminal"
            activate
            if (count of windows) = 0 then
                do script "{python} {script_path}{ios_argument}"
                delay 0.12
                try
                    set bounds of front window to {{100, 100, 1012, 620}}
                end try
            else
                do script "{python} {script_path}{ios_argument}" in front window
            end if
        end tell
        '''
        os.system(f'osascript -e {shlex.quote(applescript)}')
        sys.exit(0)

    if platform.system() == "Linux":
        python = shlex.quote(sys.executable)
        terminals = [
            ["gnome-terminal", "--", python, script_path, *(["-ios"] if IOS_MODE else [])],
            ["konsole", "-e", python, script_path, *(["-ios"] if IOS_MODE else [])],
            ["xterm", "-e", python, script_path, *(["-ios"] if IOS_MODE else [])],
        ]
        for command in terminals:
            try:
                subprocess.Popen(command)
                sys.exit(0)
            except FileNotFoundError:
                continue
        print("No supported terminal emulator found. Please run this script from a terminal.")
        sys.exit(1)

    print("Unsupported OS.")
    sys.exit(1)


async def get_general_count(server_url: str) -> int:
    http_url = server_url.replace("wss://", "https://", 1).replace("ws://", "http://", 1)
    endpoint = f"{http_url.rstrip('/')}/general-count"
    ssl_context = ssl.create_default_context(cafile=certifi.where())
    try:
        connector = aiohttp.TCPConnector(ssl=ssl_context)
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(connector=connector, timeout=timeout) as session:
            async with session.get(endpoint) as response:
                if response.status == 200:
                    return (await response.json()).get("userCount", 0)
    except Exception:
        pass
    return 0


USER_COLORS = [
    "red", "green", "yellow", "magenta", "cyan", "bright_red",
    "bright_yellow", "bright_magenta", "bright_cyan"
]

TERMCHAT_ASCII = """
████████ ███████ ██████  ███    ███  ██████ ██   ██  █████  ████████
   ██    ██      ██   ██ ████  ████ ██      ██   ██ ██   ██    ██
   ██    █████   ██████  ██ ████ ██ ██      ███████ ███████    ██
   ██    ██      ██   ██ ██  ██  ██ ██      ██   ██ ██   ██    ██
   ██    ███████ ██   ██ ██      ██  ██████ ██   ██ ██   ██    ██
"""


class SplashScreen(Screen):
    CSS = """
    SplashScreen { align: center middle; background: black; color: #87CEEB; }
    #splash { width: auto; height: auto; content-align: center middle; text-style: bold; color: #87CEEB; }
    """

    def compose(self) -> ComposeResult:
        yield Static(TERMCHAT_ASCII, id="splash")

    def on_mount(self):
        asyncio.create_task(self._animate_and_advance())

    async def _animate_and_advance(self):
        splash = self.query_one("#splash", Static)
        try:
            splash.styles.opacity = 0.0
            splash.styles.offset = (0, 25)
            splash.styles.color = "#000000"
            for i in range(73):
                t = i / 72
                eased = 1.0 if t >= 1 else 1 - pow(2, -20 * t)
                splash.styles.offset = (0, int(25 * (1 - eased)))
                splash.styles.opacity = float(eased)
                splash.styles.color = f"#{int(135*eased):02x}{int(206*eased):02x}{int(235*eased):02x}"
                splash.refresh()
                await asyncio.sleep(1 / 60)
        except Exception:
            await asyncio.sleep(1.2)
        await asyncio.sleep(0.25)
        self.app.push_screen("connection")


class ConnectionScreen(Screen):
    CSS = """
    ConnectionScreen { align: center middle; background: black; }
    #dialog { width: 80; height: 25; border: solid #87CEEB; background: black; color: white; }
    #title { dock: top; width: 100%; content-align: center middle; text-style: bold; color: #87CEEB; background: black; padding: 1 0; }
    #indicator_row { layout: horizontal; width: 100%; align: center middle; margin-bottom: 1; }
    #indicator_light { width: 2; content-align: center middle; }
    #indicator_text { margin-left: 1; color: white; }
    #hint_row { width: 100%; content-align: center middle; margin-top: 2; }
    #form { layout: vertical; height: auto; margin: 2; padding: 1; }
    .form-row { height: 3; layout: horizontal; margin-bottom: 1; }
    .label { width: 15; content-align: right middle; margin-right: 2; color: #cccccc; text-style: bold; }
    .input { width: 35; height: 3; color: white; border: solid #333333; }
    .input:focus { border: solid #87CEEB; }
    #status_label { width: 40; content-align: center middle; color: yellow; text-style: bold; }
    #general_count_label { width: 100%; content-align: center middle; }
    """

    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"), Binding("escape", "quit", "Quit"),
        Binding("tab", "focus_next", "Next Field"), Binding("shift+tab", "focus_previous", "Previous Field"),
        Binding("enter", "connect", "Connect"),
    ]

    def __init__(self):
        super().__init__()
        self.connecting = False
        self.server_available = False

    def compose(self) -> ComposeResult:
        with Container(id="dialog"):
            yield Label("TERMCHAT Connection", id="title")
            with Container(id="indicator_row"):
                yield Static("●", id="indicator_light")
                yield Label("Checking server...", id="indicator_text")
            yield Container(Label("Keep chat name and password blank to join the [#90ee90]general chat[/#90ee90]", markup=True), id="hint_row")
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
        if IOS_MODE:
            self.query_one("#dialog").styles.width = 46
            self.query_one("#dialog").styles.height = 30
            self.query_one("#form").styles.margin = (1, 1)
            self.query_one("#form").styles.padding = (0, 1)
            for widget in self.query(".input"):
                widget.styles.width = 25
            for widget in self.query(".label"):
                widget.styles.width = 12
                widget.styles.margin_right = 1
        self.query_one("#username_input").focus()
        self.server_check_task = asyncio.create_task(
            self.server_status_loop()
        )

    async def server_status_loop(self):
        while self.is_mounted:
            await asyncio.gather(
                self.check_server_status(),
                self.update_general_count()
            )
            await asyncio.sleep(5)

    async def update_general_count(self):
        count = await get_general_count(self.app.server_url)
        if self.is_mounted:
            self.query_one("#general_count_label").update(
                f"[#90ee90]{count}[/#90ee90] user/s in general chat"
            )

    async def check_server_status(self):
        try:
            websocket = await asyncio.wait_for(websockets.connect(
                self.app.server_url,
                ssl=ssl.create_default_context(cafile=certifi.where()),
                ping_interval=None,
                close_timeout=2,
            ), timeout=5)
            await websocket.close()
            self.server_available = True
        except Exception:
            self.server_available = False
        if not self.is_mounted:
            return

        light = self.query_one("#indicator_light")
        text = self.query_one("#indicator_text")
        color = "#00ff00" if self.server_available else "#ff0000"
        light.styles.color = color
        text.styles.color = color
        text.update(
            "Server available"
            if self.server_available
            else "Server unavailable"
        )

    def on_unmount(self):
        task = getattr(self, "server_check_task", None)
        if task and not task.done():
            task.cancel()

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "username_input":
            self.query_one("#chatname_input").focus()
        elif event.input.id == "chatname_input":
            self.query_one("#password_input").focus()
        else:
            await self.action_connect()

    async def action_connect(self):
        if self.connecting:
            return
        username = self.query_one("#username_input").value.strip() or "guest"
        chat_name = self.query_one("#chatname_input").value.strip() or "general"
        password = self.query_one("#password_input").value.strip() or "default"
        if username.lower() == "server":
            self.app.notify("Username 'server' is forbidden!", severity="error")
            return
        self.connecting = True
        self.query_one("#status_label").update("[yellow]Connecting...[/yellow]")
        self.app.start_chat(username, chat_name, password)

    def on_screen_resume(self):
        self.connecting = False
        try:
            self.query_one("#status_label").update("")
            self.query_one("#username_input").focus()
        except Exception:
            pass

    def action_quit(self):
        self.app.exit()


class ChatScreen(Screen):
    CSS = """
    ChatScreen { layout: vertical; background: black; color: white; }
    #header { dock: top; height: 3; background: black; color: #87CEEB; content-align: center middle; text-style: bold; padding: 1 0; }
    #messages_container { height: 1fr; border: solid #87CEEB; margin: 0; }
    #messages { height: 1fr; scrollbar-gutter: stable; border: none; background: black; color: white; padding: 1; }
    #input_container { dock: bottom; height: 5; border: solid #87CEEB; margin: 0 0 1 0; padding: 1; content-align: center middle; }
    #message_input { width: 1fr; height: 3; border: none; background: black; color: white; content-align: center middle; }
    #message_input:focus { border: none; }
    """

    BINDINGS = [Binding("ctrl+c", "quit", "Quit"), Binding("ctrl+q", "quit", "Quit")]

    def __init__(self, username: str, chat_name: str, password: str):
        super().__init__()
        self.username = username
        self.chat_name = chat_name
        self.password = password
        self.ios_colour_next_allowed = 0.0
        self.ios_colour_warning_shown = False
        self.notification_muted = False
        self.last_chat_activity = time.monotonic()
        self.reconnect_in_progress = False
        self.returning_to_login = False
        self.listener_task = None

    def compose(self) -> ComposeResult:
        yield Label(f"TERMCHAT - Connecting to '{self.chat_name}'...", id="header")
        with Container(id="messages_container"):
            yield RichLog(id="messages", highlight=True, markup=True)
        with Container(id="input_container"):
            yield Input(placeholder="Type your message here...", id="message_input")

    async def on_mount(self):
        success = await self.connect_to_server()
        if success:
            self.query_one("#message_input").focus()

    async def on_input_submitted(self, event: Input.Submitted):
        if event.input.id != "message_input":
            return
        user_message = event.value.strip()
        event.input.clear()
        if not user_message:
            return
        lower = user_message.lower()
        if lower in ("/clear", "/c"):
            self.query_one("#messages", RichLog).clear()
        elif lower in ("/quit", "/exit", "/q"):
            await self.return_to_login()
        elif lower == "/mute":
            self.notification_muted = True
            self.query_one("#messages", RichLog).write("[bold orange1]Message sounds muted[/bold orange1]")
        elif lower == "/unmute":
            self.notification_muted = False
            self.query_one("#messages", RichLog).write("[bold #00ff00]Message sounds enabled[/bold #00ff00]")
        else:
            await self.send_message(user_message)

    def action_quit(self):
        asyncio.create_task(self.return_to_login())

    async def return_to_login(self):
        if self.returning_to_login:
            return
        self.returning_to_login = True
        self.app.connected = False
        websocket = self.app.websocket
        self.app.websocket = None
        if websocket:
            try:
                await websocket.close()
            except Exception:
                pass
        if self.is_current:
            self.app.pop_screen()

    async def on_app_focus(self, event: events.AppFocus):
        if not self.app.connected and not self.returning_to_login and not self.reconnect_in_progress:
            await self.reconnect_to_server()

    async def reconnect_to_server(self):
        self.reconnect_in_progress = True
        self.query_one("#messages", RichLog).write("[bold orange1]Reconnecting to server...[/bold orange1]")
        try:
            await self.connect_to_server(reconnecting=True)
        finally:
            self.reconnect_in_progress = False

    async def connect_to_server(self, reconnecting=False):
        messages_log = self.query_one("#messages", RichLog)
        try:
            websocket = await websockets.connect(
                self.app.server_url,
                ssl=ssl.create_default_context(cafile=certifi.where()),
                ping_interval=30,
                ping_timeout=10,
                close_timeout=10,
                max_size=2**20,
                max_queue=32,
            )
            self.app.websocket = websocket
            await websocket.send(json.dumps({
                "type": "join", "username": self.username,
                "chatname": self.chat_name, "password": self.password
            }))
            while True:
                response = await asyncio.wait_for(websocket.recv(), timeout=10)
                data = json.loads(response)
                if data.get("type") == "join" and data.get("username") == self.username:
                    self.app.connected = True
                    self.query_one("#header").update(f"TERMCHAT - Connected to server: '{self.chat_name}'")
                    if reconnecting:
                        messages_log.write("[bold #00ff00]Reconnected to server[/bold #00ff00]")
                    else:
                        messages_log.write(f"[bold #87CEEB]Successfully joined chat '{escape(self.chat_name)}'[/bold #87CEEB]")
                    break
                await self.handle_message(data)
            self.listener_task = asyncio.create_task(self.listen_for_messages(websocket))
            return True
        except Exception as error:
            self.app.connected = False
            messages_log.write(f"[bold red]Failed to connect to server: {escape(str(error))}[/bold red]")
            if not reconnecting:
                self.app.notify("Could not connect to server", severity="error")
                self.app.pop_screen()
            return False

    async def listen_for_messages(self, websocket):
        messages_log = self.query_one("#messages", RichLog)
        try:
            async for message in websocket:
                if websocket is not self.app.websocket:
                    return
                try:
                    await self.handle_message(json.loads(message))
                except json.JSONDecodeError:
                    messages_log.write("[bold red]Received invalid JSON[/bold red]")
                except Exception as error:
                    messages_log.write(f"[bold red]Error processing message: {escape(str(error))}[/bold red]")
        except websockets.exceptions.ConnectionClosed as error:
            if websocket is self.app.websocket and not self.returning_to_login:
                self.app.connected = False
                messages_log.write(f"[bold orange1]Connection to server lost: {escape(str(error))}[/bold orange1]")
                self.query_one("#header").update("TERMCHAT - Disconnected")
        except Exception as error:
            if websocket is self.app.websocket and not self.returning_to_login:
                self.app.connected = False
                messages_log.write(f"[bold orange1]Connection closed: {escape(str(error))}[/bold orange1]")
                self.query_one("#header").update("TERMCHAT - Disconnected")

    def play_message_sound(self):
        try:
            self.app.bell()
        except Exception:
            print("\a", end="", flush=True)

    async def handle_message(self, data):
        messages_log = self.query_one("#messages", RichLog)
        message_type = data.get("type", "")

        if message_type == "message":
            username = data.get("username", "Unknown")
            message = data.get("content", "")
            now = time.monotonic()
            if username not in ("Server", self.username) and now - self.last_chat_activity >= 30 and not self.notification_muted:
                self.play_message_sound()
            self.last_chat_activity = now
            if username == "Server":
                messages_log.write(f"[bold #87CEEB]Server:[/bold #87CEEB] {escape(message)}")
            else:
                color = self.app.get_user_color(username)
                messages_log.write(f"[{color}]\\[{escape(username)}]:[/{color}] {escape(message)}")

        elif message_type == "join":
            username = data.get("username", "Unknown")
            if username and username != self.username:
                messages_log.write(f"[bold #87CEEB]A wild {escape(username)} has appeared.[/bold #87CEEB]")

        elif message_type == "leave":
            username = data.get("username", "Unknown")
            if username and username != self.username:
                messages_log.write(f"[bold #87CEEB]{escape(username)} has left the chat.[/bold #87CEEB]")

        elif message_type == "colourshift":
            color = data.get("color", "#87CEEB")
            if IOS_MODE:
                now = asyncio.get_running_loop().time()
                if not self.ios_colour_warning_shown:
                    messages_log.write("[bold orange1]Colour changes limited for iOS performance[/bold orange1]")
                    self.ios_colour_warning_shown = True
                if now < self.ios_colour_next_allowed:
                    return
                self.ios_colour_next_allowed = now + 0.3
                self.apply_theme_color_instantly(color)
            else:
                await self.change_theme_color(color)

        elif message_type == "bgshift":
            messages_log.clear()
            await self.change_background_color(data.get("color", "#000000"))

        elif message_type == "chatclear":
            messages_log.clear()

        elif message_type == "kicked":
            messages_log.clear()
            messages_log.write(f"[bold #FF0000]{escape(data.get('message', 'You have been kicked :)'))}[/bold #FF0000]")
            await asyncio.sleep(5)
            await self.return_to_login()

        elif message_type in ("error", "auth_failed"):
            messages_log.write(f"[bold red]{escape(data.get('message', 'Unknown error'))}[/bold red]")

    async def send_message(self, user_message):
        messages_log = self.query_one("#messages", RichLog)
        if self.app.websocket and self.app.connected:
            try:
                self.last_chat_activity = time.monotonic()
                await self.app.websocket.send(json.dumps({"type": "message", "content": user_message}))
            except Exception as error:
                self.app.connected = False
                messages_log.write(f"[bold orange1]Cannot send message: {escape(str(error))}[/bold orange1]")
                self.query_one("#header").update("TERMCHAT - Disconnected")
        else:
            messages_log.write("[bold orange1]Not connected to server. Refocus Termchat to reconnect.[/bold orange1]")

    @staticmethod
    def _hex_to_rgb(color, fallback=(135, 206, 235)):
        try:
            value = color.lstrip("#")
            if len(value) != 6:
                raise ValueError
            return tuple(int(value[i:i+2], 16) for i in (0, 2, 4))
        except Exception:
            return fallback

    @staticmethod
    def _rgb_to_hex(r, g, b):
        return f"#{max(0,min(255,int(r))):02x}{max(0,min(255,int(g))):02x}{max(0,min(255,int(b))):02x}"

    def apply_theme_color_instantly(self, new_color):
        r, g, b = self._hex_to_rgb(new_color)
        new_color = self._rgb_to_hex(r, g, b)
        dark = self._rgb_to_hex(r * 0.5, g * 0.5, b * 0.5)
        self.query_one("#header").styles.color = new_color
        self.query_one("#messages_container").styles.border = ("solid", new_color)
        self.query_one("#input_container").styles.border = ("solid", new_color)
        self.query_one("#messages").styles.scrollbar_background = new_color
        self.query_one("#messages").styles.scrollbar_color = dark
        self.app.theme_color = new_color
        self.refresh()

    async def change_theme_color(self, new_color):
        start = self._hex_to_rgb(self.app.theme_color)
        end = self._hex_to_rgb(new_color)
        for i in range(31):
            t = i / 30
            color = self._rgb_to_hex(*(start[j] + (end[j] - start[j]) * t for j in range(3)))
            self.apply_theme_color_instantly(color)
            await asyncio.sleep(0.01)
        self.app.theme_color = new_color

    async def change_background_color(self, bg_color):
        start = self._hex_to_rgb(self.app.background_color, (0, 0, 0))
        end = self._hex_to_rgb(bg_color, (0, 0, 0))
        widgets = [self, self.query_one("#header"), self.query_one("#messages_container"), self.query_one("#messages"), self.query_one("#input_container")]
        message_input = self.query_one("#message_input")
        for i in range(61):
            t = i / 60
            rgb = tuple(start[j] + (end[j] - start[j]) * t for j in range(3))
            color = self._rgb_to_hex(*rgb)
            dark = self._rgb_to_hex(*(value * 0.7 for value in rgb))
            for widget in widgets:
                widget.styles.background = color
            message_input.styles.background = dark
            self.refresh()
            await asyncio.sleep(0.01)
        self.app.background_color = bg_color


class TermchatApp(App):
    SCREENS = {"splash": SplashScreen, "connection": ConnectionScreen}

    def __init__(self):
        super().__init__()
        self.websocket: Optional[websockets.WebSocketClientProtocol] = None
        self.user_colors = {}
        self.color_index = 0
        self.connected = False
        self.theme_color = "#87CEEB"
        self.background_color = "#000000"
        self.server_url = "wss://termchat-zwaacit-e2gtaycfe5edfpbx.australiaeast-01.azurewebsites.net"

    def on_mount(self):
        self.push_screen("splash")

    def start_chat(self, username, chat_name, password):
        self.push_screen(ChatScreen(username, chat_name, password))

    def get_user_color(self, username):
        if username.lower() == "server":
            return "bold #87CEEB"
        if username not in self.user_colors:
            self.user_colors[username] = USER_COLORS[self.color_index % len(USER_COLORS)]
            self.color_index += 1
        return self.user_colors[username]

    async def action_quit(self):
        if self.websocket:
            try:
                await self.websocket.close()
            except Exception:
                pass
        self.exit()


async def main():
    await TermchatApp().run_async()


if __name__ == "__main__":
    try:
        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        if not is_in_terminal():
            launch_new_terminal()
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nExiting...")
    except Exception as error:
        print(f"Application error: {error}")
        sys.exit(1)
