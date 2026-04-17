# ============================================
# Файл: services/gemini.py (gemini-2.5-flash)
# ============================================
import os
import logging
import base64
import json
import re
import asyncio
import httpx
from typing import Dict, Any, List
from PIL import Image
import io

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        
        if not self.api_key:
            logger.error("❌ GEMINI_API_KEY not set!")
            self.available = False
            return
        
        # Використовуємо gemini-2.5-flash через HTTP API
        self.model = "gemini-2.5-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        self.available = True
        logger.info(f"✅ Gemini 2.5 Flash configured via HTTP API")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini 2.5 Flash"""
        
        if not self.available:
            logger.warning("Gemini not available, using mock mode")
            return self._mock_analysis(photo_bytes, filename)
        
        try:
            # Оптимізуємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Зменшуємо для швидкості
            max_size = 1024
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Конвертуємо в base64
            img_buffer = io.BytesIO()
            image.save(img_buffer, format='JPEG', quality=85)
            base64_image = base64.b64encode(img_buffer.getvalue()).decode('utf-8')
            
            # Промпт для Gemini
            prompt = """Ти професійний нутриціолог. Проаналізуй це фото їжі.

Поверни ТІЛЬКИ JSON (без пояснень, без markdown):
{
    "name": "назва страви українською",
    "calories": число (калорії),
    "protein": число (білки в грамах),
    "fat": число (жири в грамах),
    "carbs": число (вуглеводи в грамах),
    "feedback": "коротка корисна рекомендація українською (1 речення)"
}

Якщо не впізнаєш страву: {"name": "Невідомо", "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "feedback": "Не вдалося розпізнати страву"}"""
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "topP": 0.95,
                    "topK": 40,
                    "maxOutputTokens": 500
                }
            }
            
            logger.info(f"🚀 Sending request to Gemini 2.5 Flash...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.url, json=payload, timeout=30.0)
                
                if response.status_code != 200:
                    error_text = response.text[:200]
                    logger.error(f"Gemini API error {response.status_code}: {error_text}")
                    
                    if "429" in error_text:
                        return self._mock_analysis(photo_bytes, filename, error="quota_exceeded")
                    elif "403" in error_text or "401" in error_text:
                        logger.error("API key invalid or expired")
                        return self._mock_analysis(photo_bytes, filename, error="invalid_key")
                    else:
                        return self._mock_analysis(photo_bytes, filename, error=str(response.status_code))
                
                data = response.json()
                
                # Парсимо відповідь
                if "candidates" in data and len(data["candidates"]) > 0:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info(f"Gemini response: {text[:200]}")
                    
                    # Очищаємо від markdown
                    text = re.sub(r'^```json\s*', '', text)
                    text = re.sub(r'^```\s*', '', text)
                    text = re.sub(r'\s*```$', '', text)
                    
                    # Шукаємо JSON
                    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                    if json_match:
                        text = json_match.group()
                    
                    analysis = json.loads(text)
                    
                    return {
                        "name": analysis.get("name", "Невідомо"),
                        "calories": max(0, int(analysis.get("calories", 0))),
                        "protein": max(0, float(analysis.get("protein", 0))),
                        "fat": max(0, float(analysis.get("fat", 0))),
                        "carbs": max(0, float(analysis.get("carbs", 0))),
                        "feedback": analysis.get("feedback", "✅ Смачного!")
                    }
                else:
                    logger.error(f"Unexpected API response: {data}")
                    return self._mock_analysis(photo_bytes, filename, error="no_candidates")
                    
        except asyncio.TimeoutError:
            logger.error("Gemini timeout after 30 seconds")
            return self._mock_analysis(photo_bytes, filename, error="timeout")
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {e}")
            return self._mock_analysis(photo_bytes, filename, error="json_error")
        except Exception as e:
            logger.error(f"Gemini error: {e}", exc_info=True)
            return self._mock_analysis(photo_bytes, filename, error=str(e)[:50])
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування через Gemini 2.5 Flash"""
        
        if not self.available:
            return self._mock_weekly_analysis(meals, averages, user_profile)
        
        try:
            prompt = f"""Проаналізуй харчування за тиждень:

Середні показники за день:
- Калорії: {averages.get('calories', 0):.0f} ккал
- Білки: {averages.get('protein', 0):.1f} г
- Жири: {averages.get('fat', 0):.1f} г
- Вуглеводи: {averages.get('carbs', 0):.1f} г

Кількість прийомів: {len(meals)}"""

            if user_profile:
                prompt += f"""

Дані користувача:
- Вік: {user_profile.get('age')}
- Стать: {user_profile.get('gender')}
- Вага: {user_profile.get('weight')} кг
- Зріст: {user_profile.get('height')} см
- Ціль: {user_profile.get('goal')}
- Норма калорій: {user_profile.get('daily_calorie_goal')} ккал"""

            prompt += """

Напиши короткий аналіз українською мовою (3-5 речень):
1. Загальна оцінка
2. Що можна покращити
3. 1-2 рекомендації

Будь дружнім, використовуй емодзі."""

            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.5, "maxOutputTokens": 500}
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.url, json=payload, timeout=30.0)
                
                if response.status_code != 200:
                    return self._mock_weekly_analysis(meals, averages, user_profile)
                
                data = response.json()
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                else:
                    return self._mock_weekly_analysis(meals, averages, user_profile)
                    
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return self._mock_weekly_analysis(meals, averages, user_profile)
    
    def _mock_analysis(self, photo_bytes: bytes, filename: str, error: str = None) -> Dict[str, Any]:
        """Тестовий аналіз (коли Gemini недоступний)"""
        
        filename_lower = filename.lower()
        
        if 'apple' in filename_lower or 'яблуко' in filename_lower:
            return {"name": "Яблуко", "calories": 95, "protein": 0.5, "fat": 0.3, "carbs": 25, "feedback": "🍎 Яблуко - чудовий вибір! Багате на клітковину."}
        elif 'banana' in filename_lower or 'банан' in filename_lower:
            return {"name": "Банан", "calories": 105, "protein": 1.3, "fat": 0.4, "carbs": 27, "feedback": "🍌 Банан - гарне джерело енергії та калію."}
        elif 'croissant' in filename_lower or 'круасан' in filename_lower:
            return {"name": "Круасан", "calories": 350, "protein": 8, "fat": 18, "carbs": 40, "feedback": "🥐 Круасан смачний, але краще обмежитися одним."}
        elif 'pizza' in filename_lower or 'піца' in filename_lower:
            return {"name": "Піца", "calories": 285, "protein": 12, "fat": 10, "carbs": 35, "feedback": "🍕 Піца смачна, але краще обмежитися одним шматочком."}
        elif 'salad' in filename_lower or 'салат' in filename_lower:
            return {"name": "Салат", "calories": 150, "protein": 5, "fat": 8, "carbs": 15, "feedback": "🥗 Чудовий вибір! Багато клітковини."}
        else:
            import random
            meals = [
                {"name": "Вівсянка з ягодами", "calories": 320, "protein": 12, "fat": 8, "carbs": 48, "feedback": "🥣 Чудовий сніданок! Багато клітковини."},
                {"name": "Гречка з куркою", "calories": 450, "protein": 35, "fat": 12, "carbs": 45, "feedback": "🍗 Відмінний обід! Добре збалансовано."},
                {"name": "Рис з овочами", "calories": 380, "protein": 10, "fat": 8, "carbs": 65, "feedback": "🍚 Ситно та корисно."},
                {"name": "Сирники", "calories": 280, "protein": 18, "fat": 12, "carbs": 25, "feedback": "🥞 Смачний сніданок! Багато кальцію."}
            ]
            meal = random.choice(meals)
            if error:
                meal["feedback"] = f"⚠️ Тестовий режим (Gemini: {error}). {meal['feedback']}"
            return meal
    
    def _mock_weekly_analysis(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Тестовий тижневий аналіз"""
        total_meals = len(meals)
        avg_calories = averages.get('calories', 0)
        
        recommendations = []
        if avg_calories < 1500:
            recommendations.append("🔸 Збільште калорійність раціону")
        elif avg_calories > 2500:
            recommendations.append("🔸 Зменште калорійність раціону")
        else:
            recommendations.append("🔸 Калорійність в нормі")
        
        if avg_calories < 60:
            recommendations.append("🔸 Додайте більше білка")
        
        if total_meals < 14:
            recommendations.append("🔸 Додавайте більше прийомів їжі")
        
        return f"""📊 *Тижневий звіт*

За тиждень додано *{total_meals}* прийомів їжі.
Середня калорійність: *{avg_calories:.0f}* ккал/день

*Рекомендації:*
{chr(10).join(recommendations)}

💡 *Порада:* Додавайте більше прийомів їжі для точнішого аналізу!"""
