#!/usr/bin/env python3
"""
Pont série ESP32 → API Django GérioTrack
----------------------------------------
L'ESP32 envoie une ligne JSON (USB) ; ce script la relaie vers :
  POST http://127.0.0.1:8000/api/sensors/ingest/

Usage :
  python serial_bridge.py
  python serial_bridge.py --port COM5
  python serial_bridge.py --list

Prérequis : pip install pyserial requests
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime

try:
    import serial
    from serial.tools import list_ports
except ImportError:
    print("Installez pyserial :  pip install pyserial")
    sys.exit(1)

try:
    import requests
except ImportError:
    print("Installez requests :  pip install requests")
    sys.exit(1)


DEFAULT_API = "http://127.0.0.1:8000/api/sensors/ingest/"
DEFAULT_BAUD = 115200
DEFAULT_DEVICE = "ESP32-001"
DEFAULT_PATIENT = "P001"


def list_serial_ports() -> list:
    return list(list_ports.comports())


def pick_port(preferred: str | None) -> str:
    ports = list_serial_ports()
    if preferred:
        return preferred
    if not ports:
        raise SystemExit(
            "Aucun port COM trouvé. Branchez l'ESP32 en USB, "
            "puis relancez avec --list pour voir les ports."
        )
    # Préférer un port qui ressemble à un ESP / Silicon Labs / CP210x / CH340
    keywords = ("silicon", "cp210", "ch340", "usb serial", "uart", "esp", "wch")
    for p in ports:
        blob = f"{p.description} {p.manufacturer or ''} {p.device}".lower()
        if any(k in blob for k in keywords):
            return p.device
    return ports[0].device


def normalize_payload(raw: dict, device_id: str, patient_id: str) -> dict:
    """Accepte le JSON ESP32 et le normalise pour /api/sensors/ingest/."""
    out = {
        "device_id": raw.get("device_id") or device_id,
        "patient_id": raw.get("patient_id") or patient_id,
    }

    motion = raw.get("motion") or raw.get("mpu") or {}
    if not motion and any(k in raw for k in ("ax", "ay", "az", "gx", "gy", "gz")):
        motion = {
            "ax": raw.get("ax"), "ay": raw.get("ay"), "az": raw.get("az"),
            "gx": raw.get("gx"), "gy": raw.get("gy"), "gz": raw.get("gz"),
        }
    if motion:
        out["motion"] = motion

    env = raw.get("env") or raw.get("dht") or {}
    if not env and ("temperature" in raw or "humidity" in raw or "temp" in raw):
        env = {
            "temperature": raw.get("temperature", raw.get("temp")),
            "humidity": raw.get("humidity", raw.get("hum")),
        }
    if env:
        out["env"] = env

    gps = raw.get("gps") or {}
    if not gps and ("lat" in raw or "latitude" in raw):
        gps = {
            "lat": raw.get("lat", raw.get("latitude")),
            "lon": raw.get("lon", raw.get("lng", raw.get("longitude"))),
            "altitude": raw.get("altitude", raw.get("alt")),
            "speed": raw.get("speed"),
            "accuracy": raw.get("accuracy", raw.get("hdop")),
        }
    if gps and (gps.get("lat") is not None or gps.get("lon") is not None):
        out["gps"] = gps

    ecg = raw.get("ecg") or {}
    if not ecg and any(k in raw for k in ("ecg_raw", "bpm", "heart_rate")):
        ecg = {
            "raw": raw.get("ecg_raw", raw.get("ecg")),
            "bpm": raw.get("bpm", raw.get("heart_rate")),
        }
    if ecg:
        out["ecg_raw"] = ecg.get("raw", ecg.get("ecg_raw"))
        out["bpm"] = ecg.get("bpm", ecg.get("heart_rate"))

    return out


def post_ingest(api: str, payload: dict) -> bool:
    try:
        r = requests.post(api, json=payload, timeout=3)
        if r.status_code >= 400:
            print(f"  ✗ API {r.status_code}: {r.text[:200]}")
            return False
        return True
    except requests.RequestException as exc:
        print(f"  ✗ API injoignable ({exc}). Django tourne-t-il ?")
        return False


def run_bridge(port: str, baud: int, api: str, device_id: str, patient_id: str) -> None:
    print(f"[{datetime.now():%H:%M:%S}] Ouverture {port} @ {baud} → {api}")
    print(f"  device={device_id}  patient={patient_id}")
    print("  Ctrl+C pour arrêter.\n")

    ser = serial.Serial(port, baud, timeout=1)
    time.sleep(2)  # reset USB ESP32
    ser.reset_input_buffer()

    ok_count = 0
    fail_count = 0
    try:
        while True:
            line = ser.readline()
            if not line:
                continue
            try:
                text = line.decode("utf-8", errors="ignore").strip()
            except Exception:
                continue
            if not text or not text.startswith("{"):
                # Affiche les logs non-JSON du firmware (boot, erreurs capteurs…)
                if text:
                    print(f"  · ESP: {text}")
                continue
            try:
                raw = json.loads(text)
            except json.JSONDecodeError:
                print(f"  · JSON invalide: {text[:120]}")
                continue

            payload = normalize_payload(raw, device_id, patient_id)
            if post_ingest(api, payload):
                ok_count += 1
                m = payload.get("motion") or {}
                e = payload.get("env") or {}
                g = payload.get("gps") or {}
                bits = [
                    f"ax={m.get('ax', '?')}",
                    f"t={e.get('temperature', '?')}",
                    f"gps={g.get('lat', '—')}",
                ]
                print(f"  ✓ #{ok_count} {' · '.join(bits)}")
            else:
                fail_count += 1
                if fail_count >= 5:
                    print("  Trop d'échecs API — vérifiez `python manage.py runserver`")
                    fail_count = 0
    except KeyboardInterrupt:
        print(f"\nArrêt. Frames envoyées : {ok_count}")
    finally:
        ser.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Pont série ESP32 → GérioTrack")
    parser.add_argument("--port", help="Port COM (ex: COM5). Auto si omis.")
    parser.add_argument("--baud", type=int, default=DEFAULT_BAUD)
    parser.add_argument("--api", default=DEFAULT_API)
    parser.add_argument("--device-id", default=DEFAULT_DEVICE)
    parser.add_argument("--patient-id", default=DEFAULT_PATIENT)
    parser.add_argument("--list", action="store_true", help="Lister les ports COM")
    args = parser.parse_args()

    if args.list:
        ports = list_serial_ports()
        if not ports:
            print("Aucun port série détecté.")
            return
        print("Ports disponibles :")
        for p in ports:
            print(f"  {p.device:8}  {p.description}  ({p.manufacturer or '?'})")
        return

    port = pick_port(args.port)
    run_bridge(port, args.baud, args.api, args.device_id, args.patient_id)


if __name__ == "__main__":
    main()
