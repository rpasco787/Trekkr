from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routers import auth, health


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown events."""
    # Startup: Initialize the database
    init_db()
    yield
    # Shutdown: Cleanup if needed

app = FastAPI(
    title="Trekkr API",
    description="Backend API for Trekkr",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware configuration
# Update origins list when frontend is available
origins = [
    "http://localhost:3000",
    "http://localhost:5173",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(health.router, prefix="/api", tags=["health"])
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])


@app.get("/")
async def root():
    return {"message": "Welcome to Trekkr API"}

