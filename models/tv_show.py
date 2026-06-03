from dataclasses import dataclass, field
from typing import Optional

@dataclass(slots=True)
class TVShow:
    # المعرفات الأساسية
    tmdb_id: int
    
    # العناوين (في مسار الـ TV بنستخدم name بدل title)
    name: str
    original_name: str
    
    # القصة
    overview: str
    
    # التقييمات والإحصائيات
    rating: float
    vote_count: int
    
    # التواريخ
    first_air_date: Optional[str]
    
    # المواسم والحلقات (الإضافات الخاصة بالمسلسلات)
    number_of_seasons: Optional[int]
    number_of_episodes: Optional[int]
    
    # الصور
    poster_url: Optional[str]
    backdrop_path: Optional[str]
    
    # الروابط الخارجية والمعرفات
    imdb_id: Optional[str]
    trailer_url: Optional[str]
    
    # التصنيفات (محمية بقيمة افتراضية آمنة)
    genre_ids: list[int] = field(default_factory=list)
