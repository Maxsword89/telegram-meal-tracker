# ============================================
# Файл: bot/handlers.py
# ============================================
import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo
from telegram.ext import CommandHandler, MessageHandler, filters, ContextTypes
from telegram.constants import ParseMode

logger = logging.getLogger(__name__)

WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-food-bot-jedx.onrender.com")

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - show main menu"""
    user = update.effective_user
    logger.info(f"📨 Start command from user {user.id}")
    
    keyboard = [
        [
            InlineKeyboardButton(
                text="📊 DASHBOARD",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ADD MEAL",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ SETTINGS",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = f"""
🍽️ *Aura Health - Food Tracker*

Welcome, {user.first_name}! 👋

Your personal AI nutritionist powered by *Gemini 2.0 Flash*.

*📊 DASHBOARD* - Track your daily progress
*📸 ADD MEAL* - Analyze food with AI
*⚙️ SETTINGS* - Manage your profile

Tap the buttons below to get started! 🚀
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
                text="📊 DASHBOARD",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ADD MEAL",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ SETTINGS",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    help_text = """
📖 *Help Guide*

*Commands:*
/start - Main menu
/help - This guide

*How to use:*
1️⃣ Set up your profile in Settings
2️⃣ Take a photo of your meal
3️⃣ AI will analyze calories and nutrients
4️⃣ Track your progress on Dashboard

*Tips:*
- Take photos in good lighting
- Include the whole plate
- Be consistent with logging

Need help? Contact support.
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
                text="📊 DASHBOARD",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="📸 ADD MEAL",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/add-meal?user_id={user.id}")
            )
        ],
        [
            InlineKeyboardButton(
                text="⚙️ SETTINGS",
                web_app=WebAppInfo(url=f"{WEBAPP_URL}/settings?user_id={user.id}")
            )
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(
        "🍽️ *Main Menu*\n\nChoose an option:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=reply_markup
    )

def setup_handlers(application):
    """Setup bot handlers"""
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("✅ Handlers setup completed")
