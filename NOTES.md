# Rebuild notes

A ground-up rewrite of `spotify-playlist-automation`, written mostly by me.
AI helps by explaining, reviewing and writing tests. It doesn't write the files.

The old repo stays around as a **reference for what the playlists should
contain**, the same way CS2510 (https://github.com/CS2510/Current-Code) uses
Unity's API as a reference for its engine. I look at it to see *what* a result
should be, then write my own *how*.

## Goals

- Every question has one obvious file as its answer: "go here for this."
- Every step leaves something that runs and that I fully understand.
- No abstraction until I've written the same thing twice.

## Rules

1. Data moves in one direction: load → merge → store → playlists → sync.
2. Playlist files never talk to Spotify. They take history and return
   a name, a description and a list of tracks. Only the sync code writes to Spotify.
3. Name files after what they do. No `main3.py`, `shared/`, `_internal/`.
4. A file I can't hold in my head (roughly 300–400 lines) is a sign to split it.
5. Don't commit a line I can't explain.
6. One commit per capability, named after it ("Add Last.fm source").
7. Once something works, write down *why* each rule exists while I still
   remember the bug that caused it.

## Target shape (grows into this; don't create it up front)

```text
run.py                 the one entry point
config.toml            every tunable number in one place
metadata.json          aliases/overrides (copy from old repo at step 7)
artist_curation.json   pinned/excluded artists (copy at step 8)
engine/                like CS2510's engine/: shared by every playlist
  history.py           load listens
  lastfm.py            fetch scrobbles
  merge.py             combine sources, drop duplicates
  identity.py          "are these the same song/artist?"
  spotify.py           login, search, read/write playlists
  sync.py              make a Spotify playlist match a list of tracks
playlists/             like CS2510's games/: one file per family
  _template.py         copy this to start a new playlist (like helpers/square)
  current_history.py
  yearly.py
  museum.py
  discovery.py
  trends.py
data/                  gitignored: database, exports, caches
```

## The steps

Each step adds one capability because a playlist needed it.

1. **One file that shows something.** `top.py`, about 40 lines: read the
   export, count plays per track, print the top 50. No API, no folders.
2. **Time windows.** Still one file: This Week, This Month and This Year, printed.
   A small `Listen` dataclass will probably show up here.
3. **Push one playlist to Spotify.** Log in, find or create "This Week" and
   replace its contents. Now split into `engine/` and `playlists/`.
   Reuse the existing playlist ID from the old sync cache
   (`current_history/spotify_sync_cache.json` → `playlist_ids.week`), or I'll
   end up with two "This Week" playlists.
4. **Settle the shape** once all seven Current History playlists work. Decide
   what a playlist definition is (probably just a function). Keep it tiny.
5. **SQLite** once reloading the JSON gets annoying. Engine-only change.
6. **Last.fm** for listens newer than the export. Simplest merge rule first:
   drop a scrobble if a Spotify play of the same track is within a few minutes.
   Add trickier rules only when the playlists show me a real problem.
7. **Identity rules** when duplicates show up (single vs album version).
   Bring over `metadata.json`.
8. **New families, each forcing a new engine feature:**
   - Yearly: calendar windows, and not rewriting finished years.
   - Museum: artist curation, minimum sizes, archive instead of delete.
   - Discovery: depends on Museum's result, so playlists need a run order.
   - Trends: monthly buckets and statistics. Hardest; do it last.
9. **Smarter sync** (diff and reorder instead of replace) when big playlists or
   rate limits make full replacement hurt.
10. **Automate** with a GitHub Actions schedule, plus keeping state between runs.

## Step 1 details

The old repo has a compressed export with 232,470 listens:
`../spotify-playlist-automation/local-data/spotify-extended-history-compact.json.gz`

It's a gzipped JSON object; the listens are in its `"rows"` list. Each row has
Spotify's standard export fields:

| Field | Meaning |
| --- | --- |
| `ts` | when the play *ended*, UTC, e.g. `2015-04-20T21:50:19Z` |
| `ms_played` | how long it actually played |
| `master_metadata_track_name` | track title |
| `master_metadata_album_artist_name` | artist |
| `master_metadata_album_album_name` | album |
| `spotify_track_uri` | e.g. `spotify:track:36GSpacsMAC9m9hOJA3nJ0` |
| `skipped`, `reason_start`, `reason_end` | how the play started and ended |

Things I'll run into:
- Very short plays are noise. Spotify itself counts a stream at 30 seconds.
  But songs shorter than 30s (Pig Destroyer, interludes) could never count, so
  also count a short play if `reason_end == "trackdone"` (1,030 plays, 441 songs).
  Don't use `skipped == False` for this: 64,443 short plays say not-skipped but
  ended with next/back. Loophole: `trackdone` after dragging the progress bar to
  the end. At step 5, with real track lengths, require play time ≈ track length.
- Some rows (podcasts, local files) have no track name or URI.
- Copy the file into `data/` and gitignore it. It's personal history.
- A fresh export comes from Spotify's privacy page as `my_spotify_data.zip`
  (Extended streaming history), with `Streaming_History_Audio_*.json` inside.

## Reusing the old caches

All in `../spotify-playlist-automation/local-data/cache/`. The data is worth keeping
(months of API lookups), but the storage is the problem.

### What's there (checked Nov 2026)

| File | Worth keeping |
| --- | --- |
| `spotify_album_uri_cache.json` | 1,037 albums (type, release date, image, track positions) plus track→album links |
| `spotify_artist_cache.json` | 528 artists (URI, image) |
| `spotify_cache.json` | track durations from the API and from search, plus 616 search results (531 are "no match") |
| `spotify_playlist_duration_cache.json` | ~19k artist/track → URI links and durations from my old playlist CSVs |
| `spotify_duration_guess_cache.json` | 6,633 durations guessed from the median of finished plays |
| `lastfm_scrobbles_cache.json` | 54,761 scrobbles (listens, not really a cache; same rows as `listens.db`) |
| `<app>/spotify_sync_cache.json` | Spotify playlist IDs for every playlist I already have, plus archived ones. In Current History, `whole_time` is the old name for These 3 Years (back when "whole time" only covered 3 years) |

Don't carry over: `canonical/`, `canonical_events` in `listens.db` and
`resolved_duration_*`. Those are *decisions* the old code made, and I'll rebuild
them. Also skip backups, audits, `cd-*` and `python-venv/` (285 MB).

### What's wrong with how they're stored

- **The same fact lives in many places.** Durations alone are in about eight maps
  across four files. 62 tracks have two different durations (more than 2s apart),
  depending on which file you read.
- **Every file builds its keys differently.** Some use `artist||track||album`,
  others `artist\ttrack\talbum`, each with its own lowercasing/cleanup.
- **Decisions are mixed in with evidence.** 1,190 values in the "trusted" playlist
  duration cache are identical to the median guesses, so I can't tell anymore
  which ones came from Spotify.
- **Some decisions look wrong.** In 75 tracks, the history-based guess overrode
  the Spotify API by more than 30s. Example: `0Sjd5a0IrSUsXPCpEOOQZh`, where the API
  and search both say 340.6s but 113.5s was chosen. Investigate this first.

### How to store them instead

One SQLite file, `data/cache.db`. The core idea is to **store observations, not
decisions**: every row says what was seen, where, and when. Picking the "right"
value is code that runs at read time, so changing a rule means rerunning, not
fixing cached data.

```text
tracks        uri PK, name, artist, album_uri, duration_ms, fetched_at
albums        uri PK, name, album_type, release_date, image_url, fetched_at
artists       uri PK, name, image_url, fetched_at
durations     uri, source, duration_ms, observed_at
              (source = spotify_api | playlist_csv | history_median | manual)
uri_matches   artist, track, album, uri (NULL = searched, no match),
              method (strict | loose | playlist_csv | manual), score, searched_at
playlists     key PK, family, spotify_id, snapshot_id, archived_at
imports       file, imported_at, rows   (what came from the old repo)
```

### The clear path when something looks weird

1. **Keep the old JSON untouched** in `data/legacy/`, read-only. Never edit it.
2. **One import script** (`tools/import_legacy.py`), one function per old file.
   Re-runnable: delete `cache.db`, run it again, get the same result. It prints
   counts and every conflict it finds.
3. **Re-derive keys** with my own `identity.py` instead of trusting the old key strings.
4. **Manual fixes are rows with `source = 'manual'`**, which always win and are
   easy to list.
5. **`tools/why.py "<artist>" "<track>"`** prints everything known about one track:
   its listens, every URI match, every duration with its source, and which one was
   picked and why. That's where I go first when something looks off.

When to do this: at step 5 (SQLite). Before then the Spotify export already has
URIs, so the caches aren't needed yet. Only the playlist IDs are needed, at step 3.

## Where to look in the old repo

Look for *what* it does. Rewrite the *how* myself.

| When I'm on... | Look at |
| --- | --- |
| Playlist sizes/windows | `apps/current_history/config.py` (and each `apps/*/config.py`) |
| Merge rules and their thresholds | `engine/src/music_engine/_internal/music_history/merge.py` and `config.py` next to it |
| Text normalization / identity | `engine/src/music_engine/_internal/music_history/utils.py` |
| Finding URIs for Last.fm-only tracks | `engine/src/music_engine/_internal/music_history/spotify_search/` |
| Sync, chunking, reordering | `engine/src/music_engine/_internal/playlist/sync.py` |
| Getting a refresh token | `get_refresh_token.py` (repo root) |
| Scheduled run | `.github/workflows/spotify-sync.yml` |
| "Am I done?" | compare my output to `local-data/generated/<app>/playlists.json` |
