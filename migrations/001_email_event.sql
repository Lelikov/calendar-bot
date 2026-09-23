-- Delivery statuses of the emails we send, tied to a booking through the metadata
-- Unisender Go echoes back in its webhooks.
--
-- Applied by hand: the service owns this table, but the database is Cal.com's and the
-- project has no migration tool.

CREATE TABLE IF NOT EXISTS email_event
(
    id                   bigserial PRIMARY KEY,
    booking_uid          text        NOT NULL,
    trigger_event        text,
    role                 text,
    job_id               text        NOT NULL,
    email                text        NOT NULL,
    status               text        NOT NULL,
    event_time           timestamptz NOT NULL,
    delivery_status      text,
    destination_response text,
    created_at           timestamptz NOT NULL DEFAULT now()
);

-- A webhook call is retried until it is answered with 200, so the same event arrives
-- more than once. This index is what makes the insert idempotent.
CREATE UNIQUE INDEX IF NOT EXISTS email_event_unique_idx
    ON email_event (job_id, email, status, event_time);

CREATE INDEX IF NOT EXISTS email_event_booking_uid_idx
    ON email_event (booking_uid);
