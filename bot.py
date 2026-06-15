import asyncio
import logging
import random
import re
from dataclasses import dataclass
from datetime import datetime
import pytz
from typing import Optional, Set

import aiohttp
from bs4 import BeautifulSoup
from telegram import Bot, Update, BotCommand
from telegram.constants import ParseMode
from telegram.error import TelegramError
from telegram.ext import Application, CommandHandler, ContextTypes

from config import (
    TELEGRAM_TOKEN,
    INITIAL_SUBSCRIBERS,
    CHECK_INTERVAL,
    SEANCE_URLS,
    REQUEST_TIMEOUT,
    MIN_DELAY,
    MAX_DELAY,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("bot.log", encoding="utf-8"),
    ],
)
logger = logging.getLogger("kinoluch_bot")

active_subscribers: Set[str] = set(INITIAL_SUBSCRIBERS)

@dataclass
class SeanceInfo:
    url: str
    movie_title: str = ""
    seance_datetime: str = ""
    hall: str = ""
    available: bool = False
    last_status: Optional[bool] = None   # None = ещё не проверяли
    last_checked: Optional[datetime] = None  # Время последней проверки запросом

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
]

BASE_HEADERS = {
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection": "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Referer": "https://krsk.kinoluch.ru/poster",
}

def parse_seance_page(html: str, url: str) -> SeanceInfo:
    """Извлекает информацию о сеансе и проверяет доступность билетов."""
    soup = BeautifulSoup(html, "lxml")
    info = SeanceInfo(url=url)

    # Название фильма
    film_link = soup.select_one("div.movie-title a.sub-title")
    if film_link:
        info.movie_title = film_link.get_text(strip=True)

    # Дата/время и зал
    for p in soup.select("p.title"):
        text = p.get_text(strip=True)
        sibling = p.find_next_sibling("p", class_="sub-title")
        if not sibling:
            continue
        if "Дата" in text and not info.seance_datetime:
            info.seance_datetime = sibling.get_text(strip=True)
        elif "Зал" in text and not info.hall:
            info.hall = sibling.get_text(strip=True)

    # Доступность: hall-scheme есть и нет error-no-places
    has_hall_scheme = bool(soup.find(class_=re.compile(r"\bhall-scheme\b")))
    has_no_places   = bool(soup.find(class_=re.compile(r"\berror-no-places\b")))
    info.available  = has_hall_scheme and not has_no_places

    return info

async def fetch_page(session: aiohttp.ClientSession, url: str) -> Optional[str]:
    headers = {**BASE_HEADERS, "User-Agent": random.choice(USER_AGENTS)}
    try:
        async with session.get(
            url,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
            allow_redirects=True,
        ) as resp:
            if resp.status == 200:
                return await resp.text(encoding="utf-8", errors="replace")
            logger.warning("HTTP %s при запросе %s", resp.status, url)
    except asyncio.TimeoutError:
        logger.warning("Таймаут: %s", url)
    except aiohttp.ClientError as e:
        logger.warning("Сетевая ошибка %s: %s", url, e)
    return None

NOTIFY_TEMPLATE = (
    "🎟 *Билеты открыты\\!*\n\n"
    "🎬 *Фильм:* {title}\n"
    "🕐 *Дата и время:* {dt}\n"
    "🎭 *Зал:* {hall}\n"
    "🔗 [Купить билет]({url})"
)

def _escape(text: str) -> str:
    """Экранирует спецсимволы для MarkdownV2."""
    for ch in r"\_*[]()~`>#+-=|{}.!":
        text = text.replace(ch, f"\\{ch}")
    return text


async def send_notification(bot: Bot, info: SeanceInfo) -> None:
    """Отправляет индивидуальное уведомление активным подписчикам."""
    if not active_subscribers:
        return

    text = NOTIFY_TEMPLATE.format(
        title=_escape(info.movie_title or "Неизвестный фильм"),
        dt=_escape(info.seance_datetime or "—"),
        hall=_escape(info.hall or "—"),
        url=info.url,
    )
    for chat_id in list(active_subscribers):
        try:
            await bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=ParseMode.MARKDOWN_V2,
                disable_web_page_preview=False,
            )
            logger.info("Уведомление отправлено пользователю %s: %s", chat_id, info.url)
        except TelegramError as e:
            logger.error("Ошибка отправки уведомления пользователю %s: %s", chat_id, e)

async def check_all_seances(
    session: aiohttp.ClientSession,
    bot: Bot,
    seances: list[SeanceInfo],
) -> None:
    """Последовательно проверяет сеансы и отправляет уведомления сразу при обнаружении доступности."""
    for seance in seances:
        await asyncio.sleep(random.uniform(MIN_DELAY, MAX_DELAY))

        html = await fetch_page(session, seance.url)
        
        tz_krsk = pytz.timezone('Asia/Krasnoyarsk')
        seance.last_checked = datetime.now(tz_krsk)

        if html is None:
            continue

        updated = parse_seance_page(html, seance.url)

        if not seance.movie_title and updated.movie_title:
            seance.movie_title   = updated.movie_title
            seance.seance_datetime = updated.seance_datetime
            seance.hall          = updated.hall

        seance.last_status = updated.available
        seance.available   = updated.available

        status_str = "✅ ДОСТУПЕН" if updated.available else "❌ недоступен"
        logger.info(
            "[%s] %s — %s",
            status_str,
            seance.movie_title or seance.url,
            seance.seance_datetime,
        )

        if updated.available:
            await send_notification(bot, seance)


async def _background_monitor(bot: Bot, seances: list[SeanceInfo]) -> None:
    connector = aiohttp.TCPConnector(ssl=False, limit=5)
    async with aiohttp.ClientSession(connector=connector) as session:
        while True:
            try:
                await check_all_seances(session, bot, seances)
            except Exception as e:
                logger.exception("Ошибка в цикле мониторинга: %s", e)
            
            logger.info("Все сеансы проверены. Следующий запуск очереди через %d сек.", CHECK_INTERVAL)
            await asyncio.sleep(CHECK_INTERVAL)

HELP_TEXT = (
    "/on — 🔔 включить уведомления для текущего чата\n"
    "/off — 🔕 отключить уведомления для текущего чата\n"
    "/status — 📋 текущий статус всех сеансов\n"
    "/start"
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text(HELP_TEXT, parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_on(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global active_subscribers
    chat_id = str(update.effective_chat.id)
    
    active_subscribers.add(chat_id)
    logger.info("Уведомления ВКЛЮЧЕНЫ для чата %s (инициатор: %s)", chat_id, update.effective_user.id)
    await update.message.reply_text("🔔 Уведомления *включены* для этого чата\\. Буду присылать сообщения сразу при обнаружении доступных мест\\.", parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_off(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    global active_subscribers
    chat_id = str(update.effective_chat.id)
    
    if chat_id in active_subscribers:
        active_subscribers.remove(chat_id)
        
    logger.info("Уведомления ОТКЛЮЧЕНЫ для чата %s (инициатор: %s)", chat_id, update.effective_user.id)
    await update.message.reply_text("🔕 Уведомления *отключены* для этого чата\\. Мониторинг продолжается в фоне, но вы получать сообщения не будете\\.", parse_mode=ParseMode.MARKDOWN_V2)


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat_id = str(update.effective_chat.id)
    is_enabled = chat_id in active_subscribers
    
    state = "🔔 включены" if is_enabled else "🔕 отключены"
    lines = [f"*Уведомления для этого чата:* {_escape(state)}\n"]

    seances: list[SeanceInfo] = context.bot_data.get("seances", [])

    if not seances:
        lines.append("_Мониторинг ещё не запускался или список пуст\\._")
    else:
        lines.append("*Сеансы:*")
        for s in seances:
            icon = "✅" if s.available else ("❓" if s.last_status is None else "❌")
            title = _escape(s.movie_title or s.url)
            dt    = _escape(s.seance_datetime or "—")
            
            if s.last_checked:
                time_str = _escape(s.last_checked.strftime("%H:%M:%S"))
                lines.append(f"{icon} {title} — {dt} _\\(проверен в {time_str}\\)_")
            else:
                lines.append(f"{icon} {title} — {dt} _\\(еще не проверялся\\)_")

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode=ParseMode.MARKDOWN_V2,
        disable_web_page_preview=True,
    )

async def post_init(application: Application) -> None:
    """Выполняет настройку меню команд и запускает фоновый мониторинг."""
    commands = [
        BotCommand("start", "Главное меню и справка по работе бота"),
        BotCommand("on", "Включить мгновенные уведомления о билетах для текущего чата"),
        BotCommand("off", "Отключить уведомления (мониторинг в тихом режиме)"),
        BotCommand("status", "Показать текущий статус доступности билетов по всем сеансам")
    ]
    await application.bot.set_my_commands(commands)
    logger.info("Список команд успешно зарегистрирован в меню Telegram.")

    seances = [SeanceInfo(url=url) for url in SEANCE_URLS]
    application.bot_data["seances"] = seances
    asyncio.create_task(_background_monitor(application.bot, seances))

def main() -> None:
    app = (
        Application.builder()
        .token(TELEGRAM_TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("on",     cmd_on))
    app.add_handler(CommandHandler("off",    cmd_off))
    app.add_handler(CommandHandler("status", cmd_status))

    logger.info("Бот запускается...")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()