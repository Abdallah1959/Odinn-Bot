import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres  # الاعتماد الكامل على الـ API النظيف الموحد

logger = logging.getLogger(__name__)

class MovieSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="movie", description="ابحث عن فيلم وشاهد التقييم والتريلر والمشاهدة المباشرة 🍿")
    @app_commands.describe(query="اسم الفيلم المُراد البحث عنه")
    async def search_movie(self, interaction: discord.Interaction, query: str):
        # 1. Defer لمنع الـ Timeout أثناء جلب بيانات الـ API
        await interaction.response.defer(thinking=True)
        
        # تسجيل طلب البحث في الـ Log باستخدام Lazy Formatting للاستقرار والأداء العالي
        logger.info("Movie search requested | user_id=%s | query=%s", interaction.user.id, query)

        # 2. البحث عن الفيلم عبر السيشن الآمن
        results = await self.bot.services.tmdb.search_movies(query)
        if not results:
            await interaction.followup.send(f"❌ لم يتم العثور على أي فيلم باسم: `{query}`")
            return

        # 3. استخدام max() لجلب النتيجة الفضلى مباشرة بناءً على محرك الترتيب
        best_match = max(results, key=calculate_search_score)
        movie_id = best_match.get("id")

        # 4. جلب التفاصيل الكاملة والـ Fallback للفيلم (تُرجع كائن Movie Model حصراً)
        movie = await self.bot.services.tmdb.get_movie_details(movie_id)
        if not movie:
            await interaction.followup.send("⚠️ حدث خطأ أثناء سحب تفاصيل الفيلم من السيرفر.")
            return

        # 5. معالجة النصوص وحمايتها من الـ NoneType والتضخم (Embed Safety)
        overview = movie.overview or "لا توجد قصة متاحة حالياً."
        if len(overview) > 900:
            overview = overview[:900] + "..."

        # استخراج سنة الإصدار بأمان للعنوان السينمائي الاحترافي
        release_year = movie.release_date[:4] if movie.release_date and len(movie.release_date) >= 4 else "غير محدد"

        # حماية الـ Title من الـ NoneType والوقوع في فخ طباعة الكلمة النصية "None"
        movie_name = movie.original_title or movie.title or "Unknown Movie"

        # 6. بناء الـ Embed الاحترافي ذو المظهر العالمي (Netflix / Plex style)
        embed = discord.Embed(
            title=f"🎬 {movie_name} ({release_year})",
            description=f"**القصة:**\n{overview}",
            color=discord.Color.dark_red()  # لون أحمر هادئ واحترافي سينمائي
        )
        embed.set_author(name="🔍 نتيجة البحث الفضلى")

        # حماية إضافية لتفادي NoneType أثناء مقارنة الاسم العربي بالأصلي
        if movie.title and movie.original_title and movie.title.lower() != movie.original_title.lower():
            embed.add_field(name="🌐 العنوان العربي", value=movie.title, inline=False)

        # دمج التقييم وعدد الأصوات للحصول على حقل UX نظيف وعالمي
        votes_str = f"{movie.vote_count:,}" if movie.vote_count else "0"
        embed.add_field(
            name="⭐ TMDB Rating", 
            value=f"**{movie.rating:.1f}**/10\n👥 {votes_str} votes", 
            inline=True
        )
        
        # حماية حقل تاريخ الإصدار لتفادي ظهور None
        release_date = movie.release_date if movie.release_date else "غير متوفر"
        embed.add_field(name="📅 Release Date", value=f"`{release_date}`", inline=True)

        # [الالتزام بالمعمارية]: استدعاء الـ Runtime مباشرة من خصائص الـ Model بشكل آمن ونظيف
        runtime_raw = getattr(movie, 'runtime', None)
        runtime_str = f"{runtime_raw} min" if runtime_raw else "غير متوفر"
        embed.add_field(name="⏱️ Runtime", value=f"`{runtime_str}`", inline=True)

        # استدعاء الـ Helper الموحد لملء التصنيفات بشكل سليم ومعماري صحيح
        embed.add_field(name="🎭 Genres", value=format_genres(movie.genre_ids), inline=False)

        # [الالتزام بالمعمارية]: سحب مسار الـ Backdrop النظيف من كائن الـ Model مباشرة
        backdrop_path = getattr(movie, 'backdrop_path', None)
        if backdrop_path:
            embed.set_image(url=f"https://image.tmdb.org/t/p/w1280{backdrop_path}")
            
        if movie.poster_url:
            embed.set_thumbnail(url=movie.poster_url)

        embed.set_footer(text="Odinn Cinema Network • Powered by TMDB Engine 🍿")

        # 7. الأزرار المرتبة استراتيجياً لرفع معدل النقر مع تعطيل الـ Timeout للحفاظ على الموارد
        view = discord.ui.View(timeout=None)
        
        watch_id = movie.imdb_id if movie.imdb_id else str(movie.tmdb_id)
        
        # تأمين رابط وبنية مسار المشاهدة لـ VidSrc بشكل كامل ومباشر
        watch_url = f"https://vidsrc.to/embed/movie/{watch_id}"
        
        # زر المشاهدة الرئيسي أولاً دائماً لرفع معدل الـ UX والـ Click Rate
        view.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link))
        
        # زر الإعلان الترويجي ثانياً
        if movie.trailer_url:
            view.add_item(discord.ui.Button(label="Watch Trailer 🍿", url=movie.trailer_url, style=discord.ButtonStyle.link))
            
        # تأمين وضبط مسار الرابط الخارجي لـ IMDb بالكامل
        if movie.imdb_id:
            imdb_url = f"https://www.imdb.com/title/{movie.imdb_id}/"
            view.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link))

        # إرسال الكارت السينمائي المتكامل النهائي للمستخدم
        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(MovieSearch(bot))
