import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from app.db_types import GUID


class Base(DeclarativeBase):
    pass


class Product(Base):
    __tablename__ = "products"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(Text)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    acceptance_criteria_format_default: Mapped[str] = mapped_column(Text, default="basic")
    key_prefix: Mapped[str] = mapped_column(Text)
    next_issue_number: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    initiatives: Mapped[list["Initiative"]] = relationship(
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


class Feature(Base):
    __tablename__ = "features"

    id: Mapped[uuid.UUID] = mapped_column(GUID, primary_key=True, default=uuid.uuid4)
    epic_id: Mapped[uuid.UUID] = mapped_column(GUID, ForeignKey("epics.id", ondelete="CASCADE"))
    default_project_id: Mapped[uuid.UUID | None] = mapped_column(GUID, default=None)
    name: Mapped[str] = mapped_column(Text)
    requirements: Mapped[str | None] = mapped_column(Text, default=None)
    status: Mapped[str] = mapped_column(Text, default="draft")
    acceptance_criteria_format: Mapped[str] = mapped_column(Text, default="basic")
    issue_number: Mapped[int] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    epic: Mapped["Epic"] = relationship(back_populates="features")

    @property
    def issue_key(self) -> str:
        return f"{self.epic.initiative.product.key_prefix}-{self.issue_number}"
