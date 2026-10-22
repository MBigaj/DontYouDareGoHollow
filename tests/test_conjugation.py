import pytest

from hollow.domain.conjugation import Ending, NotAVerb, TeForm, Verb, classify, te_form

# Every verb in the deck's first 172 cards, as learned so far, plus する.
DECK = [
    ("なる", "なる", Ending.TSU, "なって"),
    ("やる", "やる", Ending.TSU, "やって"),
    ("分かる", "わかる", Ending.TSU, "わかって"),
    ("来る", "くる", Ending.IRREGULAR, "きて"),
    ("行く", "いく", Ending.ITE, "いって"),
    ("帰る", "かえる", Ending.TSU, "かえって"),
    ("上げる", "あげる", Ending.RU_VERB, "あげて"),
    ("上る", "のぼる", Ending.TSU, "のぼって"),
    ("入れる", "いれる", Ending.RU_VERB, "いれて"),
    ("入る", "はいる", Ending.TSU, "はいって"),
    ("出る", "でる", Ending.RU_VERB, "でて"),
    ("出す", "だす", Ending.SHITE, "だして"),
    ("休む", "やすむ", Ending.NDE, "やすんで"),
    ("空く", "すく", Ending.ITE, "すいて"),
    ("晴れる", "はれる", Ending.RU_VERB, "はれて"),
    ("開く", "ひらく", Ending.ITE, "ひらいて"),
    ("閉じる", "とじる", Ending.RU_VERB, "とじて"),
    ("閉まる", "しまる", Ending.TSU, "しまって"),
    ("聞く", "きく", Ending.ITE, "きいて"),
    ("くれる", "くれる", Ending.RU_VERB, "くれて"),
    ("飲む", "のむ", Ending.NDE, "のんで"),
    ("買う", "かう", Ending.TSU, "かって"),
    ("見る", "みる", Ending.RU_VERB, "みて"),
    ("見つかる", "みつかる", Ending.TSU, "みつかって"),
    ("言う", "いう", Ending.TSU, "いって"),
    ("話す", "はなす", Ending.SHITE, "はなして"),
    ("覚える", "おぼえる", Ending.RU_VERB, "おぼえて"),
    ("止める", "やめる", Ending.RU_VERB, "やめて"),
    ("走る", "はしる", Ending.TSU, "はしって"),
    ("泳ぐ", "およぐ", Ending.ITE, "およいで"),
    ("遊ぶ", "あそぶ", Ending.NDE, "あそんで"),
    ("死ぬ", "しぬ", Ending.NDE, "しんで"),
    ("待つ", "まつ", Ending.TSU, "まって"),
    ("する", "する", Ending.IRREGULAR, "して"),
    ("勉強する", "べんきょうする", Ending.IRREGULAR, "べんきょうして"),
]


@pytest.mark.parametrize(("written", "kana", "ending", "answer"), DECK)
def test_te_form_of_every_deck_verb(written: str, kana: str, ending: Ending, answer: str) -> None:
    assert classify(written, kana) is ending
    assert te_form(written, kana).kana == answer


def test_homographs_follow_the_written_form() -> None:
    assert te_form("切る", "きる").kana == "きって"
    assert te_form("着る", "きる").kana == "きて"
    assert te_form("要る", "いる").kana == "いって"
    assert te_form("居る", "いる").kana == "いて"


def test_written_answers_keep_the_kanji() -> None:
    assert te_form("食べる", "たべる") == TeForm("たべて", "食べて")
    assert te_form("行く", "いく") == TeForm("いって", "行って")
    assert te_form("来る", "くる") == TeForm("きて", "来て")
    assert te_form("勉強する", "べんきょうする").written == "勉強して"


@pytest.mark.parametrize("answer", ["たべて", "食べて", " たべて ", "タベテ", "ﾀﾍﾞﾃ"])
def test_answers_in_kana_kanji_or_katakana_count(answer: str) -> None:
    assert Verb("食べる", "たべる", "eat").te_form.accepts(answer)


@pytest.mark.parametrize("answer", ["たべって", "たべる", "", "食べた"])
def test_wrong_answers_do_not(answer: str) -> None:
    assert not Verb("食べる", "たべる").te_form.accepts(answer)


def test_nouns_are_not_verbs() -> None:
    with pytest.raises(NotAVerb):
        classify("本", "ほん")
    with pytest.raises(NotAVerb):
        classify("それ", "")


def test_verb_exposes_its_group() -> None:
    assert Verb("帰る", "かえる").ending is Ending.TSU
