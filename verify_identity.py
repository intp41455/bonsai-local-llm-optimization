"""无损性验证：开了 MTP 草稿头的 greedy 输出，必须与不开逐字节一致。

前提：GGML_CUDA_BATCH_INVARIANT=1（让 1 列与多列 PTQ1_0 kernel 用完全相同的算术）。
方法：同一 prompt、temperature=0、固定 seed，分别开/关 spec，比对 content 的 sha256。

同时复测 B 档（K=1）的稳定性。
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8899
BASE = f"http://127.0.0.1:{PORT}"

COMMON = [
    "-ngl", "99", "-fa", "on", "-np", "1", "-b", "2048", "-ub", "512",
    "-c", "32768", "-ctk", "q4_0", "-ctv", "q4_0",
    "--jinja", "--metrics", "-n", "24576",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--reasoning-budget-message", "Now produce the complete answer.",
]

SPEC_ON = ["--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
           "--spec-draft-depth-max", "24576",
           "-ctkd", "q4_0", "-ctvd", "q4_0", "--backend-sampling"]
SPEC_OFF = ["--backend-sampling"]

PROMPTS = [
    "Write a Python function that merges two sorted lists. Code only.",
    "Write a bash one-liner that finds the 10 largest files under /var.",
    "List the first 5 prime numbers, comma separated, nothing else.",
]


def kill() -> None:
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"], capture_output=True)
    time.sleep(3)


def wait_ready(proc, timeout=420) -> bool:
    t0 = time.time()
    while time.time() - t0 < timeout:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"{BASE}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def post(path, payload, timeout=900):
    req = urllib.request.Request(f"{BASE}{path}", data=json.dumps(payload).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def run(tag: str, spec: list[str]) -> dict:
    print(f"\n--- arm {tag} ---", flush=True)
    log = open(ROOT / f"id_{tag}.log", "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    cmd = [str(BIN / "llama-server.exe"), "-m", str(MODEL),
           "--host", "127.0.0.1", "--port", str(PORT)] + COMMON + spec
    proc = subprocess.Popen(cmd, cwd=str(BIN), stdout=log,
                            stderr=subprocess.STDOUT, env=env)
    res = {"tag": tag, "items": []}
    try:
        if not wait_ready(proc):
            print("  !! 启动失败", flush=True)
            return res
        time.sleep(2)
        for i, p in enumerate(PROMPTS):
            r = post("/completion", {
                "prompt": p, "n_predict": 200, "temperature": 0.0,
                "seed": 42, "cache_prompt": False, "stream": False})
            txt = r.get("content", "") or ""
            t = r.get("timings", {})
            res["items"].append({
                "i": i, "sha": hashlib.sha256(txt.encode()).hexdigest()[:16],
                "len": len(txt), "decode": t.get("predicted_per_second", 0.0),
                "acc": (t.get("draft_n_accepted", 0) / t["draft_n"])
                       if t.get("draft_n") else None,
            })
            print(f"  p{i} sha={res['items'][-1]['sha']} len={len(txt):4d} "
                  f"dec={res['items'][-1]['decode']:.2f} "
                  f"acc={res['items'][-1]['acc'] if res['items'][-1]['acc'] is None else round(res['items'][-1]['acc'],3)}",
                  flush=True)
    finally:
        kill()
        log.close()
    return res


def main() -> None:
    a = run("mtp-on", SPEC_ON)
    b = run("mtp-off", SPEC_OFF)
    print(f"\n{'='*64}\n### 无损性判定 (greedy, temp=0, seed=42)\n{'='*64}")
    same = 0
    for x, y in zip(a["items"], b["items"]):
        ok = x["sha"] == y["sha"]
        same += ok
        print(f"  prompt {x['i']}: MTP={x['sha']}  no-MTP={y['sha']}  "
              f"{'✓ 逐字节一致' if ok else '✗ 不一致'}")
    print(f"\n  {same}/{len(a['items'])} 条提示词输出逐字节一致")
    if same == len(a["items"]):
        print("  => MTP 投机解码严格无损（batch invariant 生效）")
    ds = [x["decode"] for x in a["items"] if x["decode"]]
    if ds:
        print(f"  MTP 平均 decode {sum(ds)/len(ds):.2f} t/s")
    (ROOT / "identity_result.json").write_text(
        json.dumps({"on": a, "off": b}, indent=2, ensure_ascii=False),
        encoding="utf-8")


if __name__ == "__main__":
    main()
