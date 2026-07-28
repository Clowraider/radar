import { dev } from "$app/environment";
import dotenv from "dotenv";
import { existsSync } from "node:fs";
import { resolve } from "node:path";
import pg from "pg";

const { Pool } = pg;

let envLoaded = false;
let pool: pg.Pool | undefined;

function loadEnvironment() {
	if (envLoaded) return;

	const candidates = [
		resolve(process.cwd(), "radar-web.env"),
		resolve(process.cwd(), ".env"),
		resolve(process.cwd(), "..", ".env"),
	];
	for (const path of candidates) {
		if (existsSync(path)) {
			dotenv.config({ path, override: false });
		}
	}

	envLoaded = true;
}

function numberFromEnv(value: string | undefined, fallback: number) {
	if (!value) return fallback;
	const parsed = Number(value);
	return Number.isFinite(parsed) ? parsed : fallback;
}

function createPool() {
	loadEnvironment();

	if (process.env.DATABASE_URL) {
		return new Pool({
			connectionString: process.env.DATABASE_URL,
			max: numberFromEnv(process.env.RADAR_DB_POOL_MAX, dev ? 4 : 10),
			idleTimeoutMillis: 30_000,
		});
	}

	return new Pool({
		host: process.env.RADAR_DB_HOST || "localhost",
		port: numberFromEnv(process.env.RADAR_DB_PORT, 5432),
		database: process.env.RADAR_DB_NAME || "radar_trh",
		user: process.env.RADAR_DB_USER || "postgres",
		password: process.env.RADAR_DB_PASSWORD,
		max: numberFromEnv(process.env.RADAR_DB_POOL_MAX, dev ? 4 : 10),
		idleTimeoutMillis: 30_000,
	});
}

export function getPool() {
	if (!pool) pool = createPool();
	return pool;
}

export async function query<T extends pg.QueryResultRow>(
	sql: string,
	values: unknown[] = [],
) {
	return getPool().query<T>(sql, values);
}
