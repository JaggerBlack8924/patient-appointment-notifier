import os
from typing import Annotated

from fastapi import Depends, FastAPI, Header
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from .appointment_notifier import AppointmentUpdate, NotificationResult, notify_patient
from .infrai_realtime import InfraiError, InfraiRealtime

app = FastAPI(title="Patient appointment notifier")


def realtime_client() -> InfraiRealtime:
    api_key = os.environ["INFRAI_API_KEY"]
    return InfraiRealtime(api_key)


class SessionRequest(BaseModel):
    patient_id: str = Field(min_length=1)


@app.exception_handler(InfraiError)
async def infrai_error_handler(_request: object, exc: InfraiError) -> JSONResponse:
    status = exc.status_code if 400 <= exc.status_code < 500 else 502
    return JSONResponse(status_code=status, content={"detail": {"code": exc.code, "error": exc.detail}})


@app.post("/appointments/notify", response_model=NotificationResult)
async def publish_update(
    update: AppointmentUpdate,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    realtime: Annotated[InfraiRealtime, Depends(realtime_client)],
) -> NotificationResult:
    try:
        return await notify_patient(realtime, update, idempotency_key)
    finally:
        await realtime.close()


@app.post("/realtime/session")
async def create_session(
    session: SessionRequest,
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key")],
    realtime: Annotated[InfraiRealtime, Depends(realtime_client)],
) -> dict[str, object]:
    channel = f"patient:{session.patient_id}:appointments"
    try:
        await realtime.create_channel(channel, f"{idempotency_key}:channel")
        token = await realtime.issue_token(session.patient_id, channel, f"{idempotency_key}:token")
        return {"channel": channel, "token": token}
    finally:
        await realtime.close()
