# Termchat

Cross-platform Python terminal client for real-time chat. Connect to the termchat-backend and chat with others using simple authentication.

## Features

- Cross-platform compatibility (Linux, Mac, Windows)
- HTTPS WebSocket connection on port 443 (works on restricted networks)
- Real-time messaging with other users
- Simple authentication (username, chat name, password)
- Clean terminal interface with green/black color scheme
- Minimal output - only real server messages shown
- Progress animation during connection

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

The application will show:
1. ASCII art splash screen
2. Login form with clearly visible fields for:
   - **Username**: Your display name in the chat
   - **Chat name**: The chat room to join  
   - **Password**: Password for the chat room
3. Connection progress animation
4. Chat interface once connected

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
