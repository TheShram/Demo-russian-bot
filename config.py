# config.py - КОНФИГУРАЦИЯ ДЕМО-БОТА

import os
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()


class Config:
    # Обязательные параметры
    BOT_TOKEN = os.getenv("BOT_TOKEN", "")
    BOT_USERNAME = os.getenv("BOT_USERNAME", "DemoRussianBot")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

    # Контакты разработчика (ЗАМЕНИТЕ НА СВОИ!)
    DEVELOPER_USERNAME = os.getenv("DEVELOPER_USERNAME", "theshramjee")
    DEVELOPER_EMAIL = os.getenv("DEVELOPER_EMAIL", "shramjee@example.com")

    # Настройки демо-режима
    DEMO_MODE = True
    DUEL_ENABLED = False  # Только демо-дуэли

    # Webhook настройки для Railway
    PORT = int(os.getenv("PORT", 8080))
    WEBHOOK_PATH = "/webhook"
    WEBHOOK_URL = None  # Будет установлен автоматически

    def __init__(self):
        # Валидация
        if not self.BOT_TOKEN:
            raise ValueError("❌ BOT_TOKEN не установлен! Добавьте его в переменные окружения.")

        if self.ADMIN_ID == 0:
            print("⚠️ ВНИМАНИЕ: ADMIN_ID не установлен!")

        print(f"✅ Конфигурация загружена. Бот: @{self.BOT_USERNAME}")


config = Config()