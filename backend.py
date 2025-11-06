from datetime import datetime
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3

app = FastAPI()

# Models
class User(BaseModel):
    displayName: str
    userId: str

class Message(BaseModel):
    sender: User
    receiver: User
    content: str
    timestamp: datetime

# Util functions
def parse_time(time_str: str):
    """Convert SQLite timestamp str to datetime object"""
    if isinstance(time_str, str):
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
    return time_str

# TODO: WS /ws/typing  
# TODO: GET /api/presence

# Post a generic HTTP message
# This is not async now since we're using standard HTTP so it can run in thread pool as opposed to singlethreaded event loop.
# When we switch to websockets I'll use async since we'll need to await on the Websocket session
@app.post("/api/message")
def message(content: str, senderId: str, receiverId: str):
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()

        # fetch displayName (validate users exist)
        cursor.execute('SELECT displayName FROM users WHERE userId = ?', (senderId,))
        sender_name = cursor.fetchone()[0]
        if not sender_name:
            raise HTTPException(status_code=404, detail=f"User {senderId} not found")

        cursor.execute('SELECT displayName FROM users WHERE userId = ?', (receiverId,))
        receiver_name = cursor.fetchone()[0]
        if not receiver_name:
            raise HTTPException(status_code=404, detail=f"User {receiverId} not found")

        sender = User(userId=senderId, displayName=sender_name)
        receiver = User(userId=receiverId, displayName=receiver_name)

        msg = Message(
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

            msg = Message(
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
