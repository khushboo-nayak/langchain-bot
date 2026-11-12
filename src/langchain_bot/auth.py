from typing import TypedDict
import sqlite3
from pathlib import Path
UserRecord = TypedDict("User", {"email": str, "full_name": str, "role": str})
root=Path(__file__).resolve().parents[2]
DB_PATH = root / "ecommerce.db"
def authenticate_user(email:str, password:str, role=None):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    if role is not None:
        cursor.execute("SELECT email, full_name, role FROM users WHERE email = ? AND password = ? AND role = ?", (email, password, role))
    else:
        cursor.execute("SELECT email, full_name, role FROM users WHERE email = ? AND password = ?", (email, password))        
    result = cursor.fetchone()
    conn.close()
    if result:
        return UserRecord(email=result[0], full_name=result[1], role=result[2])
    return None
