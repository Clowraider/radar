<script lang="ts">
  import type { PageData } from './$types';

  let { data }: { data: PageData } = $props();

  const numberFormatter = new Intl.NumberFormat('es-AR');
  const compactFormatter = new Intl.NumberFormat('es-AR', {
    notation: 'compact',
    maximumFractionDigits: 1
  });

  const monthLabel = $derived(
    data.months.find((month) => month.value === data.selectedMonth)?.label ?? 'Sin datos'
  );
  const maxDaily = $derived(Math.max(...data.dailyActivity.map((day) => day.newsCount), 1));
  const maxSource = $derived(Math.max(...data.sources.map((source) => source.newsCount), 1));
  const peakDay = $derived(
    data.dailyActivity.reduce(
      (peak, day) => (day.newsCount > peak.newsCount ? day : peak),
      { date: null as string | null, newsCount: 0 }
    )
  );
  const activityPath = $derived(
    data.dailyActivity.length > 0
      ? data.dailyActivity
          .map((day, index) => {
            const x = data.dailyActivity.length === 1 ? 50 : (index / (data.dailyActivity.length - 1)) * 100;
            const y = 90 - (day.newsCount / maxDaily) * 76;
            return `${x},${y}`;
          })
          .join(' ')
      : ''
  );

  function formatNumber(value: number | null | undefined) {
    return numberFormatter.format(value ?? 0);
  }

  function formatCompact(value: number | null | undefined) {
    return compactFormatter.format(value ?? 0);
  }

  function formatDate(value: string | null | undefined) {
    if (!value) return 'Sin fecha';
    return new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'long', year: 'numeric' }).format(
      new Date(`${value}T00:00:00`)
    );
  }

  function formatDateShort(value: string | null | undefined) {
    if (!value) return 'Sin fecha';
    return new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short' }).format(
      new Date(`${value}T00:00:00`)
    );
  }
</script>

<svelte:head>
  <title>{data.keyword} — Radar</title>
  <meta
    name="description"
    content={`Radar muestra noticias, actividad diaria y cobertura por fuentes para ${data.keyword}.`}
  />
</svelte:head>

<main class="relative min-h-screen overflow-hidden px-4 py-5 text-slate-100 sm:px-6 lg:px-10">
  <div class="pointer-events-none absolute inset-0 overflow-hidden">
    <div class="absolute left-[7%] top-14 h-52 w-52 animate-float rounded-full bg-radar-cyan/20 blur-3xl"></div>
    <div class="absolute right-[12%] top-10 h-64 w-64 rounded-full bg-radar-violet/20 blur-3xl"></div>
    <div class="absolute bottom-10 left-1/2 h-72 w-72 rounded-full bg-radar-amber/10 blur-3xl"></div>
    <div class="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.04)_1px,transparent_1px)] bg-[size:56px_56px] opacity-30"></div>
  </div>

  <section class="relative mx-auto flex w-full max-w-7xl flex-col gap-7">
    <header class="flex flex-col gap-4 pt-3 sm:flex-row sm:items-center sm:justify-between">
      <a href={`/?month=${data.selectedMonth ?? ''}`} class="group flex items-center gap-3" aria-label="Volver a Radar home">
        <span class="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-radar-cyan/35 bg-radar-cyan/10 shadow-glow">
          <span class="absolute h-4 w-4 animate-pulseGlow rounded-full bg-radar-cyan"></span>
          <span class="h-8 w-8 rounded-full border border-radar-cyan/40"></span>
        </span>
        <span>
          <span class="block text-xl font-semibold tracking-tight text-white">Radar</span>
          <span class="block text-xs uppercase tracking-[0.3em] text-radar-cyan/80">detalle de tema</span>
        </span>
      </a>

      <form class="glass-panel rounded-2xl px-3 py-2" method="GET" aria-label="Seleccionar mes">
        <label class="sr-only" for="month">Mes</label>
        <select
          id="month"
          name="month"
          class="w-full min-w-56 rounded-xl border border-slate-700/70 bg-slate-950/80 px-4 py-3 text-sm font-medium capitalize text-slate-100 outline-none transition hover:border-radar-cyan/60 focus:border-radar-cyan focus:ring-2 focus:ring-radar-cyan/20"
          onchange={(event) => event.currentTarget.form?.requestSubmit()}
        >
          {#each data.months as month}
            <option value={month.value} selected={month.value === data.selectedMonth}>
              {month.label} · {formatCompact(month.totalNews)} noticias
            </option>
          {/each}
        </select>
      </form>
    </header>

    <section class="grid gap-5 lg:grid-cols-[1.05fr_0.95fr]">
      <article class="glass-panel relative overflow-hidden rounded-[2rem] p-6 sm:p-8 lg:p-10">
        <div class="absolute right-0 top-0 h-48 w-48 rounded-full bg-radar-cyan/10 blur-3xl"></div>
        <div class="relative z-10">
          <p class="mb-4 inline-flex rounded-full border border-radar-cyan/20 bg-radar-cyan/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-radar-cyan">
            Tema · {monthLabel}
          </p>
          <h1 class="max-w-4xl text-4xl font-semibold tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
            {data.keyword}
          </h1>
          <p class="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
            Lectura pública del tema: volumen de noticias, ritmo diario, cobertura por fuentes anonimizadas y artículos relacionados.
          </p>

          <div class="mt-8 grid gap-3 sm:grid-cols-3">
            <div class="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
              <p class="text-sm text-slate-400">Noticias</p>
              <p class="mt-2 text-4xl font-semibold text-white">{formatNumber(data.overview?.newsCount)}</p>
            </div>
            <div class="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
              <p class="text-sm text-slate-400">Menciones</p>
              <p class="mt-2 text-4xl font-semibold text-white">{formatNumber(data.overview?.totalOccurrences)}</p>
            </div>
            <div class="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
              <p class="text-sm text-slate-400">Pico diario</p>
              <p class="mt-2 text-4xl font-semibold text-radar-cyan">{formatNumber(peakDay.newsCount)}</p>
            </div>
          </div>
        </div>
      </article>

      <article class="glass-panel rounded-[2rem] p-6 sm:p-7">
        <div class="mb-6 flex items-end justify-between gap-4">
          <div>
            <p class="text-sm uppercase tracking-[0.24em] text-radar-cyan/90">Ritmo del tema</p>
            <h2 class="mt-2 text-2xl font-semibold text-white">Actividad diaria</h2>
          </div>
          <p class="text-right text-sm text-slate-400">{formatDateShort(peakDay.date)}</p>
        </div>

        {#if data.dailyActivity.length > 0}
          <div class="relative h-72 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/45 p-4">
            <svg class="absolute inset-0 h-full w-full p-4" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
              <defs>
                <linearGradient id="topic-activity-line" x1="0" x2="1" y1="0" y2="0">
                  <stop offset="0%" stop-color="#8b5cf6" />
                  <stop offset="60%" stop-color="#42e8f4" />
                  <stop offset="100%" stop-color="#fbbf24" />
                </linearGradient>
              </defs>
              <polyline points={activityPath} fill="none" stroke="url(#topic-activity-line)" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
            </svg>

            <div class="absolute inset-x-4 bottom-4 flex h-44 items-end gap-1.5 sm:gap-2">
              {#each data.dailyActivity as day}
                <div class="group relative flex min-w-0 flex-1 items-end justify-center">
                  <div
                    class="w-full rounded-t-xl border border-radar-cyan/20 bg-gradient-to-t from-radar-violet/70 via-radar-cyan/75 to-white opacity-95 shadow-[0_0_18px_rgba(66,232,244,0.18)] transition duration-300 group-hover:scale-y-105 group-hover:opacity-100 group-hover:shadow-glow"
                    style={`height: ${Math.max(10, (day.newsCount / maxDaily) * 100)}%`}
                  ></div>
                  <div class="pointer-events-none absolute bottom-full z-20 mb-3 hidden min-w-max rounded-xl border border-white/10 bg-slate-950 px-3 py-2 text-xs text-white shadow-2xl group-hover:block">
                    <span class="block whitespace-nowrap capitalize">{formatDateShort(day.date)}</span>
                    <span class="block whitespace-nowrap text-radar-cyan">{formatNumber(day.newsCount)} noticias</span>
                  </div>
                </div>
              {/each}
            </div>
          </div>
        {:else}
          <div class="rounded-3xl border border-dashed border-white/15 bg-slate-950/35 p-8 text-center">
            <p class="text-lg font-semibold text-white">Sin actividad para este tema en el mes.</p>
            <p class="mt-2 text-sm text-slate-400">Probá otro mes o volvé al pulso mensual.</p>
          </div>
        {/if}
      </article>
    </section>

    <section class="grid gap-5 lg:grid-cols-[0.82fr_1.18fr]">
      <article class="glass-panel rounded-[2rem] p-6 sm:p-7">
        <div class="mb-7 flex items-end justify-between gap-4">
          <div>
            <p class="text-sm uppercase tracking-[0.24em] text-radar-amber/90">Cobertura</p>
            <h2 class="mt-2 text-2xl font-semibold text-white">Fuentes</h2>
          </div>
          <p class="text-right text-sm text-slate-400">Aliases públicos</p>
        </div>

        {#if data.sources.length > 0}
          <div class="space-y-4">
            {#each data.sources as source, index}
              <div class="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                <div class="mb-3 flex items-center justify-between gap-3">
                  <div class="flex items-center gap-3">
                    <span class="flex h-9 w-9 items-center justify-center rounded-xl bg-radar-amber/10 text-sm font-bold text-radar-amber">
                      {index + 1}
                    </span>
                    <div>
                      <p class="font-semibold text-white">{source.alias}</p>
                      <p class="text-xs text-slate-400">{formatNumber(source.totalOccurrences)} menciones</p>
                    </div>
                  </div>
                  <p class="text-lg font-semibold text-white">{formatNumber(source.newsCount)}</p>
                </div>
                <div class="h-2 overflow-hidden rounded-full bg-slate-800">
                  <div
                    class="h-full rounded-full bg-gradient-to-r from-radar-amber to-radar-cyan transition-all duration-700"
                    style={`width: ${Math.max(3, (source.newsCount / maxSource) * 100)}%`}
                  ></div>
                </div>
              </div>
            {/each}
          </div>
        {:else}
          <p class="rounded-3xl border border-dashed border-white/15 bg-slate-950/35 p-6 text-center text-slate-400">Sin cobertura por fuentes para este tema.</p>
        {/if}
      </article>

      <article class="glass-panel rounded-[2rem] p-6 sm:p-7">
        <div class="mb-7 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <p class="text-sm uppercase tracking-[0.24em] text-radar-violet/90">Lectura</p>
            <h2 class="mt-2 text-2xl font-semibold text-white">Noticias relacionadas</h2>
            <p class="mt-2 text-sm text-slate-400">Links externos, sin imágenes de los sitios fuente.</p>
          </div>

          <form class="grid gap-3 sm:grid-cols-2" method="GET" aria-label="Filtrar noticias relacionadas">
            <input type="hidden" name="month" value={data.selectedMonth ?? ''} />
            <label class="grid gap-1 text-xs uppercase tracking-[0.18em] text-slate-500">
              Fuente
              <select
                name="source"
                class="min-w-36 rounded-xl border border-slate-700/70 bg-slate-950/80 px-3 py-2 text-sm normal-case tracking-normal text-slate-100 outline-none transition hover:border-radar-cyan/60 focus:border-radar-cyan focus:ring-2 focus:ring-radar-cyan/20"
                onchange={(event) => event.currentTarget.form?.requestSubmit()}
              >
                <option value="all" selected={data.selectedSource === 'all'}>Todas</option>
                {#each data.sources as source}
                  <option value={source.key} selected={data.selectedSource === source.key}>
                    {source.alias}
                  </option>
                {/each}
              </select>
            </label>

            <label class="grid gap-1 text-xs uppercase tracking-[0.18em] text-slate-500">
              Orden
              <select
                name="order"
                class="min-w-40 rounded-xl border border-slate-700/70 bg-slate-950/80 px-3 py-2 text-sm normal-case tracking-normal text-slate-100 outline-none transition hover:border-radar-cyan/60 focus:border-radar-cyan focus:ring-2 focus:ring-radar-cyan/20"
                onchange={(event) => event.currentTarget.form?.requestSubmit()}
              >
                <option value="representative" selected={data.order === 'representative'}>Más representativas</option>
                <option value="recent" selected={data.order === 'recent'}>Más recientes</option>
              </select>
            </label>
          </form>
        </div>

        {#if data.news.length > 0}
          <div class="grid gap-4">
            {#each data.news as article}
              {#snippet articleContent()}
                <div class="flex h-16 w-16 items-center justify-center rounded-2xl border border-white/10 bg-slate-950/60 text-xs uppercase tracking-[0.22em] text-radar-cyan/70">
                  Radar
                </div>
                <div class="flex flex-col justify-between gap-3">
                  <div>
                    <p class="text-xs uppercase tracking-[0.2em] text-slate-500">{formatDate(article.publishedAt)}</p>
                    <h3 class="mt-2 text-lg font-semibold leading-snug text-white transition group-hover:text-radar-cyan">
                      {article.title}
                    </h3>
                  </div>
                  <p class="text-sm text-slate-400">Abrir noticia original →</p>
                </div>
              {/snippet}

              {#if article.url}
                <a
                  class="group grid gap-4 rounded-3xl border border-white/10 bg-white/[0.035] p-4 transition duration-300 hover:-translate-y-0.5 hover:border-radar-cyan/45 hover:bg-radar-cyan/10 sm:grid-cols-[4.5rem_1fr]"
                  href={article.url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  {@render articleContent()}
                </a>
              {:else}
                <div
                  class="group grid gap-4 rounded-3xl border border-white/10 bg-white/[0.035] p-4 sm:grid-cols-[4.5rem_1fr]"
                >
                  {@render articleContent()}
                </div>
              {/if}
            {/each}
          </div>
        {:else}
          <div class="rounded-3xl border border-dashed border-white/15 bg-slate-950/35 p-8 text-center">
            <p class="text-lg font-semibold text-white">No se encontraron noticias para este filtro.</p>
            <p class="mt-2 text-sm text-slate-400">Probá otra fuente, otro orden o volvé al pulso mensual.</p>
          </div>
        {/if}
      </article>
    </section>
  </section>
</main>
