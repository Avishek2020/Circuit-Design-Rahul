"""
Synthetic data generator for ColdChain Guardian AI.
Run: python data/seed.py
Fixed seed=42 for reproducibility.
"""

import json
import random
import math
import os
from datetime import datetime, timedelta, timezone

random.seed(42)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE_DIR, "synthetic")
os.makedirs(OUT_DIR, exist_ok=True)

# ── helpers ──────────────────────────────────────────────────────────────────

def fmt_dt(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")

def rand_dt(start: datetime, end: datetime) -> datetime:
    delta = end - start
    secs = int(delta.total_seconds())
    return start + timedelta(seconds=random.randint(0, secs))

def jitter(val: float, spread: float) -> float:
    return round(val + random.uniform(-spread, spread), 2)

DRIVER_NAMES = [
    "John Carter", "Maria Gonzalez", "David Kim", "Sarah Chen", "Marcus Webb",
    "Priya Patel", "James O'Brien", "Fatima Al-Hassan", "Carlos Ruiz", "Elena Novak",
    "Tyler Brooks", "Ayasha Redcloud", "Omar Farooq", "Ling Zhao", "Derek Thompson",
    "Yuki Tanaka", "Samuel Okafor", "Nadia Petrov", "Brendan Walsh", "Zoe Martins",
]

MANAGER_NAMES = [
    "Dr. Patricia Wells", "Robert Huang", "Lisa Monroe", "Ahmed Khalil",
    "Jennifer Park", "Thomas Eriksson", "Amara Diallo", "Chris Nguyen",
    "Sophie Bouchard", "Victor Santos",
]

INVESTIGATOR_NAMES = [
    "Dr. Patricia Wells", "Robert Huang", "Lisa Monroe", "Ahmed Khalil", "Jennifer Park",
]

TECH_NAMES = [
    "Mike Torres", "Sandra Lee", "Kevin O'Sullivan", "Rashida Johnson",
    "Frank Mueller", "Yemi Adeyemi", "Paul Renault",
]

# ── warehouses ────────────────────────────────────────────────────────────────

WAREHOUSE_CONFIGS = [
    ("WH-01", "FrostGuard Central Hub",    "Chicago, IL",       41.8781, -87.6298),
    ("WH-02", "PolarPath Los Angeles",     "Los Angeles, CA",   34.0522, -118.2437),
    ("WH-03", "ArcticFlow Dallas",         "Dallas, TX",        32.7767, -96.7970),
    ("WH-04", "ChillChain New York",       "New York, NY",      40.7128, -74.0060),
    ("WH-05", "IceLane Atlanta",           "Atlanta, GA",       33.7490, -84.3880),
    ("WH-06", "FrostEdge Seattle",         "Seattle, WA",       47.6062, -122.3321),
    ("WH-07", "ColdVault Denver",          "Denver, CO",        39.7392, -104.9903),
    ("WH-08", "GlacierPoint Miami",        "Miami, FL",         25.7617, -80.1918),
    ("WH-09", "TundraTrans Phoenix",       "Phoenix, AZ",       33.4484, -112.0740),
    ("WH-10", "FreezeLink Boston",         "Boston, MA",        42.3601, -71.0589),
]

CERTS = ["HACCP", "ISO 22000", "FDA Registered", "SQF Level 2", "BRC Grade A"]

def build_warehouses():
    whs = []
    for i, (wid, name, loc, lat, lon) in enumerate(WAREHOUSE_CONFIGS):
        cap = random.choice([300, 400, 500, 600, 800])
        occ = random.randint(int(cap * 0.3), int(cap * 0.9))
        cert_subset = random.sample(CERTS, k=random.randint(2, 4))
        since = datetime(2015 + i % 7, random.randint(1, 12), random.randint(1, 28))
        whs.append({
            "warehouse_id": wid,
            "name": name,
            "location": loc,
            "latitude": lat,
            "longitude": lon,
            "capacity_pallets": cap,
            "current_occupancy_pallets": occ,
            "temperature_zones": [
                {"zone": "A", "type": "frozen",  "temp_range": [-25, -15]},
                {"zone": "B", "type": "chilled", "temp_range": [0,    4]},
                {"zone": "C", "type": "ambient", "temp_range": [15,  25]},
            ],
            "certifications": cert_subset,
            "contact_manager": MANAGER_NAMES[i],
            "phone": f"+1-{random.randint(200,999)}-555-{random.randint(1000,9999):04d}",
            "operational_since": since.strftime("%Y-%m-%d"),
        })
    return whs

# ── trucks ────────────────────────────────────────────────────────────────────

TRUCK_MAKES = {
    "Volvo":    ["FH16", "FH500"],
    "Scania":   ["R450", "S580"],
    "Mercedes": ["Actros 2545", "Actros 1845"],
    "MAN":      ["TGX 26.500", "TGX 18.440"],
    "DAF":      ["XF 530", "CF 450"],
}
REFRIG_UNITS = [
    "Thermo King SLXi-400", "Carrier Vector 1550", "Thermo King T-680R",
    "Carrier Supra 850U", "Frigoblock FK 35",
]

def build_trucks():
    trucks = []
    for i in range(1, 21):
        make = random.choice(list(TRUCK_MAKES))
        model = random.choice(TRUCK_MAKES[make])
        year = random.randint(2018, 2023)
        last_maint = datetime(2024, random.randint(1, 10), random.randint(1, 28))
        next_maint = last_maint + timedelta(days=90)
        overdue = i in (5, 13)  # two trucks intentionally overdue
        notes = "Maintenance overdue – compressor showing wear" if overdue else ""
        status = "maintenance_required" if overdue else random.choice(["active", "active", "active", "in_repair"])
        trucks.append({
            "truck_id": f"TRK-{i:03d}",
            "license_plate": f"CLD-{random.randint(1000,9999)}",
            "make": make,
            "model": model,
            "year": year,
            "max_payload_kg": random.choice([15000, 18000, 20000, 22000]),
            "refrigeration_unit": random.choice(REFRIG_UNITS),
            "last_maintenance_date": last_maint.strftime("%Y-%m-%d"),
            "next_maintenance_due": next_maint.strftime("%Y-%m-%d"),
            "current_status": status,
            "assigned_driver": DRIVER_NAMES[i - 1],
            "notes": notes,
        })
    return trucks

# ── shipments ─────────────────────────────────────────────────────────────────

PRODUCT_SPECS = {
    "meat":    (["Beef Quarters", "Pork Loins", "Lamb Chops"],               -4,  4),
    "dairy":   (["Butter Blocks", "Cheese Wheels", "Fresh Cream"],            1,  4),
    "produce": (["Leafy Greens", "Strawberries", "Tomatoes"],                 2,  8),
    "pharma":  (["Insulin Vials", "Vaccine Doses", "Biologics"],              2,  8),
    "seafood": (["Atlantic Salmon", "Tuna Steaks", "Shrimp"],                -2,  2),
    "frozen":  (["Frozen Beef", "Ice Cream", "Frozen Vegetables"],          -25,-15),
}

INCIDENT_SHIPMENTS = {7, 15, 23, 42, 67, 81, 90}  # 0-indexed positions
START = datetime(2024, 10, 1, tzinfo=timezone.utc)
END   = datetime(2024, 11, 30, tzinfo=timezone.utc)

def build_shipments(warehouses, trucks):
    wh_ids = [w["warehouse_id"] for w in warehouses]
    tk_ids = [t["truck_id"] for t in trucks]
    shipments = []
    for i in range(1, 101):
        cat = random.choice(list(PRODUCT_SPECS))
        products, tmin, tmax = PRODUCT_SPECS[cat]
        product = random.choice(products)
        origin, dest = random.sample(wh_ids, 2)
        truck_id = random.choice(tk_ids)
        driver = next(t["assigned_driver"] for t in trucks if t["truck_id"] == truck_id)
        dist = random.randint(80, 1200)
        hours = dist / random.uniform(60, 90)
        depart = rand_dt(START, END - timedelta(days=2))
        arrive = depart + timedelta(hours=hours)
        is_problem = (i - 1) in INCIDENT_SHIPMENTS or random.random() < 0.08
        if is_problem:
            status = random.choice(["failed_inspection", "delayed"])
            notes = "Temperature excursion recorded during transit." if (i - 1) in INCIDENT_SHIPMENTS else "Delayed due to route deviation."
        else:
            status = "delivered" if arrive < datetime.now(timezone.utc) else "in_transit"
            notes = ""
        shipments.append({
            "shipment_id": f"SHP-{i:04d}",
            "origin_warehouse_id": origin,
            "destination_warehouse_id": dest,
            "truck_id": truck_id,
            "product_type": product,
            "product_category": cat,
            "required_temp_min": tmin,
            "required_temp_max": tmax,
            "quantity_kg": random.randint(100, 2000),
            "departure_time": fmt_dt(depart),
            "arrival_time": fmt_dt(arrive),
            "status": status,
            "distance_km": dist,
            "driver_name": driver,
            "notes": notes,
        })
    return shipments

# ── temperature readings ───────────────────────────────────────────────────────

def build_temp_readings(shipments):
    readings = []
    rid = 1
    for shp in shipments:
        shp_id = shp["shipment_id"]
        truck_id = shp["truck_id"]
        tmin = shp["required_temp_min"]
        tmax = shp["required_temp_max"]
        t_mid = (tmin + tmax) / 2
        depart = datetime.strptime(shp["departure_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        arrive = datetime.strptime(shp["arrival_time"],   "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        duration_min = max(15, int((arrive - depart).total_seconds() / 60))
        steps = duration_min // 15
        has_excursion = shp["notes"] == "Temperature excursion recorded during transit."
        # pick 1-3 excursion windows (expressed as step indices)
        excursion_windows = []
        if has_excursion:
            n_exc = random.randint(1, 3)
            for _ in range(n_exc):
                start_step = random.randint(2, max(2, steps - 10))
                dur_steps  = random.randint(2, 6)   # 30-90 min
                deviation  = random.uniform(3, 8)
                excursion_windows.append((start_step, start_step + dur_steps, deviation))
        lat_start = random.uniform(25, 48)
        lon_start = random.uniform(-120, -70)
        lat_end   = lat_start + random.uniform(-5, 5)
        lon_end   = lon_start + random.uniform(-5, 5)
        sensor_id = f"SENS-{truck_id}-A"
        for step in range(steps + 1):
            ts = depart + timedelta(minutes=step * 15)
            # interpolate position
            frac = step / max(1, steps)
            lat = round(lat_start + frac * (lat_end - lat_start), 5)
            lon = round(lon_start + frac * (lon_end - lon_start), 5)
            # determine temperature
            temp = jitter(t_mid, (tmax - tmin) * 0.3)
            is_exc = False
            for ws, we, dev in excursion_windows:
                if ws <= step < we:
                    temp = round(tmax + dev, 2) if random.random() > 0.5 else round(tmin - dev, 2)
                    is_exc = True
                    break
            readings.append({
                "reading_id":          f"RDG-{rid:05d}",
                "shipment_id":         shp_id,
                "truck_id":            truck_id,
                "timestamp":           fmt_dt(ts),
                "temperature_celsius": temp,
                "humidity_percent":    round(random.uniform(78, 95), 1),
                "sensor_id":           sensor_id,
                "is_excursion":        is_exc,
                "location_lat":        lat,
                "location_lon":        lon,
            })
            rid += 1
    return readings

# ── door events ───────────────────────────────────────────────────────────────

def build_door_events(shipments):
    events = []
    eid = 1
    for shp in shipments:
        shp_id  = shp["shipment_id"]
        tk_id   = shp["truck_id"]
        depart  = datetime.strptime(shp["departure_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        arrive  = datetime.strptime(shp["arrival_time"],   "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        n_stops = random.randint(1, 4)
        for s in range(n_stops):
            # pick open time within transit window
            open_ts = rand_dt(depart + timedelta(minutes=30), arrive - timedelta(minutes=30))
            suspicious = random.random() < 0.07   # ~7% suspicious
            if suspicious:
                # force a 2-4 AM time
                open_ts = open_ts.replace(hour=random.randint(2, 4), minute=random.randint(0, 59))
            dur_secs  = random.randint(45, 600)
            close_ts  = open_ts + timedelta(seconds=dur_secs)
            lat = round(random.uniform(25, 48), 5)
            lon = round(random.uniform(-120, -70), 5)
            note = "Unscheduled overnight access" if suspicious else random.choice(["Delivery checkpoint", "Temperature check", "Loading", "Unloading", ""])
            # open event
            events.append({
                "event_id":           f"DOOR-{eid:05d}",
                "shipment_id":        shp_id,
                "truck_id":           tk_id,
                "timestamp":          fmt_dt(open_ts),
                "event_type":         "open",
                "duration_seconds":   None,
                "location_lat":       lat,
                "location_lon":       lon,
                "is_scheduled_stop":  not suspicious,
                "notes":              note,
            })
            eid += 1
            # close event
            events.append({
                "event_id":           f"DOOR-{eid:05d}",
                "shipment_id":        shp_id,
                "truck_id":           tk_id,
                "timestamp":          fmt_dt(close_ts),
                "event_type":         "close",
                "duration_seconds":   dur_secs,
                "location_lat":       lat,
                "location_lon":       lon,
                "is_scheduled_stop":  not suspicious,
                "notes":              "",
            })
            eid += 1
    return events

# ── maintenance reports ───────────────────────────────────────────────────────

MAINT_TYPES    = ["scheduled", "unscheduled", "breakdown"]
PARTS_OPTIONS  = [
    ["door_seal"],
    ["refrigerant_charge", "filter"],
    ["compressor_belt"],
    ["thermostat", "door_seal"],
    ["condenser_coil", "refrigerant_charge"],
    ["brake_pads", "air_filter"],
]
ISSUES_OPTIONS = [
    [],
    [],
    ["minor_refrigerant_leak"],
    ["door_seal_wear"],
    ["thermostat_drift", "door_seal_wear"],
    ["compressor_noise"],
]

def build_maintenance(trucks):
    reports = []
    rid = 1
    for truck in trucks:
        n = random.randint(2, 3)
        base_date = datetime(2024, 1, 1)
        for j in range(n):
            date = base_date + timedelta(days=random.randint(j * 90, j * 90 + 89))
            mtype = "scheduled" if j == 0 else random.choice(MAINT_TYPES)
            issues = random.choice(ISSUES_OPTIONS)
            parts  = random.choice(PARTS_OPTIONS)
            passed = not (issues and random.random() < 0.25)
            failed_note = " – failed due to unresolved compressor issue" if not passed else ""
            reports.append({
                "report_id":          f"MNT-{rid:03d}",
                "truck_id":           truck["truck_id"],
                "date":               date.strftime("%Y-%m-%d"),
                "type":               mtype,
                "description":        f"{mtype.capitalize()} service: refrigeration unit check, door seal inspection{failed_note}",
                "technician":         random.choice(TECH_NAMES),
                "cost_usd":           random.randint(400, 3500),
                "issues_found":       issues,
                "parts_replaced":     parts,
                "next_service_km":    random.choice([50000, 75000, 100000]),
                "passed_inspection":  passed,
            })
            rid += 1
    return reports

# ── incidents ─────────────────────────────────────────────────────────────────

INCIDENT_TYPES = [
    "temperature_excursion", "door_breach", "delayed_delivery",
    "equipment_failure", "contamination_risk",
]
ROOT_CAUSES = [
    "refrigeration_unit_failure", "door_seal_failure", "power_outage",
    "operator_error", "traffic_delay", "mechanical_breakdown",
]
CORRECTIVE = [
    "Emergency compressor repair; product disposed; FDA notification submitted.",
    "Door seal replaced; shipment held for inspection; released after 48h.",
    "Route replanned; delivery rescheduled; customer notified.",
    "Full refrigeration overhaul; truck taken out of service for 72h.",
    "Product quarantined pending lab results; supplier notified.",
]

def build_incidents(shipments):
    problem_shps = [s for s in shipments if s["status"] in ("failed_inspection", "delayed")]
    incidents = []
    iid = 1
    for shp in random.sample(problem_shps, min(len(problem_shps), 18)):
        itype    = random.choice(INCIDENT_TYPES)
        severity = random.choices(["low","medium","high","critical"], weights=[1,3,3,1])[0]
        depart   = datetime.strptime(shp["departure_time"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        arrive   = datetime.strptime(shp["arrival_time"],   "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
        inc_time = rand_dt(depart, arrive)
        dur_min  = random.randint(20, 180)
        dev      = round(random.uniform(2, 10), 1)
        tmax     = shp["required_temp_max"]
        actual_t = round(tmax + dev, 1)
        disposed = severity in ("high", "critical")
        loss     = random.randint(2000, 25000) if disposed else 0
        incidents.append({
            "incident_id":          f"INC-{iid:03d}",
            "shipment_id":          shp["shipment_id"],
            "truck_id":             shp["truck_id"],
            "warehouse_id":         shp["destination_warehouse_id"],
            "type":                 itype,
            "severity":             severity,
            "timestamp":            fmt_dt(inc_time),
            "duration_minutes":     dur_min,
            "max_temp_deviation":   dev,
            "description":          (
                f"Temperature reached {actual_t}°C (required max: {tmax}°C) "
                f"during transit – {itype.replace('_',' ')}."
            ),
            "regulatory_reportable": severity in ("high", "critical"),
            "product_disposed":      disposed,
            "disposal_kg":           shp["quantity_kg"] if disposed else 0,
            "financial_loss_usd":    loss,
            "root_cause":            random.choice(ROOT_CAUSES),
            "corrective_action":     random.choice(CORRECTIVE),
            "status":                random.choice(["open", "investigating", "closed", "closed"]),
            "investigator":          random.choice(INVESTIGATOR_NAMES),
        })
        iid += 1
    return incidents

# ── write & summarise ─────────────────────────────────────────────────────────

def write_json(name, data):
    path = os.path.join(OUT_DIR, name)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"  {name:<35} {len(data):>5} records  →  {path}")

def main():
    print("ColdChain Guardian AI – synthetic data generator")
    print("=" * 55)

    warehouses   = build_warehouses()
    trucks       = build_trucks()
    shipments    = build_shipments(warehouses, trucks)
    temp_rdgs    = build_temp_readings(shipments)
    door_events  = build_door_events(shipments)
    maintenance  = build_maintenance(trucks)
    incidents    = build_incidents(shipments)

    write_json("warehouses.json",           warehouses)
    write_json("trucks.json",               trucks)
    write_json("shipments.json",            shipments)
    write_json("temperature_readings.json", temp_rdgs)
    write_json("door_events.json",          door_events)
    write_json("maintenance_reports.json",  maintenance)
    write_json("incidents.json",            incidents)

    print("=" * 55)
    total = sum([len(warehouses), len(trucks), len(shipments),
                 len(temp_rdgs), len(door_events), len(maintenance), len(incidents)])
    print(f"  Total records generated: {total}")
    exc_count = sum(1 for r in temp_rdgs if r["is_excursion"])
    print(f"  Temperature excursions:  {exc_count}")
    print("Done.")

if __name__ == "__main__":
    main()
