import os
import logging
from typing import List, Dict, Any, Optional
from supabase import create_client, Client
import asyncio

logger = logging.getLogger(__name__)

class DatabaseService:
    def __init__(self):
        url: str = os.environ.get("SUPABASE_URL")
        key: str = os.environ.get("SUPABASE_KEY")
        
        if not url or not key:
            logger.error("❌ Supabase URL or Key is missing in .env")
            self.supabase = None
        else:
            self.supabase: Client = create_client(url, key)
            logger.info("✅ Supabase initialized.")

    async def test_connection(self) -> bool:
        if not self.supabase:
            return False
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("watchlist").select("id").limit(1).execute()
            )
            return True
        except Exception:
            logger.exception("Database connection test failed")
            return False

    async def add_to_watchlist(self, user_id: int, tmdb_id: int, media_type: str, media_name: str, poster_url: str, release_year: str) -> bool:
        if not self.supabase:
            return False
        
        data = {
            "user_id": user_id,
            "tmdb_id": tmdb_id,
            "media_type": media_type,
            "media_name": media_name,
            "poster_url": poster_url,
            "release_year": release_year
        }
        
        try:
            # Idempotent write operation.
            # Repeated additions of the same item must not create duplicates.
            await asyncio.to_thread(
                lambda: self.supabase.table("watchlist")
                .upsert(data, on_conflict="user_id,tmdb_id,media_type")
                .execute()
            )
            return True
        except Exception:
            logger.exception("Error adding to watchlist for user %s", user_id)
            return False

    async def remove_from_watchlist(self, user_id: int, tmdb_id: int, media_type: str) -> bool:
        if not self.supabase:
            return False
        
        try:
            await asyncio.to_thread(
                lambda: self.supabase.table("watchlist").delete().match({
                    "user_id": user_id, 
                    "tmdb_id": tmdb_id, 
                    "media_type": media_type
                }).execute()
            )
            return True
        except Exception:
            logger.exception("Error removing from watchlist for user %s", user_id)
            return False

    async def get_watchlist(self, user_id: int) -> List[Dict[str, Any]]:
        if not self.supabase:
            return []
        
        try:
            response = await asyncio.to_thread(
                lambda: self.supabase.table("watchlist").select("*").eq("user_id", user_id).order("added_at", desc=True).execute()
            )
            return response.data
        except Exception:
            logger.exception("Error getting watchlist for user %s", user_id)
            return []

    async def is_in_watchlist(self, user_id: int, tmdb_id: int, media_type: str) -> bool:
        if not self.supabase:
            return False
            
        try:
            response = await asyncio.to_thread(
                lambda: self.supabase.table("watchlist").select("id").match({
                    "user_id": user_id, 
                    "tmdb_id": tmdb_id, 
                    "media_type": media_type
                }).execute()
            )
            return len(response.data) > 0
        except Exception:
            logger.exception("Error checking watchlist for user %s", user_id)
            return False

    async def count_watchlist_items(self, user_id: int, media_type: Optional[str] = None) -> int:
        if not self.supabase:
            return 0
            
        try:
            query = self.supabase.table("watchlist").select("id", count="exact").eq("user_id", user_id)
            if media_type:
                query = query.eq("media_type", media_type)
                
            response = await asyncio.to_thread(lambda: query.execute())
            return response.count if response.count is not None else 0
        except Exception:
            logger.exception("Error counting watchlist items for user %s", user_id)
            return 0
