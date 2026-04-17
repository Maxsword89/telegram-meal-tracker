# ============================================
# Файл: main.py (ФІНАЛЬНИЙ)
# ============================================
import os
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, UploadFile, File
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from dotenv import load_dotenv
from datetime import datetime, timedelta
from typing import Optional, List
import json

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://telegram-meal-tracker.onrender.com")

from telegram import Update
from telegram.ext import Application
from bot.handlers import setup_handlers

from services.gemini import GeminiService
from services.nutrition import NutritionCalculator

# Initialize services
try:
    gemini_service = GeminiService()
    logger.info("Gemini service initialized")
except Exception as e:
    logger.error(f"Gemini init error: {e}")
    gemini_service = None

nutrition_calculator = NutritionCalculator()

app_instance = None

# ============================================
# IN-MEMORY DATABASE
# ============================================
_memory_db = {
    "users": {},
    "meals": {},
    "supplements": {},
    "water": {},
    "notifications": {}
}

def init_supabase():
    logger.info("⚠️ Running in memory-only mode")
    return None

supabase = None

def save_user_profile(telegram_id: int, profile: dict):
    _memory_db["users"][telegram_id] = profile
    logger.info(f"✅ Profile saved for {telegram_id}")
    return profile

def get_user_profile(telegram_id: int):
    return _memory_db["users"].get(telegram_id)

def save_meal(telegram_id: int, meal_data: dict):
    if telegram_id not in _memory_db["meals"]:
        _memory_db["meals"][telegram_id] = []
    _memory_db["meals"][telegram_id].append(meal_data)
    logger.info(f"✅ Meal saved for {telegram_id}")
    return meal_data

def get_today_meals(telegram_id: int):
    return _memory_db["meals"].get(telegram_id, [])

def get_weekly_meals(telegram_id: int):
    meals = _memory_db["meals"].get(telegram_id, [])
    week_ago = datetime.now() - timedelta(days=7)
    filtered = []
    for meal in meals:
        try:
            meal_time = datetime.fromisoformat(meal.get("created_at", datetime.now().isoformat()))
            if meal_time >= week_ago:
                filtered.append(meal)
        except:
            filtered.append(meal)
    return filtered

def save_water(telegram_id: int, amount: int):
    _memory_db["water"][telegram_id] = amount
    return amount

def get_water(telegram_id: int):
    return _memory_db["water"].get(telegram_id, 0)

def save_notifications(telegram_id: int, times: list):
    _memory_db["notifications"][telegram_id] = times
    return True

def get_notifications(telegram_id: int):
    return _memory_db["notifications"].get(telegram_id, [])

# ============================================
# FASTAPI APP
# ============================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    global app_instance
    logger.info("🚀 Starting up...")
    init_supabase()
    
    if app_instance is None:
        logger.info("Creating bot application...")
        app_instance = Application.builder().token(BOT_TOKEN).build()
        setup_handlers(app_instance)
        await app_instance.initialize()
        
        webhook_url = f"{WEBAPP_URL}/webhook"
        await app_instance.bot.set_webhook(webhook_url)
        logger.info(f"✅ Bot setup complete. Webhook: {webhook_url}")
    
    logger.info("✅ Startup complete")
    yield
    
    logger.info("🛑 Shutting down...")
    if app_instance:
        await app_instance.bot.delete_webhook()
        await app_instance.shutdown()

app = FastAPI(lifespan=lifespan)

os.makedirs("webapp/static", exist_ok=True)
app.mount("/static", StaticFiles(directory="webapp/static"), name="static")

# ============================================
# TELEGRAM WEBHOOK
# ============================================

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"📨 Webhook received")
        if app_instance is None:
            return JSONResponse({"status": "error", "message": "Bot not initialized"}, status_code=500)
        update = Update.de_json(data, app_instance.bot)
        await app_instance.process_update(update)
        return JSONResponse({"status": "ok"})
    except Exception as e:
        logger.error(f"❌ Webhook error: {e}", exc_info=True)
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)

# ============================================
# WEBAPP PAGES
# ============================================

@app.get("/")
async def index():
    try:
        with open("webapp/index.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Welcome to Aura Health</h1><p>Open Telegram and send /start</p>")

@app.get("/add-meal")
async def add_meal_page():
    try:
        with open("webapp/add_meal.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Add Meal</h1><p>Please update the app</p>")

@app.get("/settings")
async def settings_page():
    try:
        with open("webapp/settings.html", "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    except FileNotFoundError:
        return HTMLResponse("<h1>Settings</h1><p>Please update the app</p>")

# ============================================
# API ENDPOINTS
# ============================================

@app.get("/api/user/{telegram_id}")
async def get_user(telegram_id: int):
    try:
        profile = get_user_profile(telegram_id)
        if profile:
            return JSONResponse(profile)
        return JSONResponse({"error": "User not found"}, status_code=404)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/user/{telegram_id}")
async def update_user(telegram_id: int, profile: dict):
    try:
        age = profile.get("age", 25)
        height = profile.get("height", 170)
        weight = profile.get("weight", 70)
        
        profile_data = {
            "age": int(age) if age else 25,
            "gender": profile.get("gender", "male"),
            "height": int(height) if height else 170,
            "weight": float(weight) if weight else 70,
            "activity_level": profile.get("activity_level", "moderate"),
            "goal": profile.get("goal", "maintain"),
        }
        
        daily_calories = nutrition_calculator.calculate_tdee(profile_data)
        
        user_data = {
            "age": profile_data["age"],
            "gender": profile_data["gender"],
            "height": profile_data["height"],
            "weight": profile_data["weight"],
            "activity_level": profile_data["activity_level"],
            "goal": profile_data["goal"],
            "daily_calorie_goal": daily_calories,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        result = save_user_profile(telegram_id, user_data)
        return JSONResponse(result or {})
    except Exception as e:
        logger.error(f"Error updating user: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/meals/{telegram_id}")
async def get_meals(telegram_id: int):
    try:
        meals = get_today_meals(telegram_id)
        return JSONResponse(meals)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/analyze")
async def analyze_meal(photo: UploadFile = File(...)):
    try:
        if not gemini_service:
            return JSONResponse({"error": "Gemini service not initialized"}, status_code=500)
        
        photo_bytes = await photo.read()
        analysis = await gemini_service.analyze_meal(photo_bytes, photo.filename)
        return JSONResponse(analysis)
    except Exception as e:
        logger.error(f"Analysis error: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/meals")
async def create_meal(meal: dict):
    try:
        telegram_id = meal.get("telegram_id")
        if not telegram_id:
            return JSONResponse({"error": "telegram_id required"}, status_code=400)
        
        meal_data = {
            "name": meal.get("name", "Unknown"),
            "calories": meal.get("calories", 0),
            "protein": meal.get("protein", 0),
            "fat": meal.get("fat", 0),
            "carbs": meal.get("carbs", 0),
            "feedback": meal.get("feedback", ""),
            "created_at": datetime.utcnow().isoformat()
        }
        
        result = save_meal(telegram_id, meal_data)
        return JSONResponse(result or {})
    except Exception as e:
        logger.error(f"Error creating meal: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/water/{telegram_id}")
async def get_water_endpoint(telegram_id: int):
    try:
        total = get_water(telegram_id)
        return JSONResponse({"total": total})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.post("/api/water/{telegram_id}")
async def save_water_endpoint(telegram_id: int, data: dict):
    try:
        total = data.get("total", 0)
        result = save_water(telegram_id, total)
        return JSONResponse({"total": result})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/daily-summary/{telegram_id}")
async def get_daily_summary(telegram_id: int):
    try:
        meals = get_today_meals(telegram_id)
        user_profile = get_user_profile(telegram_id)
        
        if not user_profile:
            return JSONResponse({"error": "User profile not found"}, status_code=404)
        
        summary = nutrition_calculator.get_daily_summary(meals, user_profile)
        return JSONResponse(summary)
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/api/weekly-report/{telegram_id}")
async def get_weekly_report(telegram_id: int):
    try:
        meals = get_weekly_meals(telegram_id)
        if not meals:
            return JSONResponse({"error": "No meals found"}, status_code=404)
        
        total_calories = sum(m.get("calories", 0) for m in meals)
        avg_per_day = {"calories": total_calories / 7}
        user_profile = get_user_profile(telegram_id)
        
        ai_analysis = "📊 Weekly Report\n\n"
        if gemini_service:
            try:
                ai_analysis = await gemini_service.analyze_weekly(meals, avg_per_day, user_profile)
            except Exception as e:
                ai_analysis = f"⚠️ Could not generate AI analysis: {str(e)[:100]}"
        
        return JSONResponse({"ai_analysis": ai_analysis})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

@app.get("/health")
async def health():
    return JSONResponse({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "mode": "in-memory",
        "gemini": "initialized" if gemini_service else "failed",
        "bot": "ready" if app_instance else "initializing"
    })

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
