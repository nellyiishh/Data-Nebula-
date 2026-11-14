# Wiring notes

What is real, stubbed or demo-only today. Update this in the same change that alters it.

| Surface | State | Notes |
|---|---|---|
| `GET /api/v1/health` | Wired | |
| `GET /api/v1/sites…` (list, detail, stats, layers, change, timeseries) | Wired | Serves whatever the pipeline wrote to `data/derived/` |
| `demo-reservoir` site | **Demo data** | Synthetic (`pipeline/make_demo_site.py`), `source: "demo"`. The UI must label it as not real |
| Real NISAR site | `TODO(nisar-pipeline)` | `backend/pipeline/prepare_nisar.py` is a stub; `data/manifest.json` has no sites yet |
| Static fallback for the frontend (`public/data/`) | Not built | Planned: export the same files so the demo survives an API outage |
