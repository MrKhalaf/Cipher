import sqlite3

conn = sqlite3.connect('storage/cipher.db')
c = conn.cursor()

# Create the Users table
c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        userId TEXT PRIMARY KEY,
        displayName TEXT
    )
''')

# messages
c.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        messageId INTEGER PRIMARY KEY AUTOINCREMENT,
        senderId TEXT,
        receiverId TEXT,
        content TEXT,
        timestamp DATETIME,
        FOREIGN KEY (senderId) REFERENCES users(userId),
        FOREIGN KEY (receiverId) REFERENCES users(userId)
    )
''')


