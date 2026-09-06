<script lang="ts">
  import * as d3 from "d3";
  import type { Archive } from "./types";
  import { letterIndex } from "./data";
  import { CONTEXT_EVENTS } from "./context";

  let { archive, onOpen }: { archive: Archive; onOpen: (letter_id: string) => void } = $props();

  d3.timeFormatDefaultLocale({
    dateTime: "%A %e %B %Y %X", date: "%d-%m-%Y", time: "%H:%M:%S", periods: ["AM", "PM"],
    days: ["zondag", "maandag", "dinsdag", "woensdag", "donderdag", "vrijdag", "zaterdag"],
    shortDays: ["zo", "ma", "di", "wo", "do", "vr", "za"],
    months: ["januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober", "november", "december"],
    shortMonths: ["jan", "feb", "mrt", "apr", "mei", "jun", "jul", "aug", "sep", "okt", "nov", "dec"],
  });

  let svgEl: SVGSVGElement;
  let width = $state(900);
  const height = 220;
  const margin = { top: 16, right: 24, bottom: 40, left: 24 };
  let tooltip = $state<{ x: number; y: number; text: string } | null>(null);

  const letters = $derived(letterIndex(archive).filter((l) => l.date));
  const extracted = $derived(archive.events.filter((e) => e.source === "extracted" && e.date));
  const anchors = CONTEXT_EVENTS.map((e) => ({ ...e, d: new Date(e.date) }));

  function draw() {
    if (!svgEl) return;
    const svg = d3.select(svgEl);
    svg.selectAll("*").remove();
    const all = [...letters.map((l) => l.date!), ...extracted.map((e) => e.date!), ...anchors.map((a) => a.d)];
    const [d0, d1] = all.length ? (d3.extent(all) as [Date, Date]) : [new Date("1945-01-01"), new Date("1950-01-01")];
    const x0 = d3.scaleTime().domain([d3.timeMonth.offset(d0, -2), d3.timeMonth.offset(d1, 2)]).range([margin.left, width - margin.right]);
    let x = x0.copy();
    const yLetters = height - margin.bottom - 70;
    const yEvents = height - margin.bottom - 40;
    const yAnchors = height - margin.bottom - 10;

    const g = svg.append("g");
    const axis = svg.append("g").attr("transform", `translate(0,${height - margin.bottom + 14})`).attr("class", "axis");
    const track = (y: number, label: string) => {
      g.append("line").attr("x1", margin.left).attr("x2", width - margin.right).attr("y1", y).attr("y2", y).attr("class", "track");
      svg.append("text").attr("x", margin.left).attr("y", y - 9).attr("class", "track-label").text(label);
    };
    track(yLetters, "Brieven");
    track(yEvents, "Gebeurtenissen uit de brieven");
    track(yAnchors, "Historische context");

    const show = (ev: MouseEvent, text: string) => (tooltip = { x: ev.offsetX, y: ev.offsetY, text });
    const hide = () => (tooltip = null);

    const anchorMarks = g.selectAll(".anchor").data(anchors).join("g").attr("class", "anchor");
    anchorMarks.append("rect").attr("width", 3).attr("height", 14).attr("rx", 1.5).attr("y", yAnchors - 7)
      .attr("fill", "var(--anchor)")
      .on("mousemove", (ev, d) => show(ev, `${d3.timeFormat("%-d %b %Y")(d.d)} · ${d.label}`)).on("mouseleave", hide);

    const evMarks = g.selectAll(".event").data(extracted).join("circle").attr("class", "event")
      .attr("r", 4.5).attr("cy", yEvents).attr("fill", "var(--series-2)").attr("stroke", "var(--surface-1)").attr("stroke-width", 2)
      .on("mousemove", (ev, d) => show(ev, `${d.date_text ?? ""} · ${d.description}`)).on("mouseleave", hide)
      .on("click", (_, d) => d.letter_id && onOpen(d.letter_id));

    const letterMarks = g.selectAll(".letter").data(letters).join("g").attr("class", "letter").style("cursor", "pointer")
      .on("mousemove", (ev, d) => show(ev, `${d3.timeFormat("%-d %B %Y")(d.date!)} · ${d.pages.length} pagina's`)).on("mouseleave", hide)
      .on("click", (_, d) => onOpen(d.letter_id));
    letterMarks.append("rect").attr("width", 6).attr("height", 22).attr("rx", 3).attr("y", yLetters - 11).attr("fill", "var(--series-1)");
    // invisible, larger hit target
    letterMarks.append("rect").attr("width", 18).attr("height", 34).attr("y", yLetters - 17).attr("fill", "transparent");

    function place() {
      anchorMarks.attr("transform", (d) => `translate(${x(d.d) - 1.5},0)`);
      evMarks.attr("cx", (d) => x(d.date!));
      letterMarks.attr("transform", (d) => `translate(${x(d.date!) - 3},0)`);
      axis.call(d3.axisBottom(x).ticks(width / 110).tickSizeOuter(0));
    }
    place();

    svg.call(
      d3.zoom<SVGSVGElement, unknown>()
        .scaleExtent([1, 40])
        .translateExtent([[margin.left, 0], [width - margin.right, height]])
        .extent([[margin.left, 0], [width - margin.right, height]])
        .on("zoom", (ev) => { x = ev.transform.rescaleX(x0); place(); }),
    );
  }

  $effect(() => { draw(); });
</script>

<div class="card timeline" bind:clientWidth={width}>
  <div class="head">
    <h2>Tijdlijn</h2>
    <span class="muted">Scroll om te zoomen, sleep om te schuiven, klik op een brief om te lezen.</span>
  </div>
  <svg bind:this={svgEl} {width} {height} role="img" aria-label="Tijdlijn van brieven en gebeurtenissen"></svg>
  {#if tooltip}
    <div class="tooltip" style="left:{tooltip.x + 12}px; top:{tooltip.y - 8}px">{tooltip.text}</div>
  {/if}
  <div class="legend">
    <span><i style="background:var(--series-1)"></i>Brief</span>
    <span><i style="background:var(--series-2); border-radius:50%"></i>Gebeurtenis uit brief</span>
    <span><i style="background:var(--anchor)"></i>Historische context</span>
  </div>
</div>

<style>
  .timeline { position: relative; }
  .head { display: flex; justify-content: space-between; align-items: baseline; gap: 1rem; flex-wrap: wrap; }
  svg { display: block; width: 100%; overflow: visible; }
  svg :global(.track) { stroke: var(--line); stroke-width: 1; }
  svg :global(.track-label) { fill: var(--text-muted); font-size: 11px; text-transform: uppercase; letter-spacing: 0.08em; }
  svg :global(.axis text) { fill: var(--text-secondary); font-size: 12px; }
  svg :global(.axis path), svg :global(.axis line) { stroke: var(--line); }
  .tooltip { position: absolute; pointer-events: none; background: var(--surface-1); border: 1px solid var(--line);
    border-radius: 6px; padding: 0.3rem 0.5rem; font-size: 0.85rem; max-width: 320px; box-shadow: 0 2px 8px rgba(0,0,0,0.12); }
  .legend { display: flex; gap: 1.2rem; font-size: 0.85rem; color: var(--text-secondary); margin-top: 0.4rem; }
  .legend i { display: inline-block; width: 10px; height: 10px; border-radius: 3px; margin-right: 0.35rem; vertical-align: -1px; }
</style>
