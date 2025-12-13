import os
import json
import hashlib
import hmac
from urllib.parse import parse_qsl

from flask import Flask, request, jsonify
from flask_cors import CORS

# --------------------------------------------------------------------------
# --- 1. КОНФІГУРАЦІЯ ТА ВАЛІДАЦІЯ TELEGRAM ---
# --------------------------------------------------------------------------

# !!! ВИПРАВЛЕНО !!! Тепер читаємо TELEGRAM_BOT_TOKEN, як ви вказали.
BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
if not BOT_TOKEN:
    print("FATAL ERROR: TELEGRAM_BOT_TOKEN is not set in environment variables.")

# Функція валідації initData (фікс проблеми 401 Unauthorized)
def validate_init_data(init_data: str) -> bool:
    """
    Перевіряє криптографічний підпис Telegram WebApp initData.
    """
    if not BOT_TOKEN:
        return False

    try:
        # Розділяємо initData на пари ключ-значення
        parsed_data = dict(parse_qsl(init_data))
        hash_to_check = parsed_data.pop('hash', None)
        
        if not hash_to_check:
            print("Validation failed: Hash not found in initData.")
            return False

        # Сортуємо пари ключ-значення за ключем і об'єднуємо через \n
        # Це критично для валідації Telegram!
        data_check_string = "\n".join(
            f"{key}={value}"
            for key, value in sorted(parsed_data.items())
        )

        # 1. Створення секретного ключа (HMAC SHA256 з ключем 'WebAppData')
        secret_key = hmac.new(
            key=b'WebAppData',
            msg=BOT_TOKEN.encode('utf-8'),
            digestmod=hashlib.sha256
        ).digest()

        # 2. Обчислення хешу від data_check_string
        calculated_hash = hmac.new(
            key=secret_key,
            msg=data_check_string.encode('utf-8'),
            digestmod=hashlib.sha256
        ).hexdigest()

        # 3. Порівняння
        return calculated_hash == hash_to_check
        
    except Exception as e:
        print(f"Validation error: {e}")
        return False

# Middleware для перевірки авторизації
def require_auth(f):
    """Декоратор, що вимагає валідації initData перед виконанням маршруту."""
    def wrapper(*args, **kwargs):
        data = request.get_json()
        init_data = data.get('initData')
        
        if not validate_init_data(init_data):
            # Повертаємо 401, якщо валідація не пройдена
            return jsonify({'error': 'Unauthorized'}), 401
        
        return f(*args, **kwargs)
    
    wrapper.__name__ = f.__name__
    return wrapper

# --------------------------------------------------------------------------
# --- 2. ЗАГЛУШКИ ДЛЯ ЛОГІКИ БАЗИ ДАНИХ ТА РОЗРАХУНКІВ (НЕ ЗМІНЮВАЛИСЯ) ---
# --------------------------------------------------------------------------

# ***УВАГА: ЗАМІНІТЬ ЦІ ЗАГЛУШКИ НА ВАШУ РЕАЛЬНУ ЛОГІКУ БД ТА РОЗРАХУНКІВ***

def calculate_target_calories(profile_data: dict) -> int:
    """Простий розрахунок цільових калорій."""
    # (ВАШ КОД РОЗРАХУНКУ ТУТ)
    return 2500 

def get_user_id_from_initdata(init_data: str) -> str:
    """Витягує Telegram user ID з initData"""
    # Це може вимагати детального парсингу initData
    return "tg_user_12345" 

def save_profile_data(profile_data: dict) -> int:
    """Зберігає профіль і повертає цільові калорії"""
    target_kcal = calculate_target_calories(profile_data)
    # (КОД ЗБЕРЕЖЕННЯ ВАШОЇ БД ТУТ)
    print(f"Saving profile for user... Target: {target_kcal} kcal") 
    return target_kcal

def get_profile_data(user_id: str) -> dict or None:
    """Отримує профіль користувача з БД"""
    # (КОД ОТРИМАННЯ З ВАШОЇ БД ТУТ)
    return {
        'name': 'Іван', 'weight': 75, 'height': 180, 'age': 30, 'gender': 'Чоловіча',
        'activity_level': 'Помірна', 'goal': 'Підтримка', 'water_target': 3000,
        'target_calories': 2200
    }

def get_daily_report_data(user_id: str) -> dict:
    """Отримує звіт для дашборду"""
    # (КОД ОТРИМАННЯ ЗВІТУ З ВАШОЇ БД ТУТ)
    return {
        'user_name': 'Іван', 'target': 2200, 'consumed': 1500, 'water_target': 3000,
        'water_consumed': 1000, 
        'date': '13 грудня', 
        'meals': [{'name': 'Сніданок', 'calories': 600, 'time': '08:00'}, 
                  {'name': 'Обід', 'calories': 900, 'time': '13:30'}]
    }

def process_photo_with_ai(image_base64: str) -> dict:
    """Імітація обробки фото AI"""
    # (КОД ВИКЛИКУ ВАШОГО AI-СЕРВІСУ ТУТ)
    return {
        'name': 'Паста Карбонара', 
        'calories': 750, 
        'description': 'Порція приблизно 300 грам. Високий вміст жирів та вуглеводів.'
    }
    
def save_meal_data(meal_data: dict, user_id: str) -> bool:
    """Зберігає прийом їжі в БД"""
    # (КОД ЗБЕРЕЖЕННЯ ЇЖІ ВАШОЇ БД ТУТ)
    return True

def save_water_data(amount: int, user_id: str) -> int:
    """Зберігає воду і повертає новий загальний об'єм"""
    # (КОД ОНОВЛЕННЯ ВОДИ ВАШОЇ БД ТУТ)
    return 1250 

# --------------------------------------------------------------------------
# --- 3. НАЛАШТУВАННЯ FLASK ТА МАРШРУТИ API (НЕ ЗМІНЮВАЛИСЯ) ---
# --------------------------------------------------------------------------

app = Flask(__name__)
CORS(app) 

@app.route('/', methods=['GET'])
def index():
    return "Telegram Meal Tracker Backend is running!", 200

@app.route('/api/get_profile', methods=['POST'])
@require_auth
def api_get_profile():
    data = request.get_json()
    user_id = get_user_id_from_initdata(data['initData'])
    profile = get_profile_data(user_id)
    
    if profile:
        return jsonify({'exists': True, 'data': profile}), 200
    else:
        return jsonify({'exists': False, 'data': None}), 200

@app.route('/api/save_profile', methods=['POST'])
@require_auth
def api_save_profile():
    profile_data = request.get_json()
    target_calories = save_profile_data(profile_data)
    
    return jsonify({'success': True, 'target_calories': target_calories}), 200

@app.route('/api/get_daily_report', methods=['POST'])
@require_auth
def api_get_daily_report():
    data = request.get_json()
    user_id = get_user_id_from_initdata(data['initData'])
    report_data = get_daily_report_data(user_id)
    return jsonify(report_data), 200

@app.route('/api/process_photo', methods=['POST'])
@require_auth
def api_process_photo():
    data = request.get_json()
    image_base64 = data.get('image_base64')
    if not image_base64:
        return jsonify({'error': 'Image data is missing'}), 400
    meal_data = process_photo_with_ai(image_base64)
    return jsonify(meal_data), 200

@app.route('/api/save_meal', methods=['POST'])
@require_auth
def api_save_meal():
    data = request.get_json()
    user_id = get_user_id_from_initdata(data['initData'])
    meal = data.get('meal')
    if save_meal_data(meal, user_id):
        return jsonify({'success': True}), 200
    return jsonify({'error': 'Failed to save meal'}), 500

@app.route('/api/save_water', methods=['POST'])
@require_auth
def api_save_water():
    data = request.get_json()
    user_id = get_user_id_from_initdata(data['initData'])
    amount = data.get('amount')
    new_amount = save_water_data(amount, user_id)
    return jsonify({'success': True, 'new_amount': new_amount}), 200


if __name__ == '__main__':
    app.run(debug=True, port=int(os.environ.get('PORT', 5000)))
