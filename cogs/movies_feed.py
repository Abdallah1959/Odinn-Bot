import discord
from discord.ext import commands, tasks
import aiohttp
import os
import aiosqlite
import logging
from typing import Optional
from discord.abc import Messageable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MoviesAndShowsFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.tmdb_api_key = os.getenv("TMDB_API_KEY") 
        self.channel_id = int(os.getenv("MOVIES_CHANNEL_ID", 1510778860982108420))
        
        if not self.tmdb_api_key:
            raise ValueError("🚨 TMDB_API_KEY is missing from environment variables!")
            
        self.session: Optional[aiohttp.ClientSession] = None 
        self.db_conn: Optional[aiosqlite.Connection] = None
        self.db_path = 'database/movies_history.db'

    async def cog_load(self):
        # رجعنا التايم أوت لـ 15 ثانية زي ما المهندس نصح
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
        if not self.db_conn: return False
        async with self.db_conn.execute('SELECT 1 FROM posted_media WHERE media_key = ?', (media_key,)) as cursor:
            row = await cursor.fetchone()
            return row is not None

    async def mark_as_posted(self, media_key: str):
        if self.db_conn:
            await self.db_conn.execute('INSERT INTO posted_media (media_key) VALUES (?)', (media_key,))

    @tasks.loop(hours=24)
    async def check_new_media(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Movies channel with ID {self.channel_id} not found.")
            return

        movie_url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        tv_url = f"https://api.themoviedb.org/3/tv/on_the_air?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        
        await self.fetch_and_post(movie_url, "movie", "🎬 فيلم جديد", discord.Color.red(), channel)
        await self.fetch_and_post(tv_url, "tv", "📺 مسلسل جديد", discord.Color.gold(), channel)

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

                        details_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={self.tmdb_api_key}&language=ar-SA&append_to_response=external_ids,videos"
                        
                        async with self.session.get(details_url) as details_response:
                            if details_response.status != 200:
                                continue
                            
                            details = await details_response.json()
                            
                            original_title = details.get("original_title") or details.get("original_name")
                            arabic_title = details.get("title") or details.get("name")
                            
                            overview = details.get("overview")
                            if not overview: 
                                en_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={self.tmdb_api_key}&language=en-US"
                                async with self.session.get(en_url) as en_response:
                                    if en_response.status == 200:
                                        en_details = await en_response.json()
                                        overview = en_details.get("overview") or "No overview available."
                            
                            poster_path = details.get("poster_path")
                            poster_url = f"https://image.tmdb.org/t/p/original{poster_path}" if poster_path else None
                            
                            imdb_id = details.get("external_ids", {}).get("imdb_id")
                            
                            trailer_url = None
                            for video in details.get("videos", {}).get("results", []):
                                if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                                    trailer_url = f"https://www.youtube.com/watch?v={video.get('key')}"
                                    break

                            embed = discord.Embed(
                                title=original_title,
                                description=overview,
                                color=embed_color
                            )
                            embed.set_author(name=type_text)
                            
                            if arabic_title and original_title != arabic_title:
                                embed.add_field(name="الاسم المترجم", value=arabic_title, inline=False)
                                
                            if poster_url:
                                embed.set_image(url=poster_url)
                            
                            view = discord.ui.View()
                            
                            if trailer_url:
                                view.add_item(discord.ui.Button(label="Trailer 🍿", url=trailer_url, style=discord.ButtonStyle.link))
                            
                            # إضافة الزرار الرسمي بتاع IMDb
                            if imdb_id:
                                imdb_official_url = f"https://www.imdb.com/title/{imdb_id}/"
                                view.add_item(discord.ui.Button(label="IMDb", url=imdb_official_url, style=discord.ButtonStyle.link))

                                # زرار المشاهدة
                                if media_type == "movie":
                                    watch_url = f"https://streamimdb.ru/embed/movie/{imdb_id}"
                                else:
                                    watch_url = f"https://streamimdb.ru/embed/tv/{imdb_id}/1/1" 
                                view.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link))

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
