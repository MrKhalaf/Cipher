from datetime import datetime
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
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

    try:
        while True:
            data = await ws.receive_json() 

            try:
                msg: Message = Message(**data)
            except ValidationError as e:
                # keep connection alive, but let client know structure is wrong
                await ws.send_json({"error": "Invalid message format", "details": str(e)})
                continue

            # validate sender is not impersonating someone else
            if msg.senderId != userId:
                await ws.send_json({
                    "error": "Unauthorized",
                    "details": "Cannot send messages as another user"
                })
                continue

            # validate recipient exists
            recipient = get_validated_user(msg.receiverId)
            if not recipient:
                await ws.send_json({
                    "error": "Invalid recipient",
                    "details": "Recipient does not exist"
                })
                continue
            
            try:
                store_message(msg, userId)
            except Exception as e:
                await ws.send_json({
                    "error": "Encountered an error when storing the message. Message may still be sent", 
                    "details": str(e)
                })

            # if recipient is online, pipe the message straight to them
            if recipient.userId in active_connections:
                await active_connections[recipient.userId].send_json(
                    msg.model_dump()
                )

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

@app.get("/")
async def root():
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
