# 变更前证据保全索引
采集时间：2026-09-27 20:37:35
目的：陛下已安排另一 agent 卸载 Windows 11 26200 预览版并更换 NVIDIA 驱动；
      本快照固化"变更前"的 OS/驱动/虚拟化/崩溃证据，供变更后做前后对照。
说明：本目录全部为只读采集结果；转储文件副本见上一级目录。
      C 盘原件（Minidump / WER / 事件日志）可能被系统回退或清理，故先行固化。

| 文件 | 字节 | sha256(前 16) |
|---|---|---|
| 01_os_version.txt | 876 | f05f266c624a0547 |
| 02_hotfix.txt | 782 | 004374b262b7af64 |
| 03_gpu_nvidia_smi.txt | 23485 | 9b3d6085f4542c73 |
| 04_gpu_controller.txt | 893 | 011f06e9ea071d5d |
| 05_hardware.txt | 1016 | c99eb402c52d919e |
| 06_vbs_deviceguard.txt | 1437 | 6b318239286eb640 |
| 07_virtual_features.txt | 707 | a37d78a678c701a3 |
| 08_wsl.txt | 1028 | d3eeabb1846eb689 |
| 09_power.txt | 750 | 81735522e590fee8 |
| 10_events_bugcheck.txt | 1204 | 21b09ca13ac11722 |
| 11_events_kernelpower_6008.txt | 6364 | a08894b03a6c8051 |
| 12_events_crash_window.txt | 70263 | 2a3e61bd8e79bffb |
| 13_events_hypervisor.txt | 26575 | 9a81db852142b8cc |
| 14_minidump_listing.txt | 663 | ce6126f93b07d6e0 |
| 15_wer_archive.txt | 851 | 8f9692b1180009fe |
| 16_services_ports.txt | 941 | e41ede78d1a9618f |
