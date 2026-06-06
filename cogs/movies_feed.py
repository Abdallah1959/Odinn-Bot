import discord
from discord.ext import commands, tasks
from discord import app_commands
import datetime
from zoneinfo import ZoneInfo
import logging
from utils.ranking import calculate_daily_pick_score
from utils.genres import format_genres
from config.settings import settings

logger = logging.getLogger(__name__)

class MoviesFeed(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.channel_id = settings.MOVIES_CHANNEL_ID
        self.daily_pick.start()

    def cog_unload(self):
        self.daily_pick.cancel()

    # ==========================================
    # Testing Command (Temporary)
    # ==========================================
    @app_commands.command(name="testfeed", description="[Admin] Trigger the daily pick manually for testing")
    async def test_feed(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        try:
            await self.daily_pick()
            await interaction.followup.send("✅ Daily Pick Sequence Triggered! Check the channel and Supabase.", ephemeral=True)
        except Exception:
            logger.exception("Error during manual testfeed trigger")
            await interaction.followup.send("❌ An error occurred during the test.", ephemeral=True)

    # ==========================================
    # Main Scheduled Task
    # ==========================================
    @tasks.loop(time=datetime.time(hour=20, minute=0, tzinfo=ZoneInfo("Africa/Cairo")))
    async def daily_pick(self):
        channel = self.bot.get_channel(self.channel_id)
        if not channel:
            logger.error("🚨 Movies channel not found! Check your MOVIES_CHANNEL_ID.")
            return

        popular_movies = await self.bot.services.tmdb.fetch_popular_movies()
        if not popular_movies:
            return

        sorted_movies = sorted(popular_movies, key=calculate_daily_pick_score, reverse=True)

        for raw_movie in sorted_movies:
            movie_id = raw_movie.get("id")
            media_key = f"movie_{movie_id}"

            if await self.bot.services.db.is_posted(media_key):
                continue

            movie = await self.bot.services.tmdb.get_movie_details(movie_id)
            if not movie:
                continue

            overview = getattr(movie, 'overview', None) or "No overview available at the moment."
            if len(overview) > 900:
                overview = overview[:900] + "..."

            release_date_str = getattr(movie, 'release_date', "") or ""
            release_year = release_date_str[:4] if len(release_date_str) >= 4 else "N/A"
            
            movie_name = getattr(movie, 'original_title', None) or getattr(movie, 'title', None) or "Unknown Movie"

            embed = discord.Embed(
                title=f"🎬 {movie_name} ({release_year})",
                description=f"**Story:**\n{overview}",
                color=discord.Color.gold()
            )
            embed.set_author(name="⭐ Movie Pick of the Day")

            if getattr(movie, 'title', None) and getattr(movie, 'original_title', None) and movie.title.lower() != movie.original_title.lower():
                embed.add_field(name="🌐 Regional Title", value=movie.title, inline=False)

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

            embed.set_footer(text="Odinn Cinema Network • Daily Pick 🍿")

            view = discord.ui.View(timeout=None)
            watch_id = getattr(movie, 'imdb_id', None) or str(getattr(movie, 'tmdb_id', ''))
            
            if watch_id:
                watch_url = f"https://vidsrc.to/embed/movie/{watch_id}"
                view.add_item(discord.ui.Button(label="Watch Now 🎬", url=watch_url, style=discord.ButtonStyle.link))

            if getattr(movie, 'trailer_url', None):
                view.add_item(discord.ui.Button(label="Watch Trailer 🍿", url=movie.trailer_url, style=discord.ButtonStyle.link))

            if getattr(movie, 'imdb_id', None):
                imdb_url = f"https://www.imdb.com/title/{movie.imdb_id}/"
                view.add_item(discord.ui.Button(label="IMDb ⭐", url=imdb_url, style=discord.ButtonStyle.link))

            try:
                await channel.send(embed=embed, view=view)
                await self.bot.services.db.mark_as_posted(media_key)
                logger.info("✅ Daily pick posted successfully: %s", movie_name)
                break 
            except Exception:
                logger.exception("Failed to post daily pick %s", movie_name)

    @daily_pick.before_loop
    async def before_daily_pick(self):
        await self.bot.wait_until_ready()

async def setup(bot):
    await bot.add_cog(MoviesFeed(bot))
