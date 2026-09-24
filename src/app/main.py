import os

import fastapi
from dotenv import load_dotenv
from fastapi.staticfiles import StaticFiles

from app.database import initialize_database

load_dotenv()

from app.admin.auth_router import router as admin_auth_router
from app.admin.router import router as admin_router
from app.auth.router import router as auth_router
from app.user_router import router as user_router
import app.log_service  # noqa: F401 — registers /auth/login, /logout, /me routes


STATIC_DIR = os.path.join(os.path.dirname(__file__), "../static")

app = fastapi.FastAPI()


@app.on_event("startup")
def startup() -> None:
    initialize_database()


app.include_router(auth_router)
app.include_router(admin_auth_router)
app.include_router(admin_router)
app.include_router(user_router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

