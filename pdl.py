#!/usr/bin/env python3
import os, sys, subprocess, urllib.request, json, time

ASSET_ID = sys.argv[1]      # GitHub asset id
OUT = sys.argv[2]           # output file
CHUNKS = int(sys.argv[3]) if len(sys.argv) > 3 else 16

API = f"https://api.github.com/repos/PrismML-Eng/llama.cpp/releases/assets/{ASSET_ID}"
HEADERS = {"Accept": "application/octet-stream",
           "User-Agent": "Mozilla/5.0"}

def get_size_and_url():
    req = urllib.request.Request(API, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=30) as r:
        # follow redirect manually to get CDN url + size
        cdn = r.geturl()
        data = r.read()
    return cdn, len(data)

# Get CDN url (redirect target) and size
import http.client, urllib.parse
req = urllib.request.Request(API, headers=HEADERS)
req.get_method = lambda: "GET"
resp = urllib.request.urlopen(req, timeout=30)
cdn = resp.geturl()
total = int(resp.headers.get("Content-Length", "0"))
print(f"CDN: {cdn[:80]}...")
print(f"Total size: {total}")

# If we already have the full file, skip
if os.path.exists(OUT) and os.path.getsize(OUT) >= total and total > 0:
    print("Already complete, skipping.")
    sys.exit(0)

part_dir = OUT + ".parts"
os.makedirs(part_dir, exist_ok=True)

step = total // CHUNKS
ranges = []
for i in range(CHUNKS):
    s = i * step
    e = total - 1 if i == CHUNKS - 1 else s + step - 1
    ranges.append((i, s, e))

def download_chunk(i, s, e):
    part = os.path.join(part_dir, f"chunk_{i:03d}.part")
    if os.path.exists(part) and os.path.getsize(part) == (e - s + 1):
        return True
    curl = ["curl", "-s", "--ssl-no-revoke", "-L",
            "-H", "Accept: application/octet-stream",
            "-r", f"{s}-{e}", "-o", part, cdn]
    for attempt in range(8):
        try:
            subprocess.run(curl, timeout=300, check=True)
            if os.path.exists(part) and os.path.getsize(part) == (e - s + 1):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False

# Launch all chunks in parallel
import concurrent.futures
ok = True
with concurrent.futures.ThreadPoolExecutor(max_workers=CHUNKS) as ex:
    futs = [ex.submit(download_chunk, i, s, e) for (i, s, e) in ranges]
    for f in concurrent.futures.as_completed(futs):
        if not f.result():
            ok = False

if not ok:
    print("SOME CHUNKS FAILED")
    sys.exit(1)

# Concatenate
with open(OUT, "wb") as out:
    for i in range(CHUNKS):
        part = os.path.join(part_dir, f"chunk_{i:03d}.part")
        with open(part, "rb") as p:
            out.write(p.read())
        os.remove(part)
print(f"Concatenated -> {OUT}, size={os.path.getsize(OUT)} (expected {total})")
