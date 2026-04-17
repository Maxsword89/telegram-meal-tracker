# ============================================
# Файл: services/nutrition.py
# ============================================
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)

class NutritionCalculator:
    """Calculate nutrition needs and summaries"""
    
    def calculate_tdee(self, profile: Dict) -> float:
        """Calculate Total Daily Energy Expenditure (TDEE)"""
        age = profile.get("age", 25)
        gender = profile.get("gender", "male")
        height = profile.get("height", 170)
        weight = profile.get("weight", 70)
        activity_level = profile.get("activity_level", "moderate")
        goal = profile.get("goal", "maintain")
        
        # Calculate BMR (Basal Metabolic Rate)
        if gender == "male":
            bmr = 10 * weight + 6.25 * height - 5 * age + 5
        else:
            bmr = 10 * weight + 6.25 * height - 5 * age - 161
        
        # Activity multipliers
        multipliers = {
            "sedentary": 1.2,
            "light": 1.375,
            "moderate": 1.55,
            "active": 1.725,
            "very_active": 1.9
        }
        
        tdee = bmr * multipliers.get(activity_level, 1.55)
        
        # Goal adjustments
        goal_multipliers = {
            "lose": 0.85,
            "maintain": 1.0,
            "gain": 1.15
        }
        
        daily_calories = tdee * goal_multipliers.get(goal, 1.0)
        
        logger.info(f"Calculated TDEE: {daily_calories:.0f} kcal for profile: age={age}, gender={gender}, weight={weight}kg, height={height}cm, activity={activity_level}, goal={goal}")
        
        return round(daily_calories, 0)
    
    def calculate_macros(self, calories: float, weight: float, goal: str) -> Dict[str, float]:
        """Calculate recommended macros (protein, fat, carbs)"""
        # Protein: 1.6-2.2 g per kg of body weight
        if goal == "gain":
            protein_per_kg = 2.0
        elif goal == "lose":
            protein_per_kg = 2.2
        else:
            protein_per_kg = 1.8
        
        protein_grams = weight * protein_per_kg
        protein_calories = protein_grams * 4
        
        # Fat: 25-30% of total calories
        fat_percent = 0.28
        fat_calories = calories * fat_percent
        fat_grams = fat_calories / 9
        
        # Carbs: remaining calories
        carbs_calories = calories - protein_calories - fat_calories
        carbs_grams = carbs_calories / 4
        
        result = {
            "protein": round(protein_grams, 1),
            "fat": round(fat_grams, 1),
            "carbs": round(carbs_grams, 1)
        }
        
        logger.info(f"Calculated macros for {calories} kcal, weight={weight}kg, goal={goal}: protein={result['protein']}g, fat={result['fat']}g, carbs={result['carbs']}g")
        
        return result
    
    def get_daily_summary(self, meals: List[Dict], user_profile: Dict) -> Dict:
        """Calculate daily nutrition summary"""
        total_calories = sum(m.get("calories", 0) for m in meals)
        total_protein = sum(m.get("protein", 0) for m in meals)
        total_fat = sum(m.get("fat", 0) for m in meals)
        total_carbs = sum(m.get("carbs", 0) for m in meals)
        
        goal_calories = user_profile.get("daily_calorie_goal", 2000) if user_profile else 2000
        goal_protein = user_profile.get("protein_goal", 100) if user_profile else 100
        goal_fat = user_profile.get("fat_goal", 50) if user_profile else 50
        goal_carbs = user_profile.get("carbs_goal", 200) if user_profile else 200
        
        remaining_calories = max(0, goal_calories - total_calories)
        progress_calories = (total_calories / goal_calories) * 100 if goal_calories > 0 else 0
        
        remaining_protein = max(0, goal_protein - total_protein)
        progress_protein = (total_protein / goal_protein) * 100 if goal_protein > 0 else 0
        
        remaining_fat = max(0, goal_fat - total_fat)
        progress_fat = (total_fat / goal_fat) * 100 if goal_fat > 0 else 0
        
        remaining_carbs = max(0, goal_carbs - total_carbs)
        progress_carbs = (total_carbs / goal_carbs) * 100 if goal_carbs > 0 else 0
        
        return {
            "total": {
                "calories": total_calories,
                "protein": total_protein,
                "fat": total_fat,
                "carbs": total_carbs
            },
            "goal": {
                "calories": goal_calories,
                "protein": goal_protein,
                "fat": goal_fat,
                "carbs": goal_carbs
            },
            "remaining": {
                "calories": remaining_calories,
                "protein": remaining_protein,
                "fat": remaining_fat,
                "carbs": remaining_carbs
            },
            "progress": {
                "calories": min(progress_calories, 100),
                "protein": min(progress_protein, 100),
                "fat": min(progress_fat, 100),
                "carbs": min(progress_carbs, 100)
            },
            "meals_count": len(meals)
        }
