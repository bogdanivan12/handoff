import uuid
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, ForeignKey, JSON, Numeric, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db_types import GUID


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    acceptance_criteria_format_default: Mapped[str] = mapped_column(
        Text, default="basic", server_default="basic"
    )
    key_prefix: Mapped[str] = mapped_column(Text, unique=True)
    next_issue_number: Mapped[int] = mapped_column(default=1, server_default="1")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    initiatives: Mapped[list["Initiative"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    projects: Mapped[list["Project"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )
    sprints: Mapped[list["Sprint"]] = relationship(
        back_populates="product", cascade="all, delete-orphan"
    )


class Initiative(Base):
    __tablename__ = "initiatives"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship(back_populates="initiatives")
    epics: Mapped[list["Epic"]] = relationship(back_populates="initiative", cascade="all, delete-orphan")


class Epic(Base):
    __tablename__ = "epics"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    initiative_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("initiatives.id", ondelete="CASCADE")
    )
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    initiative: Mapped["Initiative"] = relationship(back_populates="epics")
    features: Mapped[list["Feature"]] = relationship(back_populates="epic", cascade="all, delete-orphan")


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship(back_populates="projects")


class Sprint(Base):
    __tablename__ = "sprints"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    product_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("products.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(Text)
    start_date: Mapped[date | None] = mapped_column(Date, default=None)
    end_date: Mapped[date | None] = mapped_column(Date, default=None)
    status: Mapped[str] = mapped_column(Text, default="planned", server_default="planned")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    product: Mapped["Product"] = relationship(back_populates="sprints")


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    epic_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("epics.id", ondelete="CASCADE"))
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(
        GUID, ForeignKey("projects.id", ondelete="SET NULL"), default=None
    )
    name: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(Text, default="draft", server_default="draft")
    acceptance_criteria_format: Mapped[str] = mapped_column(
        Text, default="basic", server_default="basic"
    )
    issue_number: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    epic: Mapped["Epic"] = relationship(back_populates="features")

    @property
    def issue_key(self) -> str:
        return f"{self.epic.initiative.product.key_prefix}-{self.issue_number}"


class KnowledgeItem(Base):
    __tablename__ = "knowledge_items"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    type: Mapped[str] = mapped_column(Text)
    scope: Mapped[str] = mapped_column(Text)
    scope_ref_id: Mapped[uuid.UUID] = mapped_column(GUID)
    content: Mapped[dict] = mapped_column(JSONB().with_variant(JSON(), "sqlite"))
    confidence: Mapped[float | None] = mapped_column(Numeric(3, 2), default=None)
    provenance: Mapped[str] = mapped_column(Text, default="manual", server_default="manual")
    source_ref_type: Mapped[str | None] = mapped_column(Text, default=None)
    source_ref_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    status: Mapped[str] = mapped_column(Text, default="active", server_default="active")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())


class KnowledgeRelation(Base):
    __tablename__ = "knowledge_relations"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    from_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("knowledge_items.id", ondelete="CASCADE")
    )
    to_item_id: Mapped[uuid.UUID] = mapped_column(
        GUID, ForeignKey("knowledge_items.id", ondelete="CASCADE")
    )
    relation_type: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    __table_args__ = (
        CheckConstraint("from_item_id != to_item_id", name="ck_knowledge_relations_no_self_link"),
    )
