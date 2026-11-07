import gzip
import json
from collections import Counter
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

# constants
history_file = "data/spotify-extended-history-compact.json.gz"
min_ms = 30_000
central = ZoneInfo("America/Chicago")  # my timezone


def print_top(title, counts, limit=50):
    print(title)
    print(f"{sum(counts.values()):,} plays of {len(counts):,} songs")
    for rank, ((artist, track), count) in enumerate(counts.most_common(limit), start=1):
        print(f"{rank:>3}. {artist} - {track} ({count})")
    print()


with gzip.open(history_file, "rt", encoding="utf-8") as f:
    data = json.load(f)

rows = data["rows"]
now = max(datetime.fromisoformat(row["ts"]) for row in rows)
windows = [
    ("This Week", 7, 50),
    ("This Month", 30, 50),
    ("These 6 Months", 182, 150),
    ("This Year", 365, 200),
    ("These 3 Years", 3 * 365, 500)
]


plays = Counter()
listens = []

for row in rows:
    artist = row["master_metadata_album_artist_name"]
    track = row["master_metadata_track_name"]
    key = (artist, track)
    # now filtering
    if row["ms_played"] < min_ms:
        continue

    plays[key] += 1
    played_at = datetime.fromisoformat(row["ts"])
    listens.append((played_at, key))


for name, days, limit in windows:
    start = now - timedelta(days=days)
    window_counts = Counter()
    for played_at, key in listens:
        if played_at >= start:
            window_counts[key] += 1
    title = f"{name} (since {start.astimezone(central):%b %d %Y})"
    print_top(title, window_counts, limit)
print_top("This Entire Time", plays, limit=500)
