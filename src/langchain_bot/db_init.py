
from pathlib import Path
import sqlite3

root=Path(__file__).resolve().parents[2]
DB_PATH = root / "ecommerce.db"
SQL_SEED_PATH = root / "ecommerce_setup.sql"

def init_database():
    with open(SQL_SEED_PATH, "r", encoding="utf-8") as f:
        SQL_SEED = f.read()
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.executescript(SQL_SEED)
    conn.commit()
    return DB_PATH

def main():
    db_path=init_database()
    print(f"Database initialized at: {db_path}")

if __name__=="__main__":
    main()