"""
Конфигурация бота — редактируйте только этот файл.
"""

# ──────────────────────────────────────────────
# Telegram
# ──────────────────────────────────────────────

# Токен от @BotFather
TELEGRAM_TOKEN = "8632422297:AAEcO9s9N1eGY_930hYeLl0B4vULAcACz4w"

# ID чата/канала куда слать уведомления.
# Для личного чата — ваш числовой ID (узнать через @userinfobot).
# Для группы — ID группы (отрицательное число, например -100xxxxxxxxx).
INITIAL_SUBSCRIBERS = [
    "2056194650",
    "1368322620",
]

# ──────────────────────────────────────────────
# Параметры мониторинга
# ──────────────────────────────────────────────

# Интервал между полными обходами всех сеансов (в секундах)
CHECK_INTERVAL = 60

# Таймаут одного HTTP-запроса (в секундах)
REQUEST_TIMEOUT = 15

# Случайная пауза между запросами к сайту — защита от блокировки
MIN_DELAY = 1.5   # минимум секунд
MAX_DELAY = 4.0   # максимум секунд

# ──────────────────────────────────────────────
# URL сеансов для мониторинга
# Добавляйте/удаляйте строки по необходимости
# ──────────────────────────────────────────────
SEANCE_URLS = [
    "https://krsk.kinoluch.ru/poster/seance/196991",
    "https://krsk.kinoluch.ru/poster/seance/196909",
    "https://krsk.kinoluch.ru/poster/seance/196913",
    "https://krsk.kinoluch.ru/poster/seance/196917",
    "https://krsk.kinoluch.ru/poster/seance/196921",
    "https://krsk.kinoluch.ru/poster/seance/196925",
    "https://krsk.kinoluch.ru/poster/seance/196908",
    "https://krsk.kinoluch.ru/poster/seance/196912",
    "https://krsk.kinoluch.ru/poster/seance/196916",
    "https://krsk.kinoluch.ru/poster/seance/196920",
    "https://krsk.kinoluch.ru/poster/seance/196924",
    "https://krsk.kinoluch.ru/poster/seance/196907",
    "https://krsk.kinoluch.ru/poster/seance/196911",
    "https://krsk.kinoluch.ru/poster/seance/196915",
    "https://krsk.kinoluch.ru/poster/seance/196919",
    "https://krsk.kinoluch.ru/poster/seance/196923",
    "https://krsk.kinoluch.ru/poster/seance/196906",
    "https://krsk.kinoluch.ru/poster/seance/196910",
    "https://krsk.kinoluch.ru/poster/seance/196914",
    "https://krsk.kinoluch.ru/poster/seance/196918",
    "https://krsk.kinoluch.ru/poster/seance/196922",
]
