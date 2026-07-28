#!/usr/bin/env python3
"""
Extract Radar TRH keywords for monthly news periods.

Sources:
- dictionary: editable canonical aliases from config/keyword_dictionary.yml
- spaCy: Spanish named entities with es_core_news_lg
- YAKE: Spanish keyphrases

Modes:
    --full              process every month with published news
    --period YYYY-MM    process one month
    default             process pending periods from radar_affected_periods

Dictionary changes can affect all historical matches; run with --full and
--reset-period after significant dictionary edits.
"""

import argparse
import calendar
import importlib
import os
import re
import sys
import unicodedata
import zlib
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import date
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = PROJECT_ROOT / ".env"
DICTIONARY_PATH = PROJECT_ROOT / "config" / "keyword_dictionary.yml"
DEFAULT_SPACY_MODEL = "es_core_news_lg"
DEFAULT_MAX_TEXT_CHARS = 2500


class AlreadyRunning(RuntimeError):
    pass


def acquire_script_lock(conn, name):
    key = zlib.crc32(f"radar_trh:{name}".encode("utf-8")) & 0x7FFFFFFF
    with conn.cursor() as cur:
        cur.execute("SELECT pg_try_advisory_lock(%s)", (key,))
        acquired = cur.fetchone()[0]
    if not acquired:
        raise AlreadyRunning(f"{name}: ya hay otra ejecución activa; saliendo sin hacer cambios")


@dataclass(frozen=True)
class DictionaryEntry:
    canonical: str
    normalized: str
    keyword_type: str
    category: str | None
    priority: int
    enabled: bool
    aliases: tuple[str, ...]
    normalized_aliases: tuple[str, ...]


@dataclass(frozen=True)
class KeywordHit:
    keyword: str
    normalized_keyword: str
    canonical_keyword: str | None
    normalized_canonical_keyword: str | None
    keyword_type: str | None
    extractor_source: str
    score: float | None
    occurrences: int


def load_env_file(path=ENV_PATH):
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def env_int(name, default):
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def db_config(prefix="RADAR"):
    password = os.getenv(f"{prefix}_DB_PASSWORD")
    if not password:
        raise RuntimeError(f"Falta {prefix}_DB_PASSWORD en .env")
    return {
        "host": os.getenv(f"{prefix}_DB_HOST", "127.0.0.1"),
        "port": env_int(f"{prefix}_DB_PORT", 5432),
        "dbname": os.getenv(f"{prefix}_DB_NAME"),
        "user": os.getenv(f"{prefix}_DB_USER", "postgres"),
        "password": password,
    }


def normalize_text(value):
    value = (value or "").strip().casefold()
    value = unicodedata.normalize("NFKD", value)
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = re.sub(r"[^\w\s-]", " ", value, flags=re.UNICODE)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def clean_display(value):
    return re.sub(r"\s+", " ", (value or "").strip())


def month_start_from_string(value):
    if not re.match(r"^\d{4}-\d{2}$", value or ""):
        raise argparse.ArgumentTypeError("period must use YYYY-MM format")
    year, month = map(int, value.split("-"))
    if not 1 <= month <= 12:
        raise argparse.ArgumentTypeError("month must be between 01 and 12")
    return date(year, month, 1)


def month_bounds(month_start):
    last_day = calendar.monthrange(month_start.year, month_start.month)[1]
    next_month = date(month_start.year + (month_start.month // 12), (month_start.month % 12) + 1, 1)
    return month_start, next_month, last_day


def import_required(module_name, package_name=None):
    try:
        return importlib.import_module(module_name)
    except ImportError as exc:
        install_name = package_name or module_name
        raise RuntimeError(
            f"Falta dependencia '{install_name}'. Instalá requirements.txt y, si aplica, "
            "descargá el modelo spaCy configurado."
        ) from exc


def load_keyword_config(path=DICTIONARY_PATH):
    yaml = import_required("yaml", "PyYAML")

    if not path.exists():
        raise RuntimeError(f"No existe el diccionario de keywords: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    entries = []
    for raw in data.get("entries", []):
        canonical = clean_display(raw.get("canonical"))
        if not canonical:
            continue
        aliases = [clean_display(alias) for alias in raw.get("aliases", []) if clean_display(alias)]
        if canonical not in aliases:
            aliases.insert(0, canonical)
        normalized_aliases = tuple(dict.fromkeys(normalize_text(alias) for alias in aliases if normalize_text(alias)))
        entries.append(
            DictionaryEntry(
                canonical=canonical,
                normalized=normalize_text(canonical),
                keyword_type=raw.get("type") or "topic",
                category=raw.get("category"),
                priority=int(raw.get("priority", 0) or 0),
                enabled=bool(raw.get("enabled", True)),
                aliases=tuple(aliases),
                normalized_aliases=normalized_aliases,
            )
        )
    omitted_keywords = {
        normalized
        for keyword in data.get("omitted_keywords", [])
        if (normalized := normalize_text(keyword))
    }
    return entries, omitted_keywords


def load_dictionary(path=DICTIONARY_PATH):
    entries, _omitted_keywords = load_keyword_config(path)
    return entries


def sync_dictionary_to_db(conn, entries, *, dry_run=False):
    if dry_run:
        return

    current_keywords = [entry.normalized for entry in entries]
    current_aliases = [alias for entry in entries for alias in entry.normalized_aliases]

    with conn.cursor() as cur:
        for entry in entries:
            cur.execute(
                """
                INSERT INTO radar_keyword_dictionary (
                    canonical_keyword, normalized_keyword, keyword_type, category,
                    priority, enabled, source
                ) VALUES (%s, %s, %s, %s, %s, %s, 'config')
                ON CONFLICT (normalized_keyword) DO UPDATE SET
                    canonical_keyword = EXCLUDED.canonical_keyword,
                    keyword_type = EXCLUDED.keyword_type,
                    category = EXCLUDED.category,
                    priority = EXCLUDED.priority,
                    enabled = EXCLUDED.enabled,
                    updated_at = NOW()
                RETURNING id
                """,
                (
                    entry.canonical,
                    entry.normalized,
                    entry.keyword_type,
                    entry.category,
                    entry.priority,
                    entry.enabled,
                ),
            )
            keyword_id = cur.fetchone()[0]
            for alias in entry.aliases:
                normalized_alias = normalize_text(alias)
                if not normalized_alias:
                    continue
                cur.execute(
                    """
                    INSERT INTO radar_keyword_aliases (keyword_id, alias, normalized_alias, enabled)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (normalized_alias) DO UPDATE SET
                        keyword_id = EXCLUDED.keyword_id,
                        alias = EXCLUDED.alias,
                        enabled = EXCLUDED.enabled,
                        updated_at = NOW()
                    """,
                    (keyword_id, alias, normalized_alias, entry.enabled),
                )

        cur.execute(
            """
            UPDATE radar_keyword_dictionary
               SET enabled = FALSE,
                   updated_at = NOW()
             WHERE source = 'config'
               AND NOT (normalized_keyword = ANY(%s))
            """,
            (current_keywords,),
        )
        cur.execute(
            """
            UPDATE radar_keyword_aliases a
               SET enabled = FALSE,
                   updated_at = NOW()
              FROM radar_keyword_dictionary d
             WHERE a.keyword_id = d.id
               AND d.source = 'config'
               AND NOT (a.normalized_alias = ANY(%s))
            """,
            (current_aliases,),
        )


def build_document(row, max_text_chars):
    title = clean_display(row.get("titulo"))
    body = clean_display(row.get("texto_completo"))[:max_text_chars]
    return f"{title}. {body}".strip()


def count_alias_occurrences(normalized_document, normalized_alias):
    pattern = rf"(?<!\w){re.escape(normalized_alias)}(?!\w)"
    return len(re.findall(pattern, normalized_document, flags=re.UNICODE))


def extract_dictionary_hits(document, entries):
    normalized_document = normalize_text(document)
    hits = []
    for entry in entries:
        if not entry.enabled:
            continue
        occurrences = 0
        matched_aliases = []
        for normalized_alias in entry.normalized_aliases:
            count = count_alias_occurrences(normalized_document, normalized_alias)
            if count:
                occurrences += count
                matched_aliases.append(normalized_alias)
        if occurrences:
            score = 1.0 + (entry.priority / 100.0)
            hits.append(
                KeywordHit(
                    keyword=entry.canonical,
                    normalized_keyword=entry.normalized,
                    canonical_keyword=entry.canonical,
                    normalized_canonical_keyword=entry.normalized,
                    keyword_type=entry.keyword_type,
                    extractor_source="dictionary",
                    score=score,
                    occurrences=occurrences,
                )
            )
    return hits


def is_omitted_keyword(normalized_keyword, omitted_keywords):
    return normalized_keyword in omitted_keywords


def filter_omitted_hits(hits, omitted_keywords):
    if not omitted_keywords:
        return hits
    return [hit for hit in hits if not is_omitted_keyword(hit.normalized_keyword, omitted_keywords)]


def extract_spacy_hits(document, nlp, *, min_chars=3):
    doc = nlp(document)
    allowed_labels = {"PER", "LOC", "ORG", "MISC"}
    counts = Counter()
    labels = {}
    display = {}
    for ent in doc.ents:
        text = clean_display(ent.text)
        normalized = normalize_text(text)
        if len(normalized) < min_chars or ent.label_ not in allowed_labels:
            continue
        counts[normalized] += 1
        labels[normalized] = ent.label_.lower()
        display.setdefault(normalized, text)
    return [
        KeywordHit(
            keyword=display[normalized],
            normalized_keyword=normalized,
            canonical_keyword=None,
            normalized_canonical_keyword=None,
            keyword_type=labels.get(normalized),
            extractor_source="spacy",
            score=1.0,
            occurrences=count,
        )
        for normalized, count in counts.items()
    ]


def build_alias_map(entries):
    alias_map = {}
    for entry in entries:
        if not entry.enabled:
            continue
        for normalized_alias in entry.normalized_aliases:
            alias_map[normalized_alias] = entry
    return alias_map


def canonicalize_hit(hit, alias_map):
    entry = alias_map.get(hit.normalized_keyword)
    if entry is None:
        return hit
    return KeywordHit(
        keyword=entry.canonical,
        normalized_keyword=entry.normalized,
        canonical_keyword=entry.canonical,
        normalized_canonical_keyword=entry.normalized,
        keyword_type=entry.keyword_type,
        extractor_source=hit.extractor_source,
        score=hit.score,
        occurrences=hit.occurrences,
    )


def canonicalize_hits(hits, alias_map):
    return [canonicalize_hit(hit, alias_map) for hit in hits]


def extract_yake_hits(document, extractor, *, max_keywords, min_chars=4):
    raw_keywords = extractor.extract_keywords(document)
    hits = []
    seen = set()
    for phrase, score in raw_keywords[:max_keywords]:
        phrase = clean_display(phrase)
        normalized = normalize_text(phrase)
        if len(normalized) < min_chars or normalized in seen:
            continue
        seen.add(normalized)
        occurrences = max(1, count_alias_occurrences(normalize_text(document), normalized))
        # YAKE lower scores are better; invert for easier ranking while preserving signal.
        normalized_score = 1.0 / (1.0 + float(score))
        hits.append(
            KeywordHit(
                keyword=phrase,
                normalized_keyword=normalized,
                canonical_keyword=None,
                normalized_canonical_keyword=None,
                keyword_type="keyphrase",
                extractor_source="yake",
                score=normalized_score,
                occurrences=occurrences,
            )
        )
    return hits


def merge_hits(hits):
    merged = {}
    for hit in hits:
        key = (hit.normalized_keyword, hit.extractor_source)
        current = merged.get(key)
        if current is None:
            merged[key] = hit
            continue
        merged[key] = KeywordHit(
            keyword=current.keyword,
            normalized_keyword=current.normalized_keyword,
            canonical_keyword=current.canonical_keyword or hit.canonical_keyword,
            normalized_canonical_keyword=current.normalized_canonical_keyword or hit.normalized_canonical_keyword,
            keyword_type=current.keyword_type or hit.keyword_type,
            extractor_source=current.extractor_source,
            score=max(v for v in [current.score, hit.score] if v is not None) if current.score or hit.score else None,
            occurrences=current.occurrences + hit.occurrences,
        )
    return list(merged.values())


def create_run(conn, *, full, notes, dry_run=False):
    if dry_run:
        return None
    run_type = "full" if full else "incremental"
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO radar_processing_runs (run_type, status, notes)
            VALUES (%s, 'running', %s)
            RETURNING id
            """,
            (run_type, notes),
        )
        return cur.fetchone()[0]


def finish_run(conn, run_id, *, status, rows_detected=0, notes=None, dry_run=False):
    if dry_run or run_id is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            UPDATE radar_processing_runs
               SET status = %s,
                   finished_at = NOW(),
                   rows_detected = %s,
                   notes = COALESCE(%s, notes)
             WHERE id = %s
            """,
            (status, rows_detected, notes, run_id),
        )


def select_months(conn, args):
    if args.period:
        return [(args.period, None)]
    with conn.cursor() as cur:
        if args.full:
            cur.execute(
                """
                SELECT DISTINCT DATE_TRUNC('month', fecha_publicacion)::date AS month_start
                FROM radar_raw_noticias
                WHERE fecha_publicacion IS NOT NULL
                ORDER BY 1
                """
            )
            return [(row[0], None) for row in cur.fetchall()]
        statuses = ['pending', 'processing']
        if args.retry_failed:
            statuses.append('failed')
        cur.execute(
            """
            SELECT month_start, id
            FROM radar_affected_periods
            WHERE status = ANY(%s)
            ORDER BY month_start
            """,
            (statuses,),
        )
        return [(row[0], row[1]) for row in cur.fetchall()]


def mark_period(conn, affected_period_id, status, *, dry_run=False):
    if dry_run or affected_period_id is None:
        return
    with conn.cursor() as cur:
        cur.execute(
            "UPDATE radar_affected_periods SET status = %s, updated_at = NOW() WHERE id = %s",
            (status, affected_period_id),
        )


def fetch_news_for_month(conn, month_start, *, limit_news=None, skip_existing=True):
    start, end, _ = month_bounds(month_start)
    query = """
        SELECT id, noticia_hash, fuente, titulo, texto_completo, fecha_publicacion
        FROM radar_raw_noticias r
        WHERE fecha_publicacion >= %s
          AND fecha_publicacion < %s
    """
    params = [start, end]
    if skip_existing:
        query += """
          AND NOT EXISTS (
              SELECT 1
              FROM radar_news_keyword_processing kp
              WHERE kp.raw_noticia_id = r.id
                AND kp.status = 'completed'
          )
        """
    query += " ORDER BY fecha_publicacion, id"
    if limit_news:
        query += " LIMIT %s"
        params.append(limit_news)
    with conn.cursor() as cur:
        cur.execute(query, params)
        columns = [desc[0] for desc in cur.description]
        return [dict(zip(columns, row)) for row in cur.fetchall()]


def reset_month(conn, month_start, *, dry_run=False):
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM radar_news_keywords WHERE month_start = %s", (month_start,))
        cur.execute("DELETE FROM radar_monthly_keyword_stats WHERE month_start = %s", (month_start,))


def reset_keyword_processing(conn, month_start, *, dry_run=False):
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM radar_news_keyword_processing WHERE month_start = %s", (month_start,))


def mark_news_processed(conn, rows, *, run_id, dry_run=False):
    if dry_run or not rows:
        return 0
    sql = """
        INSERT INTO radar_news_keyword_processing (
            raw_noticia_id, month_start, status, keyword_rows, updated_from_run_id
        ) VALUES %s
        ON CONFLICT (raw_noticia_id) DO UPDATE SET
            month_start = EXCLUDED.month_start,
            status = EXCLUDED.status,
            keyword_rows = EXCLUDED.keyword_rows,
            processed_at = NOW(),
            updated_from_run_id = EXCLUDED.updated_from_run_id,
            updated_at = NOW()
    """
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=1000)
    return len(rows)


def prune_omitted_keywords(conn, month_start, omitted_keywords, *, dry_run=False):
    if dry_run or not omitted_keywords:
        return 0
    with conn.cursor() as cur:
        cur.execute(
            """
            DELETE FROM radar_news_keywords
            WHERE month_start = %s
              AND normalized_keyword = ANY(%s)
            """,
            (month_start, sorted(omitted_keywords)),
        )
        return cur.rowcount


def insert_news_keywords(conn, rows, *, dry_run=False):
    if dry_run or not rows:
        return 0
    sql = """
        INSERT INTO radar_news_keywords (
            raw_noticia_id, noticia_hash, month_start, keyword, normalized_keyword,
            canonical_keyword, normalized_canonical_keyword, keyword_type,
            extractor_source, score, occurrences, source_media
        ) VALUES %s
        ON CONFLICT (raw_noticia_id, normalized_keyword, extractor_source) DO UPDATE SET
            keyword = EXCLUDED.keyword,
            canonical_keyword = EXCLUDED.canonical_keyword,
            normalized_canonical_keyword = EXCLUDED.normalized_canonical_keyword,
            keyword_type = EXCLUDED.keyword_type,
            score = EXCLUDED.score,
            occurrences = EXCLUDED.occurrences,
            source_media = EXCLUDED.source_media,
            updated_at = NOW()
    """
    from psycopg2.extras import execute_values

    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=1000)
    return len(rows)


def refresh_monthly_stats(conn, month_start, run_id, *, dry_run=False):
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute("DELETE FROM radar_monthly_keyword_stats WHERE month_start = %s", (month_start,))
        cur.execute(
            """
            WITH keyword_media AS (
                SELECT
                    month_start,
                    normalized_keyword,
                    source_media,
                    COUNT(DISTINCT raw_noticia_id)::int AS media_news_count
                FROM radar_news_keywords
                WHERE month_start = %s
                GROUP BY month_start, normalized_keyword, source_media
            ), keyword_media_json AS (
                SELECT
                    month_start,
                    normalized_keyword,
                    COUNT(*)::int AS source_media_count,
                    jsonb_object_agg(source_media, media_news_count) AS source_media_stats
                FROM keyword_media
                GROUP BY month_start, normalized_keyword
            ), keyword_base AS (
                SELECT
                    nk.month_start,
                    MIN(nk.keyword) AS keyword,
                    nk.normalized_keyword,
                    MAX(nk.canonical_keyword) AS canonical_keyword,
                    MAX(nk.normalized_canonical_keyword) AS normalized_canonical_keyword,
                    MAX(nk.keyword_type) AS keyword_type,
                    ARRAY_AGG(DISTINCT nk.extractor_source) AS extractor_sources,
                    COUNT(DISTINCT nk.raw_noticia_id)::int AS news_count,
                    SUM(nk.occurrences)::int AS total_occurrences,
                    AVG(nk.score) AS avg_score,
                    COALESCE(MAX(d.priority), 0) AS priority
                FROM radar_news_keywords nk
                LEFT JOIN radar_keyword_dictionary d
                  ON d.normalized_keyword = COALESCE(nk.normalized_canonical_keyword, nk.normalized_keyword)
                WHERE nk.month_start = %s
                GROUP BY nk.month_start, nk.normalized_keyword
            )
            INSERT INTO radar_monthly_keyword_stats (
                month_start, keyword, normalized_keyword, canonical_keyword,
                normalized_canonical_keyword, keyword_type, extractor_sources,
                news_count, total_occurrences, avg_score, source_media_count,
                source_media_stats, priority, updated_from_run_id
            )
            SELECT
                b.month_start,
                b.keyword,
                b.normalized_keyword,
                b.canonical_keyword,
                b.normalized_canonical_keyword,
                b.keyword_type,
                b.extractor_sources,
                b.news_count,
                b.total_occurrences,
                b.avg_score,
                COALESCE(m.source_media_count, 0),
                COALESCE(m.source_media_stats, '{}'::jsonb),
                b.priority,
                %s
            FROM keyword_base b
            LEFT JOIN keyword_media_json m
              ON m.month_start = b.month_start
             AND m.normalized_keyword = b.normalized_keyword
            """,
            (month_start, month_start, run_id),
        )


def build_keyword_rows_for_news(row, month_start, *, entries, alias_map, omitted_keywords, nlp, yake_extractor, args):
    document = build_document(row, args.max_text_chars)
    hits = []
    hits.extend(extract_dictionary_hits(document, entries))
    hits.extend(canonicalize_hits(extract_spacy_hits(document, nlp), alias_map))
    hits.extend(canonicalize_hits(extract_yake_hits(document, yake_extractor, max_keywords=args.yake_max_keywords), alias_map))
    hits = filter_omitted_hits(merge_hits(hits), omitted_keywords)
    return [
        (
            row["id"],
            row["noticia_hash"],
            month_start,
            hit.keyword,
            hit.normalized_keyword,
            hit.canonical_keyword,
            hit.normalized_canonical_keyword,
            hit.keyword_type,
            hit.extractor_source,
            hit.score,
            hit.occurrences,
            row["fuente"],
        )
        for hit in hits
    ]


def process_month(conn, month_start, *, affected_period_id, entries, alias_map, omitted_keywords, nlp, yake_extractor, args, run_id):
    mark_period(conn, affected_period_id, "processing", dry_run=args.dry_run)
    if args.reset_period:
        reset_month(conn, month_start, dry_run=args.dry_run)
        reset_keyword_processing(conn, month_start, dry_run=args.dry_run)
    if not args.dry_run:
        conn.commit()

    skip_existing = not args.reset_period and not args.no_skip_existing
    news_rows = fetch_news_for_month(conn, month_start, limit_news=args.limit_news, skip_existing=skip_existing)
    processed_news = 0
    total_keyword_rows = 0
    pending_insert_rows = []
    pending_processed_rows = []

    print(f"{month_start}: selected_news={len(news_rows)} skip_existing={skip_existing}")
    for row in news_rows:
        keyword_rows = build_keyword_rows_for_news(
            row,
            month_start,
            entries=entries,
            alias_map=alias_map,
            omitted_keywords=omitted_keywords,
            nlp=nlp,
            yake_extractor=yake_extractor,
            args=args,
        )
        pending_insert_rows.extend(keyword_rows)
        pending_processed_rows.append((row["id"], month_start, "completed", len(keyword_rows), run_id))
        processed_news += 1
        total_keyword_rows += len(keyword_rows)

        if processed_news % args.commit_every == 0:
            inserted = insert_news_keywords(conn, pending_insert_rows, dry_run=args.dry_run)
            marked = mark_news_processed(conn, pending_processed_rows, run_id=run_id, dry_run=args.dry_run)
            pending_insert_rows = []
            pending_processed_rows = []
            if not args.dry_run:
                conn.commit()
            print(f"{month_start}: committed news={processed_news}/{len(news_rows)} keyword_rows={inserted} processed_markers={marked}")

    inserted = insert_news_keywords(conn, pending_insert_rows, dry_run=args.dry_run)
    marked = mark_news_processed(conn, pending_processed_rows, run_id=run_id, dry_run=args.dry_run)
    if (pending_insert_rows or pending_processed_rows) and not args.dry_run:
        conn.commit()
    if pending_insert_rows or pending_processed_rows:
        print(f"{month_start}: committed final news={processed_news}/{len(news_rows)} keyword_rows={inserted} processed_markers={marked}")

    pruned = prune_omitted_keywords(conn, month_start, omitted_keywords, dry_run=args.dry_run)
    if pruned:
        print(f"{month_start}: pruned omitted keyword rows={pruned}")

    refresh_monthly_stats(conn, month_start, run_id, dry_run=args.dry_run)
    mark_period(conn, affected_period_id, "completed", dry_run=args.dry_run)
    if not args.dry_run:
        conn.commit()
    print(f"{month_start}: completed news={processed_news} keyword_rows={total_keyword_rows}")
    return processed_news, total_keyword_rows


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Extract Radar TRH keywords by monthly period")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--full", action="store_true", help="process every month with published news")
    mode.add_argument("--period", type=month_start_from_string, help="process one month in YYYY-MM format")
    parser.add_argument(
        "--pending",
        action="store_true",
        help="process pending radar_affected_periods (default when --full/--period are omitted)",
    )
    parser.add_argument("--dictionary", type=Path, default=DICTIONARY_PATH, help="keyword dictionary YAML path")
    parser.add_argument("--spacy-model", default=DEFAULT_SPACY_MODEL, help="Spanish spaCy model")
    parser.add_argument("--limit-news", type=int, help="limit news per month, useful for smoke tests")
    parser.add_argument("--commit-every", type=int, default=10, help="commit progress every N news items")
    parser.add_argument("--retry-failed", action="store_true", help="also process affected periods marked failed")
    parser.add_argument("--no-skip-existing", action="store_true", help="reprocess news even if keyword rows already exist")
    parser.add_argument("--max-text-chars", type=int, default=DEFAULT_MAX_TEXT_CHARS, help="max body chars per news item")
    parser.add_argument("--yake-max-keywords", type=int, default=12, help="YAKE keyphrases per news item")
    parser.add_argument("--reset-period", action="store_true", help="delete existing keyword rows/stats before processing each period")
    parser.add_argument("--dry-run", action="store_true", help="read and extract but do not write database changes")
    parser.add_argument("--notes", help="optional note stored on the processing run")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.limit_news is not None and args.limit_news <= 0:
        raise RuntimeError("--limit-news debe ser mayor a 0")
    if args.yake_max_keywords <= 0:
        raise RuntimeError("--yake-max-keywords debe ser mayor a 0")
    if args.commit_every <= 0:
        raise RuntimeError("--commit-every debe ser mayor a 0")
    if args.limit_news is not None and not args.period:
        raise RuntimeError("--limit-news solo se permite con --period para smoke tests")

    psycopg2 = import_required("psycopg2", "psycopg2-binary")
    load_env_file()
    conn = psycopg2.connect(**db_config("RADAR"))

    run_id = None
    total_news = 0
    total_keyword_rows = 0
    try:
        acquire_script_lock(conn, "extract_keywords")

        yake = import_required("yake")
        spacy = import_required("spacy")
        entries, omitted_keywords = load_keyword_config(args.dictionary)
        alias_map = build_alias_map(entries)
        print(f"dictionary entries: {len(entries)}")
        print(f"omitted keywords: {len(omitted_keywords)}")
        print(f"loading spaCy model: {args.spacy_model}")
        nlp = spacy.load(args.spacy_model)
        yake_extractor = yake.KeywordExtractor(lan="es", n=3, dedupLim=0.9, top=args.yake_max_keywords)

        full_run = bool(args.full)
        run_id = create_run(conn, full=full_run, notes=args.notes or "extract keywords", dry_run=args.dry_run)
        sync_dictionary_to_db(conn, entries, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
        months = select_months(conn, args)
        if not months:
            print("no periods selected")
            finish_run(conn, run_id, status="completed", rows_detected=0, dry_run=args.dry_run)
            conn.commit()
            return 0

        print(f"periods selected: {len(months)}")
        for month_start, affected_period_id in months:
            news_count, keyword_count = process_month(
                conn,
                month_start,
                affected_period_id=affected_period_id,
                entries=entries,
                alias_map=alias_map,
                omitted_keywords=omitted_keywords,
                nlp=nlp,
                yake_extractor=yake_extractor,
                args=args,
                run_id=run_id,
            )
            total_news += news_count
            total_keyword_rows += keyword_count
            if not args.dry_run:
                conn.commit()

        finish_run(conn, run_id, status="completed", rows_detected=total_news, dry_run=args.dry_run)
        if not args.dry_run:
            conn.commit()
        print(f"keyword extraction complete | news={total_news} keyword_rows={total_keyword_rows}")
        return total_keyword_rows
    except Exception as exc:
        conn.rollback()
        if run_id is not None:
            try:
                finish_run(conn, run_id, status="failed", rows_detected=total_news, notes=str(exc), dry_run=args.dry_run)
                if not args.dry_run:
                    conn.commit()
            except Exception:
                conn.rollback()
        raise
    finally:
        conn.close()


if __name__ == "__main__":
    try:
        main()
    except AlreadyRunning as exc:
        print(str(exc), file=sys.stderr)
        sys.exit(0)
    except Exception as exc:
        print(f"extract keywords error: {exc}", file=sys.stderr)
        sys.exit(1)
