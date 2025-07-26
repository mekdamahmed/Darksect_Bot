import discord
from discord import app_commands
from discord.ext import commands
import json
import os
import random
from typing import List, Dict
from .general import log_event # We import the logger from our general cog

# --- DATA FILE HELPER FUNCTIONS ---
TOURNAMENT_FILE = 'data/tournament_data.json'

def load_data() -> Dict:
    """Loads tournament data from the JSON file."""
    if not os.path.exists(TOURNAMENT_FILE) or os.path.getsize(TOURNAMENT_FILE) == 0:
        return {"is_active": False}
    with open(TOURNAMENT_FILE, 'r', encoding='utf-8') as f:
        return json.load(f)

def save_data(data: Dict):
    """Saves tournament data to the JSON file."""
    with open(TOURNAMENT_FILE, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=4)

# --- COG DEFINITION ---
class Tournament(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def is_admin(self, interaction: discord.Interaction) -> bool:
        """Helper to check for admin role."""
        admin_ids = set(self.bot.config["admin_role_ids"])
        user_role_ids = {role.id for role in interaction.user.roles}
        return not admin_ids.isdisjoint(user_role_ids)

    # --- HELPER: FORMAT EMBEDS ---
    def format_bracket_embed(self, interaction: discord.Interaction, t_data: Dict) -> discord.Embed:
        # ... (This function for solo tournaments remains unchanged) ...
        pass

    def format_team_status_embed(self, interaction: discord.Interaction, t_data: Dict) -> discord.Embed:
        team_a_name = t_data["teams"]["a"]["name"]
        team_b_name = t_data["teams"]["b"]["name"]
        score_a = t_data["team_scores"]["a"]
        score_b = t_data["team_scores"]["b"]
        
        embed = discord.Embed(
            title=f"📊 Status for {t_data['name']}",
            description=f"**Score:** `{team_a_name}` {score_a} - {score_b} `{team_b_name}`",
            color=discord.Color.blue()
        )
        
        team_a_members = ", ".join([interaction.guild.get_member(m).mention for m in t_data["teams"]["a"]["members"]]) or "No members yet."
        team_b_members = ", ".join([interaction.guild.get_member(m).mention for m in t_data["teams"]["b"]["members"]]) or "No members yet."

        embed.add_field(name=f"Team: {team_a_name} ({len(t_data['teams']['a']['members'])} members)", value=team_a_members, inline=False)
        embed.add_field(name=f"Team: {team_b_name} ({len(t_data['teams']['b']['members'])} members)", value=team_b_members, inline=False)

        # Display the current round's fight card
        if t_data.get("team_matches"):
            last_round_name = list(t_data["team_matches"].keys())[-1]
            matches = t_data["team_matches"][last_round_name]
            fight_card_text = ""
            for i, match in enumerate(matches):
                p1 = interaction.guild.get_member(match['p1_id'])
                p2 = interaction.guild.get_member(match['p2_id'])
                if match.get('winner_id'):
                    winner = interaction.guild.get_member(match['winner_id'])
                    fight_card_text += f"`Fight {i+1}`: {p1.mention} vs {p2.mention} -> **Winner: {winner.mention}**\n"
                else:
                    fight_card_text += f"`Fight {i+1}`: {p1.mention} vs {p2.mention}\n"
            
            embed.add_field(name=f"--- Fight Card: {last_round_name.replace('round', 'Round ')} ---", value=fight_card_text, inline=False)
            
        return embed

    # --- SOLO TOURNAMENT COMMANDS ---
    # ... (All solo tournament commands from the previous final version remain here) ...

    # --- TEAM TOURNAMENT COMMANDS (REWORKED) ---
    @app_commands.command(name="team-tournament-start", description="[ADMIN] Start registration for a Team vs Team tournament.")
    @app_commands.describe(name="The tournament's name.", team_a_name="Name for Team A.", team_b_name="Name for Team B.")
    async def team_tournament_start(self, interaction: discord.Interaction, name: str, team_a_name: str, team_b_name: str):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if t_data.get("is_active"): return await interaction.response.send_message("A tournament is already active.", ephemeral=True)

        new_data = {
            "is_active": True, "type": "team", "name": name,
            "players": [], # General player pool for registration
            "teams": {
                "a": {"name": team_a_name, "members": []}, 
                "b": {"name": team_b_name, "members": []}
            },
            "team_scores": {"a": 0, "b": 0},
            "team_matches": {}
        }
        save_data(new_data)
        
        embed = discord.Embed(title=f"🔥 Team Tournament Registration: {name} 🔥", description=f"Players can now join the tournament pool using `/team-tournament-join`!", color=discord.Color.teal())
        await interaction.response.send_message(embed=embed)
        log_event("TOURNAMENT_START", interaction.user, {"type": "team", "name": name})

    @app_commands.command(name="team-tournament-join", description="Join the player pool for the active team tournament.")
    async def team_tournament_join(self, interaction: discord.Interaction):
        t_data = load_data()
        if not t_data.get("is_active") or t_data.get("type") != "team": return await interaction.response.send_message("No active team tournament registration.", ephemeral=True)
        
        if interaction.user.id in t_data["players"]:
            return await interaction.response.send_message("You are already registered for the tournament.", ephemeral=True)
        
        t_data["players"].append(interaction.user.id)
        save_data(t_data)
        
        await interaction.response.send_message(f"✅ You have successfully joined the player pool for **{t_data['name']}**! Waiting for an admin to create teams.", ephemeral=True)

    @app_commands.command(name="team-tournament-create-teams", description="[ADMIN] Assign players to teams and create Round 1 fights.")
    async def team_tournament_create_teams(self, interaction: discord.Interaction):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if not t_data.get("is_active") or t_data.get("type") != "team": return await interaction.response.send_message("No active team tournament.", ephemeral=True)
        
        players = t_data["players"]
        if not players: return await interaction.response.send_message("No players have registered yet.", ephemeral=True)
            
        random.shuffle(players)
        midpoint = len(players) // 2
        t_data["teams"]["a"]["members"] = players[:midpoint]
        t_data["teams"]["b"]["members"] = players[midpoint:]
        
        # --- NEW: Generate Round 1 Fights ---
        team_a_shuffled = list(t_data["teams"]["a"]["members"])
        team_b_shuffled = list(t_data["teams"]["b"]["members"])
        random.shuffle(team_a_shuffled)
        random.shuffle(team_b_shuffled)
        
        matches = []
        min_len = min(len(team_a_shuffled), len(team_b_shuffled))
        for i in range(min_len):
            matches.append({"p1_id": team_a_shuffled[i], "p2_id": team_b_shuffled[i], "winner_id": None})
        
        t_data["team_matches"]["round1"] = matches
        save_data(t_data)
        
        embed = self.format_team_status_embed(interaction, t_data)
        await interaction.response.send_message(f"**Teams have been created and Round 1 fights are set!**", embed=embed)
        log_event("TEAMS_CREATED", interaction.user, {"name": t_data["name"]})

    @app_commands.command(name="team-tournament-winner", description="[ADMIN] Declare the winner of a 1v1 team match.")
    @app_commands.describe(winner="The member who won their match.")
    async def team_tournament_winner(self, interaction: discord.Interaction, winner: discord.Member):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if not t_data.get("is_active") or t_data.get("type") != "team": return await interaction.response.send_message("No active team tournament.", ephemeral=True)

        last_round_name = list(t_data["team_matches"].keys())[-1]
        found_match = False
        for match in t_data["team_matches"][last_round_name]:
            if (match["p1_id"] == winner.id or match["p2_id"] == winner.id) and not match["winner_id"]:
                match["winner_id"] = winner.id
                # Update team score
                if winner.id in t_data["teams"]["a"]["members"]:
                    t_data["team_scores"]["a"] += 1
                else:
                    t_data["team_scores"]["b"] += 1
                found_match = True
                break
        
        if not found_match: return await interaction.response.send_message("Could not find an open match for this player.", ephemeral=True)

        save_data(t_data)
        embed = self.format_team_status_embed(interaction, t_data)
        await interaction.response.send_message("Winner recorded and score updated!", embed=embed)

    @app_commands.command(name="team-tournament-next-round", description="[ADMIN] Generate a new random fight card for the next round.")
    async def team_tournament_next_round(self, interaction: discord.Interaction):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if not t_data.get("is_active") or t_data.get("type") != "team": return await interaction.response.send_message("No active team tournament.", ephemeral=True)

        last_round_name = list(t_data["team_matches"].keys())[-1]
        if any(m['winner_id'] is None for m in t_data["team_matches"][last_round_name]):
            return await interaction.response.send_message(f"Cannot start the next round until all winners for {last_round_name} are declared.", ephemeral=True)

        next_round_num = int(last_round_name.replace('round', '')) + 1
        next_round_name = f"round{next_round_num}"
        
        team_a_shuffled = list(t_data["teams"]["a"]["members"])
        team_b_shuffled = list(t_data["teams"]["b"]["members"])
        random.shuffle(team_a_shuffled)
        random.shuffle(team_b_shuffled)
        
        matches = []
        min_len = min(len(team_a_shuffled), len(team_b_shuffled))
        for i in range(min_len):
            matches.append({"p1_id": team_a_shuffled[i], "p2_id": team_b_shuffled[i], "winner_id": None})
        
        t_data["team_matches"][next_round_name] = matches
        save_data(t_data)
        
        embed = self.format_team_status_embed(interaction, t_data)
        await interaction.response.send_message(f"**A new fight card for {next_round_name} has been generated!**", embed=embed)

    # --- GENERAL TOURNAMENT COMMANDS ---
    @app_commands.command(name="tournament-status", description="Check the status of the current tournament.")
    async def tournament_status(self, interaction: discord.Interaction):
        t_data = load_data()
        if not t_data.get("is_active"): return await interaction.response.send_message("There is no active tournament.", ephemeral=True)

        if t_data["type"] == 'solo':
            embed = self.format_bracket_embed(interaction, t_data)
        elif t_data["type"] == 'team':
            embed = self.format_team_status_embed(interaction, t_data)
        else:
            embed = discord.Embed(title="No active tournament.", color=discord.Color.dark_grey())
            
        await interaction.response.send_message(embed=embed)
    
    @app_commands.command(name="tournament-end", description="[ADMIN] End the current tournament and clear all data.")
    async def tournament_end(self, interaction: discord.Interaction):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if not t_data.get("is_active"): return await interaction.response.send_message("There is no active tournament.", ephemeral=True)
            
        tournament_name = t_data["name"]
        
        # Announce final team scores if it was a team tournament
        if t_data.get("type") == "team":
            team_a_name = t_data["teams"]["a"]["name"]; team_b_name = t_data["teams"]["b"]["name"]
            score_a = t_data["team_scores"]["a"]; score_b = t_data["team_scores"]["b"]
            winner_text = ""
            if score_a > score_b:
                winner_text = f"**Team {team_a_name} is victorious!**"
            elif score_b > score_a:
                winner_text = f"**Team {team_b_name} is victorious!**"
            else:
                winner_text = "The result is a draw!"
            
            final_embed = discord.Embed(title=f"🏁 Final Score for {tournament_name} 🏁", description=f"**{team_a_name}:** `{score_a}` points\n**{team_b_name}:** `{score_b}` points\n\n{winner_text}", color=discord.Color.gold())
            await interaction.channel.send(embed=final_embed)

        save_data({"is_active": False}) # Reset the file
        await interaction.response.send_message(f"The tournament **{tournament_name}** has been officially concluded.")
        log_event("TOURNAMENT_END", interaction.user, {"name": tournament_name})

async def setup(bot: commands.Bot):
    await bot.add_cog(Tournament(bot))
