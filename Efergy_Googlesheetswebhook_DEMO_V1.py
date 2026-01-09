import sys, json, requests
from datetime import datetime

WEBHOOK_URL = "https://script.google.com/macros/s/GOOGLE_SHEETS_id/exec"

last_time = None
last_timestamp = None

for line in sys.stdin:
    msg = json.loads(line)

    if msg.get("model") != "Efergy-Optical":
        continue

    t = datetime.fromisoformat(msg["time"])

    # suppress duplicate interpretations (same timestamp)
    if last_timestamp == msg["time"]:
        continue
    last_timestamp = msg["time"]

    pulsecount = msg["pulsecount"]

    if last_time is None:
        dt = 30.0   # assume nominal interval for first update
    else:
        dt = (t - last_time).total_seconds()
        if dt <= 0:
            continue

    kw = pulsecount * 3.600 / dt

    payload = {
        "time": msg["time"],
        "pulsecount": pulsecount,
        "dt": dt,
        "kw": kw,
        "rssi": msg.get("rssi"),
        "snr": msg.get("snr")
    }

    r = requests.post(WEBHOOK_URL, json=payload)
    print("POST", r.status_code, payload)

    last_time = t
