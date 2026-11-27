# Finance Workbench V1

Finance Workbench adds an evidence-first analysis layer to the current `sbrate`
repository without changing the live crawler, scheduler, dashboard API, or
rate-update workflow.

## Goal

Every important financial number and conclusion should be traceable:

```text
raw source
  -> source locator
  -> evidence item
  -> calculation
  -> claim
  -> Excel / Word / PowerPoint output
```

V1 records the source file, bank/product, as-of date, field path, original
value, URL and unit for deposit-rate evidence.

`build_scaled_benchmark()` supports simulation-vs-actual OPB comparison and
records proportional scaling as an explicit assumption, not a forecast.

Firm output contracts require source trace and human approval. Company internal
templates or internal data must not be committed to this public repository.

This migration is contract-only and does not modify the live dashboard,
crawler, scheduler, workflow or data JSON.
