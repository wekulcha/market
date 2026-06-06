from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class SubscriptionLog(Base):
    __tablename__ = "subscription_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    restaurant_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("restaurant.id"), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric, nullable=True)
    start_dttm: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    end_dttm: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    restaurant = relationship("Restaurant", lazy="joined")
