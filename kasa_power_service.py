#!/usr/bin/env python3

import os
import asyncio
import aiohttp
import json
import warnings
from datetime import datetime, timezone

from kasa import Discover, KasaException
from kasa.credentials import Credentials

# ==================================================
# CONFIG
# ==================================================

POLL_INTERVAL = 30          # seconds
DISCOVERY_INTERVAL = 300    # re-discover every 5 minutes

KASA_EMAIL = os.getenv("KASA_EMAIL")
KASA_PASSWORD = os.getenv("KASA_PASSWORD")
GS_POST_URL = os.getenv("GS_POST_URL")

if not KASA_EMAIL or not KASA_PASSWORD:
    raise RuntimeError("KASA_EMAIL or KASA_PASSWORD not set")

if not GS_POST_URL:
    raise RuntimeError("GS_POST_URL environment variable not set")

warnings.filterwarnings("ignore")

# ==================================================
# HELPERS
# ==================================================

def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()

async def post_payload(session, payload):
    async with session.post(
        GS_POST_URL,
        json=payload,
        headers={"Content-Type": "application/json"},
        timeout=aiohttp.ClientTimeout(total=10),
    ) as resp:
        if resp.status != 200:
            text = await resp.text()
            raise RuntimeError(f"POST failed {resp.status}: {text}")

# ==================================================
# KASA DISCOVERY
# ==================================================

async def discover_devices():
    creds = Credentials(
        username=KASA_EMAIL,
        password=KASA_PASSWORD,
    )

    print("Running Kasa discovery...")
    devices = {}

    found = await Discover.discover(credentials=creds)

    for ip, dev in found.items():
        try:
            await dev.update()
            devices[dev.mac] = dev
            print(f"Discovered {dev.alias} ({dev.mac}) @ {ip}")
        except Exception as e:
            print(f"Discovery error for {ip}: {e}")

    print(f"Discovery complete: {len(devices)} devices")
    return devices

# ==================================================
# MAIN LOOP
# ==================================================

async def run_service():

    print("Kasa power service starting")

    session = aiohttp.ClientSession()
    devices = await discover_devices()
    last_discovery = asyncio.get_event_loop().time()

    try:
        while True:

            # periodic rediscovery
            now = asyncio.get_event_loop().time()
            if now - last_discovery > DISCOVERY_INTERVAL:
                devices = await discover_devices()
                last_discovery = now

            for mac, dev in list(devices.items()):
                try:
                    await dev.update()

                    energy = dev.modules.get("Energy")
                    if not energy:
                        continue

                    status = energy.status

                    payload = {
                        "source": "kasa",
                        "time": utc_now_iso(),
                        "mac": dev.mac,
                        "device": dev.alias,
                        "model": dev.model,
                        "power_w": float(status.power),
                        "voltage_v": float(status.voltage),
                        "current_a": float(status.current),
                        "relay_on": bool(dev.is_on),
                        "rssi_dbm": dev.rssi,
                    }

                    print(
                        f"POSTING KASA: {dev.alias} "
                        f"{payload['power_w']:.2f} W"
                    )

                    await post_payload(session, payload)

                except KasaException as e:
                    print(f"{dev.alias} ERROR:", e)

                except Exception as e:
                    print(f"Unexpected error for {dev.alias}: {e}")

            await asyncio.sleep(POLL_INTERVAL)

    finally:
        for dev in devices.values():
            try:
                await dev.close()
            except Exception:
                pass

        await session.close()

# ==================================================
# ENTRY POINT
# ==================================================

if __name__ == "__main__":
    asyncio.run(run_service())