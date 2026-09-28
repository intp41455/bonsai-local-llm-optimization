import csv
import json
import os

SRC = "sales.csv"
DST = "results/sales.jsonl"


def main():
    os.makedirs(os.path.dirname(DST), exist_ok=True)
    with open(SRC, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with open(DST, "w", encoding="utf-8") as out:
            for row in reader:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    main()
