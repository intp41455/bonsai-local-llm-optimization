import re

errors = []
with open("logs/run.log", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        line = line.rstrip("\n")
        if "ERROR" in line:
            m = re.match(r"ERROR\s+(\S+):\s+(.*)", line)
            if m:
                code = m.group(1)
                reason = m.group(2)
                errors.append((i, code, reason))

with open("results/errors.md", "w", encoding="utf-8") as f:
    f.write("# ERROR 汇总\n\n")
    f.write("| 行号 | 错误码 | 原因 |\n")
    f.write("| --- | --- | --- |\n")
    for i, code, reason in errors:
        f.write(f"| {i} | {code} | {reason} |\n")

print(f"共找到 {len(errors)} 条 ERROR")
