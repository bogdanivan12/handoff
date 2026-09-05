import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import Product, Project
from app.schemas import ProjectCreate, ProjectRead, ProjectUpdate

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectRead])
async def list_projects(
    product_id: uuid.UUID = Query(...), db: AsyncSession = Depends(get_db)
) -> list[Project]:
    result = await db.execute(
        select(Project).where(Project.product_id == product_id).order_by(Project.created_at)
    )
    return list(result.scalars().all())


@router.post("", response_model=ProjectRead, status_code=201)
async def create_project(payload: ProjectCreate, db: AsyncSession = Depends(get_db)) -> Project:
    product = await db.get(Product, payload.product_id)
    if product is None:
        raise HTTPException(status_code=404, detail="Product not found")

    project = Project(**payload.model_dump())
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return project


@router.get("/{project_id}", response_model=ProjectRead)
async def get_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectRead)
async def update_project(
    project_id: uuid.UUID, payload: ProjectUpdate, db: AsyncSession = Depends(get_db)
) -> Project:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return project


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: uuid.UUID, db: AsyncSession = Depends(get_db)) -> None:
    project = await db.get(Project, project_id)
    if project is None:
        raise HTTPException(status_code=404, detail="Project not found")
    await db.delete(project)
    await db.commit()
