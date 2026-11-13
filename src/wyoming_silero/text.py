"""Text preparation: from an LLM or Home Assistant answer to pieces the Russian model can speak.

Speech marks the model reads stay: ``+`` before a stressed vowel, ``*word*`` (the intonation
centre of a question) and ``**word**`` (emphasis); the rest of Markdown goes.

The model speaks Cyrillic only: it skips digits, and text without Cyrillic letters makes it raise.
High-quality English pronunciation belongs to the client (FlowPilot's "Text for speech" node, which
marks stress with `+`); here a plain letter-based fallback only keeps the speaker from going silent.
"""

import re
import unicodedata

from num2words import num2words

from .synthesizer import MAX_INPUT_CHARS

# Markup


_CODE_FENCE = re.compile(r"^\s*```.*$", re.MULTILINE)
_INLINE_CODE = re.compile(r"`([^`]*)`")
_MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
_URL = re.compile(r"\b(?:https?://|www\.)\S+", re.IGNORECASE)
_HEADING = re.compile(r"^\s{0,3}#{1,6}\s*", re.MULTILINE)
_QUOTE = re.compile(r"^\s*>+\s?", re.MULTILINE)
_BULLET = re.compile(r"^\s*(?:[-*+•–—]|\d{1,2}[.)])\s+", re.MULTILINE)
_EMPHASIS = re.compile(r"~~|(?<!\w)_+|_+(?!\w)")
# v5_6_ru reads *word* as the intonation centre of a question and **word** as emphasis
# (habr.com/ru/articles/1015942 and 1094196): paired marks stay, stray asterisks go.
_MARKED = re.compile(r"(\*{1,2})(?=[^\s*])([^*\n]*?[^\s*])\1(?!\*)")


def _keep_speech_marks(text: str) -> str:
    text = _MARKED.sub(lambda m: f"{chr(1) * len(m[1])}{m[2]}{chr(1) * len(m[1])}", text)
    return text.replace("*", "").replace(chr(1), "*")


_TABLE_RULE = re.compile(r"^\s*\|?(?:\s*:?-{3,}:?\s*\|)+\s*:?-*:?\s*$", re.MULTILINE)


def clean_markup(text: str) -> str:
    """Drop Markdown, code fences and links, keeping the words a person would read out."""
    text = _CODE_FENCE.sub("", text)
    text = _INLINE_CODE.sub(r"\1", text)
    text = _MD_LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _TABLE_RULE.sub("", text)
    text = _HEADING.sub("", text)
    text = _QUOTE.sub("", text)
    text = _BULLET.sub("", text)
    text = _EMPHASIS.sub("", text)
    text = _keep_speech_marks(text)
    text = text.replace("|", ", ")
    return text


# Numbers

_MONTHS_GENITIVE = (
    "января", "февраля", "марта", "апреля", "мая", "июня",
    "июля", "августа", "сентября", "октября", "ноября", "декабря",
)  # fmt: skip


def _plural(number: str, one: str, few: str, many: str) -> str:
    """Russian noun form after a number written in digits."""
    if "," in number or "." in number:
        return few  # 21,5 градуса
    n = int(number)
    if 11 <= n % 100 <= 14:
        return many
    if n % 10 == 1:
        return one
    if 2 <= n % 10 <= 4:
        return few
    return many


def _cardinal(number: str, gender: str = "m") -> str:
    if "," in number or "." in number:
        return str(num2words(float(number.replace(",", ".")), lang="ru"))
    return str(num2words(int(number), lang="ru", gender=gender))


def _ordinal(number: int, case: str = "n", gender: str = "m", plural: bool = False) -> str:
    return str(num2words(number, lang="ru", to="ordinal", case=case, gender=gender, plural=plural))


def _date(day: str, month: str, year: str) -> str | None:
    d, m, y = int(day), int(month), int(year)
    if not (1 <= d <= 31 and 1 <= m <= 12):
        return None
    return f"{_ordinal(d, gender='n')} {_MONTHS_GENITIVE[m - 1]} {_ordinal(y, case='g')} года"


def _sub_date(match: re.Match[str]) -> str:
    return _date(match["d"], match["m"], match["y"]) or match[0]


def _sub_time(match: re.Match[str]) -> str:
    hours, minutes = int(match[1]), match[2]
    if minutes == "00":
        spoken = "ноль ноль"
    elif minutes.startswith("0"):
        spoken = f"ноль {_cardinal(minutes[1])}"
    else:
        spoken = _cardinal(minutes)
    return f"{_cardinal(str(hours))} {spoken}"


# Case of an ordinal by the suffix written after it: 1-й, 2-го, 3-му, 5-м, 6-х.
_ORDINAL_SUFFIXES: dict[str, tuple[str, str, bool]] = {
    "й": ("n", "m", False), "ый": ("n", "m", False), "ий": ("n", "m", False),
    "ой": ("n", "m", False), "я": ("n", "f", False), "ая": ("n", "f", False),
    "е": ("n", "n", False), "ое": ("n", "n", False), "го": ("g", "m", False),
    "ого": ("g", "m", False), "му": ("d", "m", False), "ому": ("d", "m", False),
    "м": ("p", "m", False), "ом": ("p", "m", False), "х": ("p", "m", True),
    "ых": ("p", "m", True),
}  # fmt: skip


def _sub_ordinal(match: re.Match[str]) -> str:
    case, gender, plural = _ORDINAL_SUFFIXES[match[2].lower()]
    return _ordinal(int(match[1]), case=case, gender=gender, plural=plural)


# Case of a year by the word after it: 2026 год, 2026 года, в 2026 году, 2026 годом, 2026 г.
_YEAR_CASES = {"год": "n", "года": "g", "году": "p", "годом": "i", "г": "g"}


def _sub_year(match: re.Match[str]) -> str:
    word = match[2].lower().rstrip(".")
    case = _YEAR_CASES[word]
    noun = "года" if word == "г" else match[2]
    return f"{_ordinal(int(match[1]), case=case)} {noun}"


_UNITS: dict[str, tuple[str, str, str]] = {
    "%": ("процент", "процента", "процентов"),
    "°": ("градус", "градуса", "градусов"),
    "₽": ("рубль", "рубля", "рублей"),
    "€": ("евро", "евро", "евро"),
    "м/с": ("метр в секунду", "метра в секунду", "метров в секунду"),
    "км/ч": ("километр в час", "километра в час", "километров в час"),
}


def _sub_unit(match: re.Match[str]) -> str:
    number, unit = match[1], match[2]
    if unit.startswith("°"):
        unit = "°"
    return f"{_cardinal(number)} {_plural(number, *_UNITS[unit.lower()])}"


# Common written abbreviations the model would read letter by letter.
_PHRASES = [
    (re.compile(r"\bт\.\s?е\.", re.IGNORECASE), "то есть"),
    (re.compile(r"\bт\.\s?д\.", re.IGNORECASE), "так далее"),
    (re.compile(r"\bт\.\s?п\.", re.IGNORECASE), "тому подобное"),
]


_NUM = r"\d+(?:[.,]\d+)?"
_THOUSANDS = re.compile(r"(?<![\d.,])\d{1,3}(?:[   ]\d{3})+(?![\d.,]\d)")
_DATE = re.compile(r"\b(?P<d>\d{1,2})\.(?P<m>\d{1,2})\.(?P<y>\d{4})\b")
_ISO_DATE = re.compile(r"\b(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})\b")
_TIME = re.compile(r"\b([01]?\d|2[0-3]):([0-5]\d)\b")
_RANGE = re.compile(r"(\d)\s?[-–—]\s?(?=\d)")
_SIGN = re.compile(r"(^|[\s(\[«\"])([-−+])(?=\d)")
_ORDINAL = re.compile(r"\b(\d+)-(" + "|".join(_ORDINAL_SUFFIXES) + r")\b", re.IGNORECASE)
_YEAR = re.compile(r"\b(\d{4})\s+(год[ауом]{0,2}|г\.)(?!\w)", re.IGNORECASE)
_UNIT = re.compile(rf"({_NUM})\s?(%|°\s?[CСcс]?(?![a-zа-яё])|₽|€|м/с|км/ч)(?!\w)", re.IGNORECASE)
_NUMBER = re.compile(rf"(?<![\w]){_NUM}|\d+")


def expand_numbers(text: str) -> str:
    """Write numbers out in Russian words: the model skips digits."""
    text = _THOUSANDS.sub(lambda m: re.sub(r"\D", "", m[0]), text)
    text = _DATE.sub(_sub_date, text)
    text = _ISO_DATE.sub(_sub_date, text)
    text = _TIME.sub(_sub_time, text)
    text = _RANGE.sub(r"\1 — ", text)
    text = _SIGN.sub(lambda m: m[1] + ("плюс " if m[2] == "+" else "минус "), text)
    text = text.replace("№", " номер ")
    text = _ORDINAL.sub(_sub_ordinal, text)
    text = _YEAR.sub(_sub_year, text)
    text = _UNIT.sub(_sub_unit, text)
    text = _NUMBER.sub(lambda m: f" {_cardinal(m[0])} ", text)
    return text


# Latin letters

_LETTER_NAMES = {
    "a": "эй", "b": "би", "c": "си", "d": "ди", "e": "и", "f": "эф", "g": "джи", "h": "эйч",
    "i": "ай", "j": "джей", "k": "кей", "l": "эл", "m": "эм", "n": "эн", "o": "оу", "p": "пи",
    "q": "кью", "r": "ар", "s": "эс", "t": "ти", "u": "ю", "v": "ви", "w": "дабл ю", "x": "экс",
    "y": "уай", "z": "зед",
}  # fmt: skip

_DIGRAPHS = {
    "sch": "ш", "tch": "ч", "igh": "ай", "ow": "оу", "sh": "ш", "ch": "ч", "th": "т", "ph": "ф",
    "ck": "к", "qu": "кв",
    "wh": "у", "oo": "у", "ee": "и", "ea": "и", "ou": "ау", "ai": "эй", "ay": "эй", "oy": "ой",
    "kn": "н", "ng": "нг", "gh": "г", "ya": "я", "yo": "ё", "yu": "ю", "ye": "е",
}  # fmt: skip

_LETTERS = {
    "a": "а", "b": "б", "c": "к", "d": "д", "e": "е", "f": "ф", "g": "г", "h": "х", "i": "и",
    "j": "дж", "k": "к", "l": "л", "m": "м", "n": "н", "o": "о", "p": "п", "q": "к", "r": "р",
    "s": "с", "t": "т", "u": "у", "v": "в", "w": "в", "x": "кс", "y": "и", "z": "з",
}  # fmt: skip

_LATIN_WORD = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_DIGRAPH = re.compile("|".join(sorted(_DIGRAPHS, key=len, reverse=True)))


def _transliterate_word(word: str) -> str:
    if word.isupper() and len(word) <= 5:
        return " ".join(_LETTER_NAMES[c] for c in word.lower())  # USB, TV, HA
    lower = word.lower().replace("'", "")
    if len(lower) > 3 and lower.endswith("e") and lower[-2] not in "aeiouy":
        lower = lower[:-1]  # a silent final e: home, simple
    out: list[str] = []
    i = 0
    while i < len(lower):
        match = _DIGRAPH.match(lower, i)
        if match:
            out.append(_DIGRAPHS[match[0]])
            i = match.end()
        else:
            out.append(_LETTERS.get(lower[i], ""))
            i += 1
    return "".join(out)


def transliterate_latin(text: str) -> str:
    """Letter-based fallback for Latin words, so English text is not silently dropped."""
    return _LATIN_WORD.sub(lambda m: _transliterate_word(m[0]), text)


# Everything else


_STRESS_VOWELS = "аеёиоуыэюяАЕЁИОУЫЭЮЯ"
_STRAY_PLUS = re.compile(rf"\+(?![{_STRESS_VOWELS}])")
_SPACES = re.compile(r"[ \t  ]+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([,.!?;:…])")
_REPEATED_PUNCT = re.compile(r"([,;:])(?:\s*[,;:])+")
_LEADING_PUNCT = re.compile(r"^[\s,.;:!?…—–-]+")
_CYRILLIC = re.compile(r"[а-яё]", re.IGNORECASE)
_SENTENCE_END = ".!?…"


def _keep_char(char: str) -> bool:
    if char in "+\n":
        return True
    category = unicodedata.category(char)
    # Letters, digits, punctuation and spaces stay; emoji, symbols and invisible joiners go.
    return category[0] in "LNPZ"


def strip_unspeakable(text: str) -> str:
    return "".join(c if _keep_char(c) else " " for c in text)


def is_speakable(text: str) -> bool:
    """The model raises on text without Cyrillic letters."""
    return _CYRILLIC.search(text) is not None


def normalize(text: str) -> str:
    """Prepare one sentence (or line) for the model. May return an empty string."""
    text = clean_markup(text)
    for pattern, phrase in _PHRASES:
        text = pattern.sub(phrase, text)
    text = expand_numbers(text)
    text = transliterate_latin(text)
    text = strip_unspeakable(text)
    text = _STRAY_PLUS.sub("", text)
    text = text.replace("\n", " ")
    text = _SPACES.sub(" ", text)
    text = _SPACE_BEFORE_PUNCT.sub(r"\1", text)
    text = _REPEATED_PUNCT.sub(r"\1", text)
    text = _LEADING_PUNCT.sub("", text).strip()
    if not is_speakable(text):
        return ""
    if text[-1] not in _SENTENCE_END:
        # A list item or heading: end it so the intonation falls.
        text = text.rstrip(",;:—–-").rstrip() + "."
    return text


def split_long(text: str, limit: int = MAX_INPUT_CHARS) -> list[str]:
    """Cut text the model would reject as too long: at punctuation, then at spaces."""
    pieces = []
    while len(text) > limit:
        window = text[:limit]
        cut = max(window.rfind(p) for p in ",;:—")
        if cut < limit // 3:
            cut = window.rfind(" ")
        if cut < limit // 3:
            cut = limit - 1
        pieces.append(text[: cut + 1].strip())
        text = text[cut + 1 :].strip()
    if text:
        pieces.append(text)
    return [p for p in pieces if is_speakable(p)]


def prepare(text: str) -> list[str]:
    """One raw sentence in, model-ready pieces out (none if there is nothing to say)."""
    normalized = normalize(text)
    return split_long(normalized) if normalized else []


# Sentences

# Words after which a period does not end the sentence.
_ABBREVIATIONS = frozenset(
    "т е д п г гг ул им др см стр напр руб коп мин сек тыс млн млрд проф акад св".split()
)
_BOUNDARY = re.compile(r"[.!?…]+[\"'»)\]]*(?=\s)|\n")
_LAST_WORD = re.compile(r"(\w+)$")


def _is_boundary(text: str, match: re.Match[str]) -> bool:
    if match[0] == "\n" or "." not in match[0] or match[0].startswith(("!", "?", "…")):
        return True
    word = _LAST_WORD.search(text, 0, match.start())
    if word is None:
        return True
    if word[1].isdigit() and not text[: word.start()].rsplit("\n", 1)[-1].strip():
        return False  # "1. " numbering a list item
    return word[1].lower() not in _ABBREVIATIONS


class SentenceBuffer:
    """Collects streamed text and hands out whole sentences as soon as they end.

    A sentence ends at `.`, `!`, `?` or `…` followed by a space and some more text (so `21.5` and a
    period that is still waiting for its next chunk are not cut), or at a line break.
    """

    def __init__(self) -> None:
        self._buffer = ""

    def add(self, text: str) -> list[str]:
        self._buffer += text
        sentences = []
        start = 0
        for match in _BOUNDARY.finditer(self._buffer):
            end = match.end()
            # Wait for the first character of the next sentence before cutting.
            if not self._buffer[end:].strip():
                break
            if not _is_boundary(self._buffer, match):
                continue
            sentences.append(self._buffer[start:end])
            start = end
        self._buffer = self._buffer[start:]
        return [s for s in sentences if s.strip()]

    def flush(self) -> list[str]:
        rest, self._buffer = self._buffer, ""
        return [rest] if rest.strip() else []


def split_sentences(text: str) -> list[str]:
    buffer = SentenceBuffer()
    return buffer.add(text) + buffer.flush()
