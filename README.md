![Dynamic JSON Badge](https://img.shields.io/endpoint?url=https://termchat-f9cgabe4ajd9djb9.australiaeast-01.azurewebsites.net/badge.json)

# Termchat

Cross-platform Python terminal chat client. Tons of fun features, easy to use, and works over https for availability on all networks! (Even school!)

## Features

- Cross-platform compatibility (Linux, Mac, Windows)
- HTTPS WebSocket connection on port 443 (works on restricted networks)
- Real-time messaging with other users
- Simple authentication (username, chat name, password)
- Clean terminal interface with formatted messages
- Fun /commands - including some old hangouts commands!

## Installation

Binaries have been released! Check the releases tab for the downloads!

## Usage

Run the binaries for your chosen OS!

Or run the unbuilt chat client directly using python:
```bash
python3 termchat.py
```

The script will prompt you for:
- **Username**: Your display name in the chat
- **Chat name**: The chat room to join
- **Password**: Password for the chat room

Each combination of chat name and password creates/joins a new room. You can have multiple chats of the same name, but in order to join the same one as someone else the password must be the same!

## Chat Interface

Once connected, you'll see messages in the format:
```
A wild Username2 has appeared.
[Username1]: Hello
[Username2]: Hey there
```

## Commands

- `/quit`, `/exit`, `/q`: Exit the chat
- `/clear`: Clear the message box/chat area
- `Ctrl+Q`: Exit termchat

## Requirements

None! (Unless you are running the python script;)

If you are running the script directly you will need;
- Python 3.7+
- websockets library
- textual

## Backend

Connects to a server hosted on azure. All information is passed through directly and is not stored.
