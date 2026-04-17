# ============================================
# Файл: services/gemini.py (з компресією)
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
        
        self.model = "gemini-2.0-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        self.available = True
        logger.info(f"✅ Gemini configured with model: {self.model}")
    
    def _compress_image(self, image: Image.Image, max_size: int = 800, quality: int = 75) -> str:
        """
        Компресія зображення для зменшення токенів
        - max_size: максимальний розмір сторони (пікселі)
        - quality: якість JPEG (1-100, чим менше тим більша компресія)
        """
        original_size = image.size
        original_mode = image.mode
        
        # Конвертуємо в RGB
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        # Зменшуємо розмір (зберігаючи пропорції)
        if image.size[0] > max_size or image.size[1] > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"📐 Image resized: {original_size} -> {new_size}")
        
        # Зберігаємо з компресією
        img_buffer = io.BytesIO()
        image.save(img_buffer, format='JPEG', quality=quality, optimize=True)
        compressed_size = len(img_buffer.getvalue())
        
        logger.info(f"📦 Compressed size: {compressed_size} bytes (quality={quality})")
        
        return base64.b64encode(img_buffer.getvalue()).decode('utf-8')
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini з компресією"""
        
        if not self.available:
            return self._mock_analysis(photo_bytes, filename)
        
        try:
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            logger.info(f"📸 Original image: {image.size}, mode={image.mode}")
            
            # Компресуємо зображення
            base64_image = self._compress_image(image, max_size=800, quality=70)
            
            # Оптимізований промпт (коротший = менше токенів)
            prompt = """Analyze food. Return ONLY JSON:
{
    "name": "dish name in Ukrainian",
    "calories": number,
    "protein": number,
    "fat": number,
    "carbs": number,
    "feedback": "short recommendation in Ukrainian"
}
If unclear: {"name":"Невідомо","calories":0,"protein":0,"fat":0,"carbs":0,"feedback":"Не вдалося розпізнати"}"""
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                    ]
                }],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 300  # Зменшено для економії
                }
            }
            
            logger.info(f"🚀 Sending compressed request to Gemini...")
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.url, json=payload, timeout=30.0)
                
                if response.status_code != 200:
                    error_text = response.text[:200]
                    logger.error(f"Gemini API error {response.status_code}: {error_text}")
                    
                    if "429" in error_text:
                        return self._mock_analysis(photo_bytes, filename, error="quota_exceeded")
                    return self._mock_analysis(photo_bytes, filename, error=f"HTTP_{response.status_code}")
                
                data = response.json()
                
                if "candidates" in data and len(data["candidates"]) > 0:
                    text = data["candidates"][0]["content"]["parts"][0]["text"]
                    logger.info(f"📝 Gemini response received")
                    
                    # Парсимо JSON
                    text = re.sub(r'^```json\s*', '', text)
                    text = re.sub(r'^```\s*', '', text)
                    text = re.sub(r'\s*```$', '', text)
                    
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
                    return self._mock_analysis(photo_bytes, filename, error="no_candidates")
                    
        except asyncio.TimeoutError:
            logger.error("Gemini timeout")
            return self._mock_analysis(photo_bytes, filename, error="timeout")
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return self._mock_analysis(photo_bytes, filename, error=str(e)[:50])
    
    def _mock_analysis(self, photo_bytes: bytes, filename: str, error: str = None) -> Dict[str, Any]:
        """Тестовий аналіз при помилці API"""
        
        # Спрощене визначення за назвою файлу
        name_lower = filename.lower()
        
        if 'apple' in name_lower or 'яблуко' in name_lower:
            return {"name": "Яблуко", "calories": 95, "protein": 0.5, "fat": 0.3, "carbs": 25, "feedback": "🍎 Багате на клітковину"}
        elif 'banana' in name_lower or 'банан' in name_lower:
            return {"name": "Банан", "calories": 105, "protein": 1.3, "fat": 0.4, "carbs": 27, "feedback": "🍌 Джерело калію"}
        elif 'croissant' in name_lower or 'круасан' in name_lower:
            return {"name": "Круасан", "calories": 350, "protein": 8, "fat": 18, "carbs": 40, "feedback": "🥐 Краще обмежитись одним"}
        else:
            return {
                "name": "Страва", 
                "calories": 300, 
                "protein": 15, 
                "fat": 10, 
                "carbs": 35, 
                "feedback": "🧪 Тестовий режим. Оновіть API ключ."
            }
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування"""
        
        if not self.available:
            return self._mock_weekly_analysis(meals, averages, user_profile)
        
        try:
            # Коротший промпт для економії
            prompt = f"""Analyze weekly nutrition:
Daily avg: {averages.get('calories', 0):.0f} kcal
Give short analysis (2-3 sentences) in Ukrainian with recommendations."""
            
            payload = {
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {"temperature": 0.5, "maxOutputTokens": 300}
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
    
    def _mock_weekly_analysis(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Тестовий тижневий аналіз"""
        total_meals = len(meals)
        avg_calories = averages.get('calories', 0)
        
        return f"""📊 Тижневий звіт

За тиждень додано {total_meals} прийомів.
Середня калорійність: {avg_calories:.0f} ккал/день

💡 Додавайте більше прийомів їжі для точного аналізу!"""
