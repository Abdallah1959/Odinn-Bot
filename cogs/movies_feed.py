import discord
from discord.ext import commands, tasks
import aiohttp

class MoviesFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # الـ API Key بتاعك محطوط وجاهز
        self.tmdb_api_key = "6308ce9754ab0b92f4b376e6b70d6cfe" 
        
        # ⚠️ متنساش تحط الـ ID بتاع روم الأفلام هنا (بدون علامات تنصيص)
        self.channel_id = 1510778860982108420  
        
        # دي مصفوفة عشان البوت يفتكر الأفلام اللي بعتها وميكررهاش
        self.posted_movies = set()
        
        # تشغيل اللوب أول ما البوت يفتح
        self.check_new_movies.start()

    def cog_unload(self):
        self.check_new_movies.cancel()

    async def get_movie_trailer(self, movie_id):
        """دالة بتجيب لينك تريلر اليوتيوب للفيلم"""
        url = f"https://api.themoviedb.org/3/movie/{movie_id}/videos?api_key={self.tmdb_api_key}"
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    for video in data.get("results", []):
                        if video.get("type") == "Trailer" and video.get("site") == "YouTube":
                            return f"https://www.youtube.com/watch?v={video.get('key')}"
        return None

    @tasks.loop(hours=24) # البوت هيبحث عن الجديد كل 24 ساعة
    async def check_new_movies(self):
        await self.bot.wait_until_ready()
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            return

        # رابط بيجيب أحدث الأفلام اللي نزلت (التريند)
        url = f"https://api.themoviedb.org/3/trending/movie/day?api_key={self.tmdb_api_key}&language=ar-SA"
        
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                if response.status == 200:
                    data = await response.json()
                    movies = data.get("results", [])[:3] # هنجيب أول 3 أفلام تريند بس عشان منعملش سبام

                    for movie in movies:
                        movie_id = movie.get("id")
                        
                        # لو الفيلم ده اتبعت قبل كده، تجاهله
                        if movie_id in self.posted_movies:
                            continue

                        title = movie.get("title")
                        overview = movie.get("overview") or "لا توجد قصة متاحة حالياً."
                        poster_path = movie.get("poster_path")
                        poster_url = f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else None
                        
                        # نجيب التريلر
                        trailer_url = await self.get_movie_trailer(movie_id)

                        # تصميم رسالة الـ Embed الفخمة
                        embed = discord.Embed(
                            title=f"🎬 فيلم جديد: {title}",
                            description=overview,
                            color=discord.Color.blue()
                        )
                        if poster_url:
                            embed.set_image(url=poster_url)
                        
                        # زرار مشاهدة التريلر لو موجود
                        view = discord.ui.View()
                        if trailer_url:
                            button = discord.ui.Button(label="شاهد التريلر 🍿", url=trailer_url, style=discord.ButtonStyle.link)
                            view.add_item(button)

                        await channel.send(embed=embed, view=view)
                        
                        # حفظ الـ ID عشان ميبعتوش تاني
                        self.posted_movies.add(movie_id)

async def setup(bot):
    await bot.add_cog(MoviesFeed(bot))
