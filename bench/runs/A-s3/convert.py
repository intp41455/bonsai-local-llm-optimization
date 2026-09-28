import csv
import json
import os

def main():
    src = "sales.csv"
    dst = "results/sales.jsonl"
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    with open(src, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with open(dst, "w", encoding="utf-8") as out:
            for row in reader:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
