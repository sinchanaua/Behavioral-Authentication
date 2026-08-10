"""
utils/database.py
------------------
Manages user registration and login using SQLite.

SQLite is a lightweight database built into Python.
No installation needed — it creates a local .db file.

Database file: data/users.db
Table: users
  - id       : auto increment
  - username : unique username
  - password : hashed password (secure)
  - created  : registration timestamp
"""

import sqlite3
import hashlib
import os
from datetime import datetime

DB_PATH = "data/users.db"


def get_connection():
    """Creates and returns a database connection."""
    os.makedirs("data", exist_ok=True)
    return sqlite3.connect(DB_PATH)


def create_tables():
    """
    Creates the users table if it doesn't exist.
    Called once when the app starts.
    """
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id        INTEGER PRIMARY KEY AUTOINCREMENT,
            username  TEXT    UNIQUE NOT NULL,
            password  TEXT    NOT NULL,
            created   TEXT    NOT NULL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS login_history (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            username    TEXT    NOT NULL,
            timestamp   TEXT    NOT NULL,
            success     INTEGER NOT NULL,
            message     TEXT,
            ip_address  TEXT
        )
    """)
    conn.commit()
    conn.close()
    print("[DB] Database initialized successfully.")


def hash_password(password):
    """
    Converts plain password to a secure hash using SHA-256.
    We NEVER store plain passwords — always hashed.
    Example: "mypassword" → "a665a45920..."
    """
    return hashlib.sha256(password.encode()).hexdigest()


def register_user(username, password):
    """
    Registers a new user in the database.
    Returns: (True, "Success") or (False, "Error message")
    """
    if not username or not password:
        return False, "Username and password cannot be empty."

    if len(username) < 3:
        return False, "Username must be at least 3 characters."

    if len(password) < 6:
        return False, "Password must be at least 6 characters."

    hashed = hash_password(password)
    created = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO users (username, password, created) VALUES (?, ?, ?)",
            (username.strip(), hashed, created)
        )
        conn.commit()
        conn.close()
        print(f"[DB] User registered: {username}")
        return True, "Registration successful!"

    except sqlite3.IntegrityError:
        return False, "Username already exists. Please choose another."
    except Exception as e:
        return False, f"Database error: {str(e)}"


def login_user(username, password):
    """
    Verifies username and password.
    Returns: (True, "Success") or (False, "Error message")
    """
    if not username or not password:
        return False, "Please enter username and password."

    hashed = hash_password(password)

    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, username FROM users WHERE username=? AND password=?",
            (username.strip(), hashed)
        )
        user = cursor.fetchone()
        conn.close()

        if user:
            print(f"[DB] Login successful: {username}")
            return True, "Login successful!"
        else:
            return False, "Invalid username or password."

    except Exception as e:
        return False, f"Database error: {str(e)}"


def log_login_attempt(username, success, message, ip_address=None):
    """Stores every login attempt in the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO login_history (username, timestamp, success, message, ip_address)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                username.strip() if username else "",
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                1 if success else 0,
                message,
                ip_address or ""
            )
        )
        conn.commit()
        conn.close()
        print(f"[DB] Login attempt logged: {username} - {'SUCCESS' if success else 'FAIL'}")
    except Exception as e:
        print(f"[DB] Failed to log login attempt: {e}")


def fetch_login_history(limit=50):
    """Returns the most recent login attempts."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT timestamp, username, success, message, ip_address
            FROM login_history
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,)
        )
        rows = cursor.fetchall()
        conn.close()

        history = []
        for timestamp, username, success, message, ip_address in rows:
            history.append({
                "timestamp": timestamp,
                "username": username,
                "status": "Success" if success else "Failed",
                "message": message,
                "ip_address": ip_address,
            })
        return history
    except Exception as e:
        print(f"[DB] Failed to fetch login history: {e}")
        return []


def user_exists(username):
    """Checks if a username already exists in the database."""
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT id FROM users WHERE username=?", (username,))
        result = cursor.fetchone()
        conn.close()
        return result is not None
    except:
        return False


# Run directly to test
if __name__ == "__main__":
    create_tables()
    print(register_user("testuser", "password123"))
    print(login_user("testuser", "password123"))
    print(login_user("testuser", "wrongpassword"))