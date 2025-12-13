from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os
import time
import sqlite3
from datetime import datetime

# --- КОНФІГУРАЦІЯ FLASK ТА БД ---
app = Flask(__name__, static_folder='.')
CORS(app) 

# Шлях до файлу бази даних SQLite
DATABASE = 'app_tracker.db'

# Базовий користувач (для імітації авторизації)
MOCK_USER_ID = "123456789" 
MOCK_USER_NAME = "Макс"

# --- ФУНКЦІЇ РОБОТИ З БАЗОЮ ДАНИХ (SQLite) ---

def get_db_connection():
    """Створює та повертає з'єднання з БД."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row 
    return conn

def init_db():
    """Ініціалізує базу даних: створює таблиці, якщо вони не існують."""
    with app.app_context():
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Таблиця для прийомів води
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS water_intake (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                amount INTEGER NOT NULL,
                timestamp TEXT NOT NULL
            )
        """)
        
        # Таблиця для профілю (ОНОВЛЕНО: додано поля для розрахунку калорій)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS user_profile (
                user_id TEXT PRIMARY KEY,
                name TEXT,
                weight REAL,
                height INTEGER,
                age INTEGER,
                gender TEXT,
                activity_level TEXT,
                goal TEXT,
                target_calories INTEGER, -- НОВЕ ПОЛЕ ДЛЯ ЗБЕРЕЖЕННЯ ЦІЛІ
                water_target INTEGER
            )
        """)
        
        conn.commit()
        conn.close()

init_db()

# --- АЛГОРИТМ РОЗРАХУНКУ (З ВАШОГО КОДУ) ---

def calculate_target_calories(weight, height, age, gender, activity_level, goal):
    """
    Виконує повний розрахунок BMR, TDEE та цільової норми калорій.
    """
    
    # 1. Розрахунок BMR (Міффлін-Сан-Жеор)
    if gender == "Чоловіча":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else: # Жіноча
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161
        
    # 2. Визначення Коефіцієнта Активності (AM)
    activity_map = {
        "Мінімальна": 1.2,
        "Легка": 1.375,
        "Помірна": 1.55,
        "Висока": 1.725,
        "Екстремальна": 1.9
    }
    am = activity_map.get(activity_level, 1.2)
    
    # 3. Розрахунок TDEE
    tdee = bmr * am
    
    # 4. Коригування під Мету
    if goal == "Схуднення":
        target_kcal = tdee * 0.85
    elif goal == "Набір маси":
        target_kcal = tdee * 1.15
    else: # Підтримка ваги
        target_kcal = tdee
        
    return round(target_kcal)
# -------------------------------------------------------------

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def authenticate_user(init_data):
    if init_data and MOCK_USER_ID in init_data:
        return MOCK_USER_ID
    return None

def get_today_water_intake(user_id):
    conn = get_db_connection()
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    query = """
        SELECT SUM(amount) AS total_water 
        FROM water_intake 
        WHERE user_id = ? AND timestamp >= ?
    """
    result = conn.execute(query, (user_id, today_start)).fetchone()
    conn.close()
    return result['total_water'] if result and result['total_water'] else 0

def get_user_profile(user_id):
    conn = get_db_connection()
    profile = conn.execute("SELECT * FROM user_profile WHERE user_id = ?", (user_id,)).fetchone()
    conn.close()
    
    # Повертаємо об'єкт Row або None
    return profile

# ІМІТАЦІЯ ДАНИХ (для прийомів їжі, поки вони не в БД)
MOCK_MEALS = [] # Тепер порожній список, щоб відображати "Сьогодні ще не було..."
MOCK_TOTAL_CALORIES = 0 
# -------------------------------------------------------------


# --- РОУТИ API ---

@app.route('/profile.html') # Обслуговує сторінку профілю
def serve_profile():
    return send_from_directory(app.static_folder, 'profile.html')

@app.route('/')
def serve_index():
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory(app.static_folder, filename)

@app.route('/api/get_profile', methods=['POST'])
def get_profile():
    """Перевіряє, чи існує профіль користувача, і повертає дані."""
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if user_id:
        profile = get_user_profile(user_id)
        
        if profile:
            # Якщо профіль існує, повертаємо його дані
            profile_data = dict(profile)
            return jsonify({"exists": True, "data": profile_data}), 200
        
        # Якщо профіль не існує, повертаємо false
        return jsonify({"exists": False}), 200
    
    return jsonify({"exists": False}), 200

@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    """
    Зберігає дані профілю, виконує розрахунок цільової норми та зберігає в БД.
    """
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        # Зчитування та валідація вхідних даних
        name = data.get('name', MOCK_USER_NAME)
        weight = float(data.get('weight', 0))
        height = int(data.get('height', 0))
        age = int(data.get('age', 0))
        gender = data.get('gender', 'Чоловіча')
        activity = data.get('activity_level', 'Мінімальна') 
        goal = data.get('goal', 'Підтримка')
        water_target = int(data.get('water_target', 2500)) # Ціль по воді
        
        if not (weight > 0 and height > 0 and age > 0):
             return jsonify({"error": "Invalid profile data"}), 400

        # ВИКОНАННЯ РОЗРАХУНКУ
        target_calories = calculate_target_calories(weight, height, age, gender, activity, goal)
        
        # Збереження даних (профіль + цільова норма) в БД
        conn = get_db_connection()
        conn.execute(
            """INSERT OR REPLACE INTO user_profile 
               (user_id, name, weight, height, age, gender, activity_level, goal, target_calories, water_target) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (user_id, name, weight, height, age, gender, activity, goal, target_calories, water_target)
        )
        conn.commit()
        conn.close()
        
        return jsonify({"success": True, "target_calories": target_calories}), 200
        
    except Exception as e:
        app.logger.error(f"Error saving profile and calculating calories: {e}")
        return jsonify({"error": "Processing error"}), 500


@app.route('/api/get_daily_report', methods=['POST'])
def get_daily_report():
    """
    Повертає дані для дашборда, з РЕАЛЬНИМИ даними води та цільовими калоріями.
    """
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    profile = get_user_profile(user_id)
    
    # Використовуємо дані з профілю, якщо вони існують
    target_kcal = profile['target_calories'] if profile and profile['target_calories'] else 2000
    target_water = profile['water_target'] if profile and profile['water_target'] else 2500
    user_name = profile['name'] if profile and profile['name'] else MOCK_USER_NAME

    # Отримання даних про воду з SQLite
    water_consumed_real = get_today_water_intake(user_id)
    
    report_data = {
        "user_name": user_name,
        "target": target_kcal,
        "consumed": MOCK_TOTAL_CALORIES,
        "meals": MOCK_MEALS,
        "water_target": target_water,
        "water_consumed": water_consumed_real, 
        "date": datetime.now().strftime("%d %B, %Y")
    }
    
    return jsonify(report_data), 200


@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    """Імітує обробку фото AI та повертає результат."""
    # (Логіка залишається без змін)
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    time.sleep(2) 
    
    mock_response = {
        "name": "Медовик",
        "calories": 450, 
        "description": "Класичний десерт із медовими коржами та ніжним сметанним кремом. Подано невелику порцію.",
    }
    
    return jsonify(mock_response), 200


@app.route('/api/save_meal', methods=['POST'])
def save_meal():
    """Зберігає прийом їжі (поки що лише імітація)."""
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    return jsonify({"success": True}), 200


@app.route('/api/save_water', methods=['POST'])
def save_water():
    """Зберігає прийом води в реальній базі даних SQLite."""
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    amount = data.get('amount')
    if not isinstance(amount, int) or amount <= 0:
        return jsonify({"error": "Invalid water amount"}), 400

    try:
        conn = get_db_connection()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        conn.execute(
            "INSERT INTO water_intake (user_id, amount, timestamp) VALUES (?, ?, ?)",
            (user_id, amount, timestamp)
        )
        conn.commit()
        conn.close()

        new_total_water = get_today_water_intake(user_id)

        return jsonify({"success": True, "new_amount": new_total_water}), 200

    except Exception as e:
        app.logger.error(f"Database error on save_water: {e}")
        return jsonify({"error": "Database write error"}), 500


# --- ЗАПУСК ---

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
