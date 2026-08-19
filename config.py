import os

from sqlalchemy import create_engine
from dotenv import load_dotenv

load_dotenv()


DB_CONFIG = {
    "host": os.getenv("MYSQLHOST"),
    "port": os.getenv("MYSQLPORT", "3306"),
    "user": os.getenv("MYSQLUSER"),
    "password": os.getenv("MYSQLPASSWORD"),
    "database": os.getenv("MYSQLDATABASE")
}


SERVER_URL = (
    f"mysql+pymysql://{DB_CONFIG['user']}:"
    f"{DB_CONFIG['password']}@"
    f"{DB_CONFIG['host']}:"
    f"{DB_CONFIG['port']}"
)


DATABASE_URL = (
    f"{SERVER_URL}/{DB_CONFIG['database']}"
)


server_engine = create_engine(
    SERVER_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    future=True
)


db_engine = create_engine(
    DATABASE_URL,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    future=True
)