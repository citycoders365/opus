"""
TravelloBus End-to-End Auto-Dropoff Demo
=========================================
This script simulates the FULL lifecycle:
1. Issue tickets to passengers going to different stops
2. Send GPS pings as bus moves along the route
3. Watch occupancy DROP automatically as bus passes each destination stop

No tickets are ever deleted — the auto-dropoff is pure math:
  occupied = COUNT(tickets WHERE dest_index > current_gps_stop_index)
"""
import sys, io, json, time, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

BASE = "https://travellobus-opus.onrender.com"
BUS = "AP-16-1234"

def api_post(path, data):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(data).encode(),
        headers={"Content-Type": "application/json"}
    )
    r = urllib.request.urlopen(req)
    return json.loads(r.read())

def api_get(path):
    r = urllib.request.urlopen(BASE + path)
    return json.loads(r.read())

def get_occupancy():
    d = api_get("/api/bus_state/" + BUS)
    return d["occupied_seats"], d["empty_seats"], d["standing_count"], d["current_stop_index"]

# Route stops for reference
STOPS = [
    (0, "VIJAYAWADA PNBS", 16.5089, 80.6156),
    (1, "TADEPALLI",       16.4803, 80.6188),
    (2, "MANGALAGIRI",     16.4122, 80.5584),
    (3, "NAMBURU",         16.3626, 80.5000),
    (4, "PEDDAKAKANI",     16.3400, 80.4908),
    (5, "GUNTUR RTC",      16.2956, 80.4561),
]

print("=" * 65)
print("  TRAVELLOBUS AUTO-DROPOFF DEMO")
print("  Bus: %s | Capacity: 60 seats" % BUS)
print("=" * 65)

# ── STEP 1: Reset — check current state ──
occ, emp, std, idx = get_occupancy()
print("\n[INITIAL STATE] Occupied: %d | Empty: %d | Standing: %d | Stop: %d" % (occ, emp, std, idx))

# ── STEP 2: Issue tickets to different destinations ──
print("\n--- STEP 1: ISSUING TICKETS ---")
tickets = [
    ("VIJAYAWADA PNBS", "TADEPALLI",   10),  # 10 pax getting off at stop 1
    ("VIJAYAWADA PNBS", "MANGALAGIRI",  15),  # 15 pax getting off at stop 2
    ("VIJAYAWADA PNBS", "NAMBURU",       8),  # 8 pax getting off at stop 3
    ("VIJAYAWADA PNBS", "PEDDAKAKANI",   5),  # 5 pax getting off at stop 4
    ("VIJAYAWADA PNBS", "GUNTUR RTC",   22),  # 22 pax going to the end
]

total_issued = 0
for origin, dest, count in tickets:
    res = api_post("/api/issue_ticket", {
        "bus_id": BUS,
        "origin": origin,
        "destination": dest,
        "ticket_count": count,
    })
    total_issued += count
    print("  Ticket: %d pax -> %s (indices: %d->%d)" % (
        count, dest, res.get("origin_index", "?"), res.get("dest_index", "?")))

print("  TOTAL ISSUED: %d passengers" % total_issued)

# Check occupancy after ticketing
occ, emp, std, idx = get_occupancy()
print("\n  [AFTER TICKETING] Occupied: %d | Empty: %d | Standing: %d" % (occ, emp, std))

# ── STEP 3: Simulate GPS movement along route ──
print("\n--- STEP 2: GPS SIMULATION (bus moving along route) ---")
print("  Watch occupancy DROP as bus passes each destination stop!\n")

for stop_idx, stop_name, lat, lng in STOPS:
    # Send GPS ping near this stop
    res = api_post("/api/gps_ping", {
        "bus_id": BUS,
        "lat": lat,
        "lng": lng,
    })

    # Check occupancy after GPS update
    occ, emp, std, idx = get_occupancy()

    # Calculate who dropped off
    bar = "#" * occ + "." * emp
    bar = bar[:60]  # cap at 60 chars for display

    print("  [Stop %d] %s" % (stop_idx, stop_name))
    print("    GPS -> Nearest: %s (dist: %sm)" % (res["nearest_stop"], res["distance_m"]))
    print("    Occupancy: %d/%d [%s]" % (occ, 60, bar))
    if std > 0:
        print("    STANDING: %d passengers!" % std)
    print()

    time.sleep(0.5)  # Small delay for readability

# ── STEP 4: Summary ──
print("=" * 65)
print("  DEMO COMPLETE!")
print("=" * 65)
occ, emp, std, idx = get_occupancy()
print("  Started with: %d passengers" % total_issued)
print("  Final state:  %d on board, %d empty seats" % (occ, emp))
print("  Auto-dropped: %d passengers (without deleting any tickets!)" % (total_issued - occ))
print()
print("  The auto-dropoff engine uses PURE MATH:")
print("  occupied = SUM(tickets WHERE dest_index > current_stop_index)")
print("  No tickets were deleted. They're all still in the database.")
print("=" * 65)
