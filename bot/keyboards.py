from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
from services.nasa_firms import REGIONS, CONFIDENCE_LABELS


def _max_days(region: str) -> int:
    """Максимальный период зависит от размера bbox."""
    bbox = REGIONS.get(region)
    if not bbox:
        return 1
    width = abs(bbox[2] - bbox[0])
    height = abs(bbox[3] - bbox[1])
    if width > 50 or height > 30:
        return 2
    return 7


def main_menu() -> ReplyKeyboardMarkup:
    """Главное меню бота."""
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🔥 Пожары по региону")],
            [KeyboardButton(text="📍 Мой район")],
            [KeyboardButton(text="📊 Статистика"), KeyboardButton(text="ℹ️ Помощь")],
        ],
        resize_keyboard=True,
    )


def my_area_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора способа ввода местоположения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📍 Поделиться геолокацией", callback_data="myarea:geo")],
        [InlineKeyboardButton(text="✏️ Ввести координаты вручную", callback_data="myarea:manual")],
    ])


def regions_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура выбора региона из REGIONS."""
    buttons = [
        [InlineKeyboardButton(text=name, callback_data=f"region:{name}")]
        for name in REGIONS.keys()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def confidence_keyboard(region: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора уровня достоверности для заданного региона."""
    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"confidence:{region}:{key}"
        )]
        for key, label in CONFIDENCE_LABELS.items()
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)


def days_keyboard(region: str, confidence: str) -> InlineKeyboardMarkup:
    """Клавиатура выбора периода; недоступные варианты скрываются в зависимости от размера bbox."""
    all_options = [("24 часа", 1), ("2 дня", 2), ("7 дней", 7)]
    max_days = _max_days(region)
    options = [(label, days) for label, days in all_options if days <= max_days]
    buttons = [
        [InlineKeyboardButton(
            text=label,
            callback_data=f"fires:{region}:{confidence}:{days}"
        )]
        for label, days in options
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
