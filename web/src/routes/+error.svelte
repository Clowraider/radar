<script lang="ts">
  import { page } from '$app/state';

  const isNotFound = $derived(page.status === 404);
</script>

<svelte:head>
  <title>{isNotFound ? 'Página no encontrada' : 'Error'} — Radar</title>
  <meta name="description" content="Radar no encontró la página solicitada." />
</svelte:head>

<main class="relative min-h-screen overflow-hidden px-4 py-8 text-slate-100 sm:px-6 lg:px-10">
  <div class="pointer-events-none absolute inset-0 overflow-hidden">
    <div class="absolute left-[12%] top-20 h-56 w-56 animate-float rounded-full bg-radar-cyan/20 blur-3xl"></div>
    <div class="absolute right-[14%] top-16 h-64 w-64 rounded-full bg-radar-violet/20 blur-3xl"></div>
    <div class="absolute bottom-20 left-1/2 h-72 w-72 rounded-full bg-radar-amber/10 blur-3xl"></div>
    <div class="absolute inset-0 bg-[linear-gradient(rgba(148,163,184,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(148,163,184,0.04)_1px,transparent_1px)] bg-[size:56px_56px] opacity-30"></div>
  </div>

  <section class="relative mx-auto flex min-h-[78vh] w-full max-w-4xl items-center justify-center">
    <article class="glass-panel w-full overflow-hidden rounded-[2rem] p-7 text-center sm:p-10 lg:p-12">
      <div class="mx-auto mb-7 flex h-20 w-20 items-center justify-center rounded-3xl border border-radar-cyan/35 bg-radar-cyan/10 shadow-glow">
        <span class="text-3xl font-semibold text-radar-cyan">{page.status}</span>
      </div>

      <p class="mb-4 inline-flex rounded-full border border-radar-violet/25 bg-radar-violet/10 px-4 py-2 text-xs font-semibold uppercase tracking-[0.28em] text-radar-violet">
        {isNotFound ? 'Señal no encontrada' : 'Radar detectó un problema'}
      </p>

      <h1 class="text-4xl font-semibold tracking-[-0.05em] text-white sm:text-6xl">
        {isNotFound ? 'Esta ruta no existe.' : 'No pudimos cargar esta vista.'}
      </h1>

      <p class="mx-auto mt-5 max-w-2xl text-base leading-7 text-slate-300 sm:text-lg">
        {isNotFound
          ? 'Puede que el enlace esté mal escrito, que el tema haya cambiado o que la página todavía no forme parte de Radar.'
          : page.error?.message ?? 'Intentá volver al pulso mensual o recargar la página.'}
      </p>

      <div class="mt-8 flex flex-col justify-center gap-3 sm:flex-row">
        <a
          class="rounded-2xl border border-radar-cyan/35 bg-radar-cyan/10 px-5 py-3 font-semibold text-radar-cyan transition hover:-translate-y-0.5 hover:bg-radar-cyan/20 hover:text-white"
          href="/"
        >
          Volver al pulso mensual
        </a>
        <button
          class="rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-3 font-semibold text-slate-200 transition hover:-translate-y-0.5 hover:border-radar-violet/40 hover:bg-radar-violet/10 hover:text-white"
          onclick={() => history.back()}
        >
          Volver atrás
        </button>
      </div>
    </article>
  </section>
</main>
