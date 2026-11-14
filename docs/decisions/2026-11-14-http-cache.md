# HTTP cache for prepared site files: 1 hour

**Decision.** Layer images, change images and site files (`/sites/{id}/files/…`) are sent with
`Cache-Control: public, max-age=3600`.

**Why.** The API only serves files the offline pipeline wrote; they change only when someone
reruns it. Caching saves the server re-sending the same images on every frame of the time
slider. Site JSON (`/sites`, `/sites/{id}`) and point time series are not cached.

**Cost.** After a pipeline rerun and redeploy, a browser or CDN may show the old images for up
to an hour. Acceptable for a hackathon demo; to force a refresh, redeploy with new dates or
lower the TTL in `backend/app/features/sites/routes.py`.
