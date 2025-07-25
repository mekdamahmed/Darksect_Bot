import discord
from discord.ext import commands
import os
import json
from dotenv import load_dotenv

# --- NEW IMPORTS FOR KEEP_ALIVE ---
from flask import Flask
from threading import Thread
# ------------------------------------

# --- Load Configuration ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
if TOKEN is None:
    raise ValueError("FATAL ERROR: DISCORD_TOKEN is not set in the .env file.")

with open('config.json', 'r') as f:
    config = json.load(f)

# --- NEW: KEEP ALIVE WEB SERVER CODE ---
app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
# -----------------------------------------

# --- Bot Initialization ---
class GuildBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!",
            intents=discord.Intents.all(),
        )
        self.config = config

    async def setup_hook(self):
        print("--- Loading Cogs ---")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"  [+] Loaded Cog: {filename}")
                except Exception as e:
                    print(f"  [!] Failed to load {filename}: {e}")
        
        await self.tree.sync()
        print("--- Command tree synced ---")

    async def on_ready(self):
        print(f"\n--- Bot is online and ready! ---")
        print(f"Logged in as: {self.user}")
        print(f"Bot ID: {self.user.id}")
        print("---------------------------------")

# --- Run the Bot ---
if __name__ == "__main__":
    bot = GuildBot()
    keep_alive() # <-- ADDED THIS LINE TO START THE WEB SERVER
    bot.run(TOKEN)
