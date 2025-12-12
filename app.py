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

# 1. КОНФІГУРАЦІЯ БАЗИ ДАНИХ (PostgreSQL / Neon.tech)
db_url = os.environ.get('DATABASE_URL')

# Render та Heroku іноді вимагають заміни 'postgres://' на 'postgresql://'
if db_url and db_url.startswith("postgres://"):
    db_url = db_url.replace("postgres://", "postgresql://", 1)

# Використовуємо змінну середовища. Якщо її немає, додаток не запуститься
app.config['SQLALCHEMY_DATABASE_URI'] = db_url
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. БЕЗПЕКА: ТОКЕН БОТА (Змінна середовища Render)
TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN')

# 3. НАЛАШТУВАННЯ CORS
CORS(app)

# 4. НАЛАШТУВАННЯ ЛОГУВАННЯ
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

# --- ФУНКЦІЇ БЕЗПЕКИ (ФІНАЛЬНИЙ ПАРСИНГ initData) ---

def validate_telegram_init_data(init_data_string: str) -> dict | None:
    """Перевіряє хеш initData вручну, використовуючи недекодовані значення для обчислення хешу."""
    if not init_data_string or not TELEGRAM_BOT_TOKEN:
        return None

    params = init_data_string.split('&')
    data_to_check = {}
    received_hash = None
    
    # Створюємо список елементів, які будуть використані для формування check_string
    raw_check_data = []

    for param in params:
        if not param:
            continue
            
        try:
            key, value = param.split('=', 1)
            
            # Телеграм вимагає, щоб для обчислення хешу використовувалися 
            # оригінальні (не-декодовані) ключі та значення, крім поля 'hash'.
            if key == 'hash':
                received_hash = value # Тут value вже URL-декодоване
            else:
                raw_check_data.append((key, value))
                
                # Додатково декодуємо для подальшого парсингу user/auth_date
                decoded_key = urllib.parse.unquote(key)
                decoded_value = urllib.parse.unquote(value)
                data_to_check[decoded_key] = decoded_value

        except ValueError:
            continue

    if not received_hash:
        app.logger.error("SECURITY ALERT: Hash missing.")
        return None
    
    # 1. Формуємо рядок для перевірки: сортуємо за ключами і приєднуємо знаком '\n'.
    # Ми використовуємо RAW_CHECK_DATA, щоб зберегти оригінальне кодування, як вимагає Telegram.
    
    # Сортуємо за ключами (перший елемент кортежу)
    raw_check_data.sort(key=lambda x: x[0])
    
    data_check_string = []
    for key, value in raw_check_data:
        # Тут ми використовуємо URL-кодовані значення для формування рядка
        data_check_string.append(f"{key}={value}")

    data_check_string = "\n".join(data_check_string)

    # 2. Секретний ключ
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode('utf-8')).digest()

    # 3. Обчислюємо хеш
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if calculated_hash != received_hash:
        app.logger.error(f"SECURITY ALERT: Hash mismatch (Manual parse failed).")
        app.logger.error(f"Check String: {data_check_string}")
        app.logger.error(f"Calculated Hash: {calculated_hash}")
        app.logger.error(f"Received Hash: {received_hash}")
        return None

    # Якщо хеш збігається, отримуємо user_id з декодованих даних
    if 'user' in data_to_check:
        try:
            user_data = json.loads(data_to_check['user'])
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
        app.logger.error("DIAGNOSTIC: InitData missing from request.")
        return None

    return validate_telegram_init_data(init_data)


# --- КІНЦЕВІ ТОЧКИ API ---

# 1. Обробка фото (Симуляція AI - готова до заміни на Gemini)
@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    user_info = get_user_data_from_request()
    if user_info is None:
        app.logger.error("DIAGNOSTIC: process_photo FAILED - Unauthorized.")
        return jsonify({"error": "Unauthorized"}), 401
    
    # ТУТ МАЄ БУТИ ЛОГІКА ЗЧИТУВАННЯ ФАЙЛУ З request.files ТА ВИКЛИК GEMINI API
    
    # Симуляція результату
    time.sleep(1) 
    meal_data = {
        "name": "Айвар із лавашем (Render API)",
        "calories": 450,
        "description": "AI розпізнав: Паста з солодкого перцю та баклажанів. Оцінка: ~450 ккал."
    }

    return jsonify(meal_data), 200


# 2. Збереження прийому їжі (Запис у БД)
@app.route('/api/save_meal', methods=['POST'])
def save_meal():
    user_info = get_user_data_from_request()
    if user_info is None:
        app.logger.error("DIAGNOSTIC: save_meal FAILED - Unauthorized.")
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


# 3. Отримання щоденного звіту (Читання з БД)
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


# Створення таблиць (для PaaS це виконується один раз)
with app.app_context():
     # Після підключення до Neon.tech, це створить таблицю Meals у вашій базі даних
     db.create_all()
