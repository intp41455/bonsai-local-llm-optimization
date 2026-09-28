#!/usr/bin/env python3
import os, sys, subprocess, urllib.request, concurrent.futures, time

ASSET_ID = sys.argv[1]      # GitHub asset id
OUT = sys.argv[2]           # output file
CHUNK_MB = int(sys.argv[3]) if len(sys.argv) > 3 else 2   # small chunks avoid proxy reset
CONC = int(sys.argv[4]) if len(sys.argv) > 4 else 12

API = f"https://api.github.com/repos/PrismML-Eng/llama.cpp/releases/assets/{ASSET_ID}"
HEADERS = {"Accept": "application/octet-stream",
           "User-Agent": "Mozilla/5.0"}

# Get CDN url (redirect target) and size
req = urllib.request.Request(API, headers=HEADERS)
resp = urllib.request.urlopen(req, timeout=30)
cdn = resp.geturl()
total = int(resp.headers.get("Content-Length", "0"))
print(f"CDN len: {total}")

if os.path.exists(OUT) and os.path.getsize(OUT) >= total and total > 0:
    print("Already complete, skipping.")
    sys.exit(0)

part_dir = OUT + ".parts"
os.makedirs(part_dir, exist_ok=True)

# chunk size in bytes
step = CHUNK_MB * 1024 * 1024
ranges = []
for i in range(0, total, step):
    s = i
    e = min(i + step - 1, total - 1)
    ranges.append((len(ranges), s, e))
print(f"Total chunks: {len(ranges)} of {CHUNK_MB}MB each, concurrency={CONC}")

def download_chunk(idx, s, e):
    part = os.path.join(part_dir, f"chunk_{idx:04d}.part")
    target = e - s + 1
    # resume until exact size reached
    for attempt in range(40):
        cur = os.path.getsize(part) if os.path.exists(part) else 0
        if cur == target:
            return True
        start = s + cur
        if start > e:
            return True
        curl = ["curl", "-s", "--ssl-no-revoke", "-L",
                "-H", "Accept: application/octet-stream",
                "-r", f"{start}-{e}", "-C", "-", "-o", part, cdn]
        try:
            subprocess.run(curl, timeout=120, check=True)
        except Exception:
            time.sleep(1)
            continue
        if os.path.exists(part) and os.path.getsize(part) == target:
            return True
    return False

ok = True
with concurrent.futures.ThreadPoolExecutor(max_workers=CONC) as ex:
    futs = [ex.submit(download_chunk, i, s, e) for (i, s, e) in ranges]
    for f in concurrent.futures.as_completed(futs):
        if not f.result():
            ok = False

if not ok:
    print("SOME CHUNKS FAILED")
    sys.exit(1)

with open(OUT, "wb") as out:
    for i in range(len(ranges)):
        part = os.path.join(part_dir, f"chunk_{i:04d}.part")
        with open(part, "rb") as p:
            out.write(p.read())
        os.remove(part)
print(f"Concatenated -> {OUT}, size={os.path.getsize(OUT)} (expected {total})")
