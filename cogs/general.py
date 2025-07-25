import discord
from discord import app_commands
from discord.ext import commands
import datetime
import json
import os

LOG_FILE = 'data/audit_log.json'

def log_event(event_type: str, user: discord.Member, details: dict):
    """A centralized function to log events to a JSON file."""
    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        logs = []
    else:
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            try:
                logs = json.load(f)
            except json.JSONDecodeError:
                logs = [] # If file is corrupted or empty

    log_entry = {
        "event_type": event_type,
        "user_id": user.id,
        "user_name": user.name,
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "details": details
    }
    logs.insert(0, log_entry)
    
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, indent=4, ensure_ascii=False)


class General(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    def is_admin(self, interaction: discord.Interaction) -> bool:
        admin_ids = set(self.config["admin_role_ids"])
        user_role_ids = {role.id for role in interaction.user.roles}
        return not admin_ids.isdisjoint(user_role_ids)

    @app_commands.command(name="announce", description="[ADMIN] Post a formatted announcement.")
    @app_commands.describe(title="The title of the announcement.", message="The main content (use '\\n' for new lines).")
    async def announce(self, interaction: discord.Interaction, title: str, message: str):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        target_channel = self.bot.get_channel(self.config["announcement_channel_id"])
        mention_role = interaction.guild.get_role(self.config["guild_member_role_id"])
        if not target_channel or not mention_role: return await interaction.followup.send("Error: Could not find announcement channel or role.")
        
        embed = discord.Embed(title=f"📣 {title}", description=message.replace("\\n", "\n"), color=discord.Color.gold(), timestamp=datetime.datetime.now())
        embed.set_footer(text=f"Announcement by {interaction.user.display_name}", icon_url=interaction.user.display_avatar)
        
        await target_channel.send(content=mention_role.mention, embed=embed)
        await interaction.followup.send("✅ Announcement has been posted successfully!")
        log_event("ANNOUNCEMENT", interaction.user, {"title": title})

    @app_commands.command(name="view-logs", description="[ADMIN] View the recent activity logs.")
    @app_commands.describe(event_type="Optional: Filter by event type (e.g., PROMOTION).")
    async def view_logs(self, interaction: discord.Interaction, event_type: str = None):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)

        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            return await interaction.followup.send("Log file is empty.")

        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            logs = json.load(f)

        if event_type:
            logs = [log for log in logs if log['event_type'].lower() == event_type.lower()]

        if not logs:
            return await interaction.followup.send(f"No logs found for event type: `{event_type}`.")

        embed = discord.Embed(title="📜 Audit Log", description="Showing the last 10 entries.", color=discord.Color.light_grey())
        
        for log in logs[:10]:
            timestamp_dt = datetime.datetime.fromisoformat(log['timestamp'])
            details_str = ", ".join([f"**{k}**: {v}" for k, v in log['details'].items()])
            field_name = f"🔹 {log['event_type']} by {log['user_name']}"
            field_value = f"<t:{int(timestamp_dt.timestamp())}:R>\n**Details:** {details_str}"
            embed.add_field(name=field_name, value=field_value, inline=False)
            
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="help", description="Shows a list of all available bot commands.")
    async def help(self, interaction: discord.Interaction):
        await interaction.response.defer(ephemeral=True)
        embed = discord.Embed(title="🤖 Bot Commands Guide", color=discord.Color.purple())
        
        # Updated help text
        admin_commands = "`/announce`, `/promote`, `/demote`, `/view-logs`"
        gank_commands = "`/gank-ping`: Calls available members to a war."
        alliance_commands = "`/admin-add-guild`, `/admin-remove-guild`, `/admin-add-solo-ally`, `/admin-remove-solo-ally`, `/ally-add-member`, `/ally-remove-member`, `/view-ally-guild`"
        tournament_commands = "`/solo-tournament-start`, `/tournament-winner`, `/tournament-status`, `/tournament-end`"
        public_commands = "`/alliance-leaderboard`, `/help`"
    
        embed.add_field(name="👑 Admin Commands", value=admin_commands, inline=False)
        embed.add_field(name="💥 Gank Commands", value=gank_commands, inline=False)
        embed.add_field(name="🤝 Alliance Management", value=alliance_commands, inline=False)
        embed.add_field(name="⚔️ Tournament", value=tournament_commands, inline=False)
        embed.add_field(name="🌍 Public", value=public_commands, inline=False)
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(General(bot))