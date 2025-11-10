from datetime import datetime
from typing import Literal
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError
import sqlite3

app = FastAPI()

# Models
class User(BaseModel):
    displayName: str
    userId: str

# MessageRecord is used to pull full context for messages received when the user wasn't logged on
class MessageRecord(BaseModel):
    sender: User
    receiver: User
    content: str
    timestamp: datetime

# class for when the message is sent during websocket connection
class Message(BaseModel):
    receiverId: str
    content: str

# Base class for WebSocket messages
class WebSocketMessage(BaseModel):
    type: str  # e.g., "message", "presence"

# Chat message
class ChatMessage(WebSocketMessage):
    type: Literal["message"] = "message"
    receiver: str
    content: str

# Presence update
class PresenceRequest(WebSocketMessage):
    type: Literal["presence"] = "presence"

# Util functions


def parse_time(time_str: str):
    """Convert SQLite timestamp str to datetime object"""
    if isinstance(time_str, str):
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
    return time_str

def get_validated_user(userId:str):
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT displayName FROM users WHERE userId = (?)", (userId,))
        result = cursor.fetchone()

        if result:
            return User(userId=userId, displayName=result[0])
        return None

'''Store message in the central messages table. Returns true if message is stored'''
def store_message(msg: Message, senderId: str):
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()
        cursor.execute('INSERT INTO messages (senderId, receiverId, content, timestamp) VALUES (?, ?, ?, ?)',
                       (senderId, msg.receiverId, msg.content, datetime.now())
                       )
        conn.commit() # push to db

async def send_presence_update(ws: WebSocket):
    """Sends presence update list to the web socket connections"""
    # List of online users
    online_users = []

    # loop through the active connections and get users ids
    for uid in active_connections.keys():
        # validate user exists
        user = get_validated_user(uid)
        # only add if user is valid
        if user:
            online_users.append({
                "userId": user.userId,
                "displayName": user.displayName
            })

    # send presence update to the websocket
    await ws.send_json({
        "type": "presence",
        "users": online_users,
        "count": len(online_users)
    })



# In memory store for session maintenance (for live chat & presence APIs)
active_connections: dict[str, WebSocket] = {}

# TODO: WS /ws/typing  
# TODO: GET /api/presence

@app.websocket("/ws/session")
async def session(ws:WebSocket, userId: str):
    user: User = get_validated_user(userId)
    # return unauthorized if user id doesnt exist
    if not user:
        await ws.close(code=4401, reason="unauthorized")
        return
    
    # await to begin the ws connection until we confirm FastAPI sent it
    await ws.accept()
    active_connections[userId] = ws # add new connection

    send_presence_update(ws) # send initial presence update

    try:
        while True:
            # TODO: consider how we can add HTTP header to receive more than just messages.
            data = await ws.receive_json() 

            message_type = data.get("type", "message") # default to message type

            # Pydantic for validating the JSON we get from client matches Message
            if message_type == "message":
                try:
                    msg = Message(**data)
                    store_message(msg, userId)
                except ValidationError as e:
                    await ws.send_json({
                        "type": "error",
                        "error": "Invalid message format",
                        "details": str(e)
                    })
            elif message_type == "presence":
                await send_presence_update(userId)
            else:
                await ws.send_json({
                    "type": "error",
                    "error": "Unknown message type: {message_type}"
                })
            
    except WebSocketDisconnect:
        active_connections.pop(userId, None) # remove connection from record


# Post a generic HTTP message
# This is not async now since we're using standard HTTP so it can run in thread pool as opposed to singlethreaded event loop.
# When we switch to websockets I'll use async since we'll need to await on the Websocket session
@app.post("/api/message")
def message(content: str, senderId: str, receiverId: str):
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()

        # fetch displayName (validate users exist)
        cursor.execute('SELECT displayName FROM users WHERE userId = ?', (senderId,))
        sender_name = cursor.fetchone()
        if not sender_name:
            raise HTTPException(status_code=404, detail=f"User {senderId} not found")

        cursor.execute('SELECT displayName FROM users WHERE userId = ?', (receiverId,))
        receiver_name = cursor.fetchone()
        if not receiver_name:
            raise HTTPException(status_code=404, detail=f"User {receiverId} not found")

        sender = User(userId=senderId, displayName=sender_name)
        receiver = User(userId=receiverId, displayName=receiver_name)

        msg = MessageRecord(
            sender=sender,
            receiver=receiver,
            content=content,
            timestamp=datetime.now()
        )

        # SQLite upload of the message
        cursor.execute('INSERT INTO messages (senderId, receiverId, content, timestamp) VALUES (?, ?, ?, ?)',
                       (msg.sender.userId, msg.receiver.userId, msg.content, msg.timestamp)
                       )
        conn.commit()

    print(f"Wrote \"{msg.content}\" from {sender.displayName} to {receiver.displayName} into DB")
    return {"message": msg}


# Fetch all the messages sent to and by the user from the DB
@app.get("/api/message")
def fetchMessages(userId: str):
    with sqlite3.connect('storage/cipher.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(
            '''
            SELECT m.content, m.timestamp,
                   s.userId as senderId, s.displayName as senderName,
                   r.userId as receiverId, r.displayName as receiverName
            FROM messages m
            JOIN users s ON m.senderId = s.userId
            JOIN users r ON m.receiverId = r.userId
            WHERE m.senderId = ? OR m.receiverId = ?
            ORDER BY m.timestamp ASC
            ''', (userId, userId))

        chat_history = []
        for row in cursor.fetchall():
            # Parse timestamp string to datetime object

            msg = MessageRecord(
                sender=User(userId=row['senderId'], displayName=row['senderName']),
                receiver=User(userId=row['receiverId'], displayName=row['receiverName']),
                content=row['content'],
                timestamp=parse_time(row["timestamp"])
            )
            chat_history.append(msg)

        print(f"messages to & from {userId}: {len(chat_history)} messages")

    return {"chat_history": chat_history}

# Create a new user
@app.post("/api/users")
def createUser(userId: str, displayName: str):
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()

        cursor.execute('INSERT OR REPLACE INTO users (userId, displayName) VALUES (?, ?)',
                  (userId, displayName))
        conn.commit()

    return {"userId": userId, "displayName": displayName}

# Get all users (optionally filtered by search string)
@app.get("/api/users")
def fetch_all_users(search: str = None):
    with sqlite3.connect('storage/cipher.db') as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if search:
            # Search for users whose displayName contains the search string
            cursor.execute('SELECT * FROM users WHERE displayName LIKE ?', (f'%{search}%',))
        else:
            cursor.execute('SELECT * FROM users')

        users = [User(userId=row['userId'], displayName=row['displayName']) for row in cursor.fetchall()]

    return {"users": users, "is_search": search is not None}

# Get all online users
@app.get("/api/presence")
def fetch_online_users(userId: str = None):
    """Get all online users, optionally excluding the requesting userId"""
    # If userId is provided, return only that user's presence status
    if userId:
        online = userId in active_connections # check if user is online
        user = get_validated_user(userId) # get user details

        # return presence status
        return {
            "userId": userId,
            "displayName": user.displayName if user else None,
            "isOnline": online
        }
    # Otherwise, return the list of all online users
    else:
        online_users = [] # list of online users
        
        # loop through the active connections and get users ids
        for uid in active_connections.keys():
            user = get_validated_user(uid) # validate user exists
            
            # only add if user is valid
            if user:
                online_users.append({
                    "userId": uid,
                    "displayName": user.displayName
                })
            
            # return presence status
            return {
                "onlineUser": online_users,
                "count": len(online_users)
            }

@app.get("/")
async def root():
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
