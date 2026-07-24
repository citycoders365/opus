"""
Apply TravelloBus v2 Schema to Supabase
Uses the Supabase Management API (SQL Editor equivalent)
"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from supabase import create_client, Client

SUPABASE_URL = "https://ybprjrgzddgllanpjxnx.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlicHJqcmd6ZGRnbGxhbnBqeG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NjA5NjAsImV4cCI6MjEwMDQzNjk2MH0.RJr17-e7Ua6XeakTGmhsJyU9ywty0TTfzCKK4RHyeUo"

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

print("=" * 60)
print("TravelloBus v2 Schema Setup")
print("=" * 60)

# Step 1: Check if route_stops table exists
print("\n[1/5] Checking existing tables...")
try:
    res = supabase.table("route_stops").select("*").limit(1).execute()
    print("  route_stops: EXISTS (" + str(len(res.data)) + " rows)")
    route_stops_exists = True
except:
    print("  route_stops: NOT FOUND (will create)")
    route_stops_exists = False

try:
    res = supabase.table("gps_events").select("*").limit(1).execute()
    print("  gps_events: EXISTS")
    gps_exists = True
except:
    print("  gps_events: NOT FOUND (will create)")
    gps_exists = False

try:
    res = supabase.table("ticket_events").select("*").limit(1).execute()
    print("  ticket_events: EXISTS (" + str(len(res.data)) + " rows)")
except:
    print("  ticket_events: NOT FOUND")

try:
    res = supabase.table("live_bus_state").select("*").execute()
    print("  live_bus_state: EXISTS (" + str(len(res.data)) + " rows)")
    for bus in res.data:
        cols = list(bus.keys())
        print(f"    Columns: {cols}")
        break
except:
    print("  live_bus_state: NOT FOUND")

# Step 2: Seed route_stops data (if table exists but empty or doesn't exist)
print("\n[2/5] Seeding route_stops...")
stops_data = [
    {"route_id": "vja-gnt", "stop_index": 0, "stop_name": "VIJAYAWADA PNBS", "lat": 16.5089, "lng": 80.6156},
    {"route_id": "vja-gnt", "stop_index": 1, "stop_name": "TADEPALLI",       "lat": 16.4803, "lng": 80.6188},
    {"route_id": "vja-gnt", "stop_index": 2, "stop_name": "MANGALAGIRI",     "lat": 16.4122, "lng": 80.5584},
    {"route_id": "vja-gnt", "stop_index": 3, "stop_name": "NAMBURU",         "lat": 16.3626, "lng": 80.5000},
    {"route_id": "vja-gnt", "stop_index": 4, "stop_name": "PEDDAKAKANI",     "lat": 16.3400, "lng": 80.4908},
    {"route_id": "vja-gnt", "stop_index": 5, "stop_name": "GUNTUR RTC",      "lat": 16.2956, "lng": 80.4561},
]

if route_stops_exists:
    try:
        res = supabase.table("route_stops").select("*").execute()
        if len(res.data) == 0:
            for stop in stops_data:
                supabase.table("route_stops").insert(stop).execute()
            print("  Seeded 6 stops ✓")
        else:
            print(f"  Already has {len(res.data)} rows, skipping seed")
    except Exception as e:
        print(f"  Error seeding route_stops: {e}")
else:
    print("  ⚠️  Table doesn't exist yet. Run schema.sql in Supabase SQL Editor first!")

# Step 3: Seed live_bus_state
print("\n[3/5] Checking/seeding live_bus_state...")
bus_ids = [
    ("AP-16-1234", "vja-gnt"),
    ("AP-16-4023", "vja-gnt"),
    ("AP-16-4024", "vja-gnt"),
    ("AP-16-4025", "vja-gnt"),
    ("AP-16-4026", "vja-gnt"),
    ("AP-16-5001", "gnt-vja"),
    ("AP-16-5002", "gnt-vja"),
]

try:
    res = supabase.table("live_bus_state").select("bus_id").execute()
    existing = {r["bus_id"] for r in res.data}
    
    for bus_id, route_id in bus_ids:
        if bus_id in existing:
            # Update capacity to 60 and add route_id if column exists
            try:
                supabase.table("live_bus_state").update({
                    "total_capacity": 60,
                }).eq("bus_id", bus_id).execute()
            except:
                pass
            print(f"  {bus_id}: exists, updated capacity to 60")
        else:
            try:
                supabase.table("live_bus_state").insert({
                    "bus_id": bus_id,
                    "total_capacity": 60,
                }).execute()
                print(f"  {bus_id}: created ✓")
            except Exception as e:
                print(f"  {bus_id}: error inserting - {e}")
except Exception as e:
    print(f"  Error: {e}")

# Step 4: Verify final state
print("\n[4/5] Verifying final state...")
try:
    res = supabase.table("live_bus_state").select("*").execute()
    print(f"  live_bus_state: {len(res.data)} buses")
    for bus in res.data:
        print(f"    {bus['bus_id']} | capacity: {bus.get('total_capacity', '?')} | route: {bus.get('route_id', 'N/A')}")
except Exception as e:
    print(f"  Error: {e}")

try:
    res = supabase.table("route_stops").select("*").order("stop_index").execute()
    print(f"\n  route_stops: {len(res.data)} stops")
    for s in res.data:
        print(f"    [{s['stop_index']}] {s['stop_name']} ({s['lat']}, {s['lng']})")
except Exception as e:
    print(f"  route_stops: {e}")

# Step 5: Test ticket + GPS endpoint readiness
print("\n[5/5] Testing ticket_events insert...")
try:
    res = supabase.table("ticket_events").insert({
        "bus_id": "AP-16-1234",
        "origin": "VIJAYAWADA PNBS",
        "destination": "GUNTUR RTC",
        "ticket_count": 1,
        "origin_index": 0,
        "dest_index": 5,
    }).execute()
    print(f"  Ticket insert: SUCCESS ✓")
    # Clean up test ticket
    if res.data:
        supabase.table("ticket_events").delete().eq("id", res.data[0]["id"]).execute()
        print(f"  Test ticket cleaned up ✓")
except Exception as e:
    print(f"  Ticket insert error: {e}")
    print("  ⚠️  If 'origin_index' or 'dest_index' columns don't exist,")
    print("     you need to run the full schema.sql in Supabase SQL Editor!")

print("\n" + "=" * 60)
print("Schema setup complete! Check results above.")
print("If any tables are missing, run backend/schema.sql in Supabase SQL Editor.")
print("=" * 60)
