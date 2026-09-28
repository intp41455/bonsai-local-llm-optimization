# -*- coding: utf-8 -*-
r"""阶段 G：批量驱动 12 项任务并自动验收，结果落 results.jsonl。

用法:
  python run_all.py B --tasks 1,3,4,5,6,7,8,9,11,12
  python run_all.py B-t11 --tasks 11
顺序执行、串行推理（后端 -np 1），不并行。
"""
import json
import os
import re
import subprocess
import sys
import time

BENCH = r"D:\Bonsai-demo\bench"
HARNESS = os.path.join(BENCH, "bench_harness.py")
CHECK = os.path.join(BENCH, "check_tasks.py")
FIX = os.path.join(BENCH, "fixtures")
PRESET = {"count": 3, "amount": 350}


def prep(cfg):
    run = os.path.join(BENCH, "runs", cfg)
    os.makedirs(os.path.join(run, "results"), exist_ok=True)
    if cfg.endswith("t11"):
        with open(os.path.join(run, "results", "sales.json"), "w", encoding="utf-8") as f:
            f.write(json.dumps(PRESET, ensure_ascii=False, indent=2) + "\n")
    return run


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    cfg = sys.argv[1]
    tasks = [int(x) for x in sys.argv[3].split(",")]
    run = prep(cfg)
    out = os.path.join(BENCH, "results.jsonl")
    print("== 批量运行 cfg=%s 目录=%s 任务=%s" % (cfg, run, tasks))
    for t in tasks:
        t0 = time.time()
        log = os.path.join(run, "results", "_harness_task%d.log" % t)
        with open(log, "w", encoding="utf-8") as lf:
            subprocess.run([sys.executable, HARNESS, "--run-dir", run, "--task", str(t),
                            "--max-rounds", "16", "--time-cap", "1500"],
                           stdout=lf, stderr=subprocess.STDOUT)
        try:
            rj = json.load(open(os.path.join(run, "results", "_run_task%d.json" % t), encoding="utf-8"))
        except Exception as e:
            rj = {"error": repr(e)}
        p = subprocess.run([sys.executable, CHECK, run, str(t)],
                           capture_output=True, text=True)
        txt = p.stdout
        npass = 0
        nfail = 0
        m = re.search(r"结果:\s*(\d+)\s*通过\s*/\s*(\d+)\s*失败", txt)
        if m:
            npass, nfail = int(m.group(1)), int(m.group(2))
        else:
            print("  任务%-3d !! 验收脚本未给出结果，stdout 前 300 字: %s" % (t, txt[:300]))
        rec = {"cfg": cfg, "task": t, "pass": npass, "fail": nfail,
               "ok": (nfail == 0), "wall_s": round(time.time() - t0, 1),
               "stop_reason": rj.get("stop_reason"), "rounds": rj.get("rounds"),
               "tool_retries": rj.get("tool_retries"),
               "prompt_n": rj.get("prompt_n"), "cache_n": rj.get("cache_n"),
               "decode_tps": rj.get("decode_tps"), "finish_reasons": rj.get("finish_reasons"),
               "checks": [ln.strip() for ln in txt.splitlines() if ln.strip().startswith("FAIL")],
               "at": time.strftime("%Y-%m-%d %H:%M:%S")}
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print("  任务%-3d %s  %d通过/%d失败  墙钟%.0fs stop=%s 轮=%s"
              % (t, "OK  " if rec["ok"] else "FAIL", npass, nfail, rec["wall_s"],
                 rec["stop_reason"], rec["rounds"]))
        for c in rec["checks"]:
            print("       " + c)
    print("== 全部结束，汇总: %s" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())