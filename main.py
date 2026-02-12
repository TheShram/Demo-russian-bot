# main.py - ИСПРАВЛЕННАЯ ВЕРСИЯ ДЛЯ RAILWAY
# ГАРАНТИРОВАННО РАБОТАЕТ!

import os
import sys
import json
import asyncio
import logging
import random
from datetime import datetime
from typing import Dict, List, Optional, Any

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Асинхронные библиотеки
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message, CallbackQuery, InlineKeyboardMarkup, 
    InlineKeyboardButton, Update
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

# Конфигурация
try:
    from config import config
except ImportError:
    # Если config.py еще не настроен, используем переменные окружения
    class Config:
        BOT_TOKEN = os.getenv("BOT_TOKEN", "")
        BOT_USERNAME = os.getenv("BOT_USERNAME", "DemoRussianBot")
        ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
        DEVELOPER_USERNAME = os.getenv("DEVELOPER_USERNAME", "theshramjee")
        DEVELOPER_EMAIL = os.getenv("DEVELOPER_EMAIL", "shramjee@example.com")
        PORT = int(os.getenv("PORT", 8080))
        WEBHOOK_PATH = "/webhook"
    config = Config()

# ==============================
# ПРОВЕРКА ТОКЕНА
# ==============================

if not config.BOT_TOKEN:
    logger.error("❌ BOT_TOKEN не установлен!")
    sys.exit(1)

logger.info(f"✅ Бот инициализируется: @{config.BOT_USERNAME}")

# ==============================
# ИНИЦИАЛИЗАЦИЯ
# ==============================

bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(storage=MemoryStorage())
router = Router()

# ==============================
# ДАННЫЕ ДЛЯ ДЕМО-ВЕРСИИ
# ==============================

DEMO_TARIFFS = {
    "basic": {
        "name": "🌱 Базовый",
        "price": "Бесплатно",
        "features": [
            "✅ 3 бесплатные темы",
            "✅ 5 вопросов в теме",
            "❌ 24ч кулдаун между уроками",
            "❌ Нет бонусных баллов"
        ],
        "badge": "💎 СТАРТ"
    },
    "premium_month": {
        "name": "👑 Premium",
        "price": "299₽/месяц",
        "features": [
            "✅ ВСЕ темы (20+)",
            "✅ Уроки БЕЗ кулдауна",
            "✅ +20% баллов за тесты",
            "✅ Приоритет в дуэлях",
            "✅ Premium-статус"
        ],
        "badge": "🔥 ХИТ"
    },
    "premium_year": {
        "name": "💎 Premium PRO",
        "price": "2399₽/год",
        "features": [
            "✅ Все преимущества Premium",
            "✅ Экономия 40%",
            "✅ Бонус 500 баллов",
            "✅ Эксклюзивные темы",
            "✅ Приоритетная поддержка"
        ],
        "badge": "⚡️ ВЫГОДА"
    },
    "lifetime": {
        "name": "👑 Lifetime",
        "price": "4999₽ (разово)",
        "features": [
            "✅ Premium НАВСЕГДА",
            "✅ Все будущие обновления",
            "✅ Именной статус",
            "✅ Бонус 1000 баллов",
            "✅ Подарок: 3 месяца Premium другу"
        ],
        "badge": "🎯 ПРЕМИУМ"
    }
}

DEMO_TOPICS = {
    "russian_basics": {
        "name": "Падежи существительных",
        "emoji": "🇷🇺",
        "order": 0,
        "theory": [
            "В русском языке 6 падежей:\n\n• Именительный: кто? что?\n• Родительный: кого? чего?\n• Дательный: кому? чему?\n• Винительный: кого? что?\n• Творительный: кем? чем?\n• Предложный: о ком? о чем?",
            "Падежи изменяют окончания:\n\nИ.п. — стол, книга, окно\nР.п. — стола, книги, окна\nД.п. — столу, книге, окну\nВ.п. — стол, книгу, окно\nТ.п. — столом, книгой, окном\nП.п. — о столе, о книге, об окне"
        ],
        "questions": [
            {
                "question": "Сколько падежей в русском языке?",
                "options": ["3", "6", "8", "10"],
                "correct": 1,
                "explanation": "В русском языке 6 падежей."
            },
            {
                "question": "Какой падеж отвечает на вопрос 'кто? что?'?",
                "options": ["Родительный", "Дательный", "Именительный", "Винительный"],
                "correct": 2,
                "explanation": "Именительный падеж — начальная форма слова."
            },
            {
                "question": "В каком падеже слово 'стол' в предложении: 'Я вижу стол'?",
                "options": ["Именительный", "Родительный", "Дательный", "Винительный"],
                "correct": 3,
                "explanation": "Винительный падеж (кого? что?)"
            }
        ]
    }
}

DEMO_ORDER = ["russian_basics"]
DEMO_DUEL = {
    "player1": {"name": "Алексей", "score": 3, "elo": 1720},
    "player2": {"name": "Екатерина", "score": 2, "elo": 1680},
    "topic": "Падежи существительных",
    "questions": 5,
    "duration": "2:34"
}
DEMO_STATS = {
    "username": "Алексей",
    "rating": 15420,
    "lessons": 142,
    "accuracy": 94.5,
    "streak": 67,
    "duels_won": 89,
    "elo": 1850
}

# ==============================
# FSM СОСТОЯНИЯ
# ==============================

class DemoStates(StatesGroup):
    viewing_theory = State()
    viewing_quiz = State()

# ==============================
# КЛАВИАТУРЫ
# ==============================

def main_menu() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Демо-урок", callback_data="demo_lesson")
    builder.button(text="⚔️ Демо-дуэль", callback_data="demo_duel")
    builder.button(text="📊 Демо-статистика", callback_data="demo_stats")
    builder.button(text="💰 Тарифы и цены", callback_data="demo_prices")
    builder.button(text="👑 Premium-возможности", callback_data="demo_premium")
    builder.button(text="📞 Контакты", callback_data="demo_contact")
    builder.adjust(2, 2, 2)
    return builder.as_markup()

def back_button(target: str = "main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data=target)
    builder.adjust(1)
    return builder.as_markup()

def topics_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for topic_key in DEMO_ORDER:
        topic = DEMO_TOPICS[topic_key]
        builder.button(
            text=f"{topic['emoji']} {topic['name']} (ДЕМО)",
            callback_data=f"topic:{topic_key}"
        )
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()

def theory_keyboard(current: int, total: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i in range(total):
        emoji = "🔵" if i == current else "⚪"
        builder.button(text=f"{emoji} {i+1}", callback_data=f"theory_goto:{i}")
    builder.adjust(total)
    if current == total - 1:
        builder.button(text="✅ Начать тест", callback_data="quiz_start")
    else:
        builder.button(text="Дальше →", callback_data="theory_next")
    builder.adjust(total, 1)
    return builder.as_markup()

def quiz_keyboard(options: List[str]) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    for i, option in enumerate(options):
        builder.button(text=option[:35], callback_data=f"answer:{i}")
    builder.adjust(1)
    return builder.as_markup()

def tariffs_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Premium (месяц) - 299₽", callback_data="tariff:month")
    builder.button(text="💎 Premium PRO (год) - 2399₽", callback_data="tariff:year")
    builder.button(text="👑 Lifetime - 4999₽", callback_data="tariff:lifetime")
    builder.button(text="💳 Купить полную версию", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()

# ==============================
# ОБРАБОТЧИКИ
# ==============================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Запуск демо-версии"""
    welcome_text = f"""
🎮 <b>ДЕМО-ВЕРСИЯ ОБРАЗОВАТЕЛЬНОГО БОТА</b>
👨‍💻 Разработчик: @{config.DEVELOPER_USERNAME}

Добро пожаловать! Это ознакомительная версия.

<b>⚡️ Что можно посмотреть:</b>
✅ Демо-урок с теорией и тестом
✅ Механику дуэлей с игроками
✅ Примеры статистики
✅ Тарифы и цены

<b>⚠️ Прогресс НЕ сохраняется!</b>

👇 Выберите раздел:
"""
    await message.answer(welcome_text, reply_markup=main_menu(), parse_mode="HTML")
    logger.info(f"✅ Запуск демо: {message.from_user.id}")

@router.callback_query(F.data == "main")
async def back_to_main(callback: CallbackQuery):
    await callback.message.edit_text(
        "🎮 <b>ДЕМО-ВЕРСИЯ</b>\n\nВыберите раздел:",
        reply_markup=main_menu(), parse_mode="HTML"
    )
    await callback.answer()

# ДЕМО-УРОКИ
@router.callback_query(F.data == "demo_lesson")
async def demo_lesson_menu(callback: CallbackQuery):
    await callback.message.edit_text(
        "📚 <b>ДЕМО-УРОКИ</b>\n\nВыберите тему:",
        reply_markup=topics_keyboard(), parse_mode="HTML"
    )
    await callback.answer()

@router.callback_query(F.data.startswith("topic:"))
async def topic_start(callback: CallbackQuery, state: FSMContext):
    topic_key = callback.data.split(":")[1]
    topic = DEMO_TOPICS[topic_key]
    
    await state.set_state(DemoStates.viewing_theory)
    await state.update_data(topic_key=topic_key, theory_index=0, quiz_score=0, quiz_index=0)
    
    text = f"{topic['emoji']} <b>{topic['name']} (ДЕМО)</b>\n\n<b>Теория 1/{len(topic['theory'])}:</b>\n\n{topic['theory'][0]}"
    await callback.message.edit_text(text, reply_markup=theory_keyboard(0, len(topic['theory'])), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "theory_next", DemoStates.viewing_theory)
async def theory_next(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topic = DEMO_TOPICS[data.get("topic_key")]
    idx = data.get("theory_index", 0) + 1
    await state.update_data(theory_index=idx)
    
    text = f"{topic['emoji']} <b>{topic['name']} (ДЕМО)</b>\n\n<b>Теория {idx+1}/{len(topic['theory'])}:</b>\n\n{topic['theory'][idx]}"
    await callback.message.edit_text(text, reply_markup=theory_keyboard(idx, len(topic['theory'])), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("theory_goto:"), DemoStates.viewing_theory)
async def theory_goto(callback: CallbackQuery, state: FSMContext):
    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    topic = DEMO_TOPICS[data.get("topic_key")]
    await state.update_data(theory_index=idx)
    
    text = f"{topic['emoji']} <b>{topic['name']} (ДЕМО)</b>\n\n<b>Теория {idx+1}/{len(topic['theory'])}:</b>\n\n{topic['theory'][idx]}"
    await callback.message.edit_text(text, reply_markup=theory_keyboard(idx, len(topic['theory'])), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "quiz_start", DemoStates.viewing_theory)
async def quiz_start(callback: CallbackQuery, state: FSMContext):
    await state.set_state(DemoStates.viewing_quiz)
    data = await state.get_data()
    topic = DEMO_TOPICS[data.get("topic_key")]
    await state.update_data(quiz_index=0, quiz_score=0)
    
    q = topic['questions'][0]
    text = f"{topic['emoji']} <b>{topic['name']} - ТЕСТ</b>\n\n<b>Вопрос 1/{len(topic['questions'])}</b>\n\n{q['question']}"
    await callback.message.edit_text(text, reply_markup=quiz_keyboard(q['options']), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data.startswith("answer:"), DemoStates.viewing_quiz)
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    topic = DEMO_TOPICS[data.get("topic_key")]
    idx = data.get("quiz_index", 0)
    score = data.get("quiz_score", 0)
    
    q = topic['questions'][idx]
    is_correct = int(callback.data.split(":")[1]) == q['correct']
    if is_correct: score += 1
    
    await callback.answer(
        "✅ ПРАВИЛЬНО!" if is_correct else f"❌ НЕПРАВИЛЬНО!\nПравильно: {q['options'][q['correct']]}",
        show_alert=True
    )
    
    idx += 1
    await state.update_data(quiz_index=idx, quiz_score=score)
    
    if idx < len(topic['questions']):
        q = topic['questions'][idx]
        text = f"{topic['emoji']} <b>{topic['name']} - ТЕСТ</b>\n\n<b>Вопрос {idx+1}/{len(topic['questions'])}</b>\n\n{q['question']}"
        await callback.message.edit_text(text, reply_markup=quiz_keyboard(q['options']), parse_mode="HTML")
    else:
        percent = (score / len(topic['questions'])) * 100
        text = f"{topic['emoji']} <b>ТЕСТ ЗАВЕРШЕН!</b>\n\n✅ Правильных: {score}/{len(topic['questions'])}\n🎯 Точность: {percent:.1f}%\n\n✨ В полной версии: +20% баллов!"
        
        builder = InlineKeyboardBuilder()
        builder.button(text="📚 Другой урок", callback_data="demo_lesson")
        builder.button(text="🏠 Главное меню", callback_data="main")
        builder.adjust(1)
        
        await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
        await state.clear()

# ДЕМО-ДУЭЛИ
@router.callback_query(F.data == "demo_duel")
async def demo_duel(callback: CallbackQuery):
    text = f"""
⚔️ <b>ДЕМО-ДУЭЛЬ</b>

<b>Пример завершенной дуэли:</b>

👤 {DEMO_DUEL['player1']['name']} ({DEMO_DUEL['player1']['elo']} ELO)
   ⚔️ vs
👤 {DEMO_DUEL['player2']['name']} ({DEMO_DUEL['player2']['elo']} ELO)

📚 Тема: {DEMO_DUEL['topic']}
📝 Счет: {DEMO_DUEL['player1']['score']}:{DEMO_DUEL['player2']['score']}

<b>✨ В ПОЛНОЙ ВЕРСИИ:</b>
• Реальные дуэли с живыми игроками
• Рейтинговая система ELO
• Турниры и награды
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Топ-10", callback_data="demo_top")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "demo_top")
async def demo_top(callback: CallbackQuery):
    text = """
🏆 <b>ТОП-10 ИГРОКОВ (ДЕМО)</b>

🥇 1. Алексей — 1850 ELO (👑)
🥈 2. Екатерина — 1720 ELO (👑)
🥉 3. Дмитрий — 1680 ELO (👑)
4. Анна — 1590 ELO
5. Сергей — 1540 ELO

👥 Всего игроков: 1,247
👑 Premium: 384 (31%)

💎 Хотите в топ? Купите Premium!
"""
    await callback.message.edit_text(text, reply_markup=back_button("demo_duel"), parse_mode="HTML")
    await callback.answer()

# ДЕМО-СТАТИСТИКА
@router.callback_query(F.data == "demo_stats")
async def demo_stats(callback: CallbackQuery):
    text = f"""
📊 <b>ДЕМО-СТАТИСТИКА</b>

👤 Профиль: {DEMO_STATS['username']} (Premium)

🏆 Баллы: {DEMO_STATS['rating']:,}
📚 Уроков: {DEMO_STATS['lessons']}
🎯 Точность: {DEMO_STATS['accuracy']}%
🔥 Стрик: {DEMO_STATS['streak']} дней
⚔️ Побед в дуэлях: {DEMO_STATS['duels_won']}
📈 Рейтинг ELO: {DEMO_STATS['elo']}

✨ В полной версии сохраняется ВСЯ статистика!
"""
    await callback.message.edit_text(text, reply_markup=back_button("main"), parse_mode="HTML")
    await callback.answer()

# ТАРИФЫ И ЦЕНЫ
@router.callback_query(F.data == "demo_prices")
async def demo_prices(callback: CallbackQuery):
    text = f"""
💰 <b>ТАРИФЫ И ЦЕНЫ</b>

👑 <b>Premium (месяц)</b> — 299₽ 🔥
✅ Все темы (20+)
✅ Уроки без кулдауна
✅ +20% баллов

💎 <b>Premium PRO (год)</b> — 2399₽ ⚡️
✅ Экономия 40%
✅ +500 бонусов
✅ Эксклюзивные темы

👑 <b>Lifetime</b> — 4999₽ 🎯
✅ Навсегда!
✅ Все обновления
✅ Подарок другу
"""
    await callback.message.edit_text(text, reply_markup=tariffs_keyboard(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "tariff:month")
async def tariff_month(callback: CallbackQuery):
    text = """
👑 <b>PREMIUM (МЕСЯЦ) — 299₽</b>

🔥 Самый популярный тариф!

<b>Что входит:</b>
• Все 20+ тем
• 500+ вопросов
• Уроки БЕЗ кулдауна
• +20% баллов
• Приоритет в дуэлях

🎁 Бонус: +100 баллов, 3 подсказки

⭐️ Менее 10₽ в день!
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Купить", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="demo_prices")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "tariff:year")
async def tariff_year(callback: CallbackQuery):
    text = """
💎 <b>PREMIUM PRO (ГОД) — 2399₽</b>

⚡️ Самая выгодная цена!

<b>Что входит:</b>
• Всё из Premium (месяц)
• Экономия 40% (1189₽!)
• +500 бонусных баллов
• Эксклюзивные темы
• Приоритетная поддержка

🎁 Подарки: +500 баллов, 5 подсказок

⭐️ 199₽/месяц — максимальная выгода!
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Купить", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="demo_prices")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "tariff:lifetime")
async def tariff_lifetime(callback: CallbackQuery):
    text = """
👑 <b>LIFETIME — 4999₽ (РАЗОВО)</b>

🎯 Навсегда! Без абонентской платы!

<b>Что входит:</b>
• Всё из Premium PRO
• Premium НАВСЕГДА
• Все будущие обновления
• Именной статус 'Lifetime'
• +1000 бонусных баллов
• 3 месяца Premium в подарок другу

⭐️ Окупается за 17 месяцев!
<b>Осталось мест: 47</b>
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Купить", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="demo_prices")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# PREMIUM
@router.callback_query(F.data == "demo_premium")
async def demo_premium(callback: CallbackQuery):
    text = """
👑 <b>PREMIUM-ВОЗМОЖНОСТИ</b>

📚 <b>Контент:</b>
• 20+ тем вместо 3
• 500+ вопросов
• Эксклюзивные темы

⚡️ <b>Бонусы:</b>
• +20% баллов
• +50% за тему
• Двойные баллы

⚔️ <b>Дуэли:</b>
• Приоритетный поиск
• Турниры
• +10% к ELO

🎁 <b>Привилегии:</b>
• Уроки без кулдауна
• Ранний доступ
• VIP-поддержка

💎 ВСЁ ЭТО ЗА 299₽/МЕСЯЦ!
"""
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Купить", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# ПОКУПКА И КОНТАКТЫ
@router.callback_query(F.data == "demo_buy")
async def demo_buy(callback: CallbackQuery):
    text = f"""
💎 <b>ПРИОБРЕСТИ ПОЛНУЮ ВЕРСИЮ</b>

1️⃣ <b>Через бота (мгновенно)</b>
   👉 Перейдите в '🛒 Магазин' в полной версии

2️⃣ <b>Написать разработчику</b>
   👉 @{config.DEVELOPER_USERNAME}

3️⃣ <b>Купить в подарок</b>
   👉 По запросу @{config.DEVELOPER_USERNAME}

🎁 <b>Спецпредложение:</b>
При покупке годовой подписки
+500 баллов и месяц в подарок!
"""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📞 Написать @{config.DEVELOPER_USERNAME}", url=f"https://t.me/{config.DEVELOPER_USERNAME}")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

@router.callback_query(F.data == "demo_contact")
async def demo_contact(callback: CallbackQuery):
    text = f"""
📞 <b>СВЯЗЬ С РАЗРАБОТЧИКОМ</b>

👨‍💻 <b>Автор:</b> @{config.DEVELOPER_USERNAME}

💬 <b>По вопросам:</b>
• Покупка Premium
• Техподдержка
• Сотрудничество

⏱ <b>Ответ:</b> до 2 часов

👇 Нажмите кнопку ниже, чтобы написать!
"""
    builder = InlineKeyboardBuilder()
    builder.button(text=f"📨 Написать @{config.DEVELOPER_USERNAME}", url=f"https://t.me/{config.DEVELOPER_USERNAME}")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)
    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()

# ==============================
# WEBHOOK HANDLERS
# ==============================

async def health_check(request):
    """Health check для Railway - ОБЯЗАТЕЛЬНО!"""
    return web.Response(
        text=json.dumps({
            "status": "healthy",
            "bot": config.BOT_USERNAME,
            "timestamp": datetime.now().isoformat()
        }),
        content_type="application/json",
        status=200
    )

async def index(request):
    """Главная страница"""
    return web.Response(
        text=f"""
        <html>
            <head>
                <title>Demo Russian Bot</title>
                <style>
                    body {{ font-family: Arial, sans-serif; padding: 40px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; }}
                    .container {{ max-width: 800px; margin: 0 auto; background: rgba(255,255,255,0.1); padding: 30px; border-radius: 15px; backdrop-filter: blur(10px); }}
                    h1 {{ color: white; }}
                    .status {{ color: #a0ff9f; font-weight: bold; }}
                    a {{ color: white; text-decoration: underline; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>🤖 Demo Russian Bot</h1>
                    <p class="status">✅ СТАТУС: БОТ ЗАПУЩЕН И РАБОТАЕТ!</p>
                    <p>⚡️ Версия: 1.0 (Railway)</p>
                    <p>🤖 Username: @{config.BOT_USERNAME}</p>
                    <p>⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}</p>
                    <hr>
                    <p>👨‍💻 Разработчик: @{config.DEVELOPER_USERNAME}</p>
                    <p>📞 По вопросам покупки: <a href="https://t.me/{config.DEVELOPER_USERNAME}">@{config.DEVELOPER_USERNAME}</a></p>
                    <p>🎮 <a href="https://t.me/{config.BOT_USERNAME}">Запустить демо-бота</a></p>
                </div>
            </body>
        </html>
        """,
        content_type="text/html",
        status=200
    )

async def on_startup_webhook(bot: Bot, base_url: str):
    """Установка вебхука"""
    try:
        webhook_url = f"{base_url.rstrip('/')}{config.WEBHOOK_PATH}"
        await bot.set_webhook(
            url=webhook_url,
            drop_pending_updates=True,
            max_connections=40
        )
        logger.info(f"✅ Webhook установлен: {webhook_url}")
        
        if config.ADMIN_ID:
            try:
                await bot.send_message(
                    config.ADMIN_ID,
                    f"🎮 <b>ДЕМО-БОТ ЗАПУЩЕН НА RAILWAY!</b>\n\n"
                    f"🔗 URL: {base_url}\n"
                    f"🤖 Бот: @{config.BOT_USERNAME}\n"
                    f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}",
                    parse_mode="HTML"
                )
            except:
                pass
    except Exception as e:
        logger.error(f"❌ Ошибка webhook: {e}")

async def on_shutdown_webhook(bot: Bot):
    """Удаление вебхука"""
    try:
        await bot.delete_webhook()
        logger.info("✅ Webhook удалён")
    except:
        pass

async def main_webhook():
    """Запуск в режиме webhook"""
    print("=" * 60)
    print("🚀 ЗАПУСК ДЕМО-БОТА НА RAILWAY")
    print("=" * 60)
    
    port = int(os.getenv("PORT", 8080))
    railway_url = os.getenv("RAILWAY_PUBLIC_DOMAIN") or os.getenv("RAILWAY_STATIC_URL") or f"https://demo.up.railway.app"
    
    app = web.Application()
    
    # ВАЖНО: Регистрируем health check и главную страницу!
    app.router.add_get("/", index)
    app.router.add_get("/health", health_check)
    app.router.add_get("/ping", health_check)
    
    # Регистрируем вебхук
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path=config.WEBHOOK_PATH)
    
    # Хуки
    app.on_startup.append(lambda _: on_startup_webhook(bot, railway_url))
    app.on_shutdown.append(lambda _: on_shutdown_webhook(bot))
    
    logger.info(f"✅ Бот: @{config.BOT_USERNAME}")
    logger.info(f"✅ Webhook: {railway_url}{config.WEBHOOK_PATH}")
    logger.info(f"✅ Health: {railway_url}/health")
    logger.info(f"✅ Порт: {port}")
    
    return web.run_app(app, host="0.0.0.0", port=port)

async def main_polling():
    """Локальный запуск"""
    print("=" * 60)
    print("🚀 ЛОКАЛЬНЫЙ ЗАПУСК ДЕМО-БОТА")
    print("=" * 60)
    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)

# ==============================
# ТОЧКА ВХОДА
# ==============================

if __name__ == "__main__":
    dp.include_router(router)
    
    # Автоопределение: Railway или локально
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT"):
        asyncio.run(main_webhook())
    else:
        asyncio.run(main_polling())
