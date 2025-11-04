# Cipher

![Cipher Logo](assets/textLogoCipher.png)

Messaging app exploring networking protocols and encryption

#### Setup
```
pip install -r requirements.txt
python3 backend.py
python backend.py & sleep 2 && open http://localhost:8000
```

### Endpoints will be built with different protocols for experimentation

POST /api/message - send messages
WS /ws/typing - typing indicators
GET /api/presence - presence count
GET /api/messages - message history

Frontend already wired up for dark mode + messenger UI.
