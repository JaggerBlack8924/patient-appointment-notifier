from datetime import UTC, datetime

from health_notify.appointment_notifier import AppointmentState, AppointmentUpdate, patient_event


def test_cancelled_notification_omits_schedule_and_internal_reason() -> None:
    update = AppointmentUpdate(
        appointment_id="appt_204",
        patient_id="patient_81",
        state=AppointmentState.CANCELLED,
        starts_at=datetime(2026, 9, 8, 9, 30, tzinfo=UTC),
        internal_reason="clinician coverage change",
    )

    event, data = patient_event(update)

    assert event == "appointment.cancelled"
    assert data == {"appointment_id": "appt_204", "state": "cancelled"}
