import discord
from discord.ext import commands
import sqlite3

# إعداد البوت
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="/", intents=intents)

# قاعدة البيانات
conn = sqlite3.connect("players.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    username TEXT,
    mmr INTEGER DEFAULT 1000,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0
)''')
conn.commit()

# إضافة أو تحديث لاعب
def add_or_update_player(user):
    c.execute("SELECT * FROM players WHERE id = ?", (str(user.id),))
    result = c.fetchone()
    if not result:
        c.execute("INSERT INTO players (id, username) VALUES (?, ?)", (str(user.id), user.name))
        conn.commit()

# أمر عرض الرانك
@bot.command()
async def rank(ctx):
    add_or_update_player(ctx.author)
    c.execute("SELECT mmr, wins, losses FROM players WHERE id = ?", (str(ctx.author.id),))
    mmr, wins, losses = c.fetchone()
    await ctx.send(f"**{ctx.author.name}**\nMMR: {mmr}\nWins: {wins}\nLosses: {losses}")

# أمر عرض التوب 10
@bot.command()
async def top(ctx):
    c.execute("SELECT username, mmr FROM players ORDER BY mmr DESC LIMIT 10")
    top_players = c.fetchall()
    leaderboard = "\n".join([f"#{i+1} - {user}: {mmr}" for i, (user, mmr) in enumerate(top_players)])
    await ctx.send("**🏆 Top 10 Players:**\n" + leaderboard)

# تشغيل البوت
bot.run("YOUR_BOT_TOKEN_HERE")
