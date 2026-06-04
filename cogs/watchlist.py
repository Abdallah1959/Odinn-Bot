# cogs/watchlist.py
import discord
from discord.ext import commands
from discord import app_commands
import logging
from views.watchlist_views import WatchlistHomeView

logger = logging.getLogger(__name__)

class Watchlist(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(name="watchlist", description="View your personal Cinema Library 🍿")
    async def show_watchlist(self, interaction: discord.Interaction):
        # التفكير في الخلفية لضمان عدم حدوث Timeout
        await interaction.response.defer(thinking=True, ephemeral=True) # إضافة Ephemeral هنا أيضاً
        
        user_id = interaction.user.id
        logger.info("Library Dashboard requested | user_id=%s", user_id)

        try:
            movies_count = await self.bot.services.db.count_watchlist_items(user_id, "movie")
            tv_count = await self.bot.services.db.count_watchlist_items(user_id, "tv")
            total_items = movies_count + tv_count

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
            
            view = WatchlistHomeView(self.bot, user_id)

            # إرسال الرسالة كـ Ephemeral (تظهر للمستخدم فقط)
            await interaction.followup.send(embed=embed, view=view, ephemeral=True)

        except Exception:
            logger.exception("Error loading library dashboard")
            await interaction.followup.send("❌ An unexpected error occurred while loading your library.", ephemeral=True)


async def setup(bot):
    await bot.add_cog(Watchlist(bot))
