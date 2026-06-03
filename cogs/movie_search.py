import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres

logger = logging.getLogger(__name__)

async def build_movie_card(movie):
    overview = getattr(movie, 'overview', None) or "لا توجد قصة متاحة حالياً."
    if len(overview) > 350:
        overview = overview[:350] + "..."

    desc = ""
    arabic_title = getattr(movie, 'title', None)
    original_title = getattr(movie, 'original_title', None)

    if arabic_title and original_title and arabic_title.lower() != original_title.lower():
        desc += f"**🌐 {arabic_title}**\n\n"

    desc += f"**القصة:**\n{overview}"

    release_date_str = getattr(movie, 'release_date', "") or ""
    release_year = release_date_str[:4] if len(release_date_str) >= 4 else "غير محدد"
    movie_name = original_title or arabic_title or "Unknown Movie"

    embed = discord.Embed(
        title=f"{movie_name} ({release_year})",
        description=desc,
        color=discord.Color.from_rgb(229, 9, 20)
    )
    embed.set_author(name="🎬 Movie Search Result")

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


class MovieView(discord.ui.View):
    def __init__(self, movie, results, bot, is_in_watchlist: bool = False):
        super().__init__(timeout=300)
        self.movie = movie
        self.bot = bot
        self.results = results
        
        watch_id = getattr(movie, 'imdb_id', None) or str(getattr(movie, 'tmdb_id', ''))
        if watch_id:
            watch_url = f"https://vidsrc.to/embed/movie/{watch_id}"
            self.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link, row=0))

        if getattr(movie, 'trailer_url', None):
            self.add_item(discord.ui.Button(label="Watch Trailer 🍿", url=movie.trailer_url, style=discord.ButtonStyle.link, row=0))

        if getattr(movie, 'imdb_id', None):
            imdb_url = f"https://www.imdb.com/title/{movie.imdb_id}/"
            self.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link, row=0))

        if len(results) > 1:
            self.add_item(MovieSelect(results, bot))

        # تحديث حالة الزر فور بناء الكارت إذا كان الفيلم في القائمة
        if is_in_watchlist:
            self.add_to_watchlist_btn.style = discord.ButtonStyle.success
            self.add_to_watchlist_btn.label = "In Watchlist ✅"
            self.add_to_watchlist_btn.disabled = True

    @discord.ui.button(label="Add To Watchlist ⭐", style=discord.ButtonStyle.secondary, custom_id="add_to_watchlist_movie", row=0)
    async def add_to_watchlist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            user_id = interaction.user.id
            tmdb_id = getattr(self.movie, 'tmdb_id', None)
            
            if not tmdb_id:
                button.disabled = False
                await interaction.followup.send("❌ لا يمكن إضافة هذا الفيلم حالياً (بيانات مفقودة).", ephemeral=True)
                return
                
            media_type = "movie"
            media_name = getattr(self.movie, 'title') or getattr(self.movie, 'original_title') or "Unknown"
            poster_url = getattr(self.movie, 'poster_url', None)
            release_date_str = getattr(self.movie, 'release_date', "") or ""
            release_year = release_date_str[:4] if len(release_date_str) >= 4 else "N/A"

            # Check إضافي تحسباً لأي تضارب (Race Condition)
            is_in = await self.bot.services.db.is_in_watchlist(user_id, tmdb_id, media_type)
            if is_in:
                button.style = discord.ButtonStyle.success
                button.label = "In Watchlist ✅"
                button.disabled = True
                await interaction.followup.send("⚠️ هذا الفيلم موجود بالفعل في قائمة المشاهدة الخاصة بك!", ephemeral=True)
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
                await interaction.followup.send("❌ حدث خطأ أثناء إضافة الفيلم، يرجى المحاولة لاحقاً.", ephemeral=True)
                
        finally:
            await interaction.edit_original_response(view=self)


class MovieSelect(discord.ui.Select):
    def __init__(self, results, bot):
        self.bot = bot
        self.results = results
        options = []
        for m in results[:10]:
            title = m.get("original_title") or m.get("title") or "Unknown"
            year = m.get("release_date", "N/A")[:4] if m.get("release_date") else "N/A"
            label = f"{title[:90]} ({year})" 
            
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
        movie_id = int(self.values[0])
        movie = await self.bot.services.tmdb.get_movie_details(movie_id)

        if not movie:
            await interaction.response.send_message("⚠️ حدث خطأ أثناء سحب تفاصيل الفيلم.", ephemeral=True)
            return

        embed = await build_movie_card(movie)
        
        tmdb_id = getattr(movie, 'tmdb_id', movie_id)
        is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "movie")
        view = MovieView(movie, self.results, self.bot, is_in_watchlist)
        
        await interaction.response.edit_message(embed=embed, view=view)


class MovieSearch(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    async def movie_autocomplete(
        self,
        interaction: discord.Interaction,
        current: str
    ) -> list[app_commands.Choice[str]]:
        
        current = current.strip()
        if len(current) < 2:
            return []

        results = await self.bot.services.tmdb.search_movies(current)
        if not results:
            return []

        sorted_results = sorted(
            results,
            key=calculate_search_score,
            reverse=True
        )

        choices = []
        seen_names = set()

        for movie in sorted_results:
            title = movie.get("original_title") or movie.get("title") or "Unknown"
            year = movie.get("release_date", "")[:4] if movie.get("release_date") else "N/A"
            display_name = f"{title} ({year})"

            if display_name not in seen_names:
                choices.append(
                    app_commands.Choice(
                        name=display_name[:100],
                        value=title[:100]
                    )
                )
                seen_names.add(display_name)

            if len(choices) >= 25:
                break

        return choices

    @app_commands.command(name="movie", description="ابحث عن فيلم وشاهد التقييم والتريلر والمشاهدة المباشرة 🍿")
    @app_commands.describe(query="اسم الفيلم المُراد البحث عنه")
    @app_commands.autocomplete(query=movie_autocomplete)
    async def search_movie(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        logger.info("Movie search requested | user_id=%s | query=%s", interaction.user.id, query)

        results = await self.bot.services.tmdb.search_movies(query)
        if not results:
            await interaction.followup.send(f"❌ لم يتم العثور على أي فيلم باسم: `{query}`")
            return

        sorted_results = sorted(results, key=calculate_search_score, reverse=True)
        best_match = sorted_results[0]
        movie_id = best_match.get("id")

        movie = await self.bot.services.tmdb.get_movie_details(movie_id)
        if not movie:
            await interaction.followup.send("⚠️ حدث خطأ أثناء سحب تفاصيل الفيلم من السيرفر.")
            return

        embed = await build_movie_card(movie)
        
        tmdb_id = getattr(movie, 'tmdb_id', movie_id)
        is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "movie")
        view = MovieView(movie, sorted_results, self.bot, is_in_watchlist)

        await interaction.followup.send(embed=embed, view=view)


async def setup(bot):
    await bot.add_cog(MovieSearch(bot))
