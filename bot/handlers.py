# ============================================
# Файл: bot/handlers.py
# ============================================
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# НОВА АДРЕСА
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-meal-tracker.onrender.com")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show main menu"""
    user = update.effective_user
    logger.info(f"📨 Start command from user {user.id}")
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 ГОЛОВНА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
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
    
    welcome_text = f"""
🍽️ *Aura Health - Трекер харчування*

Вітаю, {user.first_name}! 👋

Твій персональний AI-нутриціолог.

*📊 ГОЛОВНА* - Відстежуй прогрес
*📸 ДОДАТИ СТРАВУ* - Аналіз фото через AI
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
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 ГОЛОВНА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
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
1️⃣ Налаштуй профіль в Settings
2️⃣ Сфотографуй їжу
3️⃣ AI визначить калорії та БЖУ
4️⃣ Стеж за прогресом на Dashboard

*Поради:*
- Фотографуйте при хорошому освітленні
- Додавайте прийоми регулярно
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle any text message - show main menu"""
    user = update.effective_user
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 ГОЛОВНА",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
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
    
    await update.message.reply_text(
        "🍽️ *Головне меню*\n\nОберіть дію:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

def setup_handlers(application):
    """Setup bot handlers"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Handlers setup completed")
