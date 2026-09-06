<script lang="ts">
  import { loadArchive, letterIndex } from "./lib/data";
  import type { Archive } from "./lib/types";
  import Timeline from "./lib/Timeline.svelte";
  import LetterReader from "./lib/LetterReader.svelte";
  import Search from "./lib/Search.svelte";
  import Entities from "./lib/Entities.svelte";

  type View = "tijdlijn" | "brieven" | "zoeken" | "mensen";
  let view = $state<View>("tijdlijn");
  let archive = $state<Archive | null>(null);
  let selected = $state<string | null>(null);
  let error = $state("");

  async function refresh() {
    try { archive = await loadArchive(); } catch (e) { error = String(e); }
  }
  refresh();

  function open(letter_id: string) { selected = letter_id; view = "brieven"; }
  const letters = $derived(archive ? letterIndex(archive) : []);
  $effect(() => { if (!selected && letters.length) selected = letters[0].letter_id; });
</script>

<header>
  <div>
    <h1>Echoes in Ink</h1>
    <p class="muted">Brieven van Wim Nieuwdorp, 1945–1950 {#if archive}<span class="mode">{archive.mode === "live" ? "· werkmodus" : "· archief"}</span>{/if}</p>
  </div>
  <nav>
    {#each ["tijdlijn", "brieven", "zoeken", "mensen"] as const as v}
      <button class:primary={view === v} onclick={() => (view = v)}>{v}</button>
    {/each}
  </nav>
</header>

<main>
  {#if error}<p class="card">Kon het archief niet laden: {error}</p>
  {:else if !archive}<p class="muted">laden…</p>
  {:else if view === "tijdlijn"}
    <Timeline {archive} onOpen={open} />
    <section class="card list">
      <h2>Alle brieven</h2>
      {#if letters.length === 0}<p class="muted">Nog geen pagina's. Draai <span class="mono">just ingest &lt;map&gt;</span>.</p>{/if}
      <ul>
        {#each letters as l}
          <li><button class="link" onclick={() => open(l.letter_id)}>{l.date ? l.date.toLocaleDateString("nl-NL", { day: "numeric", month: "long", year: "numeric" }) : l.letter_id}</button>
            <span class="muted">{l.pages.length} pagina's</span></li>
        {/each}
      </ul>
    </section>
  {:else if view === "brieven"}
    <div class="picker">
      <select bind:value={selected}>
        {#each letters as l}<option value={l.letter_id}>{l.letter_id}{l.title ? ` · ${l.title}` : ""}</option>{/each}
      </select>
    </div>
    {#if selected}<LetterReader {archive} letterId={selected} onSaved={refresh} />{/if}
  {:else if view === "zoeken"}
    <Search {archive} onOpen={open} />
  {:else}
    <Entities {archive} onOpen={open} />
  {/if}
</main>

<style>
  header { display: flex; justify-content: space-between; align-items: center; gap: 1rem; padding: 1rem 1.5rem 0; flex-wrap: wrap; }
  header p { margin: 0; }
  .mode { font-size: 0.85rem; }
  nav { display: flex; gap: 0.4rem; }
  nav button { text-transform: capitalize; }
  main { padding: 1rem 1.5rem 3rem; display: grid; gap: 1rem; max-width: 1400px; margin: 0 auto; }
  .list ul { list-style: none; padding: 0; margin: 0; columns: 2; }
  .list li { padding: 0.2rem 0; break-inside: avoid; }
  .link { background: none; border: none; color: var(--series-1); padding: 0; text-align: left; }
  .picker select { min-width: 20rem; }
</style>
