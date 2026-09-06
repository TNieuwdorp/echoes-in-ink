import polars as pl

from echoes import ingest, schema


def test_parse_filename():
    assert ingest.parse_filename("1945-03-15_p1") == ("1945-03-15", 1)
    assert ingest.parse_filename("L042_p12_extra") == ("L042", 12)
    assert ingest.parse_filename("IMG_20260906_123456") == (None, None)


def test_ingest_fixtures(fixtures, data_dir):
    df = ingest.ingest(fixtures)
    assert df.height == 3
    assert df["page_id"].n_unique() == 3
    assert set(df["letter_id"]) == {"1945-03-15"}
    assert df.filter(pl.col("filename") == "1945-03-15_p2.jpg")["page_no"][0] == 2
    assert df["captured_at"].null_count() == 0
    # idempotent: re-ingesting keeps the same rows
    again = ingest.ingest(fixtures)
    assert again.height == 3
    assert (data_dir / "pages.parquet").exists()
    assert set(again.columns) == set(schema.PAGES)


def test_page_id_is_content_hash(fixtures, tmp_path):
    src = fixtures / "1945-03-15_p1.jpg"
    copy = tmp_path / "renamed.jpg"
    copy.write_bytes(src.read_bytes())
    assert ingest.page_id_for(src) == ingest.page_id_for(copy)
