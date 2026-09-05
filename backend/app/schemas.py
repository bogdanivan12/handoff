import uuid
from datetime import datetime

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
