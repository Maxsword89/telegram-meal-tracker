# app.py (ФІНАЛЬНИЙ КОД)
from flask import Flask, request, jsonify
from urllib.parse import parse_qsl
import json
from datetime import datetime
from flask_cors import CORS

app = Flask(__name__)
CORS(app) # Дозволяє запити з Telegram WebApp

# --------------------------------------------------------------------------
# --- 1. ІМІТАЦІЯ БАЗИ ДАНИХ (Для тестування на Render) ---
# --------------------------------------------------------------------------
# Дані зберігаються в пам'яті сервера і будуть скинуті при перезавантаженні Render.

USER_PROFILES = {} # Зберігає профіль користувача (ім'я, ціль, вода)
USER_MEALS = {}    # Зберігає прийоми їжі {user_id: [{'name': '...', 'calories': 0, 'time': 'HH:MM'}, ...]}
USER_WATER = {}    # Зберігає споживання води {user_id: 1500}

# --------------------------------------------------------------------------
# --- 2. ДОПОМІЖНІ ФУНКЦІЇ ДЛЯ ОБРОБКИ ТА РОЗРАХУНКІВ ---
# --------------------------------------------------------------------------

def get_user_id_from_initdata(init_data: str) -> str:
    """Витягує Telegram user ID з initData"""
    try:
        parsed_data = dict(parse_qsl(init_data))
        user_json = json.loads(parsed_data.get('user', '{}'))
        return str(user_json.get('id', 'mock_user_id'))
    except:
        return 'mock_user_id'

def calculate_target_calories(profile_data: dict) -> int:
    """Розрахунок цільових калорій (дуже спрощений)"""
    # Хардкод, який гарантує, що ми бачимо різні числа
    weight = profile_data.get('weight', 75)
    
    if profile_data.get('goal') == 'Схуднення':
        base_kcal = weight * 25
        return int(base_kcal * 0.9)
    elif profile_data.get('goal') == 'Набір маси':
        base_kcal = weight * 35
        return int(base_kcal * 1.1)
    
    return int(weight * 30) # Підтримка

# --------------------------------------------------------------------------
# --- 3. ЛОГІКА ЗБЕРЕЖЕННЯ/ОТРИМАННЯ ДАНИХ (ІМІТАЦІЯ БД) ---
# --------------------------------------------------------------------------

def save_profile_data(profile_data: dict) -> int:
    """Зберігає профіль користувача"""
    user_id = get_user_id_from_initdata(profile_data['initData'])
    target_kcal = calculate_target_calories(profile_data)
    
    # ЗБЕРЕЖЕННЯ ПРОФІЛЮ
    profile_data['target_calories'] = target_kcal
    USER_PROFILES[user_id] = profile_data
    
    return target_kcal


def get_profile_data(user_id: str) -> dict or None:
    """Отримує профіль користувача"""
    
    profile = USER_PROFILES.get(user_id)
    
    if profile:
        return {
            'name': profile.get('name'), 
            'weight': profile.get('weight'), 
            'height': profile.get('height'), 
            'age': profile.get('age'), 
            'gender': profile.get('gender'),
            'activity_level': profile.get('activity_level'), 
            'goal': profile.get('goal'), 
            'water_target': profile.get('water_target'),
            'target_calories': profile.get('target_calories')
        }
    
    return None

# ФІКС 2 (ЗБЕРЕЖЕННЯ ЇЖІ)
def save_meal_data(user_id: str, meal: dict) -> bool:
    """Зберігає прийом їжі для поточного дня"""
    
    # Додаємо час
    meal['time'] = datetime.now().strftime('%H:%M')
    
    # Ініціалізація списку, якщо його немає
    if user_id not in USER_MEALS:
        USER_MEALS[user_id] = []
        
    # Додаємо прийом їжі
    USER_MEALS[user_id].append(meal)
    
    print(f"Meal saved for {user_id}: {meal['name']} ({meal['calories']} kcal)")
    return True

# ФІКС 3 (ЗБЕРЕЖЕННЯ ВОДИ)
def save_water_data(user_id: str, amount_ml: int) -> int:
    """Зберігає споживання води та повертає новий загальний обсяг"""
    
    current_amount = USER_WATER.get(user_id, 0)
    new_amount = current_amount + amount_ml
    
    # ЗБЕРЕЖЕННЯ ВОДИ
    USER_WATER[user_id] = new_amount
    
    print(f"Water saved for {user_id}: +{amount_ml}ml. Total: {new_amount}ml")
    return new_amount


def get_daily_report_data(user_id: str) -> dict:
    """Отримує звіт для дашборду, використовуючи збережені дані"""
    
    profile = get_profile_data(user_id)
    
    # Якщо профіль не знайдено (користувач вперше)
    if not profile:
        return {
            'user_name': 'Користувач', 'target': 2000, 'consumed': 0, 
            'water_target': 2500, 'water_consumed': 0, 
            'date': datetime.now().strftime('%d %B %Y'), 
            'meals': []
        }
    
    # Дані зі збереженого профілю
    user_name = profile['name']
    target_kcal = profile['target_calories']
    water_target = profile['water_target']
    
    # Дані зі збережених прийомів їжі
    meals = USER_MEALS.get(user_id, [])
    consumed_kcal = sum(meal['calories'] for meal in meals)
    
    # Дані зі збереженої води
    water_consumed = USER_WATER.get(user_id, 0)
        
    return {
        'user_name': user_name,
        'target': target_kcal, 
        'consumed': consumed_kcal, 
        'water_target': water_target,
        'water_consumed': water_consumed, 
        'date': datetime.now().strftime('%d %B %Y'), 
        'meals': meals
    }

# ФІКС 1: ФУНКЦІЯ AI-ОБРОБКИ (ТЕПЕР ПОВЕРТАЄ КОРЕКТНИЙ ОБ'ЄКТ)
def process_photo_with_ai(image_base64: str) -> dict:
    """Імітує обробку фото AI"""
    
    # Це приклад відповіді AI. Він має бути у форматі, який очікує фронтенд.
    return {
        'name': 'Приклад AI: Курячий салат',
        'calories': 450,
        'description': 'AI визначив: Куряче філе (200г), листя салату, помідори, соус на основі оливкової олії. Вуглеводи: 10г, Жири: 25г, Білки: 45г.'
    }


# --------------------------------------------------------------------------
# --- 4. МАРШРУТИ API (ENDPOINTS) ---
# --------------------------------------------------------------------------

@app.route('/api/get_profile', methods=['POST'])
def get_profile():
    data = request.json
    init_data = data.get('initData')
    user_id = get_user_id_from_initdata(init_data)
    
    profile = get_profile_data(user_id)
    
    if profile:
        return jsonify({'success': True, 'exists': True, 'data': profile})
    else:
        # Профіль не знайдено, користувач має заповнити форму
        return jsonify({'success': True, 'exists': False, 'data': None})


@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    try:
        # Валідація і збереження
        target_calories = save_profile_data(data)
        return jsonify({'success': True, 'target_calories': target_calories})
    except Exception as e:
        app.logger.error(f"Error saving profile: {e}")
        return jsonify({'success': False, 'error': 'Помилка збереження даних профілю'}), 500


@app.route('/api/get_daily_report', methods=['POST'])
def get_daily_report():
    data = request.json
    init_data = data.get('initData')
    user_id = get_user_id_from_initdata(init_data)
    
    report = get_daily_report_data(user_id)
    return jsonify(report)


@app.route('/api/process_photo', methods=['POST'])
def process_photo():
    data = request.json
    image_base64 = data.get('image_base64')
    
    if not image_base64:
        return jsonify({'success': False, 'error': 'Немає зображення'}), 400
        
    try:
        # Виклик функції, що імітує AI
        meal_data = process_photo_with_ai(image_base64)
        return jsonify(meal_data)
    except Exception as e:
        app.logger.error(f"Error processing photo: {e}")
        return jsonify({'success': False, 'error': f'Помилка AI: {e}'}), 500


@app.route('/api/save_meal', methods=['POST'])
def save_meal():
    data = request.json
    init_data = data.get('initData')
    meal = data.get('meal')
    user_id = get_user_id_from_initdata(init_data)
    
    if not meal:
        return jsonify({'success': False, 'error': 'Немає даних про прийом їжі'}), 400
    
    try:
        save_meal_data(user_id, meal)
        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"Error saving meal: {e}")
        return jsonify({'success': False, 'error': 'Помилка збереження прийому їжі'}), 500

@app.route('/api/save_water', methods=['POST'])
def save_water():
    data = request.json
    init_data = data.get('initData')
    amount = data.get('amount')
    user_id = get_user_id_from_initdata(init_data)

    if amount is None:
        return jsonify({'success': False, 'error': 'Не вказано кількість води'}), 400
    
    try:
        new_amount = save_water_data(user_id, amount)
        return jsonify({'success': True, 'new_amount': new_amount})
    except Exception as e:
        app.logger.error(f"Error saving water: {e}")
        return jsonify({'success': False, 'error': 'Помилка збереження води'}), 500


if __name__ == '__main__':
    # Для локального тестування
    app.run(debug=True)

# Для Render (Gunicorn)
# (не потрібно, Gunicorn використовує змінну `app`)
