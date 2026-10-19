CREATE TABLE IF NOT EXISTS app_users (
 id uuid PRIMARY KEY, username text NOT NULL UNIQUE, password_hash text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS app_sessions (
 token_hash text PRIMARY KEY, user_id uuid NOT NULL REFERENCES app_users(id) ON DELETE CASCADE,
 expires_at timestamptz NOT NULL DEFAULT now()+interval '24 hours'
);
CREATE INDEX IF NOT EXISTS app_sessions_expiry ON app_sessions(expires_at);
ALTER TABLE media ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES app_users(id);
ALTER TABLE jobs ADD COLUMN IF NOT EXISTS owner_id uuid REFERENCES app_users(id);
ALTER TABLE jobs DROP CONSTRAINT IF EXISTS jobs_idempotency_key_key;
CREATE UNIQUE INDEX IF NOT EXISTS jobs_owner_idempotency ON jobs(owner_id,idempotency_key) WHERE owner_id IS NOT NULL;
CREATE UNIQUE INDEX IF NOT EXISTS jobs_local_idempotency ON jobs(idempotency_key) WHERE owner_id IS NULL;
