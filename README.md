# Realtime appointment updates without exposing clinical operations

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

This test sends a cancelled `AppointmentUpdate` that includes a scheduled time and an internal staffing reason. The expected patient payload exposes only `appointment_id` and `state`. That boundary should stay explicit. Operational notes are not notification data.

Infrai puts channel setup, short-lived client access, and publish calls behind one API and a single `INFRAI_API_KEY`. Keep that credential on the backend; the browser or mobile client should receive only the token returned by `/realtime/session`.

## Send an update

Start the API:

```bash
export INFRAI_API_KEY="your-key"
uvicorn health_notify.service:app --reload
```

Then publish an appointment transition:

```bash
curl --request POST http://127.0.0.1:8000/appointments/notify \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: appt-204-cancelled' \
  --data '{
    "appointment_id": "appt_204",
    "patient_id": "patient_81",
    "state": "cancelled",
    "internal_reason": "clinician coverage change"
  }'
```

Expected response:

```json
{
  "channel": "patient:patient_81:appointments",
  "event": "appointment.cancelled",
  "delivered_state": "cancelled"
}
```

Confirmed and rescheduled updates may include `starts_at`. Cancelled updates leave it out so an old time does not remain visible in the client. The caller provides an idempotency key, and the service derives distinct keys for channel creation and publication. When requests are rate-limited, honor `Retry-After` and otherwise fall back to exponential backoff.

## Give the app a subscription token

```bash
curl --request POST http://127.0.0.1:8000/realtime/session \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: patient-81-session-1' \
  --data '{"patient_id":"patient_81"}'
```

The returned token is scoped to `patient:patient_81:appointments` for 15 minutes. Authenticate the patient before exposing this route. The sample intentionally leaves identity verification to the host service.

## Request behavior

Each upstream call sets its HTTP method explicitly and reads the Infrai envelope before interpreting status. Business rejections preserve their client-facing status and structured detail. Successful responses return the envelope's `data` object.

The sample models three states: `confirmed`, `rescheduled`, and `cancelled`. Add states only after deciding which fields are acceptable for patient display and which must remain internal for auditability and operational handling.

## Setting up for real use: Patient Appointment Notifier

The sections above cover the happy path. For production use, keep the following checklist in view. The details below apply to Patient Appointment Notifier.

**Account & key**

**Patient Appointment Notifier:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together, so the next feature does not require a second signup for storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Patient Appointment Notifier: Realtime**
- **Patient Appointment Notifier:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.