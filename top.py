import gzip
import json
from collections import Counter

# constants
history_file = "data/spotify-extended-history-compact.json.gz"
min_ms = 30_000

with gzip.open(history_file, "rt", encoding="utf-8") as f:
    data = json.load(f)

rows = data["rows"]

plays = Counter()

for row in rows:
    artist = row["master_metadata_album_artist_name"]
    track = row["master_metadata_track_name"]
    key = (artist, track)
    # now filtering
    if row["ms_played"] < min_ms:
        continue
    
    plays[key] += 1

print(f"{sum(plays.values()):,} plays of {len(plays):,} songs")

for rank, ((artist, track), count) in enumerate(plays.most_common(50), start=1):
    print(f"{rank:>2}. {artist} - {track} ({count})")
