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


# --- НАЛАШТУВАННЯ ТА КОНФІГУРАЦІЯ (Без змін) ---

app = Flask(__name__)

db_url = os.environ.get('DATABASE_URL')

if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# Токен все ще потрібен, але не використовується для валідації
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

CORS(app)

if not app.debug:
    handler = StreamHandler(sys.stderr)
    handler.setLevel(logging.ERROR)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.ERROR)


# --- МОДЕЛЬ ДАНИХ (Без змін) ---

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

# --- ФУНКЦІЇ БЕЗПЕКИ (ПОВНЕ ВІДКЛЮЧЕННЯ ВАЛІДАЦІЇ!!!) ---

def validate_telegram_init_data(init_data_string: str) -> dict | None:
    """
    *** ДІАГНОСТИЧНИЙ РЕЖИМ: ВАЛІДАЦІЯ ПОВНІСТЮ ВІДКЛЮЧЕНА! ***
    Повертає user_id без перевірки хешу.
    """
    if not init_data_string:
        return None

    from urllib.parse import unquote
    
    # Витягуємо дані користувача
    params = init_data_string.split('&')
    user_data_string = None
    
    for param in params:
        if param.startswith('user='):
            user_data_string = unquote(param.split('=', 1)[1])
            break
            
    if user_data_string:
        try:
            user_data = json.loads(user_data_string)
            # *** ПОВЕРТАЄМО ДАНІ БЕЗ ПЕРЕВІРКИ ХЕШУ ***
            app.logger.error("DIAGNOSTIC MODE: HASH VALIDATION IS DISABLED! Using user data.")
            return {"user_id": user_data.get("id", 999999), "username": user_data.get("username", "TestUser")}
        except (json.JSONDecodeError, IndexError):
            pass

    return None


def get_user_data_from_request():
    """Централізовано витягує та валідує дані користувача з request."""
    data = request.get_json(silent=True)
    init_data = data.get('initData') if data else None
    
    if not init_data:
        # Якщо initData взагалі відсутня, це проблема фронтенду
        app.logger.error("DIAGNOSTIC MODE: INITDATA IS MISSING IN REQUEST.")
        return None

    return validate_telegram_init_data(init_data)


# --- КІНЦЕВІ ТОЧКИ API (Виводимо повідомлення ОК) ---

@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    user_info = get_user_data_from_request()
    if user_info is None:
        app.logger.error("DIAGNOSTIC: process_photo FAILED - Unauthorized (User data not parsed).")
        return jsonify({"error": "Unauthorized"}), 401
    
    # Симуляція результату
    time.sleep(1) 
    meal_data = {
        # Додаємо мітку 'WORKING', щоб підтвердити, що це цей код
        "name": f"Айвар (РЕЖИМ БЕЗ ВАЛІДАЦІЇ). ID: {user_info['user_id']}",
        "calories": 450,
        "description": "API працює! Проблема 100% у валідації хешу."
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
        app.logger.error(f"DIAGNOSTIC: Meal saved successfully for User ID: {user_info['user_id']}")
        
    except Exception as e:
        db.session.rollback()
        app.logger.error(f"DIAGNOSTIC: !!! FATAL DATABASE ERROR IN SAVE !!!: {e}") 
        return jsonify({"error": "Database error during meal save"}), 500

    return jsonify({"message": "Meal saved successfully"}), 200


@app.route('/api/get_daily_report', methods=['POST'])
def get_daily_report():
    user_info = get_user_data_from_request()
    target_calories = 2000

    if user_info is None:
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
