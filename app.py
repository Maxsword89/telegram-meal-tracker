# --- app.py (ФІНАЛЬНИЙ КОД: ВИПРАВЛЕНА ОБРОБКА JSON ВІД GEMINI) ---

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
from google.genai.errors import APIError

# Бібліотеки Flask та Cors
from flask import Flask, request, jsonify
from flask_cors import CORS, cross_origin

# Бібліотеки для роботи з БД
import psycopg2
from psycopg2 import pool, extras

# --- КОНФІГУРАЦІЯ ---

app = Flask(__name__)
# Дозволяємо CORS для усіх джерел, щоб Mini App міг звертатися
CORS(app) 

SERVER_TZ = timezone('Europe/Kiev')

# Отримання змінних середовища
DATABASE_URL = os.environ.get('DATABASE_URL')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY') 

# Налаштування Gemini AI Client
client = None
if GEMINI_API_KEY:
    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        app.logger.info("Gemini client initialized successfully.")
    except Exception as e:
        app.logger.error(f"Error initializing Gemini client: {e}")
else:
    app.logger.error("GEMINI_API_KEY is not set.")

logging.basicConfig(level=logging.INFO)

# --- ПУЛ З'ЄДНАНЬ З БАЗОЮ ДАНИХ ---
try:
    postgreSQL_pool = psycopg2.pool.SimpleConnectionPool(
        1,  # minconn
        20, # maxconn
        DATABASE_URL,
        sslmode='require' 
    )
    app.logger.info("Connection pool created successfully.")
except Exception as e:
    app.logger.error(f"Error connecting to PostgreSQL database: {e}")

def get_db_connection():
    return postgreSQL_pool.getconn()

def release_db_connection(conn):
    postgreSQL_pool.putconn(conn)


# --- ФУНКЦІЯ ВАЛІДАЦІЇ TELEGRAM INITDATA ---
def validate_init_data(init_data):
    try:
        if not init_data:
             raise ValueError("InitData is empty.")
             
        decoded_data = unquote(init_data)
        data_parts = decoded_data.split('&')
        user_id = None
        username = "Користувач"

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


# --- 1. РОУТ: ОТРИМАННЯ ЗВІТУ (DASHBOARD) ---
@app.route('/api/get_daily_report', methods=['POST'])
@cross_origin()
def get_daily_report():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, _ = validate_init_data(init_data)

    if not user_id:
        return jsonify({"status": "error", "message": "Invalid initData"}), 401

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        now_tz = datetime.now(SERVER_TZ)
        today_start = now_tz.replace(hour=0, minute=0, second=0, microsecond=0)
        today_end = now_tz.replace(hour=23, minute=59, second=59, microsecond=999999)

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

        cur.execute("SELECT weight_kg, height_cm, activity_level FROM user_profile WHERE user_id = %s", (user_id,))
        profile_data = cur.fetchone()
        
        # TODO: Додайте логіку розрахунку цільових калорій тут
        target_calories = 2000 
        if profile_data:
             pass 

        return jsonify({
            "target": target_calories,
            "consumed": total_consumed,
            "date": now_tz.strftime('%d %B %Y'),
            "meals": meals
        }), 200

    except Exception as e:
        app.logger.error(f"Error fetching daily report for user {user_id}: {e}")
        # Повертаємо безпечний порожній набір даних у разі помилки
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

    user_id, _ = validate_init_data(init_data)
    
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


# --- 3. РОУТ: ОБРОБКА ФОТО AI (GEMINI VISION) - ПРИЙМАЄ BASE64 В JSON ТІЛІ ---
@app.route('/api/process_photo', methods=['POST'])
@cross_origin()
def process_photo():
    data = request.get_json()
    
    init_data = data.get('initData', '') 
    user_id, _ = validate_init_data(init_data)

    if not user_id:
        app.logger.error("InitData missing or invalid in JSON body.")
        return jsonify({"status": "error", "message": "Invalid initData"}), 401
    
    # 1. Отримуємо Base64 та MIME-тип
    base64_data = data.get('image_base64')
    mime_type = data.get('mime_type', 'image/jpeg') 
    
    if not base64_data:
        return jsonify({"status": "error", "message": "Missing Base64 image data"}), 400

    if not client:
        return jsonify({"status": "error", "message": "Gemini Client not initialized (API Key missing?)"}), 500

    try:
        # 2. Декодуємо Base64 у бінарні байти
        image_bytes = base64.b64decode(base64_data)
        
        # 3. Створюємо об'єкт Part для Gemini
        image_part = types.Part.from_bytes(
            data=image_bytes,
            mime_type=mime_type 
        )

        # 4. Підготовка інструкції для Gemini
        prompt = (
            "You are a professional nutritionist. Analyze the image of the food. "
            "Your task is to estimate the calories and name the dish. "
            "You MUST ONLY return a single JSON object in the following format: "
            "{'name': 'dish_name', 'calories': estimated_calories_integer, 'description': 'brief_description_in_ukrainian'} "
            "Estimate the calories for a standard portion shown in the photo. "
            "Translate dish_name and brief_description to Ukrainian."
        )
        
        # 5. Виклик Gemini Pro Vision
        response = client.models.generate_content(
            model='gemini-2.5-flash', 
            contents=[prompt, image_part]
        )
        
        # 6. Обробка відповіді: очищення від ```json...```
        json_str = response.text.strip().lstrip('```json').rstrip('```').strip() 

        try:
            meal_data = json.loads(json_str)
        except json.JSONDecodeError:
            # !!! ВИПРАВЛЕННЯ: Повертаємо 500 у разі помилки декодування JSON, логуючи сиру відповідь !!!
            app.logger.error(f"Gemini returned non-JSON response. Raw text: {response.text}")
            return jsonify({
                "status": "error", 
                "message": "AI returned invalid format. Please try another photo or report this issue."
            }), 500

        if not all(k in meal_data for k in ['name', 'calories', 'description']):
            app.logger.error(f"AI result is missing fields: {meal_data}")
            return jsonify({"status": "error", "message": "AI result is missing required fields."}), 500

        return jsonify({
            "name": meal_data['name'],
            "calories": int(meal_data['calories']),
            "description": meal_data['description']
        }), 200

    except APIError as e:
        app.logger.error(f"Gemini API Error: {e}")
        return jsonify({"status": "error", "message": f"Gemini API failed. Details: {e}"}), 500
    except Exception as e:
        app.logger.error(f"Error processing photo with Gemini: {e}")
        return jsonify({"status": "error", "message": f"AI processing failed: {e}"}), 500


# --- 4. РОУТ: ЗБЕРЕЖЕННЯ ПАРАМЕТРІВ КОРИСТУВАЧА ---
@app.route('/api/save_profile', methods=['POST'])
@cross_origin()
def save_user_profile():
    data = request.get_json()
    init_data = data.get('initData', '')
    profile_data = data.get('profile', {})

    user_id, username = validate_init_data(init_data)

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


# --- 5. РОУТ: ПЕРЕВІРКА ІСНУВАННЯ ПРОФІЛЮ ---
@app.route('/api/get_profile', methods=['POST'])
@cross_origin()
def get_user_profile():
    data = request.get_json()
    init_data = data.get('initData', '')
    user_id, _ = validate_init_data(init_data)

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
    # Використовуйте Gunicorn для продакшн, Flask для локального тестування
    app.run(host='0.0.0.0', port=5000)
