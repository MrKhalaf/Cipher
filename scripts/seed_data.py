import sqlite3
from datetime import datetime, timedelta

conn = sqlite3.connect('storage/cipher.db')
c = conn.cursor()

# Clear existing data (optional - remove if you want to keep existing data)
c.execute('DELETE FROM messages')
c.execute('DELETE FROM users')

# Seed users
users = [
    ('mohammad', 'Mohammad S. Khalaf'),
    ('khader', 'Khader A. Murtaja'),
    ('alice', 'Alice Johnson')
]

for userId, displayName in users:
    c.execute('INSERT OR REPLACE INTO users (userId, displayName) VALUES (?, ?)',
              (userId, displayName))

# Seed messages - conversation about Cipher app
base_time = datetime.now() - timedelta(hours=2)

messages = [
    # Conversation between Mohammad and Khader about Cipher
    ('khader', 'mohammad', 'Hey Mohammad! Just finished the new UI for Cipher', base_time),
    ('mohammad', 'khader', 'That\'s awesome! Can\'t wait to see it. When can we deploy?', base_time + timedelta(minutes=2)),
    ('khader', 'mohammad', 'It\'s ready to go! Want me to show you a demo first?', base_time + timedelta(minutes=5)),
    ('mohammad', 'khader', 'Absolutely! I\'m excited to see what you\'ve built', base_time + timedelta(minutes=7)),

    # One additional message from Alice to Mohammad
    ('alice', 'mohammad', 'Hey Mohammad, heard about the new Cipher release. Congrats!', base_time + timedelta(hours=1))
]

for senderId, receiverId, content, timestamp in messages:
    c.execute('''
        INSERT INTO messages (senderId, receiverId, content, timestamp)
        VALUES (?, ?, ?, ?)
    ''', (senderId, receiverId, content, timestamp))

conn.commit()
conn.close()

print("✓ Seeded the Data")