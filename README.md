# Cipher

<img src="assets/textLogoCipher.png" alt="Cipher Logo" width="400">

Messaging app exploring networking protocols and encryption

## Setup

### 1. Install dependencies
```bash
pip install -r requirements.txt
```

### 2. Initialize database
```bash
python scripts/sqlite_setup.py
python scripts/seed_data.py
```

### 3. Run the server
```bash
python backend.py
# Or with auto-open browser:
python backend.py & sleep 2 && open http://localhost:8000
```

## API Documentation

### Endpoints

#### POST `/api/message` - Send a message
Send a message between two users.

**Parameters:**
- `content` (string) - Message content
- `senderId` (string) - Sender's user ID
- `receiverId` (string) - Receiver's user ID

**Example:**
```bash
curl -X POST "http://localhost:8000/api/message?content=Hello%20World&senderId=mohammad&receiverId=khader"
```

**Response:**
```json
{
  "status": 200,
  "message": {
    "sender": {"userId": "mohammad", "displayName": "Mohammad S. Khalaf"},
    "receiver": {"userId": "khader", "displayName": "Khader A. Murtaja"},
    "content": "Hello World",
    "timestamp": "2025-11-05T07:50:19.289720"
  }
}
```

#### GET `/api/message` - Fetch messages
Retrieve all messages sent to or from a specific user.

**Parameters:**
- `userId` (string) - User ID to fetch messages for

**Example:**
```bash
curl "http://localhost:8000/api/message?userId=khader"
```

**Response:**
```json
{
  "status": 200,
  "chat_history": [
    [1, "khader", "mohammad", "Hey Mohammad! Just finished the new UI for Cipher", "2025-11-05 05:50:19.289720"],
    [2, "mohammad", "khader", "That's awesome! Can't wait to see it.", "2025-11-05 05:52:19.289720"]
  ]
}
```

### Planned Endpoints (TODO)
- `WS /ws/typing` - WebSocket for typing indicators
- `GET /api/presence` - User presence/online status

## Database

SQLite database stored at `storage/cipher.db` with two tables:
- `users` - User profiles (userId, displayName)
- `messages` - Message history (messageId, senderId, receiverId, content, timestamp)

## Seeded Test Data

The database comes with 3 test users:
- `mohammad` - Mohammad S. Khalaf
- `khader` - Khader A. Murtaja
- `alice` - Alice Johnson

And a sample conversation about the Cipher app.

## Frontend

Frontend already wired up for dark mode + messenger UI.
