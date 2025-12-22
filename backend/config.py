import os

# JWT Configuration
# In production, set SECRET_KEY environment variable to a secure random value
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "dev-secret-key-change-in-production-abc123xyz789"  # Default for development only
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60
REFRESH_TOKEN_EXPIRE_DAYS = 14

