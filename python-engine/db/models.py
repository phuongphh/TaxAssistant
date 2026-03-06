"""
SQLAlchemy models for Tax Assistant persistent data.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Index, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TaxQuery(Base):
    """Log of all tax queries processed by the engine."""

    __tablename__ = "tax_queries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(100), index=True)
    channel: Mapped[str] = mapped_column(String(20))
    customer_type: Mapped[str] = mapped_column(String(20), default="unknown")

    query_text: Mapped[str] = mapped_column(Text)
    response_text: Mapped[str] = mapped_column(Text)
    tax_category: Mapped[str | None] = mapped_column(String(50), nullable=True)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)

    intent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSONB, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TaxRegulation(Base):
    """Vietnamese tax regulation documents for RAG retrieval."""

    __tablename__ = "tax_regulations"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_number: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    title: Mapped[str] = mapped_column(Text)
    content: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(50), index=True)
    effective_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    expiry_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    embedding_id: Mapped[str | None] = mapped_column(String(100), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProcessedDocument(Base):
    """Records of documents (invoices, receipts) processed by the engine."""

    __tablename__ = "processed_documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id: Mapped[str] = mapped_column(String(100), index=True)
    user_id: Mapped[str] = mapped_column(String(100))
    document_type: Mapped[str] = mapped_column(String(50))
    file_url: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(String(50))

    extracted_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Customer(Base):
    """Persistent customer profile - long-term memory for the bot."""

    __tablename__ = "customers"
    __table_args__ = (
        UniqueConstraint("channel", "channel_user_id", name="uq_customers_channel_user"),
        Index("idx_customers_type", "customer_type"),
        Index("idx_customers_last_active", "last_active_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)
    channel_user_id: Mapped[str] = mapped_column(String(100), nullable=False)

    # Telegram/platform identity fields (populated from first message)
    username: Mapped[str | None] = mapped_column(String(100), nullable=True)
    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    display_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    # Business info (collected during onboarding)
    customer_type: Mapped[str] = mapped_column(String(20), default="unknown")
    business_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tax_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    industry: Mapped[str | None] = mapped_column(String(100), nullable=True)
    province: Mapped[str | None] = mapped_column(String(100), nullable=True)
    annual_revenue_range: Mapped[str | None] = mapped_column(String(20), nullable=True)
    employee_count_range: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Onboarding state
    onboarding_step: Mapped[str] = mapped_column(String(30), default="new")

    # Flexible JSONB fields for extensibility
    preferences: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    tax_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    notes: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    last_active_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    support_cases: Mapped[list["SupportCase"]] = relationship(back_populates="customer")
    conversation_summaries: Mapped[list["ConversationSummary"]] = relationship(back_populates="customer")


class SupportCase(Base):
    """Tracks ongoing support cases / service requests for a customer."""

    __tablename__ = "support_cases"
    __table_args__ = (
        Index("idx_cases_customer", "customer_id"),
        Index("idx_cases_status", "status", postgresql_where=text("status != 'completed'")),
        Index("idx_cases_service_type", "service_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )

    service_type: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)

    status: Mapped[str] = mapped_column(String(20), default="open")
    current_step: Mapped[str] = mapped_column(String(50), default="step_1")

    steps_data: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)
    context: Mapped[dict | None] = mapped_column(JSONB, nullable=True, default=dict)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="support_cases")


class ConversationSummary(Base):
    """LLM-generated summaries of past conversations for long-term memory."""

    __tablename__ = "conversation_summaries"
    __table_args__ = (
        Index("idx_summaries_customer", "customer_id"),
        Index("idx_summaries_date", "session_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    customer_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False
    )
    support_case_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_cases.id", ondelete="SET NULL"), nullable=True
    )

    session_date: Mapped[date] = mapped_column(Date, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    key_topics: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)
    action_items: Mapped[list | None] = mapped_column(JSONB, nullable=True, default=list)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    # Relationships
    customer: Mapped["Customer"] = relationship(back_populates="conversation_summaries")
