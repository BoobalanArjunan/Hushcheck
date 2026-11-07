"""Download calibration AMI meetings.
Excludes used-up meetings (ES2002a, IS1000a, TS3003a).
"""
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CALIB_AMI = ROOT / "calibration_data" / "ami"
CALIB_AMI.mkdir(parents=True, exist_ok=True)

MEETINGS = ["EN2001a", "EN2002a", "ES2003a", "IS1001a"]

def main():
    print("=== Downloading Calibration AMI Meetings ===")
    for m in MEETINGS:
        dest = CALIB_AMI / f"{m}.Mix-Headset.wav"
        if dest.exists() and dest.stat().st_size > 1000000:
            print(f"Already downloaded: {dest.name} ({dest.stat().st_size // (1024*1024)} MB)")
            continue
        url = f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror//amicorpus/{m}/audio/{m}.Mix-Headset.wav"
        print(f"Downloading {m}.Mix-Headset.wav...")
        sys.stdout.flush()
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as resp, open(dest, "wb") as f:
            while chunk := resp.read(65536):
                f.write(chunk)
        print(f"Saved {dest.name} ({dest.stat().st_size // (1024*1024)} MB)")
        sys.stdout.flush()
        time.sleep(1)

    print("\nCalibration AMI meetings staged successfully.")

if __name__ == "__main__":
    main()

