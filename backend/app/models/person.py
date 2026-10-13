from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin, UTCDateTime, UUIDPrimaryKeyMixin, str_enum, utcnow
from app.models.enums import EmbeddingSource, PersonRole


class Person(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "persons"

    display_name: Mapped[str] = mapped_column(String(80))
    role: Mapped[PersonRole] = mapped_column(str_enum(PersonRole), index=True)
    notes: Mapped[str] = mapped_column(Text, default="")
    sightings_count: Mapped[int] = mapped_column(Integer, default=0)
    first_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)
    last_seen_at: Mapped[datetime | None] = mapped_column(UTCDateTime, nullable=True)

    embeddings: Mapped[list[FaceEmbedding]] = relationship(
        back_populates="person", cascade="all, delete-orphan", passive_deletes=True
    )


class FaceEmbedding(UUIDPrimaryKeyMixin, Base):
    """A face signature (vector). Photos themselves are never stored (privacy by design)."""

    __tablename__ = "face_embeddings"

    person_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("persons.id", ondelete="CASCADE"), index=True
    )
    vector: Mapped[bytes] = mapped_column(LargeBinary)
    dim: Mapped[int] = mapped_column(Integer)
    model_name: Mapped[str] = mapped_column(String(64))
    source: Mapped[EmbeddingSource] = mapped_column(str_enum(EmbeddingSource))
    created_at: Mapped[datetime] = mapped_column(UTCDateTime, default=utcnow)

    person: Mapped[Person] = relationship(back_populates="embeddings")
