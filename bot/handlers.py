import logging
from aiogram import Router, F
from aiogram.enums import ContentType
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, CallbackQuery, KeyboardButton, ReplyKeyboardMarkup, ReplyKeyboardRemove

from aiogram.types import BufferedInputFile
from bot.keyboards import main_menu, regions_keyboard, confidence_keyboard, days_keyboard, my_area_keyboard
from bot.texts import (
    CMD_START, CMD_HELP,
    FIRES_SELECT_REGION, FIRES_SELECT_CONFIDENCE, FIRES_SELECT_DAYS,
    FIRES_LOADING, FIRES_ERROR, FIRES_NO_FIRES, FIRES_STATS_HEADER, FIRES_SOURCE,
    MY_AREA_START, MY_AREA_GEO_PROMPT, MY_AREA_GEO_BUTTON,
    MY_AREA_MANUAL_PROMPT, MY_AREA_INVALID_COORDS, MY_AREA_NO_FIRES,
    MY_AREA_FIRES_HEADER, STATS_SELECT_REGION,
)
from services.nasa_firms import fetch_fires, fetch_fires_bbox, get_stats
from services.map_render import render_fire_map

router = Router()
logger = logging.getLogger(__name__)


class MyAreaStates(StatesGroup):
    """FSM-состояния для ввода координат вручную."""

    waiting_for_coords = State()


@router.message(CommandStart())
async def cmd_start(message: Message):
    """Приветственное сообщение и главное меню."""
    await message.answer(CMD_START, parse_mode="HTML", reply_markup=main_menu())


@router.message(F.text == "ℹ️ Помощь")
@router.message(Command("help"))
async def cmd_help(message: Message):
    """Справка по командам бота."""
    await message.answer(CMD_HELP, parse_mode="HTML")


@router.message(F.text == "🔥 Пожары по региону")
async def fires_start(message: Message):
    """Начало сценария просмотра пожаров по региону."""
    await message.answer(FIRES_SELECT_REGION, reply_markup=regions_keyboard())


@router.callback_query(F.data.startswith("region:"))
async def fires_select_confidence(callback: CallbackQuery):
    """Шаг 2: выбор уровня достоверности после выбора региона."""
    await callback.answer()
    region = callback.data.split(":")[1]
    await callback.message.edit_text(
        FIRES_SELECT_CONFIDENCE.format(region=region),
        parse_mode="HTML",
        reply_markup=confidence_keyboard(region),
    )


@router.callback_query(F.data.startswith("confidence:"))
async def fires_select_days(callback: CallbackQuery):
    """Шаг 3: выбор периода после выбора достоверности."""
    await callback.answer()
    _, region, confidence = callback.data.split(":")
    await callback.message.edit_text(
        FIRES_SELECT_DAYS.format(region=region),
        parse_mode="HTML",
        reply_markup=days_keyboard(region, confidence),
    )


@router.callback_query(F.data.startswith("fires:"))
async def fires_show(callback: CallbackQuery):
    """Получает данные NASA FIRMS и отправляет карту с пожарами."""
    await callback.answer()
    _, region, confidence, days_str = callback.data.split(":")
    days = int(days_str)

    await callback.message.edit_text(FIRES_LOADING)

    try:
        fires = await fetch_fires(region, days=days, min_confidence=confidence)
    except Exception as e:
        logger.error(f"NASA API error: {e}")
        await callback.message.edit_text(FIRES_ERROR)
        return

    if not fires:
        await callback.message.edit_text(
            FIRES_NO_FIRES.format(region=region, days=days, confidence=confidence),
            parse_mode="HTML",
        )
        return

    stats = get_stats(fires)
    top_fires = fires[:5]

    text = FIRES_STATS_HEADER.format(
        region=region, days=days,
        total=stats['total'], high=stats['high'],
        nominal=stats['nominal'], low=stats['low'],
        avg_frp=stats['avg_frp'], max_frp=stats['max_frp'],
    )
    for i, fire in enumerate(top_fires, 1):
        text += f"\n<b>#{i}</b>\n{fire}\n"
    text += FIRES_SOURCE

    map_buf = None
    try:
        map_buf = render_fire_map(fires)
    except Exception:
        pass

    if map_buf:
        await callback.message.delete()
        await callback.message.answer_photo(
            BufferedInputFile(map_buf.read(), filename="fires.png"),
            caption=text,
            parse_mode="HTML",
        )
    else:
        await callback.message.edit_text(text, parse_mode="HTML")



@router.message(F.text == "📍 Мой район")
async def my_area_start(message: Message):
    """Начало сценария поиска пожаров вблизи пользователя."""
    await message.answer(MY_AREA_START, parse_mode="HTML", reply_markup=my_area_keyboard())


@router.callback_query(F.data == "myarea:geo")
async def my_area_request_geo(callback: CallbackQuery):
    """Запрашивает геолокацию через кнопку Telegram."""
    await callback.answer()
    geo_keyboard = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📍 Отправить геолокацию", request_location=True)]],
        resize_keyboard=True,
        one_time_keyboard=True,
    )
    await callback.message.edit_text(MY_AREA_GEO_PROMPT)
    await callback.message.answer(MY_AREA_GEO_BUTTON, reply_markup=geo_keyboard)


@router.callback_query(F.data == "myarea:manual")
async def my_area_request_manual(callback: CallbackQuery, state: FSMContext):
    """Переводит пользователя в FSM-состояние ожидания координат."""
    await callback.answer()
    await state.set_state(MyAreaStates.waiting_for_coords)
    await callback.message.delete()
    await callback.message.answer(MY_AREA_MANUAL_PROMPT, parse_mode="HTML", reply_markup=ReplyKeyboardRemove())


@router.message(MyAreaStates.waiting_for_coords)
async def my_area_handle_text(message: Message, state: FSMContext):
    """Разбирает введённые вручную координаты (широта долгота)."""
    await state.clear()
    try:
        parts = message.text.replace(",", " ").split()
        lat, lon = float(parts[0]), float(parts[1])
        if not (-90 <= lat <= 90 and -180 <= lon <= 180):
            raise ValueError
    except (ValueError, IndexError):
        await message.answer(MY_AREA_INVALID_COORDS, parse_mode="HTML")
        return

    await _fetch_and_send_area(message, lat, lon)


@router.message(F.content_type == ContentType.LOCATION)
async def my_area_handle_geo(message: Message):
    """Обрабатывает геолокацию, переданную через Telegram."""
    lat = message.location.latitude
    lon = message.location.longitude
    await _fetch_and_send_area(message, lat, lon)


async def _fetch_and_send_area(message: Message, lat: float, lon: float):
    """Строит bbox вокруг точки, запрашивает пожары и отправляет результат."""
    radius = 2.0
    bbox = (
        round(lon - radius, 4),
        round(lat - radius, 4),
        round(lon + radius, 4),
        round(lat + radius, 4),
    )

    await message.answer(FIRES_LOADING, reply_markup=main_menu())

    try:
        fires = await fetch_fires_bbox(bbox, days=1)
    except Exception as e:
        logger.error(f"NASA API error (my area): {e}")
        await message.answer(FIRES_ERROR)
        return

    if not fires:
        await message.answer(MY_AREA_NO_FIRES.format(lat=f"{lat:.4f}", lon=f"{lon:.4f}"))
        return

    stats = get_stats(fires)
    top_fires = fires[:5]

    text = MY_AREA_FIRES_HEADER.format(
        lat=f"{lat:.4f}", lon=f"{lon:.4f}",
        total=stats['total'], high=stats['high'],
        nominal=stats['nominal'], low=stats['low'],
        avg_frp=stats['avg_frp'], max_frp=stats['max_frp'],
    )
    for i, fire in enumerate(top_fires, 1):
        text += f"\n<b>#{i}</b>\n{fire}\n"
    text += FIRES_SOURCE

    try:
        map_buf = render_fire_map(fires)
        await message.answer_photo(
            BufferedInputFile(map_buf.read(), filename="fires.png"),
            caption=text,
            parse_mode="HTML",
        )
    except Exception:
        await message.answer(text, parse_mode="HTML")



@router.message(F.text == "📊 Статистика")
async def stats_start(message: Message):
    """Начало сценария просмотра статистики по региону."""
    await message.answer(STATS_SELECT_REGION, reply_markup=regions_keyboard())
