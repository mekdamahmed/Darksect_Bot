import discord
from discord import app_commands
from discord.ext import commands
from .general import log_event

class Ranks(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.config = bot.config

    def is_admin(self, interaction: discord.Interaction) -> bool:
        admin_ids = set(self.config["admin_role_ids"])
        user_role_ids = {role.id for role in interaction.user.roles}
        return not admin_ids.isdisjoint(user_role_ids)

    @app_commands.command(name="promote", description="[ADMIN] Promote a member to the next rank.")
    @app_commands.describe(member="The member to promote.")
    async def promote(self, interaction: discord.Interaction, member: discord.Member):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        hierarchy = self.config["rank_hierarchy"]
        current_rank_id = next((r.id for r in member.roles if r.id in hierarchy), None)
        if not current_rank_id: return await interaction.followup.send(f"⚠️ This member has no rank role.")
        
        current_rank_index = hierarchy.index(current_rank_id)
        if current_rank_index == len(hierarchy) - 1: return await interaction.followup.send(f"🏆 This member is at the highest rank!")
        
        new_rank_role = interaction.guild.get_role(hierarchy[current_rank_index + 1])
        current_rank_role = interaction.guild.get_role(current_rank_id)
        await member.remove_roles(current_rank_role)
        await member.add_roles(new_rank_role)
        
        embed = discord.Embed(title="📈 Promotion Successful", description=f"{member.mention} has been promoted from `{current_rank_role.name}` to **`{new_rank_role.name}`**!", color=discord.Color.brand_green())
        await interaction.followup.send(embed=embed)
        
        log_event("PROMOTION", interaction.user, {
            "target": member.name, "from": current_rank_role.name, "to": new_rank_role.name
        })

    @app_commands.command(name="demote", description="[ADMIN] Demote a member to the previous rank.")
    @app_commands.describe(member="The member to demote.")
    async def demote(self, interaction: discord.Interaction, member: discord.Member):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        await interaction.response.defer(ephemeral=True)
        hierarchy = self.config["rank_hierarchy"]
        current_rank_id = next((r.id for r in member.roles if r.id in hierarchy), None)
        if not current_rank_id: return await interaction.followup.send(f"⚠️ This member has no rank role.")
        
        current_rank_index = hierarchy.index(current_rank_id)
        if current_rank_index == 0: return await interaction.followup.send(f"This member is at the lowest rank!")
        
        new_rank_role = interaction.guild.get_role(hierarchy[current_rank_index - 1])
        current_rank_role = interaction.guild.get_role(current_rank_id)
        await member.remove_roles(current_rank_role)
        await member.add_roles(new_rank_role)

        embed = discord.Embed(title="📉 Demotion Successful", description=f"{member.mention} has been demoted from `{current_rank_role.name}` to **`{new_rank_role.name}`**.", color=discord.Color.orange())
        await interaction.followup.send(embed=embed)

        log_event("DEMOTION", interaction.user, {
            "target": member.name, "from": current_rank_role.name, "to": new_rank_role.name
        })

async def setup(bot: commands.Bot):
    await bot.add_cog(Ranks(bot))