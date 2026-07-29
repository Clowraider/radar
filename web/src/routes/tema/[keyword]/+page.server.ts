import type { PageServerLoad } from "./$types";
import { error } from "@sveltejs/kit";
import { query } from "$lib/server/db";

type MonthRow = {
	month_start: Date | string;
	total_news: number;
};

type TopicOverviewRow = {
	news_count: number;
	total_occurrences: number;
	first_publication_at: Date | string | null;
	last_publication_at: Date | string | null;
};

type TopicDailyRow = {
	activity_date: Date | string;
	news_count: number;
};

type TopicSourceRow = {
	source_media: string;
	alias: string | null;
	news_count: number;
	total_occurrences: number;
};

function aliasToKey(alias: string | null, fallbackIndex: number): string {
	if (!alias) return `fuente-${fallbackIndex + 1}`;
	const match = alias.match(/^Fuente (\d+)$/);
	return match ? `fuente-${match[1]}` : `fuente-${fallbackIndex + 1}`;
}

type TopicNewsRow = {
	id: string | number;
	title: string;
	url_original: string | null;
	fecha_publicacion: Date | string | null;
	total_occurrences: number;
};

type ResolvedKeywordRow = {
	keyword: string;
	normalized_keyword: string;
	news_count: number;
};

function normalizeKeyword(value: string) {
	return value
		.trim()
		.toLocaleLowerCase("es-AR")
		.normalize("NFD")
		.replace(/[\u0300-\u036f]/g, "")
		.replace(/[^\p{L}\p{N}\s-]/gu, " ")
		.replace(/\s+/g, " ")
		.trim();
}

function toMonth(value: Date | string) {
	if (value instanceof Date) return value.toISOString().slice(0, 7);
	return String(value).slice(0, 7);
}

function toDate(value: Date | string | null) {
	if (!value) return null;
	if (value instanceof Date) return value.toISOString().slice(0, 10);
	return String(value).slice(0, 10);
}

function decodeKeyword(value: string) {
	try {
		return decodeURIComponent(value).trim();
	} catch {
		return value.trim();
	}
}

function validateUrl(value: string | null): string | null {
	if (!value) return null;

	try {
		const url = new URL(value);
		if (url.protocol === "http:" || url.protocol === "https:") {
			return value;
		}
	} catch {
		// Invalid URL: fall through to return null
	}

	return null;
}

export const load: PageServerLoad = async ({ params, url }) => {
	const keyword = decodeKeyword(params.keyword);
	const normalizedKeyword = normalizeKeyword(keyword);

	if (!normalizedKeyword) {
		throw error(404, "Keyword not found");
	}

	const monthsResult = await query<MonthRow>(
		`
      SELECT month_start, total_news
      FROM radar_monthly_overview
      WHERE total_news > 0
      ORDER BY month_start DESC
    `,
	);

	const months = monthsResult.rows.map((row) => ({
		value: toMonth(row.month_start),
		label: new Intl.DateTimeFormat("es-AR", {
			month: "long",
			year: "numeric",
		}).format(new Date(`${toMonth(row.month_start)}-01T00:00:00`)),
		totalNews: row.total_news,
	}));

	const requestedMonth = url.searchParams.get("month");
	const selectedMonth = months.some((month) => month.value === requestedMonth)
		? requestedMonth
		: months[0]?.value;

	if (!selectedMonth) {
		return {
			keyword,
			normalizedKeyword,
			months,
			selectedMonth: null,
			overview: null,
			dailyActivity: [],
			sources: [],
			news: [],
		};
	}

	const monthStart = `${selectedMonth}-01`;
	const resolvedResult = await query<ResolvedKeywordRow>(
		`
      SELECT
        COALESCE(canonical_keyword, keyword) AS keyword,
        normalized_keyword,
        news_count
      FROM radar_monthly_keyword_stats
      WHERE month_start = $1::date
        AND (
          normalized_keyword = $2
          OR normalized_canonical_keyword = $2
        )
      ORDER BY news_count DESC, total_occurrences DESC
      LIMIT 1
    `,
		[monthStart, normalizedKeyword],
	);
	let resolvedKeyword = resolvedResult.rows[0];

	if (!resolvedKeyword) {
		const fuzzyResult = await query<ResolvedKeywordRow>(
			`
        SELECT
          COALESCE(canonical_keyword, keyword) AS keyword,
          normalized_keyword,
          news_count
        FROM radar_monthly_keyword_stats
        WHERE month_start = $1::date
          AND (
            position(normalized_keyword in $2) > 0
            OR position($2 in normalized_keyword) > 0
          )
        ORDER BY
          CASE WHEN position(normalized_keyword in $2) > 0 THEN 0 ELSE 1 END,
          news_count DESC,
          total_occurrences DESC
        LIMIT 1
      `,
			[monthStart, normalizedKeyword],
		);
		resolvedKeyword = fuzzyResult.rows[0];
	}

	const effectiveKeyword = resolvedKeyword?.keyword ?? keyword;
	const effectiveNormalizedKeyword =
		resolvedKeyword?.normalized_keyword ?? normalizedKeyword;
	const order =
		url.searchParams.get("order") === "recent" ? "recent" : "representative";
	const requestedSource = url.searchParams.get("source") ?? "all";
	const matchCondition = `
      nk.month_start = $1::date
      AND (
        nk.normalized_keyword = $2
        OR nk.normalized_canonical_keyword = $2
      )
    `;

	const [overviewResult, dailyResult, sourcesResult] = await Promise.all([
		query<TopicOverviewRow>(
			`
        SELECT
          COUNT(DISTINCT nk.raw_noticia_id)::int AS news_count,
          COALESCE(SUM(nk.occurrences), 0)::int AS total_occurrences,
          MIN(r.fecha_publicacion) AS first_publication_at,
          MAX(r.fecha_publicacion) AS last_publication_at
        FROM radar_news_keywords nk
        JOIN radar_raw_noticias r ON r.id = nk.raw_noticia_id
        WHERE ${matchCondition}
      `,
			[monthStart, effectiveNormalizedKeyword],
		),
		query<TopicDailyRow>(
			`
        SELECT
          r.fecha_publicacion::date AS activity_date,
          COUNT(DISTINCT nk.raw_noticia_id)::int AS news_count
        FROM radar_news_keywords nk
        JOIN radar_raw_noticias r ON r.id = nk.raw_noticia_id
        WHERE ${matchCondition}
          AND r.fecha_publicacion IS NOT NULL
        GROUP BY r.fecha_publicacion::date
        ORDER BY activity_date ASC
      `,
			[monthStart, effectiveNormalizedKeyword],
		),
		query<TopicSourceRow>(
			`
        SELECT
          COALESCE(a.alias, nk.source_media) AS alias,
          nk.source_media,
          nk.news_count,
          nk.total_occurrences
        FROM radar_source_keyword_stats nk
        LEFT JOIN radar_source_aliases a ON a.source_name = nk.source_media
        WHERE ${matchCondition}
        ORDER BY nk.news_count DESC, nk.total_occurrences DESC, nk.source_media ASC
        LIMIT 8
      `,
			[monthStart, effectiveNormalizedKeyword],
		),
	]);

	const sourceOptions = sourcesResult.rows.map((row, index) => ({
		key: aliasToKey(row.alias, index),
		alias: row.alias ?? row.source_media,
		media: row.source_media,
		newsCount: row.news_count,
		totalOccurrences: row.total_occurrences,
	}));
	const selectedSource = sourceOptions.find(
		(source) => source.key === requestedSource,
	);
	const newsValues: unknown[] = [monthStart, effectiveNormalizedKeyword];
	const sourceFilter = selectedSource ? "AND nk.source_media = $3" : "";
	if (selectedSource) newsValues.push(selectedSource.media);
	const orderClause =
		order === "recent"
			? "r.fecha_publicacion DESC NULLS LAST, total_occurrences DESC, r.id DESC"
			: "total_occurrences DESC, r.fecha_publicacion DESC NULLS LAST, r.id DESC";
	const newsResult = await query<TopicNewsRow>(
		`
        SELECT
          r.id,
          r.titulo AS title,
          r.url_original,
          r.fecha_publicacion,
          COALESCE(SUM(nk.occurrences), 0)::int AS total_occurrences
        FROM radar_news_keywords nk
        JOIN radar_raw_noticias r ON r.id = nk.raw_noticia_id
        WHERE ${matchCondition}
          ${sourceFilter}
        GROUP BY r.id, r.titulo, r.url_original, r.fecha_publicacion
        ORDER BY ${orderClause}
        LIMIT 30
      `,
		newsValues,
	);

	const overviewRow = overviewResult.rows[0];

	return {
		keyword: effectiveKeyword,
		requestedKeyword: keyword,
		normalizedKeyword: effectiveNormalizedKeyword,
		requestedNormalizedKeyword: normalizedKeyword,
		order,
		selectedSource: selectedSource?.key ?? "all",
		months,
		selectedMonth,
		overview: overviewRow
			? {
					newsCount: overviewRow.news_count,
					totalOccurrences: overviewRow.total_occurrences,
					firstPublicationAt: toDate(overviewRow.first_publication_at),
					lastPublicationAt: toDate(overviewRow.last_publication_at),
				}
			: null,
		dailyActivity: dailyResult.rows.map((row) => ({
			date: toDate(row.activity_date),
			newsCount: row.news_count,
		})),
		sources: sourceOptions.map((source) => ({
			key: source.key,
			alias: source.alias,
			newsCount: source.newsCount,
			totalOccurrences: source.totalOccurrences,
		})),
		news: newsResult.rows.map((row) => ({
			id: String(row.id),
			title: row.title,
			url: validateUrl(row.url_original),
			publishedAt: toDate(row.fecha_publicacion),
			totalOccurrences: row.total_occurrences,
		})),
	};
};
