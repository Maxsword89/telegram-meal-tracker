import os
import json
import logging
import base64
from datetime import datetime
from urllib.parse import unquote
from pytz import timezone

# Бібліотеки Gemini AI
from google import genai
from google.genai import types

# Бібліотеки Flask та Cors
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

# Бібліотеки для роботи з БД
import psycopg2
from psycopg2 import pool, extras

# --- КОНФІГУРАЦІЯ ---

app = Flask(__name__)
CORS(app) 

# Встановлюємо часовий пояс для коректної роботи з датами
SERVER_TZ = timezone('Europe/Kiev')

# Отримання змінних середовища
DATABASE_URL = os.environ.get('DATABASE_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') # НОВИЙ КЛЮЧ
# BOT_TOKEN = os.environ.get('BOT_TOKEN') 

# Налаштування Gemini AI Client
if GEMINI_API_KEY:
    try:
        # Ініціалізуємо Gemini Client
        client = genai.Client(api_key=GEMINI_API_KEY)
    except Exception as e:
        app.logger.error(f"Error initializing Gemini client: {e}")
else:
    app.logger.error("GEMINI_API_KEY is not set.")

# Налаштування логування
logging.basicConfig(level=logging.INFO)

# --- ПУЛ З'ЄДНАНЬ З БАЗОЮ ДАНИХ (БЕЗ ЗМІН) ---
try:
    postgreSQL_pool = psycopg2.pool.SimpleConnectionPool(
        1,  # minconn
        20, # maxconn
        DATABASE_URL
    )
    app.logger.info("Connection pool created successfully")
except Exception as e:
    app.logger.error(f"Error connecting to PostgreSQL database: {e}")

def get_db_connection():
    """Отримує з'єднання з пулу."""
    return postgreSQL_pool.getconn()

def release_db_connection(conn):
    """Повертає з'єднання в пул."""
    postgreSQL_pool.putconn(conn)


# --- ФУНКЦІЯ ВАЛІДАЦІЇ TELEGRAM INITDATA (БЕЗ ЗМІН) ---
def validate_init_data(init_data, secret_key=None, hash_validation=False):
    """
    Розбирає initData для отримання user_id та username.
    """
    try:
        decoded_data = unquote(init_data)
        data_parts = decoded_data.split('&')
        user_info = None
        user_id = None
        username = "Невідомий користувач"

        for part in data_parts:
            if part.startswith('user='):
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


# --- 1. РОУТ: ОТРИМАННЯ ЗВІТУ (БЕЗ ЗМІН) ---
@app.route('/api/get_daily_report', methods=['POST'])
@cross_origin()
def get_daily_report():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, _ = validate_init_data(init_data, secret_key=None, hash_validation=False)

    if not user_id:
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
        
        meals = []
        total_consumed = 0
        for name, calories, meal_time in meals_records:
            meals.append({"time": meal_time, "name": name, "calories": calories})
            total_consumed += calories

        target_calories = 2000 # TODO: Використовувати ціль з user_profile
        
        return jsonify({
            "target": target_calories,
            "consumed": total_consumed,
            "date": now_tz.strftime('%d %B %Y'),
            "meals": meals
        }), 200

    except Exception as e:
        app.logger.error(f"Error fetching daily report for user {user_id}: {e}")
        return jsonify({
            "target": 2000,
            "consumed": 0,
            "date": datetime.now(SERVER_TZ).strftime('%d %B %Y'),
            "meals": []
        }), 200
    finally:
        if conn:
            release_db_connection(conn)


# --- 2. РОУТ: ЗБЕРЕЖЕННЯ ПРИЙОМУ ЇЖІ (БЕЗ ЗМІН) ---
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


# --- 3. РОУТ: ОБРОБКА ФОТО AI (ОНОВЛЕНО: ВИКОРИСТАННЯ GEMINI) ---
@app.route('/api/process_photo', methods=['POST'])
@cross_origin()
def process_photo():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, _ = validate_init_data(init_data, secret_key=None, hash_validation=False)

    if not user_id:
        return jsonify({"status": "error", "message": "Invalid initData"}), 401
    
    # Отримуємо Base64 рядок з фронтенду
    image_base64 = data.get('image_base64', None)
    
    if not image_base64:
        return jsonify({"status": "error", "message": "Missing image_base64 data"}), 400

    if not client:
        return jsonify({"status": "error", "message": "Gemini Client not initialized (API Key missing?)"}), 500

    try:
        # 1. Декодуємо Base64 у бінарні дані
        image_bytes = base64.b64decode(image_base64)
        
        # 2. Створюємо об'єкт Part для Gemini
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type='image/jpeg' # Припускаємо, що ми надсилаємо JPG
        )

        # 3. Підготовка інструкції для Gemini
        prompt = (
            "You are a professional nutritionist. Analyze the image of the food. "
            "Your task is to estimate the calories and name the dish. "
            "You MUST ONLY return a single JSON object in the following format: "
            "{'name': 'dish_name', 'calories': estimated_calories_integer, 'description': 'brief_description_in_ukrainian'} "
            "Estimate the calories for a standard portion shown in the photo. "
            "Translate dish_name and brief_description to Ukrainian."
        )
        
        # 4. Виклик Gemini Pro Vision
        response = client.models.generate_content(
            model='gemini-2.5-flash', # Використовуємо Flash, оскільки він швидкий та підтримує Vision
            contents=[prompt, image_part]
        )
        
        # 5. Обробка відповіді (Gemini часто додає зайві пробіли або markdown)
        json_str = response.text.strip().lstrip('```json').rstrip('```')
        
        try:
            meal_data = json.loads(json_str)
        except json.JSONDecodeError:
            app.logger.error(f"Gemini returned non-JSON response: {json_str}")
            return jsonify({"status": "error", "message": "AI returned invalid format."}), 500

        # Перевірка наявності необхідних полів
        if not all(k in meal_data for k in ['name', 'calories', 'description']):
            return jsonify({"status": "error", "message": "AI result is missing required fields."}), 500

        # Повертаємо дані у форматі, який очікує фронтенд
        return jsonify({
            "name": meal_data['name'],
            "calories": int(meal_data['calories']),
            "description": meal_data['description']
        }), 200

    except Exception as e:
        app.logger.error(f"Error processing photo with Gemini: {e}")
        # Повертаємо більш інформативну помилку
        return jsonify({"status": "error", "message": f"AI processing failed: {e}"}), 500


# --- 4. РОУТ: ЗБЕРЕЖЕННЯ ПАРАМЕТРІВ КОРИСТУВАЧА (БЕЗ ЗМІН) ---
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


# --- 5. РОУТ: ПЕРЕВІРКА ІСНУВАННЯ ПРОФІЛЮ (БЕЗ ЗМІН) ---
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
    app.run(host='0.0.0.0', port=5000)
