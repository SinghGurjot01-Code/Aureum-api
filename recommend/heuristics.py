# recommend/heuristics.py
# Simple heuristics for recommendations

def get_time_based_suggestion(hour: int) -> str:
    """Get suggestion based on time of day"""
    if 5 <= hour < 12:
        return "morning"
    elif 12 <= hour < 17:
        return "afternoon"
    elif 17 <= hour < 22:
        return "evening"
    else:
        return "night"

def get_mood_from_activity(activities: List[str]) -> str:
    """Guess mood from activity types"""
    if not activities:
        return "neutral"
    
    play_count = activities.count("play")
    skip_count = activities.count("skip")
    
    if skip_count > play_count:
        return "restless"
    elif play_count > skip_count * 2:
        return "engaged"
    else:
        return "neutral"