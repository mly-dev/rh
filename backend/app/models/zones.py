"""Zones administratives du Niger : région → département → commune."""
from sqlalchemy import Float, ForeignKey, Index, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

ZONE_LEVELS = ("region", "departement", "commune")


class AdminZone(Base):
    __tablename__ = "admin_zones"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    # nom normalisé (minuscules, sans accents) pour la correspondance à l'import
    normalized_name: Mapped[str] = mapped_column(String(120), index=True)
    level: Mapped[str] = mapped_column(String(20), index=True)
    parent_id: Mapped[int | None] = mapped_column(
        ForeignKey("admin_zones.id"), nullable=True
    )
    code: Mapped[str | None] = mapped_column(String(30), unique=True)
    centroid_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    centroid_lon: Mapped[float | None] = mapped_column(Float, nullable=True)

    parent: Mapped["AdminZone | None"] = relationship(
        remote_side=[id], backref="children"
    )

    __table_args__ = (Index("ix_zone_level_name", "level", "normalized_name"),)

    def __repr__(self) -> str:  # pragma: no cover
        return f"<AdminZone {self.level}:{self.name}>"
