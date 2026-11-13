"""Text preparation on typical agent and Home Assistant answers."""

import pytest

from wyoming_silero.text import (
    SentenceBuffer,
    expand_numbers,
    normalize,
    prepare,
    split_long,
    split_sentences,
    transliterate_latin,
)


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Сейчас 21,5 °C.", "Сейчас двадцать одна целая пять десятых градуса."),
        ("На улице -3°C.", "На улице минус три градуса."),
        ("Плюс +5°.", "Плюс плюс пять градусов."),
        ("Влажность 40%.", "Влажность сорок процентов."),
        ("Заряд 1%, 2%, 11%.", "Заряд один процент, два процента, одиннадцать процентов."),
        ("Будильник на 7:05.", "Будильник на семь ноль пять."),
        ("Встреча в 18:00.", "Встреча в восемнадцать ноль ноль."),
        (
            "Это было 13.11.2026.",
            "Это было тринадцатое ноября две тысячи двадцать шестого года.",
        ),
        ("Дата 2026-03-08.", "Дата восьмое марта две тысячи двадцать шестого года."),
        ("В 2026 году.", "В две тысячи двадцать шестом году."),
        ("1-й этаж, 2-го числа.", "первый этаж, второго числа."),
        ("Население 10 000 человек.", "Население десять тысяч человек."),
        ("Ветер 5 м/с.", "Ветер пять метров в секунду."),
        ("Квартира №12.", "Квартира номер двенадцать."),
        ("Цена 300 ₽.", "Цена триста рублей."),
        ("Ехать 2-3 часа.", "Ехать два — три часа."),
    ],
)
def test_numbers(text: str, expected: str) -> None:
    assert normalize(text) == expected


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("**Готово**, свет _включён_.", "Готово, свет включён."),
        ("## Погода", "Погода."),
        ("- Купить хлеб", "Купить хлеб."),
        ("Позвоните [в поддержку](https://example.com/help).", "Позвоните в поддержку."),
        ("Подробнее: https://example.com/a?b=1", "Подробнее."),
        ("Код `ok` получен.", "Код ок получен."),
        ("Готово! 👍🎉", "Готово!"),
        ("> Цитата", "Цитата."),
        ("| Кухня | 21 |", "Кухня, двадцать один."),
        ("Это т. е. пример, и т. д.", "Это то есть пример, и так далее."),
    ],
)
def test_markup_and_symbols(text: str, expected: str) -> None:
    assert normalize(text) == expected


def test_stress_marks_pass_through() -> None:
    assert normalize("Включаю муз+ыку на ст+анции.") == "Включаю муз+ыку на ст+анции."
    assert normalize("Язык C++ и муз+ыка.") == "Язык си и муз+ыка."


def test_latin_fallback() -> None:
    assert transliterate_latin("Spotify") == "спотифи"
    assert transliterate_latin("USB и TV") == "ю эс би и ти ви"
    assert transliterate_latin("light") == "лайт"
    assert normalize("The lights are on.") != ""


@pytest.mark.parametrize(
    "text", ["", "   ", "👍", "🎉🎉", "***", "https://example.com", "...", "\n\n"]
)
def test_nothing_to_say(text: str) -> None:
    assert prepare(text) == []


def test_digits_only_are_spoken() -> None:
    assert prepare("12345") == ["двенадцать тысяч триста сорок пять."]


def test_decimal_is_not_a_sentence_end() -> None:
    assert expand_numbers("3.5") == " три целых пять десятых "
    assert split_sentences("Сейчас 3.5 градуса. Ясно.") == ["Сейчас 3.5 градуса.", " Ясно."]


def test_sentences_keep_their_punctuation() -> None:
    assert split_sentences("Ты выключил утюг? Какая погода! Ну… ладно.") == [
        "Ты выключил утюг?",
        " Какая погода!",
        " Ну…",
        " ладно.",
    ]


def test_abbreviations_and_lists() -> None:
    assert split_sentences("Это т. е. пример. Да.") == ["Это т. е. пример.", " Да."]
    assert split_sentences("План:\n1. Хлеб\n2. Молоко") == ["План:\n", "1. Хлеб\n", "2. Молоко"]


def test_buffer_waits_for_the_next_sentence() -> None:
    buffer = SentenceBuffer()
    assert buffer.add("Первое.") == []
    assert buffer.add(" ") == []
    assert buffer.add("Вто") == ["Первое."]
    assert buffer.add("рое! Третье") == [" Второе!"]
    assert buffer.flush() == [" Третье"]
    assert buffer.flush() == []


def test_long_sentence_is_cut_for_the_model() -> None:
    sentence = ", ".join(["очень длинное перечисление разных вещей"] * 40) + "."
    pieces = prepare(sentence)
    assert len(pieces) > 1
    assert all(len(p) <= 600 for p in pieces)
    assert " ".join(pieces).replace(",", "") == sentence.replace(",", "")


def test_split_long_without_punctuation() -> None:
    pieces = split_long("слово " * 300, limit=100)
    assert all(len(p) <= 100 for p in pieces)
    assert " ".join(pieces).split() == ["слово"] * 300
