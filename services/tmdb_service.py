import aiohttp
import asyncio
import logging
from typing import Optional, List
from config.settings import settings
from models.movie import Movie
from models.tv_show import TVShow  # الاستدعاء الجديد لموديل المسلسلات

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

    async def _fetch_json(self, url: str, params: dict) -> Optional[dict]:
        """Helper داخلي لتنفيذ الطلبات والتعامل مع الأخطاء لتقليل التكرار (DRY)"""
        if not self.session:
            return None
        try:
            async with self.session.get(url, params=params) as response:
                if response.status == 200:
                    return await response.json()
                logger.warning(f"TMDB returned status {response.status}: {response.reason} for URL: {url}")
                return None
        except asyncio.TimeoutError:
            logger.error(f"🚨 Timeout error for URL: {url}")
            return None
        except aiohttp.ClientError as e:
            logger.error(f"🚨 Network error for URL: {url}: {e}")
            return None

    async def search_movies(self, query: str) -> List[dict]:
        """البحث عن الأفلام باستخدام الكلمة المفتاحية وإرجاع النتائج الخام لترتيبها بشكل آمن"""
        url = f"{self.base_url}/search/movie"
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": "ar-SA",
            "page": 1
        }
        data = await self._fetch_json(url, params)
        return data.get("results", []) if data else []

    async def search_tv(self, query: str) -> List[dict]:
        """البحث عن المسلسلات التلفزيونية باستخدام الكلمة المفتاحية"""
        url = f"{self.base_url}/search/tv"
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": "ar-SA",
            "page": 1
        }
        data = await self._fetch_json(url, params)
        return data.get("results", []) if data else []

    async def fetch_popular_movies(self) -> List[dict]:
        """جلب الأفلام المشهورة كـ dicts خام ليتغذى عليها محرك الـ Daily Picks لاحقاً"""
        url = f"{self.base_url}/movie/popular"
        params = {
            "api_key": self.api_key,
            "language": "ar-SA",
            "page": 1
        }
        data = await self._fetch_json(url, params)
        return data.get("results", []) if data else []

    async def get_movie_details(self, movie_id: int) -> Optional[Movie]:
        """جلب التفاصيل العميقة وحقنها داخل كائن الـ Movie Model بشكل صارم ومتوافق"""
        url = f"{self.base_url}/movie/{movie_id}"
        params = {
            "api_key": self.api_key,
            "language": "ar-SA",
            "append_to_response": "external_ids,videos"
        }
        
        details = await self._fetch_json(url, params)
        if not details:
            return None
            
        overview = details.get("overview")
        
        # Fallback للقصة باللغة الإنجليزية في قاموس منفصل تماماً ومستقل لحفظ الحالة
        if not overview:
            en_params = {
                "api_key": self.api_key,
                "language": "en-US"
            }
            en_details = await self._fetch_json(url, en_params)
            if en_details:
                overview = en_details.get("overview")
                
        # استخراج رابط التريلر من اليوتيوب إن وجد
        trailer_url = None
        for video in details.get("videos", {}).get("results", []):
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                break
                
        poster_path = details.get("poster_path")
        genre_ids = [genre.get("id") for genre in details.get("genres", [])] if "genres" in details else []
        
        return Movie(
            tmdb_id=details.get("id", 0),
            title=details.get("title", "غير محدد"),
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

    async def get_tv_details(self, tv_id: int) -> Optional[TVShow]:
        """جلب التفاصيل العميقة للمسلسل وحقنها داخل كائن الـ TVShow Model"""
        url = f"{self.base_url}/tv/{tv_id}"
        params = {
            "api_key": self.api_key,
            "language": "ar-SA",
            "append_to_response": "external_ids,videos"
        }
        
        details = await self._fetch_json(url, params)
        if not details:
            return None
            
        overview = details.get("overview")
        
        # Fallback للقصة باللغة الإنجليزية
        if not overview:
            en_params = {
                "api_key": self.api_key,
                "language": "en-US"
            }
            en_details = await self._fetch_json(url, en_params)
            if en_details:
                overview = en_details.get("overview")
                
        trailer_url = None
        for video in details.get("videos", {}).get("results", []):
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                break
                
        poster_path = details.get("poster_path")
        genre_ids = [genre.get("id") for genre in details.get("genres", [])] if "genres" in details else []
        
        return TVShow(
            tmdb_id=details.get("id", 0),
            name=details.get("name", "غير محدد"),
            original_name=details.get("original_name", "Untitled"),
            overview=overview or "لا توجد قصة متاحة.",
            rating=details.get("vote_average", 0.0),
            vote_count=details.get("vote_count", 0),
            first_air_date=details.get("first_air_date"),
            number_of_seasons=details.get("number_of_seasons"),
            number_of_episodes=details.get("number_of_episodes"),
            poster_url=f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else None,
            backdrop_path=details.get("backdrop_path"),
            imdb_id=details.get("external_ids", {}).get("imdb_id"),
            trailer_url=trailer_url,
            genre_ids=genre_ids
        )

    async def close(self):
        """إغلاق السيشن بأمان وتصفير المتغير للتنظيف الكامل للموارد"""
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("TMDB session closed safely.")
