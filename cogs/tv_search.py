import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres

logger = logging.getLogger(__name__)

async def build_tv_card(tv):
    # 1. تقليل القصة لـ 350 حرف
    overview = getattr(tv, 'overview', None) or "لا توجد قصة متاحة حالياً."
    if len(overview) > 350:
        overview = overview[:350] + "..."

    # 2. بناء هيكلية الوصف
    desc = ""
    arabic_name = getattr(tv, 'name', None)
    original_name = getattr(tv, 'original_name', None)

    if arabic_name and original_name and arabic_name.lower() != original_name.lower():
        desc += f"**🌐 {arabic_name}**\n\n"

    desc += f"**القصة:**\n{overview}"

    # تأمين سحب سنة الإصدار
    first_air_date_str = getattr(tv, 'first_air_date', "") or ""
    release_year = first_air_date_str[:4] if len(first_air_date_str) >= 4 else "غير محدد"
    tv_show_name = original_name or arabic_name or "Unknown TV Show"

    # 3. بناء الكارت بنفس الهوية البصرية للأفلام
    embed = discord.Embed(
        title=f"📺 {tv_show_name} ({release_year})",
        description=desc,
        color=discord.Color.from_rgb(229, 9, 20)
    )
    
    embed.set_author(name="🔍 نتيجة البحث")

    votes_str = f"{tv.vote_count:,}" if getattr(tv, 'vote_count', None) else "0"
    embed.add_field(
        name="⭐ TMDB Rating",
        value=f"**{tv.rating:.1f}**/10\n👥 {votes_str} votes",
        inline=True
    )

    first_air_date = getattr(tv, 'first_air_date', None) or "غير متوفر"
    embed.add_field(name="📅 First Air Date", value=f"`{first_air_date}`", inline=True)

    # حماية ضد القيم المفقودة واستخدام الإيموجي المناسب
    seasons = getattr(tv, 'number_of_seasons', 0)
    episodes = getattr(tv, 'number_of_episodes', 0)
    seasons_str = seasons if seasons else "غير متوفر"
    episodes_str = episodes if episodes else "غير متوفر"
    
    embed.add_field(
        name="📺 Seasons & Episodes", 
        value=f"**{seasons_str}** Seasons\n**{episodes_str}** Episodes", 
        inline=True
    )

    if getattr(tv, 'genre_ids', None):
        embed.add_field(name="🎭 Genres", value=format_genres(tv.genre_ids), inline=False)

    backdrop_path = getattr(tv, 'backdrop_path', None)
    if backdrop_path:
        embed.set_image(url=f"https://image.tmdb.org/t/p/w1280{backdrop_path}")

    if getattr(tv, 'poster_url', None):
        embed.set_thumbnail(url=tv.poster_url)

    embed.set_footer(text="Odinn Cinema Network • Powered by TMDB Engine 🍿")
    return embed


class TVSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="tv", description="ابحث عن مسلسل 📺")
    @app_commands.describe(query="اسم المسلسل المُراد البحث عنه")
    async def search_tv_command(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        logger.info("TV search requested | user_id=%s | query=%s", interaction.user.id, query)

        results = await self.bot.services.tmdb.search_tv(query)
        if not results:
            await interaction.followup.send(f"❌ لم يتم العثور على أي مسلسل باسم: `{query}`")
            return

        sorted_results = sorted(results, key=calculate_search_score, reverse=True)
        best_match = sorted_results[0]
        tv_id = best_match.get("id")

        tv = await self.bot.services.tmdb.get_tv_details(tv_id)
        if not tv:
            await interaction.followup.send("⚠️ حدث خطأ أثناء سحب تفاصيل المسلسل من السيرفر.")
            return

        # إرسال الكارت الفعلي بعد التأكد من جلب البيانات بنجاح
        embed = await build_tv_card(tv)
        await interaction.followup.send(embed=embed)


async def setup(bot):
    await bot.add_cog(TVSearch(bot))
