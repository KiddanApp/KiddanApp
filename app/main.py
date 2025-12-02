from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db import engine
from app.models import Base

from app.routers import characters, chat, lessons

@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield

app = FastAPI(title="PunjabiTutor Backend – Phase 1", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(characters.router, prefix="/characters", tags=["characters"])
app.include_router(chat.router, prefix="/chat", tags=["chat"])
app.include_router(lessons.router, prefix="/lessons", tags=["lessons"])

@app.get("/health")
async def health():
    return {"status": "ok"}
