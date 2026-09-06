<script lang="ts">
  import type { Archive, Page } from "./types";
  import { imageUrl, letterIndex, saveReview } from "./data";

  let { archive, letterId, onSaved }: { archive: Archive; letterId: string; onSaved: () => void } = $props();

  const letter = $derived(letterIndex(archive).find((l) => l.letter_id === letterId));
  let pageIdx = $state(0);
  const page = $derived<Page | undefined>(letter?.pages[pageIdx]);
  const text = $derived(archive.letters.find((l) => l.page_id === page?.page_id));
  const summary = $derived(archive.summaries.find((s) => s.letter_id === letterId));

  let editing = $state(false);
  let draft = $state("");
  let reviewer = $state(localStorage.getItem("echoes.reviewer") ?? "");
  let zoom = $state(1);
  let showProcessed = $state(false);
  let status = $state("");

  $effect(() => { pageIdx = 0; });
  $effect(() => { draft = text?.text_final ?? ""; editing = false; });

  function uncertainWords(lineNo: number): Set<string> {
    return new Set((text?.uncertain_spans ?? []).filter((u) => u.line_no === lineNo).map((u) => u.word));
  }
  function alternatives(lineNo: number, word: string): string[] {
    return (text?.uncertain_spans ?? []).find((u) => u.line_no === lineNo && u.word === word)?.alternatives ?? [];
  }

  async function save() {
    if (!page) return;
    localStorage.setItem("echoes.reviewer", reviewer);
    status = "opslaan…";
    const ok = await saveReview(page.page_id, draft, reviewer || "family");
    status = ok ? "opgeslagen" : "opslaan mislukt (draait `echoes serve`?)";
    if (ok) { editing = false; onSaved(); }
  }
</script>

{#if letter && page}
  <div class="reader">
    <div class="card image">
      <div class="bar">
        <span class="muted">{page.filename}</span>
        <span>
          <button onclick={() => (zoom = Math.max(1, zoom - 0.25))}>−</button>
          <span class="mono">{Math.round(zoom * 100)}%</span>
          <button onclick={() => (zoom = Math.min(4, zoom + 0.25))}>+</button>
          <label><input type="checkbox" bind:checked={showProcessed} /> bewerkt beeld</label>
        </span>
      </div>
      <div class="scroll">
        <img src={imageUrl(archive, page, showProcessed ? "processed" : "original")} alt="Pagina {page.page_no}" style="width:{zoom * 100}%" />
      </div>
    </div>

    <div class="card text">
      <div class="bar">
        <h2>{letter.title ?? letter.letter_id} <span class="muted">· pagina {pageIdx + 1} van {letter.pages.length}</span></h2>
        <span>
          <button disabled={pageIdx === 0} onclick={() => pageIdx--}>‹</button>
          <button disabled={pageIdx >= letter.pages.length - 1} onclick={() => pageIdx++}>›</button>
        </span>
      </div>
      {#if text}
        <p class="source">
          {#if text.text_source === "reviewed"}<span class="reviewed">✓ nagekeken door {text.reviewed_by}</span>
          {:else if text.text_source === "gold"}<span class="reviewed">✓ goud</span>
          {:else}<span class="muted">automatische transcriptie · {text.uncertain_spans?.length ?? 0} twijfelwoorden</span>{/if}
        </p>
        {#if editing}
          <textarea bind:value={draft} rows={Math.max(12, draft.split("\n").length + 1)}></textarea>
          <div class="bar">
            <input placeholder="jouw naam" bind:value={reviewer} />
            <span>
              <button onclick={() => (editing = false)}>annuleren</button>
              <button class="primary" onclick={save}>opslaan als nagekeken</button>
            </span>
          </div>
        {:else}
          <ol class="lines">
            {#each text.text_final.split("\n") as line, i}
              {@const unc = uncertainWords(i + 1)}
              <li>
                {#each line.split(" ") as word, j}
                  {#if unc.has(word)}
                    <mark title={"alternatieven: " + (alternatives(i + 1, word).join(", ") || "geen")}>{word}</mark>
                  {:else}{word}{/if}{j < line.split(" ").length - 1 ? " " : ""}
                {/each}
              </li>
            {/each}
          </ol>
          {#if archive.mode === "live"}
            <button onclick={() => (editing = true)}>corrigeren</button>
          {/if}
        {/if}
        <p class="muted small">{status}</p>
      {:else}
        <p class="muted">Nog geen transcriptie voor deze pagina. Draai <span class="mono">just transcribe</span>.</p>
      {/if}
      {#if summary?.summary_nl && pageIdx === 0}
        <details><summary>Samenvatting</summary><p>{summary.summary_nl}</p><p class="muted">{summary.summary_en}</p></details>
      {/if}
    </div>
  </div>
{:else}
  <p class="muted">Kies een brief.</p>
{/if}

<style>
  .reader { display: grid; grid-template-columns: minmax(320px, 1fr) minmax(360px, 1fr); gap: 1rem; align-items: start; }
  @media (max-width: 900px) { .reader { grid-template-columns: 1fr; } }
  .bar { display: flex; justify-content: space-between; align-items: center; gap: 0.5rem; flex-wrap: wrap; margin-bottom: 0.5rem; }
  .scroll { overflow: auto; max-height: 80vh; border-radius: 6px; background: #000; }
  img { display: block; }
  .lines { padding-left: 2.2rem; margin: 0; font-size: 1.05rem; }
  .lines li { padding: 0.1rem 0; }
  .lines li::marker { color: var(--text-muted); font-size: 0.8rem; }
  mark { background: var(--uncertain-bg); color: var(--uncertain-ink); border-radius: 3px; padding: 0 2px; cursor: help; }
  textarea { width: 100%; font-family: inherit; font-size: 1rem; line-height: 1.5; }
  .reviewed { color: var(--reviewed); }
  .small { font-size: 0.85rem; }
  .source { margin: 0 0 0.5rem; }
</style>
