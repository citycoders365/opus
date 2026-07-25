-- ============================================================
-- TravelloBus v2 — COMPLETE SETUP (run in Supabase SQL Editor)
-- This handles: RLS policies + data seeding
-- ============================================================

-- Disable RLS on all tables (safe for PoC — no user-facing auth)
ALTER TABLE route_stops ENABLE ROW LEVEL SECURITY;
ALTER TABLE ticket_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE gps_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE live_bus_state ENABLE ROW LEVEL SECURITY;

-- Create permissive policies for anon access (required for PoC)
CREATE POLICY "Allow all on route_stops" ON route_stops FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on ticket_events" ON ticket_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on gps_events" ON gps_events FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all on live_bus_state" ON live_bus_state FOR ALL USING (true) WITH CHECK (true);

-- Seed route stops (Vijayawada → Guntur corridor with real GPS)
INSERT INTO route_stops (route_id, stop_index, stop_name, lat, lng) VALUES
    ('vja-gnt', 0, 'VIJAYAWADA PNBS', 16.5089, 80.6156),
    ('vja-gnt', 1, 'TADEPALLI',       16.4803, 80.6188),
    ('vja-gnt', 2, 'MANGALAGIRI',     16.4122, 80.5584),
    ('vja-gnt', 3, 'NAMBURU',         16.3626, 80.5000),
    ('vja-gnt', 4, 'PEDDAKAKANI',     16.3400, 80.4908),
    ('vja-gnt', 5, 'GUNTUR RTC',      16.2956, 80.4561)
ON CONFLICT (route_id, stop_index) DO NOTHING;

-- Seed all buses (60-seat capacity)
INSERT INTO live_bus_state (bus_id, route_id, total_capacity, current_stop_index) VALUES
    ('AP-16-1234', 'vja-gnt', 60, 0),
    ('AP-16-4023', 'vja-gnt', 60, 0),
    ('AP-16-4024', 'vja-gnt', 60, 0),
    ('AP-16-4025', 'vja-gnt', 60, 0),
    ('AP-16-4026', 'vja-gnt', 60, 0),
    ('AP-16-5001', 'gnt-vja', 60, 0),
    ('AP-16-5002', 'gnt-vja', 60, 0)
ON CONFLICT (bus_id) DO NOTHING;

-- Create indexes
CREATE INDEX IF NOT EXISTS idx_ticket_events_bus ON ticket_events(bus_id);
CREATE INDEX IF NOT EXISTS idx_gps_events_bus ON gps_events(bus_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_route_stops_route ON route_stops(route_id);
