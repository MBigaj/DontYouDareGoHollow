"""Conjugation for the verbs in your deck: the て-form, and the plain forms built on it.

Groups follow how the て-form changes, which is how drills are split:
- ichidan (る-verbs): drop る, add て. 食べる → 食べて
- godan: the last kana decides.
  う・つ・る → って, む・ぶ・ぬ → んで, く → いて, ぐ → いで, す → して
- 行く is the one く-verb that takes って. する → して, 来る → 来て (きて).

A verb ending in -iru or -eru is ichidan unless it is a known godan exception (帰る, 入る, 走る…).
Homographs decide by the written form: 切る (cut) is godan, 着る (wear) is ichidan.

The plain forms (Undead Village) are built from that:
- 〜ている: the て-form + いる. 食べている, 読んでいる
- 〜た: the て-form with て → た, で → だ, so the same sound changes. 読んだ, 行った
- 〜ない: ichidan drop る; godan move the last kana to the あ-row (う → わ); する → しない,
  来る → 来ない (こない), and ある → ない.
- 〜なかった: 〜ない with い → かった.
"""

import unicodedata
from dataclasses import dataclass
from enum import StrEnum


class Ending(StrEnum):
    """The て-form sound change, one drill group each."""

    RU_VERB = "ru_verb"  # 食べる → 食べて
    TSU = "tsu"  # う・つ・る → って
    NDE = "nde"  # む・ぶ・ぬ → んで
    ITE = "ite"  # く・ぐ → いて・いで, and 行く → 行って
    SHITE = "shite"  # す → して
    IRREGULAR = "irregular"  # する, 来る


I_ROW = set("いきぎしじちぢにひびぴみりゐ")
E_ROW = set("えけげせぜてでねへべぺめれゑ")

GODAN_RU = {
    # written forms: godan verbs that look like ichidan
    "帰る",
    "入る",
    "走る",
    "知る",
    "切る",
    "要る",
    "減る",
    "限る",
    "喋る",
    "滑る",
    "握る",
    "参る",
    "蹴る",
    "練る",
    "焦る",
    "茂る",
    "湿る",
    "散る",
    "混じる",
    "交じる",
    "遮る",
    "覆る",
    "翻る",
    "嘲る",
    "捻る",
    "罵る",
    "陥る",
    "甦る",
    "蘇る",
    "照る",
    "侮る",
}
GODAN_RU_KANA = {
    "しゃべる",
    "すべる",
    "にぎる",
    "あせる",
    "ける",
    "ちる",
    "てる",
    "はいる",
    "はしる",
}
"""Kana-only spellings that are always godan (no ichidan homograph in common use)."""

GODAN_TE = {
    "う": "って",
    "つ": "って",
    "る": "って",
    "む": "んで",
    "ぶ": "んで",
    "ぬ": "んで",
    "く": "いて",
    "ぐ": "いで",
    "す": "して",
}
GODAN_ENDING = {
    "う": Ending.TSU,
    "つ": Ending.TSU,
    "る": Ending.TSU,
    "む": Ending.NDE,
    "ぶ": Ending.NDE,
    "ぬ": Ending.NDE,
    "く": Ending.ITE,
    "ぐ": Ending.ITE,
    "す": Ending.SHITE,
}


class Form(StrEnum):
    """What a drill asks you to turn the dictionary form into."""

    TE = "te"
    TEIRU = "teiru"
    TA = "ta"
    NAI = "nai"
    NAKATTA = "nakatta"


FORM_NAMES = {
    Form.TE: "て-form",
    Form.TEIRU: "〜ている",
    Form.TA: "〜た (plain past)",
    Form.NAI: "〜ない (plain negative)",
    Form.NAKATTA: "〜なかった (plain past negative)",
}

A_ROW = {"う": "わ", "く": "か", "ぐ": "が", "す": "さ", "つ": "た", "ぬ": "な", "ぶ": "ば",
         "む": "ま", "る": "ら"}  # fmt: skip
"""Godan 〜ない: the last kana moves to the あ-row (う becomes わ, not あ)."""


class NotAVerb(ValueError):
    pass


@dataclass(frozen=True)
class Verb:
    written: str
    """As written in your deck, e.g. 食べる (or the kana when there is no kanji)."""
    kana: str
    """Dictionary form in hiragana, e.g. たべる."""
    meaning: str = ""

    @property
    def ending(self) -> Ending:
        return classify(self.written, self.kana)

    @property
    def te_form(self) -> "TeForm":
        return te_form(self.written, self.kana)

    def form(self, form: Form) -> "TeForm":
        return conjugate(self.written, self.kana, form)


@dataclass(frozen=True)
class TeForm:
    """A conjugated form, in kana and as written (the name is from when て was the only one)."""

    kana: str
    written: str

    def accepts(self, answer: str) -> bool:
        """Accepts the kana or the written form, ignoring spaces and width or katakana slips."""
        given = normalize(answer)
        return given in {normalize(self.kana), normalize(self.written)}


def normalize(text: str) -> str:
    text = unicodedata.normalize("NFKC", text).strip().replace(" ", "").replace("　", "")
    # katakana to hiragana, so a stray IME mode is not a wrong answer
    return "".join(chr(ord(c) - 0x60) if "ァ" <= c <= "ヶ" else c for c in text)


def classify(written: str, kana: str) -> Ending:
    if not kana or not kana.endswith(tuple(GODAN_ENDING)):
        raise NotAVerb(f"{written} ({kana}) does not end like a verb")
    if kana == "する" or kana.endswith("する") or kana in {"くる"} or written in {"来る"}:
        return Ending.IRREGULAR
    if kana.endswith("る") and len(kana) >= 2 and kana[-2] in I_ROW | E_ROW:
        if written in GODAN_RU or (written == kana and kana in GODAN_RU_KANA):
            return Ending.TSU
        return Ending.RU_VERB
    return GODAN_ENDING[kana[-1]]


def te_form(written: str, kana: str) -> TeForm:
    ending = classify(written, kana)
    if ending is Ending.IRREGULAR:
        if kana.endswith("する"):
            return TeForm(kana[:-2] + "して", written[:-2] + "して")
        return TeForm("きて", "来て" if written.startswith("来") else "きて")
    if ending is Ending.RU_VERB:
        return TeForm(kana[:-1] + "て", written[:-1] + "て")
    if kana in {"いく", "ゆく"} or written in {"行く", "逝く"}:
        return TeForm(kana[:-1] + "って", written[:-1] + "って")
    suffix = GODAN_TE[kana[-1]]
    return TeForm(kana[:-1] + suffix, written[:-1] + suffix)


def nai_form(written: str, kana: str) -> TeForm:
    """The plain negative: 食べない, 書かない, 買わない, しない, 来ない, and ある → ない."""
    ending = classify(written, kana)
    if ending is Ending.IRREGULAR:
        if kana.endswith("する"):
            return TeForm(kana[:-2] + "しない", written[:-2] + "しない")
        return TeForm("こない", "来ない" if written.startswith("来") else "こない")
    if kana == "ある":
        return TeForm("ない", "ない")
    if ending is Ending.RU_VERB:
        return TeForm(kana[:-1] + "ない", written[:-1] + "ない")
    stem = A_ROW[kana[-1]]
    return TeForm(kana[:-1] + stem + "ない", written[:-1] + stem + "ない")


def conjugate(written: str, kana: str, form: Form) -> TeForm:
    """The verb in `form`, built from the て-form or the plain negative."""
    if form is Form.NAI:
        return nai_form(written, kana)
    if form is Form.NAKATTA:
        nai = nai_form(written, kana)
        return TeForm(nai.kana[:-1] + "かった", nai.written[:-1] + "かった")
    te = te_form(written, kana)
    if form is Form.TEIRU:
        return TeForm(te.kana + "いる", te.written + "いる")
    if form is Form.TA:
        past = {"て": "た", "で": "だ"}
        return TeForm(te.kana[:-1] + past[te.kana[-1]], te.written[:-1] + past[te.written[-1]])
    return te
