from datetime import datetime
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
import os
from pydantic import BaseModel
import sqlite3

app = FastAPI()

class User(BaseModel):
    displayName: str
    userId: str

class Message(BaseModel):
    sender: User
    receiver: User
    content: str
    timestamp: datetime


# TODO: WS /ws/typing  
# TODO: GET /api/presence
# TODO: GET /api/messages

# Post a generic HTTP message
# This is not async now since we're using standard HTTP so it can run in thread pool as opposed to singlethreaded event loop.
# When we switch to websockets I'll use async since we'll need to await on the Websocket session
@app.post("/api/message")
def message(content: str, senderId: str, receiverId: str):
    conn = sqlite3.connect('storage/cipher.db')
    cursor = conn.cursor()

    # fetch displayName (just for testing purposes)
    cursor.execute('SELECT displayName FROM users WHERE userId = ?', (senderId,))
    senderName = cursor.fetchone()[0]
    cursor.execute('SELECT displayName FROM users WHERE userId = ?', (receiverId,))
    receiverName = cursor.fetchone()[0]

    sender = User(userId=senderId, displayName=senderName)
    receiver = User(userId=receiverId, displayName=receiverName)

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
    conn.close()


    print(f"Wrote \"{msg.content}\" from {sender.displayName} to {receiver.displayName} into DB")
    return {"status": 200, "message": msg}


# Fetch all the messages sent to and by the user from the DB
@app.get("/api/message")
def fetchMessages(userId: str):
    conn = sqlite3.connect('storage/cipher.db')
    cursor = conn.cursor()
    messages= cursor.execute(
        '''
        SELECT * FROM messages 
        WHERE senderId = (?) OR receiverId = (?) 
        ''', (userId, userId))
    
    chat_history = []
    for msg in messages:
        chat_history.append(msg)

    print(f"messages for {userId}:\n{chat_history}")

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

@app.get("/")
async def root():
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
