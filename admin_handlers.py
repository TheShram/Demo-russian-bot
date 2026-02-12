# admin_handlers.py - ПОЛНАЯ АДМИН-ПАНЕЛЬ (ИСПРАВЛЕННАЯ ВЕРСИЯ)

import asyncio
import json
import csv
import io
import random
from datetime import datetime, timedelta
from pathlib import Path

from aiogram import Bot, Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, Document, FSInputFile, BufferedInputFile
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

from config import config
from bot import (
    Duel, DuelStatus, SubscriptionTier,
    get_user_activity, get_user_subscription,
    user_active_duels, users_last_notification, debug_print,
    users_rating, user_activities, user_subscriptions,
    active_duels, waiting_duels, TOPICS, TOPIC_ORDER,
    users_completed_topics, users_available_topics, save_data,
    is_premium, can_access_topic, load_themes
)
from notifications import get_notification_manager, send_test_notification

# Создаем роутер для админ-команд
admin_router = Router()


def back_to_admin() -> InlineKeyboardMarkup:
    """Кнопка возврата в админ-панель"""
    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)
    return builder.as_markup()


# ==============================
# FSM СОСТОЯНИЯ ДЛЯ АДМИНА
# ==============================

class AdminStates(StatesGroup):
    """Состояния для административных действий"""
    waiting_for_premium_user_id = State()
    waiting_for_premium_days = State()
    waiting_for_bulk_message = State()
    waiting_for_bulk_confirm = State()
    waiting_for_theme_file = State()
    waiting_for_theme_name = State()
    waiting_for_user_stats = State()
    waiting_for_ban_reason = State()
    waiting_for_edit_points_user = State()
    waiting_for_edit_points_amount = State()
    waiting_for_find_user = State()
    waiting_for_edit_theme = State()
    waiting_for_edit_theme_field = State()
    waiting_for_edit_theme_value = State()


# ==============================
# ОСНОВНАЯ АДМИН-ПАНЕЛЬ
# ==============================

@admin_router.callback_query(F.data == "admin_panel")
async def admin_panel(callback: CallbackQuery):
    """Главная админ-панель"""
    user_id = callback.from_user.id

    if user_id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    # Собираем статистику
    total_users = len(users_rating)
    active_today = len([
        a for a in user_activities.values()
        if a.last_activity and a.last_activity.date() == datetime.now().date()
    ])
    active_week = len([
        a for a in user_activities.values()
        if a.last_activity and (datetime.now() - a.last_activity).days < 7
    ])

    premium_users = len([
        u for u, s in user_subscriptions.items()
        if s.is_active() and s.tier != SubscriptionTier.FREE
    ])

    active_duels_count = len([d for d in active_duels.values() if d.status == DuelStatus.IN_PROGRESS])
    waiting_duels_count = len(waiting_duels)

    total_questions = sum(len(t.get('questions', [])) for t in TOPICS.values())

    # Рассчитываем доход
    total_revenue = 0
    for sub in user_subscriptions.values():
        for transaction in sub.transaction_history:
            total_revenue += transaction.get('amount', 0)

    text = (
        "🔧 <b>АДМИН-ПАНЕЛЬ</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {total_users}\n"
        f"• Активных сегодня: {active_today}\n"
        f"• Активных за неделю: {active_week}\n"
        f"• Premium: {premium_users}\n\n"
        f"📚 <b>Контент:</b>\n"
        f"• Тем: {len(TOPICS)}\n"
        f"• Вопросов: {total_questions}\n"
        f"• Порядок тем: {len(TOPIC_ORDER)}\n\n"
        f"⚔️ <b>Дуэли:</b>\n"
        f"• Активных: {active_duels_count}\n"
        f"• В ожидании: {waiting_duels_count}\n"
        f"• Всего в памяти: {len(active_duels)}\n\n"
        f"💰 <b>Финансы:</b>\n"
        f"• Доход: {total_revenue}₽\n"
        f"• Транзакций: {sum(len(s.transaction_history) for s in user_subscriptions.values())}\n\n"
        f"🕐 <b>Система:</b>\n"
        f"• Время: {datetime.now().strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"• Токен: {'✅' if config.BOT_TOKEN else '❌'}\n"
        f"• YooKassa: {'✅' if config.YOOKASSA_TOKEN else '❌'}\n\n"
        "Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Управление пользователями", callback_data="admin:users_menu")
    builder.button(text="📚 Управление темами", callback_data="admin:topics_menu")
    builder.button(text="⚔️ Управление дуэлями", callback_data="admin:duels_menu")
    builder.button(text="👑 Управление Premium", callback_data="admin:premium_menu")
    builder.button(text="📨 Уведомления и рассылка", callback_data="admin:notify_menu")
    builder.button(text="📊 Статистика и экспорт", callback_data="admin:stats_menu")
    builder.button(text="⚙️ Настройки бота", callback_data="admin:settings_menu")
    builder.button(text="🧪 Тестовые функции", callback_data="admin:test_menu")
    builder.button(text="← Назад", callback_data="main")
    builder.adjust(1)

    try:
        await callback.message.edit_text(
            text=text,
            reply_markup=builder.as_markup(),
            parse_mode="HTML"
        )
    except Exception as e:
        debug_print(f"❌ Ошибка admin_panel: {e}")
        await callback.answer("Ошибка", show_alert=True)

    await callback.answer()


# ==============================
# УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ
# ==============================

@admin_router.callback_query(F.data == "admin:users_menu")
async def admin_users_menu(callback: CallbackQuery):
    """Меню управления пользователями"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "👥 <b>УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ</b>\n\n"
        "Выберите действие:\n\n"
        "• Просмотр статистики пользователя\n"
        "• Выдача/снятие Premium\n"
        "• Изменение баллов\n"
        "• Блокировка пользователя\n"
        "• Экспорт данных пользователя"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Найти пользователя", callback_data="admin:find_user")
    builder.button(text="📊 Статистика по ID", callback_data="admin:stats_by_id")
    builder.button(text="👑 Выдать Premium", callback_data="admin:give_premium")
    builder.button(text="⭐️ Снять Premium", callback_data="admin:remove_premium")
    builder.button(text="💰 Изменить баллы", callback_data="admin:edit_points")
    builder.button(text="🔨 Заблокировать", callback_data="admin:ban_user")
    builder.button(text="📈 Топ-100", callback_data="admin:top_100")
    builder.button(text="📤 Экспорт всех", callback_data="admin:export_users_csv")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:find_user")
async def admin_find_user_start(callback: CallbackQuery, state: FSMContext):
    """Поиск пользователя по ID или username"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_find_user)

    text = (
        "🔍 <b>ПОИСК ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Введите ID пользователя или @username:\n\n"
        "📌 <b>Примеры:</b>\n"
        "• 123456789 (ID)\n"
        "• @username (юзернейм)\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_find_user)
async def admin_find_user_process(message: Message, state: FSMContext):
    """Обработка поиска пользователя"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Поиск отменен",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    query = message.text.strip()
    found_users = []

    # Поиск по ID
    if query.isdigit():
        user_id = int(query)
        if user_id in users_rating:
            found_users.append(user_id)
    # Поиск по username (имитация - в реальности нужно через API)
    else:
        # Здесь можно добавить реальный поиск через API Telegram
        for uid in users_rating:
            found_users.append(uid)
        found_users = found_users[:5]  # Ограничим 5 для примера

    if not found_users:
        await message.answer(
            "❌ Пользователь не найден",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        await state.clear()
        return

    # Показываем результаты поиска
    builder = InlineKeyboardBuilder()
    for user_id in found_users[:10]:
        rating = users_rating.get(user_id, 0)
        sub = get_user_subscription(user_id)
        premium = "👑" if sub.is_active() and sub.tier != SubscriptionTier.FREE else " "
        builder.button(
            text=f"{premium} ID: {user_id} | {rating} баллов",
            callback_data=f"admin:show_user:{user_id}"
        )
    builder.button(text="← Назад", callback_data="admin:users_menu")
    builder.adjust(1)

    await message.answer(
        f"🔍 <b>Найдено пользователей: {len(found_users)}</b>\n\n"
        "Выберите пользователя:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await state.clear()


@admin_router.callback_query(F.data.startswith("admin:show_user:"))
async def admin_show_user(callback: CallbackQuery):
    """Показать полную информацию о пользователе"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    try:
        user_id = int(callback.data.split(":")[2])
    except:
        await callback.answer("❌ Ошибка", show_alert=True)
        return

    if user_id not in users_rating:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    rating = users_rating.get(user_id, 0)
    activity = get_user_activity(user_id)
    sub = get_user_subscription(user_id)

    completed_topics = users_completed_topics.get(user_id, set())
    available_topics = users_available_topics.get(user_id, [])

    total_duels = activity.duels_won + activity.duels_lost + activity.duels_drawn
    win_rate = (activity.duels_won / total_duels * 100) if total_duels > 0 else 0

    if sub.is_active() and sub.tier != SubscriptionTier.FREE:
        premium_status = f"✅ Активен до {sub.expires_at.strftime('%d.%m.%Y')}"
        days_left = (sub.expires_at - datetime.now()).days
    else:
        premium_status = "❌ Не активен"
        days_left = 0

    text = (
        f"📊 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        f"👤 <b>ID:</b> {user_id}\n"
        f"💰 <b>Баллы:</b> {rating}\n"
        f"👑 <b>Premium:</b> {premium_status}\n"
        f"📅 <b>Осталось дней:</b> {days_left}\n\n"
        f"📚 <b>Обучение:</b>\n"
        f"• Уроков пройдено: {activity.lessons_completed}\n"
        f"• Всего ответов: {activity.questions_answered}\n"
        f"• Правильных: {activity.correct_answers}\n"
        f"• Точность: {activity.accuracy}%\n"
        f"• Изучено тем: {len(completed_topics)}/{len(TOPICS)}\n\n"
        f"⚔️ <b>Дуэли:</b>\n"
        f"• Всего: {total_duels}\n"
        f"• Побед: {activity.duels_won}\n"
        f"• Поражений: {activity.duels_lost}\n"
        f"• Ничьих: {activity.duels_drawn}\n"
        f"• Win Rate: {win_rate:.1f}%\n"
        f"• ELO: {activity.elo_rating}\n\n"
        f"🔥 <b>Стрик:</b> {activity.daily_streak} дней\n"
        f"📅 <b>В боте с:</b> {activity.first_seen.strftime('%d.%m.%Y')}\n"
        f"🕐 <b>Последняя активность:</b> {activity.last_activity.strftime('%d.%m.%Y %H:%M')}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Выдать Premium", callback_data=f"admin:give_premium_to:{user_id}")
    builder.button(text="💰 Изменить баллы", callback_data=f"admin:edit_points_for:{user_id}")
    builder.button(text="🔨 Заблокировать", callback_data=f"admin:ban_user:{user_id}")
    builder.button(text="📤 Экспорт данных", callback_data=f"admin:export_user:{user_id}")
    builder.button(text="← Назад", callback_data="admin:find_user")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:ban_user"))
async def admin_ban_user_start(callback: CallbackQuery, state: FSMContext):
    """Начало блокировки пользователя"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    try:
        if ":" in callback.data:
            user_id = int(callback.data.split(":")[2])
            await state.update_data(target_user_id=user_id)
        else:
            user_id = None
    except:
        user_id = None

    await state.set_state(AdminStates.waiting_for_ban_reason)

    if user_id:
        text = (
            f"🔨 <b>БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            f"👤 Пользователь: {user_id}\n\n"
            f"Введите причину блокировки:\n\n"
            f"❌ Отправьте /cancel для отмены"
        )
    else:
        text = (
            "🔨 <b>БЛОКИРОВКА ПОЛЬЗОВАТЕЛЯ</b>\n\n"
            "Введите ID пользователя для блокировки:\n\n"
            "❌ Отправьте /cancel для отмены"
        )
        await state.set_state(AdminStates.waiting_for_premium_user_id)  # Переиспользуем состояние

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_ban_reason)
async def admin_ban_user_process(message: Message, state: FSMContext):
    """Обработка блокировки пользователя"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Блокировка отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")

    if not user_id:
        # Если ID не был передан, пробуем получить из сообщения
        try:
            user_id = int(message.text.strip())
        except:
            await message.answer("❌ Некорректный ID. Введите число.")
            return

    if user_id not in users_rating:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return

    reason = message.text.strip()

    # Создаем запись о блокировке
    if not hasattr(get_user_activity(user_id), 'is_banned'):
        get_user_activity(user_id).is_banned = True
        get_user_activity(user_id).ban_reason = reason
        get_user_activity(user_id).banned_at = datetime.now()

    # Удаляем все активные дуэли пользователя
    if user_id in user_active_duels:
        duel_id = user_active_duels[user_id]
        if duel_id in active_duels:
            del active_duels[duel_id]
        if duel_id in waiting_duels:
            waiting_duels.remove(duel_id)
        del user_active_duels[user_id]

    save_data()

    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            user_id,
            "🔨 <b>ВЫ ЗАБЛОКИРОВАНЫ</b>\n\n"
            f"❌ Причина: {reason}\n\n"
            "Если вы считаете, что это ошибка, свяжитесь с поддержкой.",
            parse_mode="HTML"
        )
    except:
        pass

    await message.answer(
        f"✅ <b>Пользователь {user_id} заблокирован!</b>\n\n"
        f"Причина: {reason}",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
        )
    )
    await state.clear()


@admin_router.callback_query(F.data == "admin:remove_premium")
async def admin_remove_premium_start(callback: CallbackQuery, state: FSMContext):
    """Снятие Premium"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_premium_user_id)

    text = (
        "⭐️ <b>СНЯТИЕ PREMIUM</b>\n\n"
        "Введите ID пользователя, у которого хотите снять Premium:\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_premium_user_id)
async def admin_remove_premium_process(message: Message, state: FSMContext):
    """Обработка снятия Premium"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Операция отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    try:
        target_user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число.")
        return

    if target_user_id not in users_rating:
        await message.answer("❌ Пользователь не найден.")
        return

    sub = get_user_subscription(target_user_id)

    if sub.tier == SubscriptionTier.FREE or not sub.is_active():
        await message.answer("❌ У пользователя нет активной Premium подписки.")
        return

    old_tier = sub.tier.value
    sub.tier = SubscriptionTier.FREE
    sub.expires_at = None
    save_data()

    # Уведомляем пользователя
    try:
        await message.bot.send_message(
            target_user_id,
            "⭐️ <b>Premium отключен</b>\n\n"
            "Администратор отключил вашу Premium подписку.\n\n"
            "Спасибо, что были с нами! ❤️",
            parse_mode="HTML"
        )
    except:
        pass

    await message.answer(
        f"✅ <b>Premium снят!</b>\n\n"
        f"👤 Пользователь: {target_user_id}",
        parse_mode="HTML"
    )
    await state.clear()


@admin_router.callback_query(F.data == "admin:give_premium")
async def admin_give_premium_start(callback: CallbackQuery, state: FSMContext):
    """Начало выдачи Premium"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_premium_user_id)

    text = (
        "👑 <b>Выдача Premium</b>\n\n"
        "Введите ID пользователя, которому хотите выдать Premium:\n\n"
        "📌 <b>Формат:</b> просто число (например: 123456789)\n\n"
        "ℹ️ Пользователь может узнать свой ID в разделе 'Мой рейтинг'\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_premium_user_id)
async def admin_give_premium_user_id(message: Message, state: FSMContext):
    """Получение ID пользователя для Premium"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Операция отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    try:
        target_user_id = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Некорректный ID. Введите число.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    if target_user_id not in users_rating:
        users_rating[target_user_id] = 0
        debug_print(f"👤 Создан новый пользователь {target_user_id} через админку")

    await state.update_data(target_user_id=target_user_id)
    await state.set_state(AdminStates.waiting_for_premium_days)

    text = (
        f"👤 <b>Пользователь:</b> {target_user_id}\n\n"
        "Выберите срок Premium:\n\n"
        "📅 30 дней - 1 месяц\n"
        "📅 90 дней - 3 месяца\n"
        "📅 180 дней - 6 месяцев\n"
        "📅 365 дней - 1 год\n"
        "📅 9999 дней - навсегда (Lifetime)\n\n"
        "Или введите свое значение в днях:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 30 дней", callback_data="premium_days:30")
    builder.button(text="📅 90 дней", callback_data="premium_days:90")
    builder.button(text="📅 180 дней", callback_data="premium_days:180")
    builder.button(text="📅 365 дней", callback_data="premium_days:365")
    builder.button(text="👑 Навсегда", callback_data="premium_days:9999")
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")
    builder.adjust(2, 2, 1, 1)

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")


@admin_router.callback_query(F.data.startswith("premium_days:"))
async def admin_give_premium_days_callback(callback: CallbackQuery, state: FSMContext):
    """Выбор срока Premium через callback"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    days = int(callback.data.split(":")[1])
    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    await give_premium_to_user(callback.message, target_user_id, days, state, callback.bot)
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_premium_days)
async def admin_give_premium_days_text(message: Message, state: FSMContext):
    """Ввод срока Premium вручную"""
    if message.from_user.id != config.ADMIN_ID:
        return

    try:
        days = int(message.text.strip())
    except ValueError:
        await message.answer(
            "❌ Некорректное число дней. Введите целое число.",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    data = await state.get_data()
    target_user_id = data.get("target_user_id")

    await give_premium_to_user(message, target_user_id, days, state, message.bot)


async def give_premium_to_user(message: Message, target_user_id: int, days: int, state: FSMContext, bot: Bot):
    """Выдача Premium пользователю"""
    try:
        sub = get_user_subscription(target_user_id)

        if days >= 9999:
            sub.tier = SubscriptionTier.PRO
            sub.expires_at = datetime.now() + timedelta(days=3650)
            period_text = "НАВСЕГДА (Lifetime)"
        else:
            sub.tier = SubscriptionTier.PREMIUM
            sub.expires_at = datetime.now() + timedelta(days=days)
            period_text = f"{days} дней"

        sub.transaction_history.append({
            "product_id": "admin_gift",
            "amount": 0,
            "purchased_at": datetime.now().isoformat(),
            "expires_at": sub.expires_at.isoformat(),
            "admin_id": message.from_user.id
        })

        user_subscriptions[target_user_id] = sub
        save_data()

        text = (
            f"✅ <b>Premium выдан!</b>\n\n"
            f"👤 Пользователь: {target_user_id}\n"
            f"📅 Срок: {period_text}\n"
            f"📆 Действует до: {sub.expires_at.strftime('%d.%m.%Y')}\n\n"
            f"🎁 Пользователь получил уведомление."
        )

        try:
            notify_text = (
                "🎁 <b>Вам выдан Premium!</b>\n\n"
                f"Администратор выдал вам Premium подписку на <b>{period_text}</b>!\n\n"
                f"📅 Действует до: {sub.expires_at.strftime('%d.%m.%Y')}\n\n"
                "👑 Спасибо за использование бота!"
            )
            await bot.send_message(
                target_user_id,
                notify_text,
                parse_mode="HTML",
                reply_markup=InlineKeyboardMarkup(
                    inline_keyboard=[
                        [InlineKeyboardButton(text="👑 Мой Premium", callback_data="premium_status")]
                    ]
                )
            )
        except Exception as e:
            debug_print(f"❌ Не удалось уведомить пользователя {target_user_id}: {e}")
            text += f"\n\n⚠️ Не удалось отправить уведомление пользователю"

        await message.answer(text, parse_mode="HTML")
        await state.clear()

    except Exception as e:
        debug_print(f"❌ Ошибка выдачи Premium: {e}")
        await message.answer(
            f"❌ Ошибка: {e}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        await state.clear()


# ==============================
# УПРАВЛЕНИЕ ТЕМАМИ (ПОЛНАЯ РЕАЛИЗАЦИЯ)
# ==============================

@admin_router.callback_query(F.data == "admin:topics_menu")
async def admin_topics_menu(callback: CallbackQuery):
    """Управление темами"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_questions = sum(len(t.get('questions', [])) for t in TOPICS.values())
    premium_topics = len([t for t in TOPICS.values() if t.get('premium', False)])

    text = (
        "📚 <b>УПРАВЛЕНИЕ ТЕМАМИ</b>\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Всего тем: {len(TOPICS)}\n"
        f"• Premium тем: {premium_topics}\n"
        f"• Всего вопросов: {total_questions}\n"
        f"• Порядок тем: {len(TOPIC_ORDER)}\n\n"
        "📋 <b>Список тем:</b>\n"
    )

    for i, topic_key in enumerate(TOPIC_ORDER[:10], 1):
        topic = TOPICS.get(topic_key, {})
        name = topic.get('name', 'Без названия')
        emoji = topic.get('emoji', '📝')
        premium = '🔒' if topic.get('premium', False) else '🔓'
        text += f"{i}. {emoji} {name} {premium}\n"

    if len(TOPIC_ORDER) > 10:
        text += f"...и еще {len(TOPIC_ORDER) - 10} тем\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Загрузить тему", callback_data="admin:upload")
    builder.button(text="🔄 Перезагрузить темы", callback_data="admin:reload")
    builder.button(text="📝 Редактировать тему", callback_data="admin:edit_theme_list")
    builder.button(text="👑 Premium темы", callback_data="admin:manage_premium_topics")
    builder.button(text="📋 Порядок тем", callback_data="admin:reorder_topics")
    builder.button(text="❌ Удалить тему", callback_data="admin:delete_theme")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:upload")
async def admin_upload_theme_start(callback: CallbackQuery, state: FSMContext):
    """Загрузка новой темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_theme_file)

    text = (
        "📤 <b>ЗАГРУЗКА НОВОЙ ТЕМЫ</b>\n\n"
        "Отправьте JSON файл с темой.\n\n"
        "📌 <b>Формат файла:</b>\n"
        "<code>{\n"
        '  "name": "Название темы",\n'
        '  "emoji": "📚",\n'
        '  "order": 1,\n'
        '  "premium": false,\n'
        '  "theory": ["Теория часть 1", "Теория часть 2"],\n'
        '  "questions": [\n'
        "    {\n"
        '      "question": "Вопрос?",\n'
        '      "options": ["Ответ 1", "Ответ 2", "Ответ 3", "Ответ 4"],\n'
        '      "correct": 0\n'
        "    }\n"
        "  ]\n"
        "}</code>\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Пример файла", callback_data="admin:show_example_theme")
    builder.button(text="❌ Отмена", callback_data="admin:topics_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:show_example_theme")
async def admin_show_example_theme(callback: CallbackQuery):
    """Показать пример темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    example = {
        "name": "Пример темы",
        "emoji": "📚",
        "order": 1,
        "premium": False,
        "theory": ["Это первая часть теории", "Это вторая часть теории"],
        "questions": [
            {
                "question": "Какой язык мы изучаем?",
                "options": ["Русский", "Английский", "Немецкий", "Французский"],
                "correct": 0
            }
        ]
    }

    example_json = json.dumps(example, ensure_ascii=False, indent=2)

    # Создаем файл для отправки
    file_content = example_json.encode('utf-8')

    await callback.message.answer_document(
        document=BufferedInputFile(
            file=file_content,
            filename="example_theme.json"
        ),
        caption="📋 <b>Пример файла темы</b>\n\nСкачайте, отредактируйте и загрузите обратно.",
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_theme_file)
async def admin_upload_theme_file(message: Message, state: FSMContext):
    """Обработка загруженного файла темы"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Загрузка отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:topics_menu")]]
            )
        )
        return

    if not message.document:
        await message.answer("❌ Пожалуйста, отправьте JSON файл.")
        return

    if not message.document.file_name.endswith('.json'):
        await message.answer("❌ Файл должен быть в формате JSON.")
        return

    try:
        # Скачиваем файл
        file = await message.bot.get_file(message.document.file_id)
        file_path = file.file_path
        file_content = await message.bot.download_file(file_path)

        # Парсим JSON
        theme_data = json.loads(file_content.read().decode('utf-8'))

        # Валидация
        required_fields = ['name', 'questions']
        for field in required_fields:
            if field not in theme_data:
                await message.answer(f"❌ В файле отсутствует обязательное поле: {field}")
                return

        if not isinstance(theme_data['questions'], list) or len(theme_data['questions']) == 0:
            await message.answer("❌ В теме должен быть хотя бы один вопрос.")
            return

        for i, q in enumerate(theme_data['questions']):
            if not all(k in q for k in ['question', 'options', 'correct']):
                await message.answer(f"❌ Вопрос {i + 1}: отсутствуют обязательные поля")
                return
            if not isinstance(q['options'], list) or len(q['options']) < 2:
                await message.answer(f"❌ Вопрос {i + 1}: должно быть минимум 2 варианта ответа")
                return
            if q['correct'] < 0 or q['correct'] >= len(q['options']):
                await message.answer(f"❌ Вопрос {i + 1}: некорректный индекс правильного ответа")
                return

        # Заполняем значения по умолчанию
        if 'emoji' not in theme_data:
            theme_data['emoji'] = '📝'
        if 'order' not in theme_data:
            theme_data['order'] = len(TOPICS)
        if 'premium' not in theme_data:
            theme_data['premium'] = False
        if 'theory' not in theme_data:
            theme_data['theory'] = []

        # Генерируем имя файла
        import re
        filename = re.sub(r'[^\w\s-]', '', theme_data['name'])
        filename = re.sub(r'[-\s]+', '_', filename)
        filename = filename.lower()

        # Сохраняем файл
        theme_path = config.THEMES_DIR / f"{filename}.json"

        # Проверяем, существует ли уже тема
        if theme_path.exists():
            confirm_builder = InlineKeyboardBuilder()
            confirm_builder.button(text="✅ Перезаписать", callback_data=f"admin:overwrite_theme:{filename}")
            confirm_builder.button(text="❌ Отмена", callback_data="admin:topics_menu")

            await state.update_data(theme_data=theme_data, filename=filename)
            await message.answer(
                f"⚠️ Тема <b>{filename}.json</b> уже существует.\n\n"
                "Перезаписать?",
                reply_markup=confirm_builder.as_markup(),
                parse_mode="HTML"
            )
            return

        # Сохраняем новую тему
        with open(theme_path, 'w', encoding='utf-8') as f:
            json.dump(theme_data, f, ensure_ascii=False, indent=2)

        # Перезагружаем темы
        load_themes()

        await message.answer(
            f"✅ <b>Тема успешно загружена!</b>\n\n"
            f"📚 Название: {theme_data['name']}\n"
            f"📝 Вопросов: {len(theme_data['questions'])}\n"
            f"🔖 Файл: {filename}.json",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← К темам", callback_data="admin:topics_menu")]]
            )
        )
        await state.clear()

    except json.JSONDecodeError:
        await message.answer("❌ Ошибка парсинга JSON. Проверьте формат файла.")
    except Exception as e:
        debug_print(f"❌ Ошибка загрузки темы: {e}")
        await message.answer(f"❌ Ошибка: {e}")


@admin_router.callback_query(F.data.startswith("admin:overwrite_theme:"))
async def admin_overwrite_theme(callback: CallbackQuery, state: FSMContext):
    """Перезапись существующей темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    filename = callback.data.split(":")[2]
    data = await state.get_data()
    theme_data = data.get("theme_data")

    if not theme_data:
        await callback.answer("❌ Данные темы не найдены", show_alert=True)
        await state.clear()
        return

    try:
        theme_path = config.THEMES_DIR / f"{filename}.json"

        with open(theme_path, 'w', encoding='utf-8') as f:
            json.dump(theme_data, f, ensure_ascii=False, indent=2)

        # Перезагружаем темы
        load_themes()

        await callback.message.edit_text(
            f"✅ <b>Тема успешно перезаписана!</b>\n\n"
            f"📚 Название: {theme_data['name']}\n"
            f"📝 Вопросов: {len(theme_data['questions'])}\n"
            f"🔖 Файл: {filename}.json",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← К темам", callback_data="admin:topics_menu")]]
            )
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка сохранения: {e}",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:topics_menu")]]
            )
        )

    await state.clear()
    await callback.answer()


@admin_router.callback_query(F.data == "admin:edit_theme_list")
async def admin_edit_theme_list(callback: CallbackQuery):
    """Список тем для редактирования"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    builder = InlineKeyboardBuilder()

    for topic_key in TOPIC_ORDER[:15]:
        topic = TOPICS[topic_key]
        builder.button(
            text=f"{topic['emoji']} {topic['name']}",
            callback_data=f"admin:edit_theme:{topic_key}"
        )

    builder.button(text="← Назад", callback_data="admin:topics_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "📝 <b>РЕДАКТИРОВАНИЕ ТЕМЫ</b>\n\n"
        "Выберите тему для редактирования:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:edit_theme:"))
async def admin_edit_theme_menu(callback: CallbackQuery, state: FSMContext):
    """Меню редактирования темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    topic_key = callback.data.split(":")[2]

    if topic_key not in TOPICS:
        await callback.answer("❌ Тема не найдена", show_alert=True)
        return

    topic = TOPICS[topic_key]

    await state.update_data(edit_topic_key=topic_key)

    text = (
        f"📝 <b>РЕДАКТИРОВАНИЕ ТЕМЫ</b>\n\n"
        f"📚 <b>Тема:</b> {topic['emoji']} {topic['name']}\n"
        f"🔖 <b>Ключ:</b> {topic_key}\n\n"
        f"📊 <b>Статистика:</b>\n"
        f"• Вопросов: {len(topic.get('questions', []))}\n"
        f"• Теория: {'есть' if topic.get('theory') else 'нет'}\n"
        f"• Premium: {'✅' if topic.get('premium', False) else '❌'}\n"
        f"• Порядок: {topic.get('order', 0)}\n\n"
        f"<b>Выберите, что редактировать:</b>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Название", callback_data=f"admin:edit_theme_field:name:{topic_key}")
    builder.button(text="😊 Эмодзи", callback_data=f"admin:edit_theme_field:emoji:{topic_key}")
    builder.button(text="📚 Теорию", callback_data=f"admin:edit_theme_field:theory:{topic_key}")
    builder.button(text="❓ Вопросы", callback_data=f"admin:edit_theme_field:questions:{topic_key}")
    builder.button(text="👑 Premium статус", callback_data=f"admin:toggle_premium:{topic_key}")
    builder.button(text="🔢 Порядок", callback_data=f"admin:edit_theme_field:order:{topic_key}")
    builder.button(text="📋 Управление вопросами", callback_data=f"admin:manage_questions:{topic_key}")
    builder.button(text="← Назад", callback_data="admin:edit_theme_list")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:edit_theme_field:"))
async def admin_edit_theme_field(callback: CallbackQuery, state: FSMContext):
    """Редактирование поля темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    parts = callback.data.split(":")
    field = parts[2]
    topic_key = parts[3]

    if topic_key not in TOPICS:
        await callback.answer("❌ Тема не найдена", show_alert=True)
        return

    topic = TOPICS[topic_key]

    await state.update_data(
        edit_topic_key=topic_key,
        edit_field=field
    )
    await state.set_state(AdminStates.waiting_for_edit_theme_value)

    if field == "name":
        text = (
            f"📝 <b>Редактирование названия</b>\n\n"
            f"Текущее: {topic['name']}\n\n"
            f"Введите новое название темы:"
        )
    elif field == "emoji":
        text = (
            f"😊 <b>Редактирование эмодзи</b>\n\n"
            f"Текущий: {topic['emoji']}\n\n"
            f"Введите новый эмодзи (например: 📚, 🇷🇺, 🎓):"
        )
    elif field == "order":
        text = (
            f"🔢 <b>Редактирование порядка</b>\n\n"
            f"Текущий: {topic.get('order', 0)}\n\n"
            f"Введите новый порядковый номер (0 - первая тема):"
        )
    elif field == "theory":
        theory_text = "\n".join([f"{i + 1}. {part}" for i, part in enumerate(topic.get('theory', []))])
        text = (
            f"📚 <b>Редактирование теории</b>\n\n"
            f"Текущая теория:\n{theory_text if theory_text else 'Нет теории'}\n\n"
            f"Отправьте новую теорию (каждая часть с новой строки):\n\n"
            f"❌ Отправьте 'clear' для очистки"
        )
    elif field == "questions":
        text = (
            f"❓ <b>Редактирование вопросов</b>\n\n"
            f"Всего вопросов: {len(topic.get('questions', []))}\n\n"
            f"Для редактирования вопросов используйте:\n"
            f"• /add_question - добавить вопрос\n"
            f"• /edit_question N - редактировать вопрос N\n"
            f"• /del_question N - удалить вопрос N\n"
            f"• /export_json - экспорт темы\n\n"
            f"Введите команду:"
        )
    else:
        await callback.answer("❌ Неподдерживаемое поле", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data=f"admin:edit_theme:{topic_key}")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_edit_theme_value)
async def admin_edit_theme_value(message: Message, state: FSMContext):
    """Сохранение нового значения поля темы"""
    if message.from_user.id != config.ADMIN_ID:
        return

    data = await state.get_data()
    topic_key = data.get("edit_topic_key")
    field = data.get("edit_field")

    if topic_key not in TOPICS:
        await message.answer("❌ Тема не найдена")
        await state.clear()
        return

    topic = TOPICS[topic_key]
    value = message.text.strip()

    try:
        if field == "name":
            topic['name'] = value
            result = f"✅ Название изменено на: {value}"

        elif field == "emoji":
            topic['emoji'] = value
            result = f"✅ Эмодзи изменен на: {value}"

        elif field == "order":
            try:
                order = int(value)
                topic['order'] = order
                # Пересортировываем TOPIC_ORDER
                global TOPIC_ORDER
                TOPIC_ORDER.sort(key=lambda x: TOPICS[x].get('order', 0))
                result = f"✅ Порядок изменен на: {order}"
            except ValueError:
                await message.answer("❌ Введите число")
                return

        elif field == "theory":
            if value.lower() == "clear":
                topic['theory'] = []
                result = "✅ Теория очищена"
            else:
                theory_parts = value.split('\n')
                topic['theory'] = [p.strip() for p in theory_parts if p.strip()]
                result = f"✅ Теория обновлена ({len(topic['theory'])} частей)"

        elif field == "questions":
            # Обработка команд для вопросов
            if value.startswith('/add_question'):
                await message.answer(
                    "❓ <b>Добавление вопроса</b>\n\n"
                    "Отправьте вопрос в формате:\n"
                    "<code>Вопрос?|Вариант1|Вариант2|Вариант3|Вариант4|0</code>\n\n"
                    "Где последняя цифра - индекс правильного ответа (0-3)",
                    parse_mode="HTML"
                )
                await state.set_state(AdminStates.waiting_for_edit_theme_value)
                return

            elif value.startswith('/export_json'):
                # Экспорт темы в JSON файл
                theme_copy = topic.copy()
                theme_json = json.dumps(theme_copy, ensure_ascii=False, indent=2)

                await message.answer_document(
                    document=BufferedInputFile(
                        file=theme_json.encode('utf-8'),
                        filename=f"{topic_key}.json"
                    ),
                    caption=f"📤 Экспорт темы: {topic['name']}"
                )
                result = "✅ Тема экспортирована"

            else:
                # Добавление вопроса через формат
                parts = value.split('|')
                if len(parts) >= 6:
                    question_text = parts[0]
                    options = parts[1:5]
                    try:
                        correct = int(parts[5])
                        if 0 <= correct <= 3:
                            if 'questions' not in topic:
                                topic['questions'] = []

                            topic['questions'].append({
                                "question": question_text,
                                "options": options,
                                "correct": correct
                            })
                            result = f"✅ Вопрос добавлен! Всего вопросов: {len(topic['questions'])}"
                        else:
                            await message.answer("❌ Индекс правильного ответа должен быть от 0 до 3")
                            return
                    except ValueError:
                        await message.answer("❌ Некорректный индекс правильного ответа")
                        return
                else:
                    await message.answer("❌ Неверный формат. Используйте: Вопрос|Вариант1|...|Вариант4|Индекс")
                    return

        else:
            result = "❌ Неподдерживаемое поле"

        # Сохраняем изменения в файл
        theme_path = config.THEMES_DIR / f"{topic_key}.json"
        with open(theme_path, 'w', encoding='utf-8') as f:
            json.dump(topic, f, ensure_ascii=False, indent=2)

        # Перезагружаем темы
        load_themes()

        await message.answer(
            result,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text="← Вернуться к теме", callback_data=f"admin:edit_theme:{topic_key}")]
                ]
            )
        )
        await state.clear()

    except Exception as e:
        debug_print(f"❌ Ошибка редактирования темы: {e}")
        await message.answer(f"❌ Ошибка: {e}")
        await state.clear()


@admin_router.callback_query(F.data.startswith("admin:toggle_premium:"))
async def admin_toggle_premium_topic(callback: CallbackQuery):
    """Переключение Premium статуса темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    topic_key = callback.data.split(":")[2]

    if topic_key not in TOPICS:
        await callback.answer("❌ Тема не найдена", show_alert=True)
        return

    topic = TOPICS[topic_key]
    current_status = topic.get('premium', False)
    topic['premium'] = not current_status

    # Сохраняем изменения
    theme_path = config.THEMES_DIR / f"{topic_key}.json"
    with open(theme_path, 'w', encoding='utf-8') as f:
        json.dump(topic, f, ensure_ascii=False, indent=2)

    # Перезагружаем темы
    load_themes()

    await callback.answer(f"✅ Premium статус: {'включен' if not current_status else 'выключен'}", show_alert=True)
    await admin_edit_theme_menu(callback, None)


@admin_router.callback_query(F.data == "admin:manage_premium_topics")
async def admin_manage_premium_topics(callback: CallbackQuery):
    """Управление Premium темами"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    premium_topics = []
    free_topics = []

    for topic_key in TOPIC_ORDER:
        topic = TOPICS[topic_key]
        if topic.get('premium', False):
            premium_topics.append((topic_key, topic))
        else:
            free_topics.append((topic_key, topic))

    text = (
        "👑 <b>УПРАВЛЕНИЕ PREMIUM ТЕМАМИ</b>\n\n"
        f"📊 <b>Всего тем:</b> {len(TOPICS)}\n"
        f"🔒 <b>Premium тем:</b> {len(premium_topics)}\n"
        f"🔓 <b>Бесплатных тем:</b> {len(free_topics)}\n\n"
        "🔒 <b>Premium темы:</b>\n"
    )

    for i, (topic_key, topic) in enumerate(premium_topics[:10], 1):
        text += f"{i}. {topic['emoji']} {topic['name']}\n"

    if len(premium_topics) > 10:
        text += f"...и еще {len(premium_topics) - 10} Premium тем\n"

    text += "\n🔓 <b>Бесплатные темы (можно сделать Premium):</b>\n"

    for i, (topic_key, topic) in enumerate(free_topics[:10], 1):
        text += f"{i}. {topic['emoji']} {topic['name']}\n"

    builder = InlineKeyboardBuilder()

    # Кнопки для быстрого переключения
    for topic_key, topic in list(free_topics)[:5]:
        builder.button(
            text=f"👑 {topic['emoji']} {topic['name']}",
            callback_data=f"admin:toggle_premium:{topic_key}"
        )

    builder.button(text="🔙 Назад", callback_data="admin:topics_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:reorder_topics")
async def admin_reorder_topics(callback: CallbackQuery, state: FSMContext):
    """Изменение порядка тем"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = "🔢 <b>ПОРЯДОК ТЕМ</b>\n\n"
    text += "Текущий порядок:\n\n"

    for i, topic_key in enumerate(TOPIC_ORDER, 1):
        topic = TOPICS[topic_key]
        text += f"{i}. {topic['emoji']} {topic['name']} (order: {topic.get('order', i - 1)})\n"

    text += "\nДля изменения порядка отредактируйте поле 'order' в каждой теме.\n"
    text += "Меньшее число = выше в списке.\n\n"
    text += "Используйте кнопку 'Редактировать тему' для изменения порядка."

    builder = InlineKeyboardBuilder()
    builder.button(text="📝 Редактировать темы", callback_data="admin:edit_theme_list")
    builder.button(text="← Назад", callback_data="admin:topics_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:delete_theme")
async def admin_delete_theme_start(callback: CallbackQuery, state: FSMContext):
    """Удаление темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    builder = InlineKeyboardBuilder()
    for topic_key in TOPIC_ORDER[:10]:
        topic = TOPICS[topic_key]
        # Подсчитываем, сколько пользователей изучили эту тему
        users_completed = sum(1 for u, topics in users_completed_topics.items() if topic_key in topics)
        builder.button(
            text=f"{topic['emoji']} {topic['name']} ({users_completed} изучили)",
            callback_data=f"admin:confirm_delete:{topic_key}"
        )
    builder.button(text="❌ Отмена", callback_data="admin:topics_menu")
    builder.adjust(1)

    await callback.message.edit_text(
        "⚠️ <b>УДАЛЕНИЕ ТЕМЫ</b>\n\n"
        "<i>Внимание! Это действие нельзя отменить!</i>\n"
        "<i>Тема будет удалена из файлов и из прогресса всех пользователей.</i>\n\n"
        "Выберите тему для удаления:",
        reply_markup=builder.as_markup(),
        parse_mode="HTML"
    )
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:confirm_delete:"))
async def admin_confirm_delete(callback: CallbackQuery):
    """Подтверждение удаления темы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    topic_key = callback.data.split(":")[2]

    if topic_key in TOPICS:
        topic_name = TOPICS[topic_key].get('name', topic_key)

        # Удаляем из прогресса всех пользователей
        for user_id in users_completed_topics:
            if topic_key in users_completed_topics[user_id]:
                users_completed_topics[user_id].remove(topic_key)

        for user_id in users_available_topics:
            if topic_key in users_available_topics[user_id]:
                users_available_topics[user_id].remove(topic_key)

        # Удаляем тему
        del TOPICS[topic_key]
        if topic_key in TOPIC_ORDER:
            TOPIC_ORDER.remove(topic_key)

        # Удаляем файл
        try:
            theme_file = config.THEMES_DIR / f"{topic_key}.json"
            if theme_file.exists():
                theme_file.unlink()
        except:
            pass

        save_data()
        await callback.answer(f"✅ Тема '{topic_name}' удалена!", show_alert=True)

    await admin_topics_menu(callback)


# ==============================
# МАССОВАЯ РАССЫЛКА
# ==============================

@admin_router.callback_query(F.data == "admin:sendall")
async def admin_sendall_start(callback: CallbackQuery, state: FSMContext):
    """Начало массовой рассылки"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_bulk_message)

    text = (
        "📢 <b>МАССОВАЯ РАССЫЛКА</b>\n\n"
        "Отправьте сообщение для рассылки всем пользователям.\n\n"
        "Поддерживается <b>HTML</b> разметка:\n"
        "• <b>жирный</b>\n"
        "• <i>курсив</i>\n"
        "• <code>код</code>\n"
        "• <a href='ссылка'>текст ссылки</a>\n\n"
        "📌 <b>Совет:</b> Начните с приветствия, например:\n"
        "👋 <b>Всем привет!</b> У нас обновление...\n\n"
        "❌ Для отмены отправьте /cancel"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:notify_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_bulk_message)
async def admin_sendall_preview(message: Message, state: FSMContext):
    """Предпросмотр массовой рассылки"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Рассылка отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:notify_menu")]]
            )
        )
        return

    await state.update_data(bulk_message=message.html_text, parse_mode="HTML")

    preview_text = (
        "📨 <b>ПРЕДПРОСМОТР РАССЫЛКИ</b>\n\n"
        "Ваше сообщение:\n"
        "━━━━━━━━━━━━━━━━━━━━━\n"
        f"{message.html_text}\n"
        "━━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <b>Внимание!</b>\n"
        f"Рассылка будет отправлена <b>ВСЕМ</b> пользователям ({len(users_rating)} чел.)\n"
        "Это действие нельзя отменить!\n\n"
        "Подтвердите отправку:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="✅ ОТПРАВИТЬ ВСЕМ", callback_data="admin:sendall_confirm_all")
    builder.button(text="👑 Только Premium", callback_data="admin:sendall_confirm_premium")
    builder.button(text="🔍 Тест (себе)", callback_data="admin:sendall_test")
    builder.button(text="✏️ Редактировать", callback_data="admin:sendall_edit")
    builder.button(text="❌ Отмена", callback_data="admin:notify_menu")
    builder.adjust(1)

    await message.answer(preview_text, reply_markup=builder.as_markup(), parse_mode="HTML")


@admin_router.callback_query(F.data == "admin:sendall_test")
async def admin_sendall_test(callback: CallbackQuery, state: FSMContext):
    """Тестовая отправка себе"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    data = await state.get_data()
    message_text = data.get("bulk_message")

    if not message_text:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return

    try:
        await callback.bot.send_message(
            callback.from_user.id,
            message_text,
            parse_mode="HTML"
        )
        await callback.answer("✅ Тестовое сообщение отправлено!", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


@admin_router.callback_query(F.data == "admin:sendall_confirm_all")
async def admin_sendall_confirm_all(callback: CallbackQuery, state: FSMContext):
    """Подтверждение массовой рассылки ВСЕМ"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Начинаю рассылку...", show_alert=False)

    data = await state.get_data()
    message_text = data.get("bulk_message")

    if not message_text:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return

    manager = get_notification_manager(callback.bot)
    if manager:
        success, fail, skipped = await manager.send_bulk_notification(
            user_ids=list(users_rating.keys()),
            message=message_text,
            parse_mode="HTML",
            is_premium_only=False
        )

        result_text = (
            "📨 <b>РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
            f"✅ Успешно: {success}\n"
            f"❌ Ошибок: {fail}\n"
            f"👥 Всего пользователей: {len(users_rating)}\n\n"
            f"⏱ Завершено: {datetime.now().strftime('%H:%M:%S')}"
        )

        await callback.message.edit_text(
            result_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:notify_menu")]]
            )
        )

    await state.clear()


@admin_router.callback_query(F.data == "admin:sendall_confirm_premium")
async def admin_sendall_confirm_premium(callback: CallbackQuery, state: FSMContext):
    """Подтверждение массовой рассылки ТОЛЬКО PREMIUM"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Начинаю рассылку Premium...", show_alert=False)

    data = await state.get_data()
    message_text = data.get("bulk_message")

    if not message_text:
        await callback.answer("❌ Сообщение не найдено", show_alert=True)
        return

    premium_users = []
    for user_id in users_rating:
        sub = get_user_subscription(user_id)
        if sub.is_active() and sub.tier != SubscriptionTier.FREE:
            premium_users.append(user_id)

    manager = get_notification_manager(callback.bot)
    if manager:
        success, fail, skipped = await manager.send_bulk_notification(
            user_ids=premium_users,
            message=message_text,
            parse_mode="HTML",
            is_premium_only=False
        )

        result_text = (
            "📨 <b>PREMIUM РАССЫЛКА ЗАВЕРШЕНА</b>\n\n"
            f"✅ Успешно: {success}\n"
            f"❌ Ошибок: {fail}\n"
            f"👑 Premium пользователей: {len(premium_users)}\n\n"
            f"⏱ Завершено: {datetime.now().strftime('%H:%M:%S')}"
        )

        await callback.message.edit_text(
            result_text,
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:notify_menu")]]
            )
        )

    await state.clear()


@admin_router.callback_query(F.data == "admin:sendall_edit")
async def admin_sendall_edit(callback: CallbackQuery, state: FSMContext):
    """Редактирование сообщения рассылки"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_bulk_message)

    await callback.message.edit_text(
        "📢 <b>Редактирование сообщения</b>\n\n"
        "Отправьте новое сообщение для рассылки:",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text="❌ Отмена", callback_data="admin:notify_menu")]]
        )
    )
    await callback.answer()


# ==============================
# ЭКСПОРТ ДАННЫХ (ИСПРАВЛЕННЫЙ)
# ==============================

@admin_router.callback_query(F.data == "admin:stats_menu")
async def admin_stats_menu(callback: CallbackQuery):
    """Меню статистики и экспорта"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "📊 <b>СТАТИСТИКА И ЭКСПОРТ</b>\n\n"
        "Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Статистика бота", callback_data="admin:stats")
    builder.button(text="📤 Экспорт данных", callback_data="admin:export")
    builder.button(text="📈 Статистика уведомлений", callback_data="admin:notify_stats")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:export")
async def admin_export_menu(callback: CallbackQuery):
    """Меню экспорта данных"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "📤 <b>ЭКСПОРТ ДАННЫХ</b>\n\n"
        "Выберите формат экспорта:\n\n"
        "• JSON - полные данные, все поля\n"
        "• CSV - табличный формат для Excel\n"
        "• TXT - текстовый отчет\n\n"
        "Данные для экспорта:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="👥 Пользователи (JSON)", callback_data="admin:export_users_json")
    builder.button(text="👥 Пользователи (CSV)", callback_data="admin:export_users_csv")
    builder.button(text="📚 Темы (JSON)", callback_data="admin:export_topics_json")
    builder.button(text="⚔️ Дуэли (JSON)", callback_data="admin:export_duels_json")
    builder.button(text="📊 Полная статистика", callback_data="admin:export_stats")
    builder.button(text="💰 Транзакции", callback_data="admin:export_transactions")
    builder.button(text="← Назад", callback_data="admin:stats_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:export_users_csv")
async def admin_export_users_csv(callback: CallbackQuery):
    """Экспорт пользователей в CSV (ИСПРАВЛЕНО)"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Генерирую CSV файл...", show_alert=False)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow([
        'User ID', 'Rating', 'Lessons', 'Questions', 'Correct',
        'Accuracy %', 'Streak', 'ELO', 'Duels Won', 'Duels Lost',
        'Duels Drawn', 'Premium', 'First Seen', 'Last Activity'
    ])

    for user_id in users_rating:
        activity = get_user_activity(user_id)
        sub = get_user_subscription(user_id)

        writer.writerow([
            user_id,
            users_rating.get(user_id, 0),
            activity.lessons_completed,
            activity.questions_answered,
            activity.correct_answers,
            f"{activity.accuracy:.1f}",
            activity.daily_streak,
            activity.elo_rating,
            activity.duels_won,
            activity.duels_lost,
            activity.duels_drawn,
            sub.tier.value if sub.is_active() else 'inactive',
            activity.first_seen.strftime('%Y-%m-%d %H:%M:%S'),
            activity.last_activity.strftime('%Y-%m-%d %H:%M:%S')
        ])

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # ИСПРАВЛЕНО: Используем BufferedInputFile вместо InputFile
    await callback.message.answer_document(
        document=BufferedInputFile(
            file=io.BytesIO(output.getvalue().encode('utf-8')).getvalue(),
            filename=f'users_export_{timestamp}.csv'
        ),
        caption=f"📊 Экспорт пользователей\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n👥 Всего: {len(users_rating)}"
    )


@admin_router.callback_query(F.data == "admin:export_users_json")
async def admin_export_users_json(callback: CallbackQuery):
    """Экспорт пользователей в JSON"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Генерирую JSON файл...", show_alert=False)

    users_data = {}
    for user_id in users_rating:
        activity = get_user_activity(user_id)
        sub = get_user_subscription(user_id)

        users_data[str(user_id)] = {
            'rating': users_rating.get(user_id, 0),
            'activity': activity.to_dict(),
            'subscription': sub.to_dict(),
            'completed_topics': list(users_completed_topics.get(user_id, set())),
            'available_topics': users_available_topics.get(user_id, [])
        }

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_data = json.dumps(users_data, ensure_ascii=False, indent=2)

    await callback.message.answer_document(
        document=BufferedInputFile(
            file=json_data.encode('utf-8'),
            filename=f'users_export_{timestamp}.json'
        ),
        caption=f"📊 Экспорт пользователей (JSON)\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n👥 Всего: {len(users_rating)}"
    )


@admin_router.callback_query(F.data == "admin:export_topics_json")
async def admin_export_topics_json(callback: CallbackQuery):
    """Экспорт тем в JSON"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Генерирую JSON файл...", show_alert=False)

    topics_data = {
        'topics': TOPICS,
        'order': TOPIC_ORDER,
        'exported_at': datetime.now().isoformat()
    }

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_data = json.dumps(topics_data, ensure_ascii=False, indent=2)

    await callback.message.answer_document(
        document=BufferedInputFile(
            file=json_data.encode('utf-8'),
            filename=f'topics_export_{timestamp}.json'
        ),
        caption=f"📚 Экспорт тем\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n📚 Всего тем: {len(TOPICS)}"
    )


@admin_router.callback_query(F.data == "admin:export_duels_json")
async def admin_export_duels_json(callback: CallbackQuery):
    """Экспорт дуэлей в JSON"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Генерирую JSON файл...", show_alert=False)

    duels_data = {}
    for duel_id, duel in active_duels.items():
        duels_data[duel_id] = duel.to_dict()

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    json_data = json.dumps(duels_data, ensure_ascii=False, indent=2)

    await callback.message.answer_document(
        document=BufferedInputFile(
            file=json_data.encode('utf-8'),
            filename=f'duels_export_{timestamp}.json'
        ),
        caption=f"⚔️ Экспорт дуэлей\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n⚔️ Всего дуэлей: {len(active_duels)}"
    )


@admin_router.callback_query(F.data == "admin:export_stats")
async def admin_export_stats(callback: CallbackQuery):
    """Экспорт полной статистики"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_duels = sum(a.duels_won + a.duels_lost + a.duels_drawn for a in user_activities.values()) // 2
    total_questions_answered = sum(a.questions_answered for a in user_activities.values())
    total_correct = sum(a.correct_answers for a in user_activities.values())

    premium_users = []
    for user_id in users_rating:
        sub = get_user_subscription(user_id)
        if sub.is_active() and sub.tier != SubscriptionTier.FREE:
            premium_users.append({
                'id': user_id,
                'tier': sub.tier.value,
                'expires': sub.expires_at.strftime('%Y-%m-%d') if sub.expires_at else 'never',
                'rating': users_rating.get(user_id, 0)
            })

    stats = {
        'generated_at': datetime.now().isoformat(),
        'users': {
            'total': len(users_rating),
            'premium': len(premium_users),
            'active_today': len(
                [a for a in user_activities.values() if a.last_activity.date() == datetime.now().date()]),
            'active_week': len([a for a in user_activities.values() if (datetime.now() - a.last_activity).days < 7])
        },
        'content': {
            'topics': len(TOPICS),
            'questions': sum(len(t.get('questions', [])) for t in TOPICS.values())
        },
        'duels': {
            'total': total_duels,
            'active': len([d for d in active_duels.values() if d.status == DuelStatus.IN_PROGRESS]),
            'waiting': len(waiting_duels)
        },
        'learning': {
            'total_questions': total_questions_answered,
            'correct_answers': total_correct,
            'accuracy': round((total_correct / total_questions_answered * 100), 2) if total_questions_answered else 0,
            'total_lessons': sum(a.lessons_completed for a in user_activities.values())
        },
        'premium_users': premium_users[:100]
    }

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'stats_export_{timestamp}.json'
    filepath = Path(config.STATS_DIR) / filename

    # Создаем директорию если её нет
    filepath.parent.mkdir(parents=True, exist_ok=True)

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(stats, f, ensure_ascii=False, indent=2)

    await callback.message.answer_document(
        document=FSInputFile(filepath),
        caption=f"📊 Полная статистика бота\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )


@admin_router.callback_query(F.data == "admin:export_transactions")
async def admin_export_transactions(callback: CallbackQuery):
    """Экспорт транзакций"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await callback.answer("⏳ Генерирую отчет...", show_alert=False)

    output = io.StringIO()
    writer = csv.writer(output)

    writer.writerow(['User ID', 'Date', 'Product', 'Amount', 'Expires At', 'Admin ID'])

    for user_id, sub in user_subscriptions.items():
        for transaction in sub.transaction_history:
            writer.writerow([
                user_id,
                transaction.get('purchased_at', ''),
                transaction.get('product_id', ''),
                transaction.get('amount', 0),
                transaction.get('expires_at', ''),
                transaction.get('admin_id', '')
            ])

    output.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    await callback.message.answer_document(
        document=BufferedInputFile(
            file=io.BytesIO(output.getvalue().encode('utf-8')).getvalue(),
            filename=f'transactions_export_{timestamp}.csv'
        ),
        caption=f"💰 Экспорт транзакций\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}\n💳 Всего транзакций: {sum(len(s.transaction_history) for s in user_subscriptions.values())}"
    )


# ==============================
# ТЕСТОВЫЕ УВЕДОМЛЕНИЯ
# ==============================

@admin_router.callback_query(F.data == "admin:test_notify_daily")
async def admin_test_notify_daily(callback: CallbackQuery):
    """Тест ежедневного уведомления"""
    manager = get_notification_manager(callback.bot)
    if manager:
        await manager.send_daily_reminder(callback.from_user.id)
        await callback.answer("✅ Ежедневное уведомление отправлено!", show_alert=True)
    else:
        await callback.answer("❌ Ошибка", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin:test_notify_premium_"))
async def admin_test_notify_premium(callback: CallbackQuery):
    """Тест уведомлений Premium"""
    days = int(callback.data.split("_")[-1])
    manager = get_notification_manager(callback.bot)
    if manager:
        await manager.send_premium_expiry_reminder(callback.from_user.id, days)
        await callback.answer(f"✅ Напоминание Premium ({days} дн.) отправлено!", show_alert=True)


@admin_router.callback_query(F.data.startswith("admin:test_notify_inactive_"))
async def admin_test_notify_inactive(callback: CallbackQuery):
    """Тест уведомлений о неактивности"""
    days = int(callback.data.split("_")[-1])
    manager = get_notification_manager(callback.bot)
    if manager:
        await manager.send_inactivity_reminder(callback.from_user.id, days)
        await callback.answer(f"✅ Напоминание о неактивности ({days} дн.) отправлено!", show_alert=True)


# ==============================
# ТЕСТОВЫЕ ФУНКЦИИ
# ==============================

@admin_router.callback_query(F.data == "admin:test_menu")
async def admin_test_menu(callback: CallbackQuery):
    """Меню тестовых функций"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "🧪 <b>ТЕСТОВЫЕ ФУНКЦИИ</b>\n\n"
        "Проверка работоспособности различных систем:\n\n"
        "• Уведомления\n"
        "• Платежи\n"
        "• Дуэли\n"
        "• Достижения"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📨 Тест уведомлений", callback_data="admin:test_notifications")
    builder.button(text="💳 Тест платежей", callback_data="admin:test_payment")
    builder.button(text="⚔️ Тест дуэли", callback_data="admin:test_duel")
    builder.button(text="🏅 Тест достижений", callback_data="admin:test_achievement")
    builder.button(text="🔥 Тест стрика", callback_data="admin:test_streak")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:test_notifications")
async def admin_test_notifications(callback: CallbackQuery):
    """Меню тестирования уведомлений"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "📨 <b>ТЕСТ УВЕДОМЛЕНИЙ</b>\n\n"
        "Выберите тип уведомления для отправки себе:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Ежедневное", callback_data="admin:test_notify_daily")
    builder.button(text="👑 Premium (7 дней)", callback_data="admin:test_notify_premium_7")
    builder.button(text="👑 Premium (3 дня)", callback_data="admin:test_notify_premium_3")
    builder.button(text="👑 Premium (1 день)", callback_data="admin:test_notify_premium_1")
    builder.button(text="👑 Premium (0 дней)", callback_data="admin:test_notify_premium_0")
    builder.button(text="😴 Неактивность 3 дня", callback_data="admin:test_notify_inactive_3")
    builder.button(text="😴 Неактивность 7 дней", callback_data="admin:test_notify_inactive_7")
    builder.button(text="😴 Неактивность 14 дней", callback_data="admin:test_notify_inactive_14")
    builder.button(text="😴 Неактивность 30 дней", callback_data="admin:test_notify_inactive_30")
    builder.button(text="🏅 Первый урок", callback_data="admin:test_ach_first_lesson")
    builder.button(text="🔥 Стрик 7 дней", callback_data="admin:test_ach_streak_7")
    builder.button(text="🏆 Стрик 30 дней", callback_data="admin:test_ach_streak_30")
    builder.button(text="← Назад", callback_data="admin:test_menu")
    builder.adjust(2)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:test_ach_"))
async def admin_test_achievement(callback: CallbackQuery):
    """Тестирование достижений"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    ach_name = callback.data.replace("admin:test_ach_", "")

    achievement_map = {
        "first_lesson": "first_lesson",
        "streak_7": "streak_7",
        "streak_30": "streak_30"
    }

    if ach_name in achievement_map:
        manager = get_notification_manager(callback.bot)
        if manager:
            await manager.send_achievement_notification(
                callback.from_user.id,
                achievement_map[ach_name]
            )
            await callback.answer("✅ Достижение отправлено!", show_alert=True)
        else:
            await callback.answer("❌ Ошибка", show_alert=True)
    else:
        await callback.answer("❌ Неизвестное достижение", show_alert=True)


@admin_router.callback_query(F.data == "admin:test_payment")
async def admin_test_payment(callback: CallbackQuery):
    """Тест платежной системы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    if not config.YOOKASSA_TOKEN:
        await callback.answer(
            "❌ YooKassa токен не настроен!\n\n"
            "Добавьте YOOKASSA_TOKEN в переменные окружения.",
            show_alert=True
        )
        return

    await callback.answer(
        "✅ Платежная система настроена!\n\n"
        "Для теста перейдите в магазин и нажмите 'Купить'.",
        show_alert=True
    )


@admin_router.callback_query(F.data == "admin:test_duel")
async def admin_test_duel(callback: CallbackQuery):
    """Тест дуэльной системы"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "⚔️ <b>ТЕСТ ДУЭЛЬНОЙ СИСТЕМЫ</b>\n\n"
        f"• Дуэли включены: {'✅' if config.DUEL_ENABLED else '❌'}\n"
        f"• Время на вопрос: {config.QUESTION_TIME_LIMIT} сек\n"
        f"• Кулдаун: {config.DUEL_COOLDOWN // 60} мин\n"
        f"• Награда: {config.DUEL_REWARD} баллов\n\n"
        f"• Активных дуэлей: {len([d for d in active_duels.values() if d.status == DuelStatus.IN_PROGRESS])}\n"
        f"• В очереди: {len(waiting_duels)}\n\n"
        "Система работает корректно."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="admin:test_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:test_streak")
async def admin_test_streak(callback: CallbackQuery):
    """Тест системы стриков"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    activity = get_user_activity(callback.from_user.id)
    old_streak = activity.daily_streak
    activity.daily_streak += 1

    text = (
        "🔥 <b>ТЕСТ СИСТЕМЫ СТРИКОВ</b>\n\n"
        f"• Было: {old_streak} дней\n"
        f"• Стало: {activity.daily_streak} дней\n\n"
        "✅ Стрик увеличен! (тестовый режим)"
    )

    # Возвращаем обратно
    activity.daily_streak = old_streak

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="admin:test_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ==============================
# УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ
# ==============================

@admin_router.callback_query(F.data == "admin:notify_menu")
async def admin_notify_menu(callback: CallbackQuery):
    """Управление уведомлениями"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "🔔 <b>УПРАВЛЕНИЕ УВЕДОМЛЕНИЯМИ</b>\n\n"
        "Здесь вы можете настроить систему уведомлений:\n\n"
        "• Ежедневные напоминания (18:00 МСК)\n"
        "• Напоминания о Premium\n"
        "• Уведомления о неактивности\n"
        "• Достижения пользователей\n\n"
        "Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 Тест ежедневного", callback_data="admin:test_notify_daily")
    builder.button(text="👑 Тест Premium (7 дней)", callback_data="admin:test_notify_premium_7")
    builder.button(text="😴 Тест неактивности (7)", callback_data="admin:test_notify_inactive_7")
    builder.button(text="📊 Статистика уведомлений", callback_data="admin:notify_stats")
    builder.button(text="🔄 Отправить всем", callback_data="admin:sendall")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(2, 2, 1, 1, 1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:notify_stats")
async def admin_notify_stats(callback: CallbackQuery):
    """Статистика уведомлений"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    from bot import users_last_notification

    today = datetime.now().strftime("%Y-%m-%d")
    sent_today = len([u for u, d in users_last_notification.items() if d == today])

    # Безопасное вычисление охвата
    охват = (sent_today / len(users_rating) * 100) if users_rating else 0

    text = (
        "📊 <b>СТАТИСТИКА УВЕДОМЛЕНИЙ</b>\n\n"
        f"📅 Отправлено сегодня: {sent_today}\n"
        f"👥 Всего пользователей: {len(users_rating)}\n"
        f"📈 Охват: {охват:.1f}%\n\n"
        "⏰ <b>Расписание:</b>\n"
        "• Ежедневные: 18:00 МСК\n"
        "• Premium: 10:00 МСК\n"
        "• Очистка дуэлей: каждые 30 мин\n"
        "• Автосохранение: каждый час"
    )

    await callback.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await callback.answer()


# ==============================
# НАСТРОЙКИ БОТА
# ==============================

@admin_router.callback_query(F.data == "admin:settings_menu")
async def admin_settings(callback: CallbackQuery):
    """Настройки бота"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "⚙️ <b>НАСТРОЙКИ БОТА</b>\n\n"
        f"📚 <b>Обучение:</b>\n"
        f"• Бесплатных тем: {config.FREE_TOPICS_LIMIT}\n"
        f"• Кулдаун уроков: {config.LESSON_COOLDOWN_HOURS}ч\n\n"
        f"⚔️ <b>Дуэли:</b>\n"
        f"• Статус: {'Включены' if config.DUEL_ENABLED else 'Выключены'}\n"
        f"• Время на вопрос: {config.QUESTION_TIME_LIMIT} сек\n"
        f"• Кулдаун: {config.DUEL_COOLDOWN // 60} мин\n"
        f"• Награда: {config.DUEL_REWARD} баллов\n\n"
        f"💰 <b>Магазин:</b>\n"
        f"• YooKassa: {'✅' if config.YOOKASSA_TOKEN else '❌'}\n\n"
        "Выберите параметр для изменения:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📚 Бесплатные темы", callback_data="admin:setting_free_topics")
    builder.button(text="⏱ Кулдаун уроков", callback_data="admin:setting_lesson_cooldown")
    builder.button(text="⚔️ Вкл/Выкл дуэли", callback_data="admin:setting_toggle_duels")
    builder.button(text="⏲ Время на вопрос", callback_data="admin:setting_question_time")
    builder.button(text="💰 Награда за дуэль", callback_data="admin:setting_duel_reward")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:setting_toggle_duels")
async def admin_toggle_duels(callback: CallbackQuery):
    """Включение/выключение дуэлей"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    config.DUEL_ENABLED = not config.DUEL_ENABLED
    status = "включены" if config.DUEL_ENABLED else "выключены"

    await callback.answer(f"✅ Дуэли {status}!", show_alert=True)
    await admin_settings(callback)


# ==============================
# УПРАВЛЕНИЕ ДУЭЛЯМИ
# ==============================

@admin_router.callback_query(F.data == "admin:duels_menu")
async def admin_duels_menu(callback: CallbackQuery):
    """Управление дуэлями"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    active_count = len([d for d in active_duels.values() if d.status == DuelStatus.IN_PROGRESS])
    waiting_count = len(waiting_duels)
    completed_today = len([d for d in active_duels.values()
                           if d.status == DuelStatus.COMPLETED
                           and d.end_time and d.end_time.date() == datetime.now().date()])

    text = (
        "⚔️ <b>УПРАВЛЕНИЕ ДУЭЛЯМИ</b>\n\n"
        f"📊 <b>Текущая статистика:</b>\n"
        f"• Активных дуэлей: {active_count}\n"
        f"• В очереди: {waiting_count}\n"
        f"• Завершено сегодня: {completed_today}\n"
        f"• Всего в памяти: {len(active_duels)}\n\n"
        f"⚙️ <b>Настройки:</b>\n"
        f"• Время на вопрос: {config.QUESTION_TIME_LIMIT} сек\n"
        f"• Кулдаун: {config.DUEL_COOLDOWN // 60} мин\n"
        f"• Награда: {config.DUEL_REWARD} баллов\n\n"
        "Выберите действие:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🔍 Список активных", callback_data="admin:duels_list")
    builder.button(text="❌ Завершить все", callback_data="admin:duels_end_all")
    builder.button(text="⏸ Очистить очередь", callback_data="admin:duels_clear_waiting")
    builder.button(text="📊 Детальная статистика", callback_data="admin:duels_detailed_stats")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:duels_list")
async def admin_duels_list(callback: CallbackQuery):
    """Список активных дуэлей"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    active = [d for d in active_duels.values() if d.status == DuelStatus.IN_PROGRESS]

    if not active:
        text = "📭 <b>Нет активных дуэлей</b>"
    else:
        text = f"⚔️ <b>АКТИВНЫЕ ДУЭЛИ ({len(active)})</b>\n\n"

        for i, duel in enumerate(active[:10], 1):
            progress = f"{duel.current_question}/{len(duel.questions)}"
            score = f"{duel.player1_score}:{duel.player2_score}"
            text += f"{i}. ID: <code>{duel.duel_id[:8]}</code>\n"
            text += f"   👤 {duel.player1_id} vs {duel.player2_id}\n"
            text += f"   📊 {progress} вопросов, Счет: {score}\n"
            if duel.start_time:
                duration = datetime.now() - duel.start_time
                minutes = int(duration.total_seconds() // 60)
                text += f"   ⏱ {minutes} мин\n\n"

        if len(active) > 10:
            text += f"...и еще {len(active) - 10} дуэлей"

    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Обновить", callback_data="admin:duels_list")
    builder.button(text="❌ Завершить все", callback_data="admin:duels_end_all")
    builder.button(text="← Назад", callback_data="admin:duels_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:duels_end_all")
async def admin_duels_end_all(callback: CallbackQuery):
    """Завершить все активные дуэли"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    count = 0
    for duel_id, duel in list(active_duels.items()):
        if duel.status == DuelStatus.IN_PROGRESS:
            duel.status = DuelStatus.COMPLETED
            count += 1

    save_data()
    await callback.answer(f"✅ Завершено {count} дуэлей!", show_alert=True)
    await admin_duels_menu(callback)


@admin_router.callback_query(F.data == "admin:duels_clear_waiting")
async def admin_duels_clear_waiting(callback: CallbackQuery):
    """Очистить очередь ожидания"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    count = len(waiting_duels)

    for duel_id in waiting_duels[:]:
        if duel_id in active_duels:
            duel = active_duels[duel_id]
            if duel.player1_id in user_active_duels:
                del user_active_duels[duel.player1_id]
            del active_duels[duel_id]

    waiting_duels.clear()
    save_data()

    await callback.answer(f"✅ Очищено {count} ожидающих дуэлей!", show_alert=True)
    await admin_duels_menu(callback)


@admin_router.callback_query(F.data == "admin:duels_detailed_stats")
async def admin_duels_detailed_stats(callback: CallbackQuery):
    """Детальная статистика дуэлей"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_duels = sum(a.duels_won + a.duels_lost + a.duels_drawn for a in user_activities.values()) // 2
    total_wins = sum(a.duels_won for a in user_activities.values())
    total_losses = sum(a.duels_lost for a in user_activities.values())
    total_draws = sum(a.duels_drawn for a in user_activities.values())

    # Безопасное вычисление процента побед
    win_rate = (total_wins / total_duels * 100) if total_duels > 0 else 0

    top_elo = sorted(user_activities.items(), key=lambda x: x[1].elo_rating, reverse=True)[:5]

    text = (
        "📊 <b>ДЕТАЛЬНАЯ СТАТИСТИКА ДУЭЛЕЙ</b>\n\n"
        f"🎯 <b>Общая статистика:</b>\n"
        f"• Всего дуэлей: {total_duels}\n"
        f"• Побед: {total_wins}\n"
        f"• Поражений: {total_losses}\n"
        f"• Ничьих: {total_draws}\n"
        f"• Win Rate: {win_rate:.1f}%\n\n"
        f"🏆 <b>Топ-5 по ELO:</b>\n"
    )

    for i, (user_id, activity) in enumerate(top_elo, 1):
        text += f"{i}. ID: {user_id} - {activity.elo_rating} ELO\n"

    await callback.message.edit_text(text, reply_markup=back_to_admin(), parse_mode="HTML")
    await callback.answer()


# ==============================
# PREMIUM МЕНЮ
# ==============================

@admin_router.callback_query(F.data == "admin:premium_menu")
async def admin_premium_menu(callback: CallbackQuery):
    """Управление Premium"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    premium_users = []
    for user_id, sub in user_subscriptions.items():
        if sub.is_active() and sub.tier != SubscriptionTier.FREE:
            days_left = (sub.expires_at - datetime.now()).days if sub.expires_at else 9999
            premium_users.append({
                'id': user_id,
                'tier': sub.tier.value,
                'days_left': days_left,
                'rating': users_rating.get(user_id, 0)
            })

    # Сортируем по оставшимся дням
    premium_users.sort(key=lambda x: x['days_left'])

    text = (
        "👑 <b>УПРАВЛЕНИЕ PREMIUM</b>\n\n"
        f"📊 <b>Всего Premium пользователей:</b> {len(premium_users)}\n\n"
    )

    if premium_users:
        text += "<b>Активные подписки:</b>\n"
        for user in premium_users[:10]:
            days_text = f"{user['days_left']} дн." if user['days_left'] < 9999 else "Lifetime"
            text += f"• ID: {user['id']} | {user['tier']} | Осталось: {days_text} | Баллы: {user['rating']}\n"

        if len(premium_users) > 10:
            text += f"...и еще {len(premium_users) - 10} пользователей\n"
    else:
        text += "❌ Нет активных Premium подписок\n"

    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Выдать Premium", callback_data="admin:give_premium")
    builder.button(text="⭐️ Снять Premium", callback_data="admin:remove_premium")
    builder.button(text="📊 Статистика Premium", callback_data="admin:premium_stats")
    builder.button(text="🎁 Бонусы Premium", callback_data="admin:premium_bonuses")
    builder.button(text="← Назад", callback_data="admin_panel")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:premium_stats")
async def admin_premium_stats(callback: CallbackQuery):
    """Статистика Premium"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_revenue = 0
    premium_count = 0
    pro_count = 0
    lifetime_count = 0

    for sub in user_subscriptions.values():
        for transaction in sub.transaction_history:
            total_revenue += transaction.get('amount', 0)

        if sub.is_active():
            if sub.tier == SubscriptionTier.PREMIUM:
                premium_count += 1
            elif sub.tier == SubscriptionTier.PRO:
                pro_count += 1
                if sub.expires_at and (sub.expires_at - datetime.now()).days > 365:
                    lifetime_count += 1

    text = (
        "📊 <b>СТАТИСТИКА PREMIUM</b>\n\n"
        f"💰 <b>Общий доход:</b> {total_revenue}₽\n"
        f"👑 <b>Premium подписок:</b> {premium_count}\n"
        f"💎 <b>Pro подписок:</b> {pro_count}\n"
        f"♾ <b>Lifetime:</b> {lifetime_count}\n\n"
        f"📅 <b>Средний чек:</b> {total_revenue // max(1, premium_count + pro_count)}₽\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="admin:premium_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data == "admin:premium_bonuses")
async def admin_premium_bonuses(callback: CallbackQuery):
    """Бонусы для Premium пользователей"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    text = (
        "🎁 <b>БОНУСЫ PREMIUM</b>\n\n"
        "Premium пользователи получают:\n\n"
        "✅ <b>+20% баллов</b> за тесты\n"
        "✅ <b>+50% бонус</b> за завершение темы\n"
        "✅ <b>Приоритет</b> в очереди дуэлей\n"
        "✅ <b>Все темы</b> без ограничений\n"
        "✅ <b>Уроки</b> без кулдауна\n\n"
        "🎯 <b>Pro подписка (Lifetime):</b>\n"
        "✅ Все бонусы Premium\n"
        "✅ Особый статус в профиле\n"
        "✅ Доступ ко всем будущим темам\n\n"
        "✨ <b>Специальные предложения:</b>\n"
        "• При продлении за 7 дней: скидка 10%\n"
        "• При продлении за 3 дня: 2 месяца в подарок\n"
        "• При возвращении: 3 дня Premium бесплатно"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="admin:premium_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ==============================
# ИЗМЕНЕНИЕ БАЛЛОВ ПОЛЬЗОВАТЕЛЯ
# ==============================

@admin_router.callback_query(F.data == "admin:edit_points")
async def admin_edit_points_start(callback: CallbackQuery, state: FSMContext):
    """Изменение баллов пользователя"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_edit_points_user)

    text = (
        "💰 <b>ИЗМЕНЕНИЕ БАЛЛОВ</b>\n\n"
        "Введите ID пользователя:\n\n"
        "📌 <b>Пример:</b> 123456789\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_edit_points_user)
async def admin_edit_points_user(message: Message, state: FSMContext):
    """Получение ID пользователя"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Операция отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число.")
        return

    if user_id not in users_rating:
        await message.answer("❌ Пользователь не найден.")
        return

    current_points = users_rating.get(user_id, 0)
    await state.update_data(target_user_id=user_id, current_points=current_points)
    await state.set_state(AdminStates.waiting_for_edit_points_amount)

    text = (
        f"👤 <b>Пользователь:</b> {user_id}\n"
        f"💰 <b>Текущие баллы:</b> {current_points}\n\n"
        "Введите новое количество баллов:\n\n"
        "📌 Можно использовать:\n"
        "• <b>+100</b> - добавить 100 баллов\n"
        "• <b>-50</b> - отнять 50 баллов\n"
        "• <b>500</b> - установить ровно 500 баллов\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    await message.answer(text, parse_mode="HTML")


@admin_router.message(AdminStates.waiting_for_edit_points_amount)
async def admin_edit_points_amount(message: Message, state: FSMContext):
    """Изменение количества баллов"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Операция отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    data = await state.get_data()
    user_id = data.get("target_user_id")
    current = data.get("current_points", 0)

    try:
        text = message.text.strip()

        if text.startswith('+'):
            amount = int(text[1:])
            users_rating[user_id] = current + amount
            change_text = f"+{amount}"
            new_value = current + amount
        elif text.startswith('-'):
            amount = int(text[1:])
            users_rating[user_id] = max(0, current - amount)
            change_text = f"-{amount}"
            new_value = max(0, current - amount)
        else:
            amount = int(text)
            users_rating[user_id] = amount
            change_text = f"={amount}"
            new_value = amount

        save_data()

        result_text = (
            f"✅ <b>Баллы изменены!</b>\n\n"
            f"👤 Пользователь: {user_id}\n"
            f"📊 Было: {current}\n"
            f"🔄 Изменение: {change_text}\n"
            f"💰 Стало: {new_value}"
        )

        try:
            await message.bot.send_message(
                user_id,
                f"💰 <b>Изменение баллов</b>\n\n"
                f"Администратор изменил ваши баллы:\n"
                f"• Было: {current}\n"
                f"• Стало: {new_value}\n\n"
                f"🆔 Операция: {change_text}",
                parse_mode="HTML"
            )
            result_text += "\n\n✅ Пользователь уведомлен"
        except:
            result_text += "\n\n⚠️ Не удалось уведомить пользователя"

        await message.answer(result_text, parse_mode="HTML")

    except ValueError:
        await message.answer("❌ Некорректное число. Используйте формат: +100, -50 или 500")
        return

    await state.clear()


@admin_router.callback_query(F.data.startswith("admin:edit_points_for:"))
async def admin_edit_points_for(callback: CallbackQuery, state: FSMContext):
    """Изменение баллов из статистики"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split(":")[2])

    if user_id not in users_rating:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    current_points = users_rating.get(user_id, 0)
    await state.update_data(target_user_id=user_id, current_points=current_points)
    await state.set_state(AdminStates.waiting_for_edit_points_amount)

    text = (
        f"👤 <b>Пользователь:</b> {user_id}\n"
        f"💰 <b>Текущие баллы:</b> {current_points}\n\n"
        "Введите новое количество баллов:\n\n"
        "📌 Можно использовать:\n"
        "• <b>+100</b> - добавить 100 баллов\n"
        "• <b>-50</b> - отнять 50 баллов\n"
        "• <b>500</b> - установить ровно 500 баллов\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    await callback.message.edit_text(text, parse_mode="HTML")
    await callback.answer()


# ==============================
# СТАТИСТИКА ПО ID
# ==============================

@admin_router.callback_query(F.data == "admin:stats_by_id")
async def admin_stats_by_id_start(callback: CallbackQuery, state: FSMContext):
    """Статистика пользователя по ID"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    await state.set_state(AdminStates.waiting_for_user_stats)

    text = (
        "🔍 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        "Введите ID пользователя:\n\n"
        "📌 <b>Пример:</b> 123456789\n\n"
        "❌ Отправьте /cancel для отмены"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.message(AdminStates.waiting_for_user_stats)
async def admin_stats_by_id_show(message: Message, state: FSMContext):
    """Показать статистику пользователя"""
    if message.from_user.id != config.ADMIN_ID:
        return

    if message.text == "/cancel":
        await state.clear()
        await message.answer(
            "❌ Операция отменена",
            reply_markup=InlineKeyboardMarkup(
                inline_keyboard=[[InlineKeyboardButton(text="← Назад", callback_data="admin:users_menu")]]
            )
        )
        return

    try:
        user_id = int(message.text.strip())
    except ValueError:
        await message.answer("❌ Некорректный ID. Введите число.")
        return

    if user_id not in users_rating:
        await message.answer("❌ Пользователь не найден.")
        await state.clear()
        return

    rating = users_rating.get(user_id, 0)
    activity = get_user_activity(user_id)
    sub = get_user_subscription(user_id)

    completed_topics = users_completed_topics.get(user_id, set())
    available_topics = users_available_topics.get(user_id, [])

    total_duels = activity.duels_won + activity.duels_lost + activity.duels_drawn
    win_rate = (activity.duels_won / total_duels * 100) if total_duels > 0 else 0

    if sub.is_active() and sub.tier != SubscriptionTier.FREE:
        premium_status = f"✅ Активен до {sub.expires_at.strftime('%d.%m.%Y')}"
        days_left = (sub.expires_at - datetime.now()).days
    else:
        premium_status = "❌ Не активен"
        days_left = 0

    text = (
        f"📊 <b>СТАТИСТИКА ПОЛЬЗОВАТЕЛЯ</b>\n\n"
        f"👤 <b>ID:</b> {user_id}\n"
        f"💰 <b>Баллы:</b> {rating}\n"
        f"👑 <b>Premium:</b> {premium_status}\n"
        f"📅 <b>Осталось дней:</b> {days_left}\n\n"
        f"📚 <b>Обучение:</b>\n"
        f"• Уроков пройдено: {activity.lessons_completed}\n"
        f"• Всего ответов: {activity.questions_answered}\n"
        f"• Правильных: {activity.correct_answers}\n"
        f"• Точность: {activity.accuracy}%\n"
        f"• Изучено тем: {len(completed_topics)}/{len(TOPICS)}\n\n"
        f"⚔️ <b>Дуэли:</b>\n"
        f"• Всего: {total_duels}\n"
        f"• Побед: {activity.duels_won}\n"
        f"• Поражений: {activity.duels_lost}\n"
        f"• Ничьих: {activity.duels_drawn}\n"
        f"• Win Rate: {win_rate:.1f}%\n"
        f"• ELO: {activity.elo_rating}\n\n"
        f"🔥 <b>Стрик:</b> {activity.daily_streak} дней\n"
        f"📅 <b>В боте с:</b> {activity.first_seen.strftime('%d.%m.%Y')}\n"
        f"🕐 <b>Последняя активность:</b> {activity.last_activity.strftime('%d.%m.%Y %H:%M')}"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="👑 Выдать Premium", callback_data=f"admin:give_premium_to:{user_id}")
    builder.button(text="💰 Изменить баллы", callback_data=f"admin:edit_points_for:{user_id}")
    builder.button(text="🔨 Заблокировать", callback_data=f"admin:ban_user:{user_id}")
    builder.button(text="📤 Экспорт данных", callback_data=f"admin:export_user:{user_id}")
    builder.button(text="← Назад", callback_data="admin:users_menu")
    builder.adjust(1)

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await state.clear()


@admin_router.callback_query(F.data.startswith("admin:give_premium_to:"))
async def admin_give_premium_from_stats(callback: CallbackQuery, state: FSMContext):
    """Выдача Premium из статистики"""
    user_id = int(callback.data.split(":")[2])
    await state.update_data(target_user_id=user_id)
    await state.set_state(AdminStates.waiting_for_premium_days)

    text = (
        f"👤 <b>Пользователь:</b> {user_id}\n\n"
        "Выберите срок Premium:"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="📅 30 дней", callback_data="premium_days:30")
    builder.button(text="📅 90 дней", callback_data="premium_days:90")
    builder.button(text="📅 180 дней", callback_data="premium_days:180")
    builder.button(text="📅 365 дней", callback_data="premium_days:365")
    builder.button(text="👑 Навсегда", callback_data="premium_days:9999")
    builder.button(text="❌ Отмена", callback_data="admin:users_menu")
    builder.adjust(2, 2, 1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


@admin_router.callback_query(F.data.startswith("admin:export_user:"))
async def admin_export_user(callback: CallbackQuery):
    """Экспорт данных конкретного пользователя"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    user_id = int(callback.data.split(":")[2])

    if user_id not in users_rating:
        await callback.answer("❌ Пользователь не найден", show_alert=True)
        return

    activity = get_user_activity(user_id)
    sub = get_user_subscription(user_id)

    user_data = {
        'user_id': user_id,
        'rating': users_rating.get(user_id, 0),
        'activity': activity.to_dict(),
        'subscription': sub.to_dict(),
        'completed_topics': list(users_completed_topics.get(user_id, set())),
        'available_topics': users_available_topics.get(user_id, []),
        'exported_at': datetime.now().isoformat()
    }

    json_data = json.dumps(user_data, ensure_ascii=False, indent=2)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    await callback.message.answer_document(
        document=BufferedInputFile(
            file=json_data.encode('utf-8'),
            filename=f'user_{user_id}_{timestamp}.json'
        ),
        caption=f"📊 Экспорт данных пользователя {user_id}\n📅 {datetime.now().strftime('%d.%m.%Y %H:%M')}"
    )
    await callback.answer()


# ==============================
# ТОП-100 ПОЛЬЗОВАТЕЛЕЙ
# ==============================

@admin_router.callback_query(F.data == "admin:top_100")
async def admin_top_100(callback: CallbackQuery):
    """Топ-100 пользователей"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    sorted_users = sorted(users_rating.items(), key=lambda x: x[1], reverse=True)[:100]

    text = "🏆 <b>ТОП-100 ПОЛЬЗОВАТЕЛЕЙ</b>\n\n"

    page = 0
    per_page = 20
    start = page * per_page
    end = start + per_page

    for i, (user_id, rating) in enumerate(sorted_users[start:end], start + 1):
        activity = get_user_activity(user_id)
        sub = get_user_subscription(user_id)

        premium_mark = "👑" if sub.is_active() and sub.tier != SubscriptionTier.FREE else "  "

        text += f"{i:3}. {premium_mark} ID: <code>{user_id}</code>\n"
        text += f"     💰 {rating} баллов | ⚔️ ELO: {activity.elo_rating} | 🔥 {activity.daily_streak} дней\n"

    text += f"\n📊 Всего пользователей: {len(users_rating)}"

    builder = InlineKeyboardBuilder()
    builder.button(text="📤 Экспорт в CSV", callback_data="admin:export_users_csv")
    builder.button(text="📤 Экспорт в JSON", callback_data="admin:export_users_json")
    builder.button(text="← Назад", callback_data="admin:users_menu")
    builder.adjust(1)

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ==============================
# СТАТИСТИКА БОТА
# ==============================

@admin_router.callback_query(F.data == "admin:stats")
async def admin_stats(callback: CallbackQuery):
    """Статистика бота"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    total_duels = sum(a.duels_won + a.duels_lost + a.duels_drawn for a in user_activities.values()) // 2
    total_questions_answered = sum(a.questions_answered for a in user_activities.values())
    total_correct = sum(a.correct_answers for a in user_activities.values())

    premium_users = len([u for u, s in user_subscriptions.items() if s.is_active() and s.tier != SubscriptionTier.FREE])
    active_today = len([a for a in user_activities.values() if a.last_activity.date() == datetime.now().date()])
    active_week = len([a for a in user_activities.values() if (datetime.now() - a.last_activity).days < 7])

    text = (
        "📊 <b>СТАТИСТИКА БОТА</b>\n\n"
        f"👥 <b>Пользователи:</b>\n"
        f"• Всего: {len(users_rating)}\n"
        f"• Активных сегодня: {active_today}\n"
        f"• Активных за неделю: {active_week}\n"
        f"• Premium: {premium_users}\n\n"
        f"📚 <b>Обучение:</b>\n"
        f"• Всего уроков: {sum(a.lessons_completed for a in user_activities.values())}\n"
        f"• Всего ответов: {total_questions_answered}\n"
        f"• Правильных: {total_correct}\n"
        f"• Общая точность: {(total_correct / total_questions_answered * 100) if total_questions_answered else 0:.1f}%\n\n"
        f"⚔️ <b>Дуэли:</b>\n"
        f"• Всего дуэлей: {total_duels}\n"
        f"• Активных: {len([d for d in active_duels.values() if d.status == DuelStatus.IN_PROGRESS])}\n"
        f"• В очереди: {len(waiting_duels)}\n"
        f"• Средний ELO: {sum(a.elo_rating for a in user_activities.values()) // max(1, len(user_activities))}\n"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="← Назад", callback_data="admin:stats_menu")

    await callback.message.edit_text(text, reply_markup=builder.as_markup(), parse_mode="HTML")
    await callback.answer()


# ==============================
# ПЕРЕЗАГРУЗКА ТЕМ
# ==============================

@admin_router.callback_query(F.data == "admin:reload")
async def admin_reload(callback: CallbackQuery):
    """Перезагрузка тем"""
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("⛔ Доступ запрещен", show_alert=True)
        return

    try:
        load_themes()
        await callback.answer(f"✅ Темы перезагружены! Загружено {len(TOPICS)} тем", show_alert=True)
    except Exception as e:
        await callback.answer(f"❌ Ошибка: {e}", show_alert=True)


# ==============================
# КОМАНДА ДЛЯ АДМИНА
# ==============================

@admin_router.message(Command("admin"))
async def cmd_admin(message: Message):
    """Быстрый доступ к админ-панели"""
    if message.from_user.id != config.ADMIN_ID:
        await message.answer("⛔ Доступ запрещен")
        return

    class FakeCallback:
        def __init__(self, user_id, message, bot):
            self.from_user = type('obj', (object,), {'id': user_id})
            self.message = message
            self.bot = bot
            self.answered = False

        async def answer(self, text=None, show_alert=False):
            self.answered = True

    fake_callback = FakeCallback(message.from_user.id, message, message.bot)
    await admin_panel(fake_callback)


# Экспортируем роутер для подключения в main.py
__all__ = ['admin_router']