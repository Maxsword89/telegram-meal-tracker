from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hmac
import hashlib
import urllib.parse
import json
import time
from flask_cors import CORS
import os
import sys
import logging
from logging import StreamHandler


# --- НАЛАШТУВАННЯ ТА КОНФІГУРАЦІЯ ---

app = Flask(__name__)

db_url = os.environ.get('DATABASE_URL')
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# !!! УВАГА: ДІАГНОСТИЧНИЙ ТОКЕН ЖОРСТКО ПРОПИСАНИЙ !!!
# Після успішного тестування ЦЕЙ РЯДОК МАЄ БУТИ ВИДАЛЕНИЙ.
DIAGNOSTIC_BOT_TOKEN = "8533436780:AAFXtcxhMvEA6k9GDugXwTSerTVBspw85dU"
TELEGRAM_BOT_TOKEN = DIAGNOSTIC_BOT_TOKEN # Використовуємо його замість змінної середовища

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

# --- ФУНКЦІЇ БЕЗПЕКИ (З ЖОРСТКО ПРОПИСАНИМ ТОКЕНОМ) ---

def validate_telegram_init_data(init_data_string: str) -> dict | None:
    """Перевіряє хеш initData, ігноруючи 'hash' та 'signature', використовуючи жорстко прописаний токен."""
    # Тепер ми використовуємо DIAGNOSTIC_BOT_TOKEN, тому перевіряємо його
    if not init_data_string or not TELEGRAM_BOT_TOKEN:
        return None

    params = init_data_string.split('&')
    data_to_check = {} 
    received_hash = None
    raw_check_data = [] 

    for param in params:
        if not param:
            continue
            
        try:
            key, value = param.split('=', 1)
            
            if key == 'hash':
                received_hash = value
            elif key == 'signature': 
                continue 
            else:
                raw_check_data.append((key, value))
                
                decoded_key = urllib.parse.unquote(key)
                decoded_value = urllib.parse.unquote(value)
                data_to_check[decoded_key] = decoded_value

        except ValueError:
            continue

    if not received_hash:
        app.logger.error("SECURITY ALERT: Hash missing.")
        return None
    
    # 1. Формуємо рядок для перевірки:
    raw_check_data.sort(key=lambda x: x[0])
    
    data_check_string = []
    for key, value in raw_check_data:
        data_check_string.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_string)

    # 2. Секретний ключ (Використовує жорстко прописаний токен)
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode('utf-8')).digest()

    # 3. Обчислюємо хеш
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if calculated_hash != received_hash:
        app.logger.error(f"DIAGNOSTIC FAILURE: Hash mismatch (Hardcoded token failed).")
        app.logger.error(f"Check String: {data_check_string}")
        app.logger.error(f"Calculated Hash: {calculated_hash}")
        app.logger.error(f"Received Hash: {received_hash}")
        return None

    # Якщо хеш збігається, отримуємо user_id
    if 'user' in data_to_check:
        try:
            user_data = json.loads(data_to_check['user'])
            auth_date = data_to_check.get('auth_date')
            
            if auth_date and (time.time() - int(auth_date) > 86400):
                 app.logger.error("SECURITY ALERT: Auth data expired.")
                 return None
                 
            # !!! УСПІШНЕ ПІДТВЕРДЖЕННЯ:
            app.logger.error(f"SUCCESS: Hash matched with hardcoded token! User ID: {user_data.get('id')}")
            return {"user_id": user_data.get("id"), "username": user_data.get("username")}
        except (json.JSONDecodeError, IndexError) as e:
            app.logger.error(f"Failed to parse user JSON: {e}")
            return None

    return None


def get_user_data_from_request():
    """Централізовано витягує та валідує дані користувача з request."""
    data = request.get_json(silent=True)
    init_data = data.get('initData') if data else None
    
    if not init_data:
        return None

    return validate_telegram_init_data(init_data)


# --- КІНЦЕВІ ТОЧКИ API (Виводимо повідомлення ОК) ---

@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    user_info = get_user_data_from_request()
    if user_info is None:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Симуляція результату
    time.sleep(1) 
    meal_data = {
        "name": "Айвар із лавашем (ОК, ТЕСТ НА ХЕШ УСПІШНИЙ!)",
        "calories": 450,
        "description": "AI розпізнав: Паста з солодкого перцю та баклажанів. Оцінка: ~450 ккал."
    }

    return jsonify(meal_data), 200


@app.route('/api/save_meal', methods=['POST'])
def save_meal():
    # ... (решта функцій, що використовують get_user_data_from_request) ...
    user_info = get_user_data_from_request()
    if user_info is None:
        return jsonify({"error": "Unauthorized"}), 401

    data = request.get_json()
    meal_data = data.get('meal', {})
    
    # ... (логіка збереження) ...
    try:
        new_meal = Meal(
            user_id=user_info['user_id'],
            name=meal_data['name'],
            calories=meal_data['calories'],
            timestamp=datetime.now()
        )
        db.session.add(new_meal)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": "Database error during meal save"}), 500

    return jsonify({"message": "Meal saved successfully"}), 200

@app.route('/api/get_daily_report', methods=['POST'])
def get_daily_report():
    # ... (решта функцій) ...
    user_info = get_user_data_from_request()
    target_calories = 2000

    if user_info is None:
        return jsonify({"target": target_calories, "consumed": 0, "date": datetime.now().strftime("%d %B %Y"), "meals": []}), 200

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
