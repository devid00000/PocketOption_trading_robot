# PocketOption Trading Robot

Trading terminal for Pocket Option built with Python and PySide6.

## Status

The project is under active development and is currently intended for demo-account testing.

The current known limitation is that the experimental chart does not yet fully match the Pocket Option chart. A separate persistent-browser diagnostic source is being tested to identify the exact market-data stream used by the platform.

## Safety

- Test only with a demo account until the market-data and trade-result pipelines are verified.
- Never commit `.env`, SSID values, cookies, databases, or logs.
```
