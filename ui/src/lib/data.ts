/**
 * Data access. Two modes, one interface:
 *  - live:   `echoes serve` is running; frames arrive as Arrow IPC from /api and edits are POSTed back.
 *  - static: the exported site; frames are Parquet files under /data read in-browser with parquet-wasm.
 */
import { tableFromIPC, type Table } from "apache-arrow";
import wasmInit, { readParquet } from "parquet-wasm";
import wasmUrl from "parquet-wasm/esm/parquet_wasm_bg.wasm?url";
import type { Archive, Entity, Event, LetterMeta, LetterPage, Page, Summary } from "./types";

let wasmReady: Promise<unknown> | null = null;

function rows<T>(table: Table): T[] {
  // Arrow -> plain objects; nested lists/structs become arrays/objects, dates stay Date.
  const out: T[] = [];
  for (const row of table) {
    const obj: Record<string, unknown> = {};
    for (const [k, v] of row) obj[k] = plain(v);
    out.push(obj as T);
  }
  return out;
}

function plain(v: unknown): unknown {
  if (v == null) return v;
  if (typeof v === "bigint") return Number(v);
  if (v instanceof Date) return v;
  if (typeof v === "object" && "toArray" in (v as object) && typeof (v as { toArray: unknown }).toArray === "function") {
    return Array.from((v as { toArray: () => unknown[] }).toArray()).map(plain);
  }
  if (typeof v === "object" && "toJSON" in (v as object)) {
    const j = (v as { toJSON: () => unknown }).toJSON();
    return typeof j === "object" && j !== null ? Object.fromEntries(Object.entries(j).map(([k, x]) => [k, plain(x)])) : j;
  }
  return v;
}

async function liveFrame<T>(name: string): Promise<T[] | null> {
  try {
    const res = await fetch(`/api/frames/${name}`);
    // a static host answers every path with index.html; only trust a real Arrow response
    if (!res.ok || !(res.headers.get("content-type") ?? "").includes("arrow")) return null;
    return rows<T>(tableFromIPC(new Uint8Array(await res.arrayBuffer())));
  } catch {
    return null;
  }
}

async function staticFrame<T>(name: string): Promise<T[]> {
  wasmReady ??= wasmInit(wasmUrl);
  await wasmReady;
  const res = await fetch(`${import.meta.env.BASE_URL}data/${name}.parquet`);
  if (!res.ok) return [];
  const wasmTable = readParquet(new Uint8Array(await res.arrayBuffer()));
  return rows<T>(tableFromIPC(wasmTable.intoIPCStream()));
}

export async function loadArchive(): Promise<Archive> {
  const livePages = await liveFrame<Page>("pages");
  const mode: Archive["mode"] = livePages ? "live" : "static";
  const get = <T,>(name: string) => (mode === "live" ? liveFrame<T>(name).then((r) => r ?? []) : staticFrame<T>(name));
  const [pages, letters, meta, entities, events, summaries] = await Promise.all([
    livePages ?? staticFrame<Page>("pages"),
    get<LetterPage>("letters"),
    get<LetterMeta>("letter_meta"),
    get<Entity>("entities"),
    get<Event>("events"),
    get<Summary>("summaries"),
  ]);
  return { mode, pages, letters, meta, entities, events, summaries };
}

export function imageUrl(archive: Archive, page: Page, kind: "original" | "processed" = "original"): string {
  if (archive.mode === "live") return `/api/image/${page.page_id}?kind=${kind}`;
  return `${import.meta.env.BASE_URL}data/${page.image ?? `images/${page.page_id}.jpg`}`;
}

export async function saveReview(page_id: string, text_final: string, reviewed_by: string): Promise<boolean> {
  const res = await fetch("/api/review", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ page_id, text_final, reviewed_by }),
  });
  return res.ok;
}

/** Letters grouped from pages, ordered by date (from meta or a YYYY-MM-DD letter_id). */
export function letterIndex(archive: Archive) {
  const byLetter = new Map<string, Page[]>();
  for (const p of archive.pages) {
    const key = p.letter_id ?? `(los) ${p.filename}`;
    byLetter.set(key, [...(byLetter.get(key) ?? []), p]);
  }
  const metaBy = new Map(archive.meta.map((m) => [m.letter_id, m]));
  return [...byLetter.entries()]
    .map(([letter_id, pages]) => {
      const m = metaBy.get(letter_id);
      const iso = /^\d{4}-\d{2}-\d{2}/.exec(letter_id)?.[0];
      const date = m?.date ?? (iso ? new Date(iso) : null);
      return { letter_id, date, title: m?.title ?? null, pages: pages.sort((a, b) => (a.page_no ?? 0) - (b.page_no ?? 0) || a.filename.localeCompare(b.filename)) };
    })
    .sort((a, b) => (a.date?.getTime() ?? Infinity) - (b.date?.getTime() ?? Infinity));
}
