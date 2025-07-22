import os
import re
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from fastapi import HTTPException

# Load DB URL securely - NO fallback credentials
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError(
        "DATABASE_URL environment variable is required. "
        "Please set it in your .env file or environment."
    )

# Get pool settings from environment with secure defaults
DB_POOL_SIZE = int(os.getenv("DB_POOL_SIZE", "10"))
DB_MAX_OVERFLOW = int(os.getenv("DB_MAX_OVERFLOW", "20"))
DB_POOL_TIMEOUT = int(os.getenv("DB_POOL_TIMEOUT", "30"))
DB_POOL_RECYCLE = int(os.getenv("DB_POOL_RECYCLE", "1800"))

# Create SQLAlchemy engine with configurable pooling parameters
engine = create_engine(
    DATABASE_URL,
    pool_size=DB_POOL_SIZE,
    max_overflow=DB_MAX_OVERFLOW,
    pool_timeout=DB_POOL_TIMEOUT,
    pool_recycle=DB_POOL_RECYCLE,
    echo=False  # Never log SQL in production for security
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
    Rejects reserved/dangerous subdomains.
    """
    if not host:
        raise HTTPException(status_code=400, detail="Missing Host header")
    
    # Get base domain from environment for validation
    base_domain = os.getenv("BASE_DOMAIN", "gradeinsight.com")
    
    # Validate host ends with our base domain
    if not host.endswith(f".{base_domain}") and host != base_domain:
        raise HTTPException(status_code=400, detail="Invalid host domain")
    
    # Handle main domain (no subdomain)
    if host == base_domain:
        return "main"  # or however you want to handle the main domain
    
    # Extract subdomain
    subdomain = host.replace(f".{base_domain}", "").lower()
    
    # Reserved subdomains that should not be allowed as tenants
    reserved_subdomains = {
        "www", "api", "app", "mail", "email", "ftp", "ssh", 
        "test", "staging", "dev", "demo", "support", "help", "blog",
        "docs", "status", "monitor", "cdn", "static", "assets"
    }
    
    if subdomain in reserved_subdomains:
        raise HTTPException(status_code=400, detail="Reserved subdomain not allowed")
    
    # Restrict tenant to alphanumeric + hyphen, 3-63 chars (DNS limits)
    if not re.fullmatch(r"[a-z0-9\-]{3,63}", subdomain):
        raise HTTPException(
            status_code=400, 
            detail="Invalid tenant: must be 3-63 characters, alphanumeric and hyphens only"
        )
    
    # Don't allow subdomains starting or ending with hyphen
    if subdomain.startswith("-") or subdomain.endswith("-"):
        raise HTTPException(status_code=400, detail="Tenant cannot start or end with hyphen")
    
    return subdomain
