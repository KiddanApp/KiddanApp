from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import characters, chat, lessons, admin

app = FastAPI(title="PunjabiTutor Backend – Phase 1")

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
app.include_router(admin.router, tags=["admin"])

@app.get("/health")
async def health():
    return {"status": "ok"}
