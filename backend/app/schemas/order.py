from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class OrderDto(BaseModel):
    id: int | None = None
    status: str | None = None
    userId: int | None = None
    deliveryAddress: str | None = None
    tableNumber: str | None = None
    comment: str | None = None
    restaurantId: int | None = None
    createdAt: datetime | None = None
    updatedAt: datetime | None = None
    courierId: int | None = None
    orderType: str | None = None
    itemsTotal: Decimal | None = None
    deliveryFee: Decimal | None = None
    serviceFee: Decimal | None = None
    total: Decimal | None = None
    isPaid: bool | None = None
    reviewRating: int | None = None
    reviewText: str | None = None
    reviewCreatedAt: datetime | None = None


class OrderCheckoutLine(BaseModel):
    mealId: int
    quantity: int
    unitPrice: Decimal | None = None


class OrderCheckoutRequest(BaseModel):
    restaurantId: int
    deliveryAddress: str | None = None
    tableNumber: str | None = None
    comment: str | None = None
    orderType: str
    itemsTotal: Decimal | None = None
    deliveryFee: Decimal | None = None
    serviceFee: Decimal | None = None
    total: Decimal | None = None
    items: list[OrderCheckoutLine]


class OrderStatusPatchDto(BaseModel):
    status: str


class OrderPaidPatchDto(BaseModel):
    isPaid: bool


class OrderReviewPatchDto(BaseModel):
    rating: int
    text: str | None = None


class DailyOrderPositionSummaryDto(BaseModel):
    mealName: str
    quantity: int
    totalPrice: Decimal


class DailyOrderTypeSummaryDto(BaseModel):
    orderType: str
    ordersCount: int
    revenue: Decimal
    paidOrdersCount: int
    unpaidOrdersCount: int
    paidRevenue: Decimal
    unpaidRevenue: Decimal
    cancelledOrdersCount: int
    cancelledRevenue: Decimal
    avgCheck: Decimal
    itemsTotal: Decimal
    deliveryFeeTotal: Decimal
    serviceFeeTotal: Decimal
    courierAssignedOrdersCount: int
    positions: list[DailyOrderPositionSummaryDto] = []


class DailyRestaurantSummaryDto(BaseModel):
    restaurantId: int
    restaurantName: str
    totalOrdersCount: int
    totalRevenue: Decimal
    paidOrdersCount: int
    unpaidOrdersCount: int
    paidRevenue: Decimal
    unpaidRevenue: Decimal
    cancelledOrdersCount: int
    cancelledRevenue: Decimal
    avgCheck: Decimal
    dineIn: DailyOrderTypeSummaryDto
    delivery: DailyOrderTypeSummaryDto


class DailyStaffSummaryDto(BaseModel):
    reportDate: str
    timezone: str
    generatedAt: datetime
    restaurants: list[DailyRestaurantSummaryDto] = []
