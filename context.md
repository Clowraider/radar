# Code Context

## Files Retrieved
1. `scripts/sync_trh_raw_to_radar.py` (lines 1-255) - raw TRH → Radar sync entry point, args, env loading, DB assumptions, advisory lock, print/error behavior.
2. `scripts/detect_affected_periods.py` (lines 27-244) - affected-month detection entry point, args, run table writes, status updates, advisory lock, print/error behavior.
3. `scripts/extract_keywords.py` (lines 1-110, 421-540, 758-871) - keyword extraction modes, env/dependency assumptions, pending/processing period selection, resumability, print/error behavior.
4. `scripts/build_monthly_aggregates.py` (lines 1-145, 340-438) - aggregate build modes, period selection, run table writes, advisory lock, print/error behavior.
5. `README.md` (lines 20-64, 87-102, 119-260) - documented processing order, cron/advisory lock expectations, invocation examples.
6. `docs/processing.md` (lines 5-35, 37-180, 181-209) - processing data flow, cron notes, mode matrix, resumability notes.
7. `requirements.txt` (lines 1-5) - Python dependencies needed by the scripts.

## Key Code

### Common conventions across scripts

All four scripts load repo-root `.env` with simple `KEY=VALUE` parsing via `os.environ.setdefault`, so real environment variables override `.env` values. DB config requires `<PREFIX>_DB_PASSWORD`; host defaults to `127.0.0.1`, port to `5432`, user to `postgres`, and dbname has no default.

```python
# scripts/sync_trh_raw_to_radar.py lines 50-78
ENV_PATH = PROJECT_ROOT / ".env"
def load_env_file(path=ENV_PATH): ... os.environ.setdefault(...)
def db_config(prefix):
    password = os.getenv(f"{prefix}_DB_PASSWORD")
    if not password:
        raise RuntimeError(f"Falta {prefix}_DB_PASSWORD en .env")
```

The same DB config shape is repeated in `detect_affected_periods.py` lines 44-72, `extract_keywords.py` lines 77-105, and `build_monthly_aggregates.py` lines 44-72.

Each script has a per-script PostgreSQL advisory lock:

```python
# representative: scripts/detect_affected_periods.py lines 35-41
def acquire_script_lock(conn, name):
    key = zlib.crc32(f"radar_trh:{name}".encode("utf-8")) & 0x7FFFFFFF
    cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
    if not acquired:
        raise AlreadyRunning(f"{name}: ya hay otra ejecución activa; saliendo sin hacer cambios")
```

`AlreadyRunning` is caught at CLI level in every script, printed to stderr, and exits `0`; other exceptions print a script-specific `... error: {exc}` message to stderr and exit `1`.

### `scripts/sync_trh_raw_to_radar.py`

Invocation:

```bash
python scripts/sync_trh_raw_to_radar.py              # incremental cron mode
python scripts/sync_trh_raw_to_radar.py --full       # full copy
python scripts/sync_trh_raw_to_radar.py --lookback-hours 48 --batch-size 1000
```

Args from lines 220-244:
- `--full`: copies all valid source rows.
- `--lookback-hours`: default `RADAR_SYNC_LOOKBACK_HOURS` or `48`; must be positive unless `--full`.
- `--batch-size`: default `RADAR_SYNC_BATCH_SIZE` or `1000`; must be positive.

DB/env assumptions:
- Requires both `RADAR_DB_*` and `TRH_DB_*` connection values; password mandatory for each prefix (lines 68-78, 178-187).
- Incremental source query requires `noticias_historico.embedding IS NOT NULL` and `fecha_extraccion >= NOW() - lookback` (lines 81-108).
- Writes/upserts `radar_raw_noticias` by `noticia_hash`, setting `synced_at = NOW()` (lines 140-165).
- Full mode does **not** require embeddings in the source query; incremental does (lines 99-103).

Print/logging:
- stdout per batch: `sync batch: {copied} rows | total: {total}` (line 204).
- stdout completion: `sync complete | mode=... | rows upserted: ...` (line 209).
- stderr lock skip exits `0`; stderr `sync error: ...` exits `1` (lines 247-255).

### `scripts/detect_affected_periods.py`

Invocation:

```bash
python scripts/detect_affected_periods.py                         # incremental by Radar synced_at
python scripts/detect_affected_periods.py --lookback-hours 48
python scripts/detect_affected_periods.py --from-extraction-date   # incremental by TRH fecha_extraccion
python scripts/detect_affected_periods.py --full                   # all months
python scripts/detect_affected_periods.py --notes "..."
```

Args from lines 169-184:
- `--full`: detects all months with `fecha_publicacion IS NOT NULL`.
- `--lookback-hours`: default `RADAR_PROCESS_LOOKBACK_HOURS`, else `RADAR_SYNC_LOOKBACK_HOURS`, else `48`; must be positive unless full.
- `--from-extraction-date`: uses `fecha_extraccion` instead of `synced_at` for incremental selection.
- `--notes`: stored in `radar_processing_runs`.

DB/env assumptions:
- Requires `RADAR_DB_*` connection values; password mandatory (lines 62-72).
- Creates a `radar_processing_runs` row with `status='running'` then marks `completed`/`failed` (lines 75-101, 197-228).
- Groups affected analytics months by `fecha_publicacion` (lines 104-134).
- Upserts `radar_affected_periods` with conflict key `(month_start, reason)` and resets status to `pending` on conflict (lines 137-166).
- Reasons: `full_refresh`, `recent_extraction`, or `recent_sync` (line 212).

Print/logging:
- stdout summary: `processing run: ...`, `mode: ... | reason: ...`, `affected periods: ... | rows detected: ...`, then per-month `- YYYY-MM-DD: N rows` (lines 217-221).
- stderr lock skip exits `0`; stderr `detect affected periods error: ...` exits `1` (lines 236-244).

### `scripts/extract_keywords.py`

Invocation:

```bash
python scripts/extract_keywords.py                                      # pending + processing periods
python scripts/extract_keywords.py --retry-failed                       # also failed periods
python scripts/extract_keywords.py --full --reset-period                # all months, rebuild keyword rows/stats
python scripts/extract_keywords.py --period 2025-05 --reset-period      # one month
python scripts/extract_keywords.py --period 2025-05 --reset-period --limit-news 20
python scripts/extract_keywords.py --commit-every 25
python scripts/extract_keywords.py --dictionary config/keyword_dictionary.yml --spacy-model es_core_news_lg
python scripts/extract_keywords.py --dry-run
```

Args from lines 758-779:
- Mutually exclusive `--full` / `--period YYYY-MM`; no mode means pending mode.
- `--pending` exists but is redundant/default when `--full`/`--period` are omitted.
- `--dictionary`: default `config/keyword_dictionary.yml`.
- `--spacy-model`: default `es_core_news_lg`.
- `--limit-news`: only valid with `--period`, positive; smoke tests only.
- `--commit-every`: default `10`, positive.
- `--retry-failed`: include affected periods marked `failed`.
- `--no-skip-existing`: reprocess even if keyword processing marker exists.
- `--max-text-chars`: default `2500`.
- `--yake-max-keywords`: default `12`, positive.
- `--reset-period`: deletes existing keyword rows/stats and processing markers for each period.
- `--dry-run`: reads/extracts but does not write DB changes.
- `--notes`: stored in `radar_processing_runs`.

DB/env/dependency assumptions:
- Requires `RADAR_DB_*` connection values; password mandatory (lines 95-105).
- Imports dependencies at runtime and raises helpful errors if missing: `psycopg2`, `yake`, `spacy`, `yaml`/PyYAML (lines 793, 803-805; requirements list includes all plus `es-core-news-lg`).
- Reads and syncs dictionary entries from YAML into `radar_keyword_dictionary` / `radar_keyword_aliases` unless dry-run (lines 33-37, 803-817).
- Default period selection uses `radar_affected_periods` statuses `pending` and `processing`; `--retry-failed` adds `failed` (lines 454-480). This is deliberate resumability.
- `--full` selects all distinct months from `radar_raw_noticias` with `fecha_publicacion` (lines 458-467).
- Per-month processing marks affected period `processing`, optionally resets, fetches news in month, skips rows already completed in `radar_news_keyword_processing` unless reset/no-skip-existing, commits every N news, refreshes `radar_monthly_keyword_stats`, then marks period `completed` (lines 493-533, 758-847).

Print/logging:
- stdout setup: `dictionary entries: N`, `omitted keywords: N`, `loading spaCy model: ...` (lines 807-810).
- stdout if no work: `no periods selected` (line 820).
- stdout selected count: `periods selected: N` (line 825).
- stdout per month and progress: `YYYY-MM-DD: selected_news=N skip_existing=True/False`, `... committed news=X/Y keyword_rows=N processed_markers=N`, `... committed final ...`, optional `... pruned omitted keyword rows=N`, `... completed news=N keyword_rows=N` (lines 713-754).
- stdout completion: `keyword extraction complete | news=N keyword_rows=N` (line 847).
- stderr lock skip exits `0`; stderr `extract keywords error: ...` exits `1` (lines 863-871).

### `scripts/build_monthly_aggregates.py`

Invocation:

```bash
python scripts/build_monthly_aggregates.py                       # affected periods status completed
python scripts/build_monthly_aggregates.py --period 2025-05       # one month
python scripts/build_monthly_aggregates.py --full                 # all months with raw news
python scripts/build_monthly_aggregates.py --include-processing   # include processing periods too
python scripts/build_monthly_aggregates.py --notes "..."
```

Args from lines 368-379:
- Mutually exclusive `--full` / `--period YYYY-MM`; no mode means affected-period mode.
- `--include-processing`: default mode includes `processing` in addition to `completed`.
- `--notes`: stored in `radar_processing_runs`.

DB/env assumptions:
- Requires `RADAR_DB_*` connection values; password mandatory (lines 62-72).
- Creates/finishes a `radar_processing_runs` row (lines 89-115, 389-421).
- Default period selection reads distinct `month_start` from `radar_affected_periods` where status is `completed`; optional `processing` (lines 118-145).
- Full mode selects distinct months from `radar_raw_noticias` by `fecha_publicacion` (lines 122-131).
- For each month, deletes/rebuilds `radar_source_keyword_stats`, `radar_source_monthly_stats`, `radar_daily_activity`, and `radar_monthly_overview` (lines 354-365; reset table list at lines 144-151 in the full file context).
- Does **not** mark `radar_affected_periods` as consumed/archived after aggregate build; repeated default runs will rebuild completed periods again unless another process changes statuses.

Print/logging:
- stdout if no work: `no periods selected` (line 399).
- stdout selected count: `periods selected: N` (line 402).
- stdout per month: `YYYY-MM-DD: overview=N daily=N sources=N source_keywords=N` (lines 407-410).
- stdout completion: `monthly aggregates complete | periods=N` (line 415).
- stderr lock skip exits `0`; stderr `build monthly aggregates error: ...` exits `1` (lines 430-438).

## Architecture

Documented flow (`docs/processing.md` lines 5-18):

```text
TRH noticias_historico
  ↓ sync by fecha_extraccion
Radar radar_raw_noticias
  ↓ detect affected months by fecha_publicacion, using recent synced_at/fecha_extraccion as input window
radar_affected_periods
  ↓ extract keywords by month; mark each raw news item processed
radar_news_keyword_processing
  ↓ refresh keyword stats
radar_news_keywords + radar_monthly_keyword_stats
  ↓ build internal aggregates with real source names
radar_monthly_overview + radar_daily_activity + radar_source_*_stats
```

Recommended normal incremental chain for a cron-friendly `proceso.py`:

```bash
python scripts/sync_trh_raw_to_radar.py
python scripts/detect_affected_periods.py
python scripts/extract_keywords.py
python scripts/build_monthly_aggregates.py
```

Recommended first/full initialization chain from `README.md` lines 51-64:

```bash
python scripts/sync_trh_raw_to_radar.py --full
python scripts/detect_affected_periods.py --full
python scripts/extract_keywords.py        # after optional smoke test; processes pending months
python scripts/build_monthly_aggregates.py
```

Important date semantics from `README.md` lines 20-30:
- `fecha_extraccion`: when TRH found/indexed the story; used by sync incremental.
- `fecha_publicacion`: publication date; used for month analytics.
- `synced_at`: when Radar copied the row; default affected-period detection window.

## Recommended lock strategy for `proceso.py`

Use an **outer PostgreSQL advisory lock for the whole orchestrator run**, not only a local file lock. Existing per-script locks already prevent two instances of the same child script, and docs explicitly prefer PostgreSQL locks because they work across servers when pointing to the same Radar DB (`README.md` lines 87-102; `docs/processing.md` lines 31-35).

Recommended behavior:
1. `proceso.py` loads `.env` with the same parser convention and connects to `RADAR` DB.
2. Attempt `pg_try_advisory_lock(crc32("radar_trh:proceso") & 0x7FFFFFFF)` before launching any child process.
3. If not acquired: print a concise message to stderr and exit `0`, matching existing `AlreadyRunning` semantics.
4. Hold that DB connection open for the entire chain; release happens automatically on connection close, or explicitly with `pg_advisory_unlock` in `finally`.
5. Run child scripts sequentially via the current Python interpreter (`sys.executable`) from project root, preserving stdout/stderr for cron logs.
6. Stop the chain on the first non-zero child exit code and return that code. Caveat: child per-script lock skips exit `0`, so if the orchestrator needs to treat "child already running" as a stop condition, it must parse the Spanish lock-skip stderr text or, better, avoid direct overlap by making cron call only `proceso.py`.
7. Keep the existing per-script locks; they remain useful defense-in-depth for manual invocations or accidental direct cron entries.

Avoid relying only on `flock` because it is host-local and the project docs call out multi-server safety via PostgreSQL advisory locks. A local `flock` can be added as an extra guard for same-host cron noise, but the authoritative lock should be Radar DB advisory lock.

## Start Here

Open `scripts/sync_trh_raw_to_radar.py` first. It has the clearest common patterns for `.env` loading, DB config, advisory lock acquisition, argparse defaults, stdout progress, and CLI exit behavior that `proceso.py` should mirror before chaining the other scripts.

## Open Questions / Risks

- `build_monthly_aggregates.py` default mode rebuilds all affected periods with status `completed` every run and does not update those statuses after aggregation. Confirm whether `proceso.py` should accept repeated rebuilds, pass `--period` values from this run only, or introduce/expect a downstream consumed status elsewhere.
- Child scripts return useful counts from `main()`, but CLI execution ignores them; only process exit code and stdout/stderr are available to an orchestrator using subprocesses.
- `.env.example` could not be read because the runtime safety policy blocked access to sensitive env paths; env assumptions above come from script code and docs.
- Engram memory tools were not available in this subagent toolset, so important discoveries could not be saved to Engram despite the instruction.
