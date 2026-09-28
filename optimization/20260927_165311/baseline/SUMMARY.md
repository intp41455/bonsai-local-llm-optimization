# Stage A baseline summary - Bonsai demo optimization

Captured: 2026-09-27 17:05:38 +08:00
Work dir: D:\Bonsai-demo\optimization\20260927_165311

## Runtime state at capture (read-only)
- Backend PID 43384 = dist\bonsai2-8gb-combo\bin\llama-server.exe (10,752-byte SHIM; real code in llama-server-impl.dll)
  cmdline: -m ...Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf -ngl 99 -fa on -np 1 -c 65536 -b 2048 -ub 512
           -ctk q4_0 -ctv q4_0 --backend-sampling --jinja --metrics --host 127.0.0.1 --port 8081 --alias bonsai-2-27b
- Proxy PID 40108 = python -u proxy/bonsai_proxy.py --port 8080 --upstream 8081 --effort medium
- Listeners: 127.0.0.1:8081 -> 43384 ; 127.0.0.1:8080 -> 40108
- BUSY CHECK: /slots -> is_processing = false  => IDLE at capture. Re-check before any restart.
- /props: build_info b181-9ef3205 | model_alias bonsai-2-27b | ftype 'PTQ1_0 - 1.75 bpw ternary (group 128)'
          modalities.vision=false (no mmproj loaded) | total_slots=1 | n_ctx=65536
- /slots params: max_tokens=-1, n_predict=-1, speculative.types=none, backend_sampling=false (slot view)
- GPU: 7731/8151 MiB used | util 6% | 49C | 22.24W | gfx clock 2025/3090 MHz | mem 12001 MHz  => idle, NOT throttled
- Model: Ternary-Bonsai-2-27B-PTQ1_0-mtp-lean.gguf | 6,297,658,848 bytes (5.865 GiB)

## Version identity
- git HEAD 9ef32054fe44797376792c869891163083d64bd0 (2026-09-25) 'Refresh Bonsai 2 upstream progress and Q2_0 support scope (#244)'
- /props build_info b181-9ef3205 => binary IS built from this commit (source and binary same version)
- git status: 175 dirty entries = OTHER agents' uncommitted work. DO NOT reset/stash/checkout/clean.

## Environment variables
- No LLAMA_ARG_* / BONSAI_* in shell env, nor in persisted User/Machine env (see env_llama_bonsai.txt).
- => effective params come ONLY from the launcher cmdline. No env override. Confirms P01.

## Findings confirmed at baseline
- P01 CONFIRMED: online config returns max_tokens=-1; cmdline has no --reasoning-budget and no -n.
- P02 CONFIRMED: proxy launched with hardcoded --effort medium (capture\effort.txt = 'medium').
- NEW / stronger than the plan: the model chat template resolves reasoning_effort default to **xhigh**
  (reasoning_effort|default('xhigh')). A request that omits the effort kwarg gets the HEAVIEST thinking
  instruction. Only xhigh/medium/low accepted; anything else raises an exception.
- P03 evidence intact: slot n_prompt_tokens=65535 vs n_ctx=65536 (leftover from previous request).
- vision=false => BONSAI_MMPROJ_CPU item is a no-op for this launcher (no --mmproj passed).

## Not yet verified (later stages)
- Request-level reasoning budget support of this binary (stage D).
- Real long-task throughput; capture\timings.jsonl records 17.6-20.2 tok/s (re-measure in stage G).

## Files
- processes.json listeners.json api_health.json api_props.json api_slots.json
- gpu_nvidia-smi.csv binary_info.txt model_info.txt env_llama_bonsai.txt
- git_info.txt git_status_porcelain.txt captured_at.txt
- *.utf8.txt  (GBK launchers converted to UTF-8 for reading)