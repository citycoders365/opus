"""Test the live Render backend"""
import sys, io, json, urllib.request
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

base = 'https://travellobus-opus.onrender.com'

print("=== Test 1: Root endpoint ===")
r = urllib.request.urlopen(base + '/')
d = json.loads(r.read())
print("Service:", d["service"], "-", d["status"])
print("Routes loaded:", d["routes_loaded"])

print("\n=== Test 2: Route stops ===")
r = urllib.request.urlopen(base + '/api/route_stops/vja-gnt')
d = json.loads(r.read())
print("Total stops:", len(d["stops"]))
for s in d["stops"]:
    idx = s["index"]
    name = s["name"]
    print("  [%d] %s (%.4f, %.4f)" % (idx, name, s["lat"], s["lng"]))

print("\n=== Test 3: Bus state (auto-dropoff engine) ===")
r = urllib.request.urlopen(base + '/api/bus_state/AP-16-1234')
d = json.loads(r.read())
print("Bus:", d["bus_id"])
print("Capacity:", d["total_capacity"])
print("Occupied:", d["occupied_seats"])
print("Empty:", d["empty_seats"])
print("Standing:", d["standing_count"])
print("Stop index:", d["current_stop_index"])

print("\n=== Test 4: Admin fleet ===")
r = urllib.request.urlopen(base + '/api/admin/fleet')
d = json.loads(r.read())
print("Total buses:", d["total_buses"])
for b in d["fleet"]:
    print("  %s | route: %s | onboard: %d/%d" % (b["bus_id"], b["route_id"], b["total_on_board"], b["total_capacity"]))

print("\nALL TESTS PASSED!")
