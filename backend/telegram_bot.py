"""
Telegram Bot Example for Lumina Launcher
This bot generates and manages activation keys

Requires: pip install aiogram python-dotenv
"""

import logging
import os
import uuid
import asyncio
from datetime import datetime, timedelta
from dotenv import load_dotenv
from aiogram import Bot, Dispatcher, types, F
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command

# Import from server DB
import sys
sys.path.append('.')
from server_db import db_manager

# Configuration
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "7423482417:AAGdwZcgK-LSDSN13rxpFoiJxVz72h6tJxo")
ADMIN_ID = int(os.getenv("ADMIN_ID", "5606191133"))

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize bot and dispatcher
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
bot = Bot(token=BOT_TOKEN)

# ═══════════════════════════════════════════════════════════
#  COMMANDS
# ═══════════════════════════════════════════════════════════

@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    """Start command"""
    markup = types.ReplyKeyboardMarkup(
        keyboard=[
            [types.KeyboardButton(text="/help")]
        ],
        resize_keyboard=True
    )
    await message.reply(
        "👋 Добро пожаловать в Lumina Launcher!\n\n"
        "🎮 Используйте команды:\n"
        "/help - Справка\n"
        "/admin - Админ панель (только для администратора)",
        reply_markup=markup
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Help command"""
    await message.reply(
        "📖 Справка:\n\n"
        "1️⃣ Обратитесь к администратору для получения ключа активации\n"
        "2️⃣ Введите полученный ключ в лаунчер\n"
        "3️⃣ Нажмите 'Активировать'\n\n"
        "💡 Ключ привязывается к вашему аккаунту\n"
        "⚠️ Не передавайте ключ другим людям!"
    )


@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    """Admin panel"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Доступ запрещен. Эта команда только для администратора.")
        return
    
    markup = types.InlineKeyboardMarkup(inline_keyboard=[
        [
            types.InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats"),
            types.InlineKeyboardButton(text="👥 Пользователи", callback_data="admin_users")
        ]
    ])
    
    await message.reply(
        "🔧 Админ панель:\n\n"
        "Команды:\n"
        "/createkey [дней] - Создать ключ с указанным сроком\n"
        "/stats - Статистика\n"
        "/users - Список пользователей\n"
        "/cleanup - Очистить ключи",
        reply_markup=markup
    )


@dp.message(Command("stats"))
async def cmd_stats(message: types.Message):
    """Show statistics"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Доступ запрещен.")
        return
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM users")
        user_count = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM keys")
        total_keys = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM keys WHERE status = 'active'")
        active_keys = cursor.fetchone()[0]
        
        cursor.execute("SELECT COUNT(*) FROM keys WHERE status = 'used'")
        used_keys = cursor.fetchone()[0]
        
        conn.close()
        
        await message.reply(
            "📊 Статистика:\n\n"
            f"👥 Пользователей: {user_count}\n"
            f"🔑 Всего ключей: {total_keys}\n"
            f"✅ Активных ключей: {active_keys}\n"
            f"✔️ Использованных ключей: {used_keys}"
        )
    except Exception as e:
        logger.error(f"Error getting stats: {e}")
        await message.reply("❌ Ошибка при получении статистики.")


@dp.message(Command("users"))
async def cmd_users(message: types.Message):
    """List users"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Доступ запрещен.")
        return
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, created_at FROM users ORDER BY created_at DESC LIMIT 20")
        users = cursor.fetchall()
        
        conn.close()
        
        if not users:
            await message.reply("📭 Нет пользователей")
            return
        
        text = "👥 Пользователи (последние 20):\n\n"
        for username, created in users:
            text += f"• {username} - {created}\n"
        
        await message.reply(text)
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        await message.reply("❌ Ошибка.")


@dp.message(Command("createkey"))
async def cmd_createkey(message: types.Message):
    """Create key with specified days"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Доступ запрещен.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Использование: /createkey [количество дней]\nПример: /createkey 60")
        return
    
    try:
        days = int(args[1])
        
        key = f"LUMINA-ADMIN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:12].upper()}"
        expiry = datetime.now() + timedelta(days=days)
        
        success, msg = db_manager.add_key(key, expires_at=expiry.isoformat())
        
        if success:
            await message.reply(
                f"✅ Ключ создан:\n\n"
                f"`{key}`\n\n"
                f"⏰ Срок: {days} дней\n"
                f"📅 Истекает: {expiry.strftime('%d.%m.%Y %H:%M')}",
                parse_mode="Markdown"
            )
        else:
            await message.reply(f"❌ {msg}")
    except ValueError:
        await message.reply("❌ Неверный формат. Укажите количество дней числом.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply("❌ Ошибка.")


@dp.message(Command("cleanup"))
async def cmd_cleanup(message: types.Message):
    """Clean up expired keys"""
    if message.from_user.id != ADMIN_ID:
        await message.reply("❌ Доступ запрещен.")
        return
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        # Mark expired keys as 'expired'
        cursor.execute(
            "UPDATE keys SET status = 'expired' WHERE expires_at < datetime('now') AND status = 'active'"
        )
        
        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        
        await message.reply(f"✅ Очищено: {deleted} истекших ключей отмечены как 'истекшие'")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply("❌ Ошибка.")


# ═══════════════════════════════════════════════════════════
#  CALLBACKS
# ═══════════════════════════════════════════════════════════

@dp.callback_query(F.data == "copy_key")
async def copy_key_callback(query: types.CallbackQuery):
    """Copy key button"""
    await query.answer("✅ Ключ скопирован в буфер обмена", show_alert=False)


@dp.callback_query(F.data.startswith("admin_"))
async def admin_callback(query: types.CallbackQuery):
    """Admin panel callbacks"""
    if query.from_user.id != ADMIN_ID:
        await query.answer("Доступ запрещен", show_alert=True)
        return
    
    data = query.data
    
    if data == "admin_stats":
        await cmd_stats(query.message)
    elif data == "admin_users":
        await cmd_users(query.message)
    
    await query.answer()


# ═══════════════════════════════════════════════════════════
#  ERROR HANDLERS
# ═══════════════════════════════════════════════════════════

@dp.message()
async def default_handler(message: types.Message):
    """Default message handler"""
    await message.reply(
        "👋 Привет! Обратитесь к администратору для получения ключа или используйте /help."
    )


# ═══════════════════════════════════════════════════════════
#  MAIN
# ═══════════════════════════════════════════════════════════

async def main():
    logger.info("Starting Lumina Launcher Telegram Bot...")
    print("🤖 Бот запущен и ждет команд!")
    print("Доступные команды:")
    print("  /start - Начать")
    print("  /help - Справка")
    print("  /admin - Админ панель (ADMIN_ID только)")
    
    # Delete any existing webhook to avoid conflict with long polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
