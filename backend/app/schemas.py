import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict


class ProductCreate(BaseModel):
    name: str
    description: str | None = None
    key_prefix: str


class ProductUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    key_prefix: str | None = None


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str | None
    key_prefix: str
    created_at: datetime
    updated_at: datetime


class InitiativeCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    description: str | None = None


class InitiativeUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class InitiativeRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class EpicCreate(BaseModel):
    initiative_id: uuid.UUID
    name: str
    description: str | None = None


class EpicUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class EpicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    initiative_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class FeatureCreate(BaseModel):
    epic_id: uuid.UUID
    name: str
    requirements: str | None = None


class FeatureUpdate(BaseModel):
    name: str | None = None
    requirements: str | None = None
    status: str | None = None


class FeatureRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    epic_id: uuid.UUID
    name: str
    requirements: str | None
    status: str
    acceptance_criteria_format: str
    issue_number: int
    issue_key: str
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    description: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None


class ProjectRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class SprintCreate(BaseModel):
    product_id: uuid.UUID
    name: str
    start_date: date | None = None
    end_date: date | None = None


class SprintUpdate(BaseModel):
    name: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    status: str | None = None


class SprintRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    product_id: uuid.UUID
    name: str
    start_date: date | None
    end_date: date | None
    status: str
    created_at: datetime
    updated_at: datetime
