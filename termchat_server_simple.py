#!/usr/bin/env python3
"""
Simple Termchat Server - WebSocket backend for handling chat messages and commands
Implements /colour and /n commands as requested
"""

import asyncio
import websockets
import json
import random
import logging

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ASCII Art for /n command
BIGGO_ASCII = """░▒▓███████▓▒░  ░▒▓█▓▒░  ░▒▓██████▓▒░   ░▒▓██████▓▒░   ░▒▓██████▓▒░  
░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░        ░▒▓█▓▒░        ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒▒▓███▓▒░ ░▒▓█▓▒▒▓███▓▒░ ░▒▓████████▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░░▒▓█▓▒░ 
░▒▓█▓▒░░▒▓█▓▒░ ░▒▓█▓▒░  ░▒▓██████▓▒░   ░▒▓██████▓▒░  ░▒▓█▓▒░░▒▓█▓▒░ """

# Global store for clients
clients = {}  # websocket -> {"username": str, "chatname": str}
rooms = {}    # chatname -> set of websockets

async def register_client(websocket, username, chatname):
    """Register a new client"""
    clients[websocket] = {"username": username, "chatname": chatname}
    
    if chatname not in rooms:
        rooms[chatname] = set()
    rooms[chatname].add(websocket)
    
    # Send join confirmation
    await websocket.send(json.dumps({
        "type": "join",
        "username": username
    }))
    
    # Notify others in the room
    message = {
        "type": "join",
        "username": username
    }
    await broadcast_to_others(websocket, message)
    
    logger.info(f"User {username} joined room {chatname}")

async def unregister_client(websocket):
    """Unregister a client"""
    if websocket in clients:
        client_info = clients[websocket]
        username = client_info["username"]
        chatname = client_info["chatname"]
        
        # Remove from data structures
        del clients[websocket]
        if chatname in rooms:
            rooms[chatname].discard(websocket)
            if not rooms[chatname]:  # Remove empty room
                del rooms[chatname]
        
        # Notify others in the room
        message = {
            "type": "leave",
            "username": username
        }
        await broadcast_to_others(websocket, message)
        
        logger.info(f"User {username} left room {chatname}")

async def broadcast_to_room(chatname, message):
    """Broadcast message to all clients in a room"""
    if chatname in rooms:
        disconnected = []
        for websocket in rooms[chatname]:
            try:
                await websocket.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                disconnected.append(websocket)
        
        # Clean up disconnected clients
        for websocket in disconnected:
            await unregister_client(websocket)

async def broadcast_to_others(sender_websocket, message):
    """Broadcast message to others in the same room as sender"""
    if sender_websocket in clients:
        chatname = clients[sender_websocket]["chatname"]
        if chatname in rooms:
            disconnected = []
            for websocket in rooms[chatname]:
                if websocket != sender_websocket:
                    try:
                        await websocket.send(json.dumps(message))
                    except websockets.exceptions.ConnectionClosed:
                        disconnected.append(websocket)
            
            # Clean up disconnected clients
            for websocket in disconnected:
                await unregister_client(websocket)

async def handle_colour_command(websocket):
    """Handle /colour command - generate random hex color and send colourshift to user"""
    # Generate random hex color (6-digit format)
    hex_color = ''.join([random.choice('0123456789ABCDEF') for _ in range(6)])
    
    # Send colourshift command to the user's frontend
    colourshift_message = {
        "type": "colourshift",
        "color": hex_color
    }
    
    try:
        await websocket.send(json.dumps(colourshift_message))
        username = clients[websocket]["username"]
        logger.info(f"Sent colourshift #{hex_color} to user {username}")
    except websockets.exceptions.ConnectionClosed:
        pass

async def handle_n_command(websocket):
    """Handle /n command - broadcast ASCII art to everyone in chat"""
    if websocket in clients:
        chatname = clients[websocket]["chatname"]
        username = clients[websocket]["username"]
        
        # Send ASCII art as server message to everyone in the room
        ascii_message = {
            "type": "message",
            "username": "Server",
            "content": BIGGO_ASCII
        }
        await broadcast_to_room(chatname, ascii_message)
        
        logger.info(f"User {username} triggered /n command - ASCII art broadcasted")

async def handle_client(websocket):
    """Handle a new client connection"""
    logger.info(f"New client connected from {websocket.remote_address}")
    
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                await process_message(websocket, data)
            except json.JSONDecodeError:
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Invalid JSON format"
                }))
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await websocket.send(json.dumps({
                    "type": "error",
                    "message": "Server error processing message"
                }))
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client disconnected")
    finally:
        await unregister_client(websocket)

async def process_message(websocket, data):
    """Process different types of messages from clients"""
    message_type = data.get("type", "")
    
    if message_type == "join":
        await handle_join(websocket, data)
    elif message_type == "message":
        await handle_message(websocket, data)
    else:
        await websocket.send(json.dumps({
            "type": "error",
            "message": f"Unknown message type: {message_type}"
        }))

async def handle_join(websocket, data):
    """Handle user joining a chat room"""
    username = data.get("username", "").strip()
    chatname = data.get("chatname", "").strip()
    password = data.get("password", "").strip()
    
    # Basic validation
    if not username or not chatname:
        await websocket.send(json.dumps({
            "type": "auth_failed",
            "message": "Username and chat name are required"
        }))
        return
    
    if username.lower() == "server":
        await websocket.send(json.dumps({
            "type": "auth_failed",
            "message": "Username 'server' is not allowed"
        }))
        return
    
    # Check if username is already taken in this room
    if chatname in rooms:
        for client_ws in rooms[chatname]:
            if client_ws in clients and clients[client_ws]["username"] == username:
                await websocket.send(json.dumps({
                    "type": "auth_failed",
                    "message": f"Username '{username}' is already taken in this room"
                }))
                return
    
    # Register the client
    await register_client(websocket, username, chatname)

async def handle_message(websocket, data):
    """Handle chat messages and commands"""
    if websocket not in clients:
        await websocket.send(json.dumps({
            "type": "error",
            "message": "Not authenticated. Please join a room first."
        }))
        return
    
    client_info = clients[websocket]
    username = client_info["username"]
    chatname = client_info["chatname"]
    content = data.get("content", "").strip()
    
    if not content:
        return
    
    # Check for commands
    if content.startswith('/'):
        await handle_command(websocket, content)
    else:
        # Regular message - broadcast to all users in room
        message = {
            "type": "message",
            "username": username,
            "content": content
        }
        await broadcast_to_room(chatname, message)

async def handle_command(websocket, command):
    """Handle special commands"""
    command_parts = command.split()
    cmd = command_parts[0].lower()
    
    if cmd == "/colour" or cmd == "/color":
        await handle_colour_command(websocket)
    elif cmd == "/n":
        await handle_n_command(websocket)
    elif cmd == "/help":
        help_text = """Available commands:
/help - Show this help message
/colour - Change your terminal colors
/quit - Exit the chat"""
        
        help_message = {
            "type": "message",
            "username": "Server",
            "content": help_text
        }
        await websocket.send(json.dumps(help_message))
    else:
        # Unknown command - treat as regular message
        if websocket in clients:
            client_info = clients[websocket]
            username = client_info["username"]
            chatname = client_info["chatname"]
            
            message = {
                "type": "message",
                "username": username,
                "content": command
            }
            await broadcast_to_room(chatname, message)

async def main():
    """Start the Termchat server"""
    host = "localhost"
    port = 8765
    
    logger.info(f"Starting Termchat server on {host}:{port}")
    
    start_server = websockets.serve(handle_client, host, port)
    await start_server
    
    logger.info("Termchat server started successfully!")
    logger.info("Waiting for client connections...")
    
    # Run forever
    await asyncio.Future()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nServer shutting down...")
    except Exception as e:
        print(f"Server error: {e}")