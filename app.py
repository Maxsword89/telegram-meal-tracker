# app.py (ФІНАЛЬНИЙ КОД: ДОДАНО ОБСЛУГОВУВАННЯ HTML)
from flask import Flask, request, jsonify, send_from_directory # <<< ДОДАНО send_from_directory
from urllib.parse import parse_qsl
import json
from datetime import datetime
from flask_cors import CORS
import time 

app = Flask(__name__)
CORS(app) 

# --- 1. ІМІТАЦІЯ БАЗИ ДАНИХ ---
USER_PROFILES = {} 
USER_MEALS = {}    
USER_WATER = {}    

# --- 2. ДОПОМІЖНІ ФУНКЦІЇ ---

def get_user_id_from_initdata(init_data: str) -> str:
    """Витягує Telegram user ID з initData"""
    if not init_data:
        return 'mock_user_id'
    try:
        parsed_data = dict(parse_qsl(init_data))
        user_json = json.loads(parsed_data.get('user', '{}'))
        return str(user_json.get('id', 'mock_user_id'))
    except Exception as e:
        app.logger.error(f"Error parsing initData: {e}")
        return 'mock_user_id'

def calculate_target_calories(profile_data: dict) -> int:
    """Розрахунок цільових калорій (спрощений)"""
    weight = profile_data.get('weight', 75)
    base_kcal = weight * 30
    
    if profile_data.get('goal') == 'Схуднення':
        return int(base_kcal * 0.9) 
    elif profile_data.get('goal') == 'Набір маси':
        return int(base_kcal * 1.1) 
    
    return int(base_kcal) 

# --- 3. ЛОГІКА ЗБЕРЕЖЕННЯ/ОТРИМАННЯ ДАНИХ ---

def save_profile_data(profile_data: dict) -> int:
    user_id = get_user_id_from_initdata(profile_data['initData'])
    target_kcal = calculate_target_calories(profile_data)
    
    profile_data['target_calories'] = target_kcal
    USER_PROFILES[user_id] = profile_data
    
    return target_kcal


def get_profile_data(user_id: str) -> dict or None:
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

def save_meal_data(user_id: str, meal: dict) -> bool:
    meal['time'] = datetime.now().strftime('%H:%M')
    
    if user_id not in USER_MEALS:
        USER_MEALS[user_id] = []
        
    USER_MEALS[user_id].append(meal)
    
    return True

def save_water_data(user_id: str, amount_ml: int) -> int:
    current_amount = USER_WATER.get(user_id, 0)
    new_amount = current_amount + amount_ml
    
    USER_WATER[user_id] = new_amount
    
    return new_amount


def get_daily_report_data(user_id: str) -> dict:
    profile = get_profile_data(user_id)
    
    if not profile:
        return {
            'user_name': 'Користувач', 'target': 2000, 'consumed': 0, 
            'water_target': 2500, 'water_consumed': 0, 
            'date': datetime.now().strftime('%d %B %Y'), 
            'meals': []
        }
    
    user_name = profile['name']
    target_kcal = profile['target_calories']
    water_target = profile['water_target']
    
    meals = USER_MEALS.get(user_id, [])
    consumed_kcal = sum(meal['calories'] for meal in meals)
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


def process_photo_with_ai(image_base64: str) -> dict:
    """Імітує обробку фото AI"""
    time.sleep(2) 
    
    return {
        'name': 'Приклад AI: Курячий салат',
        'calories': 450,
        'description': 'AI визначив: Куряче філе (200г), листя салату, помідори, соус на основі оливкової олії. Вуглеводи: 10г, Жири: 25г, Білки: 45г.'
    }


# --- 4. МАРШРУТИ API (ENDPOINTS) ---

@app.route('/api/get_profile', methods=['POST'])
def get_profile():
    data = request.json
    init_data = data.get('initData')
    user_id = get_user_id_from_initdata(init_data)
    profile = get_profile_data(user_id)
    
    if profile:
        return jsonify({'success': True, 'exists': True, 'data': profile})
    else:
        return jsonify({'success': True, 'exists': False, 'data': None})


@app.route('/api/save_profile', methods=['POST'])
def save_profile():
    data = request.json
    try:
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

# --- 5. СТАТИЧНІ МАРШРУТИ (FIX 404 URL Not Found) ---
# Обслуговують index.html, profile.html та інші статичні файли
@app.route('/')
def serve_index():
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static(filename):
    return send_from_directory('.', filename)
# -----------------------------------------------------

if __name__ == '__main__':
    app.run(debug=True)
