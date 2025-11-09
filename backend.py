'''
IMPORTS - These are all the external libraries and tools we need for this backend.
Think of imports like importing frameworks in iOS (like Foundation or UIKit) or
in Android (like androidx.appcompat).

- datetime: Provides datetime objects for working with dates and times
- FastAPI: The web framework that makes building REST APIs easy
- WebSocket: For real-time bidirectional communication (we'll use this later)
- HTTPException: For throwing HTTP errors (like 404 Not Found, 500 Internal Server Error)
- HTMLResponse/StreamingResponse: Special response types for returning HTML or streams
- StaticFiles: For serving static files (CSS, JS, images)
- BaseModel: From pydantic, helps us define data models with automatic validation
- sqlite3: Python's built-in SQLite database library
'''
from datetime import datetime
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
import sqlite3

'''
Create our FastAPI application instance. This 'app' object is the core of our backend.
All our endpoints (@app.get, @app.post) are attached to this app object.

When we run the server at the bottom, we pass this app to uvicorn to run it.
'''
app = FastAPI()

# Models

'''
The User() and Message classes are objects I just created to make it easier to manage 
and define exactly what feature a user and a message must have. By doing this, we have 
an agreed upon standard for what we need to have before sending a message and creating a
user so that we're not creating different standards and it makes it simpler to develop.

Notice how I first define User before Message. The reason for this is because User is 
actually a variable inside of Message! Message records the sender & receiver which must
both be User options.

Effectively this means that I need get both the displayName (the name we show) and the 
userId (imagine something like a username) before we send & receive messages.
'''
class User(BaseModel):
    displayName: str
    userId: str

class Message(BaseModel):
    sender: User
    receiver: User
    content: str
    timestamp: datetime

# Util functions
'''
Util functions is a generic name for any function that exists only to help other functions.

You typically create a util function for 2 reasons:
1. You're rewriting the same block of code multiple times in different places - in which case
you should write a util function to avoid repeating the same code block and maybe having mistakes.

2. You want to make the original function cleaner by replacing multiple lines of code with one
function call. 
'''
def parse_time(time_str: str):
    """Convert SQLite timestamp str to datetime object"""
    '''
    This function takes a timestamp as a string (like "2025-01-15 14:30:45.123456")
    and converts it into a Python datetime object that we can work with.

    isinstance() checks if the variable is a certain type - here we check if it's a string.
    If it is a string, we parse it using strptime() which converts strings to datetime objects.
    If it's already a datetime object, we just return it as-is.
    '''
    if isinstance(time_str, str):
        return datetime.strptime(time_str, '%Y-%m-%d %H:%M:%S.%f')
    return time_str

# TODO: WS /ws/typing  
# TODO: GET /api/presence

# Post a generic HTTP message
# This is not async now since we're using standard HTTP so it can run in thread pool as opposed to singlethreaded event loop.
# When we switch to websockets I'll use async since we'll need to await on the Websocket session


'''
Explanation of the above comment:

HTTP is the standard messaging protocol for sending information inside of an application as you're already familiar.

REST API defines standards for our message so that our applications can all understand each other easily. It defines
things like GET meaning get an object, PUT, etc.

If you looked at the top of the file I import something called FastAPI. FastAPI is a library that makes it super easy to write
Rest APIs, just like OpenAPI that you've worked with before.

I simply define the api by writing '@' and then defining what the operation (POST, GET, etc) will be and then
the string for the endpoint (here it's /api/message).
'''
@app.post("/api/message") # we're going to write out method to be able to POST to the message endpoint to write and upload msgs
def message(content: str, senderId: str, receiverId: str):
    '''
    This function handles POST requests to /api/message. When someone sends a message,
    this is what processes it.

    The function takes 3 parameters:
    - content: the actual message text
    - senderId: who's sending the message (like "mohammad")
    - receiverId: who's receiving the message (like "khader")

    Notice the type hints (content: str) - this tells Python and other developers what
    type each parameter should be, similar to type declarations in Swift/Kotlin.
    '''
    '''
    SQL is a language for fetching data from databases. It's an organized way of defining the exact data we need.

    Example: 
    SELECT displayName 
    FROM users 
    WHERE userId = khader
    - get the displayName column
    - From the `users` table
    - when the userId is khader
    
    This would return us the displayNames from all rows where the userId is khader.

    In our local database now this would return (Khader A. Murtaja)

    One of these databases that works well with SQL is called SQLite (imported sqlite3 above)
    SQLite it cool in that it runs natively on Python locally without much setup.

    Below I'll explain some of the basic concepts.
    
    if you read the README.md I have scripts you need to run that will do the work of setting up the db file and all of that for you 
    by now the folder and file should be there already and you can just pass 'storage/cipher.db' above.

    Everything inside of the `with` clause below is what happens while we have opened our local database.
    After the with clause ends (indicated by the end of indented code under it) the connection to our db file is closed.
    '''
    with sqlite3.connect('storage/cipher.db') as conn: # here i give the location of my local db file.

        cursor = conn.cursor() # the cursor is just how we run our queries to fetch the data, so defining it here.

        # fetch displayName (validate users exist)
        # through our cursor I run the query "SELECT  . . . " to get the displayNames for the two users
        # the one who wrote the msg and the one who will receive it (mohammad > khader)
        '''
        The '?' in the SQL query is a placeholder for security. Instead of putting the value
        directly in the string (which could allow SQL injection attacks), we pass it separately
        in a tuple (senderId,) - note the comma makes it a tuple even with one item.

        fetchone() gets one row from the results, and [0] gets the first column (displayName).

        If the user doesn't exist, sender_name will be None, so we raise an HTTPException.
        This is like throwing an error in mobile dev - it stops execution and returns a 404
        error to whoever made the request.
        '''
        cursor.execute('SELECT displayName FROM users WHERE userId = ?', (senderId,))
        sender_name = cursor.fetchone()
        if not sender_name:
            raise HTTPException(status_code=404, detail=f"User {senderId} not found")

        # Same validation for the receiver - make sure they exist in the database
        cursor.execute('SELECT displayName FROM users WHERE userId = ?', (receiverId,))
        receiver_name = cursor.fetchone()
        if not receiver_name:
            raise HTTPException(status_code=404, detail=f"User {receiverId} not found")

        '''
        Now that we've validated both users exist, we create User objects for them.
        Remember our User class from the top? We're creating instances of it here.

        This is like creating a struct/object in Swift or a data class in Kotlin.
        '''
        sender = User(userId=senderId, displayName=sender_name[0])
        receiver = User(userId=receiverId, displayName=receiver_name[0])

        '''
        Now we create our Message object with all the required fields.
        datetime.now() gets the current time - this is when the message was created.

        This Message object now has everything: who sent it, who receives it,
        what the content is, and when it was sent.
        '''
        msg = Message(
            sender=sender,
            receiver=receiver,
            content=content,
            timestamp=datetime.now()
        )

        # SQLite upload of the message
        '''
        INSERT INTO is the SQL command to add a new row to a table.
        We're inserting into the 'messages' table, specifying which columns we're filling,
        and providing the values with the ? placeholders again for security.

        The VALUES clause provides the actual data in the same order as the columns listed.

        conn.commit() is CRITICAL - it saves the changes to the database. Without this,
        the message would never actually be saved! Think of it like hitting "save" after
        editing a document.
        '''
        cursor.execute('INSERT INTO messages (senderId, receiverId, content, timestamp) VALUES (?, ?, ?, ?)',
                       (msg.sender.userId, msg.receiver.userId, msg.content, msg.timestamp)
                       )
        conn.commit()

    '''
    This print statement is just for debugging - it shows in the server logs that the
    message was successfully written. The f-string (f"...") allows us to embed variables
    directly in the string using {variable_name}.

    Finally, we return a dictionary (similar to a map in mobile dev) containing the
    message object. FastAPI automatically converts this to JSON for the response.
    '''
    print(f"Wrote \"{msg.content}\" from {sender.displayName} to {receiver.displayName} into DB")
    return {"message": msg}


# Fetch all the messages sent to and by the user from the DB
'''
This is a GET endpoint (not POST like above). GET is for retrieving data, not creating it.
When the mobile app wants to load the chat history, it calls this endpoint.
'''
@app.get("/api/message")
def fetchMessages(userId: str):
    '''
    This function fetches all messages where the user is either the sender OR receiver.
    So if mohammad calls this, he gets all messages he sent and all messages sent to him.
    '''
    with sqlite3.connect('storage/cipher.db') as conn:
        '''
        row_factory = sqlite3.Row makes it so we can access columns by name instead of index.
        Instead of row[0], row[1], we can do row['content'], row['timestamp'] which is
        much clearer and less error-prone.
        '''
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        '''
        This is a more complex SQL query using JOIN. Let me break it down:

        - We're selecting from the messages table (aliased as 'm')
        - JOIN users s means join with the users table (aliased as 's' for sender)
          matching where m.senderId = s.userId
        - JOIN users r means join with the users table again (aliased as 'r' for receiver)
          matching where m.receiverId = r.userId

        Why JOIN? Because the messages table only stores userId strings, but we want
        the full user information (displayName) for both sender and receiver.

        WHERE m.senderId = ? OR m.receiverId = ? filters to messages where our user
        is involved (either sending or receiving).

        ORDER BY m.timestamp ASC sorts messages by time, oldest first (ASC = ascending).
        '''
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

        '''
        chat_history = [] creates an empty list (similar to arrays in mobile dev).
        We'll fill this list with Message objects.

        cursor.fetchall() gets ALL rows from the query result (unlike fetchone() which
        gets just one row).

        The for loop iterates through each row - this is like a for-each loop in Swift/Kotlin.
        '''
        chat_history = []
        for row in cursor.fetchall():
            '''
            For each row from the database, we create a Message object.
            Notice how we're creating User objects inline here - we don't store them
            in variables because we only need them to create the Message.

            We use parse_time() (our util function from the top) to convert the timestamp
            string from the database into a proper datetime object.

            Then we append (add) this message to our chat_history list.
            '''
            msg = Message(
                sender=User(userId=row['senderId'], displayName=row['senderName']),
                receiver=User(userId=row['receiverId'], displayName=row['receiverName']),
                content=row['content'],
                timestamp=parse_time(row["timestamp"])
            )
            chat_history.append(msg)

        '''
        len() gets the length of the list - how many messages we found.
        This print is just for debugging in the server logs.
        '''
        print(f"messages to & from {userId}: {len(chat_history)} messages")

    '''
    Return the chat history as a dictionary. FastAPI converts this to JSON automatically,
    so the mobile app receives a JSON object with a "chat_history" array containing
    all the messages.
    '''
    return {"chat_history": chat_history}

# Create a new user
'''
This POST endpoint creates a new user in the database. When someone signs up or
first uses the app, we call this to create their user record.
'''
@app.post("/api/users")
def createUser(userId: str, displayName: str):
    '''
    Takes two parameters:
    - userId: the unique identifier (like a username)
    - displayName: the name we show to other users
    '''
    with sqlite3.connect('storage/cipher.db') as conn:
        cursor = conn.cursor()

        '''
        INSERT OR REPLACE is special - it means:
        - If this userId doesn't exist, INSERT it (create new user)
        - If this userId already exists, REPLACE it (update the user)

        This is useful because we don't have to check if the user exists first.
        It's like an "upsert" operation (update or insert).
        '''
        cursor.execute('INSERT OR REPLACE INTO users (userId, displayName) VALUES (?, ?)',
                  (userId, displayName))
        conn.commit()

    '''
    Return the user information we just created/updated. This confirms to the
    mobile app that the operation was successful.
    '''
    return {"userId": userId, "displayName": displayName}

'''
This is the root endpoint - when you visit http://localhost:8000/ in a browser,
this function handles it. It serves our frontend HTML page.

Notice this is an async function - async/await in Python is similar to async/await
in Swift. It allows the function to handle other requests while waiting for I/O
operations (like reading files).
'''
@app.get("/")
async def root():
    '''
    Opens the index.html file from the frontend folder and reads its contents.
    The 'with' statement ensures the file is properly closed after reading.

    HTMLResponse tells FastAPI to return this as HTML (not JSON), so the browser
    renders it as a web page.
    '''
    with open("frontend/index.html") as f:
        return HTMLResponse(f.read())

'''
app.mount() makes a whole directory available for serving static files (CSS, JS, images).
When someone requests /frontend/style.css, FastAPI will automatically serve the file
from the frontend directory.

This is how we serve all our frontend assets (HTML, CSS, JavaScript files).
'''
app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")

'''
This is the entry point of the application - it only runs when you execute this file
directly (not when importing it as a module).

if __name__ == "__main__" is a Python idiom that means "only run this code if this
file is being run directly, not if it's being imported."

uvicorn is the web server that runs our FastAPI application. We tell it to:
- Run our 'app' object
- Listen on all network interfaces (0.0.0.0)
- Use port 8000

So when you run 'python backend.py', uvicorn starts up and your API is available
at http://localhost:8000
'''
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
