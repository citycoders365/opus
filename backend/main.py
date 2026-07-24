"""
TravelloBus Backend v2 — FastAPI + Supabase
============================================
Core Features:
  - POST /api/issue_ticket     → Record ticket, enrich with stop indices
  - POST /api/gps_ping         → Receive GPS from ESP32, snap to nearest stop, update state
  - GET  /api/bus_state/{id}   → Live occupancy (auto-dropoff via Route Sequence Index)
  - GET  /api/route_stops/{id} → Ordered stop list with GPS coords
  - GET  /api/admin/fleet      → All buses with full state (admin dashboard)
  - GET  /api/admin/ghost_routes → Routes with avg < 20% occupancy
  - GET  /api/dropoffs/{id}    → Per-stop drop-off counts (legacy compat)
"""

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from supabase import create_client, Client
from typing import Optional
import os, math, time

# ============================================================
# APP SETUP
# ============================================================
app = FastAPI(title="TravelloBus Backend v2")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://ybprjrgzddgllanpjxnx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InlicHJqcmd6ZGRnbGxhbnBqeG54Iiwicm9sZSI6ImFub24iLCJpYXQiOjE3ODQ4NjA5NjAsImV4cCI6MjEwMDQzNjk2MH0.RJr17-e7Ua6XeakTGmhsJyU9ywty0TTfzCKK4RHyeUo")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# ============================================================
# IN-MEMORY ROUTE CACHE (loaded once at startup)
# ============================================================
# Structure: { "vja-gnt": [ {index, name, lat, lng}, ... ] }
_route_cache: dict = {}

def _load_routes():
    """Load route_stops from Supabase into memory. Called once at startup."""
    global _route_cache
    try:
        res = supabase.table("route_stops").select("*").order("stop_index").execute()
        _route_cache = {}
        for row in res.data:
            rid = row["route_id"]
            if rid not in _route_cache:
                _route_cache[rid] = []
            _route_cache[rid].append({
                "index": row["stop_index"],
                "name": row["stop_name"],
                "lat": row["lat"],
                "lng": row["lng"],
            })
    except Exception as e:
        print(f"[WARN] Could not load routes from DB: {e}")
        # Fallback hardcoded route for resilience
        _route_cache = {
            "vja-gnt": [
                {"index": 0, "name": "VIJAYAWADA PNBS", "lat": 16.5089, "lng": 80.6156},
                {"index": 1, "name": "TADEPALLI",       "lat": 16.4803, "lng": 80.6188},
                {"index": 2, "name": "MANGALAGIRI",     "lat": 16.4122, "lng": 80.5584},
                {"index": 3, "name": "NAMBURU",         "lat": 16.3626, "lng": 80.5000},
                {"index": 4, "name": "PEDDAKAKANI",     "lat": 16.3400, "lng": 80.4908},
                {"index": 5, "name": "GUNTUR RTC",      "lat": 16.2956, "lng": 80.4561},
            ]
        }

@app.on_event("startup")
async def startup():
    _load_routes()
    print(f"[BOOT] Loaded {len(_route_cache)} route(s): {list(_route_cache.keys())}")

# ============================================================
# HELPER: Haversine distance (meters)
# ============================================================
def _haversine(lat1, lng1, lat2, lng2) -> float:
    """Calculate distance between two GPS points in meters."""
    R = 6371000  # Earth radius in meters
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlam/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))

def _snap_to_nearest_stop(lat: float, lng: float, route_id: str) -> dict:
    """Find the nearest stop on a route to a GPS coordinate.
    Returns: { index, name, distance_m }
    """
    stops = _route_cache.get(route_id, [])
    if not stops:
        return {"index": 0, "name": "UNKNOWN", "distance_m": 99999}
    
    best = None
    for stop in stops:
        d = _haversine(lat, lng, stop["lat"], stop["lng"])
        if best is None or d < best["distance_m"]:
            best = {"index": stop["index"], "name": stop["name"], "distance_m": d}
    return best

def _get_stop_index(stop_name: str, route_id: str) -> int:
    """Look up the stop index for a stop name on a route."""
    stops = _route_cache.get(route_id, [])
    for stop in stops:
        if stop["name"].upper() == stop_name.upper():
            return stop["index"]
    return -1

# ============================================================
# HELPER: Compute live occupancy with auto-dropoff
# ============================================================
def _compute_occupancy(bus_id: str, current_stop_index: int, route_id: str, total_capacity: int) -> dict:
    """
    THE CORE AUTO-DROPOFF ENGINE.
    
    Logic:
      1. Fetch all ticket_events for this bus
      2. For each ticket, look up destination's stop index
      3. If dest_index <= current_stop_index → passenger has EXITED (don't count)
      4. If dest_index > current_stop_index → passenger is STILL ON BOARD (count)
      5. standing = max(0, occupied - capacity)
    
    For return routes (gnt-vja), the logic inverts:
      dest_index >= current_stop_index → exited (indices decrease along route)
    """
    res = supabase.table("ticket_events") \
        .select("destination, ticket_count, dest_index") \
        .eq("bus_id", bus_id) \
        .execute()
    
    is_return = route_id == "gnt-vja"
    occupied = 0
    dropoffs_map = {}  # stop_name → count of passengers dropping there
    
    for row in res.data:
        dest = row["destination"]
        count = row["ticket_count"]
        dest_idx = row.get("dest_index")
        
        # If dest_index wasn't stored, look it up
        if dest_idx is None:
            dest_idx = _get_stop_index(dest, route_id)
        
        # Auto-dropoff check
        if is_return:
            # Return route: stop indices go 5→0, passenger exits when bus passes their stop
            still_on_board = dest_idx < current_stop_index
        else:
            # Forward route: stop indices go 0→5
            still_on_board = dest_idx > current_stop_index
        
        if still_on_board:
            occupied += count
            dropoffs_map[dest] = dropoffs_map.get(dest, 0) + count
    
    standing = max(0, occupied - total_capacity)
    seated = min(occupied, total_capacity)
    empty = max(0, total_capacity - occupied)
    
    # Format dropoffs for frontend
    dropoffs = [
        {"stop": name, "count": cnt, "eta": "N/A"}
        for name, cnt in dropoffs_map.items()
    ]
    
    return {
        "occupied_seats": seated,
        "standing_count": standing,
        "empty_seats": empty,
        "total_on_board": occupied,
        "dropoffs": dropoffs,
    }

# ============================================================
# SCHEMAS
# ============================================================
class TicketEvent(BaseModel):
    bus_id: str
    origin: str
    destination: str
    ticket_count: int

class GPSPing(BaseModel):
    bus_id: str
    lat: float
    lng: float

# ============================================================
# ENDPOINTS
# ============================================================

@app.post("/api/issue_ticket")
async def issue_ticket(event: TicketEvent):
    """
    Called by the ETM when a ticket is printed.
    Enriches with stop indices for the auto-dropoff engine.
    """
    try:
        # Look up bus to get its route
        bus_res = supabase.table("live_bus_state") \
            .select("route_id") \
            .eq("bus_id", event.bus_id) \
            .execute()
        
        route_id = "vja-gnt"  # default
        if bus_res.data:
            route_id = bus_res.data[0].get("route_id", "vja-gnt")
        
        # Enrich with stop indices
        origin_idx = _get_stop_index(event.origin, route_id)
        dest_idx = _get_stop_index(event.destination, route_id)
        
        # Insert ticket event with indices
        supabase.table("ticket_events").insert({
            "bus_id": event.bus_id,
            "origin": event.origin,
            "destination": event.destination,
            "ticket_count": event.ticket_count,
            "origin_index": origin_idx,
            "dest_index": dest_idx,
        }).execute()
        
        return {
            "status": "success",
            "message": f"{event.ticket_count} ticket(s) issued",
            "origin_index": origin_idx,
            "dest_index": dest_idx,
        }
    
    except Exception as e:
        print(f"[ERROR] issue_ticket: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.post("/api/gps_ping")
async def gps_ping(ping: GPSPing):
    """
    Called by the ESP32 (or GPS simulator) every 20-30 seconds.
    1. Stores the raw GPS event for audit
    2. Snaps to nearest stop on the bus's route
    3. Updates live_bus_state with current position
    """
    try:
        # Get bus route
        bus_res = supabase.table("live_bus_state") \
            .select("route_id") \
            .eq("bus_id", ping.bus_id) \
            .execute()
        
        if not bus_res.data:
            raise HTTPException(status_code=404, detail=f"Bus {ping.bus_id} not found")
        
        route_id = bus_res.data[0].get("route_id", "vja-gnt")
        
        # 1. Store raw GPS event
        supabase.table("gps_events").insert({
            "bus_id": ping.bus_id,
            "lat": ping.lat,
            "lng": ping.lng,
        }).execute()
        
        # 2. Snap to nearest stop
        nearest = _snap_to_nearest_stop(ping.lat, ping.lng, route_id)
        
        # 3. Update live state
        supabase.table("live_bus_state").update({
            "current_stop_index": nearest["index"],
            "last_gps_lat": ping.lat,
            "last_gps_lng": ping.lng,
            "last_gps_timestamp": "now()",
            "last_updated": "now()",
        }).eq("bus_id", ping.bus_id).execute()
        
        return {
            "status": "success",
            "nearest_stop": nearest["name"],
            "stop_index": nearest["index"],
            "distance_m": round(nearest["distance_m"], 1),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] gps_ping: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/bus_state/{bus_id}")
async def get_bus_state(bus_id: str):
    """
    Returns live occupancy computed via the auto-dropoff engine.
    Passengers whose destination_index <= current_stop_index are auto-removed.
    """
    try:
        res = supabase.table("live_bus_state") \
            .select("*") \
            .eq("bus_id", bus_id) \
            .execute()
        
        if not res.data:
            raise HTTPException(status_code=404, detail="Bus not found")
        
        state = res.data[0]
        capacity = state.get("total_capacity", 60)
        current_idx = state.get("current_stop_index", 0)
        route_id = state.get("route_id", "vja-gnt")
        
        # Compute live occupancy with auto-dropoff
        occ = _compute_occupancy(bus_id, current_idx, route_id, capacity)
        
        return {
            "bus_id": bus_id,
            "route_id": route_id,
            "total_capacity": capacity,
            "current_stop_index": current_idx,
            "occupied_seats": occ["occupied_seats"],
            "standing_count": occ["standing_count"],
            "empty_seats": occ["empty_seats"],
            "total_on_board": occ["total_on_board"],
            "dropoffs": occ["dropoffs"],
            "last_gps_lat": state.get("last_gps_lat"),
            "last_gps_lng": state.get("last_gps_lng"),
            "last_gps_timestamp": state.get("last_gps_timestamp"),
            "last_updated": state.get("last_updated"),
        }
    
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] bus_state: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/route_stops/{route_id}")
async def get_route_stops(route_id: str):
    """Returns ordered stop list with GPS coordinates."""
    stops = _route_cache.get(route_id, [])
    if not stops:
        raise HTTPException(status_code=404, detail=f"Route '{route_id}' not found")
    return {"route_id": route_id, "stops": stops}


@app.get("/api/admin/fleet")
async def admin_fleet():
    """
    Returns all buses with full live state. For admin dashboard.
    Includes exact standing counts (not shown to passengers).
    """
    try:
        buses_res = supabase.table("live_bus_state").select("*").execute()
        fleet = []
        
        for bus in buses_res.data:
            bus_id = bus["bus_id"]
            capacity = bus.get("total_capacity", 60)
            current_idx = bus.get("current_stop_index", 0)
            route_id = bus.get("route_id", "vja-gnt")
            
            occ = _compute_occupancy(bus_id, current_idx, route_id, capacity)
            
            # Determine current stop name
            stops = _route_cache.get(route_id, [])
            current_stop_name = "Unknown"
            for s in stops:
                if s["index"] == current_idx:
                    current_stop_name = s["name"]
                    break
            
            # Ghost route flag: if total_on_board < 20% of capacity
            is_ghost = occ["total_on_board"] < (capacity * 0.2)
            utilization_pct = round((occ["total_on_board"] / capacity) * 100) if capacity > 0 else 0
            
            fleet.append({
                "bus_id": bus_id,
                "route_id": route_id,
                "total_capacity": capacity,
                "current_stop_index": current_idx,
                "current_stop_name": current_stop_name,
                "occupied_seats": occ["occupied_seats"],
                "standing_count": occ["standing_count"],
                "empty_seats": occ["empty_seats"],
                "total_on_board": occ["total_on_board"],
                "utilization_pct": utilization_pct,
                "is_ghost": is_ghost,
                "last_gps_lat": bus.get("last_gps_lat"),
                "last_gps_lng": bus.get("last_gps_lng"),
                "last_gps_timestamp": bus.get("last_gps_timestamp"),
                "last_updated": bus.get("last_updated"),
                "dropoffs": occ["dropoffs"],
            })
        
        return {"fleet": fleet, "total_buses": len(fleet)}
    
    except Exception as e:
        print(f"[ERROR] admin_fleet: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/admin/ghost_routes")
async def admin_ghost_routes():
    """
    Returns buses flagged as Ghost Routes (< 20% utilization).
    Includes estimated daily diesel waste.
    """
    try:
        fleet_data = await admin_fleet()
        ghosts = [b for b in fleet_data["fleet"] if b["is_ghost"]]
        
        for g in ghosts:
            # Estimated diesel cost: ~₹1,500/day for a running bus
            g["estimated_daily_diesel"] = 1500
            g["recommendation"] = (
                "Consider merging with adjacent schedule or deploying a mini-bus."
                if g["utilization_pct"] < 10
                else "Monitor for 7 days. If utilization stays below 20%, consider rescheduling."
            )
        
        return {
            "ghost_count": len(ghosts),
            "ghosts": ghosts,
            "potential_daily_savings": len(ghosts) * 1500,
        }
    
    except Exception as e:
        print(f"[ERROR] ghost_routes: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/api/dropoffs/{bus_id}")
async def get_dropoffs(bus_id: str):
    """Legacy endpoint: per-stop drop-off counts."""
    try:
        state = await get_bus_state(bus_id)
        return {"dropoffs": state.get("dropoffs", [])}
    except HTTPException:
        raise
    except Exception as e:
        print(f"[ERROR] dropoffs: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


@app.get("/")
async def root():
    return {
        "service": "TravelloBus Backend v2",
        "status": "running",
        "routes_loaded": list(_route_cache.keys()),
        "endpoints": [
            "POST /api/issue_ticket",
            "POST /api/gps_ping",
            "GET  /api/bus_state/{bus_id}",
            "GET  /api/route_stops/{route_id}",
            "GET  /api/admin/fleet",
            "GET  /api/admin/ghost_routes",
        ]
    }

# Run via: uvicorn main:app --reload
