from sqlalchemy import Column, String, DateTime, func
from app.database import Base


class ProcessedEvent(Base):
    """Kafka events already applied, so a redelivered event isn't applied twice."""
    __tablename__ = "processed_events"

    event_key = Column(String, primary_key=True)  # e.g. "ORD-20260926-D3A31180_ORDER_CANCELLED"
    processed_at = Column(DateTime(timezone=True), server_default=func.now())
