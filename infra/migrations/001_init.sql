CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE users (
  id uuid PRIMARY KEY,
  name text,
  embedding jsonb,
  enrolled_at timestamptz
);

CREATE TABLE logs (
  id bigserial PRIMARY KEY,
  user_id uuid NULL,
  name text NULL,
  camera_id text,
  matched boolean,
  score numeric,
  ts timestamptz,
  raw_image bytea
);

CREATE TABLE events_realtime (
  id bigserial PRIMARY KEY,
  payload jsonb,
  created_at timestamptz DEFAULT now()
);
