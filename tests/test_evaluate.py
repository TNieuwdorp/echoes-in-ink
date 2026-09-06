import polars as pl

from echoes import evaluate as ev
from echoes import schema


def test_normalise_joins_hyphenated_lines():
    assert ev.normalise("We trof-\nfen het goed") == "We troffen het goed"
    assert ev.normalise("# comment\nhello   world") == "hello world"


def test_cer_wer():
    assert ev.cer("Lieve Vader", "Lieve Vader") == 0.0
    assert 0 < ev.cer("Lieve Vader", "Lieve Vadur") < 0.2
    assert ev.wer("Lieve Vader, Moeder en Han", "lieve vader moeder en han") == 0.0
    assert ev.wer("een twee drie", "een twee") > 0.3


def test_name_recall():
    ref = "Ik zag Harry en Frits in Middelburg. Morgen niet."
    assert ev.name_recall(ref, "Ik zag Harry en Frits in Middelburg") == 1.0
    assert ev.name_recall(ref, "Ik zag Harry en Fritz in Middelburg") == 2 / 3
    assert ev.name_recall("geen namen hier", "x") is None


def test_leaderboard_on_gold(fixtures, data_dir):
    from echoes import ingest

    pages = ingest.ingest(fixtures)
    gold = ev.load_gold(fixtures.parents[1] / "data" / "gold", pages)
    assert gold.height == 2
    pid = gold["page_id"][0]
    text = gold["gold_text"][0]
    lines = [ln for ln in text.splitlines() if ln and not ln.startswith("#")]
    tr = pl.DataFrame(
        [
            {
                "page_id": pid,
                "engine": "fake",
                "model": "m",
                "prompt_version": "v1",
                "variant": "page",
                "sample_no": 0,
                "line_no": i + 1,
                "text": ln,
                "confidence": "high",
                "created_at": None,
            }
            for i, ln in enumerate(lines)
        ],
        schema=schema.TRANSCRIPTIONS,
    )
    summary, _detail = ev.leaderboard(tr, schema.empty(schema.LETTERS), gold)
    assert summary.height == 1
    assert summary["cer"][0] == 0.0
    assert summary["wer"][0] == 0.0
