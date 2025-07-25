import discord
from discord.ext import commands
import os
import json
from dotenv import load_dotenv

# --- Load Configuration ---
load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")
with open('config.json', 'r') as f:
    config = json.load(f)

# --- Bot Initialization ---
class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(
            command_prefix="!", # Prefix isn't really used with slash commands
            intents=discord.Intents.all(), # Using all intents for simplicity
            application_id=os.getenv("APP_ID") # Add your bot's Application ID to .env file for guild-specific commands
        )
        # Attach config to the bot instance to be accessible in cogs
        self.config = config

    async def setup_hook(self):
        # This function is called when the bot logs in
        print("Loading cogs...")
        for filename in os.listdir('./cogs'):
            if filename.endswith('.py'):
                try:
                    await self.load_extension(f'cogs.{filename[:-3]}')
                    print(f"  > Loaded {filename}")
                except Exception as e:
                    print(f"  > Failed to load {filename}: {e}")
        
        # Optional: Sync commands to a specific guild for instant updates
        # guild = discord.Object(id=YOUR_GUILD_ID) # Add your guild ID here
        # self.tree.copy_global_to(guild=guild)
        # await self.tree.sync(guild=guild)
        await self.tree.sync() # Global sync

    async def on_ready(self):
        print(f"Success! Bot is now online as: {self.user}")

# --- Run the Bot ---
if __name__ == "__main__":
    if TOKEN is None:
        print("FATAL ERROR: DISCORD_TOKEN is not set in the .env file.")
    else:
        bot = MyBot()
        bot.run(TOKEN)
from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "I'm alive!"

def run():
  app.run(host='0.0.0.0',port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()
