#!/bin/bash
# Запуск Telegram-бота в фоновом режиме
python backend/telegram_bot.py &

# Запуск API-сервера на переднем плане
python backend/server_api.py
