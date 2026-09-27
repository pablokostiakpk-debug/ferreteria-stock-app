from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .auth import seed_users
from .database import Base, SessionLocal, engine
from .routers import auth, dashboard, import_export, products, replenishment, stock, suppliers
from .schemas import HealthOut

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"

@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        seed_users(db)
    yield


app = FastAPI(title="Stock Ferretería", version="0.1.0", lifespan=lifespan)

app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(products.router)
app.include_router(suppliers.router)
app.include_router(stock.router)
app.include_router(replenishment.router)
app.include_router(import_export.router)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/api/health", response_model=HealthOut)
def health():
    return {"ok": True}


@app.get("/{path:path}")
def spa(path: str):
    # La API se registra antes; cualquier otra ruta vuelve a la SPA.
    return FileResponse(STATIC_DIR / "index.html")
