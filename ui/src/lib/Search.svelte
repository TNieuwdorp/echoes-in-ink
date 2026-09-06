<script lang="ts">
  import type { Archive } from "./types";
  import { letterIndex } from "./data";

  let { archive, onOpen }: { archive: Archive; onOpen: (letter_id: string) => void } = $props();
  let q = $state("");

  const index = $derived(() => {
    const byPage = new Map(archive.pages.map((p) => [p.page_id, p]));
    return archive.letters.map((l) => ({ ...l, page: byPage.get(l.page_id) }));
  });

  const hits = $derived(() => {
    const needle = q.trim().toLocaleLowerCase("nl");
    if (needle.length < 2) return [];
    const out: { letter_id: string; page_no: number | null; snippet: string }[] = [];
    for (const l of index()) {
      const lines = l.text_final.split("\n");
      lines.forEach((line) => {
        const at = line.toLocaleLowerCase("nl").indexOf(needle);
        if (at >= 0) out.push({ letter_id: l.page?.letter_id ?? "?", page_no: l.page?.page_no ?? null, snippet: line });
      });
    }
    return out.slice(0, 200);
  });

  function highlight(s: string): string {
    const needle = q.trim();
    if (!needle) return s;
    const i = s.toLocaleLowerCase("nl").indexOf(needle.toLocaleLowerCase("nl"));
    if (i < 0) return s;
    return `${s.slice(0, i)}<mark>${s.slice(i, i + needle.length)}</mark>${s.slice(i + needle.length)}`;
  }
</script>

<div class="card">
  <h2>Zoeken</h2>
  <input type="search" placeholder="bijv. sigaretten, Middelburg, Han" bind:value={q} style="width:100%" />
  <p class="muted">{letterIndex(archive).length} brieven · {archive.letters.length} getranscribeerde pagina's</p>
  <ul>
    {#each hits() as h}
      <li>
        <button class="link" onclick={() => onOpen(h.letter_id)}>{h.letter_id}{h.page_no ? ` p${h.page_no}` : ""}</button>
        <span>{@html highlight(h.snippet)}</span>
      </li>
    {/each}
  </ul>
</div>

<style>
  ul { list-style: none; padding: 0; margin: 0.5rem 0 0; }
  li { padding: 0.35rem 0; border-top: 1px solid var(--line); display: grid; grid-template-columns: 9rem 1fr; gap: 0.5rem; }
  .link { background: none; border: none; color: var(--series-1); text-align: left; padding: 0; }
  :global(mark) { background: var(--uncertain-bg); color: var(--uncertain-ink); }
</style>
