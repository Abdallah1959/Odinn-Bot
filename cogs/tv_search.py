# cogs/tv_search.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from utils.ranking import calculate_search_score
from utils.genres import format_genres

logger = logging.getLogger(__name__)

async def build_tv_card(tv):
    overview = getattr(tv, 'overview', None) or "No overview available at the moment."
    if len(overview) > 350:
        overview = overview[:350] + "..."
        
    desc = ""
    arabic_name = getattr(tv, 'name', None)
    original_name = getattr(tv, 'original_name', None)
    
    if arabic_name and original_name and arabic_name.lower() != original_name.lower():
        desc += f"**🌐 {arabic_name}**\n\n"
        
    desc += f"**Story:**\n{overview}"
    
    first_air_date_str = getattr(tv, 'first_air_date', "") or ""
    release_year = first_air_date_str[:4] if len(first_air_date_str) >= 4 else "N/A"
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
    
    first_air_date = getattr(tv, 'first_air_date', None) or "N/A"
    embed.add_field(name="📅 First Air Date", value=f"`{first_air_date}`", inline=True)
    
    seasons = getattr(tv, 'number_of_seasons', 0)
    episodes = getattr(tv, 'number_of_episodes', 0)
    seasons_str = seasons if seasons else "N/A"
    episodes_str = episodes if episodes else "N/A"
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
    def __init__(self, tv, results, bot, is_in_watchlist: bool = False, library_user_id: int = None):
        super().__init__(timeout=300)
        self.tv = tv
        self.bot = bot
        self.results = results
        self.library_user_id = library_user_id  # Multi-user privacy protection
        
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

    @discord.ui.button(label="Add To Watchlist ⭐", style=discord.ButtonStyle.secondary, custom_id="add_to_watchlist_tv", row=0)
    async def add_to_watchlist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.library_user_id and interaction.user.id != self.library_user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            user_id = interaction.user.id
            tmdb_id = getattr(self.tv, 'tmdb_id', None)
            
            if not tmdb_id:
                button.disabled = False
                return await interaction.followup.send("❌ Cannot add this TV show right now (missing data).", ephemeral=True)
                
            media_type = "tv"
            media_name = getattr(self.tv, 'name') or getattr(self.tv, 'original_name') or "Unknown"
            poster_url = getattr(self.tv, 'poster_url', None)
            first_air_date_str = getattr(self.tv, 'first_air_date', "") or ""
            release_year = first_air_date_str[:4] if len(first_air_date_str) >= 4 else "N/A"

            is_in = await self.bot.services.db.is_in_watchlist(user_id, tmdb_id, media_type)
            if is_in:
                button.style = discord.ButtonStyle.success
                button.label = "In Watchlist ✅"
                button.disabled = True  # The crucial fix to prevent spam
                
                self.remove_from_watchlist_btn.style = discord.ButtonStyle.danger
                self.remove_from_watchlist_btn.label = "Remove ❌"
                self.remove_from_watchlist_btn.disabled = False
                return await interaction.followup.send("⚠️ This TV show is already in your watchlist!", ephemeral=True)

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
                await interaction.followup.send("❌ An error occurred while adding the TV show. Please try again.", ephemeral=True)
                
        except Exception:
            logger.exception("Error in add_to_watchlist_btn for user %s", interaction.user.id)
            button.disabled = False
            await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)
        finally:
            await interaction.edit_original_response(view=self)

    @discord.ui.button(label="Remove ❌", style=discord.ButtonStyle.secondary, custom_id="remove_from_watchlist_tv", row=0)
    async def remove_from_watchlist_btn(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.library_user_id and interaction.user.id != self.library_user_id:
            return await interaction.response.send_message("⚠️ This is not your library.", ephemeral=True)

        button.disabled = True
        await interaction.response.edit_message(view=self)
        
        try:
            tmdb_id = getattr(self.tv, 'tmdb_id', None)
            removed = await self.bot.services.db.remove_from_watchlist(interaction.user.id, tmdb_id, "tv")
            
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
                await interaction.followup.send("❌ An error occurred while removing the TV show.", ephemeral=True)
                
        except Exception:
            logger.exception("Error in remove_from_watchlist_btn for user %s", interaction.user.id)
            button.disabled = False
            await interaction.followup.send("❌ An unexpected error occurred.", ephemeral=True)
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
            
            raw_overview = t.get("overview") or "No overview available at the moment."
            desc = raw_overview[:80] + "..." if len(raw_overview) > 80 else raw_overview
            
            options.append(discord.SelectOption(
                label=label,
                description=desc,
                value=str(t.get("id")),
                emoji="📺"
            ))
        super().__init__(placeholder="👀 Did you mean another show? Select here...", options=options, row=1)

    async def callback(self, interaction: discord.Interaction):
        tv_id = int(self.values[0])
        
        tv = await self.bot.services.tmdb.get_tv_details(tv_id)
        if not tv:
            await interaction.response.send_message("⚠️ An error occurred while fetching TV show details.", ephemeral=True)
            return
            
        embed = await build_tv_card(tv)
        
        tmdb_id = getattr(tv, 'tmdb_id', tv_id)
        is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "tv")
        
        lib_user = self.view.library_user_id if hasattr(self.view, 'library_user_id') else None
        view = TVView(tv, self.results, self.bot, is_in_watchlist, library_user_id=lib_user)
        
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

    @app_commands.command(name="tv", description="Search for a TV show 📺")
    @app_commands.describe(query="The name of the TV show to search for")
    @app_commands.autocomplete(query=tv_autocomplete)
    async def search_tv_command(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer(thinking=True)
        logger.info("TV search requested | user_id=%s | query=%s", interaction.user.id, query)
        
        try:
            results = await self.bot.services.tmdb.search_tv(query)
            if not results:
                await interaction.followup.send(f"❌ No TV show found with the name: `{query}`")
                return
                
            sorted_results = sorted(results, key=calculate_search_score, reverse=True)
            
            best_match = sorted_results[0]
            tv_id = best_match.get("id")
            
            tv = await self.bot.services.tmdb.get_tv_details(tv_id)
            if not tv:
                await interaction.followup.send("⚠️ An error occurred while fetching TV show details from the server.")
                return
                
            embed = await build_tv_card(tv)
            
            tmdb_id = getattr(tv, 'tmdb_id', tv_id)
            is_in_watchlist = await self.bot.services.db.is_in_watchlist(interaction.user.id, tmdb_id, "tv")
            view = TVView(tv, sorted_results, self.bot, is_in_watchlist)
            
            await interaction.followup.send(embed=embed, view=view)
        except Exception:
            logger.exception("Error in search_tv_command for query: %s", query)
            await interaction.followup.send("❌ An unexpected error occurred while searching for the TV show.")


async def setup(bot):
    await bot.add_cog(TVSearch(bot))
