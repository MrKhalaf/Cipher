from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# TODO: POST /api/message
# TODO: WS /ws/typing  
# TODO: GET /api/presence
# TODO: GET /api/messages

@app.get("/")
async def root():
    with open("static/index.html") as f:
        return HTMLResponse(f.read())

app.mount("/static", StaticFiles(directory="static"), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
