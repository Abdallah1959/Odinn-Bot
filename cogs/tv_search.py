import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres

logger = logging.getLogger(__name__)

async def build_tv_card(tv):
    overview = getattr(tv, 'overview', None) or "لا توجد قصة متاحة حالياً."
    if len(overview) > 350:
        overview = overview[:350] + "..."

    desc = ""
    arabic_name = getattr(tv, 'name', None)
    original_name = getattr(tv, 'original_name', None)

    if arabic_name and original_name and arabic_name.lower() != original_name.lower():
        desc += f"**🌐 {arabic_name}**\n\n"

    desc += f"**القصة:**\n{overview}"

    first_air_date_str = getattr(tv, 'first_air_date', "") or ""
    release_year = first_air_date_str[:4] if len(first_air_date_str) >= 4 else "غير محدد"
    tv_show_name = original_name or arabic_name or "Unknown TV Show"

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

    seasons = getattr(tv, 'number_of_seasons', 0)
    episodes = getattr(tv, 'number_of_episodes', 0)
    seasons_str = seasons if seasons else "غير متوفر"
    episodes_str = episodes if episodes else "غير متوفر"
    
    embed.add_field(
        name="📺 Seasons & Episodes", 
        value=f"📺 **{seasons_str}** Seasons\n🎞️ **{episodes_str}** Episodes", 
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

# كلاس القائمة المنسدلة
class TVSelect(discord.ui.Select):
    def __init__(self, results, bot):
        self.bot = bot
        self.results = results
        options = []
        for t in results[:10]:
            title = t.get("original_name") or t.get("name") or "Unknown"
            year = t.get("first_air_date", "N/A")[:4] if t.get("first_air_date") else "N/A"
            label = f"{title[:90]} ({year})" 
            
            raw_overview = t.get("overview") or "لا توجد قصة متاحة حالياً."
            desc = raw_overview[:80] + "..." if len(raw_overview) > 80 else raw_overview
            
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(t.get("id")),
                emoji="📺"
            ))
        super().__init__(placeholder="👀 هل تقصد مسلسل آخر؟ اختر من هنا...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        tv_id = int(self.values[0])
        tv = await self.bot.services.tmdb.get_tv_details(tv_id)

        if not tv:
            await interaction.response.send_message("⚠️ حدث خطأ أثناء سحب تفاصيل المسلسل.", ephemeral=True)
            return

        embed = await build_tv_card(tv)
        # استخدام الـ Helper لإنشاء الأزرار والمنيو
        view = build_tv_view(tv, self.results, self.bot)
        
        await interaction.response.edit_message(embed=embed, view=view)

# [التحسين الاحترافي]: Helper لبناء الـ View بالكامل وتجنب تكرار الكود
def build_tv_view(tv, results, bot):
    view = discord.ui.View(timeout=300)

    if getattr(tv, 'tmdb_id', None):
        # سيتم تطوير الرابط لاحقاً لدعم الموسم والحلقة: /tv/{id}/{season}/{episode}
        watch_url = f"https://vidsrc.to/embed/tv/{tv.tmdb_id}"
        view.add_item(discord.ui.Button(label="Watch Now 📺", url=watch_url, style=discord.ButtonStyle.link, row=0))

    if getattr(tv, 'imdb_id', None):
        imdb_url = f"https://www.imdb.com/title/{tv.imdb_id}/"
        view.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link, row=0))

    if getattr(tv, 'trailer_url', None):
        view.add_item(discord.ui.Button(label="Trailer 🎬", url=tv.trailer_url, style=discord.ButtonStyle.link, row=0))

    if len(results) > 1:
        view.add_item(TVSelect(results, bot))

    return view

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

        embed = await build_tv_card(tv)
        # استخدام الـ Helper لإنشاء الأزرار والمنيو
        view = build_tv_view(tv, sorted_results, self.bot)

        await interaction.followup.send(embed=embed, view=view)

async def setup(bot):
    await bot.add_cog(TVSearch(bot))
