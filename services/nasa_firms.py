import csv
import io
import httpx
from dataclasses import dataclass
from config import config

# Регионы: координаты (min_lon, min_lat, max_lon, max_lat)
REGIONS = {
    "Россия": (19.0, 41.0, 180.0, 82.0),
    "Сибирь": (60.0, 50.0, 140.0, 75.0),
    "Якутия": (105.0, 55.0, 165.0, 75.0),
    "Европа": (-25.0, 34.0, 45.0, 72.0),
    "Австралия": (110.0, -45.0, 155.0, -10.0),
    "Амазония": (-80.0, -20.0, -44.0, 10.0),
    "США": (-125.0, 24.0, -66.0, 50.0),
}


CONFIDENCE_LABELS = {
    "low": "🟡 Низкая",
    "nominal": "🟠 Средняя",
    "high": "🔴 Высокая",
}

CONFIDENCE_MAP = {
    "l": "low",
    "n": "nominal",
    "h": "high",
    "low": "low",
    "nominal": "nominal",
    "high": "high",
}

SATELLITE_NAMES = {
    "N": "Suomi NPP",
    "1": "NOAA-20",
    "2": "NOAA-21",
}

VIIRS_SOURCE = "VIIRS_SNPP_NRT"

FRP_ICONS = [
    (100, "🔥"),
    (10,  "🔶"),
    (0,   "🔸"),
]


@dataclass
class FirePoint:
    """Одна точка активного пожара из данных VIIRS."""
    latitude: float
    longitude: float
    brightness: float
    confidence: str
    acq_date: str
    acq_time: str
    satellite: str
    frp: float

    def confidence_label(self) -> str:
        """Возвращает локализованную метку уровня достоверности."""
        return CONFIDENCE_LABELS.get(self.confidence, self.confidence)

    def __str__(self) -> str:
        icon = next(ic for threshold, ic in FRP_ICONS if self.frp >= threshold)
        sat = SATELLITE_NAMES.get(self.satellite, self.satellite)
        conf = self.confidence_label() if self.confidence != "nominal" else "🟠 Средняя (норма)"

        return (
            f"📍 {self.latitude:.3f}, {self.longitude:.3f}\n"
            f"{icon} Мощность: {self.frp:.1f} МВт\n"
            f"Уверенность: {conf}\n"
            f"Спутник: {sat}\n"
            f"{self.acq_date} {self.acq_time[:2]}:{self.acq_time[2:]} UTC"
    )


async def fetch_fires_bbox(
    bbox: tuple,
    days: int = 1,
    min_confidence: str = "low",
) -> list[FirePoint]:
    """Получить пожары по произвольному bbox (min_lon, min_lat, max_lon, max_lat)."""
    area = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{config.NASA_API_KEY}/{VIIRS_SOURCE}/{area}/{days}"
    )
    return await _fetch_and_parse(url, min_confidence)


async def fetch_fires(
    region: str,
    days: int = 1,
    min_confidence: str = "nominal",
) -> list[FirePoint]:
    """
    Получить активные пожары по региону.
    
    region: ключ из REGIONS
    days: за сколько дней (1, 2)
    min_confidence: минимальный уровень уверенности (low / nominal / high)
    """
    if region not in REGIONS:
        raise ValueError(f"Неизвестный регион: {region}")

    bbox = REGIONS[region]
    area = f"{bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]}"
    url = (
        f"https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
        f"{config.NASA_API_KEY}/{VIIRS_SOURCE}/{area}/{days}"
    )

    return await _fetch_and_parse(url, min_confidence)


async def _fetch_and_parse(url: str, min_confidence: str) -> list[FirePoint]:
    """Загружает CSV по URL, фильтрует по достоверности и возвращает список FirePoint, отсортированный по FRP."""
    confidence_order = {"low": 0, "nominal": 1, "high": 2}
    min_level = confidence_order.get(min_confidence, 1)

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(url)
        response.raise_for_status()

    fires = []
    reader = csv.DictReader(io.StringIO(response.text.strip()))

    for row in reader:
        confidence_raw = row.get("confidence", "nominal").strip().lower()
        confidence = CONFIDENCE_MAP.get(confidence_raw, "nominal")

        if confidence_order.get(confidence, 0) < min_level:
            continue

        try:
            fire = FirePoint(
                latitude=float(row["latitude"]),
                longitude=float(row["longitude"]),
                brightness=float(row.get("bright_ti4") or 0),
                confidence=confidence,
                acq_date=row.get("acq_date", ""),
                acq_time=row.get("acq_time", "0000").zfill(4),
                satellite=row.get("satellite", "N/A"),
                frp=float(row.get("frp") or 0),
            )
            fires.append(fire)
        except (ValueError, KeyError):
            continue

    fires.sort(key=lambda f: f.frp, reverse=True)
    return fires


def get_stats(fires: list[FirePoint]) -> dict:
    """Базовая статистика по списку пожаров."""
    if not fires:
        return {}

    total = len(fires)
    high = sum(1 for f in fires if f.confidence == "high")
    nominal = sum(1 for f in fires if f.confidence == "nominal")
    low = sum(1 for f in fires if f.confidence == "low")
    avg_frp = sum(f.frp for f in fires) / total
    max_frp = max(f.frp for f in fires)

    return {
        "total": total,
        "high": high,
        "nominal": nominal,
        "low": low,
        "avg_frp": round(avg_frp, 1),
        "max_frp": round(max_frp, 1),
    }
