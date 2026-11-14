"""Fixed display settings. The renderer uses them to draw every image, and each site
records them so the web legend shows exactly what the pixels mean."""

# One brightness range per polarization for every date, so an animation does not
# flicker from per-image contrast stretching.
DB_RANGE: dict[str, tuple[float, float]] = {"hh": (-25.0, 0.0), "hv": (-32.0, -8.0)}
RATIO_RANGE_DB = (0.0, 15.0)
WATER_THRESHOLD_DB = -18.0
CHANGE_THRESHOLD_DB = 3.0

WATER_RGBA = (30, 144, 255, 170)
DARKER_RGB = (215, 48, 39)  # surface got darker to radar: new water, harvest, burn scar
BRIGHTER_RGB = (69, 117, 180)  # surface got brighter: water retreat, growth, fresh debris


def hex_color(rgb: tuple[int, ...]) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb[:3])
