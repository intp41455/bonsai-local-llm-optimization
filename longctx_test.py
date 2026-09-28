"""Phase 2 · 长上下文多处检索（大海捞针，三档深度）。

把三条唯一事实分别埋在约 4k / 12k / 20k token 深度，一次性提问，
检验能否全部召回 —— 给出「可用深度」的直接证据。
"""
import json
import os
import subprocess
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8080
LOG = ROOT / "longctx.log"

ARGS = [
    "-m", str(MODEL),
    "-ngl", "99", "-fa", "on", "-np", "1",
    "-c", "32768", "-b", "2048", "-ub", "512",
    "-ctk", "q4_0", "-ctv", "q4_0",
    "--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
    "--spec-draft-depth-max", "4096",
    "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling", "--jinja",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--reasoning-budget-message", "Now produce the complete answer.",
    "-n", "24576",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
    "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bonsai-2-27b",
    "--metrics",
]

BODY = (ROOT / "surgery" / "docs" / "QUALITY.md").read_text(encoding="utf-8", errors="replace")
# 英文技术文档约 4 字符/token
def seg(n):
    return (BODY + "\n\n") * n

NEEDLES = [
    (1, "【关键标记甲】本批次试验的追溯编号为 ZQ-90217，签章人为林思远。",
     ["ZQ-90217", "林思远"], 4000),
    (2, "【关键标记乙】环境试验箱的设备编号为 ENV-3315，校准有效期至 2027 年 4 月。",
     ["ENV-3315", "2027"], 12000),
    (3, "【关键标记丙】客户验收负责人为周予同，联系电话尾号为 8642。",
     ["周予同", "8642"], 20000),
]

samples = []
loglines = []


def log(s):
    print(s, flush=True)
    loglines.append(s)


def kill():
    subprocess.run(["taskkill", "/F", "/IM", "llama-server.exe"],
                   capture_output=True, text=True, encoding="utf-8", errors="replace")


def gpu_sampler(stop_evt):
    while not stop_evt.is_set():
        try:
            out = subprocess.run(
                ["nvidia-smi", "--query-gpu=clocks.mem,power.draw,memory.used",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5,
                encoding="utf-8", errors="replace").stdout.strip()
            if out:
                samples.append(out)
        except Exception:
            pass
        stop_evt.wait(2)


def post(path, payload, timeout=900):
    req = urllib.request.Request(
        f"http://127.0.0.1:{PORT}{path}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def wait_ready(proc, limit=180):
    t0 = time.time()
    while time.time() - t0 < limit:
        if proc.poll() is not None:
            return False
        try:
            with urllib.request.urlopen(f"http://127.0.0.1:{PORT}/health", timeout=3) as r:
                if r.status == 200:
                    return True
        except Exception:
            pass
        time.sleep(2)
    return False


def build_prompt():
    """段1(甲) + 段2(乙) + 段3(丙)，深度递增。"""
    p = "下面是一份技术资料汇编，请完整阅读。\n\n"
    p += seg(1) + "\n" + NEEDLES[0][1] + "\n\n"
    p += seg(2) + "\n" + NEEDLES[1][1] + "\n\n"
    p += seg(2) + "\n" + NEEDLES[2][1] + "\n\n"
    p += seg(1)
    return p


def main():
    kill()
    time.sleep(4)
    lf = open(LOG, "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    log("启动服务 ...")
    proc = subprocess.Popen([str(BIN / "llama-server.exe")] + ARGS,
                            cwd=str(BIN), stdout=lf, stderr=subprocess.STDOUT, env=env)
    try:
        if not wait_ready(proc):
            log("  !! 启动失败")
            return
        log("  服务就绪")

        stop = threading.Event()
        threading.Thread(target=gpu_sampler, args=(stop,), daemon=True).start()

        prompt = build_prompt()
        log(f"  构造前缀: {len(prompt):,} 字符")
        q = ("在上面这份资料的三处【关键标记】中，分别记录了哪些信息？"
             "请逐条列出甲、乙、丙三处的全部关键内容（编号、人名、日期、电话尾号）。")

        t0 = time.time()
        try:
            r = post("/v1/chat/completions", {
                "messages": [{"role": "user", "content": prompt},
                             {"role": "assistant", "content": "已通读。"},
                             {"role": "user", "content": q}],
                "max_tokens": 600, "temperature": 0.0, "stream": False})
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            log(f"  !! HTTP {e.code}: {body}")
            return
        dt = time.time() - t0

        ans = ((r.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
        ti = r.get("timings") or {}
        pn = ti.get("prompt_n", 0) or 0
        pp = ti.get("prompt_per_second", 0.0) or 0.0
        dec = ti.get("predicted_per_second", 0.0) or 0.0
        dn = ti.get("draft_n", 0) or 0
        da = ti.get("draft_n_accepted", 0) or 0
        acc = (da / dn) if dn else float("nan")

        log(f"\n{'='*76}\n### Phase 2 · 长上下文多处检索\n{'='*76}")
        log(f"  前缀 {pn:,} token（占 32768 上限的 {100*pn/32768:.0f}%）")
        log(f"  prefill {pp:.0f} t/s｜首字延迟 {dt:.1f}s")
        log(f"  decode {dec:.2f} t/s｜接受率 {acc:.3f}\n")

        allok = True
        for idx, (_, _, keys, depth) in enumerate(NEEDLES, 1):
            hit = [k for k in keys if k in ans]
            ok = len(hit) == len(keys)
            allok &= ok
            log(f"  标记{'甲乙丙'[idx-1]}（约 {depth:,} tok 深度）: "
                f"{'OK' if ok else 'MISS'}  命中 {hit}/{keys}")

        log(f"\n  综合: {'三处全部召回 ✅' if allok else '存在遗漏 ❌'}")
        log(f"\n  完整回答:\n  {ans[:900]}")
        log(f"\n  用时 {dt:.1f}s｜显存占用 "
            f"{subprocess.run(['nvidia-smi','--query-gpu=memory.used','--format=csv,noheader,nounits'],capture_output=True,text=True,encoding='utf-8',errors='replace').stdout.strip()} MiB")

        json.dump({"prompt_n": pn, "prefill": pp, "decode": dec, "acc": acc,
                   "answer": ans, "sec": dt, "all_ok": allok, "samples": samples},
                  open(ROOT / "longctx.json", "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    finally:
        kill()
        lf.close()
        (ROOT / "longctx_result.log").write_text("\n".join(loglines),
                                                 encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
