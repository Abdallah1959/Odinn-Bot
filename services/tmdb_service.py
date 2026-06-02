# services/tmdb_service.py
import aiohttp
import asyncio
import logging
from typing import Optional, List
from config.settings import settings
from models.movie import Movie

logger = logging.getLogger(__name__)

class TMDBService:
    def __init__(self):
        self.base_url = "https://api.themoviedb.org/3"
        self.api_key = settings.TMDB_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """فتح السيشن مرة واحدة فقط عند بدء التشغيل"""
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info("TMDB Service session initialized.")

    async def search_movies(self, query: str) -> List[dict]:
        """البحث عن الأفلام باستخدام الكلمة المفتاحية وإرجاع النتائج الخام لترتيبها بشكل آمن"""
        if not self.session:
            return []
            
        url = f"{self.base_url}/search/movie"
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": "ar-SA",
            "page": 1
        }
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("results", [])
                
                logger.warning(f"TMDB returned status: {response.status} for search query: {query}")
                return []
        except asyncio.TimeoutError:
            logger.error(f"🚨 Timeout error while searching for '{query}'")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"🚨 Network error while searching for '{query}': {e}")
            return []

    async def fetch_popular_movies(self) -> List[dict]:
        """جلب الأفلام المشهورة كـ dicts خام ليتغذى عليها محرك الـ Daily Picks لاحقاً"""
        if not self.session:
            return []
            
        url = f"{self.base_url}/movie/popular"
        params = {
            "api_key": self.api_key,
            "language": "ar-SA",
            "page": 1
        }
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get("results", [])
                
                logger.warning(f"TMDB returned status: {response.status} for popular movies")
                return []
        except asyncio.TimeoutError:
            logger.error("🚨 Timeout error while fetching popular movies.")
            return []
        except aiohttp.ClientError as e:
            logger.error(f"🚨 Client error while fetching popular movies: {e}")
            return []

    async def get_movie_details(self, movie_id: int) -> Optional[Movie]:
        """جلب التفاصيل العميقة وحقنها داخل كائن الـ Movie Model بشكل صارم ومتوافق"""
        if not self.session:
            return None
            
        url = f"{self.base_url}/movie/{movie_id}"
        params = {
            "api_key": self.api_key,
            "language": "ar-SA",
            "append_to_response": "external_ids,videos"
        }
        try:
            async with self.session.get(url, params=params) as response:
                if response.status != 200:
                    return None
                
                details = await response.json()
                overview = details.get("overview")
                
                # Fallback للقصة باللغة الإنجليزية في قاموس منفصل تماماً ومستقل لحفظ الحالة
                if not overview:
                    en_params = {
                        "api_key": self.api_key,
                        "language": "en-US"
                    }
                    try:
                        async with self.session.get(url, params=en_params) as en_response:
                            if en_response.status == 200:
                                en_details = await en_response.json()
                                overview = en_details.get("overview")
                    except (asyncio.TimeoutError, aiohttp.ClientError) as en_e:
                        logger.warning(f"⚠️ Failed to fetch English fallback for movie {movie_id}: {en_e}")
                
                # استخراج رابط التريلر من اليوتيوب إن وجد
                trailer_url = None
                for video in details.get("videos", {}).get("results", []):
                    if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                        trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                        break
                
                poster_path = details.get("poster_path")
                genre_ids = [genre.get("id") for genre in details.get("genres", [])] if "genres" in details else []
                
                # [تأمين وحقن الكونتراكت]: البناء المطابق تماماً لهيكلية كلاس Movie المعتمد مع الـ Type Safety
                return Movie(
                    tmdb_id=details.get("id", 0),  # [تعديل 2]: حماية النوع لقيمة المعرف الأساسي
                    title=details.get("title", "غير محدد"),  # [تعديل 1]: إصلاح الخطأ الإملائي
                    original_title=details.get("original_title", "Untitled"),
                    overview=overview or "لا توجد قصة متاحة.",
                    rating=details.get("vote_average", 0.0),
                    vote_count=details.get("vote_count", 0),
                    release_date=details.get("release_date"),
                    runtime=details.get("runtime"),
                    poster_url=f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else None,
                    backdrop_path=details.get("backdrop_path"),
                    imdb_id=details.get("external_ids", {}).get("imdb_id"),
                    trailer_url=trailer_url,
                    genre_ids=genre_ids
                )
        except asyncio.TimeoutError:
            logger.error(f"🚨 Timeout error while fetching movie {movie_id}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"🚨 Network error while fetching movie {movie_id}: {e}")
            return None

    async def close(self):
        """إغلاق السيشن بأمان وتصفير المتغير للتنظيف الكامل للموارد"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("TMDB session closed safely.")
