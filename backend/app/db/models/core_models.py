"""Core schema draft, based on specification (section 12 mostly).

TODO
- Derived Multimodal Data: pose output, acoustic features, transcript, and optional
emotion/gesture results

- Agreement result

- Where exactly does timeline live?
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    JSON, CheckConstraint, DateTime, Enum, Float, ForeignKey, Index,
    Integer, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def new_id() -> str:
    return uuid.uuid4().hex


class Base(DeclarativeBase):
    pass


class UserRole(str, enum.Enum):
    annotator = "annotator"
    admin = "admin"         


class ProtocolGroup(str, enum.Enum):
    shared = "shared"            # annotated by everyone (agreement set)
    individual = "individual"    # each annotator's own set


class ProcessingStatus(str, enum.Enum):
    pending = "pending"
    running = "running"
    done = "done"
    failed = "failed"


class AnnotationStatus(str, enum.Enum):
    not_started = "not_started"
    started = "started"
    completed = "completed"


class TimeBasis(str, enum.Enum):
    frame = "frame"   # indexed by frame number (e.g. pose)
    time = "time"     # indexed by seconds (e.g. audio features, transcript)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), unique=True)
    display_name: Mapped[str] = mapped_column(String(180))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[UserRole] = mapped_column(Enum(UserRole), default=UserRole.annotator)


class Video(Base):
    __tablename__ = "videos"
    __table_args__ = (
        # Same file name requires an explicit skip / replace
        # "Version" creates a new row with version + 1.
        UniqueConstraint("canonical_filename", "version", name="uq_video_filename_version"),
    )

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    uploaded_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    canonical_filename: Mapped[str] = mapped_column(String(255))
    version: Mapped[int] = mapped_column(Integer, default=1)
    source_location: Mapped[str] = mapped_column(String(500))  # server-side only, never client-supplied
    file_hash: Mapped[str | None] = mapped_column(String(64))
    protocol_group: Mapped[ProtocolGroup] = mapped_column(
        Enum(ProtocolGroup), default=ProtocolGroup.individual
    )

    status: Mapped[ProcessingStatus] = mapped_column(
        Enum(ProcessingStatus), default=ProcessingStatus.pending
    )

    # Source metadata
    source_metadata: Mapped[dict | None] = mapped_column(JSON)  # codec, resolution, etc
    duration: Mapped[float | None] = mapped_column(Float)
    frame_count: Mapped[int | None] = mapped_column(Integer)
    start_time: Mapped[float | None] = mapped_column(Float)     # first frame timestamp, seconds
    end_time: Mapped[float | None] = mapped_column(Float)
    average_fps: Mapped[float | None] = mapped_column(Float)
    is_vfr: Mapped[bool | None] = mapped_column()
    timeline_path: Mapped[str | None] = mapped_column(String(500)) # assuming timeline is extracted and saved alongside video file
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    segments: Mapped[list["Segment"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )
    summaries: Mapped[list["VideoSummary"]] = relationship(
        back_populates="video", cascade="all, delete-orphan"
    )


class Segment(Base):
    __tablename__ = "segments"
    __table_args__ = (
        CheckConstraint("start_frame >= 0", name="ck_segment_start_nonneg"),
        CheckConstraint("end_frame > start_frame", name="ck_segment_frames_ordered"),
        CheckConstraint("end_time > start_time", name="ck_segment_times_ordered"),
        Index("ix_segments_video_annotator_round", "video_id", "annotator_id", "annotation_round"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    annotator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    annotation_round: Mapped[int] = mapped_column(Integer, default=1)

    # Canonical: frame range
    start_frame: Mapped[int] = mapped_column(Integer)
    end_frame: Mapped[int] = mapped_column(Integer)
    # Derived from the timeline
    start_time: Mapped[float] = mapped_column(Float)
    end_time: Mapped[float] = mapped_column(Float)

    # Two annotation fields
    video_description: Mapped[str | None] = mapped_column(Text)
    audio_description: Mapped[str | None] = mapped_column(Text)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)

    video: Mapped[Video] = relationship(back_populates="segments")

    # Raises error (StaleData) instead of silently overwriting another save.
    __mapper_args__ = {"version_id_col": row_version}


class VideoSummary(Base):
    """One whole-video summary per annotator, video and round."""
    __tablename__ = "video_summaries"
    __table_args__ = (
        UniqueConstraint("video_id", "annotator_id", "annotation_round",
                         name="uq_summary_video_annotator_round"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    annotator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    annotation_round: Mapped[int] = mapped_column(Integer, default=1)
    summary_text: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    row_version: Mapped[int] = mapped_column(Integer, nullable=False)

    video: Mapped[Video] = relationship(back_populates="summaries")

    __mapper_args__ = {"version_id_col": row_version}


class AnnotationProgress(Base):
    """Not started / started / completed per annotator and video (spec 11)."""
    __tablename__ = "annotation_progress"
    __table_args__ = (
        UniqueConstraint("video_id", "annotator_id", "annotation_round",
                         name="uq_progress_video_annotator_round"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    video_id: Mapped[str] = mapped_column(ForeignKey("videos.id", ondelete="CASCADE"))
    annotator_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    annotation_round: Mapped[int] = mapped_column(Integer, default=1)
    status: Mapped[AnnotationStatus] = mapped_column(
        Enum(AnnotationStatus), default=AnnotationStatus.not_started
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
