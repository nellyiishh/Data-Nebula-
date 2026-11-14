# Карта TRACE: что исправить (для Altynai)

Дата: 2026-11-14 · Ветка: `merge/backend-web` (PR #1 в `main`) · Подготовил: Mavlan (фронтенд)

Сайт с настоящими данными Тогуз-Булака работает: радарные снимки NISAR, 6 пролётов, дождь IMERG, слои
когерентности и смещения. Ниже то, что видно на скриншоте и мешает. Каждый пункт проверен в Chromium
через Playwright CLI, причина найдена, для пунктов 1 и 2 рецепт проверен на сборке.

| # | Что видно | Где чинить | Сложность |
|---|---|---|---|
| 1 | На фоне карты надписи «API KEY REQUIRED» | фронт, `web/src/core/map/SarMap.tsx` | 5 минут |
| 2 | Дома, дороги, контуры не рисуются; в консоли `Worker failed to load` | фронт, `web/src/main.tsx` | 5 минут, рецепт проверен |
| 3 | «No change analysis for this area yet», нет проверки радар/фото | данные, `data/ext/toguz-bulak/` | нужен контур оползня |
| 4 | «0 km to Toguz-Bulak» | данные, `pipeline/exposure.py` | после п. 3 |
| 5 | «No registered events», одна точка «village» | данные, `data/manifest.json` | 20–30 минут |

Пункты 1–2 фронтендовые, но они маленькие, и рецепт ниже готов. Если удобнее, их сделаю я, а ты бери 3–5.

---

## 1. Подложка: CARTO теперь требует ключ

**Проверка.** Любой тайл `https://{a,b,c}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png` теперь отдаёт
одну и ту же картинку «API KEY REQUIRED · carto.com/basemaps/apikey», с Referer и без. Значит, это не наш баг:
CARTO закрыл бесплатный доступ.

**Где:** `web/src/core/map/SarMap.tsx`, константа `BASEMAP`, строка с `basemaps.cartocdn.com`.

**Чем заменить.** Все варианты ниже 14.11 отвечали `200` без ключа:

| Вариант | URL тайлов | Плюсы | Минусы |
|---|---|---|---|
| **Esri World Imagery** (рекомендую) | `https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}` | Спутниковое фото: видно склоны, село, дорогу, хороший контекст к радару | Порядок `{z}/{y}/{x}` (не `x/y`)! Нужна атрибуция «Esri, Maxar, Earthstar Geographics». Перед публикацией проверить условия Esri |
| OpenStreetMap | `https://tile.openstreetmap.org/{z}/{x}/{y}.png` | Подписи сёл и дорог | Светлая, по правилам OSM нельзя большую нагрузку; атрибуция «© OpenStreetMap contributors» |
| NASA GIBS | `https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/BlueMarble_ShadedRelief_Bathymetry/default/GoogleMapsCompatible_Level8/{z}/{y}/{x}.jpeg` | NASA, плюс к Relevance | Только до zoom 8, для участка 5 км слишком грубо, годится на hero-карту |

Пример замены в `BASEMAP`:

```ts
base: {
  type: 'raster',
  tiles: ['https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}'],
  tileSize: 256,
  maxzoom: 18,
  attribution: 'Imagery © Esri, Maxar, Earthstar Geographics',
},
```

Потом поправить подпись «Basemap» в `web/src/features/story/content.ts` (`DATASETS`).

---

## 2. «Worker failed to load»: векторные слои не рисуются

**Что ломается.** Все GeoJSON-слои: дома и дороги (`exposure`), контуры, радиус 2 км. MapLibre парсит GeoJSON в
web worker, а worker не загружается. Радарные снимки PNG идут без воркера, поэтому они видны.

**Причина (найдена).** MapLibre 6 строит путь к своему воркеру во время работы:
`new URL('./maplibre-gl-worker.mjs', import.meta.url)`. Vite такую строку не видит:
- в `npm run dev` запрос `/node_modules/.vite/deps/maplibre-gl-worker.mjs` → **504 Outdated Optimize Dep** (после перезапуска тоже);
- в `npm run build` файла воркера **нет в `dist/assets/`**, то есть на проде тоже сломано.

**Исправление** (проверено: воркер попадает в `dist/assets/maplibre-gl-worker-*.mjs`, ошибок в консоли нет,
дома и дороги рисуются). В `web/src/main.tsx` после импортов:

```ts
import { setWorkerUrl } from 'maplibre-gl'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

// MapLibre 6 resolves its worker at runtime, which Vite cannot see; hand it the bundled URL.
setWorkerUrl(maplibreWorkerUrl)
```

`vite.config.ts` трогать не нужно. Проверить:

```bash
cd web && npx tsc -b && npm run lint && npm run build && ls dist/assets | grep worker
```

Потом `npm run dev` → `http://localhost:5173/?site=toguz-bulak&view=app&step=infra`: на карте должны появиться
жёлтые точки (дома) и линии (дороги), в консоли без `Worker failed to load`.

---

## 3. Нет проверки «радар против фото»

**Что видно.** Сводка: «No change analysis for this area yet», `slope_echo.validation = null`.

**Причина.** Это уже записано у тебя в `docs/wiring-notes.md`: валидация считается только когда в
`data/ext/toguz-bulak/` есть `scar.geojson` (контур оползня) и `stable.geojson` (стабильная зона). Их нет.

**Что нужно.**
1. Обвести оползень (участок Донуз-Ой) на послесобытийной оптике (Sentinel-2/HLS после 10.10) → `scar.geojson`.
2. Выбрать ровный участок рядом без изменений (поле, плато, не склон и не снег) → `stable.geojson`.
3. Добавить оба в `overlays` в манифесте (`kind: "polygon"`, `id: "scar"` и `"stable"`): фронт уже умеет их рисовать и
   включает `scar` по умолчанию.
4. Перезапустить экспорт (`python -m pipeline.export_static`), закоммитить `data/web/`.

Внимание: последний пролёт **11.10**, это всего через день после события, а следующий снимок после 10.10 только один.
Если есть пролёт 23.10, его стоит добавить в `granules`, иначе пара «до/после» одна. И снег с конца октября: отметь в
`limitations`, если он есть на снимках.

---

## 4. «0 km to Toguz-Bulak»

**Причина.** `exposure` считается вокруг точки села (`method`: «measured around this point, not around the slide»),
поэтому расстояние от села до села = 0. Формально верно, но на экране читается странно.

**Варианты:**
- после п. 3 считать радиус 2 км и расстояние от **центра контура оползня** до села (как в описании `exposure` в README фронта);
- до этого: не писать `distance_km` (или `null`), тогда фронт можно научить скрывать эту плашку. Скажи, какой вариант, я подстрою фронт.

---

## 5. Пусто: «Registered events» и мало точек

**Registered events.** В `slope_echo.catalog` для Тогуз-Булака ничего нет. Нужны 2–4 реальных события рядом:
- само событие 10.10.2026 (источник МЧС/Economist.kg, ссылка уже есть в `event`);
- прошлые оползни и сели в Кара-Кульджинском районе из NASA Global Landslide Catalog / COOLR (`https://landslides.nasa.gov/`).

Формат: `{ "date": "YYYY-MM-DD", "type": "landslide|mudflow", "name": "...", "source": { "name": "...", "url": "..." } }`.

**Точки.** В `points_of_interest` только `village`. Для графика во времени (шаг 2 «Change analysis» и
Listen to Earth) нужны хотя бы:
- `body`: тело оползня;
- `scarp`: стенка срыва (верх);
- `stable`: стабильная точка для сравнения (из п. 3).

И для каждой файл в `point_extras` (когерентность и смещение по парам), как уже сделано для `village`.

---

## Мелочи (не срочно)

- **Легенда.** API уже отдаёт `display` (диапазон дБ, порог изменений, цвета). Фронт пока берёт свои числа
  (`TODO(legend-api)` в `web/src/features/sites/model/layers.ts`). Это сделаю я, только не меняй формат `display`.
- **Режим API.** Файлы `slope_echo` фронт пока всегда берёт из статики (`paths.siteFile`, `TODO(slope-echo-api)`), хотя
  у тебя есть `GET /sites/{id}/files/...`. Тоже на мне.
- **Тесты бэкенда** падают на импорте без `uv sync --group pipeline` (нужен rasterio). Стоит написать в
  `backend/` README или сделать так, чтобы эти тесты пропускались без группы.
- **Lock-файл.** После слияния `backend_p1` из `web/package-lock.json` пропали `@emnapi/*`, и `npm ci` падал.
  В PR #1 это исправлено. Если меняешь что-то в `web/`, не коммить `package-lock.json` из старой версии.

## Как проверить всё вместе

```bash
cd web && npm ci && npm run dev
```

Открыть в обычном Chromium (с включённым «Use graphics acceleration», без него WebGL не работает):
`http://localhost:5173/?site=toguz-bulak&view=app`. Пройти шаги 1–5 сверху.
