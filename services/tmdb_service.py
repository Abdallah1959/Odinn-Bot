import aiohttp
import asyncio
import logging
from typing import Optional, List
from config.settings import settings
from models.movie import Movie
from models.tv_show import TVShow 

logger = logging.getLogger(__name__)

class TMDBService:
    def __init__(self):
        self.base_url = "https://api.themoviedb.org/3"
        self.api_key = settings.TMDB_API_KEY
        self.session: Optional[aiohttp.ClientSession] = None

    async def initialize(self):
        """Initialize the aiohttp session once on startup"""
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(timeout=timeout)
        logger.info("TMDB Service session initialized.")

    async def _fetch_json(self, url: str, params: dict) -> Optional[dict]:
        """Internal DRY helper for HTTP requests and error handling"""
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
        url = f"{self.base_url}/search/movie"
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": "en-US",
            "page": 1
        }
        data = await self._fetch_json(url, params)
        return data.get("results", []) if data else []

    async def search_tv(self, query: str) -> List[dict]:
        url = f"{self.base_url}/search/tv"
        params = {
            "api_key": self.api_key,
            "query": query,
            "language": "en-US",
            "page": 1
        }
        data = await self._fetch_json(url, params)
        return data.get("results", []) if data else []

    async def fetch_popular_movies(self) -> List[dict]:
        url = f"{self.base_url}/movie/popular"
        params = {
            "api_key": self.api_key,
            "language": "en-US",
            "page": 1
        }
        data = await self._fetch_json(url, params)
        return data.get("results", []) if data else []

    async def get_movie_details(self, movie_id: int) -> Optional[Movie]:
        url = f"{self.base_url}/movie/{movie_id}"
        params = {
            "api_key": self.api_key,
            "language": "en-US",
            "append_to_response": "external_ids,videos"
        }
        
        details = await self._fetch_json(url, params)
        if not details:
            return None
            
        overview = details.get("overview")
                
        trailer_url = None
        for video in details.get("videos", {}).get("results", []):
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                break
                
        poster_path = details.get("poster_path")
        # عبقرية استخراج الـ IDs من هنا بتحمينا من أي مشاكل في الـ UI
        genre_ids = [genre.get("id") for genre in details.get("genres", [])] if "genres" in details else []
        
        return Movie(
            tmdb_id=details.get("id", 0),
            title=details.get("title", "Unknown"),
            original_title=details.get("original_title", "Untitled"),
            overview=overview or "No overview available.",
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
        url = f"{self.base_url}/tv/{tv_id}"
        params = {
            "api_key": self.api_key,
            "language": "en-US",
            "append_to_response": "external_ids,videos"
        }
        
        details = await self._fetch_json(url, params)
        if not details:
            return None
            
        overview = details.get("overview")
                
        trailer_url = None
        for video in details.get("videos", {}).get("results", []):
            if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                break
                
        poster_path = details.get("poster_path")
        genre_ids = [genre.get("id") for genre in details.get("genres", [])] if "genres" in details else []
        
        return TVShow(
            tmdb_id=details.get("id", 0),
            name=details.get("name", "Unknown"),
            original_name=details.get("original_name", "Untitled"),
            overview=overview or "No overview available.",
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
        if self.session:
            await self.session.close()
            self.session = None
            logger.info("TMDB session closed safely.")
