from datetime import datetime
from enum import StrEnum
from collections.abc import Awaitable, Callable
from typing import Any, Protocol

from pydantic import BaseModel, Field


class RealtimePublisher(Protocol):
    create_channel: Callable[[str, str], Awaitable[dict[str, Any]]]
    publish: Callable[[str, str, dict[str, Any], str, str], Awaitable[dict[str, Any]]]


class AppointmentState(StrEnum):
    CONFIRMED = "confirmed"
    RESCHEDULED = "rescheduled"
    CANCELLED = "cancelled"


class AppointmentUpdate(BaseModel):
    appointment_id: str = Field(min_length=1)
    patient_id: str = Field(min_length=1)
    state: AppointmentState
    starts_at: datetime | None = None
    internal_reason: str | None = None


class NotificationResult(BaseModel):
    channel: str
    event: str
    delivered_state: AppointmentState


def patient_event(update: AppointmentUpdate) -> tuple[str, dict[str, Any]]:
    event = f"appointment.{update.state.value}"
    data: dict[str, Any] = {
        "appointment_id": update.appointment_id,
        "state": update.state.value,
    }
    if update.state != AppointmentState.CANCELLED and update.starts_at is not None:
        data["starts_at"] = update.starts_at.isoformat()
    return event, data


async def notify_patient(
    realtime: RealtimePublisher, update: AppointmentUpdate, request_id: str
) -> NotificationResult:
    channel = f"patient:{update.patient_id}:appointments"
    event, data = patient_event(update)
    await realtime.create_channel(channel, f"{request_id}:channel")
    await realtime.publish(channel, event, data, update.patient_id, f"{request_id}:publish")
    return NotificationResult(channel=channel, event=event, delivered_state=update.state)
