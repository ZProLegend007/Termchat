# Backend Command Implementation

This document describes the implementation of the `/colour` and `/n` commands for the Termchat backend.

## Overview

Two new commands have been added to the Termchat backend server:

1. **`/colour` command**: Generates a random hex color and sends a color-shift command to the user's frontend
2. **`/n` command**: Broadcasts ASCII art to all users in the chat room

## Implementation Details

### Server-Side (`termchat_server.py`)

The server handles commands in the `handle_command` function:

```python
async def handle_command(websocket, command):
    """Handle special commands"""
    command_parts = command.split()
    cmd = command_parts[0].lower()
    
    if cmd == "/colour" or cmd == "/color":
        await handle_colour_command(websocket)
    elif cmd == "/n":
        await handle_n_command(websocket)
    # ... other commands
```

#### `/colour` Command Handler

```python
async def handle_colour_command(websocket):
    """Handle /colour command - generate random hex color and send colourshift to user"""
    # Generate random hex color (6-digit format)
    hex_color = ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    
    # Send colourshift command to the user's frontend
    colourshift_message = {
        "type": "colourshift",
        "color": hex_color
    }
    
    await websocket.send(json.dumps(colourshift_message))
    # No server message output to the chat as per requirements
```

**Features:**
- Generates 6-digit hex color (e.g., "CD36DA")
- Sends `colourshift` message type to client
- No chat output (silent command)
- Response format: `{"type": "colourshift", "color": "XXXXXX"}`

#### `/n` Command Handler

```python
async def handle_n_command(websocket):
    """Handle /n command - broadcast ASCII art to everyone in chat"""
    chatname = clients[websocket]["chatname"]
    username = clients[websocket]["username"]
    
    # Send ASCII art as server message to everyone in the room
    ascii_message = {
        "type": "message",
        "username": "Server",
        "content": BIGGO_ASCII
    }
    await broadcast_to_room(chatname, ascii_message)
```

**Features:**
- Hidden command (not listed in `/help`)
- Broadcasts ASCII art to all users in the chat room
- Displays as Server message
- Uses the specified ASCII art pattern

### Client-Side (`termchat.py`)

The client has been enhanced to handle the `colourshift` message type:

```python
elif message_type == "colourshift":
    # Handle color change command from server
    hex_color = data.get("color", "87CEEB")
    await self.handle_colourshift(hex_color)
```

#### Color Shift Handler

```python
async def handle_colourshift(self, hex_color: str):
    """Handle color shift command - change terminal theme colors"""
    # Update header and border colors
    header = self.query_one("#header")
    header.styles.color = f"#{hex_color}"
    
    messages_container = self.query_one("#messages_container")
    input_container = self.query_one("#input_container")
    messages_container.styles.border = f"solid #{hex_color}"
    input_container.styles.border = f"solid #{hex_color}"
    
    # Show confirmation message
    messages_log.write(f"[bold #{hex_color}]✨ Terminal colors shifted to #{hex_color}![/bold #{hex_color}]")
```

## Usage Examples

### Testing the Commands

1. Start the server:
   ```bash
   python3 termchat_server.py
   ```

2. Start the client:
   ```bash
   python3 termchat.py
   ```

3. In the client, try these commands:
   - Type `/colour` - your terminal colors will change
   - Type `/n` - ASCII art will appear for all users

### API Integration

For frontend script integration, the `colourshift` response format is:

```json
{
  "type": "colourshift",
  "color": "CD36DA"
}
```

Where `color` is always a 6-digit hexadecimal color code.

## Technical Notes

- Server runs on `localhost:8765` by default
- Uses WebSocket protocol for real-time communication
- Maintains chat room isolation (commands affect only users in the same room)
- Thread-safe command handling
- Graceful error handling and client disconnection management
- Logging for debugging and integration verification

## Command Behavior

- **`/colour`**: Silent to chat, only affects the requesting user
- **`/n`**: Visible to all users in the chat room as a Server message
- Both commands work in any chat room
- No authentication beyond normal chat room access required