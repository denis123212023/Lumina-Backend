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
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext

class AdminStates(StatesGroup):
    setup_password = State()
    waiting_for_password = State()

# Import from server DB
import sys
sys.path.append('.')
from server_db import db_manager

# Configuration
load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN", "7423482417:AAGdwZcgK-LSDSN13rxpFoiJxVz72h6tJxo")
ADMIN_IDS = [int(x.strip()) for x in os.getenv("ADMIN_IDS", "5606191133,5273874070").split(',')]

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
async def cmd_admin(message: types.Message, state: FSMContext):
    """Admin panel"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен. Эта команда только для администратора.")
        return
        
    if not db_manager.has_admin_password():
        await message.reply("⚠️ Админ-пароль не установлен!\n\nПожалуйста, отправьте пароль, который будет использоваться для защиты создания ключей. Сообщение с паролем будет автоматически удалено.")
        await state.set_state(AdminStates.setup_password)
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
    if message.from_user.id not in ADMIN_IDS:
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
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен.")
        return
    
    try:
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        cursor = conn.cursor()
        
        cursor.execute("SELECT username, role, created_at FROM users ORDER BY created_at DESC LIMIT 20")
        users = cursor.fetchall()
        
        conn.close()
        
        if not users:
            await message.reply("📭 Нет пользователей")
            return
        
        text = "👥 Пользователи (последние 20):\n\n"
        for username, role, created in users:
            text += f"• {username} [*{role}*] - {created}\n"
        
        await message.reply(text, parse_mode="Markdown")
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        await message.reply("❌ Ошибка.")

@dp.message(Command("setrole"))
async def cmd_setrole(message: types.Message):
    """Set user role"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен.")
        return
        
    args = message.text.split()
    if len(args) < 3:
        await message.reply("Использование: `/setrole [никнейм] [роль]`\n\nДоступные роли: `Developer`, `User`, `YT` (или `yt`, `dev`, `user`)", parse_mode="Markdown")
        return
        
    username = args[1]
    role_input = args[2].lower()
    
    role_map = {
        "developer": "Developer",
        "dev": "Developer",
        "user": "User",
        "yt": "YT",
        "youtube": "YT",
        "ютуб": "YT"
    }
    
    if role_input not in role_map:
        await message.reply("❌ Неверная роль. Выберите из: `Developer`, `User`, `YT`", parse_mode="Markdown")
        return
        
    target_role = role_map[role_input]
    
    success, msg = db_manager.change_user_role(username, target_role)
    if success:
        await message.reply(f"✅ Успешно установлена роль *{target_role}* для пользователя `{username}`!", parse_mode="Markdown")
    else:
        await message.reply(f"❌ {msg}")


@dp.message(Command("resethwid"))
async def cmd_resethwid(message: types.Message):
    """Reset user HWID"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен.")
        return
        
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Использование: `/resethwid [никнейм]`", parse_mode="Markdown")
        return
        
    username = args[1]
    success, msg = db_manager.reset_user_hwid(username)
    if success:
        await message.reply(f"✅ HWID для пользователя *{username}* успешно сброшен!", parse_mode="Markdown")
    else:
        await message.reply(f"❌ {msg}")


@dp.message(Command("createkey"))
async def cmd_createkey(message: types.Message, state: FSMContext):
    """Create key with specified days"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен.")
        return
        
    if not db_manager.has_admin_password():
        await message.reply("⚠️ Админ-пароль не установлен!\n\nПожалуйста, отправьте пароль.")
        await state.set_state(AdminStates.setup_password)
        return
    
    args = message.text.split()
    if len(args) < 2:
        await message.reply("Использование: /createkey [количество дней]\nПример: /createkey 60")
        return
    
    try:
        days = int(args[1])
        await state.update_data(days=days)
        await message.reply("🔒 Введите админ-пароль для подтверждения создания ключа:")
        await state.set_state(AdminStates.waiting_for_password)
    except ValueError:
        await message.reply("❌ Неверный формат. Укажите количество дней числом.")
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply("❌ Ошибка.")

@dp.message(AdminStates.setup_password)
async def process_setup_password(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    # Delete password message for safety
    try:
        await message.delete()
    except Exception:
        pass
        
    password = message.text.strip()
    db_manager.set_admin_password(password)
    await state.clear()
    await message.answer("✅ Админ-пароль успешно установлен и сохранен в базе данных! Теперь вы можете использовать панель администратора /admin.")

@dp.message(AdminStates.waiting_for_password)
async def process_key_password(message: types.Message, state: FSMContext):
    if message.from_user.id not in ADMIN_IDS:
        return
        
    # Delete password message for safety
    try:
        await message.delete()
    except Exception:
        pass
        
    password = message.text.strip()
    if not db_manager.check_admin_password(password):
        await message.answer("❌ Неверный админ-пароль! Создание ключа отменено.")
        await state.clear()
        return
        
    data = await state.get_data()
    days = data.get('days', 30)
    await state.clear()
    
    # Generate key
    key = f"LUMINA-ADMIN-{datetime.now().strftime('%Y%m%d')}-{uuid.uuid4().hex[:12].upper()}"
    expiry = datetime.now() + timedelta(days=days)
    
    success, msg = db_manager.add_key(key, expires_at=expiry.isoformat())
    
    if success:
        await message.answer(
            f"✅ Ключ создан:\n\n"
            f"`{key}`\n\n"
            f"⏰ Срок: {days} дней\n"
            f"📅 Истекает: {expiry.strftime('%d.%m.%Y %H:%M')}",
            parse_mode="Markdown"
        )
    else:
        await message.answer(f"❌ {msg}")



@dp.message(Command("resetpassword"))
async def cmd_resetpassword(message: types.Message, state: FSMContext):
    """Reset admin password — only for ADMIN_IDS"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен.")
        return
    await state.clear()
    try:
        import sqlite3
        conn = sqlite3.connect(db_manager.db_path)
        conn.execute("DELETE FROM settings WHERE key='admin_password'")
        conn.commit()
        conn.close()
        await message.reply(
            "✅ Пароль администратора сброшен!\n\n"
            "Напиши /admin — бот попросит установить новый пароль."
        )
    except Exception as e:
        await message.reply(f"❌ Ошибка: {e}")


@dp.message(Command("update"))
async def cmd_update(message: types.Message, state: FSMContext):
    """Update mod.jar by downloading from a direct URL"""
    if message.from_user.id not in ADMIN_IDS:
        await message.reply("❌ Доступ запрещен.")
        return

    args = message.text.strip().split(maxsplit=1)

    # Если ссылка не передана — объяснить как пользоваться
    if len(args) < 2 or not args[1].startswith("http"):
        await message.reply(
            "📦 *Обновление мода*\n\n"
            "Использование:\n"
            "`/update <прямая_ссылка_на_jar>`\n\n"
            "Примеры ссылок:\n"
            "• Google Drive: включи общий доступ → скопируй ID файла →\n"
            "  `https://drive.google.com/uc?export=download&id=ВАШ_ID`\n"
            "• Dropbox: замени `?dl=0` на `?dl=1` в конце ссылки\n"
            "• Любой прямой URL на `.jar` файл",
            parse_mode="Markdown"
        )
        return

    url = args[1].strip()
    status_msg = await message.reply("⏳ Скачиваю файл с сервера...")

    target_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "mod.jar")
    temp_path   = target_path + ".tmp"

    try:
        import requests as req
        headers = {"User-Agent": "LuminaLauncher/1.0"}

        # Скачиваем по частям чтобы не грузить память
        with req.get(url, headers=headers, stream=True, timeout=120) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            downloaded = 0
            with open(temp_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=1024 * 256):
                    if chunk:
                        f.write(chunk)
                        downloaded += len(chunk)

        file_size = os.path.getsize(temp_path)
        if file_size < 1000:
            os.remove(temp_path)
            await status_msg.edit_text("❌ Файл слишком маленький или ссылка неверная.")
            return

        # Заменяем старый файл
        if os.path.exists(target_path):
            os.remove(target_path)
        os.rename(temp_path, target_path)

        # Обновляем версию в БД
        new_version = datetime.now().strftime('%Y%m%d%H%M%S')
        db_manager.set_setting("mod_version", new_version)

        file_size_mb = file_size / (1024 * 1024)
        await status_msg.edit_text(
            f"✅ *Мод обновлён!*\n\n"
            f"📦 Размер: `{file_size_mb:.2f} MB`\n"
            f"🔖 Новая версия: `{new_version}`\n\n"
            f"Все лаунчеры скачают обновление при следующем запуске!",
            parse_mode="Markdown"
        )
    except Exception as e:
        logger.error(f"Mod update error: {e}")
        if os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass
        await status_msg.edit_text(
            f"❌ Ошибка при скачивании файла:\n`{e}`\n\n"
            "Убедись что ссылка прямая и файл доступен без авторизации.",
            parse_mode="Markdown"
        )


@dp.message(Command("cleanup"))
async def cmd_cleanup(message: types.Message):
    """Clean up expired keys"""
    if message.from_user.id not in ADMIN_IDS:
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
    if query.from_user.id not in ADMIN_IDS:
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
    print("  /admin - Админ панель (только для ADMIN_IDS)")
    
    # Delete any existing webhook to avoid conflict with long polling
    await bot.delete_webhook(drop_pending_updates=True)
    
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
