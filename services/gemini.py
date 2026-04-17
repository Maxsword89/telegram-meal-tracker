# ============================================
# Файл: services/gemini.py (ВИПРАВЛЕНИЙ)
# ============================================
import os
import logging
import google.generativeai as genai
from PIL import Image
import io
import json
import re
import asyncio
from typing import Dict, Any, List

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.available = False
        self.model = None
        api_key = os.getenv("GEMINI_API_KEY")
        
        logger.info(f"🔑 GEMINI_API_KEY present: {bool(api_key)}")
        
        if not api_key:
            logger.error("❌ GEMINI_API_KEY not set! Please add it in Render environment variables.")
            return
        
        try:
            genai.configure(api_key=api_key)
            logger.info("✅ Gemini configured successfully")
            
            # Список актуальних моделей (оновлено)
            models_to_try = [
                'gemini-2.0-flash',
                'gemini-1.5-flash',
                'gemini-1.5-pro',
                'gemini-pro'
            ]
            
            for model_name in models_to_try:
                try:
                    logger.info(f"🔄 Trying model: {model_name}")
                    test_model = genai.GenerativeModel(model_name)
                    # Короткий тест
                    test_response = test_model.generate_content("Test")
                    if test_response and test_response.text:
                        self.model = test_model
                        self.available = True
                        logger.info(f"✅ Gemini model initialized: {model_name}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ Model {model_name} failed: {str(e)[:100]}")
                    continue
            
            if not self.available:
                logger.warning("⚠️ No Gemini model available. Using mock mode.")
                
        except Exception as e:
            logger.error(f"❌ Gemini initialization error: {e}")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini (з fallback)"""
        
        # Якщо Gemini не доступний, використовуємо тестовий режим
        if not self.available or not self.model:
            logger.info("📸 Using mock mode for meal analysis")
            return self._mock_analysis(photo_bytes, filename)
        
        try:
            # Відкриваємо фото
            image = Image.open(io.BytesIO(photo_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Стискаємо
            max_size = 1024
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
            
            # Промпт
            prompt = """Analyze this food image. Return ONLY valid JSON:
{
    "name": "dish name in Ukrainian",
    "calories": number,
    "protein": number,
    "fat": number,
    "carbs": number,
    "feedback": "short recommendation in Ukrainian (1 sentence)"
}"""
            
            # Запит з таймаутом
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, image])),
                timeout=25.0
            )
            
            text = response.text.strip()
            logger.info(f"Gemini response: {text[:200]}")
            
            # Очищаємо
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
            
        except asyncio.TimeoutError:
            logger.error("Gemini timeout")
            return self._mock_analysis(photo_bytes, filename, error="timeout")
        except Exception as e:
            logger.error(f"Gemini API error: {e}")
            return self._mock_analysis(photo_bytes, filename, error=str(e))
    
    def _mock_analysis(self, photo_bytes: bytes, filename: str, error: str = None) -> Dict[str, Any]:
        """Тестовий аналіз для режиму без Gemini"""
        
        # Спроба визначити страву за назвою файлу
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
            # Випадкова тестова страва
            import random
            meals = [
                {"name": "Вівсянка з ягодами", "calories": 320, "protein": 12, "fat": 8, "carbs": 48, "feedback": "🥣 Чудовий сніданок!"},
                {"name": "Гречка з куркою", "calories": 450, "protein": 35, "fat": 12, "carbs": 45, "feedback": "🍗 Відмінний обід! Добре збалансовано."},
                {"name": "Рис з овочами", "calories": 380, "protein": 10, "fat": 8, "carbs": 65, "feedback": "🍚 Ситно та корисно."}
            ]
            meal = random.choice(meals)
            if error:
                meal["feedback"] = f"⚠️ Тестовий режим (Gemini: {error[:50]}). {meal['feedback']}"
            else:
                meal["feedback"] = f"🧪 ТЕСТОВИЙ РЕЖИМ: {meal['feedback']}"
            return meal
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Аналіз тижневого харчування"""
        
        if not self.available or not self.model:
            return self._mock_weekly_analysis(meals, averages, user_profile)
        
        try:
            prompt = f"""Analyze weekly nutrition (in Ukrainian):
Average per day: {averages.get('calories', 0):.0f} kcal
Give short analysis with recommendations (3-5 sentences)."""
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=30.0
            )
            return response.text
        except Exception as e:
            logger.error(f"Weekly analysis error: {e}")
            return self._mock_weekly_analysis(meals, averages, user_profile)
    
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
        
        if total_meals < 14:
            recommendations.append("🔸 Додавайте більше прийомів їжі для точного аналізу")
        
        return f"""📊 *Тижневий звіт (ТЕСТОВИЙ РЕЖИМ)*

За тиждень додано *{total_meals}* прийомів їжі.
Середня калорійність: *{avg_calories:.0f}* ккал/день

*Рекомендації:*
{chr(10).join(recommendations)}

💡 *Порада:* Додавайте більше прийомів їжі для точнішого AI-аналізу!"""
