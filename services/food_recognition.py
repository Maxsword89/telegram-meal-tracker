# services/food_recognition.py
import os
import base64
import httpx
from typing import Dict, Any, Optional
from PIL import Image
import io
import logging
import asyncio

logger = logging.getLogger(__name__)


class BaiduFoodRecognition:
    """Розпізнавання страв через Baidu API (безкоштовно, 50,000 запитів/день)"""
    
    def __init__(self):
        self.api_key = os.getenv("BAIDU_API_KEY")
        self.secret_key = os.getenv("BAIDU_SECRET_KEY")
        self.access_token = None
        self.token_expiry = 0
        
        if not self.api_key or not self.secret_key:
            logger.warning("Baidu API keys not set. Recognition will use mock mode.")
    
    async def get_access_token(self) -> Optional[str]:
        """Отримання access token для Baidu API (діє 30 днів)"""
        import time
        
        # Перевіряємо чи токен ще дійсний
        if self.access_token and time.time() < self.token_expiry:
            return self.access_token
        
        if not self.api_key or not self.secret_key:
            return None
            
        url = "https://aip.baidubce.com/oauth/2.0/token"
        params = {
            "grant_type": "client_credentials",
            "client_id": self.api_key,
            "client_secret": self.secret_key
        }
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, params=params, timeout=10.0)
                data = response.json()
                
                if "access_token" in data:
                    self.access_token = data["access_token"]
                    self.token_expiry = time.time() + (data.get("expires_in", 2592000) - 300)
                    logger.info("✅ Baidu access token obtained")
                    return self.access_token
                else:
                    logger.error(f"Baidu token error: {data}")
                    return None
        except Exception as e:
            logger.error(f"Baidu token request error: {e}")
            return None
    
    async def recognize_dish(self, photo_bytes: bytes) -> Optional[Dict]:
        """
        Розпізнавання страви за фото
        Повертає: {"name": str, "calories": int, "confidence": float}
        """
        token = await self.get_access_token()
        if not token:
            return None
        
        try:
            # Стискаємо фото (Baidu вимагає до 4MB)
            image = Image.open(io.BytesIO(photo_bytes))
            if image.mode != 'RGB':
                image = image.convert('RGB')
            
            # Зменшуємо до розумного розміру
            image.thumbnail((800, 800))
            buffer = io.BytesIO()
            image.save(buffer, format='JPEG', quality=85)
            img_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')
            
            # Запит до Baidu
            url = f"https://aip.baidubce.com/rest/2.0/image-classify/v2/dish?access_token={token}"
            
            async with httpx.AsyncClient() as client:
                response = await client.post(url, data={"image": img_base64, "top_num": 3}, timeout=15.0)
                data = response.json()
                
                if "result" in data and data["result"]:
                    # Беремо найкращий результат
                    result = data["result"][0]
                    return {
                        "name": result.get("name"),
                        "calories": result.get("calories", 0),
                        "confidence": result.get("probability", 0)
                    }
                else:
                    logger.error(f"Baidu recognition failed: {data.get('error_msg', 'Unknown error')}")
                    return None
                    
        except Exception as e:
            logger.error(f"Baidu recognition error: {e}")
            return None


class USDAService:
    """Отримання детальних даних про харчування з USDA FoodData Central"""
    
    def __init__(self):
        self.api_key = os.getenv("USDA_API_KEY", "DEMO_KEY")
        self.base_url = "https://api.nal.usda.gov/fdc/v1"
        
    async def search_food(self, query: str) -> Optional[Dict]:
        """
        Пошук продукту в базі USDA
        Повертає: {"name": str, "calories": float, "protein": float, "fat": float, "carbs": float}
        """
        if not query:
            return None
            
        try:
            url = f"{self.base_url}/foods/search"
            params = {
                "api_key": self.api_key,
                "query": query,
                "pageSize": 1,
                "dataType": ["Foundation", "SR Legacy", "Branded"]
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(url, params=params, timeout=10.0)
                data = response.json()
                
                if data.get("foods"):
                    food = data["foods"][0]
                    nutrients = {}
                    for n in food.get("foodNutrients", []):
                        name = n.get("nutrientName", "")
                        value = n.get("value", 0)
                        if "Energy" in name:
                            nutrients["calories"] = value
                        elif "Protein" in name:
                            nutrients["protein"] = value
                        elif "Total lipid" in name:
                            nutrients["fat"] = value
                        elif "Carbohydrate" in name:
                            nutrients["carbs"] = value
                    
                    return {
                        "name": food.get("description", query),
                        "calories": nutrients.get("calories", 0),
                        "protein": round(nutrients.get("protein", 0), 1),
                        "fat": round(nutrients.get("fat", 0), 1),
                        "carbs": round(nutrients.get("carbs", 0), 1),
                    }
                return None
                
        except Exception as e:
            logger.error(f"USDA search error: {e}")
            return None


class FoodRecognitionService:
    """Головний сервіс, що об'єднує Baidu та USDA"""
    
    def __init__(self):
        self.baidu = BaiduFoodRecognition()
        self.usda = USDAService()
        self.use_mock = not (os.getenv("BAIDU_API_KEY") and os.getenv("USDA_API_KEY"))
        
        if self.use_mock:
            logger.warning("⚠️ Food recognition in MOCK mode. Set BAIDU_API_KEY and USDA_API_KEY for real recognition.")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """
        Повний аналіз страви:
        1. Baidu розпізнає страву за фото
        2. USDA надає детальні дані про харчування
        """
        # Тестовий режим
        if self.use_mock:
            return self._mock_analysis(photo_bytes, filename)
        
        try:
            # Крок 1: Розпізнаємо страву через Baidu
            dish_info = await self.baidu.recognize_dish(photo_bytes)
            
            if not dish_info:
                return {
                    "name": "Невідомо",
                    "calories": 0,
                    "protein": 0,
                    "fat": 0,
                    "carbs": 0,
                    "feedback": "❌ Не вдалося розпізнати страву. Спробуйте інше фото."
                }
            
            dish_name = dish_info["name"]
            baidu_calories = dish_info["calories"]
            confidence = dish_info["confidence"]
            
            # Крок 2: Шукаємо детальні дані в USDA
            nutrition = await self.usda.search_food(dish_name)
            
            if nutrition and nutrition["calories"] > 0:
                # Використовуємо точні дані з USDA
                return {
                    "name": nutrition["name"],
                    "calories": int(nutrition["calories"]),
                    "protein": nutrition["protein"],
                    "fat": nutrition["fat"],
                    "carbs": nutrition["carbs"],
                    "feedback": f"✅ Розпізнано: {dish_name} (впевненість: {confidence:.0%}). Дані з бази USDA."
                }
            else:
                # Використовуємо калорії від Baidu
                return {
                    "name": dish_name,
                    "calories": baidu_calories,
                    "protein": 0,
                    "fat": 0,
                    "carbs": 0,
                    "feedback": f"✅ Розпізнано: {dish_name}. (Точні дані відсутні в базі)"
                }
                
        except Exception as e:
            logger.error(f"Food recognition error: {e}")
            return self._mock_analysis(photo_bytes, filename, error=str(e)[:50])
    
    def _mock_analysis(self, photo_bytes: bytes, filename: str, error: str = None) -> Dict:
        """Тестовий аналіз для режиму без API ключів"""
        
        filename_lower = filename.lower()
        
        if 'apple' in filename_lower or 'яблуко' in filename_lower:
            return {"name": "Яблуко", "calories": 95, "protein": 0.5, "fat": 0.3, "carbs": 25, "feedback": "🍎 Багате на клітковину"}
        elif 'banana' in filename_lower or 'банан' in filename_lower:
            return {"name": "Банан", "calories": 105, "protein": 1.3, "fat": 0.4, "carbs": 27, "feedback": "🍌 Джерело калію"}
        elif 'croissant' in filename_lower or 'круасан' in filename_lower:
            return {"name": "Круасан", "calories": 350, "protein": 8, "fat": 18, "carbs": 40, "feedback": "🥐 Краще обмежитись одним"}
        elif 'pizza' in filename_lower or 'піца' in filename_lower:
            return {"name": "Піца", "calories": 285, "protein": 12, "fat": 10, "carbs": 35, "feedback": "🍕 Смачна, але калорійна"}
        else:
            return {
                "name": "Тестова страва",
                "calories": 300,
                "protein": 15,
                "fat": 10,
                "carbs": 35,
                "feedback": "🧪 ТЕСТОВИЙ РЕЖИМ: Додайте API ключі Baidu та USDA для реального аналізу."
            }
