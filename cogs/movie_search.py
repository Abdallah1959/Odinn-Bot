import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres

logger = logging.getLogger(__name__)

# دالة مساعدة مركزية لبناء الكارت السينمائي لضمان التناسق البصري التام
async def build_movie_card(movie):
    # 1. تقليل القصة لـ 350 حرف لتنظيف الـ UI وضمان عدم تضخم الرسالة
    overview = getattr(movie, 'overview', None) or "لا توجد قصة متاحة حالياً."
    if len(overview) > 350:
        overview = overview[:350] + "..."

    # 2. بناء هيكلية الوصف (العنوان العربي بالأعلى ثم القصة)
    desc = ""
    arabic_title = getattr(movie, 'title', None)
    original_title = getattr(movie, 'original_title', None)

    if arabic_title and original_title and arabic_title.lower() != original_title.lower():
        desc += f"**🌐 {arabic_title}**\n\n"

    desc += f"**القصة:**\n{overview}"

    # تأمين سحب سنة الإصدار لمنع أخطاء الـ NoneType
    release_date_str = getattr(movie, 'release_date', "") or ""
    release_year = release_date_str[:4] if len(release_date_str) >= 4 else "غير محدد"
    movie_name = original_title or arabic_title or "Unknown Movie"

    # 3. استخدام لون Netflix الأحمر العالمي المعتمد
    embed = discord.Embed(
        title=f"🎬 {movie_name} ({release_year})",
        description=desc,
        color=discord.Color.from_rgb(229, 9, 20)
    )
    embed.set_author(name="🔍 نتيجة البحث")

    votes_str = f"{movie.vote_count:,}" if getattr(movie, 'vote_count', None) else "0"
    embed.add_field(
        name="⭐ TMDB Rating",
        value=f"**{movie.rating:.1f}**/10\n👥 {votes_str} votes",
        inline=True
    )

    release_date = getattr(movie, 'release_date', None) or "غير متوفر"
    embed.add_field(name="📅 Release Date", value=f"`{release_date}`", inline=True)

    runtime_raw = getattr(movie, 'runtime', None)
    runtime_str = f"{runtime_raw} min" if runtime_raw else "غير متوفر"
    embed.add_field(name="⏱️ Runtime", value=f"`{runtime_str}`", inline=True)

    if getattr(movie, 'genre_ids', None):
        embed.add_field(name="🎭 Genres", value=format_genres(movie.genre_ids), inline=False)

    backdrop_path = getattr(movie, 'backdrop_path', None)
    if backdrop_path:
        embed.set_image(url=f"https://image.tmdb.org/t/p/w1280{backdrop_path}")

    if getattr(movie, 'poster_url', None):
        embed.set_thumbnail(url=movie.poster_url)

    embed.set_footer(text="Odinn Cinema Network • Powered by TMDB Engine 🍿")
    return embed

# كلاس القائمة المنسدلة (Select Menu) لإعطاء خيارات بحث تفاعلية بديلة
class MovieSelect(discord.ui.Select):
    def __init__(self, results, bot):
        self.bot = bot
        self.results = results  # تخزين النتائج لإعادة تمريرها وحفظ حالة القائمة
        options = []
        # جلب أفضل 10 نتائج لضمان شمولية البحث (مثل سلاسل هاري بوتر)
        for m in results[:10]:
            title = m.get("original_title") or m.get("title") or "Unknown"
            year = m.get("release_date", "N/A")[:4] if m.get("release_date") else "N/A"
            label = f"{title[:90]} ({year})" 
            
            # تأمين الوصف وقصه عند 80 حرفًا لمنع أخطاء تجاوز أحرف المنيو في ديسكورد
            raw_overview = m.get("overview") or "لا توجد قصة متاحة حالياً."
            desc = raw_overview[:80] + "..." if len(raw_overview) > 80 else raw_overview
            
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(m.get("id")),
                emoji="🎬"
            ))
        super().__init__(placeholder="👀 هل تقصد نسخة أخرى؟ اختر من هنا...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        # [تحديث الملاحظة الهندسية]: إزالة الـ Defer لتجربة مستخدم لحظية وبدون وميض
        movie_id = int(self.values[0])
        movie = await self.bot.services.tmdb.get_movie_details(movie_id)

        if not movie:
            await interaction.response.send_message("⚠️ حدث خطأ أثناء سحب تفاصيل الفيلم.", ephemeral=True)
            return

        # إعادة بناء الكارت ذو التصميم العالمي للفيلم المختار حديثاً
        embed = await build_movie_card(movie)

        # تصفير وبناء عناصر الـ View من جديد بالروابط المحدثة لمنع الاختلاط
        view = discord.ui.View(timeout=None)

        watch_id = getattr(movie, 'imdb_id', None) or str(getattr(movie, 'tmdb_id', ''))
        if watch_id:
            watch_url = f"https://vidsrc.to/embed/movie/{watch_id}"
            view.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link, row=0))

        if getattr(movie, 'trailer_url', None):
            view.add_item(discord.ui.Button(label="Watch Trailer 🍿", url=movie.trailer_url, style=discord.ButtonStyle.link, row=0))

        if getattr(movie, 'imdb_id', None):
            imdb_url = f"https://www.imdb.com/title/{movie.imdb_id}/"
            view.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link, row=0))

        # حقن قائمة الخيارات نفسها مجدداً في الـ View للمحافظة على إمكانية التنقل اللانهائي
        view.add_item(MovieSelect(self.results, self.bot))
        
        # [تحديث الملاحظة الهندسية]: تعديل الرسالة الأصلية مباشرة للحصول على أسرع استجابة
        await interaction.response.edit_message(embed=embed, view=view)

class MovieSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="movie", description="ابحث عن فيلم وشاهد التقييم والتريلر والمشاهدة المباشرة 🍿")
    @app_commands.describe(query="اسم الفيلم المُراد البحث عنه")
    async def search_movie(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        logger.info("Movie search requested | user_id=%s | query=%s", interaction.user.id, query)

        results = await self.bot.services.tmdb.search_movies(query)
        if not results:
            await interaction.followup.send(f"❌ لم يتم العثور على أي فيلم باسم: `{query}`")
            return

        # ترتيب القائمة المرجعة عبر محرك البحث واختيار النتيجة الأعلى سكور تلقائياً كـ Default
        sorted_results = sorted(results, key=calculate_search_score, reverse=True)
        best_match = sorted_results[0]
        movie_id = best_match.get("id")

        movie = await self.bot.services.tmdb.get_movie_details(movie_id)
        if not movie:
            await interaction.followup.send("⚠️ حدث خطأ أثناء سحب تفاصيل الفيلم من السيرفر.")
            return

        embed = await build_movie_card(movie)

        view = discord.ui.View(timeout=None)

        # بناء أزرار روابط المشاهدة والإعلانات في الصف العلوي (row=0)
        watch_id = getattr(movie, 'imdb_id', None) or str(getattr(movie, 'tmdb_id', ''))
        if watch_id:
            watch_url = f"https://vidsrc.to/embed/movie/{watch_id}"
            view.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link, row=0))

        if getattr(movie, 'trailer_url', None):
            view.add_item(discord.ui.Button(label="Watch Trailer 🍿", url=movie.trailer_url, style=discord.ButtonStyle.link, row=0))

        if getattr(movie, 'imdb_id', None):
            imdb_url = f"https://www.imdb.com/title/{movie.imdb_id}/"
            view.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link, row=0))

        # في حال تواجُد أكثر من فيلم مطابق للبحث، نقوم بحقن القائمة المنسدلة في الصف السفلي (row=1)
        if len(sorted_results) > 1:
            view.add_item(MovieSelect(sorted_results, self.bot))

        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(MovieSearch(bot))
