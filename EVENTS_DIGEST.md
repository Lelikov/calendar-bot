# Events Digest

Сводка актуального payload для всех событий.

## Общий контракт

- `booking_uid`: `str` (всегда добавляется адаптером)
- `event`: `EventType`
- `data`: `dict[str, Any] | None`

### Общий формат получателей

Во всех событиях, где раньше передавался `email`, теперь используется:

`users: list[UserRef]`, где `UserRef`:
- `email: str`
- `role: str`
- `time_zone: str` — добавляется для `booking.created` и `booking.reassigned`

---

## booking.reminder_sent

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "client"}]` |

## booking.created

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "organizer", time_zone: str} \| {email: str, role: "client", time_zone: str}]` |
| start_time | `datetime` |
| end_time | `datetime` |

## booking.rescheduled

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| start_time | `datetime` |
| end_time | `datetime` |
| previous_booking.start_time | `datetime \| None` |

## booking.reassigned

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "previous_organizer", time_zone: str} \| {email: str, role: "organizer", time_zone: str} \| {email: str, role: "client", time_zone: str}]` |

## booking.cancelled

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| cancellation_reason | `str \| None` |

## chat.created

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| organizer_id | `str` |
| client_id | `str` |

## chat.deleted

| Поле | Тип |
|---|---|
| booking_uid | `str` |

## chat.message_sent

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| user_id | `str` |

## meeting.url_created

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "client" \| "organizer"}]` |
| meeting_url | `str` |

## meeting.url_deleted

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "client" \| "organizer"}]` |

## notification.telegram_sent

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "organizer"}]` |
| trigger_event | `TriggerEvent` |

## notification.email_sent

### Базовый кейс

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "organizer" \| "client"}]` |
| job_id | `str \| None` |
| trigger_event | `TriggerEvent` |

### Кейс отклонённого бронирования (`notify_client_booking_rejected`)

| Поле | Тип |
|---|---|
| booking_uid | `str` |
| users | `list[{email: str, role: "client"}]` |
| job_id | `str \| None` |
| available_from | `datetime` |
| has_active_booking | `bool` |
| active_booking_start | `datetime \| None` |
| previous_meeting_dates | `list[datetime]` |
| rejection_reasons | `list[str]` |
| trigger_event | `TriggerEvent` (`BOOKING_REJECTED`) |
