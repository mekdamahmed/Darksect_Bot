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
        embed = discord.Embed(title=f"⚔️ Bracket for {t_data['name']} ⚔️", color=discord.Color.red())
        if not t_data.get("bracket"):
            players = [interaction.guild.get_member(p_id) for p_id in t_data.get("players", [])]
            players_list = "\n".join([p.mention for p in players if p])
            embed.description = f"**Registration Phase**\n\n**Players ({len(players)}/16):**\n{players_list or 'No players yet.'}"
            return embed
            
        for round_name, matches in t_data['bracket'].items():
            round_text = ""
            for i, match in enumerate(matches):
                p1 = interaction.guild.get_member(match['p1_id'])
                p2 = interaction.guild.get_member(match['p2_id'])
                p1_mention = p1.mention if p1 else f"`ID: {match['p1_id']}`"
                p2_mention = p2.mention if p2 else f"`ID: {match['p2_id']}`"
                
                if match.get('winner_id'):
                    winner = interaction.guild.get_member(match['winner_id'])
                    winner_mention = winner.mention if winner else f"`ID: {match['winner_id']}`"
                    round_text += f"`Match {i+1}`: {p1_mention} vs {p2_mention} -> **Winner: {winner_mention}**\n"
                else:
                    round_text += f"`Match {i+1}`: {p1_mention} vs {p2_mention}\n"
            embed.add_field(name=f"--- {round_name.replace('round', 'Round ')} ---", value=round_text or "TBD", inline=False)
        return embed

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

    # --- HELPER: CHECK AND ADVANCE ROUND (WITH RANKING) ---
    async def check_and_advance_round(self, interaction: discord.Interaction):
        t_data = load_data()
        last_round_name = list(t_data["bracket"].keys())[-1]
        last_round_matches = t_data["bracket"][last_round_name]

        if any(m['winner_id'] is None for m in last_round_matches): return

        winners_ids = [m['winner_id'] for m in last_round_matches]
        
        if len(winners_ids) == 1:
            # --- FINAL RANKING LOGIC ---
            final_rankings = {"1st": None, "2nd": None, "semi": [], "quarter": [], "round1": []}
            bracket = t_data["bracket"]
            
            final_match = bracket[last_round_name][0]
            final_rankings["1st"] = final_match["winner_id"]
            final_rankings["2nd"] = final_match["p1_id"] if final_match["p1_id"] != final_match["winner_id"] else final_match["p2_id"]
            
            for round_num in reversed(range(1, len(bracket) + 1)):
                round_name = f"round{round_num}"
                losers_this_round = [m["p1_id"] if m["p1_id"] != m["winner_id"] else m["p2_id"] for m in bracket[round_name]]
                
                if len(bracket) > 1 and round_num == len(bracket) - 1:
                    final_rankings["semi"] = losers_this_round
                elif len(bracket) > 2 and round_num == len(bracket) - 2:
                    final_rankings["quarter"] = losers_this_round
                elif round_num == 1:
                    final_rankings["round1"] = losers_this_round

            embed = discord.Embed(title=f"🏆 Final Rankings for {t_data['name']} 🏆", color=discord.Color.gold())
            
            first = interaction.guild.get_member(final_rankings["1st"]); embed.add_field(name="🥇 1st Place", value=first.mention if first else "Not Found", inline=False)
            second = interaction.guild.get_member(final_rankings["2nd"]); embed.add_field(name="🥈 2nd Place", value=second.mention if second else "Not Found", inline=False)
            if final_rankings["semi"]:
                mentions = ", ".join([interaction.guild.get_member(p).mention for p in final_rankings["semi"]])
                embed.add_field(name="🥉 Semi-Finalists (3rd/4th)", value=mentions, inline=False)
            if final_rankings["quarter"]:
                mentions = ", ".join([interaction.guild.get_member(p).mention for p in final_rankings["quarter"]])
                embed.add_field(name="🏅 Quarter-Finalists", value=mentions, inline=False)
            if final_rankings["round1"]:
                mentions = ", ".join([interaction.guild.get_member(p).mention for p in final_rankings["round1"]])
                embed.add_field(name="⚔️ Eliminated in Round 1", value=mentions, inline=False)
            
            await interaction.channel.send(embed=embed)
            save_data({"is_active": False})
            return

        next_round_num = int(last_round_name.replace('round', '')) + 1
        next_round_name = f"round{next_round_num}"
        random.shuffle(winners_ids)
        new_matches = [{"p1_id": winners_ids[i], "p2_id": winners_ids[i+1], "winner_id": None} for i in range(0, len(winners_ids), 2)]
        t_data["bracket"][next_round_name] = new_matches
        save_data(t_data)
        
        embed = self.format_bracket_embed(interaction, t_data)
        await interaction.channel.send(f"**All winners recorded! The next round has been generated automatically.**", embed=embed)

    # --- SOLO TOURNAMENT COMMANDS ---
    @app_commands.command(name="solo-tournament-start", description="[ADMIN] Start a 1v1 bracket tournament (4, 8, or 16 players).")
    @app_commands.describe(name="The name of the tournament.", players="Mention all players who will participate.")
    async def solo_tournament_start(self, interaction: discord.Interaction, name: str, players: str):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if t_data.get("is_active"): return await interaction.response.send_message("A tournament is already active.", ephemeral=True)
        
        participant_list = interaction.message.mentions
        if len(participant_list) not in [4, 8, 16]: return await interaction.response.send_message(f"Bracket requires 4, 8, or 16 players. You provided {len(participant_list)}.", ephemeral=True)
        
        player_ids = [p.id for p in participant_list]
        random.shuffle(player_ids)
        matches = [{"p1_id": player_ids[i], "p2_id": player_ids[i+1], "winner_id": None} for i in range(0, len(player_ids), 2)]
        
        new_data = {"is_active": True, "type": "solo", "name": name, "players": player_ids, "bracket": {"round1": matches}}
        save_data(new_data)
        
        embed = self.format_bracket_embed(interaction, new_data)
        await interaction.response.send_message(f"**A new 1v1 tournament has started!** The bracket has been generated.", embed=embed)
        log_event("TOURNAMENT_START", interaction.user, {"type": "solo", "name": name, "players": len(player_ids)})

    @app_commands.command(name="tournament-winner", description="[ADMIN] Declare the winner of a match.")
    @app_commands.describe(winner="The member who won their match.")
    async def tournament_winner(self, interaction: discord.Interaction, winner: discord.Member):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if not t_data.get("is_active"): return await interaction.response.send_message("No active tournament.", ephemeral=True)

        if t_data.get("type") == "solo":
            found_match = False
            for matches in t_data["bracket"].values():
                for match in matches:
                    if (match["p1_id"] == winner.id or match["p2_id"] == winner.id) and not match["winner_id"]:
                        match["winner_id"] = winner.id
                        found_match = True
                        break
                if found_match: break
            
            if not found_match: return await interaction.response.send_message("Could not find an open match for this player.", ephemeral=True)

            save_data(t_data)
            await interaction.response.send_message("Winner recorded. Checking if round is complete...", ephemeral=True)
            await self.check_and_advance_round(interaction)

        elif t_data.get("type") == "team":
            last_round_name = list(t_data["team_matches"].keys())[-1]
            found_match = False
            for match in t_data["team_matches"][last_round_name]:
                if (match["p1_id"] == winner.id or match["p2_id"] == winner.id) and not match["winner_id"]:
                    match["winner_id"] = winner.id
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

    # --- TEAM TOURNAMENT COMMANDS ---
    @app_commands.command(name="team-tournament-start", description="[ADMIN] Start registration for a Team vs Team tournament.")
    @app_commands.describe(name="The tournament's name.", team_a_name="Name for Team A.", team_b_name="Name for Team B.")
    async def team_tournament_start(self, interaction: discord.Interaction, name: str, team_a_name: str, team_b_name: str):
        if not self.is_admin(interaction): return await interaction.response.send_message("Permission denied.", ephemeral=True)
        t_data = load_data()
        if t_data.get("is_active"): return await interaction.response.send_message("A tournament is already active.", ephemeral=True)

        new_data = {
            "is_active": True, "type": "team", "name": name,
            "players": [],
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
        
        if t_data.get("type") == "team":
            team_a_name = t_data["teams"]["a"]["name"]; team_b_name = t_data["teams"]["b"]["name"]
            score_a = t_data["team_scores"]["a"]; score_b = t_data["team_scores"]["b"]
            winner_text = ""
            if score_a > score_b: winner_text = f"**Team {team_a_name} is victorious!**"
            elif score_b > score_a: winner_text = f"**Team {team_b_name} is victorious!**"
            else: winner_text = "The result is a draw!"
            
            final_embed = discord.Embed(title=f"🏁 Final Score for {tournament_name} 🏁", description=f"**{team_a_name}:** `{score_a}` points\n**{team_b_name}:** `{score_b}` points\n\n{winner_text}", color=discord.Color.gold())
            await interaction.channel.send(embed=final_embed)

        save_data({"is_active": False})
        await interaction.response.send_message(f"The tournament **{tournament_name}** has been officially concluded.")
        log_event("TOURNAMENT_END", interaction.user, {"name": tournament_name})

async def setup(bot: commands.Bot):
    await bot.add_cog(Tournament(bot))
