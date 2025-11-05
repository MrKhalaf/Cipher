from datetime import datetime
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel
import os

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
    sender = User(userId=senderId, displayName="Mohammad S. Khalaf")
    receiver = User(userId=receiverId, displayName="Khader A. Murtaja")

    msg = Message(
        sender=sender,
        receiver=receiver,
        content=content,
        timestamp=datetime.now()
    )

    # for now, we just persist messages in a text file
    os.makedirs("storage", exist_ok=True)
    with open("storage/chats.txt", "a") as f:
        f.write(f"[{msg.timestamp}] {msg.sender.displayName} -> {msg.receiver.displayName}: {msg.content}\n")

    print(f"Wrote \"{msg.content}\" from user {msg.sender.displayName} to user {msg.receiver.displayName} into chats.json")
    return {"status": "sent", "message": msg}

@app.get("/")
async def root():
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
