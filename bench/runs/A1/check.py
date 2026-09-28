with open("logs/run.log", encoding="utf-8") as f:
    for i, line in enumerate(f, 1):
        if "ERROR" in line:
            print(i, repr(line.rstrip()))
