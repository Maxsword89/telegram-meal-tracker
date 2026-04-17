# ============================================
# Файл: bot/handlers.py (для версії 21.x)
# ============================================
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-meal-tracker.onrender.com")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    logger.info(f"📨 Start command from user {user.id}")
    
    user_name = user.first_name or "Користувач"
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏠 ГОЛОВНА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ДОДАТИ СТРАВУ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 СТАТИСТИКА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&tab=stats&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 ПЛАНИ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&tab=plans&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НАЛАШТУВАННЯ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🍽️ *Aura Health - Трекер харчування*

Вітаю, {user_name}! 👋

Твій персональний AI-нутриціолог.

*🏠 ГОЛОВНА* - Відстежуй прогрес
*📸 ДОДАТИ СТРАВУ* - Аналіз фото через AI
*📅 СТАТИСТИКА* - Календар та графіки
*📋 ПЛАНИ* - Плани харчування
*⚙️ НАЛАШТУВАННЯ* - Керуй профілем

Натискай на кнопки нижче! 🚀
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Menu sent to user {user.id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    user = update.effective_user
    user_name = user.first_name or "Користувач"
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏠 ГОЛОВНА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ДОДАТИ СТРАВУ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НАЛАШТУВАННЯ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_text = """
📖 *Довідка*

*Команди:*
/start - Головне меню
/help - Ця довідка

*Як користуватися:*
1️⃣ Налаштуй профіль
2️⃣ Сфотографуй їжу
3️⃣ AI визначить калорії
4️⃣ Стеж за прогресом
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Help sent to user {user.id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message"""
    user = update.effective_user
    user_name = user.first_name or "Користувач"
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="🏠 ГОЛОВНА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ДОДАТИ СТРАВУ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📅 СТАТИСТИКА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&tab=stats&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📋 ПЛАНИ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}&tab=plans&name={user_name}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ НАЛАШТУВАННЯ",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🍽️ *Головне меню*\n\nОберіть дію:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Menu resent to user {user.id}")

def setup_handlers(application: Application):
    """Setup bot handlers"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Handlers setup completed")
