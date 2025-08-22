import sqlite3
from werkzeug.security import generate_password_hash

def create_or_update_admin(username, password):
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Ensure admins table exists
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS admins (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL
        )
    """)

    # Check if username already exists
    cursor.execute("SELECT id FROM admins WHERE username = ?", (username,))
    existing = cursor.fetchone()

    if existing:
        # Update password if user exists
        hashed = generate_password_hash(password)
        cursor.execute("UPDATE admins SET password_hash = ? WHERE username = ?", (hashed, username))
        print(f"✅ Password updated for admin '{username}'")
    else:
        # Create new admin
        hashed = generate_password_hash(password)
        cursor.execute("INSERT INTO admins (username, password_hash) VALUES (?, ?)", (username, hashed))
        print(f"✅ New admin '{username}' created")

    conn.commit()
    conn.close()

if __name__ == "__main__":
    # Example usage
    username = input("Enter admin username: ")
    password = input("Enter admin password: ")
    create_or_update_admin(username, password)
