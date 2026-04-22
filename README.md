# 🔥 Fire Monitor Bot
Telegram-бот для мониторинга активных пожаров по данным NASA FIRMS (спутник VIIRS).

## Возможности
- Получение пожаров по регионам мира
- Фильтрация по уровню уверенности (low / nominal / high)
- Топ-5 очагов по мощности (FRP)
- Базовая статистика

## Быстрый старт

### 1. Клонируй и установи зависимости
```
git clone 
cd fire-monitor-bot
pip install -r requirements.txt
```

### 2. Настрой переменные окружения
```
.env.example
```
Получить NASA API ключ: https://firms.modaps.eosdis.nasa.gov/api/

### 3. Запустить бота
```
python main.py
```
