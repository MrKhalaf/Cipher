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

# Presence update
class PresenceRequest(BaseModel):
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

def get_user_from_db(userId: str):
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()
        cursor.execute('SELECT displayName FROM user WHERE userId = (?)', (userId,))
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

'''Send presence/online users update to the websocket connections'''
async def get_online_users(ws: WebSocket):
    # List of online users
    online_users = []

    # loop through the active connections and get users ids
    for uid in active_connections.keys():
        # get user from the db
        with sqlite3.connect('storage/cipher.db') as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT displayName FROM users WHERE userId = ?', (uid,))
            result = cursor.fetchone()

            if result:
                online_users.append(User(userId=uid, displayName=result[0]))

    # send the online users list to the websocket
    await ws.send_json({"users": online_users})



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
    
    await ws.accept()
    active_connections[userId] = ws # record new connection

    await get_online_users(ws) # send initial presence update

    try:
        while True:
            data = await ws.receive_json() 

            message_type = data.get("type", "message") # default to message type

            # Pydantic for validating the JSON we get from client matches Message
            # Handle chat message
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
            
            # Handle presence request
            elif message_type == "presence":
                await get_online_users(ws)
            
            # Unknown message type
            else:
                await ws.send_json({
                    "type": "error",
                    "error": f"Unknown message type: {message_type}"
                })
            
            try:
                store_message(msg, userId)
            except Exception as e:
                await ws.send_json({
                    "error": "Encountered an error when storing the message. Message may still be sent", 
                    "details": str(e)
                })

            # if recipient is online, pipe the message straight to them
            if recipient.userId in active_connections:
                try:
                    await active_connections[recipient.userId].send_json(
                        msg.model_dump()
                    )
                except Exception:
                    # Recipient disconnected between check and send
                    # Message already stored in DB, so just continue
                    pass

    except WebSocketDisconnect:
        active_connections.pop(userId, None) # remove connection from record
    except Exception as e:
        # Log unexpected errors
        print(f"Unexpected websocket error for user {userId}: {e}")
        active_connections.pop(userId, None)


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
    # If userId is provided, return only that user's presence status
    if userId:
        online = userId in active_connections # check if user is online
        user = get_user_from_db(userId) # get user details

        # return presence status
        return {
            "userId": userId,
            "displayName": user.displayName if user else None,
            "isOnline": online
        }
    # Otherwise, return the list of all online users
    else:
        # return all the online users from active connections
        return {"onlineUser": active_connections.keys()}

@app.get("/")
async def root():
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
