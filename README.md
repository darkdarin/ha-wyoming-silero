<p align="center">
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="https://raw.githubusercontent.com/darkdarin/ha-wyoming-silero/main/assets/brand/dark_logo.png">
    <img alt="Wyoming Silero" src="https://raw.githubusercontent.com/darkdarin/ha-wyoming-silero/main/assets/brand/logo.png" width="420">
  </picture>
</p>

# Wyoming Silero для Home Assistant

[![Release](https://img.shields.io/github/v/release/darkdarin/ha-wyoming-silero?sort=semver)](https://github.com/darkdarin/ha-wyoming-silero/releases)
[![CI](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/ci.yml/badge.svg)](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/ci.yml)
[![Release build](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/release.yml/badge.svg)](https://github.com/darkdarin/ha-wyoming-silero/actions/workflows/release.yml)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2026.10%2B-18BCF2?logo=homeassistant&logoColor=white)](https://www.home-assistant.io/)
![aarch64](https://img.shields.io/badge/aarch64-yes-green.svg)
![amd64](https://img.shields.io/badge/amd64-yes-green.svg)
[![License](https://img.shields.io/github/license/darkdarin/ha-wyoming-silero)](LICENSE)

Русский **синтез речи** для Assist в Home Assistant, который работает на вашем сервере Home Assistant, без
облака: сервер [Wyoming](https://github.com/OHF-Voice/wyoming) на модели
[Silero](https://github.com/snakers4/silero-models) `v5_6_ru` в виде приложения Home Assistant. Assist и
[FlowPilot](https://github.com/darkdarin/flowpilot) говорят через него как через любой голос Wyoming.

> Ранняя версия (0.1). Синтез целым текстом и потоком работает на Raspberry Pi 5.

> **Модель Silero распространяется по лицензии [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.ru):
> только некоммерческое использование.** Модель не входит в проект: приложение скачивает её у Silero при первом
> запуске. Код проекта распространяется по лицензии Apache 2.0.

## Что вы получаете

- **Родные русские голоса.** Пять дикторов чисто русской модели `v5_6_ru` (`aidar`, `baya`, `kseniya`, `xenia`,
  `eugene`) без акцента, со встроенными ударениями и омографами, вопросительной и восклицательной интонацией.
- **Быстрые ответы на Raspberry Pi 5.** Ответ начинает звучать через 0,2–0,4 с после того, как дописано его
  первое предложение; речь синтезируется примерно в 15 раз быстрее, чем звучит, поэтому длинные ответы не
  заикаются.
- **Потоковый синтез.** Предложения озвучиваются по одному, пока ассистент ещё пишет ответ.
- **Текст, который пишет LLM.** Числа, даты, время, температура и проценты читаются словами; Markdown, ссылки и
  эмодзи пропускаются; разметка ударений `+` и SSML передаются модели.
- **Без тишины.** Ответ на английском произносится по буквам, а не пропадает; на текст, в котором нечего сказать,
  клиент получает ошибку Wyoming и понимает, что произошло.
- **Локально.** После загрузки модели приложение работает без интернета.

## Что нужно

- Home Assistant OS или Supervised, **2026.10 или новее**, на aarch64 или amd64 (например, Raspberry Pi 5).
- Около **800 МБ** свободной памяти и 150 МБ на диске для модели.
- Интернет при первом запуске, чтобы скачать модель.

## Установка

### Шаг 1. Установите приложение

[![Открыть приложение в Home Assistant](https://my.home-assistant.io/badges/supervisor_addon.svg)](https://my.home-assistant.io/redirect/supervisor_addon/?addon=1f182efb_wyoming_silero&repository_url=https%3A%2F%2Fgithub.com%2Fdarkdarin%2Fha-wyoming-silero)

1. Нажмите кнопку: Home Assistant предложит добавить репозиторий и откроет страницу приложения.
   Вручную: **Настройки → Приложения → Магазин приложений → ⋮ → Репозитории**, добавьте
   `https://github.com/darkdarin/ha-wyoming-silero` и найдите **Wyoming Silero** в магазине.
2. Установите приложение и запустите его. Первый запуск скачивает модель (около 150 МБ); когда голос готов,
   в журнале появляется **Ready on tcp://0.0.0.0:10200**.

### Шаг 2. Добавьте интеграцию Wyoming

Home Assistant сам находит приложение: подтвердите интеграцию **Wyoming Protocol** в
**Настройки → Устройства и службы**.

### Шаг 3. Выберите голос

В **Настройки → Голосовые ассистенты** откройте своего ассистента, выберите **silero** как синтез речи и выберите
голос.

В FlowPilot укажите в ноде «Синтез речи Wyoming» адрес `tcp://1f182efb-wyoming-silero:10200`.

## Настройки

| Параметр | По умолчанию | Что делает |
| --- | --- | --- |
| **Голос по умолчанию** | `baya` | Используется, если клиент не выбрал голос. `aidar` и `eugene` — мужские голоса, `baya`, `kseniya` и `xenia` — женские. |
| **Частота дискретизации** | `48000` | 8000, 24000 или 48000 Гц. Синтез одинаково быстрый на всех трёх. |
| **Потоки процессора** | `2` | На Raspberry Pi 5 больше не быстрее и забирает ядра у Home Assistant. |
| **Подробный журнал** | выкл. | Каждое произнесённое предложение и время его синтеза в журнале приложения. |

### Без Home Assistant (Docker)

Образ приложения — это и обычный Docker-образ:

```sh
docker run -d --name wyoming-silero -p 10200:10200 -v wyoming-silero-data:/data \
  ghcr.io/darkdarin/ha-wyoming-silero --voice xenia --sample-rate 48000 --threads 2
```

Добавьте его в Home Assistant как интеграцию **Wyoming Protocol** с адресом этой машины и портом 10200.

## Если что-то не работает

- **Приложение останавливается при запуске с «Could not download».** Не удалось скачать модель: проверьте доступ
  сервера Home Assistant в интернет и перезапустите приложение.
- **Нет silero в списке синтеза речи.** Проверьте, что приложение запущено и для него добавлена интеграция
  Wyoming Protocol.
- **Английские слова звучат неправильно.** Сервер только произносит латинские буквы по буквам. Подготовьте текст
  до того, как он попадёт на сервер, например нодой FlowPilot «Подготовка текста для речи».
- **Неправильное ударение в слове.** Поставьте `+` перед ударной гласной в тексте (`з+амок`, `зам+ок`).

## Как это работает

```
Assist / FlowPilot ──текст (потоком)──▶ буфер предложений ──▶ подготовка текста ──▶ Silero v5_6_ru (torch, CPU)
        ▲                                                                               │
        └────────────────────────── звук, по предложению ◀───────────────────────────────┘
```

Сервер собирает текст, который приходит потоком, в предложения. Каждое законченное предложение готовится (числа —
в слова, разметка и эмодзи — прочь, латиница — по буквам) и синтезируется в одном рабочем потоке, общем для всех
клиентов. Звук уходит клиенту сразу, пока следующее предложение ещё пишется. Модель скачивается один раз в данные
приложения, проверяется по SHA-256 и прогревается до того, как сервер откроет порт.

## Разработка

| Путь | Что там |
| --- | --- |
| `src/wyoming_silero/` | Сервер: загрузка модели, очередь синтеза, подготовка текста, обработчик Wyoming, связь с Supervisor |
| `tests/` | Тесты протокола и текста на поддельном синтезаторе (без torch); `test_real_model.py` — на настоящей модели |
| `addon/` | Приложение Home Assistant: параметры, переводы, документация, список изменений |
| `Dockerfile` | Образ приложения (Debian, torch только для CPU) |
| `scripts/` | `synthesize.py` (тестовый клиент с замерами), `build_addon.py` (локальное приложение), `brand.py` (картинки), `spike.py` |

```sh
uv sync                     # без torch: для тестов этого хватает
uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
uv sync --extra model       # с torch, чтобы запустить сервер
uv run wyoming-silero --data-dir ~/.cache/wyoming-silero --uri tcp://127.0.0.1:10200
uv run scripts/synthesize.py "Привет! Сейчас 21 °C."
```

## Лицензия

Код распространяется по лицензии [Apache 2.0](LICENSE). Модель Silero `v5_6_ru`, которая скачивается при запуске,
распространяется Silero по лицензии [CC BY-NC 4.0](https://creativecommons.org/licenses/by-nc/4.0/deed.ru).
