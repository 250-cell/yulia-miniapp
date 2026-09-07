"""
Telegram Bot for notifications about new bookings.
Run separately: python bot.py
Requires BOT_TOKEN in environment or .env
"""

import os
import asyncio
from pathlib import Path

from dotenv import load_dotenv
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, ContextTypes
import aiosqlite

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = {1375984482, 5912547447}
DB_PATH = Path("/tmp/yulia_healer.db")

if not BOT_TOKEN:
    print("⚠️  BOT_TOKEN not set. Create bot via @BotFather and put token in .env")
    print("   Example .env: BOT_TOKEN=123456:ABC-DEF...")

async def notify_admins(text: str):
    """Send message to all admins. Call this from API when new booking arrives."""
    if not BOT_TOKEN:
        print("No BOT_TOKEN, skip notify:", text[:80])
        return
    bot = Bot(token=BOT_TOKEN)
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(chat_id=admin_id, text=text, parse_mode="HTML")
        except Exception as e:
            print(f"Failed to notify {admin_id}: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    is_admin = user.id in ADMIN_IDS
    text = (
        f"Привет, {user.first_name}!\n\n"
        "Это бот Божественного проводника Юлии Пархомовской.\n"
        "Открой Mini App, чтобы посмотреть услуги и записаться."
    )
    if is_admin:
        text += "\n\n🔑 Ты администратор. Здесь будут приходить уведомления о новых записях."
    await update.message.reply_text(text)

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id not in ADMIN_IDS:
        await update.message.reply_text("Только для администратора.")
        return
    try:
        async with aiosqlite.connect(DB_PATH) as db:
            cur = await db.execute("SELECT COUNT(*) FROM bookings WHERE status='pending'")
            pending = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM bookings")
            total = (await cur.fetchone())[0]
            cur = await db.execute("SELECT COUNT(*) FROM services WHERE is_active=1")
            services = (await cur.fetchone())[0]
        await update.message.reply_text(
            f"📊 Статистика:\n"
            f"• Услуг активных: {services}\n"
            f"• Всего записей: {total}\n"
            f"• Ожидают подтверждения: {pending}"
        )
    except Exception as e:
        await update.message.reply_text(f"Ошибка: {e}")

def main():
    if not BOT_TOKEN:
        print("Set BOT_TOKEN and restart.")
        return
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stats", stats))
    print("Bot started...")
    app.run_polling()

if __name__ == "__main__":
    main()
