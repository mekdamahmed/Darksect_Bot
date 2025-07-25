import discord
from discord import app_commands
from discord.ext import commands
from .general import log_event
import datetime

class Alliance(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    # --- HELPER FUNCTIONS ---
    def is_admin(self, interaction: discord.Interaction) -> bool:
        admin_ids = set(self.config["admin_role_ids"])
        user_role_ids = {role.id for role in interaction.user.roles}
        return not admin_ids.isdisjoint(user_role_ids)

    async def get_role(self, guild: discord.Guild, role_id: int) -> discord.Role:
        role = guild.get_role(role_id)
        if role is None: raise commands.CommandError(f"Role with ID {role_id} not found.")
        return role

    async def get_leader_guild_role(self, leader: discord.Member) -> discord.Role:
        known_ids = set(val for val in self.config.values() if isinstance(val, int)) | set(self.config["rank_hierarchy"])
        for role in leader.roles:
            if role.id not in known_ids and not role.is_default():
                return role
        return None

    # --- GUILD ALLIANCE COMMANDS ---
    @app_commands.command(name="admin-add-guild", description="[ADMIN] Add a new allied guild and set its leader.")
    @app_commands.describe(leader="The leader of the new allied guild.", guild_name="The name of the new guild.")
    async def admin_add_guild(self, interaction: discord.Interaction, leader: discord.Member, guild_name: str):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        if discord.utils.get(interaction.guild.roles, name=guild_name): return await interaction.followup.send(f"A guild role named `{guild_name}` already exists.")
        
        ally_leader_role = await self.get_role(interaction.guild, self.config["ally_leader_role_id"])
        new_guild_role = await interaction.guild.create_role(name=guild_name)
        await leader.add_roles(ally_leader_role, new_guild_role)
        
        embed = discord.Embed(title="✅ Alliance Formed", description=f"The guild `{guild_name}` is now an ally.", color=discord.Color.green())
        await interaction.followup.send(embed=embed)
        log_event("ALLIANCE_GUILD_ADD", interaction.user, {"guild_name": guild_name, "leader": leader.name})

    @app_commands.command(name="admin-remove-guild", description="[ADMIN] Disband an alliance with a guild.")
    @app_commands.describe(guild_role="The role of the guild to remove.")
    async def admin_remove_guild(self, interaction: discord.Interaction, guild_role: discord.Role):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        
        ally_leader_role = await self.get_role(interaction.guild, self.config["ally_leader_role_id"])
        dark_ally_role = await self.get_role(interaction.guild, self.config["dark_ally_role_id"])
        
        member_count = len(guild_role.members)
        for member in list(guild_role.members):
            await member.remove_roles(guild_role, ally_leader_role, dark_ally_role, reason="Alliance disbanded")
        
        await guild_role.delete(reason=f"Alliance disbanded by {interaction.user}")
        embed = discord.Embed(title="🗑️ Alliance Disbanded", description=f"The alliance with `{guild_role.name}` has been dissolved. Roles removed from {member_count} members.", color=discord.Color.red())
        await interaction.followup.send(embed=embed)
        log_event("ALLIANCE_GUILD_REMOVE", interaction.user, {"guild_name": guild_role.name})

    # --- SOLO ALLY COMMANDS ---
    @app_commands.command(name="admin-add-solo-ally", description="[ADMIN] Add a member as a solo ally.")
    @app_commands.describe(user="The user to add as a solo ally.")
    async def admin_add_solo_ally(self, interaction: discord.Interaction, user: discord.Member):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        dark_ally_role = await self.get_role(interaction.guild, self.config["dark_ally_role_id"])
        solo_ally_role = await self.get_role(interaction.guild, self.config["solo_ally_role_id"])
        await user.add_roles(dark_ally_role, solo_ally_role)
        embed = discord.Embed(title="👤 Solo Ally Added", description=f"{user.mention} has been added as a solo ally.", color=discord.Color.green())
        await interaction.followup.send(embed=embed)
        log_event("SOLO_ALLY_ADD", interaction.user, {"member": user.name})

    @app_commands.command(name="admin-remove-solo-ally", description="[ADMIN] Remove a member from solo allies.")
    @app_commands.describe(user="The solo ally to remove.")
    async def admin_remove_solo_ally(self, interaction: discord.Interaction, user: discord.Member):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        dark_ally_role = await self.get_role(interaction.guild, self.config["dark_ally_role_id"])
        solo_ally_role = await self.get_role(interaction.guild, self.config["solo_ally_role_id"])
        if solo_ally_role not in user.roles: return await interaction.followup.send("This user is not a solo ally.")
        await user.remove_roles(dark_ally_role, solo_ally_role)
        embed = discord.Embed(title="🗑️ Solo Ally Removed", description=f"{user.mention} has been removed from solo allies.", color=discord.Color.red())
        await interaction.followup.send(embed=embed)
        log_event("SOLO_ALLY_REMOVE", interaction.user, {"member": user.name})

    # --- ALLY LEADER COMMANDS ---
    @app_commands.command(name="ally-add-member", description="[ALLY LEADER] Add a member to your guild.")
    @app_commands.checks.has_any_role(1397797430782853261) # Using ID directly for checks
    @app_commands.describe(member="The member to add to your guild.")
    async def ally_add_member(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        leader_guild_role = await self.get_leader_guild_role(interaction.user)
        if not leader_guild_role: return await interaction.followup.send("⚠️ Could not identify your guild role.")
        
        dark_ally_role = await self.get_role(interaction.guild, self.config["dark_ally_role_id"])
        await member.add_roles(dark_ally_role, leader_guild_role)
        embed = discord.Embed(title="🤝 Member Added", description=f"{member.mention} has been added to `{leader_guild_role.name}`.", color=discord.Color.blue())
        await interaction.followup.send(embed=embed)
        log_event("ALLY_MEMBER_ADD", interaction.user, {"guild_name": leader_guild_role.name, "member": member.name})

    @app_commands.command(name="ally-remove-member", description="[ALLY LEADER] Remove a member from your guild.")
    @app_commands.checks.has_any_role(1397797430782853261) # Using ID directly for checks
    @app_commands.describe(member="The member to remove from your guild.")
    async def ally_remove_member(self, interaction: discord.Interaction, member: discord.Member):
        await interaction.response.defer(ephemeral=True)
        leader_guild_role = await self.get_leader_guild_role(interaction.user)
        if not leader_guild_role: return await interaction.followup.send("⚠️ Could not identify your guild role.")
        if leader_guild_role not in member.roles: return await interaction.followup.send("This member is not part of your guild.")
        
        dark_ally_role = await self.get_role(interaction.guild, self.config["dark_ally_role_id"])
        await member.remove_roles(dark_ally_role, leader_guild_role)
        embed = discord.Embed(title="👋 Member Removed", description=f"{member.mention} has been removed from `{leader_guild_role.name}`.", color=discord.Color.orange())
        await interaction.followup.send(embed=embed)
        log_event("ALLY_MEMBER_REMOVE", interaction.user, {"guild_name": leader_guild_role.name, "member": member.name})
    
    # --- PUBLIC ALLIANCE COMMANDS ---
    @app_commands.command(name="view-ally-guild", description="View the members of a specific allied guild.")
    @app_commands.describe(guild_role="The role of the allied guild you want to view.")
    async def view_ally_guild(self, interaction: discord.Interaction, guild_role: discord.Role):
        await interaction.response.defer()
        
        ally_leader_role = await self.get_role(interaction.guild, self.config["ally_leader_role_id"])
        leader = next((m for m in guild_role.members if ally_leader_role in m.roles), None)
        members = [m.mention for m in guild_role.members if m != leader]
        
        embed = discord.Embed(title=f"👥 Members of {guild_role.name}", color=discord.Color.purple())
        if leader:
            embed.add_field(name="👑 Leader", value=leader.mention, inline=False)
        embed.add_field(name=f"⚔️ Members ({len(members)})", value="\n".join(members) or "No other members found.", inline=False)
        await interaction.followup.send(embed=embed)

    @app_commands.command(name="alliance-leaderboard", description="Displays the leaderboard of all allies.")
    async def alliance_leaderboard(self, interaction: discord.Interaction):
        await interaction.response.defer()
        embed = discord.Embed(title="🏆 Alliance Leaderboard 🏆", color=discord.Color.gold(), timestamp=datetime.datetime.now())
        
        ally_leader_role = await self.get_role(interaction.guild, self.config["ally_leader_role_id"])
        guild_allies_text = ""
        if ally_leader_role and ally_leader_role.members:
            for leader in ally_leader_role.members:
                guild_role = await self.get_leader_guild_role(leader)
                guild_name = guild_role.name if guild_role else "Unknown"
                guild_allies_text += f"**Guild:** `{guild_name}` | **Leader:** {leader.mention}\n"
        embed.add_field(name="🛡️ Allied Guilds", value=guild_allies_text or "No allied guilds found.", inline=False)
        
        solo_ally_role = await self.get_role(interaction.guild, self.config["solo_ally_role_id"])
        if solo_ally_role and solo_ally_role.members:
            solo_allies_text = ", ".join([member.mention for member in solo_ally_role.members])
            embed.add_field(name="👤 Solo Allies", value=solo_allies_text, inline=False)
        
        await interaction.followup.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Alliance(bot))