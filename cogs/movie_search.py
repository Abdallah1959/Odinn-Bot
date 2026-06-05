# cogs/movie_search.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres

logger = logging.getLogger(__name__)

async def build_movie_card(movie):
    overview = getattr(movie, 'overview', None) or "No overview available at the moment."
    if len(overview) > 350:
        overview = overview[:350] + "..."

    desc = ""
    arabic_title = getattr(movie, 'title', None)
    original_title = getattr(movie, 'original_title', None)

    if arabic_title and original_title and arabic_title.lower() != original_title.lower():
        desc += f"**🌐 {arabic_title}**\n\n"

    desc += f"**Story:**\n{overview}"

    release_date_str = getattr(movie, 'release_date', "") or ""
    release_year = release_date_str[:4] if len(release_date_str) >= 4 else "N/A"
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

    release_date = getattr(movie, 'release_date', None) or "N/A"
    embed.add_field(name="📅 Release Date", value=f"`{release_date}`", inline=True)

    runtime_raw = getattr(movie, 'runtime', None)
    runtime_str = f"{runtime_raw} min" if runtime_raw else "N/A"
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
    def __init__(self, movie, results, bot, is_in_watchlist: bool = False, library_user_id: int = None):
        super().__init__(timeout=300)
        self.movie = movie
        self.bot = bot
        self.results = results
        self.library_user_id = library_user_id  # Multi-user privacy protection
        
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

        # Layout Shift-Free state management
        if is_in_watchlist:
            self.add_to_watchlist_btn.style = discord.ButtonStyle.success
            self.add_to_watchlist_btn.label = "In Watchlist ✅"
            self.add_to_watchlist_btn.disabled = True
            
            self.remove_from_watchlist_btn.style = discord.ButtonStyle.danger
            self.remove_from_watchlist_btn.label = "Remove ❌"
            self.remove_from_watchlist_btn.disabled = False
        else:
            self.remove_from_watchlist_btn.style = discord.ButtonStyle.secondary
            self.remove_from_watchlist_btn.label = "Remove ❌"
            self.remove_from_watchlist_btn.disabled = True

        if library_user_id:
            from views.watchlist_views import BackToLibraryButton
            self.add_item(BackToLibraryButton(bot, library_user_id))

    @discord.ui.button(label="Add To Watchlist ⭐", style=discord.ButtonStyle.secondary, custom_id="add_to_watchlist_movie", row=0)
    async def add_to_watchlist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.library_user_id and interaction.user.id != self.library_user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            user_id = interaction.user.id
            tmdb_id = getattr(self.movie, 'tmdb_id', None)
            
            if not tmdb_id:
                button.disabled = False
                return await interaction.followup.send("❌ Cannot add this movie right now (missing data).", ephemeral=True)
                
            media_type = "movie"
            media_name = getattr(self.movie, 'title') or getattr(self.movie, 'original_title') or "Unknown"
            poster_url = getattr(self.movie, 'poster_url', None)
            release_date_str = getattr(self.movie, 'release_date', "") or ""
            release_year = release_date_str[:4] if len(release_date_str) >= 4 else "N/A"

            is_in = await self.bot.services.db.is_in_watchlist(user_id, tmdb_id, media_type)
            if is_in:
                button.style = discord.ButtonStyle.success
                button.label = "In Watchlist ✅"
                button.disabled = True  # <--- اللمسة السحرية لمنع الـ Spam
                
                self.remove_from_watchlist_btn.style = discord.ButtonStyle.danger
                self.remove_from_watchlist_btn.label = "Remove ❌"
                self.remove_from_watchlist_btn.disabled = False
                return await interaction.followup.send("⚠️ This movie is already in your watchlist!", ephemeral=True)

            added = await self.bot.services.db.add_to_watchlist(
                user_id=user_id, tmdb_id=tmdb_id, media_type=media_type,
                media_name=media_name, poster_url=poster_url, release_year=release_year
            )
            
            if added:
                button.style = discord.ButtonStyle.success
                button.label = "In Watchlist ✅"
                button.disabled = True
                
                # Active Reset for Remove Button
                self.remove_from_watchlist_btn.style = discord.ButtonStyle.danger
                self.remove_from_watchlist_btn.label = "Remove ❌"
                self.remove_from_watchlist_btn.disabled = False
                
                await interaction.followup.send(f"✅ Added **{media_name}** to your watchlist.", ephemeral=True)
            else:
                button.disabled = False
                await interaction.followup.send("❌ An error occurred while adding the movie. Please try again.", ephemeral=True)
                
        except Exception:
            logger.exception("Error in add_to_watchlist_btn for user %s", interaction.user.id)
            button.disabled = False
            await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)
        finally:
            await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Remove ❌", style=discord.ButtonStyle.secondary, custom_id="remove_from_watchlist_movie", row=0)
    async def remove_from_watchlist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.library_user_id and interaction.user.id != self.library_user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            tmdb_id = getattr(self.movie, 'tmdb_id', None)
            removed = await self.bot.services.db.remove_from_watchlist(interaction.user.id, tmdb_id, "movie")
            
            if removed:
                # Toggle States Smoothly
                self.add_to_watchlist_btn.style = discord.ButtonStyle.secondary
                self.add_to_watchlist_btn.label = "Add To Watchlist ⭐"
                self.add_to_watchlist_btn.disabled = False
                
                button.style = discord.ButtonStyle.secondary
                button.label = "Removed ✅"
                button.disabled = True
                
                await interaction.followup.send("✅ Removed successfully from your watchlist.", ephemeral=True)
            else:
                button.disabled = False
                await interaction.followup.send("❌ An error occurred while removing the movie.", ephemeral=True)
                
        except Exception:
            logger.exception("Error in remove_from_watchlist_btn for user %s", interaction.user.id)
            button.disabled = False
            await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)
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
            
            raw_overview = m.get("overview") or "No overview available at the moment."
            desc = raw_overview[:80] + "..." if len(raw_overview) > 80 else raw_overview
            
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(m.get("id")),
                emoji="🎬"
            ))
        super().__init__(placeholder="👀 Did you mean another version? Select here...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        movie_id = int(self.values[0])
        movie = await self.bot.services.tmdb.get_movie_details(movie_id)

        if not movie:
            await interaction.response.send_message("⚠️ An error occurred while fetching movie details.", ephemeral=True)
            return

        embed = await build_movie_card(movie)
        
        tmdb_id = getattr(movie, 'tmdb_id', movie_id)
        is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "movie")
        
        lib_user = self.view.library_user_id if hasattr(self.view, 'library_user_id') else None
        view = MovieView(movie, self.results, self.bot, is_in_watchlist, library_user_id=lib_user)
        
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

    @app_commands.command(name="movie", description="Search for a movie, view its rating, trailer, and watch it 🍿")
    @app_commands.describe(query="The name of the movie to search for")
    @app_commands.autocomplete(query=movie_autocomplete)
    async def search_movie(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        logger.info("Movie search requested | user_id=%s | query=%s", interaction.user.id, query)

        try:
            results = await self.bot.services.tmdb.search_movies(query)
            if not results:
                await interaction.followup.send(f"❌ No movie found with the name: `{query}`")
                return

            sorted_results = sorted(results, key=calculate_search_score, reverse=True)
            best_match = sorted_results[0]
            movie_id = best_match.get("id")

            movie = await self.bot.services.tmdb.get_movie_details(movie_id)
            if not movie:
                await interaction.followup.send("⚠️ An error occurred while fetching movie details from the server.")
                return

            embed = await build_movie_card(movie)
            
            tmdb_id = getattr(movie, 'tmdb_id', movie_id)
            is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "movie")
            view = MovieView(movie, sorted_results, self.bot, is_in_watchlist)

            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            logger.exception("Error in search_movie command for query: %s", query)
            await interaction.followup.send("❌ An unexpected error occurred while searching for the movie.")


async def setup(bot):
    await bot.add_cog(MovieSearch(bot))
