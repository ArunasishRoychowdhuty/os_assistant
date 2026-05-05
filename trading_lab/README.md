# Trading Lab

Isolated research and guarded-trading scaffold. This folder is not wired into
the OS Assistant app yet.

Modes:

- `research_only`: analyze market data and produce signals only.
- `paper_trading`: simulate orders against a virtual portfolio.
- `assisted_trading`: produce an order proposal for user review.
- `live_trading_guarded`: broker execution interface exists, but every order
  stops at a preview and requires the exact `CONFIRM <preview_id>` phrase.

Non-goals:

- No autonomous real-money trading without per-order approval.
- No SQLite/local durable memory index.
- No workflow replay logs or run-history database.

Design notes:

- `RiskManager` blocks oversized, invalid, and market orders by default.
- `ConfirmationGate` stores only in-memory pending previews.
- `NoopBrokerClient` is the default live broker, so real execution is
  impossible until a broker adapter is intentionally injected.

Run tests:

```powershell
uv run --no-project python -m unittest discover trading_lab\tests
```
