import discord
from discord.ext import commands, tasks
import aiohttp
import os
import aiosqlite
import logging
from typing import Optional
from discord.abc import Messageable

# تفعيل الـ Logging الاحترافي
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MoviesAndShowsFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tmdb_api_key = os.getenv("TMDB_API_KEY") 
        self.channel_id = int(os.getenv("MOVIES_CHANNEL_ID", 1510778860982108420))
        
        if not self.tmdb_api_key:
            raise ValueError("🚨 TMDB_API_KEY is missing from environment variables!")
            
        # إضافة Type Hints للخصائص
        self.session: Optional[aiohttp.ClientSession] = None 
        self.db_conn: Optional[aiosqlite.Connection] = None
        self.db_path = 'database/movies_history.db'

    async def cog_load(self):
        timeout = aiohttp.ClientTimeout(total=15)
        self.session = aiohttp.ClientSession(timeout=timeout)
        
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.db_conn = await aiosqlite.connect(self.db_path)
        await self.db_conn.execute('''
            CREATE TABLE IF NOT EXISTS posted_media (
                media_key TEXT PRIMARY KEY
            )
        ''')
        await self.db_conn.commit()

        self.check_new_media.start()
        logger.info("MoviesAndShowsFeed Cog loaded successfully.")

    async def cog_unload(self):
        self.check_new_media.cancel()
        if self.session:
            await self.session.close()
        if self.db_conn:
            await self.db_conn.close()
        logger.info("MoviesAndShowsFeed Cog unloaded.")

    async def is_posted(self, media_key: str) -> bool:
        async with self.db_conn.execute('SELECT 1 FROM posted_media WHERE media_key = ?', (media_key,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def mark_as_posted(self, media_key: str):
        await self.db_conn.execute('INSERT INTO posted_media (media_key) VALUES (?)', (media_key,))

    async def get_trailer(self, media_id: int, media_type: str) -> Optional[str]:
        if not self.session:
            return None
            
        url = f"https://api.themoviedb.org/3/{media_type}/{media_id}/videos?api_key={self.tmdb_api_key}"
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    for video in data.get("results", []):
                        if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                            return f"https://www.youtube.com/watch?v={video.get('key')}"
        except Exception:
            logger.exception(f"Error fetching trailer for {media_type} ID: {media_id}")
        return None

    @tasks.loop(hours=24)
    async def check_new_media(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Movies channel with ID {self.channel_id} not found.")
            return

        movie_url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        tv_url = f"https://api.themoviedb.org/3/tv/on_the_air?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        
        await self.fetch_and_post(movie_url, "movie", "🎬 فيلم جديد بالسينما", discord.Color.blue(), channel)
        await self.fetch_and_post(tv_url, "tv", "📺 مسلسل جديد", discord.Color.purple(), channel)

    async def fetch_and_post(self, url: str, media_type: str, type_text: str, embed_color: discord.Color, channel: Messageable):
        if not self.session or not self.db_conn:
            return

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    items = data.get("results", [])[:2] 

                    for item in items:
                        media_id = item.get("id")
                        media_key = f"{media_type}_{media_id}" 
                        
                        if await self.is_posted(media_key):
                            continue

                        # الذوق البرمجي الأفضل
                        title = item.get("title") or item.get("name")
                        overview = item.get("overview") or "لا توجد قصة متاحة حالياً."
                        poster_path = item.get("poster_path")
                        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                        
                        trailer_url = await self.get_trailer(media_id, media_type)

                        embed = discord.Embed(
                            title=f"{type_text}: {title}",
                            description=overview,
                            color=embed_color
                        )
                        if poster_url:
                            embed.set_image(url=poster_url)
                        
                        view = discord.ui.View()
                        if trailer_url:
                            button = discord.ui.Button(label="شاهد التريلر 🍿", url=trailer_url, style=discord.ButtonStyle.link)
                            view.add_item(button)

                        # معالجة استثناءات ديسكورد بدقة
                        try:
                            await channel.send(embed=embed, view=view)
                            await self.mark_as_posted(media_key)
                        except discord.Forbidden:
                            logger.error(f"Missing permissions to send messages in {self.channel_id}")
                            continue 
                        except discord.HTTPException as http_err:
                            logger.error(f"Discord HTTP error: {http_err}")
                            continue
                    
                    await self.db_conn.commit()
                else:
                    logger.error(f"TMDB API returned status: {response.status} for {media_type}")
        except Exception:
            if self.db_conn:
                await self.db_conn.rollback() 
            logger.exception(f"🚨 Exception during fetch_and_post for {media_type}")

    @check_new_media.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MoviesAndShowsFeed(bot))
