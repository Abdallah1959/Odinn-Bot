# views/watchlist_views.py
import discord
import logging
import math

logger = logging.getLogger(__name__)

# ==========================================
# 1. Pagination Foundation (V3)
# ==========================================

class PaginationState:
    """Manages pagination state with defensive clamping and slicing logic"""
    def __init__(self, items: list, page: int = 0, per_page: int = 10):
        self.items = items
        self.per_page = per_page
        
        # Defensive Programming: Calculate total pages first to clamp page safely
        total_p = max(1, math.ceil(len(self.items) / self.per_page))
        self.page = max(0, min(page, total_p - 1))

    @property
    def total_pages(self) -> int:
        return max(1, math.ceil(len(self.items) / self.per_page))

    @property
    def current_page(self) -> int:
        return self.page + 1

    @property
    def has_next(self) -> bool:
        return self.page < self.total_pages - 1

    @property
    def has_previous(self) -> bool:
        return self.page > 0

    def get_current_items(self) -> list:
        start = self.page * self.per_page
        end = start + self.per_page
        return self.items[start:end]


class PaginationControls(discord.ui.View):
    """Base View with dynamic button states and Context-Awareness"""
    def __init__(self, bot, user_id: int, state: PaginationState, media_type: str):
        super().__init__(timeout=300)
        self.bot = bot
        self.user_id = user_id
        self.state = state
        self.media_type = media_type

        # ◀️ Previous Button
        self.prev_btn = discord.ui.Button(
            label="◀️ Previous",
            style=discord.ButtonStyle.secondary,
            custom_id="page_prev",
            row=1,
            disabled=not self.state.has_previous
        )
        self.prev_btn.callback = self.prev_callback
        self.add_item(self.prev_btn)

        # Page Indicator (Dummy Button)
        self.indicator_btn = discord.ui.Button(
            label=f"Page {self.state.current_page}/{self.state.total_pages}",
            style=discord.ButtonStyle.secondary,
            custom_id="page_indicator",
            row=1,
            disabled=True
        )
        self.add_item(self.indicator_btn)

        # ▶️ Next Button
        self.next_btn = discord.ui.Button(
            label="▶️ Next",
            style=discord.ButtonStyle.secondary,
            custom_id="page_next",
            row=1,
            disabled=not self.state.has_next
        )
        self.next_btn.callback = self.next_callback
        self.add_item(self.next_btn)

    async def _update_page(self, interaction: discord.Interaction, new_page: int):
        """Helper method to handle the common logic for both Next and Previous"""
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        if not interaction.response.is_done():
            await interaction.response.defer()

        new_state = PaginationState(
            items=self.state.items,
            page=new_page,
            per_page=self.state.per_page
        )

        is_movie = (self.media_type == "movie")
        title = "🎬 Movies Library" if is_movie else "📺 TV Shows Library"
        item_name = "movie" if is_movie else "TV show"

        total_items = len(new_state.items)
        start_idx = new_state.page * new_state.per_page + 1
        end_idx = min((new_state.page + 1) * new_state.per_page, total_items)

        description_text = (
            f"Select a {item_name} from the menu below to view details.\n\n"
            f"*Showing items {start_idx} to {end_idx} of {total_items}*\n"
            f"*Page {new_state.current_page} of {new_state.total_pages}*"
        )

        embed = discord.Embed(
            title=title,
            description=description_text,
            color=discord.Color.from_rgb(229, 9, 20)
        )
        embed.set_author(name=f"{interaction.user.display_name}'s Library", icon_url=interaction.user.display_avatar.url)

        if self.media_type == "movie":
            new_view = MoviesLibraryView(self.bot, self.user_id, new_state)
        else:
            new_view = TVLibraryView(self.bot, self.user_id, new_state)

        await interaction.edit_original_response(embed=embed, view=new_view)

    async def prev_callback(self, interaction: discord.Interaction):
        if not self.state.has_previous:
            return
        await self._update_page(interaction, self.state.page - 1)

    async def next_callback(self, interaction: discord.Interaction):
        if not self.state.has_next:
            return
        await self._update_page(interaction, self.state.page + 1)


# ==========================================
# 2. Shared Components
# ==========================================

class BackToLibraryButton(discord.ui.Button):
    def __init__(self, bot, user_id: int):
        super().__init__(label="🔙 Back to Library", style=discord.ButtonStyle.secondary, custom_id="back_to_lib_home", row=2)
        self.bot = bot
        self.user_id = user_id

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        try:
            # TODO: Implement in-memory stats caching within the main view context 
            # to prevent redundant Supabase queries during back-navigation.
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
            
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=WatchlistHomeView(self.bot, self.user_id))
            else:
                await interaction.edit_original_response(embed=embed, view=WatchlistHomeView(self.bot, self.user_id))
            
        except Exception:
            logger.exception("Error in BackToLibraryButton callback")
            await interaction.followup.send("❌ An unexpected error occurred while returning to the library.", ephemeral=True)


# ==========================================
# 3. Media Select Dropdowns
# ==========================================

class LibraryMovieSelect(discord.ui.Select):
    def __init__(self, bot, user_id: int, state: PaginationState):
        self.bot = bot
        self.user_id = user_id
        self.state = state
        
        options = []
        current_items = self.state.get_current_items()
        
        for item in current_items:
            title = item.get("media_name", "Unknown")
            year = item.get("release_year", "N/A")
            tmdb_id = str(item.get("tmdb_id"))
            
            # Defensive Slicing: Keep title at max 80 chars to safely stay below Discord's 100-char limit
            options.append(discord.SelectOption(
                label=f"{title[:80]} ({year})",
                value=tmdb_id,
                emoji="🎬"
            ))
        super().__init__(placeholder="Select a movie to view details...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)
        
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        try:
            from cogs.movie_search import build_movie_card, MovieView
            tmdb_id = int(self.values[0])
            movie = await self.bot.services.tmdb.get_movie_details(tmdb_id)
            
            if not movie:
                return await interaction.followup.send("❌ Error fetching movie details from TMDB.", ephemeral=True)
                
            embed = await build_movie_card(movie)
            view = MovieView(movie, [movie], self.bot, is_in_watchlist=True, library_user_id=self.user_id)
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception:
            logger.exception("Error in LibraryMovieSelect callback")
            await interaction.followup.send("❌ An unexpected error occurred while loading the movie.", ephemeral=True)


class LibraryTVSelect(discord.ui.Select):
    def __init__(self, bot, user_id: int, state: PaginationState):
        self.bot = bot
        self.user_id = user_id
        self.state = state
        
        options = []
        current_items = self.state.get_current_items()
        
        for item in current_items:
            name = item.get("media_name", "Unknown")
            year = item.get("release_year", "N/A")
            tmdb_id = str(item.get("tmdb_id"))
            
            # Defensive Slicing: Keep title at max 80 chars to safely stay below Discord's 100-char limit
            options.append(discord.SelectOption(
                label=f"{name[:80]} ({year})",
                value=tmdb_id,
                emoji="📺"
            ))
        super().__init__(placeholder="Select a TV show to view details...", options=options, row=0)

    async def callback(self, interaction: discord.Interaction):
        if interaction.user.id != self.user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)
        
        if not interaction.response.is_done():
            await interaction.response.defer()
            
        try:
            from cogs.tv_search import build_tv_card, TVView
            tmdb_id = int(self.values[0])
            tv = await self.bot.services.tmdb.get_tv_details(tmdb_id)  # Fix: Using tmdb_id safely
            
            if not tv:
                return await interaction.followup.send("❌ Error fetching TV show details from TMDB.", ephemeral=True)
                
            embed = await build_tv_card(tv)
            view = TVView(tv, [tv], self.bot, is_in_watchlist=True, library_user_id=self.user_id)
            await interaction.edit_original_response(embed=embed, view=view)
            
        except Exception:
            logger.exception("Error in LibraryTVSelect callback")
            await interaction.followup.send("❌ An unexpected error occurred while loading the TV show.", ephemeral=True)


# ==========================================
# 4. Library Views (Inheriting from Pagination)
# ==========================================

class MoviesLibraryView(PaginationControls):
    def __init__(self, bot, user_id: int, state: PaginationState):
        super().__init__(bot, user_id, state, media_type="movie")
        self.add_item(LibraryMovieSelect(bot, user_id, state))
        self.add_item(BackToLibraryButton(bot, user_id))


class TVLibraryView(PaginationControls):
    def __init__(self, bot, user_id: int, state: PaginationState):
        super().__init__(bot, user_id, state, media_type="tv")
        self.add_item(LibraryTVSelect(bot, user_id, state))
        self.add_item(BackToLibraryButton(bot, user_id))


# ==========================================
# 5. Main Library Dashboard
# ==========================================

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
                
                if not interaction.response.is_done():
                    return await interaction.response.edit_message(embed=embed, view=empty_view)
                else:
                    return await interaction.edit_original_response(embed=embed, view=empty_view)

            state = PaginationState(items=items, page=0, per_page=10)
            
            total_items = len(items)
            start_idx = 1
            end_idx = min(state.per_page, total_items)
            
            description_text = (
                f"Select a {item_name} from the menu below to view details.\n\n"
                f"*Showing items {start_idx} to {end_idx} of {total_items}*\n"
                f"*Page {state.current_page} of {state.total_pages}*"
            )
                
            embed = discord.Embed(
                title=title,
                description=description_text,
                color=discord.Color.from_rgb(229, 9, 20)
            )
            embed.set_author(name=f"{interaction.user.display_name}'s Library", icon_url=interaction.user.display_avatar.url)
            
            if not interaction.response.is_done():
                await interaction.response.edit_message(embed=embed, view=view_class(self.bot, self.user_id, state))
            else:
                await interaction.edit_original_response(embed=embed, view=view_class(self.bot, self.user_id, state))
            
        except Exception:
            logger.exception("Error loading %s library", item_name_plural)
            await interaction.followup.send(f"❌ An unexpected error occurred while loading your {item_name_plural}.", ephemeral=True)

    @discord.ui.button(label="🎬 Movies", style=discord.ButtonStyle.primary, custom_id="lib_movies_btn")
    async def movies_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._build_media_library(interaction, "movie")

    @discord.ui.button(label="📺 TV Shows", style=discord.ButtonStyle.secondary, custom_id="lib_tv_btn")
    async def tv_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self._build_media_library(interaction, "tv")
