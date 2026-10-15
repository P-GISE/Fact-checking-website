CREATE TABLE IF NOT EXISTS media (
 id uuid PRIMARY KEY, path text NOT NULL UNIQUE, original_name text NOT NULL,
 bytes bigint NOT NULL CHECK (bytes>0 AND bytes<=104857600), mime text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours'
);
CREATE TABLE IF NOT EXISTS jobs (
 id uuid PRIMARY KEY, media_id uuid NOT NULL UNIQUE REFERENCES media(id),
 status text NOT NULL DEFAULT 'queued' CHECK(status IN ('queued','validating','transcribing','extracting','retrieving','validating_evidence','completed','failed','cancelled','deleted')),
 version integer NOT NULL DEFAULT 0, consent boolean NOT NULL CHECK(consent),
 created_at timestamptz NOT NULL DEFAULT now(), expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours',
 started_at timestamptz, deleted_at timestamptz, error jsonb, result jsonb,
 idempotency_key text UNIQUE
);
CREATE TABLE IF NOT EXISTS claims (id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(id) ON DELETE CASCADE, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS evidence (id uuid PRIMARY KEY, claim_id uuid NOT NULL REFERENCES claims(id) ON DELETE CASCADE, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS checks (id uuid PRIMARY KEY, evidence_id uuid NOT NULL REFERENCES evidence(id) ON DELETE CASCADE, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS verdicts (claim_id uuid PRIMARY KEY REFERENCES claims(id) ON DELETE CASCADE, data jsonb NOT NULL);
CREATE TABLE IF NOT EXISTS usage_reservations (id uuid PRIMARY KEY, job_id uuid NOT NULL REFERENCES jobs(id), month text NOT NULL, reserved_micros bigint NOT NULL CHECK(reserved_micros>=0), actual_micros bigint CHECK(actual_micros>=0));
CREATE INDEX IF NOT EXISTS jobs_pending ON jobs(created_at) WHERE status='queued';
