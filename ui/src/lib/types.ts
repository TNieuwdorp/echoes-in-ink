export interface Page {
  page_id: string;
  filename: string;
  letter_id: string | null;
  page_no: number | null;
  width: number;
  height: number;
  image?: string;
}
export interface UncertainSpan { line_no: number; word: string; alternatives: string[] }
export interface LetterPage {
  page_id: string;
  text_final: string;
  text_source: "auto" | "reviewed" | "gold";
  uncertain_spans: UncertainSpan[];
  reviewed_by: string | null;
}
export interface LetterMeta { letter_id: string; date: Date | null; place: string | null; title: string | null }
export interface Entity { letter_id: string; kind: "person" | "place"; name: string; canonical: string | null; detail: string | null }
export interface Event { letter_id: string | null; date: Date | null; date_text: string | null; description: string; category: string; source: string }
export interface Summary { letter_id: string; summary_nl: string | null; summary_en: string | null; mood: string | null; notable_quotes: string[] }

export interface Archive {
  mode: "live" | "static";
  pages: Page[];
  letters: LetterPage[];
  meta: LetterMeta[];
  entities: Entity[];
  events: Event[];
  summaries: Summary[];
}
