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
  const maxKeyword = $derived(Math.max(...data.topKeywords.map((keyword) => keyword.weight), 1));
  const activeDays = $derived(data.dailyActivity.filter((day) => day.newsCount > 0).length);
  const peakDay = $derived(
    data.dailyActivity.reduce(
      (peak, day) => (day.newsCount > peak.newsCount ? day : peak),
      { date: '', newsCount: 0 }
    )
  );
  const activityPath = $derived(
    data.dailyActivity.length > 0
      ? data.dailyActivity
          .map((day, index) => {
            const x = data.dailyActivity.length === 1 ? 50 : (index / (data.dailyActivity.length - 1)) * 100;
            const y = 92 - (day.newsCount / maxDaily) * 78;
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

  const cloudPositions = [
    [50, 48, 0],
    [27, 34, 0],
    [73, 61, 0],
    [57, 25, -7],
    [39, 72, 0],
    [78, 32, 90],
    [20, 57, 0],
    [64, 82, 0],
    [84, 74, -6],
    [14, 25, 90],
    [36, 16, 0],
    [74, 14, 0],
    [14, 82, -8],
    [90, 49, 0],
    [49, 91, 90],
    [27, 89, 0],
    [58, 8, 0],
    [9, 45, 0],
    [92, 24, 90],
    [79, 91, 0],
    [34, 52, -5],
    [63, 43, 0],
    [44, 7, 90],
    [53, 66, 0]
  ];

  function keywordCloudTransform(index: number, scale = 1) {
    const [_x, _y, rotation] = cloudPositions[index % cloudPositions.length];
    return `translate(-50%, -50%) rotate(${rotation}deg) scale(${scale})`;
  }

  function keywordCloudStyle(weight: number, index: number) {
    const ratio = Math.max(0.12, Math.min(1, weight / maxKeyword));
    const [x, y] = cloudPositions[index % cloudPositions.length];
    const size = 0.78 + Math.pow(ratio, 0.62) * 2.45;
    const opacity = 0.42 + Math.pow(ratio, 0.5) * 0.58;
    const weightValue = ratio > 0.72 ? 800 : ratio > 0.38 ? 700 : 560;
    const color = ratio > 0.74 ? '#ffffff' : ratio > 0.45 ? '#b9f7fb' : ratio > 0.25 ? '#c4b5fd' : '#94a3b8';

    return [
      `left: ${x}%`,
      `top: ${y}%`,
      `font-size: clamp(0.82rem, ${size}rem, 4.1rem)`,
      `font-weight: ${weightValue}`,
      `opacity: ${opacity}`,
      `color: ${color}`,
      `transform: ${keywordCloudTransform(index)}`,
      `transform-origin: center`,
      `transition: transform 0.2s ease, opacity 0.2s ease, color 0.2s ease, text-shadow 0.2s ease`,
      `animation-delay: ${index * 45}ms`
    ].join('; ');
  }

  function keywordCloudHoverStyle(index: number) {
    return `transform: ${keywordCloudTransform(index, 1.32)}; opacity: 1; text-shadow: 0 0 22px rgba(66, 232, 244, 0.42)`;
  }

  function formatDateShort(value: string) {
    return new Intl.DateTimeFormat('es-AR', { day: '2-digit', month: 'short' }).format(
      new Date(`${value}T00:00:00`)
    );
  }

  function keywordHref(label: string) {
    return `/tema/${encodeURIComponent(label)}?month=${data.selectedMonth ?? ''}`;
  }
</script>

<svelte:head>
  <title>Radar — Pulso mensual</title>
  <meta
    name="description"
    content="Radar muestra en tiempo real la agenda mediática mensual: temas, fuentes, actividad diaria y conversaciones dominantes."
  />
</svelte:head>

<main class="relative min-h-screen overflow-hidden px-4 py-5 text-slate-100 sm:px-6 lg:px-10">
  <div class="pointer-events-none absolute inset-0 overflow-hidden">
    <div class="absolute left-[8%] top-16 h-48 w-48 animate-float rounded-full bg-radar-cyan/20 blur-3xl"></div>
    <div class="absolute right-[10%] top-8 h-64 w-64 rounded-full bg-radar-violet/20 blur-3xl"></div>
    <div class="absolute bottom-20 left-1/2 h-72 w-72 rounded-full bg-radar-amber/10 blur-3xl"></div>
    <div class="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.04)_1px,transparent_1px)] bg-[size:56px_56px] opacity-30"></div>
  </div>

  <section class="relative mx-auto flex w-full max-w-7xl flex-col gap-7">
    <header class="flex flex-col gap-4 pt-3 sm:flex-row sm:items-center sm:justify-between">
      <a href="/" class="group flex items-center gap-3" aria-label="Radar home">
        <span class="relative flex h-11 w-11 items-center justify-center rounded-2xl border border-radar-cyan/35 bg-radar-cyan/10 shadow-glow">
          <span class="absolute h-4 w-4 animate-pulseGlow rounded-full bg-radar-cyan"></span>
          <span class="h-8 w-8 rounded-full border border-radar-cyan/40"></span>
        </span>
        <span>
          <span class="block text-xl font-semibold tracking-tight text-white">Radar</span>
          <span class="block text-xs uppercase tracking-[0.3em] text-radar-cyan/80">agenda mediática</span>
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

    {#if data.overview}
      <section class="grid gap-5 lg:grid-cols-[1.12fr_0.88fr]">
        <article class="glass-panel relative overflow-hidden rounded-[2rem] p-6 sm:p-8 lg:p-10">
          <div class="absolute right-0 top-0 h-48 w-48 rounded-full bg-radar-cyan/10 blur-3xl"></div>
          <div class="relative z-10 flex min-h-[26rem] flex-col justify-between gap-8">
            <div class="max-w-3xl">
              <p class="mb-4 inline-flex rounded-full border border-radar-cyan/20 bg-radar-cyan/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-radar-cyan">
                Pulso mensual · {monthLabel}
              </p>
              <h1 class="text-4xl font-semibold tracking-[-0.05em] text-white sm:text-6xl lg:text-7xl">
                La agenda del mes, clara en 30 segundos.
              </h1>
              <p class="mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
                Radar convierte el archivo de noticias en una lectura visual de temas dominantes,
                actividad diaria y cobertura por fuentes públicas anonimizadas.
              </p>
            </div>

            <div class="grid gap-3 sm:grid-cols-3">
              <div class="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                <p class="text-sm text-slate-400">Noticias</p>
                <p class="mt-2 text-4xl font-semibold text-white">{formatNumber(data.overview.totalNews)}</p>
              </div>
              <div class="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                <p class="text-sm text-slate-400">Temas detectados</p>
                <p class="mt-2 text-4xl font-semibold text-white">{formatCompact(data.overview.keywordCount)}</p>
              </div>
              <div class="rounded-3xl border border-white/10 bg-white/[0.04] p-5">
                <p class="text-sm text-slate-400">Fuentes activas</p>
                <p class="mt-2 text-4xl font-semibold text-white">{formatNumber(data.overview.activeSourceCount)}</p>
              </div>
            </div>
          </div>
        </article>

        <aside class="glass-panel rounded-[2rem] p-6 sm:p-7">
          <div class="flex items-center justify-between gap-4">
            <div>
              <p class="text-sm uppercase tracking-[0.24em] text-radar-violet/90">Top temas</p>
              <h2 class="mt-2 text-2xl font-semibold text-white">Nube del mes</h2>
            </div>
            <span class="rounded-full border border-radar-violet/30 bg-radar-violet/10 px-3 py-1 text-xs text-radar-violet">
              live data
            </span>
          </div>

          <div class="relative mt-8 min-h-[24rem] overflow-hidden rounded-3xl bg-[radial-gradient(circle_at_50%_45%,rgba(66,232,244,0.08),transparent_62%)] p-5 text-center">
            <div class="pointer-events-none absolute inset-8 rounded-full bg-radar-cyan/5 blur-3xl"></div>
            {#each data.topKeywords as keyword, index}
              <a
                class="absolute z-10 select-none whitespace-nowrap leading-none tracking-[-0.055em] no-underline outline-none will-change-transform hover:z-30 hover:!opacity-100 hover:text-radar-cyan focus-visible:z-30 focus-visible:text-radar-cyan"
                style={keywordCloudStyle(keyword.weight, index)}
                onmouseenter={(event) => event.currentTarget.setAttribute('style', `${keywordCloudStyle(keyword.weight, index)}; ${keywordCloudHoverStyle(index)}`)}
                onmouseleave={(event) => event.currentTarget.setAttribute('style', keywordCloudStyle(keyword.weight, index))}
                onfocus={(event) => event.currentTarget.setAttribute('style', `${keywordCloudStyle(keyword.weight, index)}; ${keywordCloudHoverStyle(index)}`)}
                onblur={(event) => event.currentTarget.setAttribute('style', keywordCloudStyle(keyword.weight, index))}
                href={keywordHref(keyword.label)}
                title={`Ver ${keyword.label}: ${formatNumber(keyword.weight)} noticias`}
              >
                {keyword.label}
              </a>
            {/each}
          </div>
        </aside>
      </section>

      <section class="grid gap-5 lg:grid-cols-[0.95fr_1.05fr]">
        <article class="glass-panel rounded-[2rem] p-6 sm:p-7">
          <div class="mb-7 flex items-end justify-between gap-4">
            <div>
              <p class="text-sm uppercase tracking-[0.24em] text-radar-cyan/90">Ritmo</p>
              <h2 class="mt-2 text-2xl font-semibold text-white">Actividad diaria</h2>
            </div>
            <p class="text-right text-sm text-slate-400">Picos de cobertura por día</p>
          </div>

          {#if data.dailyActivity.length > 0}
            <div class="mb-4 grid gap-3 sm:grid-cols-3">
              <div class="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Días activos</p>
                <p class="mt-1 text-2xl font-semibold text-white">{activeDays}</p>
              </div>
              <div class="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Pico</p>
                <p class="mt-1 text-2xl font-semibold text-radar-cyan">{formatNumber(peakDay.newsCount)}</p>
              </div>
              <div class="rounded-2xl border border-white/10 bg-white/[0.035] p-4">
                <p class="text-xs uppercase tracking-[0.2em] text-slate-500">Día pico</p>
                <p class="mt-1 text-lg font-semibold capitalize text-white">{formatDateShort(peakDay.date)}</p>
              </div>
            </div>

            <div class="relative h-72 overflow-hidden rounded-3xl border border-white/10 bg-slate-950/45 p-4">
              <div class="absolute inset-x-4 top-6 flex justify-between text-[0.68rem] uppercase tracking-[0.18em] text-slate-500">
                <span>{formatDateShort(data.dailyActivity[0].date)}</span>
                <span>{formatDateShort(data.dailyActivity[data.dailyActivity.length - 1].date)}</span>
              </div>

              <svg class="absolute inset-0 h-full w-full p-4 pt-10" viewBox="0 0 100 100" preserveAspectRatio="none" aria-hidden="true">
                <defs>
                  <linearGradient id="activity-line" x1="0" x2="1" y1="0" y2="0">
                    <stop offset="0%" stop-color="#8b5cf6" />
                    <stop offset="55%" stop-color="#42e8f4" />
                    <stop offset="100%" stop-color="#fbbf24" />
                  </linearGradient>
                </defs>
                <polyline points={activityPath} fill="none" stroke="url(#activity-line)" stroke-width="2.8" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke" />
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
              <p class="text-lg font-semibold text-white">Sin actividad diaria para este mes.</p>
              <p class="mt-2 text-sm text-slate-400">Cuando existan filas en `radar_daily_activity`, Radar dibujará acá el ritmo de cobertura.</p>
            </div>
          {/if}
        </article>

        <article class="glass-panel rounded-[2rem] p-6 sm:p-7">
          <div class="mb-7 flex items-end justify-between gap-4">
            <div>
              <p class="text-sm uppercase tracking-[0.24em] text-radar-amber/90">Cobertura</p>
              <h2 class="mt-2 text-2xl font-semibold text-white">Ranking de fuentes</h2>
            </div>
            <p class="text-right text-sm text-slate-400">Aliases públicos</p>
          </div>

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
                      <p class="text-xs text-slate-400">{formatNumber(source.distinctKeywords)} temas distintos</p>
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
        </article>
      </section>
    {:else}
      <section class="glass-panel rounded-[2rem] p-8 text-center">
        <p class="text-lg text-slate-300">No hay datos mensuales disponibles todavía.</p>
      </section>
    {/if}
  </section>
</main>
