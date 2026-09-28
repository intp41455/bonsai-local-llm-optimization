"""长上下文多轮对话稳定性验证。

Phase 1 —— 多轮记忆保持：注入含 5 个可验证事实的项目文档，连续 7 轮追问
           （含跨轮指代），逐轮记录性能与正确性。
Phase 2 —— 长上下文检索：前缀堆到 ~20k token，提问埋在开头的事实（大海捞针）。

判定标准：每轮答案关键词命中 + 性能不出现断崖式退化 + 显存不爆。
"""
import json
import os
import re
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(r"D:/Bonsai-demo")
BIN = ROOT / "dist" / "bonsai2-8gb-combo" / "bin"
MODEL = ROOT / "models" / "bonsai2-gguf" / "27B" / "Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf"
PORT = 8080
LOG = ROOT / "multiturn.log"

ARGS = [
    "-m", str(MODEL),
    "-ngl", "99", "-fa", "on", "-np", "1",
    "-c", "32768", "-b", "2048", "-ub", "512",
    "-ctk", "q4_0", "-ctv", "q4_0",
    "--spec-type", "draft-mtp", "--spec-draft-n-max", "1",
    "--spec-draft-depth-max", "4096",
    "-ctkd", "q4_0", "-ctvd", "q4_0",
    "--backend-sampling",
    "--jinja",
    "--chat-template-kwargs", '{"reasoning_effort":"medium"}',
    "--reasoning-budget", "20480",
    "--reasoning-budget-message", "Now produce the complete answer.",
    "-n", "24576",
    "--temp", "1.0", "--top-p", "0.95", "--top-k", "20",
    "--host", "127.0.0.1", "--port", str(PORT), "--alias", "bonsai-2-27b",
    "--metrics",
]

# ---------------------------------------------------------------- 项目文档
DOC = """下面是「启明科技 2026 年度重点项目立项说明」，请通读并记住其中的全部关键信息。

项目代号：XR-7841
项目正式名称：边缘侧多模态感知终端研发
立项日期：2026 年 3 月 18 日
项目负责人：陈立（研发二部总监）
技术副负责人：苏昀
财务预算：287 万元人民币，其中硬件采购占 154 万、人力成本占 96 万、测试认证占 37 万
交付截止日期：2026 年 11 月 3 日
首批交付数量：1,200 台工程样机
目标毛利率：38%
主要供应商：深圳市锐芯微电子有限公司（负责 SoC 模组）、常州恒达精密（负责结构件）

技术指标要求：
整机功耗不高于 4.2 瓦，待机功耗不高于 0.15 瓦；端侧推理延迟不高于 45 毫秒；
工作温度范围为零下 20 摄氏度至零上 70 摄氏度；防护等级达到 IP54；
电池续航在典型工况下不低于 14 小时。

项目当前状态：已完成原理样机验证（Phase 1），正在进入小批量试产阶段（Phase 2）。
Phase 1 测试中发现的遗留问题共 3 项，其中 2 项已关闭，剩余 1 项为「低温启动时间超标」。

已识别的最大风险：主要供应商锐芯微电子的 SoC 模组存在交付延迟风险，
其 12 纳米产线排期已排至 2026 年 9 月，若延期将直接影响首批 1,200 台样机的产线验证窗口。
备选方案为启用第二供应商，但需额外 6 周认证周期。

质量要求：出厂前需完成 168 小时高温老化测试，并出具 CNAS 认可的第三方检测报告。
"""

FACTS = {
    "XR-7841": "项目代号",
    "11 月 3 日": "交付截止",
    "陈立": "负责人",
    "287 万": "预算",
    "锐芯微": "主要供应商/风险源",
    "4.2 瓦": "整机功耗指标",
    "1,200 台": "首批交付数量",
}

# 每轮 (问题, 期望命中的关键词集合, 说明)
TURNS = [
    ("这个项目的代号是什么？只回答代号本身。", {"XR-7841"}, "直接召回"),
    ("交付截止日期是哪一天？", {"11 月 3", "11月3"}, "直接召回"),
    ("负责人是谁？项目预算是多少万元？", {"陈立", "287"}, "双事实召回"),
    ("已识别的最大风险是什么？涉及哪家供应商？", {"锐芯微", "延迟"}, "语义召回"),
    ("首批要交付多少台工程样机？目标毛利率是多少？", {"1,200", "1200", "38"}, "数值召回"),
    ("请把项目代号、负责人、交付截止日期、预算这四项整理成一个 JSON 对象，"
     "键名用 code / owner / deadline / budget_cny。只输出 JSON。",
     {"XR-7841", "陈立", "287"}, "结构化整合"),
    ("回头看第一个问题，你当时的答案是什么？另外刚才 JSON 里 budget_cny 字段的值是多少？",
     {"XR-7841", "287"}, "跨轮指代"),
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
                ["nvidia-smi", "--query-gpu=clocks.sm,clocks.mem,power.draw,temperature.gpu,memory.used",
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


def strip_think(txt):
    """去掉思考内容，只留最终回答。"""
    t = re.sub(r"<\|?channel\|?>.*?(?=<\|?channel\|?>)", "", txt, flags=re.S)
    t = re.sub(r"<thought>.*?</thought>", "", t, flags=re.S)
    return t.strip()


def chat(messages, n_predict=400):
    return post("/v1/chat/completions", {
        "messages": messages,
        "max_tokens": n_predict,
        "temperature": 0.0,
        "stream": False,
    })


def phase1():
    log(f"\n{'='*76}\n### Phase 1 · 多轮记忆保持（7 轮）\n{'='*76}")
    messages = [{"role": "user", "content": DOC},
                {"role": "assistant", "content": "已通读并记住，请提问。"}]

    rows = []
    total_prompt = 0
    for i, (q, expect, kind) in enumerate(TURNS, 1):
        messages.append({"role": "user", "content": q})
        t0 = time.time()
        try:
            r = chat(messages)
        except Exception as e:
            log(f"  轮{i} 请求失败: {str(e)[:120]}")
            break
        dt = time.time() - t0

        choice = (r.get("choices") or [{}])[0]
        msg = choice.get("message") or {}
        ans = (msg.get("content") or "").strip()
        ti = r.get("timings") or {}
        usage = r.get("usage") or {}

        pn = ti.get("prompt_n", 0) or 0
        total_prompt += pn
        dec = ti.get("predicted_per_second", 0.0) or 0.0
        predict_n = ti.get("predicted_n", 0) or 0
        dn = ti.get("draft_n", 0) or 0
        da = ti.get("draft_n_accepted", 0) or 0
        acc = (da / dn) if dn else float("nan")

        hit = [k for k in expect if k in ans]
        ok = len(hit) > 0
        rows.append({"turn": i, "kind": kind, "ok": ok, "hits": hit,
                     "expect": list(expect), "answer": ans[:200],
                     "decode": dec, "acc": acc, "new_tokens": pn,
                     "cum": total_prompt, "sec": dt, "predict_n": predict_n})

        flag = "OK " if ok else "MISS"
        log(f"  轮{i} [{flag}] {kind:8s} 新增 {pn:5d} tok / 累计 {total_prompt:6d}  "
            f"dec={dec:6.2f} t/s  acc={acc:.3f}  {dt:5.1f}s  出 {predict_n} tok")
        log(f"       答: {ans[:150].replace(chr(10),' ')}")
        if not ok:
            log(f"       期望命中: {expect}  实际命中: {hit}")

        messages.append({"role": "assistant", "content": ans})

    return rows, messages


def phase2():
    """大海捞针：前缀 ~20k token，事实埋在开头。"""
    log(f"\n{'='*76}\n### Phase 2 · 长上下文检索（前缀约 20k token）\n{'='*76}")
    filler = (DOC + "\n\n以下是补充的技术附录，供参考。\n") * 1
    # 用真实技术文档堆叠加深，避免无意义重复触发 EOS
    extra = (ROOT / "surgery" / "docs" / "QUALITY.md")
    body = extra.read_text(encoding="utf-8", errors="replace") if extra.exists() else ""
    pad = (body + "\n\n") * 6   # 约 20k 字符 → 中文/英文混合约 8-12k token

    needle = "【关键标记】本批次试验的追溯编号为 ZQ-90217，负责人签章为「林思远」。"
    prompt = DOC + "\n\n" + pad + "\n\n" + needle + "\n\n" + pad
    q = ("在整段材料的【关键标记】处，提到的追溯编号和签章人分别是什么？"
         "只回答这两项。")

    messages = [{"role": "user", "content": prompt},
                {"role": "assistant", "content": "已通读。"},
                {"role": "user", "content": q}]
    t0 = time.time()
    try:
        r = chat(messages, n_predict=300)
    except Exception as e:
        log(f"  请求失败: {str(e)[:150]}")
        return None
    dt = time.time() - t0
    ans = ((r.get("choices") or [{}])[0].get("message") or {}).get("content", "").strip()
    ti = r.get("timings") or {}
    pn = ti.get("prompt_n", 0) or 0
    pp = ti.get("prompt_per_second", 0.0) or 0.0
    dec = ti.get("predicted_per_second", 0.0) or 0.0
    dn = ti.get("draft_n", 0) or 0
    da = ti.get("draft_n_accepted", 0) or 0
    acc = (da / dn) if dn else float("nan")
    ok = ("ZQ-90217" in ans) and ("林思远" in ans)

    log(f"  前缀 {pn} token  prefill={pp:.0f} t/s  用时 {dt:.1f}s")
    log(f"  decode={dec:.2f} t/s  acc={acc:.3f}")
    log(f"  [{'OK ' if ok else 'MISS'}] 答: {ans[:200].replace(chr(10),' ')}")
    return {"prompt_n": pn, "prefill": pp, "decode": dec, "acc": acc,
            "ok": ok, "answer": ans[:300], "sec": dt}


def main():
    kill()
    time.sleep(4)
    lf = open(LOG, "w", encoding="utf-8", errors="replace")
    env = dict(os.environ)
    env["GGML_CUDA_BATCH_INVARIANT"] = "1"
    log("启动服务（黄金配置）...")
    proc = subprocess.Popen([str(BIN / "llama-server.exe")] + ARGS,
                            cwd=str(BIN), stdout=lf, stderr=subprocess.STDOUT, env=env)
    try:
        if not wait_ready(proc):
            log("  !! 启动失败，见 " + str(LOG))
            return
        log("  服务就绪")

        stop = threading.Event()
        threading.Thread(target=gpu_sampler, args=(stop,), daemon=True).start()

        # 预热
        log("预热 ...")
        chat([{"role": "user", "content": "hi"}], n_predict=64)

        rows, _ = phase1()
        p2 = phase2()

        stop.set()
        time.sleep(2)

        # ---- 汇总
        log(f"\n{'='*76}\n### 汇总\n{'='*76}")
        if rows:
            okn = sum(1 for x in rows if x["ok"])
            log(f"  多轮记忆保持: {okn}/{len(rows)} 轮命中")
            log(f"  {'轮':>3} {'类型':<10} {'新增tok':>8} {'累计tok':>9} "
                f"{'decode':>8} {'接受率':>7} {'耗时':>7} 判定")
            for x in rows:
                log(f"  {x['turn']:>3} {x['kind']:<10} {x['new_tokens']:>8} "
                    f"{x['cum']:>9} {x['decode']:>8.2f} {x['acc']:>7.3f} "
                    f"{x['sec']:>6.1f}s {'OK' if x['ok'] else 'MISS'}")
            decs = [x["decode"] for x in rows if x["decode"]]
            if decs:
                log(f"\n  decode: 首轮 {decs[0]:.2f} → 末轮 {decs[-1]:.2f} t/s，"
                    f"平均 {sum(decs)/len(decs):.2f}，波动 "
                    f"{(max(decs)-min(decs))/max(decs)*100:.0f}%")
        if p2:
            log(f"\n  长上下文检索（{p2['prompt_n']} tok 前缀）: "
                f"{'通过' if p2['ok'] else '未通过'}｜prefill {p2['prefill']:.0f} t/s｜"
                f"decode {p2['decode']:.2f} t/s")

        # ---- GPU
        sm, mem, pw, tp, mu = [], [], [], [], []
        for s in samples:
            try:
                a, b, c, d, e = [x.strip() for x in s.split(",")]
                sm.append(int(a)); mem.append(int(b)); pw.append(float(c))
                tp.append(int(d)); mu.append(int(e))
            except Exception:
                continue
        if mem:
            log(f"\n  GPU 采样 {len(mem)} 次：")
            log(f"    显存频率 {min(mem)}~{max(mem)} MHz（满频占比 "
                f"{100*sum(1 for m in mem if m>=12001)/len(mem):.0f}%）")
            log(f"    SM {min(sm)}~{max(sm)} MHz｜功耗 {min(pw):.1f}~{max(pw):.1f} W"
                f"｜温度 {min(tp)}~{max(tp)} °C｜显存占用 {min(mu)}~{max(mu)} MiB")

        json.dump({"phase1": rows, "phase2": p2, "samples": samples},
                  open(ROOT / "multiturn.json", "w", encoding="utf-8"),
                  indent=2, ensure_ascii=False)
    finally:
        kill()
        lf.close()
        (ROOT / "multiturn_result.log").write_text("\n".join(loglines),
                                                   encoding="utf-8", errors="replace")


if __name__ == "__main__":
    main()
