# -*- coding: utf-8 -*-
r"""阶段 G：第 10 项（多轮与断点延续）专用驱动 —— 普通五轮 + 固定日志切片。

§14.2 第10项要求：读 notes.txt 并记住约束 -> 完成五轮日志摘要 -> 最后按最初约束交付总结。
切片固定、哈希入档；每轮计数入档。

【能力边界，如实标注】方案要求的“压缩边界五轮”需要一个会做历史压缩的客户端（WorkBuddy/Pi）。
本脚本是本地 harness，没有压缩器，**不实现压缩变体**；该项在报告中标记为“未实现（受 harness 能力限制）”，
不谎报已验。

用法: python bench_multiturn.py --run-dir D:\Bonsai-demo\bench\runs\B-t10
"""
import argparse
import hashlib
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import bench_harness as H   # noqa: E402

SLICES = [(1, 200), (201, 400), (401, 600), (601, 800), (801, 1000)]
# 方案 §14.2 第10项：固定切片、五轮；1000 行恰好被 5 段 200 行覆盖。
ROUND_PROMPTS = [
    "本轮请只回报你读到的切片要点，不要写文件：",
    "继续摘要本轮切片，不要写文件：",
    "继续摘要本轮切片，不要写文件：",
    "继续摘要本轮切片，不要写文件：",
    "继续摘要本轮切片，不要写文件：",
]


def make_slices(run_dir, out_dir):
    src = os.path.join(run_dir, "logs", "run.log")
    lines = open(src, encoding="utf-8").read().splitlines()
    assert len(lines) == 1000, len(lines)
    os.makedirs(out_dir, exist_ok=True)
    manifest = []
    for i, (a, b) in enumerate(SLICES, 1):
        body = "\n".join(lines[a - 1:b]) + "\n"
        name = "slice%d.log" % i
        p = os.path.join(out_dir, name)
        with open(p, "w", encoding="utf-8", newline="") as f:
            f.write(body)
        manifest.append({"name": name, "lines": [a, b],
                         "sha256": hashlib.sha256(body.encode("utf-8")).hexdigest(),
                         "chars": len(body)})
    with open(os.path.join(out_dir, "MANIFEST.json"), "w", encoding="utf-8") as f:
        json.dump({"_note": "第10项固定切片（方案 §14.2），后续复用",
                   "slices": manifest}, f, ensure_ascii=False, indent=2)
    return manifest


def main():
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser()
    ap.add_argument("--run-dir", required=True)
    ap.add_argument("--time-cap", type=float, default=1500.0)
    a = ap.parse_args()
    H.cfg["run_dir"] = a.run_dir
    os.makedirs(os.path.join(a.run_dir, "results"), exist_ok=True)
    sdir = os.path.join(a.run_dir, "slices")
    man = make_slices(a.run_dir, sdir)
    print("== 第10项 普通五轮 ==")
    for m in man:
        print("   切片 %-9s 行%-10s %6d 字符  %s"
              % (m["name"], m["lines"], m["chars"], m["sha256"][:16]))

    notes = open(os.path.join(a.run_dir, "notes.txt"), encoding="utf-8").read()
    msgs = [{"role": "system", "content": H.SYS_PROMPT},
            {"role": "user", "content": "请读 notes.txt 并记住其中全部约束：\n" + notes}]
    per_round = []
    off = H.log_offset()
    for i, (slo, shi) in enumerate(SLICES, 1):
        body = open(os.path.join(sdir, "slice%d.log" % i), encoding="utf-8").read()
        last = (i == len(SLICES))
        ask = ("最后一轮：按最初约束交付总结，写入 results/final-summary.md，"
               "并确保其中列出最初 notes.txt 的五条约束。" if last else ROUND_PROMPTS[i - 1])
        msgs.append({"role": "user", "content": "%s\n（切片 %d，原始行 %d-%d）\n%s"
                     % (ask, i, slo, shi, body)})
        r = H.call_model(msgs, timeout=max(120.0, a.time_cap))
        print("   [轮 %d] wall=%.1fs ttft=%s finish=%s 工具=%d"
              % (i, r["wall_s"], ("%.1fs" % r["ttft_s"]) if r["ttft_s"] else "-",
                 r["finish"], len(r["tool_calls"])))
        per_round.append({"round": i, "wall_s": round(r["wall_s"], 2),
                          "ttft_s": (round(r["ttft_s"], 2) if r["ttft_s"] else None),
                          "finish": r["finish"], "content_chars": len(r["content"]),
                          "reasoning_chars": len(r["reasoning"]),
                          "tool_calls": [t["name"] for t in r["tool_calls"]]})
        msgs.append({"role": "assistant", "content": r["content"] or None})
        for j, t in enumerate(r["tool_calls"]):
            try:
                res = H.do_tool(t["name"], json.loads(t["args"] or "{}"))
            except Exception as e:
                res = "ERROR: %s: %s" % (type(e).__name__, e)
            print("        -> %s => %s" % (t["name"], res.replace("\n", " | ")[:90]))
            msgs.append({"role": "tool", "tool_call_id": t["id"] or ("call_%d" % j),
                         "content": res[:8000]})
        if not last:
            msgs.append({"role": "user", "content": "继续下一轮。"})

    # 受限收尾轮：五轮摘要计数不变，仅补完模型在末轮已发起、但被原驱动截断的工具链。
    tail_rounds = []
    for k in range(1, 7):
        r = H.call_model(msgs, timeout=max(120.0, a.time_cap))
        print("   [收尾 %d] wall=%.1fs finish=%s 工具=%d"
              % (k, r["wall_s"], r["finish"], len(r["tool_calls"])))
        tail_rounds.append({"round": k, "wall_s": round(r["wall_s"], 2),
                            "finish": r["finish"], "content_chars": len(r["content"]),
                            "tool_calls": [t["name"] for t in r["tool_calls"]]})
        msgs.append({"role": "assistant", "content": r["content"] or None})
        if not r["tool_calls"]:
            break
        for j, t in enumerate(r["tool_calls"]):
            try:
                res = H.do_tool(t["name"], json.loads(t["args"] or "{}"))
            except Exception as e:
                res = "ERROR: %s: %s" % (type(e).__name__, e)
            print("        -> %s => %s" % (t["name"], res.replace("\n", " | ")[:90]))
            msgs.append({"role": "tool", "tool_call_id": t["id"] or ("call_%d" % j),
                         "content": res[:8000]})
        msgs.append({"role": "user", "content": "继续完成交付。"})

    recs = [x for x in H.log_delta(off) if (x.get("path") or "").endswith("/chat/completions")]
    fs = os.path.join(a.run_dir, "results", "final-summary.md")
    out = {"harness": "local-script (无压缩器)", "task": 10, "variant": "normal-5round",
           "compression_variant": "未实现（本地 harness 无压缩器）",
           "tail_rounds": tail_rounds,
           "tail_note": "五轮摘要之后补的收尾轮（原驱动在末轮直接退出，会把模型已发起的工具链截断）",
           "final_summary_exists": os.path.exists(fs),
           "slices": man, "rounds": per_round, "proxy_records": len(recs),
           "prompt_n": [x.get("prompt_n") for x in recs],
           "cache_n": [x.get("cache_n") for x in recs],
           "decode_tps": [x.get("decode_tps") for x in recs],
           "finish_reasons": [x.get("finish_reason") for x in recs],
           "at": time_str()}
    p = os.path.join(a.run_dir, "results", "_run_task10.json")
    with open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print("\n== 结束，记录: %s" % p)
    print("   验收: python check_tasks.py \"%s\" 10" % a.run_dir)
    return 0


def time_str():
    import time
    return time.strftime("%Y-%m-%d %H:%M:%S")


if __name__ == "__main__":
    sys.exit(main())