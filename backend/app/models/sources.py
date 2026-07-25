"""Traçabilité des fichiers importés et de leurs mappings."""
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

FILE_TYPES = ("csv", "xlsx", "pdf")
SOURCE_STATUSES = ("preview", "imported", "failed")


class DataSource(Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_type: Mapped[str] = mapped_column(String(10))
    uploaded_by: Mapped[str] = mapped_column(String(120), default="anonyme")
    uploaded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    status: Mapped[str] = mapped_column(String(20), default="preview")
    # étiquette libre : humanitaire | gouvernemental | commercial | autre
    domain: Mapped[str | None] = mapped_column(String(40), nullable=True)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    stored_path: Mapped[str] = mapped_column(Text)
    # colonnes détectées, types inférés, alertes PII, rapport d'import
    parse_report: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    mappings: Mapped[list["ColumnMapping"]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class ColumnMapping(Base):
    __tablename__ = "column_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("data_sources.id"))
    source_column: Mapped[str] = mapped_column(String(255))
    target_entity: Mapped[str] = mapped_column(String(20))
    target_field: Mapped[str] = mapped_column(String(60))

    source: Mapped[DataSource] = relationship(back_populates="mappings")
