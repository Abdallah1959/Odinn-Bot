import discord
from discord.ext import commands, tasks
from discord import app_commands
import aiohttp
import os
import aiosqlite
import logging
from typing import Optional
from discord.abc import Messageable
import datetime

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

    # ---------------------------------------------------------
    # الميزة الجديدة: أوامر البحث (Slash Commands)
    # ---------------------------------------------------------
    @app_commands.command(name="movie", description="ابحث عن فيلم وشاهد التقييم والتريلر 🍿")
    @app_commands.describe(query="اسم الفيلم اللي بتدور عليه")
    async def search_movie(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True) # عشان لو الـ API أخد وقت
        
        if not self.session:
            await interaction.followup.send("🚨 عذراً، خدمة الأفلام غير متاحة حالياً.")
            return
            
        search_url = f"https://api.themoviedb.org/3/search/movie?api_key={self.tmdb_api_key}&query={query}&language=ar-SA&page=1"
        
        try:
            async with self.session.get(search_url) as response:
                if response.status == 200:
                    data = await response.json()
                    results = data.get("results", [])
                    
                    if not results:
                        await interaction.followup.send(f"❌ ملقيتش أي فيلم بالاسم ده: `{query}`")
                        return
                        
                    # خوارزمية ترتيب النتائج بناءً على التطابق والشعبية
                    best_match = sorted(
                        results,
                        key=lambda x: (x.get("popularity", 0) * 0.5) + (x.get("vote_average", 0) * 3),
                        reverse=True
                    )[0]
                    
                    media_id = best_match.get("id")
                    embed, view = await self.build_media_embed(media_id, "movie", "🔍 نتيجة البحث", discord.Color.green())
                    
                    if embed:
                        await interaction.followup.send(embed=embed, view=view)
                    else:
                        await interaction.followup.send("⚠️ حصلت مشكلة في سحب تفاصيل الفيلم.")
                else:
                    await interaction.followup.send("🚨 فشل الاتصال بقاعدة بيانات الأفلام.")
        except Exception as e:
            logger.exception("Error in /movie search")
            await interaction.followup.send("🚨 حصل خطأ غير متوقع.")

    # ---------------------------------------------------------
    # محرك الترشيحات اليومية (Daily Picks Engine)
    # ---------------------------------------------------------
    @tasks.loop(time=datetime.time(hour=20, minute=0)) # تشتغل الساعة 8 بالليل يومياً
    async def check_new_media(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error(f"Movies channel with ID {self.channel_id} not found.")
            return

        # هنسحب من الـ Popular بدل الـ Now Playing عشان نضمن جودة أعلى
        movie_url = f"https://api.themoviedb.org/3/movie/popular?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        tv_url = f"https://api.themoviedb.org/3/tv/popular?api_key={self.tmdb_api_key}&language=ar-SA&page=1"
        
        await self.fetch_and_post_daily_pick(movie_url, "movie", "⭐ Movie Pick of the Day", discord.Color.gold(), channel)
        await self.fetch_and_post_daily_pick(tv_url, "tv", "⭐ TV Show Pick of the Day", discord.Color.gold(), channel)

    async def fetch_and_post_daily_pick(self, url: str, media_type: str, type_text: str, embed_color: discord.Color, channel: Messageable):
        if not self.session or not self.db_conn:
            return

        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    raw_items = data.get("results", [])
                    
                    valid_items = []
                    for item in raw_items:
                        vote_avg = item.get("vote_average", 0)
                        vote_count = item.get("vote_count", 0)
                        overview = item.get("overview")
                        poster = item.get("poster_path")
                        
                        # تطبيق فلاتر الجودة الصارمة
                        if vote_count >= 200 and vote_avg >= 6.5 and overview and poster:
                            # حساب الـ Score المخصص
                            custom_score = (vote_avg * 0.6) + ((item.get("popularity", 0) / 100) * 0.4)
                            item['custom_score'] = custom_score
                            valid_items.append(item)
                    
                    # ترتيب واختيار الأفضل
                    valid_items.sort(key=lambda x: x.get('custom_score', 0), reverse=True)
                    
                    for best_item in valid_items:
                        media_id = best_item.get("id")
                        media_key = f"{media_type}_{media_id}" 
                        
                        if await self.is_posted(media_key):
                            continue # لو نزلناه قبل كده، شف اللي بعده في الترتيب
                            
                        embed, view = await self.build_media_embed(media_id, media_type, type_text, embed_color)
                        
                        if embed:
                            try:
                                await channel.send(embed=embed, view=view)
                                await self.mark_as_posted(media_key)
                                await self.db_conn.commit()
                                break # كفاية عملنا Pick لواحد بس في اليوم
                            except Exception as err:
                                logger.error(f"Error sending daily pick: {err}")
                else:
                    logger.error(f"TMDB API returned status: {response.status} for {media_type}")
        except Exception:
            if self.db_conn:
                await self.db_conn.rollback() 
            logger.exception(f"🚨 Exception during daily pick for {media_type}")

    # ---------------------------------------------------------
    # دالة بناء الكارت (مفصولة عشان نستخدمها في البحث والـ Feed)
    # ---------------------------------------------------------
    async def build_media_embed(self, media_id: int, media_type: str, type_text: str, embed_color: discord.Color):
        details_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={self.tmdb_api_key}&language=ar-SA&append_to_response=external_ids,videos"
        
        async with self.session.get(details_url) as response:
            if response.status != 200:
                return None, None
                
            details = await response.json()
            
            original_title = details.get("original_title") or details.get("original_name")
            arabic_title = details.get("title") or details.get("name")
            
            overview = details.get("overview")
            if not overview: 
                en_url = f"https://api.themoviedb.org/3/{media_type}/{media_id}?api_key={self.tmdb_api_key}&language=en-US"
                async with self.session.get(en_url) as en_response:
                    if en_response.status == 200:
                        en_details = await en_response.json()
                        overview = en_details.get("overview") or "No overview available."
            
            if len(overview) > 350:
                overview = overview[:350] + "..."
                
            vote_average = details.get("vote_average", 0.0)
            release_date = details.get("release_date") or details.get("first_air_date") or "غير محدد"
            
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
                description=f"**القصة:**\n{overview}",
                color=embed_color
            )
            embed.set_author(name=type_text)
            
            if arabic_title and original_title != arabic_title:
                embed.add_field(name="🌐 الاسم المترجم", value=arabic_title, inline=False)
            
            embed.add_field(name="⭐ التقييم", value=f"{vote_average:.1f}/10", inline=True)
            embed.add_field(name="📅 الإصدار", value=release_date, inline=True)
                
            if poster_url:
                embed.set_image(url=poster_url)
                
            embed.set_footer(text="Odinn Cinema Network 🍿")
            
            view = discord.ui.View()
            
            if trailer_url:
                view.add_item(discord.ui.Button(label="Trailer 🍿", url=trailer_url, style=discord.ButtonStyle.link))
            
            if imdb_id:
                imdb_official_url = f"https://www.imdb.com/title/{imdb_id}/"
                view.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_official_url, style=discord.ButtonStyle.link))

                if media_type == "movie":
                    watch_url = f"https://streamimdb.ru/embed/movie/{imdb_id}"
                else:
                    watch_url = f"https://streamimdb.ru/embed/tv/{imdb_id}/1/1" 
                view.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link))

            return embed, view

    @check_new_media.before_loop
    async def before_check(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MoviesAndShowsFeed(bot))
