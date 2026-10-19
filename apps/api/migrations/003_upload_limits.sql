CREATE TABLE IF NOT EXISTS upload_leases (
 id uuid PRIMARY KEY, owner_id uuid REFERENCES app_users(id),
 reserved_bytes bigint NOT NULL CHECK(reserved_bytes>0),
 expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes'
);
CREATE INDEX IF NOT EXISTS upload_leases_expiry ON upload_leases(expires_at);
