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
        title=f"{tv_show_name} ({release_year})",
        description=desc,
        color=discord.Color.from_rgb(229, 9, 20)
    )
    embed.set_author(name="📺 TV Search Result")
    
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


class TVView(discord.ui.View):
    # تم إضافة library_user_id كمتغير اختياري
    def __init__(self, tv, results, bot, is_in_watchlist: bool = False, library_user_id: int = None):
        super().__init__(timeout=300)
        self.tv = tv
        self.bot = bot
        self.results = results
        
        if getattr(tv, 'tmdb_id', None):
            watch_url = f"https://vidsrc.to/embed/tv/{tv.tmdb_id}"
            self.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link, row=0))
            
        if getattr(tv, 'imdb_id', None):
            imdb_url = f"https://www.imdb.com/title/{tv.imdb_id}/"
            self.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link, row=0))
            
        if getattr(tv, 'trailer_url', None):
            self.add_item(discord.ui.Button(label="Trailer 🍿", url=tv.trailer_url, style=discord.ButtonStyle.link, row=0))
            
        if len(results) > 1:
            self.add_item(TVSelect(results, bot))

        if is_in_watchlist:
            self.add_to_watchlist_btn.style = discord.ButtonStyle.success
            self.add_to_watchlist_btn.label = "In Watchlist ✅"
            self.add_to_watchlist_btn.disabled = True

        # إضافة زر العودة للمكتبة
        if library_user_id:
            from views.watchlist_views import BackToLibraryButton
            self.add_item(BackToLibraryButton(bot, library_user_id))

    @discord.ui.button(label="Add To Watchlist ⭐", style=discord.ButtonStyle.secondary, custom_id="add_to_watchlist_tv", row=0)
    async def add_to_watchlist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            user_id = interaction.user.id
            tmdb_id = getattr(self.tv, 'tmdb_id', None)
            
            if not tmdb_id:
                button.disabled = False
                await interaction.followup.send("❌ لا يمكن إضافة هذا المسلسل حالياً (بيانات مفقودة).", ephemeral=True)
                return
                
            media_type = "tv"
            media_name = getattr(self.tv, 'name') or getattr(self.tv, 'original_name') or "Unknown"
            poster_url = getattr(self.tv, 'poster_url', None)
            first_air_date_str = getattr(self.tv, 'first_air_date', "") or ""
            release_year = first_air_date_str[:4] if len(first_air_date_str) >= 4 else "N/A"

            is_in = await self.bot.services.db.is_in_watchlist(user_id, tmdb_id, media_type)
            if is_in:
                button.style = discord.ButtonStyle.success
                button.label = "In Watchlist ✅"
                button.disabled = True
                await interaction.followup.send("⚠️ هذا المسلسل موجود بالفعل في قائمة المشاهدة الخاصة بك!", ephemeral=True)
                return

            added = await self.bot.services.db.add_to_watchlist(
                user_id=user_id,
                tmdb_id=tmdb_id,
                media_type=media_type,
                media_name=media_name,
                poster_url=poster_url,
                release_year=release_year
            )
            
            if added:
                button.style = discord.ButtonStyle.success
                button.label = "In Watchlist ✅"
                button.disabled = True
                await interaction.followup.send(f"✅ تمت إضافة **{media_name}** إلى قائمة المشاهدة.", ephemeral=True)
            else:
                button.disabled = False
                await interaction.followup.send("❌ حدث خطأ أثناء إضافة المسلسل، يرجى المحاولة لاحقاً.", ephemeral=True)
                
        finally:
            await interaction.edit_original_response(view=self)


class TVSelect(discord.ui.Select):
    def __init__(self, results, bot):
        self.bot = bot
        self.results = results
        
        options = []
        for t in results[:10]:
            name = t.get("original_name") or t.get("name") or "Unknown"
            year = t.get("first_air_date", "N/A")[:4] if t.get("first_air_date") else "N/A"
            label = f"{name[:90]} ({year})"
            
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
        
        tmdb_id = getattr(tv, 'tmdb_id', tv_id)
        is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "tv")
        view = TVView(tv, self.results, self.bot, is_in_watchlist)
        
        await interaction.response.edit_message(embed=embed, view=view)


class TVSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def tv_autocomplete(
        self, 
        interaction: discord.Interaction, 
        current: str
    ) -> list[app_commands.Choice[str]]:
        
        current = current.strip()
        if len(current) < 2:
            return []
            
        results = await self.bot.services.tmdb.search_tv(current)
        if not results:
            return []
            
        sorted_results = sorted(results, key=calculate_search_score, reverse=True)
        choices = []
        seen_names = set()
        
        for tv in sorted_results:
            name = tv.get("original_name") or tv.get("name") or "Unknown"
            year = tv.get("first_air_date", "")[:4] if tv.get("first_air_date") else "N/A"
            display_name = f"{name} ({year})"
            
            if display_name not in seen_names:
                choices.append(
                    app_commands.Choice(
                        name=display_name[:100],
                        value=name[:100]
                    )
                )
                seen_names.add(display_name)
                
            if len(choices) >= 25:
                break
                
        return choices

    @app_commands.command(name="tv", description="ابحث عن مسلسل 📺")
    @app_commands.describe(query="اسم المسلسل المُراد البحث عنه")
    @app_commands.autocomplete(query=tv_autocomplete)
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
        
        tmdb_id = getattr(tv, 'tmdb_id', tv_id)
        is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "tv")
        view = TVView(tv, sorted_results, self.bot, is_in_watchlist)
        
        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(TVSearch(bot))
