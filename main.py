# main.py - ДЕМО-ВЕРСИЯ ОБРАЗОВАТЕЛЬНОГО БОТА ДЛЯ RAILWAY
# ПОЛНОСТЬЮ ОПТИМИЗИРОВАНО ДЛЯ WEBHOOKS

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
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("bot.log", encoding="utf-8")
    ]
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
from config import config

# ==============================
# ИНИЦИАЛИЗАЦИЯ
# ==============================

# Создаем роутер
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
            "❌ Нет бонусных баллов",
            "❌ Нет Premium-тем"
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
            "✅ Premium-статус",
            "✅ Новые темы каждую неделю"
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
            "✅ Приоритетная поддержка",
            "✅ Участие в турнирах"
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
            "✅ Подарок: 3 месяца Premium другу",
            "✅ Доступ к бета-версиям"
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
            "📚 <b>Падежи в русском языке</b>\n\n"
            "В русском языке 6 падежей. Каждый падеж отвечает на свои вопросы:\n\n"
            "• Именительный: кто? что?\n"
            "• Родительный: кого? чего?\n"
            "• Дательный: кому? чему?\n"
            "• Винительный: кого? что?\n"
            "• Творительный: кем? чем?\n"
            "• Предложный: о ком? о чем?",

            "📝 <b>Изменение окончаний</b>\n\n"
            "Падежи изменяют окончания существительных:\n\n"
            "И.п. — стол, книга, окно\n"
            "Р.п. — стола, книги, окна\n"
            "Д.п. — столу, книге, окну\n"
            "В.п. — стол, книгу, окно\n"
            "Т.п. — столом, книгой, окном\n"
            "П.п. — о столе, о книге, об окне"
        ],
        "questions": [
            {
                "question": "Сколько падежей в русском языке?",
                "options": ["3", "6", "8", "10"],
                "correct": 1,
                "explanation": "В русском языке 6 падежей: именительный, родительный, дательный, винительный, творительный, предложный."
            },
            {
                "question": "Какой падеж отвечает на вопрос 'кто? что?'?",
                "options": ["Родительный", "Дательный", "Именительный", "Винительный"],
                "correct": 2,
                "explanation": "Именительный падеж — это начальная форма слова, отвечает на вопросы кто? что?"
            },
            {
                "question": "В каком падеже слово 'стол' в предложении: 'Я вижу стол'?",
                "options": ["Именительный", "Родительный", "Дательный", "Винительный"],
                "correct": 3,
                "explanation": "Винительный падеж (кого? что?) — 'вижу (что?) стол'"
            }
        ]
    },
    "demo_cases": {
        "name": "Глаголы и спряжения",
        "emoji": "📝",
        "order": 1,
        "theory": [
            "⚡️ <b>Спряжение глаголов</b>\n\n"
            "Глаголы в русском языке изменяются по лицам и числам — это называется спряжением.\n\n"
            "• <b>I спряжение:</b> глаголы на -ать, -ять, -еть\n"
            "• <b>II спряжение:</b> глаголы на -ить и 11 исключений",

            "🔤 <b>Личные окончания</b>\n\n"
            "<b>I спряжение:</b>\n"
            "Я -у/-ю\n"
            "Ты -ешь\n"
            "Он -ет\n"
            "Мы -ем\n"
            "Вы -ете\n"
            "Они -ут/-ют\n\n"
            "<b>II спряжение:</b>\n"
            "Я -у/-ю\n"
            "Ты -ишь\n"
            "Он -ит\n"
            "Мы -им\n"
            "Вы -ите\n"
            "Они -ат/-ят"
        ],
        "questions": [
            {
                "question": "К какому спряжению относится глагол 'говорить'?",
                "options": ["I спряжение", "II спряжение", "Разноспрягаемый", "Не определяется"],
                "correct": 1,
                "explanation": "Глагол 'говорить' оканчивается на -ить, относится ко II спряжению."
            },
            {
                "question": "Какое окончание у глагола I спряжения в форме 'они'?",
                "options": ["-ат/-ят", "-ут/-ют", "-ит", "-ет"],
                "correct": 1,
                "explanation": "У глаголов I спряжения в 3 лице множественного числа окончания -ут/-ют."
            }
        ]
    }
}

DEMO_ORDER = ["russian_basics", "demo_cases"]

DEMO_DUEL = {
    "player1": {"name": "Алексей", "score": 3, "elo": 1720, "rank": "👑 Гроссмейстер"},
    "player2": {"name": "Екатерина", "score": 2, "elo": 1680, "rank": "💎 Мастер"},
    "topic": "Падежи существительных",
    "questions": 5,
    "duration": "2:34",
    "rating_change_winner": "+12 ELO",
    "rating_change_loser": "-8 ELO",
    "reward": "+10 баллов"
}

DEMO_STATS = {
    "username": "Алексей",
    "rating": 15420,
    "lessons": 142,
    "accuracy": 94.5,
    "streak": 67,
    "duels_won": 89,
    "duels_total": 124,
    "elo": 1850,
    "rank": "👑 Гроссмейстер",
    "topics_completed": 15,
    "topics_total": 25,
    "achievements": 12
}

DEMO_TIPS = [
    "🎯 Регулярные занятия по 15 минут эффективнее, чем 2 часа раз в неделю",
    "📝 Записывайте новые слова в блокнот — это улучшает запоминание",
    "🗣 Читайте вслух — это развивает речь и дикцию",
    "💪 Не бойтесь ошибаться! На ошибках учатся",
    "🔄 Повторяйте пройденное через день, неделю и месяц",
    "🎮 Используйте дуэли для проверки знаний в игровой форме",
    "🎯 В русском языке 6 падежей, но чаще всего используются именительный и винительный",
    "📚 Читайте книги с субтитрами — это улучшает восприятие на слух"
]


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
    """Главное меню демо-версии"""
    builder = InlineKeyboardBuilder()

    # Основные разделы
    builder.button(text="📚 Демо-урок", callback_data="demo_lesson")
    builder.button(text="⚔️ Демо-дуэль", callback_data="demo_duel")
    builder.button(text="📊 Демо-статистика", callback_data="demo_stats")

    # Premium и тарифы
    builder.button(text="💰 Тарифы и цены", callback_data="demo_prices")
    builder.button(text="👑 Premium-возможности", callback_data="demo_premium")

    # Дополнительно
    builder.button(text="🏆 Топ-10 игроков", callback_data="demo_top")
    builder.button(text="ℹ️ О полной версии", callback_data="demo_about")

    # Контакты
    builder.button(text="📞 Связаться с разработчиком", callback_data="demo_contact")

    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def back_button(target: str = "main") -> InlineKeyboardMarkup:
    """Универсальная кнопка назад"""
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data=target)
    builder.adjust(1)
    return builder.as_markup()


def topics_keyboard() -> InlineKeyboardMarkup:
    """Список демо-тем"""
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
    """Навигация по теории"""
    builder = InlineKeyboardBuilder()

    # Кнопки страниц
    for i in range(total):
        emoji = "🔵" if i == current else "⚪"
        builder.button(text=f"{emoji} {i + 1}", callback_data=f"theory_goto:{i}")

    builder.adjust(total)

    # Кнопка перехода к тесту
    if current == total - 1:
        builder.button(text="✅ Начать тест", callback_data="quiz_start")
    else:
        builder.button(text="Дальше →", callback_data="theory_next")

    builder.adjust(total, 1)
    return builder.as_markup()


def quiz_keyboard(options: List[str]) -> InlineKeyboardMarkup:
    """Варианты ответов"""
    builder = InlineKeyboardBuilder()

    for i, option in enumerate(options):
        # Обрезаем длинные варианты
        text = option[:35] + "..." if len(option) > 35 else option
        builder.button(text=text, callback_data=f"answer:{i}")

    builder.adjust(1)
    return builder.as_markup()


def tariffs_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура тарифов"""
    builder = InlineKeyboardBuilder()

    builder.button(text="👑 Premium (месяц) - 299₽", callback_data="tariff:month")
    builder.button(text="💎 Premium PRO (год) - 2399₽", callback_data="tariff:year")
    builder.button(text="👑 Lifetime - 4999₽", callback_data="tariff:lifetime")
    builder.button(text="📋 Сравнить все тарифы", callback_data="tariff:compare")
    builder.button(text="❓ Часто задаваемые вопросы", callback_data="demo_faq")
    builder.button(text="💳 Купить полную версию", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="main")

    builder.adjust(1)
    return builder.as_markup()


def after_quiz_keyboard() -> InlineKeyboardMarkup:
    """Клавиатура после теста"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Другой урок", callback_data="demo_lesson")
    builder.button(text="🏠 Главное меню", callback_data="main")
    builder.adjust(1)
    return builder.as_markup()


# ==============================
# ОБРАБОТЧИКИ КОМАНД
# ==============================

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Запуск демо-версии"""

    welcome_text = f"""
🎮 <b>ДЕМО-ВЕРСИЯ ОБРАЗОВАТЕЛЬНОГО БОТА</b>
👨‍💻 Разработчик: @{config.DEVELOPER_USERNAME}

━━━━━━━━━━━━━━━━━━━━━
📚 <b>ИЗУЧЕНИЕ РУССКОГО ЯЗЫКА В ИГРОВОЙ ФОРМЕ</b>
━━━━━━━━━━━━━━━━━━━━━

<b>⚡️ ЧТО МОЖНО ПОСМОТРЕТЬ:</b>
✅ • Демо-урок с теорией и тестом
✅ • Механику дуэлей с игроками
✅ • Примеры статистики и достижений
✅ • Все тарифы и цены полной версии
✅ • Premium-возможности и бонусы

<b>⚠️ ВАЖНО:</b>
• Прогресс НЕ сохраняется
• Это только презентация функционала
• Полная версия продаётся отдельно

━━━━━━━━━━━━━━━━━━━━━
👇 <b>Выберите раздел для просмотра:</b>
"""

    await message.answer(
        welcome_text,
        reply_markup=main_menu(),
        parse_mode="HTML"
    )

    # Логируем запуск
    logger.info(f"Демо-бот запущен пользователем {message.from_user.id}")


@router.callback_query(F.data == "main")
async def back_to_main(callback: CallbackQuery):
    """Возврат в главное меню"""
    await callback.message.edit_text(
        "🎮 <b>ДЕМО-ВЕРСИЯ</b>\n\nВыберите раздел для просмотра:",
        reply_markup=main_menu(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# ДЕМО-УРОКИ
# ==============================

@router.callback_query(F.data == "demo_lesson")
async def demo_lesson_menu(callback: CallbackQuery):
    """Меню выбора темы"""

    text = """
📚 <b>ДЕМО-УРОКИ</b>

━━━━━━━━━━━━━━━━━━━━━
<b>В ПОЛНОЙ ВЕРСИИ:</b>
• 20+ тем по русскому языку
• 500+ вопросов с объяснениями
• Подробная теория по каждой теме
• Еженедельные обновления

<b>В ДЕМО-ВЕРСИИ:</b>
Вы можете ознакомиться с двумя темами:
━━━━━━━━━━━━━━━━━━━━━

🇷🇺 <b>Падежи существительных</b>
📝 <b>Глаголы и спряжения</b>

Выберите тему для просмотра:
"""

    await callback.message.edit_text(
        text,
        reply_markup=topics_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("topic:"))
async def topic_start(callback: CallbackQuery, state: FSMContext):
    """Начало демо-урока"""

    topic_key = callback.data.split(":")[1]

    if topic_key not in DEMO_TOPICS:
        await callback.answer("❌ Тема не найдена", show_alert=True)
        return

    topic = DEMO_TOPICS[topic_key]

    await state.set_state(DemoStates.viewing_theory)
    await state.update_data(
        topic_key=topic_key,
        theory_index=0,
        quiz_score=0,
        quiz_index=0
    )

    theory = topic['theory'][0]
    total = len(topic['theory'])

    text = f"""
{topic['emoji']} <b>{topic['name']} (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>ТЕОРИЯ (1/{total}):</b>
━━━━━━━━━━━━━━━━━━━━━

{theory}

━━━━━━━━━━━━━━━━━━━━━
<i>В полной версии: подробная теория с примерами</i>
"""

    await callback.message.edit_text(
        text,
        reply_markup=theory_keyboard(0, total),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "theory_next", DemoStates.viewing_theory)
async def theory_next(callback: CallbackQuery, state: FSMContext):
    """Следующая страница теории"""

    data = await state.get_data()
    topic_key = data.get("topic_key")
    current_idx = data.get("theory_index", 0)

    topic = DEMO_TOPICS[topic_key]
    theory_parts = topic['theory']

    next_idx = current_idx + 1
    if next_idx >= len(theory_parts):
        next_idx = len(theory_parts) - 1

    await state.update_data(theory_index=next_idx)

    text = f"""
{topic['emoji']} <b>{topic['name']} (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>ТЕОРИЯ ({next_idx + 1}/{len(theory_parts)}):</b>
━━━━━━━━━━━━━━━━━━━━━

{theory_parts[next_idx]}
"""

    await callback.message.edit_text(
        text,
        reply_markup=theory_keyboard(next_idx, len(theory_parts)),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("theory_goto:"), DemoStates.viewing_theory)
async def theory_goto(callback: CallbackQuery, state: FSMContext):
    """Переход на страницу теории"""

    idx = int(callback.data.split(":")[1])
    data = await state.get_data()
    topic_key = data.get("topic_key")

    topic = DEMO_TOPICS[topic_key]
    theory_parts = topic['theory']

    await state.update_data(theory_index=idx)

    text = f"""
{topic['emoji']} <b>{topic['name']} (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>ТЕОРИЯ ({idx + 1}/{len(theory_parts)}):</b>
━━━━━━━━━━━━━━━━━━━━━

{theory_parts[idx]}
"""

    await callback.message.edit_text(
        text,
        reply_markup=theory_keyboard(idx, len(theory_parts)),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "quiz_start", DemoStates.viewing_theory)
async def quiz_start(callback: CallbackQuery, state: FSMContext):
    """Начало теста"""

    await state.set_state(DemoStates.viewing_quiz)
    data = await state.get_data()
    topic_key = data.get("topic_key")

    topic = DEMO_TOPICS[topic_key]
    questions = topic['questions']

    await state.update_data(quiz_index=0, quiz_score=0)

    question = questions[0]

    text = f"""
{topic['emoji']} <b>{topic['name']} - ТЕСТ (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>ВОПРОС 1/{len(questions)}</b>
━━━━━━━━━━━━━━━━━━━━━

❓ {question['question']}

━━━━━━━━━━━━━━━━━━━━━
<i>В полной версии: 15+ вопросов по каждой теме</i>
"""

    await callback.message.edit_text(
        text,
        reply_markup=quiz_keyboard(question['options']),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data.startswith("answer:"), DemoStates.viewing_quiz)
async def handle_answer(callback: CallbackQuery, state: FSMContext):
    """Обработка ответа"""

    answer_idx = int(callback.data.split(":")[1])
    data = await state.get_data()

    topic_key = data.get("topic_key")
    quiz_index = data.get("quiz_index", 0)
    quiz_score = data.get("quiz_score", 0)

    topic = DEMO_TOPICS[topic_key]
    questions = topic['questions']

    if quiz_index >= len(questions):
        await callback.answer("❌ Тест уже завершен", show_alert=True)
        return

    question = questions[quiz_index]
    is_correct = answer_idx == question['correct']

    if is_correct:
        quiz_score += 1

    # Показываем результат
    if is_correct:
        result_text = f"✅ ПРАВИЛЬНО!\n{question['explanation']}"
    else:
        correct_answer = question['options'][question['correct']]
        result_text = f"❌ НЕПРАВИЛЬНО!\nПравильный ответ: {correct_answer}\n{question['explanation']}"

    await callback.answer(result_text, show_alert=True)

    # Переходим к следующему вопросу
    quiz_index += 1
    await state.update_data(quiz_index=quiz_index, quiz_score=quiz_score)

    if quiz_index < len(questions):
        # Следующий вопрос
        next_q = questions[quiz_index]

        text = f"""
{topic['emoji']} <b>{topic['name']} - ТЕСТ (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>ВОПРОС {quiz_index + 1}/{len(questions)}</b>
━━━━━━━━━━━━━━━━━━━━━

❓ {next_q['question']}
"""

        await callback.message.edit_text(
            text,
            reply_markup=quiz_keyboard(next_q['options']),
            parse_mode="HTML"
        )
    else:
        # Тест завершен
        percentage = (quiz_score / len(questions)) * 100

        text = f"""
{topic['emoji']} <b>ТЕСТ ЗАВЕРШЕН! (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>📊 РЕЗУЛЬТАТЫ:</b>
━━━━━━━━━━━━━━━━━━━━━

✅ Правильных ответов: {quiz_score}/{len(questions)}
🎯 Точность: {percentage:.1f}%

━━━━━━━━━━━━━━━━━━━━━
<b>✨ В ПОЛНОЙ ВЕРСИИ:</b>
• +20% баллов за правильные ответы
• Бонусы за идеальный тест (+50 баллов)
• Сохранение статистики в профиль
• Достижения и награды
• Прогресс по темам
━━━━━━━━━━━━━━━━━━━━━
"""

        await callback.message.edit_text(
            text,
            reply_markup=after_quiz_keyboard(),
            parse_mode="HTML"
        )
        await state.clear()


# ==============================
# ДЕМО-ДУЭЛИ
# ==============================

@router.callback_query(F.data == "demo_duel")
async def demo_duel(callback: CallbackQuery):
    """Демонстрация дуэльной системы"""

    text = f"""
⚔️ <b>ДЕМО-ДУЭЛЬ: КАК ЭТО РАБОТАЕТ</b>

━━━━━━━━━━━━━━━━━━━━━
<b>🎯 ПРИМЕР ЗАВЕРШЕННОЙ ДУЭЛИ:</b>
━━━━━━━━━━━━━━━━━━━━━

👤 <b>{DEMO_DUEL['player1']['name']}</b> {DEMO_DUEL['player1']['rank']}
   ELO: {DEMO_DUEL['player1']['elo']}
   ⚔️ ПРОТИВ
👤 <b>{DEMO_DUEL['player2']['name']}</b> {DEMO_DUEL['player2']['rank']}
   ELO: {DEMO_DUEL['player2']['elo']}

📚 Тема: {DEMO_DUEL['topic']}
📝 Вопросов: {DEMO_DUEL['questions']}
⏱ Длительность: {DEMO_DUEL['duration']}

━━━━━━━━━━━━━━━━━━━━━
🏆 <b>РЕЗУЛЬТАТ:</b>
━━━━━━━━━━━━━━━━━━━━━

{DEMO_DUEL['player1']['name']}: {DEMO_DUEL['player1']['score']} ✅
{DEMO_DUEL['player2']['name']}: {DEMO_DUEL['player2']['score']} ❌

📊 <b>Изменение рейтинга:</b>
• Победитель: {DEMO_DUEL['rating_change_winner']}
• Проигравший: {DEMO_DUEL['rating_change_loser']}
💰 Награда: {DEMO_DUEL['reward']}

━━━━━━━━━━━━━━━━━━━━━
<b>✨ В ПОЛНОЙ ВЕРСИИ:</b>
• Реальные дуэли с живыми игроками
• Система подбора по ELO (1000-2000+)
• 5+ режимов игры
• Рейтинговая таблица
• Достижения за победы
• Приглашение друзей
• Турниры и ивенты

<b>👥 Сейчас в сети:</b> 127 игроков
<b>⚔️ Активных дуэлей:</b> 34
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Топ-10 игроков", callback_data="demo_top")
    builder.button(text="📋 Правила дуэлей", callback_data="demo_duel_rules")
    builder.button(text="💰 Купить полную версию", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_duel_rules")
async def demo_duel_rules(callback: CallbackQuery):
    """Правила дуэлей"""

    text = """
⚔️ <b>ПРАВИЛА ДУЭЛЕЙ (ПОЛНАЯ ВЕРСИЯ)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>1️⃣ ФОРМАТ</b>
━━━━━━━━━━━━━━━━━━━━━
• 5 вопросов на общую тему
• 30 секунд на каждый ответ
• +1 очко за правильный ответ

━━━━━━━━━━━━━━━━━━━━━
<b>2️⃣ РЕЙТИНГ ELO</b>
━━━━━━━━━━━━━━━━━━━━━
• Начальный рейтинг: 1000
• Победа над сильным: +15-20 ELO
• Победа над слабым: +5-10 ELO
• Поражение: -5-15 ELO

━━━━━━━━━━━━━━━━━━━━━
<b>3️⃣ НАГРАДЫ</b>
━━━━━━━━━━━━━━━━━━━━━
• Победа: +10 баллов
• Ничья: +5 баллов обоим
• Серия побед: бонусные баллы
• Топ-10 сезона: эксклюзивные награды

━━━━━━━━━━━━━━━━━━━━━
<b>4️⃣ РЕЖИМЫ ИГРЫ</b>
━━━━━━━━━━━━━━━━━━━━━
🎮 Быстрая дуэль - случайная тема
👥 Дружеская дуэль - пригласить друга
🏆 Турнир - 4-8 игроков
📊 Рейтинговые игры - сезонные

━━━━━━━━━━━━━━━━━━━━━
<b>💎 PREMIUM-БОНУСЫ:</b>
• Приоритет в очереди (без ожидания)
• +20% баллов за победу
• Участие в закрытых турнирах
• Особый статус в дуэлях
• Статистика противников
━━━━━━━━━━━━━━━━━━━━━
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_button("demo_duel"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_top")
async def demo_top(callback: CallbackQuery):
    """Топ-10 игроков"""

    text = """
🏆 <b>ТОП-10 ИГРОКОВ (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
🥇 1. Алексей — 1850 ELO (15,420 баллов) 👑
🥈 2. Екатерина — 1720 ELO (12,890 баллов) 👑
🥉 3. Дмитрий — 1680 ELO (11,230 баллов) 👑
4️⃣ 4. Анна — 1590 ELO (9,840 баллов) 👑
5️⃣ 5. Сергей — 1540 ELO (8,750 баллов)
6️⃣ 6. Ольга — 1480 ELO (7,620 баллов)
7️⃣ 7. Михаил — 1420 ELO (6,540 баллов)
8️⃣ 8. Татьяна — 1390 ELO (5,980 баллов) 👑
9️⃣ 9. Андрей — 1350 ELO (5,210 баллов)
🔟 10. Наталья — 1310 ELO (4,870 баллов)
━━━━━━━━━━━━━━━━━━━━━

<b>📊 СТАТИСТИКА ПЛАТФОРМЫ:</b>
👥 Всего игроков: 1,247
👑 Premium-пользователей: 384 (31%)
⚔️ Дуэлей сыграно: 8,432
📚 Уроков пройдено: 15,789
🎯 Средний ELO: 1120

━━━━━━━━━━━━━━━━━━━━━
<b>💎 ХОТИТЕ ПОПАСТЬ В ТОП?</b>
Premium (месяц) — 299₽
Premium PRO (год) — 2399₽ (скидка 40%)
Lifetime — 4999₽ (навсегда)
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="💎 Стать Premium", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="demo_duel")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# ДЕМО-СТАТИСТИКА
# ==============================

@router.callback_query(F.data == "demo_stats")
async def demo_stats(callback: CallbackQuery):
    """Демонстрация статистики пользователя"""

    text = f"""
📊 <b>ДЕМО-СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ</b>

━━━━━━━━━━━━━━━━━━━━━
👤 <b>ПРОФИЛЬ:</b> {DEMO_STATS['username']} (Premium)
━━━━━━━━━━━━━━━━━━━━━

🏆 <b>ОБЩАЯ СТАТИСТИКА:</b>
• Баллы: {DEMO_STATS['rating']:,}
• Уроков пройдено: {DEMO_STATS['lessons']}
• Точность: {DEMO_STATS['accuracy']}%
• Стрик: {DEMO_STATS['streak']} дней 🔥

⚔️ <b>ДУЭЛИ:</b>
• Всего дуэлей: {DEMO_STATS['duels_total']}
• Побед: {DEMO_STATS['duels_won']}
• Процент побед: 72%
• Рейтинг ELO: {DEMO_STATS['elo']}
• Ранг: {DEMO_STATS['rank']}

📚 <b>ОБУЧЕНИЕ:</b>
• Изучено тем: {DEMO_STATS['topics_completed']}/{DEMO_STATS['topics_total']}
• Идеальных тестов: 28
• Бонусов получено: 3,450

🏅 <b>ДОСТИЖЕНИЯ ({DEMO_STATS['achievements']}/24):</b>
• 🔥 Недельный стрик
• 🏆 Месячный стрик
• ⚔️ 50 побед в дуэлях
• 💯 Идеальный тест
• 📚 Мастер знаний
• 💎 Premium-пользователь

━━━━━━━━━━━━━━━━━━━━━
<b>✨ В ПОЛНОЙ ВЕРСИИ:</b>
• Вся статистика сохраняется
• Детальный прогресс по темам
• Графики и диаграммы
• Сравнение с другими игроками
• Еженедельные отчеты
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="🏅 Все достижения", callback_data="demo_achievements")
    builder.button(text="📈 Прогресс по темам", callback_data="demo_progress")
    builder.button(text="💰 Купить полную версию", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_achievements")
async def demo_achievements(callback: CallbackQuery):
    """Достижения"""

    text = """
🏅 <b>ДОСТИЖЕНИЯ (ПОЛНАЯ ВЕРСИЯ)</b>

━━━━━━━━━━━━━━━━━━━━━
🔥 <b>СТРИКИ</b>
━━━━━━━━━━━━━━━━━━━━━
✅ 7 дней подряд — +100 баллов
✅ 30 дней подряд — +300 баллов
⬜ 100 дней подряд — +1000 баллов
⬜ 365 дней подряд — +5000 баллов

━━━━━━━━━━━━━━━━━━━━━
⚔️ <b>ДУЭЛИ</b>
━━━━━━━━━━━━━━━━━━━━━
✅ Первая победа — +50 баллов
✅ 10 побед — +200 баллов
✅ 50 побед — +500 баллов
⬜ 100 побед — +1000 баллов
⬜ 500 побед — +5000 баллов

━━━━━━━━━━━━━━━━━━━━━
📚 <b>ОБУЧЕНИЕ</b>
━━━━━━━━━━━━━━━━━━━━━
✅ Первый урок — +50 баллов
✅ 100% тест — +100 баллов
✅ 5 тем пройдено — +150 баллов
✅ 10 тем пройдено — +300 баллов
⬜ Все темы пройдены — +500 баллов

━━━━━━━━━━━━━━━━━━━━━
👑 <b>PREMIUM</b>
━━━━━━━━━━━━━━━━━━━━━
✅ Первая покупка — +100 баллов
✅ Год Premium — +500 баллов
⬜ Lifetime — +1000 баллов
⬜ 3 года Premium — +3000 баллов

<b>📊 Всего достижений:</b> 24
<b>📊 Максимум баллов:</b> 5,000+
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_button("demo_stats"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_progress")
async def demo_progress(callback: CallbackQuery):
    """Прогресс по темам"""

    text = """
📈 <b>ПРОГРЕСС ПО ТЕМАМ (ДЕМО)</b>

━━━━━━━━━━━━━━━━━━━━━
<b>✅ ПРОЙДЕНО (60%):</b>
━━━━━━━━━━━━━━━━━━━━━
• 🇷🇺 Падежи — 100% ⭐
• 📝 Глаголы — 92% ⭐
• 🔤 Приставки — 85% ⭐
• 📚 Части речи — 78%
• ✍️ Н и НН — 70%
• 📖 Лексика — 65%
• 🎯 Ударение — 60%

━━━━━━━━━━━━━━━━━━━━━
<b>🔄 В ПРОЦЕССЕ:</b>
━━━━━━━━━━━━━━━━━━━━━
• 🔀 Сложные предложения — 45%
• ⚡️ Деепричастия — 30%
• 💬 Прямая речь — 25%

━━━━━━━━━━━━━━━━━━━━━
<b>🔒 PREMIUM ТЕМЫ:</b>
━━━━━━━━━━━━━━━━━━━━━
• 🔍 Омонимы и паронимы
• 📊 Морфологический разбор
• 🎓 Стилистика текста
• 🌍 Заимствованные слова
• 📝 Итоговое тестирование
• 🏆 Олимпиадные задания

━━━━━━━━━━━━━━━━━━━━━
<b>📊 Общий прогресс:</b> 15/25 тем (60%)
<b>💎 Premium:</b> доступ ко ВСЕМ темам!
━━━━━━━━━━━━━━━━━━━━━
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_button("demo_stats"),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# ТАРИФЫ И ЦЕНЫ
# ==============================

@router.callback_query(F.data == "demo_prices")
async def demo_prices(callback: CallbackQuery):
    """Показ всех тарифов"""

    text = f"""
💰 <b>ТАРИФЫ И ЦЕНЫ (ПОЛНАЯ ВЕРСИЯ)</b>

━━━━━━━━━━━━━━━━━━━━━
🌱 <b>БАЗОВЫЙ - {DEMO_TARIFFS['basic']['price']}</b>
━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(DEMO_TARIFFS['basic']['features'])}

━━━━━━━━━━━━━━━━━━━━━
👑 <b>PREMIUM - {DEMO_TARIFFS['premium_month']['price']}</b> 🔥 ХИТ
━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(DEMO_TARIFFS['premium_month']['features'])}

━━━━━━━━━━━━━━━━━━━━━
💎 <b>PREMIUM PRO - {DEMO_TARIFFS['premium_year']['price']}</b> ⚡️ ВЫГОДА
━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(DEMO_TARIFFS['premium_year']['features'])}

━━━━━━━━━━━━━━━━━━━━━
👑 <b>LIFETIME - {DEMO_TARIFFS['lifetime']['price']}</b> 🎯
━━━━━━━━━━━━━━━━━━━━━
{chr(10).join(DEMO_TARIFFS['lifetime']['features'][:5])}
...
+ Имя в списке спонсоров

━━━━━━━━━━━━━━━━━━━━━
<b>👇 Нажмите для подробностей:</b>
"""

    await callback.message.edit_text(
        text,
        reply_markup=tariffs_keyboard(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "tariff:month")
async def tariff_month(callback: CallbackQuery):
    """Детали тарифа Premium месяц"""

    text = """
👑 <b>PREMIUM (МЕСЯЦ) — 299₽</b>

━━━━━━━━━━━━━━━━━━━━━
🔥 <b>САМЫЙ ПОПУЛЯРНЫЙ ТАРИФ!</b>
━━━━━━━━━━━━━━━━━━━━━

<b>📦 ЧТО ВХОДИТ:</b>

📚 <b>Доступ к контенту:</b>
• Все 20+ тем по русскому языку
• 500+ вопросов с объяснениями
• Теория по каждой теме
• Еженедельные обновления

⚡️ <b>Преимущества:</b>
• Уроки БЕЗ 24-часового ожидания
• +20% баллов за правильные ответы
• Приоритетный поиск в дуэлях
• Premium-значок в профиле

🎁 <b>Бонус при покупке:</b>
• +100 баллов на счет
• 3 подсказки в подарок

━━━━━━━━━━━━━━━━━━━━━
💳 <b>Оплата:</b> раз в месяц, автопродление
❌ <b>Отмена:</b> в любое время

<b>⭐️ ИТОГО:</b> 299₽/месяц — менее 10₽ в день!
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 КУПИТЬ PREMIUM", callback_data="demo_buy")
    builder.button(text="📋 Сравнить тарифы", callback_data="tariff:compare")
    builder.button(text="← Назад", callback_data="demo_prices")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "tariff:year")
async def tariff_year(callback: CallbackQuery):
    """Детали тарифа Premium год"""

    text = """
💎 <b>PREMIUM PRO (ГОД) — 2399₽</b>

━━━━━━━━━━━━━━━━━━━━━
⚡️ <b>САМАЯ ВЫГОДНАЯ ЦЕНА!</b>
━━━━━━━━━━━━━━━━━━━━━

<b>📦 ЧТО ВХОДИТ:</b>
✅ Всё, что в Premium (месяц)

<b>🎯 ДОПОЛНИТЕЛЬНО:</b>
• Экономия 40% — 1200₽ в год!
• Бонус +500 баллов при покупке
• Доступ к эксклюзивным темам
• Приоритетная поддержка 24/7
• Участие в закрытых турнирах
• Ранний доступ к новым функциям

━━━━━━━━━━━━━━━━━━━━━
<b>📊 РАСЧЕТ ВЫГОДЫ:</b>
• Premium помесячно: 299₽ × 12 = 3588₽
• Premium PRO (год): 2399₽
• <b>ЭКОНОМИЯ: 1189₽!</b>

<b>🎁 ПОДАРКИ:</b>
• +500 баллов
• 5 подсказок
• 3 дня Premium в подарок другу

<b>⭐️ ИТОГО:</b> 199₽/месяц — максимальная выгода!
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 КУПИТЬ PREMIUM PRO", callback_data="demo_buy")
    builder.button(text="📋 Сравнить тарифы", callback_data="tariff:compare")
    builder.button(text="← Назад", callback_data="demo_prices")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "tariff:lifetime")
async def tariff_lifetime(callback: CallbackQuery):
    """Детали тарифа Lifetime"""

    text = """
👑 <b>LIFETIME — 4999₽ (РАЗОВО)</b>

━━━━━━━━━━━━━━━━━━━━━
🎯 <b>НАВСЕГДА! БЕЗ АБОНЕНТСКОЙ ПЛАТЫ!</b>
━━━━━━━━━━━━━━━━━━━━━

<b>📦 ЧТО ВХОДИТ:</b>
✅ Всё, что в Premium PRO

<b>💎 УНИКАЛЬНЫЕ ПРЕИМУЩЕСТВА:</b>
• Premium НАВСЕГДА — без продлений!
• Все будущие темы и обновления
• Именной статус 'Lifetime'
• Доступ к бета-версиям
• Бонус +1000 баллов
• Подарок: 3 месяца Premium другу
• Имя в списке спонсоров
• VIP-поддержка

━━━━━━━━━━━━━━━━━━━━━
<b>📊 РАСЧЕТ ОКУПАЕМОСТИ:</b>
• 1 год Premium: 299₽ × 12 = 3588₽
• 2 года: 7176₽
• 3 года: 10764₽

<b>⭐️ LIFETIME:</b> 4999₽ — окупается за 17 месяцев!
<b>ДАЛЬШЕ — БЕСПЛАТНО НАВСЕГДА!</b>

⚠️ <b>Ограниченное предложение:</b>
Цена 4999₽ действует для первых 100 покупателей!
<b>Осталось мест: 47</b>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 КУПИТЬ LIFETIME", callback_data="demo_buy")
    builder.button(text="📋 Сравнить тарифы", callback_data="tariff:compare")
    builder.button(text="← Назад", callback_data="demo_prices")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "tariff:compare")
async def tariff_compare(callback: CallbackQuery):
    """Сравнение тарифов"""

    text = """
📋 <b>СРАВНЕНИЕ ТАРИФОВ</b>

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
<b>Параметр           Базовый  Premium  PRO   Lifetime</b>
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Цена            0₽      299₽/мес 2399₽/год 4999₽
Темы            3       ВСЕ      ВСЕ      ВСЕ
Вопросов        50      500+     500+     500+
Кулдаун уроков  24ч     НЕТ      НЕТ      НЕТ
Бонус баллы     0%      +20%     +20%     +20%
Дуэли           Да      Да       Да       Да
Приоритет дуэли Нет     Да       Да       Да
ELO рейтинг     Да      Да       Да       Да
Достижения      Да      Да       Да       Да
Эксклюзивные    Нет     Нет      Да       Да
темы
Бета-доступ     Нет     Нет      Нет      Да
Поддержка       Обычная Обычная Приорит VIP
Бонус при       -       100б     500б     1000б
покупке
Подарок другу   -       -        -        3 мес
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

<b>✅ РЕКОМЕНДАЦИЯ:</b>
• Для знакомства: Базовый тариф
• Для активных: Premium месяц
• Макс. выгода: Premium PRO (год)
• Навсегда: Lifetime
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_button("demo_prices"),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_faq")
async def demo_faq(callback: CallbackQuery):
    """Часто задаваемые вопросы"""

    text = """
❓ <b>ЧАСТО ЗАДАВАЕМЫЕ ВОПРОСЫ</b>

━━━━━━━━━━━━━━━━━━━━━
<b>1️⃣ Как оплатить?</b>
━━━━━━━━━━━━━━━━━━━━━
• Банковской картой (Visa, Mastercard, МИР)
• ЮMoney, СБП, Apple/Google Pay
• Безопасно через YooKassa
• Мгновенная активация

━━━━━━━━━━━━━━━━━━━━━
<b>2️⃣ Можно ли вернуть деньги?</b>
━━━━━━━━━━━━━━━━━━━━━
• Да, в течение 14 дней, если не использовали
• Возврат на карту в течение 3-10 дней
• 100% гарантия возврата

━━━━━━━━━━━━━━━━━━━━━
<b>3️⃣ Подписка продлевается автоматически?</b>
━━━━━━━━━━━━━━━━━━━━━
• Да, за 24 часа до окончания
• Можно отменить в любой момент
• Уведомление придет за 3 дня

━━━━━━━━━━━━━━━━━━━━━
<b>4️⃣ Что будет, если не продлить?</b>
━━━━━━━━━━━━━━━━━━━━━
• Потеряете доступ к Premium-функциям
• Ваш прогресс сохранится
• Можно возобновить в любой момент

━━━━━━━━━━━━━━━━━━━━━
<b>5️⃣ Добавляются ли новые темы?</b>
━━━━━━━━━━━━━━━━━━━━━
• Да, каждую неделю
• Для Premium бесплатно
• По запросам пользователей

━━━━━━━━━━━━━━━━━━━━━
<b>6️⃣ Есть ли скидки?</b>
━━━━━━━━━━━━━━━━━━━━━
• Годовая подписка -40%
• Студентам -20% (по запросу)
• Приведи друга -100₽ каждому

━━━━━━━━━━━━━━━━━━━━━
<b>7️⃣ Как связаться с поддержкой?</b>
━━━━━━━━━━━━━━━━━━━━━
• Telegram: @theshramjee
• Email: shramjee@example.com
• Время ответа: до 2 часов
• Premium: до 30 минут
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_button("demo_prices"),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# PREMIUM-ВОЗМОЖНОСТИ
# ==============================

@router.callback_query(F.data == "demo_premium")
async def demo_premium_features(callback: CallbackQuery):
    """Демонстрация Premium-возможностей"""

    text = """
👑 <b>PREMIUM-ВОЗМОЖНОСТИ</b>

━━━━━━━━━━━━━━━━━━━━━
📚 <b>КОНТЕНТ PREMIUM</b>
━━━━━━━━━━━━━━━━━━━━━
🔹 <b>20+ тем</b> вместо 3 бесплатных
🔹 <b>500+ вопросов</b> с объяснениями
🔹 Эксклюзивные темы (еженедельно)
🔹 Сложные тесты повышенного уровня
🔹 Видео-уроки (в разработке)

━━━━━━━━━━━━━━━━━━━━━
⚡️ <b>ИГРОВЫЕ БОНУСЫ</b>
━━━━━━━━━━━━━━━━━━━━━
🔹 <b>+20% баллов</b> за правильные ответы
🔹 <b>+50% бонус</b> за завершение темы
🔹 Двойные баллы (1 раз/день)
🔹 Эксклюзивные достижения
🔹 Особый статус в профиле

━━━━━━━━━━━━━━━━━━━━━
⚔️ <b>ДУЭЛИ PREMIUM</b>
━━━━━━━━━━━━━━━━━━━━━
🔹 <b>Приоритетный поиск</b> — без очереди
🔹 Участие в турнирах
🔹 +10% к рейтингу ELO
🔹 Статистика противников
🔹 Реванш без ограничений

━━━━━━━━━━━━━━━━━━━━━
🎁 <b>ОСОБЫЕ ПРИВИЛЕГИИ</b>
━━━━━━━━━━━━━━━━━━━━━
🔹 <b>Уроки без кулдауна</b> — учись в своем темпе
🔹 Ранний доступ к новым темам
🔹 Приоритетная поддержка
🔹 Скидки на будущие покупки
🔹 Участие в закрытых бета-тестах

━━━━━━━━━━━━━━━━━━━━━
<b>💎 ВСЕ ЭТО УЖЕ СЕГОДНЯ ЗА 299₽/МЕСЯЦ!</b>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Активировать Premium", callback_data="demo_buy")
    builder.button(text="📋 Сравнить тарифы", callback_data="tariff:compare")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# ПОКУПКА И КОНТАКТЫ
# ==============================

@router.callback_query(F.data == "demo_buy")
async def demo_buy(callback: CallbackQuery):
    """Призыв к покупке"""

    text = f"""
💎 <b>ПРИОБРЕСТИ ПОЛНУЮ ВЕРСИЮ</b>

━━━━━━━━━━━━━━━━━━━━━
<b>Выберите удобный способ покупки:</b>
━━━━━━━━━━━━━━━━━━━━━

1️⃣ <b>Через бота (мгновенно)</b>
   • Оплата картой, СБП, ЮMoney
   • Автоматическая активация
   • Безопасно через YooKassa
   👉 Перейдите в раздел '🛒 Магазин' в полной версии

2️⃣ <b>Написать разработчику</b>
   • Индивидуальные условия
   • Корпоративные лицензии
   • Оптовые скидки
   👉 @{config.DEVELOPER_USERNAME}

3️⃣ <b>Купить в подарок</b>
   • Подарочный сертификат
   • Активация по коду
   • Открытка с поздравлением
   👉 По запросу @{config.DEVELOPER_USERNAME}

━━━━━━━━━━━━━━━━━━━━━
🎁 <b>СПЕЦПРЕДЛОЖЕНИЕ:</b>
При покупке годовой подписки СЕГОДНЯ
👉 <b>+500 баллов и месяц в подарок!</b>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=f"📞 Написать @{config.DEVELOPER_USERNAME}", url=f"https://t.me/{config.DEVELOPER_USERNAME}")
    builder.button(text="📋 Сравнить тарифы", callback_data="tariff:compare")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_contact")
async def demo_contact(callback: CallbackQuery):
    """Контакты разработчика"""

    text = f"""
📞 <b>СВЯЗЬ С РАЗРАБОТЧИКОМ</b>

━━━━━━━━━━━━━━━━━━━━━
👨‍💻 <b>Автор бота:</b> @{config.DEVELOPER_USERNAME}
━━━━━━━━━━━━━━━━━━━━━

<b>💬 По каким вопросам обращаться:</b>
• Приобретение Premium
• Технические проблемы
• Предложения по улучшению
• Сотрудничество
• Оптовые лицензии
• Подарочные сертификаты

<b>⏱ Время ответа:</b>
• Обычные вопросы: до 2 часов
• Premium-поддержка: до 30 минут
• Срочные: 5-10 минут

<b>📧 Email:</b> {config.DEVELOPER_EMAIL}
<b>🌐 Сайт:</b> В разработке

━━━━━━━━━━━━━━━━━━━━━
<b>👇 Нажмите кнопку ниже, чтобы написать!</b>
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text=f"📨 Написать @{config.DEVELOPER_USERNAME}", url=f"https://t.me/{config.DEVELOPER_USERNAME}")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@router.callback_query(F.data == "demo_about")
async def demo_about(callback: CallbackQuery):
    """О полной версии бота"""

    text = """
ℹ️ <b>О ПОЛНОЙ ВЕРСИИ БОТА</b>

━━━━━━━━━━━━━━━━━━━━━
🤖 <b>Что это?</b>
━━━━━━━━━━━━━━━━━━━━━
Это полноценный образовательный Telegram-бот
для изучения русского языка в игровой форме.
Разработан профессиональной командой в 2026 году.

━━━━━━━━━━━━━━━━━━━━━
🎯 <b>КЛЮЧЕВЫЕ ВОЗМОЖНОСТИ:</b>
━━━━━━━━━━━━━━━━━━━━━

📚 <b>ОБУЧЕНИЕ:</b>
• 20+ тем с теорией и тестами
• 500+ вопросов разной сложности
• Система повторения пройденного
• Прогресс по каждой теме
• Статистика и достижения
• Персональные рекомендации

⚔️ <b>ДУЭЛИ:</b>
• PvP-сражения в реальном времени
• Рейтинговая система ELO
• Поиск соперников по уровню
• Приглашение друзей
• Турниры и ивенты
• Сезонные награды

👑 <b>PREMIUM:</b>
• Все темы без ограничений
• Уроки без кулдауна
• +20% баллов за ответы
• Приоритет в дуэлях
• Эксклюзивный контент
• Ранний доступ к обновлениям

💰 <b>МОНЕТИЗАЦИЯ:</b>
• Гибкая система подписок
• Разовые покупки
• Интеграция с YooKassa
• Автоматическая выдача товаров
• История транзакций

🛠 <b>ДЛЯ АДМИНА:</b>
• Полная админ-панель
• Управление темами
• Статистика и аналитика
• Массовая рассылка
• Экспорт данных
• Управление пользователями

━━━━━━━━━━━━━━━━━━━━━
<b>💎 ГОТОВЫ КУПИТЬ?</b> Напишите @theshramjee
━━━━━━━━━━━━━━━━━━━━━
"""

    builder = InlineKeyboardBuilder()
    builder.button(text="📞 Купить полную версию", callback_data="demo_buy")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    await callback.message.edit_text(
        text,
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# СОВЕТ ДНЯ
# ==============================

@router.callback_query(F.data == "demo_tip")
async def demo_tip(callback: CallbackQuery):
    """Случайный совет дня"""

    tip = random.choice(DEMO_TIPS)

    text = f"""
💡 <b>СОВЕТ ДНЯ</b>

━━━━━━━━━━━━━━━━━━━━━
{tip}
━━━━━━━━━━━━━━━━━━━━━

<i>В полной версии: ежедневные советы с напоминаниями!</i>
"""

    await callback.message.edit_text(
        text,
        reply_markup=back_button("main"),
        parse_mode="HTML"
    )
    await callback.answer()


# ==============================
# WEBHOOK HANDLERS ДЛЯ RAILWAY
# ==============================

async def on_startup_webhook(bot: Bot, base_url: str):
    """Установка вебхука при запуске"""
    try:
        await bot.set_webhook(
            url=f"{base_url}/webhook",
            drop_pending_updates=True,
            max_connections=40
        )
        logger.info(f"✅ Webhook установлен: {base_url}/webhook")

        # Отправляем уведомление админу
        if config.ADMIN_ID:
            try:
                await bot.send_message(
                    config.ADMIN_ID,
                    f"🎮 <b>ДЕМО-БОТ ЗАПУЩЕН НА RAILWAY!</b>\n\n"
                    f"🔗 URL: {base_url}\n"
                    f"⏰ Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n\n"
                    f"📊 Статистика:\n"
                    f"• Тем: {len(DEMO_TOPICS)}\n"
                    f"• Вопросов: {sum(len(t['questions']) for t in DEMO_TOPICS.values())}\n"
                    f"• Тарифов: {len(DEMO_TARIFFS)}",
                    parse_mode="HTML"
                )
                logger.info(f"✅ Уведомление админу отправлено")
            except Exception as e:
                logger.error(f"❌ Не удалось отправить уведомление админу: {e}")
    except Exception as e:
        logger.error(f"❌ Ошибка установки webhook: {e}")


async def on_shutdown_webhook(bot: Bot):
    """Удаление вебхука при остановке"""
    try:
        await bot.delete_webhook()
        logger.info("✅ Webhook удалён")
    except Exception as e:
        logger.error(f"❌ Ошибка удаления webhook: {e}")


async def main_webhook():
    """Запуск в режиме webhook для Railway"""
    print("=" * 60)
    print("🚀 ЗАПУСК ДЕМО-БОТА НА RAILWAY (WEBHOOK MODE)")
    print("=" * 60)

    # Инициализация
    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    # Настройки порта
    port = int(os.getenv("PORT", 8080))

    # Получаем URL от Railway
    railway_url = os.getenv("RAILWAY_STATIC_URL", "")
    if not railway_url:
        # Fallback для локального тестирования
        railway_url = f"https://demo-bot.up.railway.app"
        logger.warning(f"⚠️ RAILWAY_STATIC_URL не найден, использую: {railway_url}")

    # Создаём aiohttp приложение
    app = web.Application()

    # Регистрируем вебхук
    webhook_requests_handler = SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
    )
    webhook_requests_handler.register(app, path="/webhook")

    # Регистрируем health check для мониторинга
    async def health_check(request):
        return web.Response(
            text=json.dumps({
                "status": "ok",
                "timestamp": datetime.now().isoformat(),
                "bot": config.BOT_USERNAME,
                "webhook": f"{railway_url}/webhook"
            }),
            content_type="application/json"
        )

    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    app.router.add_get("/ping", lambda _: web.Response(text="pong"))

    # Регистрируем статическую страницу
    async def index(request):
        return web.Response(
            text="""
            <html>
                <head>
                    <title>Demo Russian Bot</title>
                    <style>
                        body { font-family: Arial; padding: 40px; background: #f5f5f5; }
                        .container { max-width: 800px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
                        h1 { color: #2c3e50; }
                        .status { color: green; font-weight: bold; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <h1>🤖 Demo Russian Bot</h1>
                        <p class="status">✅ Бот запущен и работает!</p>
                        <p>📊 Webhook: /webhook</p>
                        <p>🔍 Health check: /health</p>
                        <p>⏰ Время: """ + datetime.now().strftime('%d.%m.%Y %H:%M:%S') + """</p>
                        <hr>
                        <p>👨‍💻 Разработчик: @theshramjee</p>
                        <p>📞 По вопросам покупки: @theshramjee</p>
                    </div>
                </body>
            </html>
            """,
            content_type="text/html"
        )

    app.router.add_get("/", index)

    # Хуки запуска/остановки
    app.on_startup.append(lambda _: on_startup_webhook(bot, railway_url))
    app.on_shutdown.append(lambda _: on_shutdown_webhook(bot))

    print(f"✅ Бот: @{config.BOT_USERNAME}")
    print(f"✅ Webhook URL: {railway_url}/webhook")
    print(f"✅ Health check: {railway_url}/health")
    print(f"✅ Порт: {port}")
    print("=" * 60)

    # Запускаем веб-сервер
    return web.run_app(app, host="0.0.0.0", port=port)


async def main_polling():
    """Запуск в режиме polling для локальной разработки"""
    print("=" * 60)
    print("🚀 ЗАПУСК ДЕМО-БОТА ЛОКАЛЬНО (POLLING MODE)")
    print("=" * 60)

    bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    print(f"✅ Бот: @{config.BOT_USERNAME}")
    print(f"✅ Режим: Long Polling")
    print("=" * 60)

    await bot.delete_webhook(drop_pending_updates=True)
    await dp.start_polling(bot)


# ==============================
# ТОЧКА ВХОДА
# ==============================

if __name__ == "__main__":
    # Автоматическое определение среды выполнения
    if os.getenv("RAILWAY_ENVIRONMENT") or os.getenv("PORT"):
        # Мы на Railway - запускаем webhook
        asyncio.run(main_webhook())
    else:
        # Локально - запускаем polling
        asyncio.run(main_polling())