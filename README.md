# Termchat

Cross-platform Python terminal client for real-time chat. Connect to the termchat-backend and chat with others using simple authentication.

## Features

- Cross-platform compatibility (Linux, Mac, Windows)
- HTTPS WebSocket connection on port 443 (works on restricted networks)
- Real-time messaging with other users
- Simple authentication (username, chat name, password)
- Clean terminal interface with formatted messages

## Installation

1. Clone this repository
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Usage

Run the chat client:
```bash
python3 termchat.py
```

Or make it executable and run directly:
```bash
chmod +x termchat.py
./termchat.py
```

The script will prompt you for:
- **Username**: Your display name in the chat
- **Chat name**: The chat room to join
- **Password**: Password for the chat room

## Chat Interface

Once connected, you'll see messages in the format:
```
A wild Username2 has appeared.
[Username1]: Hello
[Username2]: Hey there
```

## Commands

- `/quit`, `/exit`, `/q`: Exit the chat
- `Ctrl+C`: Force quit

## Requirements

- Python 3.7+
- websockets library (see requirements.txt)

## Backend

Connects to: https://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net/
