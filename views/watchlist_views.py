import discord
import logging

logger = logging.getLogger(__name__)

# 1. زر الرجوع الموحد
class BackToLibraryButton(discord.ui.Button):
    def __init__(self, bot, user_id: int):
        super().__init__(label="🔙 Back to Library", style=discord.ButtonStyle.secondary, custom_id="back_to_lib_home", row=2)
        self.bot = bot
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        try:
            watchlist_items = await self.bot.services.db.get_watchlist(self.user_id)
            total_items = len(watchlist_items)
            movies_count = sum(1 for item in watchlist_items if item.get("media_type") == "movie")
            tv_count = total_items - movies_count

            embed = discord.Embed(
                title="📚 Your Cinema Library",
                description="**━━━━━━━━━━━━━━**\nChoose a category below to browse your saved items.",
                color=discord.Color.from_rgb(229, 9, 20)
            )
            embed.set_author(name=f"{interaction.user.display_name}'s Library", icon_url=interaction.user.display_avatar.url)
            
            embed.add_field(
                name="📊 Statistics", 
                value=(
                    f"🎬 Movies: **{movies_count}**\n"
                    f"📺 TV Shows: **{tv_count}**\n\n"
                    f"📦 Total Items: **{total_items}**\n"
                    f"**━━━━━━━━━━━━━━**"
                ), 
                inline=False
            )
            
            await interaction.response.edit_message(embed=embed, view=WatchlistHomeView(self.bot, self.user_id))
            
        except Exception:
            logger.exception("Error in BackToLibraryButton callback")
            await interaction.response.send_message("❌ An unexpected error occurred while returning to the library.", ephemeral=True)


# 2. Dropdown اختيار الأفلام
class LibraryMovieSelect(discord.ui.Select):
    def __init__(self, bot, user_id, movies):
        self.bot = bot
        self.user_id = user_id
        options = []
        for item in movies[:10]:
            title = item.get("media_name", "Unknown")
            year = item.get("release_year", "N/A")
            tmdb_id = str(item.get("tmdb_id"))
            
            options.append(discord.SelectOption(
                label=f"{title[:90]} ({year})",
                value=tmdb_id,
                emoji="🎬"
            ))
        super().__init__(placeholder="Select a movie to view details...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)
        
        await interaction.response.defer()
        
        try:
            from cogs.movie_search import build_movie_card, MovieView
            tmdb_id = int(self.values[0])
            movie = await self.bot.services.tmdb.get_movie_details(tmdb_id)
            if not movie:
                return await interaction.followup.send("❌ Error fetching movie details from TMDB.", ephemeral=True)
                
            embed = await build_movie_card(movie)
            # تم التعديل: نمرر library_user_id ليعرف الكارت أنه مفتوح من المكتبة
            view = MovieView(movie, [movie], self.bot, is_in_watchlist=True, library_user_id=self.user_id)
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception:
            logger.exception("Error in LibraryMovieSelect callback")
            await interaction.followup.send("❌ An unexpected error occurred while loading the movie.", ephemeral=True)


# 3. Dropdown اختيار المسلسلات
class LibraryTVSelect(discord.ui.Select):
    def __init__(self, bot, user_id, tv_shows):
        self.bot = bot
        self.user_id = user_id
        options = []
        for item in tv_shows[:10]:
            name = item.get("media_name", "Unknown")
            year = item.get("release_year", "N/A")
            tmdb_id = str(item.get("tmdb_id"))
            
            options.append(discord.SelectOption(
                label=f"{name[:90]} ({year})",
                value=tmdb_id,
                emoji="📺"
            ))
        super().__init__(placeholder="Select a TV show to view details...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)
        
        await interaction.response.defer()
        
        try:
            from cogs.tv_search import build_tv_card, TVView
            tmdb_id = int(self.values[0])
            tv = await self.bot.services.tmdb.get_tv_details(tmdb_id)
            if not tv:
                return await interaction.followup.send("❌ Error fetching TV show details from TMDB.", ephemeral=True)
                
            embed = await build_tv_card(tv)
            # تم التعديل: نمرر library_user_id
            view = TVView(tv, [tv], self.bot, is_in_watchlist=True, library_user_id=self.user_id)
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception:
            logger.exception("Error in LibraryTVSelect callback")
            await interaction.followup.send("❌ An unexpected error occurred while loading the TV show.", ephemeral=True)


# 4. View مكتبة الأفلام
class MoviesLibraryView(discord.ui.View):
    def __init__(self, bot, user_id: int, movies: list):
        super().__init__(timeout=300)
        self.add_item(LibraryMovieSelect(bot, user_id, movies))
        self.add_item(BackToLibraryButton(bot, user_id))


# 5. View مكتبة المسلسلات
class TVLibraryView(discord.ui.View):
    def __init__(self, bot, user_id: int, tv_shows: list):
        super().__init__(timeout=300)
        self.add_item(LibraryTVSelect(bot, user_id, tv_shows))
        self.add_item(BackToLibraryButton(bot, user_id))


# 6. الـ Dashboard الرئيسية
class WatchlistHomeView(discord.ui.View):
    def __init__(self, bot, user_id: int):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id

    async def _build_media_library(self, interaction: discord.Interaction, media_type: str):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)
            
        is_movie = (media_type == "movie")
        title = "🎬 Movies Library" if is_movie else "📺 TV Shows Library"
        item_name = "movie" if is_movie else "TV show"
        item_name_plural = "movies" if is_movie else "TV shows"
        view_class = MoviesLibraryView if is_movie else TVLibraryView
            
        try:
            watchlist_items = await self.bot.services.db.get_watchlist(self.user_id)
            items = [item for item in watchlist_items if item.get("media_type") == media_type]
            
            if not items:
                embed = discord.Embed(
                    title=title,
                    description=f"Your {item_name_plural} library is empty! Go search and add some {item_name_plural}. 🍿",
                    color=discord.Color.from_rgb(229, 9, 20)
                )
                embed.set_author(name=f"{interaction.user.display_name}'s Library", icon_url=interaction.user.display_avatar.url)
                empty_view = discord.ui.View(timeout=300)
                empty_view.add_item(BackToLibraryButton(self.bot, self.user_id))
                return await interaction.response.edit_message(embed=embed, view=empty_view)

            total_items = len(items)
            showing_count = min(10, total_items)
            
            description_text = f"Select a {item_name} from the menu below to view details.\n\n*Showing {showing_count} of {total_items} {item_name_plural}*"
            if total_items > 10:
                description_text += " *(Pagination coming soon) 🚀*"
                
            embed = discord.Embed(
                title=title,
                description=description_text,
                color=discord.Color.from_rgb(229, 9, 20)
            )
            embed.set_author(name=f"{interaction.user.display_name}'s Library", icon_url=interaction.user.display_avatar.url)
            
            await interaction.response.edit_message(embed=embed, view=view_class(self.bot, self.user_id, items))
            
        except Exception:
            logger.exception(f"Error loading {item_name_plural} library")
            await interaction.response.send_message(f"❌ An unexpected error occurred while loading your {item_name_plural}.", ephemeral=True)

    @discord.ui.button(label="🎬 Movies", style=discord.ButtonStyle.primary, custom_id="lib_movies_btn")
    async def movies_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._build_media_library(interaction, "movie")

    @discord.ui.button(label="📺 TV Shows", style=discord.ButtonStyle.secondary, custom_id="lib_tv_btn")
    async def tv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._build_media_library(interaction, "tv")
