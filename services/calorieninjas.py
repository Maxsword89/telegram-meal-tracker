# services/calorieninjas.py
import os
import httpx
from typing import Dict, Any

class CalorieNinjasService:
    def __init__(self):
        self.api_key = os.getenv("CALORIENINJAS_API_KEY")
        self.base_url = "https://api.calorieninjas.com/v1/nutrition"
    
    async def search_food(self, query: str) -> Dict[str, Any]:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                self.base_url,
                params={"query": query},
                headers={"X-Api-Key": self.api_key}
            )
            data = response.json()
            if data.get("items"):
                item = data["items"][0]
                return {
                    "name": item.get("name", query),
                    "calories": item.get("calories", 0),
                    "protein": item.get("protein_g", 0),
                    "fat": item.get("fat_total_g", 0),
                    "carbs": item.get("carbohydrates_total_g", 0)
                }
            return None
