# ============================================
# Файл: bot/handlers.py
# ============================================
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

# Адреса вашого додатку на Render
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-meal-tracker.onrender.com")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /start - показує головне меню"""
    user = update.effective_user
    logger.info(f"📨 Start command from user {user.id}")
    
    # Отримуємо ім'я користувача з Telegram
    user_name = user.first_name or "Користувач"
    
    # Клавіатура з кнопками для WebApp (передаємо user_id та name)
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

Твій персональний AI-нутриціолог на базі *Gemini AI*.

*🏠 ГОЛОВНА* - Відстежуй прогрес за сьогодні
*📸 ДОДАТИ СТРАВУ* - Аналіз фото через AI
*📅 СТАТИСТИКА* - Календар та графіки
*📋 ПЛАНИ* - Готові плани харчування
*⚙️ НАЛАШТУВАННЯ* - Керуй профілем

Натискай на кнопки нижче, щоб почати! 🚀
"""
    
    await update.message.reply_text(
        welcome_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Menu sent to user {user.id}")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка команди /help - показує довідку"""
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
1️⃣ Налаштуй профіль в розділі "Налаштування"
2️⃣ Сфотографуй страву або обери з галереї
3️⃣ ШІ визначить калорії та БЖУ
4️⃣ Стеж за прогресом на головній сторінці
5️⃣ Отримуй персоналізовані рекомендації

*Поради для точного аналізу:*
- Фотографуйте при хорошому освітленні
- Покажіть всю тарілку
- Додавайте прийоми регулярно

*Оцінка калорій:*
🟢 Н - норма (80-110% від денної норми)
🔴 Б - багато (>110% від норми)
🟠 М - мало (<80% від норми)

*Підтримка:* @your_support
"""
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )
    logger.info(f"✅ Help sent to user {user.id}")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обробка будь-якого текстового повідомлення - показує головне меню"""
    user = update.effective_user
    user_name = user.first_name or "Користувач"
    logger.info(f"📨 Message from user {user.id}: {update.message.text[:50]}")
    
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

def setup_handlers(application):
    """Налаштування обробників бота"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Handlers setup completed")
