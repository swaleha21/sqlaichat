import os
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "3306")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")
DB_NAME = os.getenv("DB_NAME", "e-commerce")

# --------------------------------------------------
# Create MySQL connection using SQLAlchemy
# --------------------------------------------------
DATABASE_URL = (
    f"mysql+pymysql://{DB_USER}:{DB_PASSWORD}"
    f"@{DB_HOST}:{DB_PORT}/{DB_NAME}"
)

engine = create_engine(
    DATABASE_URL,
    echo=True,        # shows SQL logs (good for debugging)
    pool_pre_ping=True
)

# --------------------------------------------------
# Test database connection
# --------------------------------------------------
def test_connection():
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("✅ MySQL connected successfully!")
    except SQLAlchemyError as e:
        print("❌ MySQL connection failed")
        print(e)

# --------------------------------------------------
# Create sample table
# --------------------------------------------------
def create_tables():
    query = """
    CREATE TABLE IF NOT EXISTS users (
        id INT AUTO_INCREMENT PRIMARY KEY,
        name VARCHAR(100),
        email VARCHAR(100),
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    """
    try:
        with engine.connect() as conn:
            conn.execute(text(query))
        print("✅ Tables created successfully!")
    except SQLAlchemyError as e:
        print("❌ Error creating tables")
        print(e)

# --------------------------------------------------
# Insert data
# --------------------------------------------------
def insert_user(name, email):
    query = """
    INSERT INTO users (name, email)
    VALUES (:name, :email)
    """
    try:
        with engine.connect() as conn:
            conn.execute(
                text(query),
                {"name": name, "email": email}
            )
        print("✅ User inserted successfully!")
    except SQLAlchemyError as e:
        print("❌ Error inserting user")
        print(e)

# --------------------------------------------------
# Fetch data
# --------------------------------------------------
def fetch_users():
    query = "SELECT * FROM users"
    try:
        with engine.connect() as conn:
            result = conn.execute(text(query))
            users = result.fetchall()
        return users
    except SQLAlchemyError as e:
        print("❌ Error fetching users")
        print(e)
        return []

# --------------------------------------------------
# MAIN (Run this file directly)
# --------------------------------------------------
if __name__ == "__main__":
    test_connection()
    create_tables()
    insert_user("Swaleha", "swaleha@example.com")

    users = fetch_users()
    print("\n📌 Users in database:")
    for user in users:
        print(user)