--
-- PostgreSQL database dump
--


-- Dumped from database version 18.3 (Debian 18.3-1.pgdg13+1)
-- Dumped by pg_dump version 18.4 (Ubuntu 18.4-1.pgdg24.04+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: vector; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public;


--
-- Name: EXTENSION vector; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON EXTENSION vector IS 'vector data type and ivfflat and hnsw access methods';


--
-- Name: set_radar_keywords_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_radar_keywords_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: set_radar_processing_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_radar_processing_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


--
-- Name: set_radar_raw_noticias_updated_at(); Type: FUNCTION; Schema: public; Owner: -
--

CREATE FUNCTION public.set_radar_raw_noticias_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: radar_affected_periods; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_affected_periods (
    id bigint NOT NULL,
    processing_run_id bigint,
    year integer NOT NULL,
    month integer NOT NULL,
    month_start date NOT NULL,
    status character varying(20) DEFAULT 'pending'::character varying NOT NULL,
    reason character varying(60) DEFAULT 'detected'::character varying NOT NULL,
    rows_detected integer DEFAULT 0 NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT radar_affected_periods_month_check CHECK (((month >= 1) AND (month <= 12))),
    CONSTRAINT radar_affected_periods_status_check CHECK (((status)::text = ANY (ARRAY[('pending'::character varying)::text, ('processing'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text, ('skipped'::character varying)::text])))
);


--
-- Name: radar_affected_periods_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_affected_periods_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_affected_periods_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_affected_periods_id_seq OWNED BY public.radar_affected_periods.id;


--
-- Name: radar_daily_activity; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_daily_activity (
    id bigint NOT NULL,
    month_start date NOT NULL,
    activity_date date NOT NULL,
    news_count integer DEFAULT 0 NOT NULL,
    updated_from_run_id bigint,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_daily_activity_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_daily_activity_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_daily_activity_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_daily_activity_id_seq OWNED BY public.radar_daily_activity.id;


--
-- Name: radar_keyword_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_keyword_aliases (
    id bigint NOT NULL,
    keyword_id bigint NOT NULL,
    alias text NOT NULL,
    normalized_alias text NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_keyword_aliases_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_keyword_aliases_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_keyword_aliases_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_keyword_aliases_id_seq OWNED BY public.radar_keyword_aliases.id;


--
-- Name: radar_keyword_dictionary; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_keyword_dictionary (
    id bigint NOT NULL,
    canonical_keyword text NOT NULL,
    normalized_keyword text NOT NULL,
    keyword_type character varying(40) DEFAULT 'topic'::character varying NOT NULL,
    category character varying(80),
    priority integer DEFAULT 0 NOT NULL,
    enabled boolean DEFAULT true NOT NULL,
    source character varying(40) DEFAULT 'config'::character varying NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_keyword_dictionary_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_keyword_dictionary_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_keyword_dictionary_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_keyword_dictionary_id_seq OWNED BY public.radar_keyword_dictionary.id;


--
-- Name: radar_monthly_keyword_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_monthly_keyword_stats (
    id bigint NOT NULL,
    month_start date NOT NULL,
    keyword text NOT NULL,
    normalized_keyword text NOT NULL,
    canonical_keyword text,
    normalized_canonical_keyword text,
    keyword_type character varying(40),
    extractor_sources text[] DEFAULT '{}'::text[] NOT NULL,
    news_count integer DEFAULT 0 NOT NULL,
    total_occurrences integer DEFAULT 0 NOT NULL,
    avg_score numeric(12,6),
    source_media_count integer DEFAULT 0 NOT NULL,
    source_media_stats jsonb DEFAULT '{}'::jsonb NOT NULL,
    priority integer DEFAULT 0 NOT NULL,
    updated_from_run_id bigint,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_monthly_keyword_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_monthly_keyword_stats_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_monthly_keyword_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_monthly_keyword_stats_id_seq OWNED BY public.radar_monthly_keyword_stats.id;


--
-- Name: radar_monthly_overview; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_monthly_overview (
    month_start date NOT NULL,
    total_news integer DEFAULT 0 NOT NULL,
    news_with_keywords integer DEFAULT 0 NOT NULL,
    active_source_count integer DEFAULT 0 NOT NULL,
    keyword_count integer DEFAULT 0 NOT NULL,
    top_keywords jsonb DEFAULT '[]'::jsonb NOT NULL,
    source_stats jsonb DEFAULT '[]'::jsonb NOT NULL,
    first_publication_at timestamp without time zone,
    last_publication_at timestamp without time zone,
    updated_from_run_id bigint,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_news_keyword_processing; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_news_keyword_processing (
    raw_noticia_id bigint NOT NULL,
    month_start date NOT NULL,
    status character varying(20) DEFAULT 'completed'::character varying NOT NULL,
    keyword_rows integer DEFAULT 0 NOT NULL,
    processed_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_from_run_id bigint,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT radar_news_keyword_processing_status_check CHECK (((status)::text = ANY (ARRAY[('completed'::character varying)::text, ('failed'::character varying)::text])))
);


--
-- Name: radar_news_keywords; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_news_keywords (
    id bigint NOT NULL,
    raw_noticia_id bigint NOT NULL,
    noticia_hash character varying(64) NOT NULL,
    month_start date NOT NULL,
    keyword text NOT NULL,
    normalized_keyword text NOT NULL,
    canonical_keyword text,
    normalized_canonical_keyword text,
    keyword_type character varying(40),
    extractor_source character varying(20) NOT NULL,
    score numeric(12,6),
    occurrences integer DEFAULT 1 NOT NULL,
    source_media character varying(100),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT radar_news_keywords_extractor_source_check CHECK (((extractor_source)::text = ANY (ARRAY[('dictionary'::character varying)::text, ('spacy'::character varying)::text, ('yake'::character varying)::text])))
);


--
-- Name: radar_news_keywords_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_news_keywords_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_news_keywords_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_news_keywords_id_seq OWNED BY public.radar_news_keywords.id;


--
-- Name: radar_processing_runs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_processing_runs (
    id bigint NOT NULL,
    run_type character varying(20) NOT NULL,
    status character varying(20) DEFAULT 'running'::character varying NOT NULL,
    started_at timestamp without time zone DEFAULT now() NOT NULL,
    finished_at timestamp without time zone,
    lookback_hours integer,
    rows_detected integer DEFAULT 0 NOT NULL,
    notes text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    CONSTRAINT radar_processing_runs_run_type_check CHECK (((run_type)::text = ANY (ARRAY[('full'::character varying)::text, ('incremental'::character varying)::text]))),
    CONSTRAINT radar_processing_runs_status_check CHECK (((status)::text = ANY (ARRAY[('running'::character varying)::text, ('completed'::character varying)::text, ('failed'::character varying)::text])))
);


--
-- Name: radar_processing_runs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_processing_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_processing_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_processing_runs_id_seq OWNED BY public.radar_processing_runs.id;


--
-- Name: radar_raw_noticias; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_raw_noticias (
    id bigint NOT NULL,
    trh_noticia_id integer,
    noticia_hash character varying(64) NOT NULL,
    fuente character varying(100) NOT NULL,
    url_original text NOT NULL,
    titulo text NOT NULL,
    texto_completo text,
    url_imagen text,
    fecha_publicacion timestamp without time zone,
    fecha_extraccion timestamp without time zone,
    embedding public.vector(768),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    synced_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_raw_noticias_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_raw_noticias_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_raw_noticias_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_raw_noticias_id_seq OWNED BY public.radar_raw_noticias.id;


--
-- Name: radar_source_aliases; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_source_aliases (
    source_name text NOT NULL,
    alias text NOT NULL,
    created_at timestamp with time zone DEFAULT now()
);


--
-- Name: radar_source_keyword_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_source_keyword_stats (
    id bigint NOT NULL,
    month_start date NOT NULL,
    source_media text NOT NULL,
    keyword text NOT NULL,
    normalized_keyword text NOT NULL,
    canonical_keyword text,
    normalized_canonical_keyword text,
    keyword_type character varying(40),
    news_count integer DEFAULT 0 NOT NULL,
    total_occurrences integer DEFAULT 0 NOT NULL,
    avg_score numeric(12,6),
    updated_from_run_id bigint,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_source_keyword_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_source_keyword_stats_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_source_keyword_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_source_keyword_stats_id_seq OWNED BY public.radar_source_keyword_stats.id;


--
-- Name: radar_source_monthly_stats; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.radar_source_monthly_stats (
    id bigint NOT NULL,
    month_start date NOT NULL,
    source_media text NOT NULL,
    news_count integer DEFAULT 0 NOT NULL,
    keyword_rows integer DEFAULT 0 NOT NULL,
    distinct_keywords integer DEFAULT 0 NOT NULL,
    top_keywords jsonb DEFAULT '[]'::jsonb NOT NULL,
    updated_from_run_id bigint,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


--
-- Name: radar_source_monthly_stats_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.radar_source_monthly_stats_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: radar_source_monthly_stats_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.radar_source_monthly_stats_id_seq OWNED BY public.radar_source_monthly_stats.id;


--
-- Name: radar_affected_periods id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_affected_periods ALTER COLUMN id SET DEFAULT nextval('public.radar_affected_periods_id_seq'::regclass);


--
-- Name: radar_daily_activity id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_daily_activity ALTER COLUMN id SET DEFAULT nextval('public.radar_daily_activity_id_seq'::regclass);


--
-- Name: radar_keyword_aliases id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_aliases ALTER COLUMN id SET DEFAULT nextval('public.radar_keyword_aliases_id_seq'::regclass);


--
-- Name: radar_keyword_dictionary id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_dictionary ALTER COLUMN id SET DEFAULT nextval('public.radar_keyword_dictionary_id_seq'::regclass);


--
-- Name: radar_monthly_keyword_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_monthly_keyword_stats ALTER COLUMN id SET DEFAULT nextval('public.radar_monthly_keyword_stats_id_seq'::regclass);


--
-- Name: radar_news_keywords id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keywords ALTER COLUMN id SET DEFAULT nextval('public.radar_news_keywords_id_seq'::regclass);


--
-- Name: radar_processing_runs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_processing_runs ALTER COLUMN id SET DEFAULT nextval('public.radar_processing_runs_id_seq'::regclass);


--
-- Name: radar_raw_noticias id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_raw_noticias ALTER COLUMN id SET DEFAULT nextval('public.radar_raw_noticias_id_seq'::regclass);


--
-- Name: radar_source_keyword_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_keyword_stats ALTER COLUMN id SET DEFAULT nextval('public.radar_source_keyword_stats_id_seq'::regclass);


--
-- Name: radar_source_monthly_stats id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_monthly_stats ALTER COLUMN id SET DEFAULT nextval('public.radar_source_monthly_stats_id_seq'::regclass);


--
-- Name: radar_affected_periods radar_affected_periods_month_start_reason_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_affected_periods
    ADD CONSTRAINT radar_affected_periods_month_start_reason_key UNIQUE (month_start, reason);


--
-- Name: radar_affected_periods radar_affected_periods_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_affected_periods
    ADD CONSTRAINT radar_affected_periods_pkey PRIMARY KEY (id);


--
-- Name: radar_daily_activity radar_daily_activity_month_start_activity_date_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_daily_activity
    ADD CONSTRAINT radar_daily_activity_month_start_activity_date_key UNIQUE (month_start, activity_date);


--
-- Name: radar_daily_activity radar_daily_activity_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_daily_activity
    ADD CONSTRAINT radar_daily_activity_pkey PRIMARY KEY (id);


--
-- Name: radar_keyword_aliases radar_keyword_aliases_normalized_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_aliases
    ADD CONSTRAINT radar_keyword_aliases_normalized_alias_key UNIQUE (normalized_alias);


--
-- Name: radar_keyword_aliases radar_keyword_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_aliases
    ADD CONSTRAINT radar_keyword_aliases_pkey PRIMARY KEY (id);


--
-- Name: radar_keyword_dictionary radar_keyword_dictionary_canonical_keyword_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_dictionary
    ADD CONSTRAINT radar_keyword_dictionary_canonical_keyword_key UNIQUE (canonical_keyword);


--
-- Name: radar_keyword_dictionary radar_keyword_dictionary_normalized_keyword_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_dictionary
    ADD CONSTRAINT radar_keyword_dictionary_normalized_keyword_key UNIQUE (normalized_keyword);


--
-- Name: radar_keyword_dictionary radar_keyword_dictionary_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_dictionary
    ADD CONSTRAINT radar_keyword_dictionary_pkey PRIMARY KEY (id);


--
-- Name: radar_monthly_keyword_stats radar_monthly_keyword_stats_month_start_normalized_keyword_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_monthly_keyword_stats
    ADD CONSTRAINT radar_monthly_keyword_stats_month_start_normalized_keyword_key UNIQUE (month_start, normalized_keyword);


--
-- Name: radar_monthly_keyword_stats radar_monthly_keyword_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_monthly_keyword_stats
    ADD CONSTRAINT radar_monthly_keyword_stats_pkey PRIMARY KEY (id);


--
-- Name: radar_monthly_overview radar_monthly_overview_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_monthly_overview
    ADD CONSTRAINT radar_monthly_overview_pkey PRIMARY KEY (month_start);


--
-- Name: radar_news_keyword_processing radar_news_keyword_processing_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keyword_processing
    ADD CONSTRAINT radar_news_keyword_processing_pkey PRIMARY KEY (raw_noticia_id);


--
-- Name: radar_news_keywords radar_news_keywords_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keywords
    ADD CONSTRAINT radar_news_keywords_pkey PRIMARY KEY (id);


--
-- Name: radar_news_keywords radar_news_keywords_raw_noticia_id_normalized_keyword_extra_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keywords
    ADD CONSTRAINT radar_news_keywords_raw_noticia_id_normalized_keyword_extra_key UNIQUE (raw_noticia_id, normalized_keyword, extractor_source);


--
-- Name: radar_processing_runs radar_processing_runs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_processing_runs
    ADD CONSTRAINT radar_processing_runs_pkey PRIMARY KEY (id);


--
-- Name: radar_raw_noticias radar_raw_noticias_noticia_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_raw_noticias
    ADD CONSTRAINT radar_raw_noticias_noticia_hash_key UNIQUE (noticia_hash);


--
-- Name: radar_raw_noticias radar_raw_noticias_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_raw_noticias
    ADD CONSTRAINT radar_raw_noticias_pkey PRIMARY KEY (id);


--
-- Name: radar_source_aliases radar_source_aliases_alias_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_aliases
    ADD CONSTRAINT radar_source_aliases_alias_key UNIQUE (alias);


--
-- Name: radar_source_aliases radar_source_aliases_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_aliases
    ADD CONSTRAINT radar_source_aliases_pkey PRIMARY KEY (source_name);


--
-- Name: radar_source_keyword_stats radar_source_keyword_stats_month_start_source_media_normali_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_keyword_stats
    ADD CONSTRAINT radar_source_keyword_stats_month_start_source_media_normali_key UNIQUE (month_start, source_media, normalized_keyword);


--
-- Name: radar_source_keyword_stats radar_source_keyword_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_keyword_stats
    ADD CONSTRAINT radar_source_keyword_stats_pkey PRIMARY KEY (id);


--
-- Name: radar_source_monthly_stats radar_source_monthly_stats_month_start_source_media_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_monthly_stats
    ADD CONSTRAINT radar_source_monthly_stats_month_start_source_media_key UNIQUE (month_start, source_media);


--
-- Name: radar_source_monthly_stats radar_source_monthly_stats_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_monthly_stats
    ADD CONSTRAINT radar_source_monthly_stats_pkey PRIMARY KEY (id);


--
-- Name: idx_radar_affected_periods_month_start; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_affected_periods_month_start ON public.radar_affected_periods USING btree (month_start);


--
-- Name: idx_radar_affected_periods_run; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_affected_periods_run ON public.radar_affected_periods USING btree (processing_run_id);


--
-- Name: idx_radar_affected_periods_status_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_affected_periods_status_month ON public.radar_affected_periods USING btree (status, month_start);


--
-- Name: idx_radar_daily_activity_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_daily_activity_month ON public.radar_daily_activity USING btree (month_start, activity_date);


--
-- Name: idx_radar_keyword_aliases_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_keyword_aliases_enabled ON public.radar_keyword_aliases USING btree (enabled);


--
-- Name: idx_radar_keyword_aliases_keyword; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_keyword_aliases_keyword ON public.radar_keyword_aliases USING btree (keyword_id);


--
-- Name: idx_radar_keyword_dictionary_enabled; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_keyword_dictionary_enabled ON public.radar_keyword_dictionary USING btree (enabled);


--
-- Name: idx_radar_keyword_dictionary_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_keyword_dictionary_type ON public.radar_keyword_dictionary USING btree (keyword_type);


--
-- Name: idx_radar_monthly_keyword_stats_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_monthly_keyword_stats_canonical ON public.radar_monthly_keyword_stats USING btree (normalized_canonical_keyword);


--
-- Name: idx_radar_monthly_keyword_stats_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_monthly_keyword_stats_month ON public.radar_monthly_keyword_stats USING btree (month_start);


--
-- Name: idx_radar_monthly_keyword_stats_rank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_monthly_keyword_stats_rank ON public.radar_monthly_keyword_stats USING btree (month_start, priority DESC, news_count DESC, total_occurrences DESC);


--
-- Name: idx_radar_monthly_overview_total_news; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_monthly_overview_total_news ON public.radar_monthly_overview USING btree (total_news DESC);


--
-- Name: idx_radar_news_keyword_processing_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keyword_processing_month ON public.radar_news_keyword_processing USING btree (month_start);


--
-- Name: idx_radar_news_keyword_processing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keyword_processing_status ON public.radar_news_keyword_processing USING btree (status);


--
-- Name: idx_radar_news_keywords_canonical; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keywords_canonical ON public.radar_news_keywords USING btree (normalized_canonical_keyword);


--
-- Name: idx_radar_news_keywords_media; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keywords_media ON public.radar_news_keywords USING btree (source_media);


--
-- Name: idx_radar_news_keywords_month; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keywords_month ON public.radar_news_keywords USING btree (month_start);


--
-- Name: idx_radar_news_keywords_normalized; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keywords_normalized ON public.radar_news_keywords USING btree (normalized_keyword);


--
-- Name: idx_radar_news_keywords_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_news_keywords_source ON public.radar_news_keywords USING btree (extractor_source);


--
-- Name: idx_radar_processing_runs_run_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_processing_runs_run_type ON public.radar_processing_runs USING btree (run_type);


--
-- Name: idx_radar_processing_runs_status_started; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_processing_runs_status_started ON public.radar_processing_runs USING btree (status, started_at DESC);


--
-- Name: idx_radar_raw_noticias_embedding; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_raw_noticias_embedding ON public.radar_raw_noticias USING hnsw (embedding public.vector_cosine_ops) WHERE (embedding IS NOT NULL);


--
-- Name: idx_radar_raw_noticias_fecha_extraccion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_raw_noticias_fecha_extraccion ON public.radar_raw_noticias USING btree (fecha_extraccion);


--
-- Name: idx_radar_raw_noticias_fecha_publicacion; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_raw_noticias_fecha_publicacion ON public.radar_raw_noticias USING btree (fecha_publicacion);


--
-- Name: idx_radar_raw_noticias_fuente; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_raw_noticias_fuente ON public.radar_raw_noticias USING btree (fuente);


--
-- Name: idx_radar_raw_noticias_hash; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX idx_radar_raw_noticias_hash ON public.radar_raw_noticias USING btree (noticia_hash);


--
-- Name: idx_radar_raw_noticias_synced_at; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_raw_noticias_synced_at ON public.radar_raw_noticias USING btree (synced_at);


--
-- Name: idx_radar_source_aliases_alias; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_source_aliases_alias ON public.radar_source_aliases USING btree (alias);


--
-- Name: idx_radar_source_keyword_stats_keyword; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_source_keyword_stats_keyword ON public.radar_source_keyword_stats USING btree (normalized_keyword);


--
-- Name: idx_radar_source_keyword_stats_month_rank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_source_keyword_stats_month_rank ON public.radar_source_keyword_stats USING btree (month_start, news_count DESC, total_occurrences DESC);


--
-- Name: idx_radar_source_keyword_stats_source; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_source_keyword_stats_source ON public.radar_source_keyword_stats USING btree (month_start, source_media, news_count DESC);


--
-- Name: idx_radar_source_monthly_stats_month_rank; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_radar_source_monthly_stats_month_rank ON public.radar_source_monthly_stats USING btree (month_start, news_count DESC, source_media);


--
-- Name: radar_affected_periods trg_radar_affected_periods_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_affected_periods_updated_at BEFORE UPDATE ON public.radar_affected_periods FOR EACH ROW EXECUTE FUNCTION public.set_radar_processing_updated_at();


--
-- Name: radar_daily_activity trg_radar_daily_activity_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_daily_activity_updated_at BEFORE UPDATE ON public.radar_daily_activity FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_keyword_aliases trg_radar_keyword_aliases_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_keyword_aliases_updated_at BEFORE UPDATE ON public.radar_keyword_aliases FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_keyword_dictionary trg_radar_keyword_dictionary_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_keyword_dictionary_updated_at BEFORE UPDATE ON public.radar_keyword_dictionary FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_monthly_keyword_stats trg_radar_monthly_keyword_stats_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_monthly_keyword_stats_updated_at BEFORE UPDATE ON public.radar_monthly_keyword_stats FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_monthly_overview trg_radar_monthly_overview_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_monthly_overview_updated_at BEFORE UPDATE ON public.radar_monthly_overview FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_news_keyword_processing trg_radar_news_keyword_processing_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_news_keyword_processing_updated_at BEFORE UPDATE ON public.radar_news_keyword_processing FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_news_keywords trg_radar_news_keywords_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_news_keywords_updated_at BEFORE UPDATE ON public.radar_news_keywords FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_processing_runs trg_radar_processing_runs_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_processing_runs_updated_at BEFORE UPDATE ON public.radar_processing_runs FOR EACH ROW EXECUTE FUNCTION public.set_radar_processing_updated_at();


--
-- Name: radar_raw_noticias trg_radar_raw_noticias_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_raw_noticias_updated_at BEFORE UPDATE ON public.radar_raw_noticias FOR EACH ROW EXECUTE FUNCTION public.set_radar_raw_noticias_updated_at();


--
-- Name: radar_source_keyword_stats trg_radar_source_keyword_stats_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_source_keyword_stats_updated_at BEFORE UPDATE ON public.radar_source_keyword_stats FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_source_monthly_stats trg_radar_source_monthly_stats_updated_at; Type: TRIGGER; Schema: public; Owner: -
--

CREATE TRIGGER trg_radar_source_monthly_stats_updated_at BEFORE UPDATE ON public.radar_source_monthly_stats FOR EACH ROW EXECUTE FUNCTION public.set_radar_keywords_updated_at();


--
-- Name: radar_affected_periods radar_affected_periods_processing_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_affected_periods
    ADD CONSTRAINT radar_affected_periods_processing_run_id_fkey FOREIGN KEY (processing_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- Name: radar_daily_activity radar_daily_activity_updated_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_daily_activity
    ADD CONSTRAINT radar_daily_activity_updated_from_run_id_fkey FOREIGN KEY (updated_from_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- Name: radar_keyword_aliases radar_keyword_aliases_keyword_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_keyword_aliases
    ADD CONSTRAINT radar_keyword_aliases_keyword_id_fkey FOREIGN KEY (keyword_id) REFERENCES public.radar_keyword_dictionary(id) ON DELETE CASCADE;


--
-- Name: radar_monthly_keyword_stats radar_monthly_keyword_stats_updated_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_monthly_keyword_stats
    ADD CONSTRAINT radar_monthly_keyword_stats_updated_from_run_id_fkey FOREIGN KEY (updated_from_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- Name: radar_monthly_overview radar_monthly_overview_updated_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_monthly_overview
    ADD CONSTRAINT radar_monthly_overview_updated_from_run_id_fkey FOREIGN KEY (updated_from_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- Name: radar_news_keyword_processing radar_news_keyword_processing_raw_noticia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keyword_processing
    ADD CONSTRAINT radar_news_keyword_processing_raw_noticia_id_fkey FOREIGN KEY (raw_noticia_id) REFERENCES public.radar_raw_noticias(id) ON DELETE CASCADE;


--
-- Name: radar_news_keyword_processing radar_news_keyword_processing_updated_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keyword_processing
    ADD CONSTRAINT radar_news_keyword_processing_updated_from_run_id_fkey FOREIGN KEY (updated_from_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- Name: radar_news_keywords radar_news_keywords_raw_noticia_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_news_keywords
    ADD CONSTRAINT radar_news_keywords_raw_noticia_id_fkey FOREIGN KEY (raw_noticia_id) REFERENCES public.radar_raw_noticias(id) ON DELETE CASCADE;


--
-- Name: radar_source_keyword_stats radar_source_keyword_stats_updated_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_keyword_stats
    ADD CONSTRAINT radar_source_keyword_stats_updated_from_run_id_fkey FOREIGN KEY (updated_from_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- Name: radar_source_monthly_stats radar_source_monthly_stats_updated_from_run_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.radar_source_monthly_stats
    ADD CONSTRAINT radar_source_monthly_stats_updated_from_run_id_fkey FOREIGN KEY (updated_from_run_id) REFERENCES public.radar_processing_runs(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--


