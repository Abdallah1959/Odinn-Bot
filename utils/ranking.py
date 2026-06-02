from typing import Mapping, Any

# ==========================================
# الثوابت المعتمدة لمحركات الترتيب (Weights)
# ==========================================

# 1. محرك ترتيب نتائج البحث (Search Ranking)
SEARCH_RATING_WEIGHT = 0.5
SEARCH_VOTES_WEIGHT = 0.3
SEARCH_POPULARITY_WEIGHT = 0.2

# 2. محرك ترشيحات اليوم (Daily Picks Ranking)
DAILY_RATING_WEIGHT = 0.4
DAILY_VOTES_WEIGHT = 0.2
DAILY_POPULARITY_WEIGHT = 0.4


def _extract_metrics(media_item: Mapping[str, Any]) -> tuple[float, float, float]:
    """
    دالة مساعدة لاستخراج وتطبيع (Normalize) مقاييس الفيلم لمنع تكرار الكود.
    المخرجات: (rating, normalized_votes, normalized_popularity)
    """
    rating = float(media_item.get("vote_average", 0.0))
    votes = int(media_item.get("vote_count", 0))
    popularity = float(media_item.get("popularity", 0.0))
    
    # تطبيع البيانات لجعلها في نطاق متناسق (Max Score = 10)
    normalized_votes = min(votes / 5000.0, 10.0)
    normalized_popularity = min(popularity / 200.0, 10.0)
    
    return rating, normalized_votes, normalized_popularity


def calculate_search_score(media_item: Mapping[str, Any]) -> float:
    """
    محرك ترتيب نتائج البحث: الأولوية لجودة الفيلم وثقة الناس فيه.
    - التقييم (Rating): 50%
    - عدد الأصوات (Votes): 30%
    - الشعبية والترند (Popularity): 20%
    """
    rating, normalized_votes, normalized_popularity = _extract_metrics(media_item)
    
    score = (
        (rating * SEARCH_RATING_WEIGHT) + 
        (normalized_votes * SEARCH_VOTES_WEIGHT) + 
        (normalized_popularity * SEARCH_POPULARITY_WEIGHT)
    )
    return round(score, 2)


def calculate_daily_pick_score(media_item: Mapping[str, Any]) -> float:
    """
    محرك ترتيب ترشيحات اليوم (Daily Picks): توازن بين جودة الفيلم والترند الحالي.
    - التقييم (Rating): 40%
    - عدد الأصوات (Votes): 20%
    - الشعبية والترند (Popularity): 40%
    """
    rating, normalized_votes, normalized_popularity = _extract_metrics(media_item)
    
    score = (
        (rating * DAILY_RATING_WEIGHT) + 
        (normalized_votes * DAILY_VOTES_WEIGHT) + 
        (normalized_popularity * DAILY_POPULARITY_WEIGHT)
    )
    return round(score, 2)
