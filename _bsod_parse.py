# -*- coding: utf-8 -*-
"""解析 Windows 内核小转储头部：BUGCHECK_CODE 与四个参数。"""
import struct
import sys
import glob
import os

sys.stdout.reconfigure(encoding="utf-8")

files = sorted(glob.glob(r"C:\Windows\Minidump\*.dmp"), key=os.path.getmtime, reverse=True)
if not files:
    print("未找到转储文件")
    sys.exit(0)

p = files[0]
b = open(p, "rb").read()
print("转储文件 :", p)
print("大小     :", len(b), "bytes")
print("Signature:", b[0:8])
print("ValidDump:", b[8:16])
print()

major, minor, machine, ncpu = struct.unpack_from("<IIII", b, 0x0C)
bugcheck = struct.unpack_from("<I", b, 0x18)[0]
params = struct.unpack_from("<QQQQ", b, 0x20)

print("NT 版本  : %d.%d" % (major, minor))
print("CPU 数   :", ncpu)
print("BUGCHECK : 0x%08X" % bugcheck)
for i, v in enumerate(params, 1):
    print("  参数%d   : 0x%016X  (%d)" % (i, v, v))
print()

# 常见蓝屏码释义
KNOWN = {
    0x0000000A: "IRQL_NOT_LESS_OR_EQUAL（驱动非法内存访问，常见于显卡/网卡驱动）",
    0x0000001E: "KMODE_EXCEPTION_NOT_HANDLED",
    0x0000003B: "SYSTEM_SERVICE_EXCEPTION",
    0x00000050: "PAGE_FAULT_IN_NONPAGED_AREA（内存/驱动）",
    0x0000007E: "SYSTEM_THREAD_EXCEPTION_NOT_HANDLED",
    0x000000D1: "DRIVER_IRQL_NOT_LESS_OR_EQUAL（驱动）",
    0x00000101: "CLOCK_WATCHDOG_TIMEOUT（CPU 卡死，常伴超频/降压不稳）",
    0x00000116: "VIDEO_TDR_FAILURE（显卡驱动挂起恢复失败）",
    0x00000117: "VIDEO_TDR_TIMEOUT_DETECTED（显卡无响应）",
    0x00000119: "VIDEO_SCHEDULER_INTERNAL_ERROR",
    0x00000124: "WHEA_UNCORRECTABLE_ERROR（硬件级：CPU/内存/PCIe 报错）",
    0x00000133: "DPC_WATCHDOG_VIOLATION（驱动长时间占用，常见于存储/显卡驱动）",
    0x0000013A: "KERNEL_MODE_HEAP_CORRUPTION（内核堆损坏，常为驱动越界写）",
    0x00000139: "KERNEL_SECURITY_CHECK_FAILURE",
    0x00000141: "VIDEO_ENGINE_TIMEOUT_DETECTED",
    0x0000014C: "FATAL_ABNORMAL_RESET_ERROR",
    0x0000009F: "DRIVER_POWER_STATE_FAILURE（休眠/电源状态切换失败）",
    0x000000EF: "CRITICAL_PROCESS_DIED",
    0x00020001: "HYPERVISOR_ERROR（虚拟化层报错，WIN11 VBS/内存完整性相关）",
}
print("释义     :", KNOWN.get(bugcheck, "未知/非标准码"))
