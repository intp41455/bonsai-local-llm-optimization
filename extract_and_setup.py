#!/usr/bin/env python3
import os, zipfile, sys

DEMO = os.path.dirname(os.path.abspath(__file__))
BIN_CUDA = os.path.join(DEMO, "bin", "cuda")
RELEASE_TAG = "prism-b10743-adfffbe"
STAMP = f"{RELEASE_TAG} cuda-13.3"

os.makedirs(BIN_CUDA, exist_ok=True)

def extract(zip_path, label):
    if not os.path.exists(zip_path):
        print(f"[ERR] {label} not found: {zip_path}")
        sys.exit(1)
    print(f"Extracting {label} ({os.path.getsize(zip_path)/1e6:.1f} MB) -> bin/cuda ...")
    with zipfile.ZipFile(zip_path, "r") as z:
        z.extractall(BIN_CUDA)
    print(f"  done.")

extract(os.path.join(DEMO, "llama_pdl.zip"), "llama build (cuda-13.3)")
extract(os.path.join(DEMO, "cudart_pdl.zip"), "CUDA runtime DLLs (cuda-13.3)")

# Write release stamp so future setup.ps1 runs won't re-download
stamp_path = os.path.join(BIN_CUDA, ".llama_release")
with open(stamp_path, "w", encoding="utf-8") as f:
    f.write(STAMP)
print(f"Wrote stamp: {STAMP}")

# Verify key binaries exist
required = ["llama-server.exe", "llama-cli.exe", "cudart64_13.dll", "cublas64_13.dll", "ggml-cuda.dll"]
missing = [r for r in required if not os.path.exists(os.path.join(BIN_CUDA, r))]
if missing:
    print(f"[WARN] Missing expected files: {missing}")
else:
    print("[OK] All key binaries present in bin/cuda")

print("Setup extraction complete.")
