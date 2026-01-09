#!/usr/bin/env python3

import sys
import json
import requests
import os
import socket
import threading
import time
from datetime import datetime

# ==================================================
# CONFIG
# ==================================================

# Get URL from environment (systemd)
WEBHOOK_URL = os.getenv("GS_POST_URL")

if not WEBHOOK_URL:
    # Fallback for manual testing if needed, or raise error
    raise RuntimeError("GS_POST_URL environment variable not set")

# ==================================================
# TEMPEST WEATHER LISTENER (Background Thread)
# ==================================================

# Store the latest weather data here
latest_weather = {
    "temp_c": None,
    "humidity": None,  # <--- NEW: Added Humidity storage
    "solar_w": None,
    "wind_mps": None,
    "last_update": 0
}

def monitor_tempest():
    """Listens for UDP broadcasts from Tempest Hub on port 50222"""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    try:
        s.bind(('', 50222))
    except Exception as e:
        sys.stderr.write(f"Error binding Tempest UDP: {e}\n")
        return

    while True:
        try:
            data, addr = s.recvfrom(4096)
            msg = json.loads(data)

            # 'obs_st' is the status observation packet
            if msg.get("type") == "obs_st":
                obs = msg["obs"][0]
                # Index map: 7=Temp(C), 8=Humidity(%), 11=Solar(W/m2), 2=WindAvg(m/s)
                latest_weather["temp_c"] = obs[7]
                latest_weather["humidity"] = obs[8]  # <--- NEW: Capture Humidity
                latest_weather["solar_w"] = obs[11]
                latest_weather["wind_mps"] = obs[2]
                latest_weather["last_update"] = time.time()

        except Exception:
            # Ignore bad packets
            continue

# Start the listener in the background
t = threading.Thread(target=monitor_tempest, daemon=True)
t.start()

# ==================================================
# MAIN LOOP (Reads rtl_433 from Pipe)
# ==================================================

last_time = None
last_timestamp = None

sys.stderr.write("Starting Power + Weather ingestion...\n")

for line in sys.stdin:
    try:
        msg = json.loads(line)

        # Filter for your specific Efergy device
        if msg.get("model") != "Efergy-Optical":
            continue

        # -----------------------------
        # 1. CALCULATE POWER
        # -----------------------------
        t_str = msg.get("time")
        if not t_str:
            continue

        # Handle ISO format usually provided by rtl_433
        t = datetime.fromisoformat(t_str)

        # Suppress duplicate packets (same timestamp)
        if last_timestamp == t_str:
            continue
        last_timestamp = t_str

        pulsecount = msg.get("pulsecount")
        if pulsecount is None:
            continue

        if last_time is None:
            dt = 30.0   # assume nominal interval for first update
        else:
            dt = (t - last_time).total_seconds()

        # Ignore wildly impossible time jumps (prevent bad math)
        if dt <= 0:
            continue

        kw = pulsecount * 3.600 / dt
        last_time = t

        # -----------------------------
        # 2. GATHER METRICS
        # -----------------------------

        # Check if weather data is fresh (within last 2 mins)
        weather_fresh = (time.time() - latest_weather["last_update"]) < 120

        payload = {
            "source": "house_main",  # Explicit source tag
            "time": t_str,
            "pulsecount": pulsecount,
            "dt": dt,
            "kw": kw,

            # Signal Health
            "rssi": msg.get("rssi"),
            "snr": msg.get("snr"),

            # Frequency Drift: Use freq1 if freq is missing (FSK fix)
            "freq": msg.get("freq") or msg.get("freq1"),

            # BATTERY TRICK: Map RSSI to battery_ok so it shows in the sheet
            "battery_ok": msg.get("rssi"),

            # Weather Data (only if fresh)
            "temp_c": latest_weather["temp_c"] if weather_fresh else None,
            "humidity": latest_weather["humidity"] if weather_fresh else None, # <--- NEW
            "solar_w": latest_weather["solar_w"] if weather_fresh else None,
            "wind_mps": latest_weather["wind_mps"] if weather_fresh else None
        }

        # -----------------------------
        # 3. SEND TO GOOGLE
        # -----------------------------
        try:
            r = requests.post(WEBHOOK_URL, json=payload, timeout=10)
            # Print status to logs
            print(f"POST {r.status_code} | {kw:.2f}kW | Solar: {payload['solar_w']} | RH: {payload['humidity']}%")
        except Exception as e:
            sys.stderr.write(f"Post Error: {e}\n")

    except json.JSONDecodeError:
        continue
    except Exception as e:
        sys.stderr.write(f"Loop Error: {e}\n")