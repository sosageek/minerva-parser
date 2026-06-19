# Minerva Parser

> An end-to-end pipeline that acquires and analyzes documents from heterogeneous web sources — a data-acquisition component for the Italian national LLM **Minerva**.

## Overview

Given the URL of a page from one of the supported domains, **Minerva Parser** downloads the page, extracts only its informative content as clean **Markdown**, and compares it against a hand-built **Gold Standard (GS)**. The result is exposed through a **REST API**, with a minimal **web UI** for inspecting parses and their evaluation.

The project was developed for the *Laboratorio di Ingegneria Informatica* course at **Sapienza University of Rome**. It is intended as a data-acquisition stage for **Minerva**, the Italian national LLM developed by Sapienza NLP and Babelscape: the same kind of pipeline that lets a chatbot search the web, parse the retrieved pages, and ground its answers on up-to-date content.

## Architecture

The system is split into **two containerized services** orchestrated with **Docker Compose**. The backend bind-mounts the gold-standard data as a volume; the frontend reads everything through the backend API. The code is organized in strict layers — one class per file (except `parser.py`), where each module depends only on the layer immediately below it.

- **Backend** — Python 3.11 + **FastAPI**. Web acquisition uses **Crawl4AI** with **Playwright** (Chromium); **Pydantic** validates and serializes all I/O. A single shared crawler is created lazily and released safely on shutdown to avoid zombie processes. Runs on port `8003`.
- **Frontend** — A minimal, **stateless** FastAPI app that queries the backend through an `httpx.AsyncClient` (configured via `BACKEND_URL`) and renders **Jinja2** templates comparing raw HTML, `parsed_text` and `gold_text` together with their quality metrics. Runs on port `8004`.

All gold standards are loaded into memory at backend startup (handled in the FastAPI `lifespan`), so each request avoids disk I/O.

## Supported domains

Dedicated parsers are registered for the four assigned domains:

- `en.wikipedia.org`
- `www.nps.gov`
- `thebookerprizes.com`
- `www.meteoam.it`

Each domain has its own parser (`WikipediaParser`, `NpsParser`, `BookerParser`, `MeteoAmParser`) that subclasses a common abstract `Parser`, declares the CSS selectors to exclude up front, and implements `parse` and `normalize` with domain-specific Markdown-cleaning rules to remove residual noise (links, tables, inline promo junk).

Notable per-domain handling:

- **Wikipedia** is the only parser that decomposes the excluded nodes with BeautifulSoup as a preprocessing step (rather than letting Crawl4AI's selectors do it), because Crawl4AI's selectors aggressively stripped the tail text of adjacent inline nodes (e.g. after `.noprint` elements), hurting recall. It also restores math formulas rendered as images and truncates terminal sections (References, Notes, ...).
- **The Booker Prizes** excludes promotional `paragraph--type--*` widget blocks (teasers, carousels, media) and de-duplicates consecutive identical lines left by the CMS template.
- **MeteoAM** is the only Italian-language site and the only one with client-loaded widgets (`/meteosat`); it uses a conditional `delay_before_return_html` and a fallback without `target_elements` for non-article pages.

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET`  | `/domains` | List of supported domains |
| `GET`  | `/parse?url=` | Parse a live URL and return the clean text |
| `POST` | `/parse` | Parse raw HTML supplied in the body (no network request) |
| `GET`  | `/gold_standard?url=` | Gold-standard entry for a URL |
| `GET`  | `/full_gold_standard?domain=` | Full gold standard for a domain |
| `POST` | `/evaluate` | Evaluate a `parsed_text` against a `gold_text` |
| `GET`  | `/full_gs_eval?domain=` | Aggregated evaluation over a domain's entire gold standard |

The parse output (`ParseOutput`) contains `url`, `domain`, `title`, `html_text` and `parsed_text` (clean Markdown). Pydantic I/O schemas use `extra="forbid"` to reject out-of-spec request bodies. Interactive Swagger docs are available at `/docs`.

## Evaluation metrics

Since the parser is allowed to return Markdown but the gold standards are plain text, both texts are normalized with `strip_formatting` before tokenization — so formatting choices don't penalize a parser whose extracted text is semantically correct. Four complementary metrics are computed:

- **Token-level (set-based)** — precision, recall and F1 over the intersection of unique tokens (lowercased, no punctuation). Measures *whether* the content is present, ignoring order. This is the mandatory metric.
- **Noise ratio** — `1 − precision`; highlights how much residual noise remains when recall is already high.
- **ROUGE-1 (multiset)** — like the token-level metric but `Counter`-based, so it also accounts for repetitions (e.g. a duplicated widget).
- **chrF** — character n-gram F-score via `sacrebleu` (`n = 6`, `β = 2`), normalized to `[0, 1]`; useful where morphological variants and tokenization differences would unfairly lower the token-level score.

`/full_gs_eval` runs parsing + evaluation over every GS entry of a domain and **averages** the results; if some URLs fail to crawl, the aggregate is computed only on the successful ones (failures are reported in `failed_urls`).

### Results

Global aggregated averages per domain — all four parsers land comfortably in the "Good" band (F1 > 0.80), reaching F1 ≈ 0.99:

| Domain | Token-level F1 | ROUGE-1 F1 | Noise | chrF |
|--------|:---:|:---:|:---:|:---:|
| `en.wikipedia.org` | 0.991 | 0.993 | 0.009 | 0.992 |
| `thebookerprizes.com` | 0.995 | 0.987 | 0.005 | 0.966 |
| `www.nps.gov` | 0.990 | 0.985 | 0.002 | 0.973 |
| `www.meteoam.it` | 0.987 | 0.978 | 0.012 | 0.983 |

On `en.wikipedia.org` and `www.meteoam.it` recall slightly exceeds precision (the parser keeps almost all gold content at the cost of a little residual noise). On `thebookerprizes.com` and `www.nps.gov` the relationship inverts: these pages are noisier and full of promotional content and inline junk that CSS selectors can't remove, so the cleaning heuristics had to be more aggressive — pushing precision toward 1.0 while dropping some genuine content, a deliberate recall/precision trade-off.

## Project structure

```
minerva-parser/
├── backend/
│   ├── src/
│   │   ├── parsers/       # parser.py (abstract Parser + CrawlError), per-domain parsers,
│   │   │                  # _crawler.py (single shared AsyncWebCrawler), schema.py (ParsedDocument)
│   │   ├── eval/          # eval.py (abstract Evaluator), token_level_eval.py, chrf_eval.py, rouge_eval.py
│   │   ├── utils/         # cleaning.py (normalize_whitespace, remove_markup), markdown.py (strip_formatting)
│   │   ├── server/        # server.py (endpoints + lifespan), models.py (Pydantic schemas), registry.py
│   │   └── config.py      # paths, logging and crawler flags (all overridable via env vars)
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/              # FastAPI + Jinja2 + httpx (minimal stateless UI)
├── gs_data/               # gold-standard datasets (one JSON per domain)
├── domains.json           # supported domains
└── docker-compose.yaml
```

## Getting started

**Requirements:** Docker and Docker Compose.

```bash
docker compose up --build
```

Once the containers are running:

- Web UI → http://localhost:8004
- Backend API (Swagger) → http://localhost:8003/docs

The whole stack is containerized: the backend installs Playwright/Chromium at build time, so no local Python or browser setup is needed.

## Tech stack

`Python 3.11` · `FastAPI` · `Crawl4AI` · `Playwright` · `Pydantic` · `sacrebleu` · `BeautifulSoup` · `httpx` · `Jinja2` · `Docker Compose`

## Contributors

- Gabriele Lobello
- Marco Mazzocco
- Valentina Cillo

---

<sub>Developed for the <i>Laboratorio di Ingegneria Informatica</i> — Sapienza University of Rome. A data-acquisition component for the Minerva national LLM.</sub>
