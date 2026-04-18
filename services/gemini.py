# services/gemini.py
import os
import base64
import json
import re
import httpx
from PIL import Image
import io
import logging
from typing import Dict, Any

logger = logging.getLogger(__name__)

class GeminiService:
    def __init__(self):
        self.api_key = os.getenv("GEMINI_API_KEY")
        self.model = "gemini-2.0-flash"
        self.url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        self.available = bool(self.api_key)
        
    def _compress_image(self, image: Image.Image, max_size: int = 800, quality: int = 75) -> str:
        """Стиснення зображення для економії токенів"""
        original_size = image.size
        if image.mode != 'RGB':
            image = image.convert('RGB')
        
        if image.size[0] > max_size or image.size[1] > max_size:
            ratio = max_size / max(image.size)
            new_size = (int(image.size[0] * ratio), int(image.size[1] * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)
            logger.info(f"📐 Resized: {original_size} → {new_size}")
        
        buffer = io.BytesIO()
        image.save(buffer, format='JPEG', quality=quality, optimize=True)
        return base64.b64encode(buffer.getvalue()).decode('utf-8')
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Аналіз фото їжі через Gemini 2.0 Flash"""
        
        if not self.available:
            return self._mock_analysis(filename)
        
        try:
            image = Image.open(io.BytesIO(photo_bytes))
            base64_image = self._compress_image(image)
            
            prompt = """Analyze this food image. Return ONLY valid JSON:
{
    "name": "dish name in Ukrainian",
    "calories": number,
    "protein": number,
    "fat": number,
    "carbs": number,
    "feedback": "short recommendation in Ukrainian"
}"""
            
            payload = {
                "contents": [{
                    "parts": [
                        {"text": prompt},
                        {"inline_data": {"mime_type": "image/jpeg", "data": base64_image}}
                    ]
                }],
                "generationConfig": {"temperature": 0.2, "maxOutputTokens": 300}
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(self.url, json=payload, timeout=30.0)
                
                if response.status_code != 200:
                    logger.error(f"Gemini error {response.status_code}")
                    return self._mock_analysis(filename)
                
                data = response.json()
                text = data["candidates"][0]["content"]["parts"][0]["text"]
                
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
                
        except Exception as e:
            logger.error(f"Gemini error: {e}")
            return self._mock_analysis(filename)
    
    def _mock_analysis(self, filename: str) -> Dict[str, Any]:
        """Тестовий аналіз"""
        name_lower = filename.lower()
        if 'apple' in name_lower:
            return {"name": "Яблуко", "calories": 95, "protein": 0.5, "fat": 0.3, "carbs": 25, "feedback": "🍎 Багате на клітковину"}
        elif 'banana' in name_lower:
            return {"name": "Банан", "calories": 105, "protein": 1.3, "fat": 0.4, "carbs": 27, "feedback": "🍌 Джерело калію"}
        else:
            return {"name": "Страва", "calories": 300, "protein": 15, "fat": 10, "carbs": 35, "feedback": "🧪 Тестовий режим"}
