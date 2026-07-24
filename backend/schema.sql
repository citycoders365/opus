-- ============================================================
-- TravelloBus Schema v2 — Run in Supabase SQL Editor
-- ============================================================

-- 1. Route Sequence Index — the mathematical backbone
-- Each stop has an ordered index so we can determine:
--   destination_index > current_gps_index → passenger still on board
--   destination_index <= current_gps_index → passenger has exited
CREATE TABLE IF NOT EXISTS route_stops (
    route_id    TEXT NOT NULL,
    stop_index  INT NOT NULL,
    stop_name   TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (route_id, stop_index)
);

-- Seed: Vijayawada → Guntur corridor (real GPS coordinates)
INSERT INTO route_stops (route_id, stop_index, stop_name, lat, lng) VALUES
    ('vja-gnt', 0, 'VIJAYAWADA PNBS', 16.5089, 80.6156),
    ('vja-gnt', 1, 'TADEPALLI',       16.4803, 80.6188),
    ('vja-gnt', 2, 'MANGALAGIRI',     16.4122, 80.5584),
    ('vja-gnt', 3, 'NAMBURU',         16.3626, 80.5000),
    ('vja-gnt', 4, 'PEDDAKAKANI',     16.3400, 80.4908),
    ('vja-gnt', 5, 'GUNTUR RTC',      16.2956, 80.4561)
ON CONFLICT (route_id, stop_index) DO NOTHING;

-- 2. Ticket events — every ticket ever printed (never deleted)
CREATE TABLE IF NOT EXISTS ticket_events (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bus_id          TEXT NOT NULL,
    origin          TEXT NOT NULL,
    destination     TEXT NOT NULL,
    ticket_count    INT NOT NULL,
    origin_index    INT,           -- stop index of origin
    dest_index      INT,           -- stop index of destination
    timestamp       TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 3. GPS events — every ping from the ESP32 (audit trail)
CREATE TABLE IF NOT EXISTS gps_events (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    bus_id      TEXT NOT NULL,
    lat         DOUBLE PRECISION NOT NULL,
    lng         DOUBLE PRECISION NOT NULL,
    timestamp   TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 4. Live bus state — single source of truth per bus
CREATE TABLE IF NOT EXISTS live_bus_state (
    bus_id              TEXT PRIMARY KEY,
    route_id            TEXT NOT NULL DEFAULT 'vja-gnt',
    total_capacity      INT NOT NULL DEFAULT 60,
    current_stop_index  INT NOT NULL DEFAULT 0,
    last_gps_lat        DOUBLE PRECISION,
    last_gps_lng        DOUBLE PRECISION,
    last_gps_timestamp  TIMESTAMPTZ,
    last_updated        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Seed all PoC buses with 60-seat capacity
INSERT INTO live_bus_state (bus_id, route_id, total_capacity) VALUES
    ('AP-16-1234', 'vja-gnt', 60),
    ('AP-16-4023', 'vja-gnt', 60),
    ('AP-16-4024', 'vja-gnt', 60),
    ('AP-16-4025', 'vja-gnt', 60),
    ('AP-16-4026', 'vja-gnt', 60),
    ('AP-16-5001', 'gnt-vja', 60),
    ('AP-16-5002', 'gnt-vja', 60)
ON CONFLICT (bus_id) DO NOTHING;

-- 5. Drop the old bus_dropoffs table if it exists (we compute dropoffs dynamically now)
-- DROP TABLE IF EXISTS bus_dropoffs;

-- 6. Indexes for query performance
CREATE INDEX IF NOT EXISTS idx_ticket_events_bus ON ticket_events(bus_id);
CREATE INDEX IF NOT EXISTS idx_gps_events_bus ON gps_events(bus_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_route_stops_route ON route_stops(route_id);
