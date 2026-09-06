# Five extra features and experiments

Ordered by how much they add for the family versus how much they cost to build. Each ends
with the first experiment that tells whether the idea holds.

## 1. Teach the model his hand: LoRA fine-tune on reviewed pages

Once 40 to 60 pages are reviewed, fine-tune a low-rank adapter on Qwen3.8-27B (vision tower
frozen, adapter on the language side) with image-to-gold pairs, augmented with the zoom bands
and mild geometric jitter. A second arm trains Loghi's HTR on the same pages; that
architecture is built for exactly this and trains in an hour. Success is a two-point CER drop
on held-out letters with better name recall; failure is over-fitting to 1945 depot letters
and losing on the Indies pages, which is why the holdout must span both periods. The
by-product is a writer profile: his consistent letterform confusions (u vs n, ij vs y) become
explicit correction rules for the text pass.

First experiment: LoRA rank 16 on the language side, 3 epochs, evaluate on two held-out
letters against the zero-shot few-shot baseline.

## 2. Ask the letters: question answering with page citations

Local retrieval over `letters.parquet` (chunks per page, embeddings from a small model served
beside the VLM) with the text corrector as the answering model, under one rule: every claim
cites a page, and the UI shows the photo crop of the cited line. Questions the family will
ask: when did he arrive in Batavia, who was Han, did he ever mention grandma. Reuses the
reader component and the FastAPI server.

First experiment: 20 hand-written questions with answers taken from reviewed letters; count
answers that are right and cited, right but uncited, and wrong. Ship only if wrong is rare
and uncited is zero.

## 3. Reconstruct the correspondence: linking, gaps and dating undated pages

He answers letters from home ("je brief van 3 maart") and mentions delays. Extract those
references, build the graph of letters sent and received, and compute gaps: periods with no
surviving letter, letters that must have existed. For pages without a date or with a lost
first page, infer a date range from mentioned events, first appearances of people, postmarks
when an envelope was photographed, and paper and pen type. Present it as an interval with a
confidence, never a fake exact date. This is a natural Polars piece: interval joins between
letter dates, mentioned dates and the historical anchor table, and window functions for
"first mention of" per entity.

First experiment: extract dates-mentioned from the reviewed letters and check how many
resolve to a real letter in the set.

## 4. The journey: an animated map of where he was

Geocode places from the gazetteer, order them by letter date and draw the route with d3-geo:
training in the liberated south, the crossing to the Indies (ship name and voyage dates are
usually in the letters), postings on Java or Sumatra, the way home. Scrubbing the timeline
moves a marker; clicking a stop lists the letters written there; the historical anchors sit
on the same map. Relatives who never read a page still get the story from this view.

First experiment: count how many extracted places resolve against the gazetteer without
manual help; the leftovers become the checked-in CSV.

## 5. The book: a typeset facsimile edition

The end of "finishing his work" is something physical. Export every letter as facsimile beside
transcription, with the summary, the people index, the timeline and the map as chapters,
typeset with Typst from the same Parquet files the site reads. Uncertain words stay marked in
print, footnotes explain period words and abbreviations, and the English summaries make it
readable for relatives who do not speak Dutch. Deliverable: a print-on-demand PDF the family
site links to.

First experiment: one chapter with three letters, to see whether a two-column spread survives
his long pages and how the censored strips should look.

## Runners-up

- Dutch text-to-speech so older relatives can listen to the letters.
- A family annotation layer in the review UI: memories and photos attached to a letter,
  stored in Parquet next to the transcription.
- "Language over time": vocabulary, letter length and mood per month. Also a strong Polars
  tutorial, since it is nothing but group-bys, window functions and string expressions.
