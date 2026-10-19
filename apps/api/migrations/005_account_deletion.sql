ALTER TABLE app_users ADD COLUMN IF NOT EXISTS deleted_at timestamptz;
