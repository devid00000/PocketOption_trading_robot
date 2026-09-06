# PocketOption Trading Robot

Desktop trading terminal for Pocket Option built with Python and PySide6.

## Status

The project is under active development and is currently intended for demo-account testing.

Implemented foundation:

- PySide6 desktop interface
- SSID and UID-aware account configuration
- Playwright-based auth SSID capture
- Demo/real account profiles
- Balance polling
- Currency asset discovery
- Experimental realtime candlestick chart
- Strategy and indicator models
- JSON configuration
- SQLite trade logging foundation

The current known limitation is that the experimental chart does not yet fully match the Pocket Option chart. The detailed audit, checkpoint, roadmap, and current development status are documented in [`README_PROJECT.md`](README_PROJECT.md) and [`roadmap.md`](roadmap.md).

## Safety

- Test only with a demo account until the market-data and trade-result pipelines are verified.
- Never commit `.env`, SSID values, cookies, databases, or logs.
- This project uses an unofficial Pocket Option API integration.

## Local Run

```bash
./.venv/bin/python main.py gui
```

Install dependencies with `requirements.txt`. Playwright Chromium is required for automatic SSID capture:

```bash
./.venv/bin/python -m playwright install chromium
```
