from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.db.database import Base, engine

from app.routers import (
    users,
    groups,
    logs,
    export
)


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="IntelliID API",
    description="Intelligent Identity Lifecycle Orchestrator",
    version="1.0.0"
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(users.router)
app.include_router(groups.router)
app.include_router(logs.router)
app.include_router(export.router)


@app.get("/")
async def root():

    return {
        "application": "IntelliID",
        "status": "running"
    }


@app.get("/health")
async def health():

    return {
        "status": "healthy"
    }