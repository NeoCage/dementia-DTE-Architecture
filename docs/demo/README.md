# Interactive demo

`index.html` is a self-contained page with two views.

**The record** draws one household's ninety-day trace: gait speed against her own rolling
baseline, the fidelity tier underneath it day by day, and the forward projection with its
point estimate suppressed. A nine-chapter narrated walkthrough steps through what each
part means. The data is not a reimplementation of the engine's rules — it is the engine's
own output, produced by [`scripts/export_trace.py`](../../scripts/export_trace.py).

**The ceiling** is an interactive console. Toggle the sensing, toggle consent, and watch
the tier re-derive and the claims open or close, with the same reason codes
[`src/dte/engine.py`](../../src/dte/engine.py) emits.

Open `index.html` in a browser. No build step, no server, no network.

Everything shown is synthetic. See [`DISCLAIMER.md`](../../DISCLAIMER.md).

## Regenerating the data

```bash
PYTHONPATH=src python scripts/export_trace.py > trace.json
```

The page embeds its trace inline, so regenerating is only needed if the engine's behaviour
changes and the picture should change with it.
