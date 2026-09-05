from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router
from app.routers.products import router as products_router
from app.routers.initiatives import router as initiatives_router
from app.routers.epics import router as epics_router

app = FastAPI(title="Handoff API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(products_router)
app.include_router(initiatives_router)
app.include_router(epics_router)
