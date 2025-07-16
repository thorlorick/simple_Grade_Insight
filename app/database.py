import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

# Load DB URL securely
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+psycopg2://gradeuser:gradepass@localhost:5432/gradeinsight"
)

# Create SQLAlchemy engine with sensible pooling parameters
engine = create_engine(
    DATABASE_URL,
    pool_size=10,          # number of DB connections to keep open in the pool
    max_overflow=20,       # max number of connections to open above pool_size
    pool_timeout=30,       # seconds to wait before giving up on getting connection from pool
    pool_recycle=1800,     # recycle connections after 30 minutes to avoid stale connections
    echo=False             # set True to log SQL queries (debug only)
)

# SessionLocal factory for per-request DB sessions
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency that yields a new database session and ensures closure.
    """
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_tenant_from_host(host: str) -> str:
    """
    Extract tenant subdomain from host header safely.

    Raises HTTPException if host missing or invalid.
    Only allows lowercase letters, digits, and hyphens.
    """
    if not host:
        raise HTTPException(status_code=400, detail="Missing Host header")

    subdomain = host.split(".")[0].lower()

    # Restrict tenant to alphanumeric + hyphen for safety
    if not subdomain or not re.fullmatch(r"[a-z0-9\-]+", subdomain):
        raise HTTPException(status_code=400, detail="Invalid tenant in host")

    return subdomain
