import os
import json
import logging
from datetime import datetime
from urllib.parse import unquote
from pytz import timezone

# Бібліотеки Flask та Cors
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

# Бібліотеки для роботи з БД
import psycopg2
from psycopg2 import pool, extras

# --- КОНФІГУРАЦІЯ ---

app = Flask(__name__)

# Дозволяємо CORS для усіх джерел, якщо ви використовуєте Render
CORS(app) 

# Встановлюємо часовий пояс для коректної роботи з датами
SERVER_TZ = timezone('Europe/Kiev')

# Отримання змінних середовища
DATABASE_URL = os.environ.get('DATABASE_URL')
# BOT_TOKEN = os.environ.get('BOT_TOKEN') # Поки не використовується для hash-валідації

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# --- ПУЛ З'ЄДНАНЬ З БАЗОЮ ДАНИХ ---
try:
    postgreSQL_pool = psycopg2.pool.SimpleConnectionPool(
        1,  # minconn
        20, # maxconn
        DATABASE_URL
    )
    app.logger.info("Connection pool created successfully")
except Exception as e:
    app.logger.error(f"Error connecting to PostgreSQL database: {e}")
    # Якщо підключення до БД не вдалося, додаток не може працювати
    # У виробничому середовищі тут можна викликати sys.exit()
    # Але для Render ми просто будемо обробляти помилки в роутах.


def get_db_connection():
    """Отримує з'єднання з пулу."""
    return postgreSQL_pool.getconn()

def release_db_connection(conn):
    """Повертає з'єднання в пул."""
    postgreSQL_pool.putconn(conn)


# --- ФУНКЦІЯ ВАЛІДАЦІЇ TELEGRAM INITDATA ---
def validate_init_data(init_data, secret_key=None, hash_validation=False):
    """
    Розбирає initData для отримання user_id та username.
    
    SECURITY CHECK: HASH VALIDATION IS DISABLED.
    Тимчасово використовується лише для отримання user_id.
    """
    try:
        # initData - це рядок, закодований як URL
        decoded_data = unquote(init_data)
        
        data_parts = decoded_data.split('&')
        user_info = None
        user_id = None
        username = "Невідомий користувач"

        for part in data_parts:
            if part.startswith('user='):
                # Частина 'user={"id":123,"first_name":"...","username":"..."}'
                user_json_str = part[5:]
                user_info = json.loads(user_json_str)
                user_id = user_info.get('id')
                username = user_info.get('first_name', user_info.get('username', username))
                break
        
        if user_id is None:
            raise ValueError("User ID not found in initData")

        return user_id, username
        
    except Exception as e:
        app.logger.error(f"InitData validation failed: {e}")
        return None, None


# --- 1. РОУТ: ОТРИМАННЯ ЗВІТУ (ДАШБОРД) ---
@app.route('/api/get_daily_report', methods=['POST'])
@cross_origin()
def get_daily_report():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, _ = validate_init_data(init_data, secret_key=None, hash_validation=False)

    if not user_id:
        # У разі невдалої валідації повертаємо помилку
        return jsonify({"status": "error", "message": "Invalid initData"}), 401

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 1. Визначаємо початок і кінець сьогоднішнього дня у часовому поясі Києва
        now_tz = datetime.now(SERVER_TZ)
        today_start = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now_tz.replace(hour=23, minute=59, second=59, microsecond=999999)

        # 2. Запит для отримання ВСІХ прийомів їжі за сьогодні
        cur.execute("""
            SELECT 
                meal_name, 
                calories, 
                TO_CHAR(timestamp AT TIME ZONE 'UTC' AT TIME ZONE 'Europe/Kiev', 'HH24:MI') as meal_time 
            FROM meals 
            WHERE user_id = %s 
              AND timestamp >= %s 
              AND timestamp <= %s 
            ORDER BY timestamp ASC;
        """, (user_id, today_start, today_end))
        meals_records = cur.fetchall()
        
        # 3. Обробка результатів та розрахунок загальних калорій
        meals = []
        total_consumed = 0
        for name, calories, meal_time in meals_records:
            # Тут використовуємо реальну назву страви з бази даних
            meals.append({"time": meal_time, "name": name, "calories": calories})
            total_consumed += calories

        # 4. Формування фінального звіту
        target_calories = 2000 # TODO: Використовувати ціль з user_profile
        
        return jsonify({
            "target": target_calories,
            "consumed": total_consumed,
            "date": now_tz.strftime('%d %B %Y'),
            "meals": meals
        }), 200

    except Exception as e:
        app.logger.error(f"Error fetching daily report for user {user_id}: {e}")
        # Повертаємо порожній звіт у разі помилки БД
        return jsonify({
            "target": 2000,
            "consumed": 0,
            "date": datetime.now(SERVER_TZ).strftime('%d %B %Y'),
            "meals": []
        }), 200
    finally:
        if conn:
            release_db_connection(conn)


# --- 2. РОУТ: ЗБЕРЕЖЕННЯ ПРИЙОМУ ЇЖІ ---
@app.route('/api/save_meal', methods=['POST'])
@cross_origin()
def save_meal():
    data = request.get_json()
    init_data = data.get('initData', '')
    meal = data.get('meal', {})

    user_id, _ = validate_init_data(init_data, secret_key=None, hash_validation=False)
    
    if not user_id:
        return jsonify({"status": "error", "message": "Invalid initData"}), 401

    conn = None
    try:
        meal_name = meal.get('name')
        calories = int(meal.get('calories', 0))
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "INSERT INTO meals (user_id, meal_name, calories, timestamp) VALUES (%s, %s, %s, NOW())",
            (user_id, meal_name, calories)
        )
        
        conn.commit()
        app.logger.info(f"MEAL SAVED: User {user_id}, Meal: {meal_name} ({calories} kcal)")
        return jsonify({"status": "success", "message": "Meal saved successfully"}), 200
        
    except Exception as e:
        app.logger.error(f"Error saving meal for user {user_id}: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        if conn:
            release_db_connection(conn)


# --- 3. РОУТ: ІМІТАЦІЯ ОБРОБКИ ФОТО AI ---
@app.route('/api/process_photo', methods=['POST'])
@cross_origin()
def process_photo():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, _ = validate_init_data(init_data, secret_key=None, hash_validation=False)

    if not user_id:
        return jsonify({"status": "error", "message": "Invalid initData"}), 401
    
    # !!! ТИМЧАСОВА ЗАГЛУШКА !!!
    # У реальному проекті тут буде логіка виклику AI Vision API.
    
    # Використовуємо ID користувача для унікальності заглушки
    return jsonify({
        "name": f"Розпізнано (ID: {user_id})",
        "calories": 450, 
        "description": "Це тестовий результат, імітація розпізнавання: курка гриль та трохи овочів."
    }), 200


# --- 4. НОВИЙ РОУТ: ЗБЕРЕЖЕННЯ ПАРАМЕТРІВ КОРИСТУВАЧА ---
@app.route('/api/save_profile', methods=['POST'])
@cross_origin()
def save_user_profile():
    data = request.get_json()
    init_data = data.get('initData', '')
    profile_data = data.get('profile', {})

    user_id, username = validate_init_data(init_data, secret_key=None, hash_validation=False)

    if not user_id:
        return jsonify({"status": "error", "message": "Invalid initData"}), 401

    conn = None
    try:
        weight = profile_data.get('weight')
        height = profile_data.get('height')
        activity = profile_data.get('activity')
        night_shifts = profile_data.get('night_shifts', False)
        
        if not all([weight, height, activity]):
             return jsonify({"status": "error", "message": "Missing required profile fields"}), 400

        conn = get_db_connection()
        cur = conn.cursor()

        # UPSERT (INSERT OR UPDATE)
        cur.execute("""
            INSERT INTO user_profile (user_id, username, weight_kg, height_cm, activity_level, night_shifts, last_updated)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT (user_id) DO UPDATE 
            SET username = EXCLUDED.username,
                weight_kg = EXCLUDED.weight_kg,
                height_cm = EXCLUDED.height_cm,
                activity_level = EXCLUDED.activity_level,
                night_shifts = EXCLUDED.night_shifts,
                last_updated = NOW();
        """, (user_id, username, weight, height, activity, night_shifts))
        
        conn.commit()
        app.logger.info(f"PROFILE SAVED: User {user_id} saved profile data.")
        return jsonify({"status": "success", "message": "Profile saved successfully"}), 200

    except Exception as e:
        app.logger.error(f"Error saving profile for user {user_id}: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        if conn:
            release_db_connection(conn)


# --- 5. НОВИЙ РОУТ: ПЕРЕВІРКА ІСНУВАННЯ ПРОФІЛЮ ---
@app.route('/api/get_profile', methods=['POST'])
@cross_origin()
def get_user_profile():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, username = validate_init_data(init_data, secret_key=None, hash_validation=False)

    if not user_id:
        return jsonify({"status": "error", "message": "Invalid initData"}), 401

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("SELECT weight_kg, height_cm, activity_level, night_shifts FROM user_profile WHERE user_id = %s", (user_id,))
        profile_record = cur.fetchone()
        
        if profile_record:
            # Якщо профіль знайдено, повертаємо його
            weight, height, activity, night_shifts = profile_record
            return jsonify({
                "status": "success",
                "exists": True,
                "data": {
                    "weight": weight,
                    "height": height,
                    "activity": activity,
                    "night_shifts": night_shifts,
                }
            }), 200
        else:
            # Якщо профіль НЕ знайдено
            return jsonify({
                "status": "success",
                "exists": False
            }), 200

    except Exception as e:
        app.logger.error(f"Error checking profile for user {user_id}: {e}")
        return jsonify({"status": "error", "message": "Internal server error"}), 500
    finally:
        if conn:
            release_db_connection(conn)


if __name__ == '__main__':
    # На Render це не виконується, Gunicorn запускає додаток
    app.run(host='0.0.0.0', port=5000)
