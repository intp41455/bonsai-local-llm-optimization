#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""通用「限速 CDN」并行分块下载器。
用法: python pdlx.py <url> <out> <total_bytes> [chunk_mb] [conc]
特点: 1MB 整块 + 整块重试（不依赖续传，避免 -C - 与 -r 冲突）；
      拼接后默认不删除分块（规避沙箱 bulk safe-delete 拦截），KEEP_PARTS=0 可改为删除。
"""
import concurrent.futures, os, subprocess, sys, time

url, out, total = sys.argv[1], sys.argv[2], int(sys.argv[3])
chunk_mb = int(sys.argv[4]) if len(sys.argv) > 4 else 1
conc = int(sys.argv[5]) if len(sys.argv) > 5 else 16
keep = os.environ.get("KEEP_PARTS", "1") != "0"

if os.path.exists(out) and os.path.getsize(out) == total:
    print("already complete:", out)
    sys.exit(0)

part_dir = out + ".parts"
os.makedirs(part_dir, exist_ok=True)
step = chunk_mb * 1024 * 1024
ranges = [(i, i, min(i + step - 1, total - 1)) for i in range(0, total, step)]
print("chunks=%d x %dMB  conc=%d  total=%.1f MB" % (len(ranges), chunk_mb, conc, total / 2**20), flush=True)


def get(idx, s, e):
    part = os.path.join(part_dir, "chunk_%05d.part" % idx)
    want = e - s + 1
    if os.path.exists(part) and os.path.getsize(part) == want:
        return True
    for _ in range(40):
        try:
            subprocess.run(["curl", "-s", "--ssl-no-revoke", "-L", "--max-time", "180",
                            "-r", "%d-%d" % (s, e), "-o", part, url], timeout=200, check=True)
            if os.path.exists(part) and os.path.getsize(part) == want:
                return True
        except Exception:
            pass
        time.sleep(0.4)
    return False


t0 = time.time()
done = 0
bad = []
with concurrent.futures.ThreadPoolExecutor(max_workers=conc) as ex:
    futs = {ex.submit(get, i, s, e): i for (i, s, e) in ranges}
    for f in concurrent.futures.as_completed(futs):
        done += 1
        if not f.result():
            bad.append(futs[f])
        if done % 50 == 0:
            el = time.time() - t0
            print("  %d/%d  %.1f MB/s" % (done, len(ranges), total * done / len(ranges) / 2**20 / max(el, 1e-9)), flush=True)

if bad:
    print("FAILED chunks:", len(bad), bad[:10])
    sys.exit(1)

print("assembling...", flush=True)
with open(out, "wb") as o:
    for i in range(len(ranges)):
        with open(os.path.join(part_dir, "chunk_%05d.part" % i), "rb") as p:
            o.write(p.read())
        if not keep:
            os.remove(os.path.join(part_dir, "chunk_%05d.part" % i))
print("DONE %s size=%d expected=%d  %.1fs" % (out, os.path.getsize(out), total, time.time() - t0), flush=True)
