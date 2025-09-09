-- ChittyChattyChat Database Schema
-- Version 1.0

-- Create extensions
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Rooms table
CREATE TABLE IF NOT EXISTS rooms (
  id BIGSERIAL PRIMARY KEY,
  room_id CHAR(4) UNIQUE NOT NULL,
  status TEXT NOT NULL CHECK (status IN ('pending','active','locked','closed','archived')) DEFAULT 'pending',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  accepted_at TIMESTAMPTZ,
  expires_at TIMESTAMPTZ,
  closed_at TIMESTAMPTZ,
  archive_key TEXT
);

-- Room Keys (envelope encrypted)
CREATE TABLE IF NOT EXISTS room_keys (
  room_id CHAR(4) PRIMARY KEY REFERENCES rooms(room_id) ON DELETE CASCADE,
  room_key_enc BYTEA NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Participants
CREATE TABLE IF NOT EXISTS participants (
  id BIGSERIAL PRIMARY KEY,
  room_id CHAR(4) REFERENCES rooms(room_id) ON DELETE CASCADE,
  role TEXT NOT NULL CHECK (role IN ('host','guest')),
  device_id UUID NOT NULL,
  display_name TEXT,
  ip_address INET,
  joined_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE(room_id, role)
);

-- Messages (ciphertext)
CREATE TABLE IF NOT EXISTS messages (
  id BIGSERIAL PRIMARY KEY,
  room_id CHAR(4) REFERENCES rooms(room_id) ON DELETE CASCADE,
  participant_id BIGINT REFERENCES participants(id) ON DELETE SET NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  body_ct BYTEA NOT NULL, -- ciphertext
  nonce BYTEA NOT NULL,
  tag BYTEA NOT NULL,
  msg_type TEXT NOT NULL CHECK (msg_type IN ('text','image')) DEFAULT 'text',
  ip_address INET
);

-- Attachments (MinIO)
CREATE TABLE IF NOT EXISTS attachments (
  id BIGSERIAL PRIMARY KEY,
  room_id CHAR(4) REFERENCES rooms(room_id) ON DELETE CASCADE,
  message_id BIGINT REFERENCES messages(id) ON DELETE CASCADE,
  object_key TEXT NOT NULL,
  mime_type TEXT NOT NULL,
  size_bytes BIGINT NOT NULL,
  available BOOLEAN NOT NULL DEFAULT FALSE,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Indexes for performance
CREATE INDEX IF NOT EXISTS idx_rooms_status ON rooms(status);
CREATE INDEX IF NOT EXISTS idx_rooms_expires ON rooms(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_participants_room ON participants(room_id);
CREATE INDEX IF NOT EXISTS idx_participants_device ON participants(device_id);
CREATE INDEX IF NOT EXISTS idx_messages_room_time ON messages(room_id, created_at);
CREATE INDEX IF NOT EXISTS idx_attachments_room ON attachments(room_id);
CREATE INDEX IF NOT EXISTS idx_attachments_message ON attachments(message_id);

-- Insert initial data or setup
COMMENT ON TABLE rooms IS 'Chat rooms with 4-character IDs';
COMMENT ON TABLE room_keys IS 'Encrypted room keys for hybrid encryption';
COMMENT ON TABLE participants IS 'Room participants with device binding';
COMMENT ON TABLE messages IS 'Encrypted messages';
COMMENT ON TABLE attachments IS 'File attachments stored in MinIO';