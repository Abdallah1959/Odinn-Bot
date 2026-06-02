# models/movie.py
from dataclasses import dataclass, field
from typing import Optional

@dataclass(slots=True)
class Movie:
    # المعرفات الأساسية
    tmdb_id: int
    
    # العناوين
    title: str
    original_title: str
    
    # القصة
    overview: str
    
    # التقييمات والإحصائيات
    rating: float
    vote_count: int
    
    # التواريخ والمدة
    release_date: Optional[str]
    runtime: Optional[int]
    
    # الصور
    poster_url: Optional[str]
    backdrop_path: Optional[str]
    
    # الروابط الخارجية والمعرفات
    imdb_id: Optional[str]
    trailer_url: Optional[str]
    
    # التصنيفات (تمت حمايتها بقيمة افتراضية آمنة للمصفوفات الديناميكية)
    genre_ids: list[int] = field(default_factory=list)
