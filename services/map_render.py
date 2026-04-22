import io
import logging
from staticmap import StaticMap, CircleMarker
from services.nasa_firms import FirePoint

logger = logging.getLogger(__name__)

CONFIDENCE_COLORS = {
    "high": "#FF2200",
    "nominal": "#FF8800",
    "low": "#FFCC00",
}


def render_fire_map(fires: list[FirePoint], width: int = 800, height: int = 600) -> io.BytesIO | None:
    """Рендерит PNG-карту с маркерами пожаров; возвращает None при ошибке тайлов."""
    if not fires:
        return None

    m = StaticMap(width, height)
    for fire in fires:
        color = CONFIDENCE_COLORS.get(fire.confidence, "#FF8800")
        radius = 6 if fire.confidence == "high" else 4
        m.add_marker(CircleMarker((fire.longitude, fire.latitude), color, radius))

    try:
        image = m.render()
    except Exception as e:
        logger.warning(f"Не удалось загрузить тайлы карты: {e}")
        return None

    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf
