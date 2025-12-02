from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import os

from app.routers import characters, chat, lessons, admin

app = FastAPI(title="PunjabiTutor Backend – Phase 1")

# Mount static files
static_dir = os.path.join(os.path.dirname(__file__), "static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

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

@app.get("/admin")
async def admin_panel():
    """Serve the admin panel HTML page"""
    admin_file = os.path.join(static_dir, "admin.html")
    if os.path.exists(admin_file):
        return FileResponse(admin_file, media_type='text/html')
    return {"error": "Admin panel not found"}

@app.get("/health")
async def health():
    return {"status": "ok"}
