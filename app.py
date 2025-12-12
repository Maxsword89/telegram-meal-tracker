from flask import Flask, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import hmac
import hashlib
import urllib.parse
import json
import time
from flask_cors import CORS
# Імпорти для логування
import sys
import logging
from logging import StreamHandler


# --- НАЛАШТУВАННЯ ТА КОНФІГУРАЦІЯ ---

app = Flask(__name__)

# 1. КОНФІГУРАЦІЯ БАЗИ ДАНИХ (SQLite)
# !!! ОБОВ'ЯЗКОВО ЗАМІНІТЬ 'Maxsword2025' НА ВАШЕ ІМ'Я КОРИСТУВАЧА !!!
db_path = '/home/Maxsword2025/meal_tracker.db'
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{db_path}'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# 2. БЕЗПЕКА: ТОКЕН БОТА ДЛЯ ВАЛІДАЦІЇ
# !!! ПЕРЕВІРЕНИЙ ТОКЕН: !!!
TELEGRAM_BOT_TOKEN = "8533436780:AAFfjgHWjCabQXQKgyf_gcrNJCd3PffnG10"

# 3. НАЛАШТУВАННЯ CORS
CORS(app)

# 4. НАЛАШТУВАННЯ ЛОГУВАННЯ ДЛЯ PYTHONANYWHERE
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

# --- ФУНКЦІЇ БЕЗПЕКИ (З РУЧНИМ ПАРСИНГОМ) ---

def validate_telegram_init_data(init_data_string: str) -> dict | None:
    """Перевіряє хеш initData вручну, щоб уникнути проблем parse_qs."""
    if not init_data_string:
        return None

    params = init_data_string.split('&')

    data_to_check = {}
    received_hash = None

    for param in params:
        if not param:
            continue

        try:
            key, value = param.split('=', 1)
            # URL декодування (КРИТИЧНО)
            key = urllib.parse.unquote(key)
            value = urllib.parse.unquote(value)

            if key == 'hash':
                received_hash = value
            else:
                data_to_check[key] = value
        except ValueError:
            continue

    if not received_hash:
        app.logger.error("SECURITY ALERT: Hash missing.")
        return None

    # Сортуємо ключі та формуємо рядок 'ключ=значення\n'
    sorted_keys = sorted(data_to_check.keys())

    data_check_string = []
    for key in sorted_keys:
        data_check_string.append(f"{key}={data_to_check[key]}")

    data_check_string = "\n".join(data_check_string)

    # 1. Секретний ключ
    secret_key = hashlib.sha256(TELEGRAM_BOT_TOKEN.encode('utf-8')).digest()

    # 2. Обчислюємо хеш
    calculated_hash = hmac.new(
        secret_key,
        data_check_string.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()

    if calculated_hash != received_hash:
        # Виводимо обидва хеші для діагностики, якщо знову виникне помилка
        app.logger.error(f"SECURITY ALERT: Hash mismatch (Manual parse failed). Calculated: {calculated_hash}, Received: {received_hash}")
        return None

    # Якщо хеш збігається, отримуємо user_id з JSON
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
        return None

    return validate_telegram_init_data(init_data)


# --- КІНЦЕВІ ТОЧКИ API ---

# 1. Обробка фото (Симуляція AI)
@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    user_info = get_user_data_from_request()
    if user_info is None:
        app.logger.error("DIAGNOSTIC: process_photo FAILED - Unauthorized.")
        return jsonify({"error": "Unauthorized"}), 401

    app.logger.error("DIAGNOSTIC: process_photo received JSON (Simulating AI response).")

    # !!! СИМУЛЯЦІЯ AI !!!
    time.sleep(1)
    meal_data = {
        "name": "Айвар із лавашем (Ручний Парсинг)",
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


# Створення таблиць при запуску (важливо для першого запуску)
with app.app_context():
     # Це забезпечує, що таблиці будуть створені, якщо файлу БД немає
     db.create_all()

# Для PythonAnywhere цей блок не виконується
if __name__ == '__main__':
    app.run(debug=True)
