import discord
from discord import app_commands
from discord.ext import commands
import datetime
from .general import log_event # نستدعي دالة التسجيل من الملف العام

class Gank(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    @app_commands.command(name="gank-ping", description="Ping all online members and allies for a war.")
    @app_commands.checks.has_any_role(1319063563305746432, 1397797430782853261) # Guild Members & Ally Leaders
    @app_commands.describe(
        enemy_guild="The name of the enemy guild.",
        server_name="The name/number of the server where the gank is."
    )
    async def gank_ping(self, interaction: discord.Interaction, enemy_guild: str, server_name: str):
        
        await interaction.response.send_message("Your gank ping is being prepared...", ephemeral=True)

        # Get the dedicated channel for pings
        ping_channel = self.bot.get_channel(self.config["gank_ping_channel_id"])
        if not ping_channel:
            return await interaction.followup.send("Error: Gank ping channel not found. Please check the config.", ephemeral=True)

        # Roles to ping
        guild_members_role_id = self.config["guild_member_role_id"]
        allies_role_id = self.config["dark_ally_role_id"]

        guild_role = interaction.guild.get_role(guild_members_role_id)
        ally_role = interaction.guild.get_role(allies_role_id)
        
        if not guild_role or not ally_role:
            return await interaction.followup.send("Error: One of the target roles could not be found.", ephemeral=True)

        online_members_to_ping = set()
        
        # --- THIS IS THE MODIFIED PART ---
        # Define statuses that are considered "available"
        # Now includes Do Not Disturb (dnd)
        available_statuses = [discord.Status.online, discord.Status.idle, discord.Status.dnd]
        # ---------------------------------

        # Check members with the guild role
        for member in guild_role.members:
            if member.status in available_statuses:
                online_members_to_ping.add(member)
        
        # Check members with the ally role
        for member in ally_role.members:
            if member.status in available_statuses:
                online_members_to_ping.add(member)

        if not online_members_to_ping:
            await interaction.followup.send("No relevant members are currently available to ping.", ephemeral=True)
            return

        # Split mentions into chunks to avoid exceeding message character limit
        mentions_list = [member.mention for member in online_members_to_ping]
        
        embed = discord.Embed(
            title="⚔️ CALL TO ARMS! ⚔️",
            description=f"All available units are required for an urgent battle!",
            color=discord.Color.red(),
            timestamp=datetime.datetime.now(datetime.timezone.utc)
        )
        embed.add_field(name="Enemy Guild", value=f"`{enemy_guild}`", inline=True)
        embed.add_field(name="Server", value=f"`{server_name}`", inline=True)
        embed.add_field(name="Available Fighters", value=f"**{len(online_members_to_ping)}** members are being pinged.", inline=False)
        embed.set_footer(text=f"Ping requested by {interaction.user.display_name}", icon_url=interaction.user.display_avatar)
        
        # Send mentions and embed to the specified channel
        # We send mentions in chunks of 50 to be safe
        chunk_size = 50
        for i in range(0, len(mentions_list), chunk_size):
            chunk = mentions_list[i:i + chunk_size]
            await ping_channel.send(" ".join(chunk))

        await ping_channel.send(embed=embed)
        
        await interaction.followup.send("✅ Gank Ping has been sent to the dedicated channel!", ephemeral=True)
        
        # Log the event
        log_event("GANK_PING", interaction.user, {
            "enemy_guild": enemy_guild,
            "server": server_name,
            "pinged_count": len(online_members_to_ping)
        })

async def setup(bot: commands.Bot):
    await bot.add_cog(Gank(bot))