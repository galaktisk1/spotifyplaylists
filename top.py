import gzip
import json

history_file = "data/spotify-extended-history-compact.json.gz"

with gzip.open(history_file, "rt", encoding="utf-8") as f:
    data = json.load(f)

rows = data["rows"]
print(len(rows))

first_row = rows[0]
print(json.dumps(first_row, indent=2))
print(first_row["ms_played"] / 1000)
print(rows[-1])
