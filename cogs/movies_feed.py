import discord
from discord.ext import commands, tasks
import aiohttp
import os
import sqlite3
import logging
from dotenv import load_dotenv

# تفعيل الـ Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# تحميل ملف .env
load_dotenv()

class MoviesAndShowsFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # سحب المتغيرات من ملف البيئة
        self.tmdb_api_key = os.getenv("TMDB_API_KEY") 
        self.channel_id = int(os.getenv("MOVIES_CHANNEL_ID", 1510778860982108420)) # استبدل الرقم لو مش هتسحبه من .env
        
        self.session = None # تهيئة الـ Session
        
        # إعداد قاعدة بيانات SQLite
        # تأكد من وجود مجلد باسم database في مسار المشروع
        self.db_path = 'database/movies_history.db'
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.db_conn = sqlite3.connect(self.db_path)
        self.cursor = self.db_conn.cursor()
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS posted_media (
                media_key TEXT PRIMARY KEY
            )
        ''')
        self.db_conn.commit()

    async def cog_load(self):
        """تشتغل تلقائياً عند تحميل الـ Cog"""
        self.session = aiohttp.ClientSession()
        self.check_new_media.start()
        logger.info("MoviesAndShowsFeed Cog loaded and session started.")

    async def cog_unload(self):
        """تشتغل تلقائياً عند إيقاف الـ Cog"""
        self.check_new_media.cancel()
        if self.session:
            await self.session.close()
        self.db_conn.close()
        logger.info("MoviesAndShowsFeed Cog unloaded, session and DB closed.")

    def is_posted(self, media_key):
        self.cursor.execute('SELECT 1 FROM posted_media WHERE media_key = ?', (media_key,))
        return self.cursor.fetchone() is not None

    def mark_as_posted(self, media_key):
        self.cursor.execute('INSERT INTO posted_media (media_key) VALUES (?)', (media_key,))
        self.db_conn.commit()

    async def get_trailer(self, media_id, media_type):
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
                else:
                    logger.warning(f"Failed to fetch trailer for {media_id}. Status: {response.status}")
        except Exception as e:
            logger.error(f"Error fetching trailer for {media_id}: {e}")
        return None

    @tasks.loop(hours=24)
    async def check_new_media(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Movies channel with ID {self.channel_id} not found.")
            return

        if not self.tmdb_api_key:
            logger.error("TMDB API Key is missing! Check your .env file.")
            return

        # استخدام endpoints للإصدارات الجديدة فعلياً
        movie_url = f"https://api.themoviedb.org/3/movie/now_playing?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        tv_url = f"https://api.themoviedb.org/3/tv/on_the_air?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        
        await self.fetch_and_post(movie_url, "movie", "🎬 فيلم جديد بالسينما", discord.Color.blue(), channel)
        await self.fetch_and_post(tv_url, "tv", "📺 حلقة/مسلسل جديد", discord.Color.purple(), channel)

    async def fetch_and_post(self, url, media_type, type_text, embed_color, channel):
        if not self.session:
            return

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    # سحب أول 2 فقط لتقليل الـ Requests وتجنب الـ Rate Limit
                    items = data.get("results", [])[:2] 

                    for item in items:
                        media_id = item.get("id")
                        media_key = f"{media_type}_{media_id}" # حل مشكلة تكرار الـ ID
                        
                        if self.is_posted(media_key):
                            continue

                        title = item.get("title") if media_type == "movie" else item.get("name")
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

                        await channel.send(embed=embed, view=view)
                        self.mark_as_posted(media_key)
                else:
                    logger.error(f"TMDB API returned status: {response.status} for {media_type}")
        except Exception as e:
            logger.error(f"Exception during fetch_and_post for {media_type}: {e}")

    @check_new_media.before_loop
    async def before_check(self):
        """التأكد من جاهزية البوت قبل تشغيل اللوب"""
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MoviesAndShowsFeed(bot))
