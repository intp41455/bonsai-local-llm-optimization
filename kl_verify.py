#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""KV 精度验证（用 bundle 自带的 llama-perplexity）。

以 f16 KV 为参考基准，量化三种配置相对 f16 的 KL 散度与 top-1 一致率：
  1) q4_0 KV                  <- 我们的 8GB 服务配置
  2) q8_0 KV                  <- 高精度备选（显存翻倍）
  3) q4_0 KV + 禁 Hadamard 旋转 <- 验证旋转对精度的贡献
对应用 base 模型（无 MTP 层），排除投机解码干扰。
"""
import os, re, subprocess

BASE = r"D:\Bonsai-demo"
BINDIR = os.path.join(BASE, "bundle", "bin")
PERP = os.path.join(BINDIR, "llama-perplexity.exe")
M27 = os.path.join(BASE, "models", "bonsai2-gguf", "27B")
MODEL = os.path.join(M27, "Ternary-Bonsai-2-27B-PTQ1_0.gguf")
CORPUS = os.path.join(BASE, "calib.txt")
REF = os.path.join(BASE, "kl_ref_f16.dat")
CTX = "2048"

COMMON = ["-m", MODEL, "-f", CORPUS, "-c", CTX, "-b", CTX, "-ub", CTX,
          "-ngl", "99", "-fa", "on", "--chunks", "4", "--no-warmup"]

CASES = [
    ("q4_0-KV",            ["-ctk", "q4_0", "-ctv", "q4_0"], {}),
    ("q8_0-KV",            ["-ctk", "q8_0", "-ctv", "q8_0"], {}),
    ("q4_0-KV-rot-off",    ["-ctk", "q4_0", "-ctv", "q4_0"], {"LLAMA_ATTN_ROT_DISABLE": "1"}),
]


def run(args, env, logname):
    e = dict(os.environ)
    e["PATH"] = BINDIR + os.pathsep + e["PATH"]
    e.update(env)
    lp = os.path.join(BASE, logname)
    with open(lp, "wb") as lg:
        subprocess.run([PERP] + args, stdout=lg, stderr=subprocess.STDOUT, env=e)
    raw = open(lp, "rb").read().decode("utf-8", "replace")
    return raw


def parse(raw):
    """抓 [1]PPL、KL、top-1 一致率等指标（含 ISO-8601 分隔符写法）。"""
    out = {}
    for pat, key in [
        (r"Final estimate:\s*PPL\s*=\s*([\d.]+)", "ppl"),
        (r"Mean\s+KLD\s*=\s*([\d.eE+-]+)", "kld"),
        (r"Mean\s+KLD base\s*=\s*([\d.eE+-]+)", "kld_base"),
        (r"Mean\s+top-1\s+agreement\s*=\s*([\d.]+)", "top1"),
        (r"top-1 agreement\s*=\s*([\d.]+)", "top1b"),
        (r"Maximum\s+KLD\s*=\s*([\d.eE+-]+)", "kld_max"),
        (r"99\.9%\s*KLD\s*<?=?\s*([\d.eE+-]+)", "kld999"),
    ]:
        m = re.findall(pat, raw)
        if m:
            out[key] = m[-1]
    if "top1" not in out and "top1b" in out:
        out["top1"] = out["top1b"]
    return out


print("=== 步骤 1/4：生成 f16 参考基准 ===", flush=True)
raw = run(COMMON + ["--kl-divergence-base", REF], {}, "kl_00_f16.log")
print("  %s" % parse(raw), flush=True)
print("  参考文件存在: %s" % os.path.isfile(REF), flush=True)

print("\n=== 步骤 2-4：量化各配置相对 f16 的偏差 ===", flush=True)
rows = []
for name, kv, env in CASES:
    print("\n--- %s ---" % name, flush=True)
    raw = run(COMMON + kv + ["--kl-divergence", "--kl-divergence-base", REF], env, "kl_%s.log" % name)
    d = parse(raw)
    print("  %s" % d, flush=True)
    if not d.get("kld") and not d.get("top1"):
        tail = [l for l in raw.splitlines() if l.strip()][-6:]
        print("  未解析到指标，日志尾部:", flush=True)
        for l in tail:
            print("    " + l[:120], flush=True)
    rows.append((name, d.get("ppl", "-"), d.get("kld", "-"), d.get("top1", "-"), d.get("kld_max", "-")))

print("\n\n============ KV 精度验证结果 ============", flush=True)
print("%-20s %-10s %-14s %-12s %s" % ("配置", "PPL", "平均KLD", "top-1一致", "最大KLD"), flush=True)
for r in rows:
    print("%-20s %-10s %-14s %-12s %s" % r, flush=True)
print("\n参照（官方 RECEIPTS.md，16k chunks vs f16）: q8_0 KL 0.00017 / 99.38%; q4_0 KL 0.00218 / 97.93%", flush=True)
