from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
import time
from flask_cors import CORS
import os
import sys
import logging
from logging import StreamHandler
# Прибрано імпорт hmac та hashlib, оскільки вони не використовуються


# --- НАЛАШТУВАННЯ ТА КОНФІГУРАЦІЯ ---

app = Flask(__name__)

# 1. КОНФІГУРАЦІЯ БАЗИ ДАНИХ
db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. БЕЗПЕКА: ТОКЕН БОТА (ЧИТАЄМО ЗІ ЗМІННОЇ СЕРЕДОВИЩА)
# ПЕРЕКОНАЙТЕСЯ, ЩО ЦЯ ЗМІННА ВСТАНОВЛЕНА НА RENDER!
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN') 

CORS(app)

if not app.debug:
    handler = StreamHandler(sys.stderr)
    handler.setLevel(logging.ERROR)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.ERROR)


# --- МОДЕЛЬ ДАНИХ ---

class Meal(db.Model):
    __tablename__ = 'meals'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.BigInteger, nullable=False, index=True)
    name = db.Column(db.String(100), nullable=False)
    calories = db.Column(db.Integer, nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            'time': self.timestamp.strftime('%H:%M'),
            'name': self.name,
            'calories': self.calories
        }

# --- ФУНКЦІЇ БЕЗПЕКИ (ВАЛІДАЦІЯ ТИМЧАСОВО ВІДКЛЮЧЕНА) ---

def validate_telegram_init_data(init_data_string: str) -> dict | None:
    """
    *** УВАГА: ВАЛІДАЦІЯ ХЕШУ ПОВНІСТЮ ВІДКЛЮЧЕНА! ***
    Лише перевіряє, чи присутні дані користувача (user_id).
    """
    if not init_data_string:
        return None

    from urllib.parse import unquote
    
    # Витягуємо дані користувача (єдина перевірка)
    params = init_data_string.split('&')
    user_data_string = None
    
    for param in params:
        if param.startswith('user='):
            user_data_string = unquote(param.split('=', 1)[1])
            break
            
    if user_data_string:
        try:
            user_data = json.loads(user_data_string)
            app.logger.info("SECURITY CHECK: HASH VALIDATION IS DISABLED (Using user ID).")
            # ПОВЕРТАЄМО ДАНІ БЕЗ ПЕРЕВІРКИ ХЕШУ
            return {"user_id": user_data.get("id"), "username": user_data.get("username")}
        except (json.JSONDecodeError, IndexError):
            pass

    return None


def get_user_data_from_request():
    """Централізовано витягує та валідує дані користувача з request."""
    data = request.get_json(silent=True)
    init_data = data.get('initData') if data else None
    
    if not init_data:
        app.logger.error("INITDATA IS MISSING IN REQUEST.")
        return None

    return validate_telegram_init_data(init_data)


# --- КІНЦЕВІ ТОЧКИ API ---

@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    user_info = get_user_data_from_request()
    if user_info is None:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Симуляція результату
    time.sleep(1) 
    meal_data = {
        "name": f"Розпізнано (ID: {user_info['user_id']})",
        "calories": 450,
        "description": "Розпізнавання успішне. Додайте цю страву."
    }

    return jsonify(meal_data), 200


@app.route('/api/save_meal', methods=['POST'])
def save_meal():
    user_info = get_user_data_from_request()
    if user_info is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    meal_data = data.get('meal', {})

    if not all([meal_data.get('name'), meal_data.get('calories') is not None]):
        return jsonify({"error": "Missing meal details"}), 400

    try:
        new_meal = Meal(
            user_id=user_info['user_id'],
            name=meal_data['name'],
            calories=meal_data['calories'],
            timestamp=datetime.now()
        )

        db.session.add(new_meal)
        db.session.commit()
        app.logger.info(f"Meal saved successfully for User ID: {user_info['user_id']}")
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"Database error during meal save: {e}") 
        return jsonify({"error": "Database error during meal save"}), 500

    return jsonify({"message": "Meal saved successfully"}), 200


@app.route('/api/get_daily_report', methods=['POST'])
def get_daily_report():
    user_info = get_user_data_from_request()
    target_calories = 2000

    if user_info is None:
        # Повертаємо пустий звіт, якщо дані користувача не валідовані
        return jsonify({
            "target": target_calories, "consumed": 0,
            "date": datetime.now().strftime("%d %B %Y"), "meals": []
        }), 200

    user_id = user_info['user_id']
    
    today = datetime.now().date()
    start_of_day = datetime(today.year, today.month, today.day)

    daily_meals = Meal.query.filter(
        Meal.user_id == user_id,
        Meal.timestamp >= start_of_day
    ).order_by(Meal.timestamp.asc()).all()

    consumed_calories = sum(meal.calories for meal in daily_meals)

    return jsonify({
        "target": target_calories,
        "consumed": consumed_calories,
        "date": datetime.now().strftime("%d %B %Y"),
        "meals": [meal.to_dict() for meal in daily_meals]
    }), 200


# Створення таблиць
with app.app_context():
     db.create_all()
