from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.routers.health import router as health_router
from app.routers.products import router as products_router
from app.routers.initiatives import router as initiatives_router
from app.routers.epics import router as epics_router
from app.routers.features import router as features_router
from app.routers.projects import router as projects_router
from app.routers.sprints import router as sprints_router
from app.routers.knowledge_items import router as knowledge_items_router
from app.routers.knowledge_relations import router as knowledge_relations_router
from app.routers.tasks import router as tasks_router
from app.routers.acceptance_criteria import router as acceptance_criteria_router
from app.routers.task_dependencies import router as task_dependencies_router
from app.routers.feature_dependencies import router as feature_dependencies_router

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
app.include_router(features_router)
app.include_router(projects_router)
app.include_router(sprints_router)
app.include_router(knowledge_items_router)
app.include_router(knowledge_relations_router)
app.include_router(tasks_router)
app.include_router(acceptance_criteria_router)
app.include_router(task_dependencies_router)
app.include_router(feature_dependencies_router)
