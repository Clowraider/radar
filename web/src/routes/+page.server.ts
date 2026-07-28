import type { PageServerLoad } from "./$types";
import { query } from "$lib/server/db";

type MonthRow = {
	month_start: Date | string;
	total_news: number;
};

type OverviewRow = {
	month_start: Date | string;
	total_news: number;
	news_with_keywords: number;
	active_source_count: number;
	keyword_count: number;
	top_keywords: unknown;
	first_publication_at: Date | string | null;
	last_publication_at: Date | string | null;
};

type DailyRow = {
	activity_date: Date | string;
	news_count: number;
};

type SourceRow = {
	source_media: string;
	news_count: number;
	distinct_keywords: number;
};

type KeywordFallbackRow = {
	keyword: string | null;
	canonical_keyword: string | null;
	news_count: number;
	total_occurrences: number;
};

type KeywordItem = {
	label: string;
	weight: number;
	occurrences?: number;
};

function toMonth(value: Date | string) {
	if (value instanceof Date) return value.toISOString().slice(0, 7);
	return String(value).slice(0, 7);
}

function toDate(value: Date | string) {
	if (value instanceof Date) return value.toISOString().slice(0, 10);
	return String(value).slice(0, 10);
}

function toNumber(value: unknown) {
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : 0;
}

function normalizeTopKeywords(value: unknown): KeywordItem[] {
	if (!Array.isArray(value)) return [];

	return value
		.map((item) => {
			if (typeof item === "string") {
				return { label: item, weight: 1 };
			}

			if (!item || typeof item !== "object") return null;
			const record = item as Record<string, unknown>;
			const label = String(
				record.keyword ??
					record.canonical_keyword ??
					record.label ??
					record.name ??
					record.term ??
					"",
			).trim();

			if (!label) return null;

			return {
				label,
				weight: toNumber(
					record.news_count ??
						record.weight ??
						record.count ??
						record.total_occurrences ??
						1,
				),
				occurrences:
					toNumber(record.total_occurrences ?? record.occurrences ?? 0) ||
					undefined,
			};
		})
		.filter((item): item is KeywordItem => Boolean(item))
		.slice(0, 24);
}

async function getKeywordFallback(month: string): Promise<KeywordItem[]> {
	const result = await query<KeywordFallbackRow>(
		`
      SELECT
        COALESCE(canonical_keyword, keyword) AS keyword,
        canonical_keyword,
        SUM(news_count)::int AS news_count,
        SUM(total_occurrences)::int AS total_occurrences
      FROM radar_source_keyword_stats
      WHERE month_start = $1::date
      GROUP BY COALESCE(canonical_keyword, keyword), canonical_keyword
      ORDER BY SUM(news_count) DESC, SUM(total_occurrences) DESC
      LIMIT 24
    `,
		[`${month}-01`],
	);

	return result.rows.map((row) => ({
		label: row.canonical_keyword || row.keyword || "Tema",
		weight: row.news_count,
		occurrences: row.total_occurrences,
	}));
}

export const load: PageServerLoad = async ({ url }) => {
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
			months,
			selectedMonth: null,
			overview: null,
			dailyActivity: [],
			sources: [],
			topKeywords: [],
		};
	}

	const [overviewResult, dailyResult, sourcesResult] = await Promise.all([
		query<OverviewRow>(
			`
        SELECT
          month_start,
          total_news,
          news_with_keywords,
          active_source_count,
          keyword_count,
          top_keywords,
          first_publication_at,
          last_publication_at
        FROM radar_monthly_overview
        WHERE month_start = $1::date
        LIMIT 1
      `,
			[`${selectedMonth}-01`],
		),
		query<DailyRow>(
			`
        SELECT activity_date, news_count
        FROM radar_daily_activity
        WHERE month_start = $1::date
        ORDER BY activity_date ASC
      `,
			[`${selectedMonth}-01`],
		),
		query<SourceRow>(
			`
        SELECT source_media, news_count, distinct_keywords
        FROM radar_source_monthly_stats
        WHERE month_start = $1::date
        ORDER BY news_count DESC, source_media ASC
        LIMIT 8
      `,
			[`${selectedMonth}-01`],
		),
	]);

	const overviewRow = overviewResult.rows[0];
	let topKeywords = normalizeTopKeywords(overviewRow?.top_keywords);
	if (topKeywords.length === 0)
		topKeywords = await getKeywordFallback(selectedMonth);

	return {
		months,
		selectedMonth,
		overview: overviewRow
			? {
					month: toMonth(overviewRow.month_start),
					totalNews: overviewRow.total_news,
					newsWithKeywords: overviewRow.news_with_keywords,
					activeSourceCount: overviewRow.active_source_count,
					keywordCount: overviewRow.keyword_count,
					firstPublicationAt: overviewRow.first_publication_at
						? toDate(overviewRow.first_publication_at)
						: null,
					lastPublicationAt: overviewRow.last_publication_at
						? toDate(overviewRow.last_publication_at)
						: null,
				}
			: null,
		dailyActivity: dailyResult.rows.map((row) => ({
			date: toDate(row.activity_date),
			newsCount: row.news_count,
		})),
		sources: sourcesResult.rows.map((row, index) => ({
			alias: `Fuente ${index + 1}`,
			newsCount: row.news_count,
			distinctKeywords: row.distinct_keywords,
		})),
		topKeywords,
	};
};
