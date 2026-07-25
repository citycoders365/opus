"""Seed data into new Supabase project"""
import sys, io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from supabase import create_client

s = create_client(
    'https://ybprjrgzddgllanpjxnx.supabase.co',
    'eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlicHJqcmd6ZGRnbGxhbnBqeG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NjA5NjAsImV4cCI6MjEwMDQzNjk2MH0.RJr17-e7Ua6XeakTGmhsJyU9ywty0TTfzCKK4RHyeUo'
)

print("=== Seeding route_stops ===")
stops = [
    {"route_id": "vja-gnt", "stop_index": 0, "stop_name": "VIJAYAWADA PNBS", "lat": 16.5089, "lng": 80.6156},
    {"route_id": "vja-gnt", "stop_index": 1, "stop_name": "TADEPALLI",       "lat": 16.4803, "lng": 80.6188},
    {"route_id": "vja-gnt", "stop_index": 2, "stop_name": "MANGALAGIRI",     "lat": 16.4122, "lng": 80.5584},
    {"route_id": "vja-gnt", "stop_index": 3, "stop_name": "NAMBURU",         "lat": 16.3626, "lng": 80.5000},
    {"route_id": "vja-gnt", "stop_index": 4, "stop_name": "PEDDAKAKANI",     "lat": 16.3400, "lng": 80.4908},
    {"route_id": "vja-gnt", "stop_index": 5, "stop_name": "GUNTUR RTC",      "lat": 16.2956, "lng": 80.4561},
]
for st in stops:
    try:
        s.table("route_stops").insert(st).execute()
        print(f"  [{st['stop_index']}] {st['stop_name']} - inserted")
    except Exception as e:
        err = str(e)
        if "duplicate" in err.lower() or "23505" in err:
            print(f"  [{st['stop_index']}] {st['stop_name']} - already exists")
        else:
            print(f"  [{st['stop_index']}] ERROR: {err[:80]}")

print("\n=== Seeding live_bus_state ===")
buses = [
    ("AP-16-1234", "vja-gnt"),
    ("AP-16-4023", "vja-gnt"),
    ("AP-16-4024", "vja-gnt"),
    ("AP-16-4025", "vja-gnt"),
    ("AP-16-4026", "vja-gnt"),
    ("AP-16-5001", "gnt-vja"),
    ("AP-16-5002", "gnt-vja"),
]
for bus_id, route_id in buses:
    try:
        s.table("live_bus_state").insert({
            "bus_id": bus_id,
            "route_id": route_id,
            "total_capacity": 60,
            "current_stop_index": 0,
        }).execute()
        print(f"  {bus_id} ({route_id}) - inserted")
    except Exception as e:
        err = str(e)
        if "duplicate" in err.lower() or "23505" in err:
            print(f"  {bus_id} - already exists")
        else:
            print(f"  {bus_id} ERROR: {err[:80]}")

print("\n=== Verification ===")
r1 = s.table("route_stops").select("*").order("stop_index").execute()
print(f"route_stops: {len(r1.data)} rows")
for r in r1.data:
    print(f"  [{r['stop_index']}] {r['stop_name']} ({r['lat']}, {r['lng']})")

r2 = s.table("live_bus_state").select("*").execute()
print(f"\nlive_bus_state: {len(r2.data)} buses")
for b in r2.data:
    print(f"  {b['bus_id']} | capacity: {b['total_capacity']} | route: {b['route_id']}")

print("\nDONE! Supabase is fully seeded.")
