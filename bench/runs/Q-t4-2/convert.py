import csv
import json

def main():
    with open("sales.csv", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        with open("results/sales.jsonl", "w", encoding="utf-8") as out:
            for row in reader:
                out.write(json.dumps(row, ensure_ascii=False) + "\n")

if __name__ == "__main__":
    main()
