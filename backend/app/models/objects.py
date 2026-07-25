"""Objets métier de l'ontologie : Site, Stock, Incident (agrégé), Indicateur.

Contrainte de conception : aucune table ni aucun champ ne peut représenter
une personne physique identifiable. Les incidents sont des comptages par
zone (pas de coordonnées, pas de détail individuel) ; les « bénéficiaires »
n'existent que comme valeurs numériques agrégées dans Indicator.
"""
from datetime import date, datetime, timezone

from sqlalchemy import (
    JSON,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base

SITE_STATUSES = ("fonctionnel", "partiel", "non_fonctionnel", "inconnu")


class Site(Base):
    __tablename__ = "sites"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    site_type: Mapped[str] = mapped_column(String(80), index=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("admin_zones.id"), index=True)
    lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    status: Mapped[str] = mapped_column(String(30), default="inconnu")
    capacity: Mapped[float | None] = mapped_column(Numeric(14, 2), nullable=True)
    capacity_unit: Mapped[str | None] = mapped_column(String(60), nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_sources.id"), nullable=True
    )
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    zone = relationship("AdminZone")
    stocks: Mapped[list["Stock"]] = relationship(back_populates="site")


class Stock(Base):
    __tablename__ = "stocks"

    id: Mapped[int] = mapped_column(primary_key=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("admin_zones.id"), index=True)
    resource_name: Mapped[str] = mapped_column(String(120), index=True)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    quantity: Mapped[float] = mapped_column(Numeric(16, 3))
    unit: Mapped[str | None] = mapped_column(String(40), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_sources.id"), nullable=True
    )
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    site: Mapped[Site | None] = relationship(back_populates="stocks")
    zone = relationship("AdminZone")


class Incident(Base):
    """Incidents strictement agrégés par zone : type + comptage + période.

    Volontairement sans coordonnées ni lien vers un site : un incident est
    une fréquence par zone, jamais un événement individuel géolocalisé.
    """

    __tablename__ = "incidents"
    __table_args__ = (CheckConstraint("count >= 1", name="ck_incident_count_min"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("admin_zones.id"), index=True)
    incident_type: Mapped[str] = mapped_column(String(120), index=True)
    count: Mapped[int] = mapped_column(Integer, default=1)
    severity: Mapped[str | None] = mapped_column(String(40), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_sources.id"), nullable=True
    )
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    zone = relationship("AdminZone")


class Indicator(Base):
    """Indicateur agrégé : nom + valeur + unité + période + zone (± site)."""

    __tablename__ = "indicators"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), index=True)
    value: Mapped[float] = mapped_column(Numeric(18, 4))
    unit: Mapped[str | None] = mapped_column(String(60), nullable=True)
    zone_id: Mapped[int] = mapped_column(ForeignKey("admin_zones.id"), index=True)
    site_id: Mapped[int | None] = mapped_column(ForeignKey("sites.id"), nullable=True)
    period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    period_end: Mapped[date | None] = mapped_column(Date, nullable=True)
    source_id: Mapped[int | None] = mapped_column(
        ForeignKey("data_sources.id"), nullable=True
    )
    properties: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    zone = relationship("AdminZone")
    site = relationship("Site")


class RagQuery(Base):
    """Journal des questions posées en langage naturel (démo + audit)."""

    __tablename__ = "rag_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    question: Mapped[str] = mapped_column(Text)
    plan: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    answer: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
