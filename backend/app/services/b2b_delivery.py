from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


class DeliveryProviderError(ValueError):
    pass


@dataclass(frozen=True)
class DeliveryRequest:
    order_number: str
    pickup_address: str
    delivery_address: str
    courier_name: str
    courier_contact: str | None = None
    pickup_window: str | None = None
    delivery_window: str | None = None
    cost_kopecks: int | None = None


@dataclass(frozen=True)
class DeliveryAssignment:
    provider: str
    status: str
    external_delivery_id: str | None
    courier_name: str
    courier_contact: str | None
    cost_kopecks: int | None
    internal_notes: str | None


class DeliveryProvider(ABC):
    name: str

    @abstractmethod
    async def assign(self, request: DeliveryRequest) -> DeliveryAssignment:
        raise NotImplementedError


class ManualDeliveryProvider(DeliveryProvider):
    """Manual dispatcher used by the MVP and replaceable by a courier adapter."""

    name = "MANUAL"

    async def assign(self, request: DeliveryRequest) -> DeliveryAssignment:
        if not request.courier_name.strip():
            raise DeliveryProviderError("courier name is required")
        if not request.pickup_address.strip() or not request.delivery_address.strip():
            raise DeliveryProviderError("pickup and delivery addresses are required")
        notes = "; ".join(
            item
            for item in (request.pickup_window, request.delivery_window)
            if item
        ) or None
        return DeliveryAssignment(
            provider=self.name,
            status="ASSIGNED",
            external_delivery_id=None,
            courier_name=request.courier_name.strip(),
            courier_contact=request.courier_contact,
            cost_kopecks=request.cost_kopecks,
            internal_notes=notes,
        )


def get_delivery_provider(name: str) -> DeliveryProvider:
    provider = name.strip().lower()
    if provider == "manual":
        return ManualDeliveryProvider()
    raise DeliveryProviderError(f"delivery provider is not configured: {provider}")
