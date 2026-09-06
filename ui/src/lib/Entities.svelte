<script lang="ts">
  import type { Archive } from "./types";
  import * as d3 from "d3";

  let { archive, onOpen }: { archive: Archive; onOpen: (letter_id: string) => void } = $props();
  let kind = $state<"person" | "place">("person");

  const groups = $derived(() => {
    const m = new Map<string, Set<string>>();
    for (const e of archive.entities) {
      if (e.kind !== kind) continue;
      const key = e.canonical ?? e.name;
      m.set(key, (m.get(key) ?? new Set()).add(e.letter_id));
    }
    return [...m.entries()].map(([name, letters]) => ({ name, letters: [...letters].sort() })).sort((a, b) => b.letters.length - a.letters.length);
  });
  const max = $derived(() => d3.max(groups(), (g) => g.letters.length) ?? 1);
</script>

<div class="card">
  <div class="bar">
    <h2>{kind === "person" ? "Mensen" : "Plaatsen"}</h2>
    <span>
      <button class:primary={kind === "person"} onclick={() => (kind = "person")}>mensen</button>
      <button class:primary={kind === "place"} onclick={() => (kind = "place")}>plaatsen</button>
    </span>
  </div>
  {#if groups().length === 0}
    <p class="muted">Nog geen namen: draai <span class="mono">echoes enrich</span> na het transcriberen.</p>
  {/if}
  <ul>
    {#each groups() as g}
      <li>
        <span class="name">{g.name}</span>
        <span class="barwrap"><span class="fill" style="width:{(g.letters.length / max()) * 100}%"></span></span>
        <span class="muted mono">{g.letters.length}</span>
        <span class="letters">{#each g.letters as l}<button class="link" onclick={() => onOpen(l)}>{l}</button>{/each}</span>
      </li>
    {/each}
  </ul>
</div>

<style>
  .bar { display: flex; justify-content: space-between; align-items: center; }
  ul { list-style: none; padding: 0; margin: 0.5rem 0 0; }
  li { display: grid; grid-template-columns: 12rem 1fr 2.5rem 1fr; gap: 0.6rem; align-items: center; padding: 0.3rem 0; border-top: 1px solid var(--line); }
  .barwrap { display: block; height: 8px; background: var(--surface-0); border-radius: 4px; overflow: hidden; }
  .fill { display: block; height: 100%; background: var(--series-3); border-radius: 4px; }
  .letters { display: flex; flex-wrap: wrap; gap: 0.3rem; }
  .link { background: none; border: 1px solid var(--line); color: var(--series-1); font-size: 0.8rem; padding: 0 0.35rem; }
</style>
