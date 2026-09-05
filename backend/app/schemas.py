import uuid
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from app.knowledge_content import KnowledgeContent


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


class KnowledgeItemCreate(BaseModel):
    scope: Literal["product", "project"]
    scope_ref_id: uuid.UUID
    content: KnowledgeContent
    confidence: float | None = Field(default=None, ge=0, le=1)
    provenance: Literal["manual", "extracted_from_task", "extracted_from_agent_session"] = "manual"


class KnowledgeItemUpdate(BaseModel):
    content: KnowledgeContent | None = None
    status: Literal["draft", "active", "superseded", "conflicting", "rejected"] | None = None


class KnowledgeItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    type: str
    scope: str
    scope_ref_id: uuid.UUID
    content: dict
    confidence: float | None
    provenance: str
    status: str
    created_at: datetime
    updated_at: datetime


class KnowledgeRelationCreate(BaseModel):
    from_item_id: uuid.UUID
    to_item_id: uuid.UUID
    relation_type: Literal["supersedes", "conflicts_with", "derived_from", "refines"]


class KnowledgeRelationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_item_id: uuid.UUID
    to_item_id: uuid.UUID
    relation_type: str
    created_at: datetime


class TaskCreate(BaseModel):
    feature_id: uuid.UUID
    project_id: uuid.UUID
    sprint_id: uuid.UUID | None = None
    title: str
    task_type: Literal["feature", "bug", "improvement", "chore", "research"]
    context: str | None = None
    scope: str | None = None
    out_of_scope: str | None = None
    position: int | None = None


class TaskUpdate(BaseModel):
    title: str | None = None
    task_type: Literal["feature", "bug", "improvement", "chore", "research"] | None = None
    status: Literal["todo", "in_progress", "done", "outdated"] | None = None
    sprint_id: uuid.UUID | None = None
    context: str | None = None
    scope: str | None = None
    out_of_scope: str | None = None
    position: int | None = None


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    feature_id: uuid.UUID
    project_id: uuid.UUID
    sprint_id: uuid.UUID | None
    title: str
    task_type: str
    status: str
    issue_number: int
    issue_key: str
    context: str | None
    scope: str | None
    out_of_scope: str | None
    position: int | None
    created_at: datetime
    updated_at: datetime
    is_blocked: bool


class AcceptanceCriterionCreate(BaseModel):
    format: Literal["basic", "gherkin"] = "basic"
    description: str | None = None
    given: str | None = None
    when_: str | None = None
    then_: str | None = None
    position: int = 0


class AcceptanceCriterionUpdate(BaseModel):
    description: str | None = None
    given: str | None = None
    when_: str | None = None
    then_: str | None = None
    position: int | None = None
    checked: bool | None = None
    notes: str | None = None


class AcceptanceCriterionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    format: str
    description: str | None
    given: str | None
    when_: str | None
    then_: str | None
    position: int
    checked: bool
    checked_at: datetime | None
    notes: str | None
    created_at: datetime


class TaskDependencyTaskSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    issue_key: str
    title: str
    status: str


class TaskDependencyCreate(BaseModel):
    depends_on_task_id: uuid.UUID


class TaskDependencyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    task_id: uuid.UUID
    depends_on_task: TaskDependencyTaskSummary
    created_at: datetime


class TaskIsBlockedRead(BaseModel):
    is_blocked: bool
    blocking_tasks: list[TaskDependencyTaskSummary]
