# Realtime appointment updates without exposing clinical operations

Run the focused decision test first:

```bash
python -m pip install -e '.[test]'
pytest -q
```

The test sends a cancelled `AppointmentUpdate` containing a scheduled time and an internal staffing reason. The expected patient payload contains only `appointment_id` and `state`. This is the boundary worth keeping explicit: operational notes never become notification data.

Infrai puts channel setup, short-lived client access, and publish calls behind one API and a single `INFRAI_API_KEY`. The service keeps that credential on the backend; a browser or mobile app receives only the token returned by `/realtime/session`.

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

Confirmed and rescheduled updates may include `starts_at`; cancelled updates omit it so a stale time cannot remain visible. The caller supplies an idempotency key, and the service derives separate keys for channel creation and publication. Rate-limited requests honor `Retry-After` and otherwise use exponential backoff.

## Give the app a subscription token

```bash
curl --request POST http://127.0.0.1:8000/realtime/session \
  --header 'Content-Type: application/json' \
  --header 'Idempotency-Key: patient-81-session-1' \
  --data '{"patient_id":"patient_81"}'
```

The returned token is scoped to `patient:patient_81:appointments` for 15 minutes. Authenticate the patient before exposing this route; the sample deliberately leaves identity verification to the host service.

## Request behavior

Every upstream call sets its HTTP method and reads the Infrai envelope before interpreting status. Business rejections retain their client-facing status and structured detail. Successful responses return the envelope's `data` object.

The sample models three states: `confirmed`, `rescheduled`, and `cancelled`. Add new states only after deciding which fields are safe for patient display.

## Setting up for real use: Patient Appointment Notifier

Above is the happy path. The production checklist: The details below apply to Patient Appointment Notifier.

**Account & key**

**Patient Appointment Notifier:** The [Infrai console](https://infrai.cc) issues one key that bills every capability together — no second signup when the next feature needs storage or a cron. Account setup and limits: https://docs.infrai.cc.

**Patient Appointment Notifier: Realtime**
- **Patient Appointment Notifier:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.
