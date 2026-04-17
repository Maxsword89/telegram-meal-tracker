# ============================================
# Файл: services/gemini.py
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
        api_key = os.getenv("GEMINI_API_KEY")
        
        logger.info(f"🔑 GEMINI_API_KEY present: {bool(api_key)}")
        
        if not api_key:
            logger.error("❌ GEMINI_API_KEY not set!")
            raise ValueError("GEMINI_API_KEY not set")
        
        try:
            genai.configure(api_key=api_key)
            logger.info("✅ Gemini configured successfully")
            
            # Try different models
            models_to_try = [
                'gemini-2.0-flash',
                'gemini-1.5-flash',
                'gemini-pro'
            ]
            
            self.model = None
            for model_name in models_to_try:
                try:
                    logger.info(f"🔄 Trying model: {model_name}")
                    test_model = genai.GenerativeModel(model_name)
                    test_response = test_model.generate_content("Test")
                    if test_response and test_response.text:
                        self.model = test_model
                        logger.info(f"✅ Gemini model initialized: {model_name}")
                        break
                except Exception as e:
                    logger.warning(f"⚠️ Model {model_name} failed: {e}")
                    continue
            
            if not self.model:
                raise Exception("No available Gemini model found")
            
            # Test the model
            test_response = self.model.generate_content("Say 'API works'")
            logger.info(f"✅ Gemini test successful: {test_response.text[:50]}")
                
        except Exception as e:
            logger.error(f"❌ Gemini initialization error: {e}")
            raise ValueError(f"Gemini initialization failed: {e}")
    
    async def analyze_meal(self, photo_bytes: bytes, filename: str) -> Dict[str, Any]:
        """Analyze food photo with Gemini AI"""
        try:
            logger.info(f"📸 Starting analysis for: {filename}")
            logger.info(f"📏 Photo size: {len(photo_bytes)} bytes")
            
            # Open and process image
            image = Image.open(io.BytesIO(photo_bytes))
            logger.info(f"🖼️ Image mode: {image.mode}, size: {image.size}")
            
            if image.mode != 'RGB':
                image = image.convert('RGB')
                logger.info("🔄 Converted to RGB")
            
            # Compress for speed
            max_size = 1024
            if image.size[0] > max_size or image.size[1] > max_size:
                image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
                logger.info(f"📐 Resized to {image.size}")
            
            # Save to bytes
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='JPEG', quality=85)
            img_byte_arr = img_byte_arr.getvalue()
            logger.info(f"📦 Compressed size: {len(img_byte_arr)} bytes")
            
            # Prompt for Gemini
            prompt = """You are a professional nutritionist. Analyze this food image carefully.

Return ONLY valid JSON (no markdown, no extra text):

{
    "name": "exact dish name in English",
    "calories": estimated calories (number),
    "protein": protein in grams (number),
    "fat": fat in grams (number),
    "carbs": carbohydrates in grams (number),
    "feedback": "short health recommendation (1 sentence)"
}

Be specific and accurate."""
            
            logger.info("🚀 Sending request to Gemini API...")
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content([prompt, img_byte_arr])),
                timeout=30.0
            )
            
            text = response.text.strip()
            logger.info(f"📝 Gemini response received: {text[:200]}")
            
            # Clean response
            text = re.sub(r'^```json\s*', '', text)
            text = re.sub(r'^```\s*', '', text)
            text = re.sub(r'\s*```$', '', text)
            
            # Find JSON
            json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
            if json_match:
                text = json_match.group()
            
            analysis = json.loads(text)
            
            result = {
                "name": analysis.get("name", "Unknown"),
                "calories": max(0, int(analysis.get("calories", 0))),
                "protein": max(0, float(analysis.get("protein", 0))),
                "fat": max(0, float(analysis.get("fat", 0))),
                "carbs": max(0, float(analysis.get("carbs", 0))),
                "feedback": analysis.get("feedback", "✅ Enjoy your meal!")
            }
            
            logger.info(f"✅ Analyzed: {result['name']} - {result['calories']} kcal")
            return result
            
        except asyncio.TimeoutError:
            logger.error("❌ Gemini timeout after 30 seconds")
            return {
                "name": "Analysis Timeout",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "⏰ Timeout. Please try again."
            }
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON parse error: {e}")
            return {
                "name": "Parse Error",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": "❌ Could not parse AI response. Try again."
            }
        except Exception as e:
            logger.error(f"❌ Gemini API error: {e}", exc_info=True)
            return {
                "name": "Error",
                "calories": 0,
                "protein": 0,
                "fat": 0,
                "carbs": 0,
                "feedback": f"❌ Error: {str(e)[:100]}"
            }
    
    async def analyze_weekly(self, meals: List[Dict], averages: Dict, user_profile: Dict) -> str:
        """Analyze weekly nutrition"""
        try:
            logger.info("📊 Starting weekly analysis")
            
            prompt = f"""Analyze this week's nutrition:

Daily averages:
- Calories: {averages.get('calories', 0):.0f} kcal
- Protein: {averages.get('protein', 0):.1f}g
- Fat: {averages.get('fat', 0):.1f}g
- Carbs: {averages.get('carbs', 0):.1f}g

Total meals: {len(meals)}"""

            if user_profile:
                prompt += f"""

User data:
- Age: {user_profile.get('age')}
- Gender: {user_profile.get('gender')}
- Weight: {user_profile.get('weight')} kg
- Height: {user_profile.get('height')} cm
- Goal: {user_profile.get('goal')}
- Daily calorie target: {user_profile.get('daily_calorie_goal')} kcal"""

            prompt += """

Give a detailed analysis (5-7 sentences):
1. Overall nutrition assessment
2. Macro balance analysis
3. What can be improved
4. 2-3 specific recommendations for next week

Be friendly and motivating."""
            
            loop = asyncio.get_event_loop()
            response = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: self.model.generate_content(prompt)),
                timeout=40.0
            )
            
            logger.info("✅ Weekly analysis generated")
            return response.text
            
        except Exception as e:
            logger.error(f"❌ Weekly analysis error: {e}")
            return "📊 Could not generate analysis. Please try again later."
