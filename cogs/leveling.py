import discord
from discord.ext import commands
import random
import time
from database.db_manager import add_xp, get_user, update_level

class Leveling(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.cooldowns = {} 

        # ==========================================
        # ⚙️ الإعدادات الأساسية للسيرفر (تعديل الـ IDs)
        # ==========================================
        # حط ID روم التهنئة بالأسفل (رقم صحيح)
        self.level_up_channel_id = 1510680410961739967  

        # إعداد مكافآت الرتب التلقائية {رقم المستوى: ID الرتبة}
        self.role_rewards = {
            5: 987654321098765432,   # رتبة مستوى 5
            10: 876543210987654321   # رتبة مستوى 10
        }

    @commands.Cog.listener()
    async def on_ready(self):
        print("⚙️ Leveling Cog is ready and listening to messages!")

    @commands.Cog.listener()
    async def on_message(self, message):
        if message.author.bot or not message.guild:
            return

        user_id = message.author.id
        guild_id = message.guild.id
        current_time = time.time()

        # نظام الـ Cooldown الحقيقي (60 ثانية)
        if user_id in self.cooldowns:
            if current_time - self.cooldowns[user_id] < 60:
                return 

        self.cooldowns[user_id] = current_time

        # توزيع الـ XP العشوائي
        xp_to_add = random.randint(15, 25)
        add_xp(user_id, guild_id, xp_to_add)

        user_data = get_user(user_id, guild_id)
        if user_data:
            current_xp, current_level = user_data
            # دي المعادلة اللي غالباً نسيت تغيرها هنا
            xp_needed = 100 * (current_level + 1) + 50 * (current_level ** 2)

            # التحقق من الارتقاء
            if current_xp >= xp_needed:
                new_level = current_level + 1
                update_level(user_id, guild_id, new_level)

                # منح الرتب التلقائية
                if new_level in self.role_rewards:
                    role_id = self.role_rewards[new_level]
                    role = message.guild.get_role(role_id)
                    if role:
                        try:
                            await message.author.add_roles(role)
                            print(f"✅ Given role {role.name} to {message.author.name}")
                        except discord.Forbidden:
                            print("❌ Missing permissions to assign this role.")

                # إرسال إيمبيد التهنئة في الروم المخصصة
                level_channel = self.bot.get_channel(self.level_up_channel_id)
                if level_channel:
                    embed = discord.Embed(
                        title="🎉 ارتقاء في التصنيف!",
                        description=f"أسطورة جديدة تُولد! {message.author.mention} وصل للمستوى **{new_level}** ⚔️",
                        color=discord.Color.gold()
                    )
                    if message.author.display_avatar:
                        embed.set_thumbnail(url=message.author.display_avatar.url)
                    
                    await level_channel.send(content=f"{message.author.mention}", embed=embed)

    @commands.command(name="level", help="بيعرض الـ XP والمستوى الحالي")
    async def level(self, ctx, member: discord.Member = None):
        member = member or ctx.author
        user_data = get_user(member.id, ctx.guild.id)
        
        if not user_data:
            await ctx.send(f"⚠️ {member.mention} لسه معندوش أي XP في سيرفر أودين!")
            return
            
        current_xp, current_level = user_data
        xp_needed = 100 * (current_level + 1) + 50 * (current_level ** 2)
        
        embed = discord.Embed(
            title=f"⚔️ إحصائيات المحارب | {member.display_name}", 
            color=discord.Color.dark_theme() 
        )
        if member.display_avatar:
            embed.set_thumbnail(url=member.display_avatar.url)
            
        embed.add_field(name="🛡️ المستوى (Level)", value=f"**{current_level}**", inline=True)
        embed.add_field(name="✨ نقاط الخبرة (XP)", value=f"**{current_xp} / {xp_needed}**", inline=True)
        
        progress = int((current_xp / xp_needed) * 10)
        progress_bar = ("🟩" * progress) + ("⬛" * (10 - progress))
        embed.add_field(name="التقدم للمستوى القادم", value=progress_bar, inline=False)
        
        await ctx.send(embed=embed)

async def setup(bot):
    await bot.add_cog(Leveling(bot))
