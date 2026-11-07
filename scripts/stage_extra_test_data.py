"""Stage additional test data prior to freeze:
1. 2 unused AMI meetings: EN2004a and EN2005a into test_data/ami/
2. 100 LibriSpeech test-clean flac files into test_data/librispeech/
Never transcribes anything.
"""
import os
import subprocess
import tarfile
from pathlib import Path
import urllib.request

ROOT = Path(__file__).resolve().parent.parent
TEST_DIR = ROOT / "test_data"
TEST_AMI = TEST_DIR / "ami"
TEST_LIBRI = TEST_DIR / "librispeech"

TEST_AMI.mkdir(parents=True, exist_ok=True)
TEST_LIBRI.mkdir(parents=True, exist_ok=True)

# 1. Download extra AMI meetings
extra_meetings = ["EN2004a", "EN2005a"]
for m in extra_meetings:
    dest = TEST_AMI / f"{m}.Mix-Headset.wav"
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"AMI {m} already staged: {dest.name} ({dest.stat().st_size} bytes)")
        continue
    url = f"https://groups.inf.ed.ac.uk/ami/AMICorpusMirror//amicorpus/{m}/audio/{m}.Mix-Headset.wav"
    print(f"Downloading AMI {m} from {url}...")
    subprocess.run(["curl", "-sSL", "-C", "-", "--retry", "10", "--retry-delay", "3", "-o", str(dest), url], check=True)
    print(f"  -> Staged {dest.name} ({dest.stat().st_size} bytes)")

# 2. Extract 100 LibriSpeech test-clean flac files
existing_libri = list(TEST_LIBRI.glob("*.flac"))
if len(existing_libri) >= 100:
    print(f"LibriSpeech test-clean already staged: {len(existing_libri)} files.")
else:
    print("Extracting 100 files from LibriSpeech test-clean...")
    url = "https://www.openslr.org/resources/12/test-clean.tar.gz"
    # Stream tar to extract first 100 flac files
    proc = subprocess.Popen(["curl", "-sSL", url], stdout=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout, mode="r|gz") as tar:
        count = 0
        for member in tar:
            if member.name.endswith(".flac"):
                # Extract file name
                fname = Path(member.name).name
                dest = TEST_LIBRI / fname
                f = tar.extractfile(member)
                if f:
                    with open(dest, "wb") as out:
                        out.write(f.read())
                    count += 1
                    if count % 20 == 0:
                        print(f"  Extracted [{count}/100] LibriSpeech test-clean files...")
                    if count >= 100:
                        break
    proc.terminate()
    print(f"Completed staging {count} LibriSpeech test-clean files.")

print("\nExtra test data staged successfully. None transcribed.")
