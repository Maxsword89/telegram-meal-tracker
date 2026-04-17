# ============================================
# Файл: services/gemini.py (з детальним логуванням)
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
        
        logger.info(f"🔍 GEMINI_API_KEY present: {bool(self.api_key)}")
        if self.api_key:
            logger.info(f"🔍 API_KEY first 10 chars: {self.api_key[:10]}...")
        
        if not self.api_key:
            logger.error("❌ GEMINI_API_KEY not set!")
            self.available = False
            return
        
        # Використовуємо gemini-2.0-flash (більш стабільний)
        self.model = "gemini-2.0-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        self.available = True
        logger.info(f"✅ Gemini configured with model: {self.model}")
        
        # Тестуємо API ключ
        try:
            test_payload = {
                "contents": [{"parts": [{"text": "Test"}]}]
            }
            import httpx
            response = httpx.post(self.url, json=test_payload, timeout=10)
            logger.info(f"🔍 API test response status: {response.status_code}")
            if response.status_code == 200:
                logger.info("✅ Gemini API key is valid!")
            else:
                logger.error(f"❌ Gemini API test failed: {response.status_code} - {response.text[:200]}")
                self.available = False
        except Exception as e:
            logger.error(f"❌ Gemini API test error: {e}")
            self.available = False
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini"""
        
        logger.info(f"📸 analyze_meal called, available: {self.available}")
        
        if not self.available:
            logger.warning("Gemini not available, using mock mode")
            return self._mock_analysis(photo_bytes, filename, error="not_available")
        
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
            logger.info(f"📸 Photo encoded, size: {len(base64_image)} chars")
            
            # Промпт для Gemini
            prompt = """Ти професійний нутриціолог. Проаналізуй це фото їжі.

Поверни ТІЛЬКИ JSON (без пояснень, без markdown):
{
    "name": "назва страви українською",
    "calories": число,
    "protein": число,
    "fat": число,
    "carbs": число,
    "feedback": "коротка рекомендація українською"
}

Якщо не впізнаєш: {"name": "Невідомо", "calories": 0, "protein": 0, "fat": 0, "carbs": 0, "feedback": "Не вдалося розпізнати"}"""
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 500
                }
            }
            
            logger.info(f"🚀 Sending request to Gemini API...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.url, json=payload, timeout=30.0)
                
                logger.info(f"📡 Response status: {response.status_code}")
                
                if response.status_code != 200:
                    error_text = response.text[:500]
                    logger.error(f"Gemini API error {response.status_code}: {error_text}")
                    
                    if "429" in error_text:
                        return self._mock_analysis(photo_bytes, filename, error="quota_exceeded")
                    elif "403" in error_text or "401" in error_text:
                        logger.error("API key invalid or expired")
                        return self._mock_analysis(photo_bytes, filename, error="invalid_key")
                    else:
                        return self._mock_analysis(photo_bytes, filename, error=f"HTTP_{response.status_code}")
                
                data = response.json()
                logger.info(f"📡 Response keys: {list(data.keys()) if data else 'none'}")
                
                # Парсимо відповідь
                if "candidates" in data and len(data["candidates"]) > 0:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info(f"📝 Gemini response: {text[:200]}")
                    
                    # Очищаємо від markdown
                    text = re.sub(r'^```json\s*', '', text)
                    text = re.sub(r'^```\s*', '', text)
                    text = re.sub(r'\s*```$', '', text)
                    
                    # Шукаємо JSON
                    json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
                    if json_match:
                        text = json_match.group()
                    
                    analysis = json.loads(text)
                    
                    result = {
                        "name": analysis.get("name", "Невідомо"),
                        "calories": max(0, int(analysis.get("calories", 0))),
                        "protein": max(0, float(analysis.get("protein", 0))),
                        "fat": max(0, float(analysis.get("fat", 0))),
                        "carbs": max(0, float(analysis.get("carbs", 0))),
                        "feedback": analysis.get("feedback", "✅ Смачного!")
                    }
                    logger.info(f"✅ Analysis result: {result['name']} - {result['calories']} kcal")
                    return result
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
        """Аналіз тижневого харчування"""
        
        if not self.available:
            return self._mock_weekly_analysis(meals, averages, user_profile)
        
        try:
            prompt = f"""Проаналізуй харчування за тиждень:

Середні показники за день:
- Калорії: {averages.get('calories', 0):.0f} ккал
- Білки: {averages.get('protein', 0):.1f} г
- Жири: {averages.get('fat', 0):.1f} г
- Вуглеводи: {averages.get('carbs', 0):.1f} г

Напиши короткий аналіз українською (3-5 речень) з рекомендаціями."""
            
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
        """Тестовий аналіз"""
        logger.info(f"📸 Using MOCK analysis, error: {error}")
        
        import random
        meals = [
            {"name": "Вівсянка з ягодами", "calories": 320, "protein": 12, "fat": 8, "carbs": 48, "feedback": "🥣 Чудовий сніданок!"},
            {"name": "Гречка з куркою", "calories": 450, "protein": 35, "fat": 12, "carbs": 45, "feedback": "🍗 Відмінний обід!"},
            {"name": "Рис з овочами", "calories": 380, "protein": 10, "fat": 8, "carbs": 65, "feedback": "🍚 Ситно та корисно!"}
        ]
        meal = random.choice(meals)
        if error:
            meal["feedback"] = f"⚠️ Тестовий режим (помилка: {error}). {meal['feedback']}"
        return meal
    
    def _mock_weekly_analysis(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Тестовий тижневий аналіз"""
        total_meals = len(meals)
        avg_calories = averages.get('calories', 0)
        
        return f"""📊 *Тижневий звіт (Тестовий режим)*

За тиждень додано *{total_meals}* прийомів.
Середня калорійність: *{avg_calories:.0f}* ккал/день

💡 *Порада:* Додавайте більше прийомів їжі!"""
