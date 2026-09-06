from echoes import reconcile as rc


def test_align_lines_monotone():
    ref = ["Lieve Vader, Moeder en Han,", "Hier is dan mijn eerste teken van leven.", "schrijven."]
    hyp = [
        "Lieve Vader, Moeder en Han,",
        "EXTRA LINE",
        "Hier is dan mijn eerste teken van leven",
        "schrijven.",
    ]
    assert rc.align_lines(ref, hyp) == [0, 2, 3]


def test_vote_prefers_majority_and_records_alternatives():
    ref = ["Ik", "hoop", "dat", "jullie", "het", "goed", "maakt"]
    hyps = [
        ["Ik", "hoop", "dat", "jullie", "het", "goed", "maakt"],
        ["Ik", "hoop", "dat", "jullie", "het", "geed", "maakt"],
        ["Ik", "hoop", "dat", "jullie", "het", "goed", "maakt"],
    ]
    v = rc.vote_tokens(ref, hyps)
    assert v.text == "Ik hoop dat jullie het goed maakt"
    assert v.alternatives == {5: ["geed"]}
    assert "{goed|geed}" in v.marked()


def test_vote_flips_when_reference_is_outvoted():
    ref = ["Wim", "v.", "Ollosel"]
    hyps = [["Wim", "v.", "Alloosel"], ["Wim", "v.", "Alloosel"]]
    v = rc.vote_tokens(ref, hyps)
    assert v.tokens[2] == "Alloosel"
    assert v.alternatives[2] == ["Ollosel"]


def test_vote_page_end_to_end():
    readings = [
        ["15 Maart 1945.", "Lieve Vader, Moeder en Han,"],
        ["15 Maart 1945.", "Lieve Vader, Moeder en Hans,"],
        ["15 Maart 1945", "Lieve Vader, Moeder en Han,"],
    ]
    voted = rc.vote_page(readings)
    assert [v.n for v in voted] == [1, 2]
    assert voted[1].text == "Lieve Vader, Moeder en Han,"
    assert voted[1].uncertain()[0]["alternatives"] == ["Hans,"]
