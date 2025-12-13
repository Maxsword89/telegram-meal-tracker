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
MOCK_CALORIES_TARGET = 2000
MOCK_WATER_TARGET = 2500

# --- ФУНКЦІЇ РОБОТИ З БАЗОЮ ДАНИХ (SQLite) ---

def get_db_connection():
    """Створює та повертає з'єднання з БД."""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row # Дозволяє отримувати результат як словник
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
        
        conn.commit()
        conn.close()

# Ініціалізуємо БД при запуску
init_db()

# --- ДОПОМІЖНІ ФУНКЦІЇ ---

def authenticate_user(init_data):
    """Імітація перевірки initData для отримання user_id."""
    # У реальному застосунку тут буде складна перевірка хешу Telegram.
    if init_data and MOCK_USER_ID in init_data:
        return MOCK_USER_ID
    return None

def get_today_water_intake(user_id):
    """Розраховує загальну кількість води, спожитої сьогодні, з БД."""
    conn = get_db_connection()
    today_start = datetime.now().strftime("%Y-%m-%d 00:00:00")
    
    # Сумуємо воду, додану сьогодні
    query = """
        SELECT SUM(amount) AS total_water 
        FROM water_intake 
        WHERE user_id = ? AND timestamp >= ?
    """
    
    result = conn.execute(query, (user_id, today_start)).fetchone()
    conn.close()
    
    # Повертаємо загальну суму або 0
    return result['total_water'] if result and result['total_water'] else 0

# --- ІМІТАЦІЯ ДАНИХ (для інших метрик, поки вони не в БД) ---

MOCK_MEALS = [
    {"time": "08:30", "name": "Вівсянка з ягодами", "calories": 350},
    {"time": "13:15", "name": "Курячий салат", "calories": 500},
    {"time": "18:40", "name": "Медовик", "calories": 400},
]
MOCK_TOTAL_CALORIES = sum(m['calories'] for m in MOCK_MEALS)
# -------------------------------------------------------------


# --- РОУТИ API ---

@app.route('/')
def serve_index():
    """Обслуговує головну сторінку index.html."""
    return send_from_directory(app.static_folder, 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Обслуговує статичні файли (CSS, JS)."""
    return send_from_directory(app.static_folder, filename)

@app.route('/api/get_profile', methods=['POST'])
def get_profile():
    """Перевіряє, чи існує профіль користувача (імітація)."""
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if user_id:
        return jsonify({"exists": True, "name": MOCK_USER_NAME}), 200
    
    return jsonify({"exists": False}), 200


@app.route('/api/get_daily_report', methods=['POST'])
def get_daily_report():
    """
    Повертає дані для дашборда, тепер з РЕАЛЬНИМИ даними води з SQLite.
    """
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    # 1. Отримання даних про воду з SQLite
    water_consumed_real = get_today_water_intake(user_id)
    
    # 2. Формування звіту (інші поля поки імітовані)
    report_data = {
        "target": MOCK_CALORIES_TARGET,
        "consumed": MOCK_TOTAL_CALORIES,
        "meals": MOCK_MEALS,
        "water_target": MOCK_WATER_TARGET,
        "water_consumed": water_consumed_real, # <--- РЕАЛЬНЕ ЗНАЧЕННЯ З БД
        "date": datetime.now().strftime("%d %B, %Y")
    }
    
    return jsonify(report_data), 200


@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    """Імітує обробку фото AI та повертає результат."""
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
    """
    Зберігає прийом їжі (поки що лише імітація, без додавання до БД).
    У реальній версії тут буде запис у таблицю Meals.
    """
    data = request.json
    user_id = authenticate_user(data.get('initData'))
    
    if not user_id:
        return jsonify({"error": "Unauthorized"}), 401
    
    # Оскільки ми зараз не зберігаємо всі прийоми їжі в SQLite, 
    # ми просто підтверджуємо успіх.
    return jsonify({"success": True}), 200


@app.route('/api/save_water', methods=['POST'])
def save_water():
    """
    НОВИЙ РОУТ: Зберігає прийом води в реальній базі даних SQLite.
    """
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
        
        # Вставка нового запису про воду в БД
        conn.execute(
            "INSERT INTO water_intake (user_id, amount, timestamp) VALUES (?, ?, ?)",
            (user_id, amount, timestamp)
        )
        conn.commit()
        conn.close()

        # Повертаємо оновлену загальну кількість води (для перевірки)
        new_total_water = get_today_water_intake(user_id)

        return jsonify({"success": True, "new_amount": new_total_water}), 200

    except Exception as e:
        app.logger.error(f"Database error on save_water: {e}")
        return jsonify({"error": "Database write error"}), 500


# --- ЗАПУСК ---

if __name__ == '__main__':
    # Встановлюємо порт, який використовує Render або стандартний 5000
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
