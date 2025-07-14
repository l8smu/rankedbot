import discord
from discord.ext import commands, tasks
from discord import app_commands
import sqlite3
import asyncio
import random
import os
import logging
from datetime import datetime, timedelta
from itertools import combinations

# Setup logging system
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('heatseeker_bot.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HeatSeeker')

# Bot setup with enhanced intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables for queue and match system
player_queue = []
active_matches = {}
match_id_counter = 1
queue_timeout_task = None
queue_last_activity = None
pending_team_selection = {}  # Store pending team selection data
captain_draft_state = {}  # Store captain draft state

# Global variables for private chat system
private_chats = {}  # Store private chat data
used_hsm_numbers = set()  # Track used HSM numbers

# Channel configuration
QUEUE_CHANNEL_NAME = "heatseeker-queue"  # Main queue channel
RESULTS_CHANNEL_NAME = "heatseeker-results"  # Results channel for completed matches
MATCH_CATEGORY_NAME = "HeatSeeker Matches"  # Category for match channels
PRIVATE_CATEGORY_NAME = "HSM Private Chats"  # Category for private chats

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

# Create matches table for queue system
c.execute('''CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY,
    team1_players TEXT,
    team2_players TEXT,
    winner INTEGER,
    created_at TEXT,
    ended_at TEXT,
    channel_id TEXT,
    admin_modified INTEGER DEFAULT 0,
    cancelled INTEGER DEFAULT 0
)''')

# Create private chats table
c.execute('''CREATE TABLE IF NOT EXISTS private_chats (
    hsm_number INTEGER PRIMARY KEY,
    creator_id TEXT,
    channel_id TEXT,
    voice_channel_id TEXT,
    created_at TEXT,
    is_active INTEGER DEFAULT 1
)''')

# Create private matches table for queue participants
c.execute('''CREATE TABLE IF NOT EXISTS private_matches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    channel_id TEXT NOT NULL,
    created_at TEXT NOT NULL,
    is_active INTEGER DEFAULT 1
)''')
conn.commit()

def initialize_match_counter():
    """Initialize match_id_counter based on existing database entries"""
    global match_id_counter
    try:
        # Get the highest existing match_id from database
        c.execute("SELECT MAX(match_id) FROM matches")
        result = c.fetchone()
        if result and result[0] is not None:
            match_id_counter = result[0] + 1
        else:
            match_id_counter = 1
        print(f"[DEBUG] Match ID counter initialized to: {match_id_counter}")
    except Exception as e:
        print(f"[DEBUG] Error initializing match counter: {e}")
        match_id_counter = 1

def restore_active_matches():
    """Restore active matches from database on bot restart"""
    global active_matches
    try:
        # Get all matches that don't have a winner set (active matches)
        c.execute("""
            SELECT match_id, team1_players, team2_players, created_at, channel_id
            FROM matches 
            WHERE winner IS NULL OR winner = 0
        """)
        db_matches = c.fetchall()
        
        restored_count = 0
        for match_id, team1_ids, team2_ids, created_at, channel_id in db_matches:
            # Parse team player IDs
            team1_player_ids = team1_ids.split(',') if team1_ids else []
            team2_player_ids = team2_ids.split(',') if team2_ids else []
            
            # Get player data for each team
            team1 = []
            team2 = []
            
            for player_id in team1_player_ids:
                c.execute("SELECT username, mmr FROM players WHERE id = ?", (player_id,))
                result = c.fetchone()
                if result:
                    username, mmr = result
                    team1.append({'id': player_id, 'username': username, 'mmr': mmr})
            
            for player_id in team2_player_ids:
                c.execute("SELECT username, mmr FROM players WHERE id = ?", (player_id,))
                result = c.fetchone()
                if result:
                    username, mmr = result
                    team2.append({'id': player_id, 'username': username, 'mmr': mmr})
            
            # Only restore if we have complete team data
            if len(team1) == 2 and len(team2) == 2:
                # Generate HSM number (simplified - use match_id as HSM number)
                hsm_number = match_id
                
                active_matches[match_id] = {
                    'team1': team1,
                    'team2': team2,
                    'players': team1_player_ids + team2_player_ids,
                    'channel_id': channel_id,
                    'hsm_number': hsm_number,
                    'distribution_method': 'Restored',
                    'created_at': created_at
                }
                restored_count += 1
                print(f"[DEBUG] Restored match {match_id}: HSM{hsm_number}")
        
        print(f"[DEBUG] Restored {restored_count} active matches from database")
    except Exception as e:
        print(f"[DEBUG] Error restoring active matches: {e}")
        active_matches = {}

# Add sample data for demonstration
def add_sample_data():
    """Add sample players for demonstration"""
    sample_players = [
        ('123456789', 'PlayerOne', 1200, 15, 5),
        ('987654321', 'TopGamer', 1450, 25, 8),
        ('456789123', 'SkillMaster', 1350, 20, 12),
        ('789123456', 'ProPlayer', 1100, 18, 15),
        ('321654987', 'GameChamp', 1300, 22, 10),
        ('654321789', 'EliteGamer', 1500, 30, 5),
        ('147258369', 'RankClimber', 1250, 16, 9),
        ('963852741', 'CompetitivePro', 1400, 28, 7),
        ('258741963', 'StrategyMaster', 1180, 14, 11),
        ('741852963', 'LeaderboardKing', 1600, 35, 3)
    ]
    
    for player_id, username, mmr, wins, losses in sample_players:
        c.execute("SELECT * FROM players WHERE id = ?", (player_id,))
        if not c.fetchone():
            c.execute("INSERT INTO players (id, username, mmr, wins, losses) VALUES (?, ?, ?, ?, ?)",
                     (player_id, username, mmr, wins, losses))
    conn.commit()
    logger.info(f"Added {len(sample_players)} sample players to database")

# Logging helper functions
def log_queue_event(event_type, user_name, details=""):
    """Log queue-related events"""
    logger.info(f"QUEUE {event_type}: {user_name} - {details}")

def log_match_event(event_type, match_id, details=""):
    """Log match-related events"""
    logger.info(f"MATCH {event_type}: Match #{match_id} - {details}")

def log_admin_action(action, admin_name, details=""):
    """Log admin actions"""
    logger.info(f"ADMIN {action}: {admin_name} - {details}")

def log_player_update(player_name, old_stats, new_stats):
    """Log player stat updates"""
    logger.info(f"PLAYER UPDATE: {player_name} - MMR: {old_stats['mmr']}->{new_stats['mmr']}, W/L: {old_stats['wins']}/{old_stats['losses']}->{new_stats['wins']}/{new_stats['losses']}")

# Button Views for Professional Queue System
class QueueView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🎮 Join Queue', style=discord.ButtonStyle.green, custom_id='join_queue')
    async def join_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_join_queue(interaction)
    
    @discord.ui.button(label='🚪 Leave Queue', style=discord.ButtonStyle.red, custom_id='leave_queue')
    async def leave_queue(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_leave_queue(interaction)
    
    @discord.ui.button(label='📊 Queue Status', style=discord.ButtonStyle.blurple, custom_id='queue_status')
    async def queue_status(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_queue_status(interaction)

class MatchView(discord.ui.View):
    def __init__(self, match_id):
        super().__init__(timeout=None)
        self.match_id = match_id
    
    @discord.ui.button(label='🏆 Team 1 Won', style=discord.ButtonStyle.green, custom_id='team1_win')
    async def team1_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_match_result(interaction, 1, self.match_id)
    
    @discord.ui.button(label='🏆 Team 2 Won', style=discord.ButtonStyle.green, custom_id='team2_win')
    async def team2_win(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_match_result(interaction, 2, self.match_id)
    
    @discord.ui.button(label='❌ Cancel Match', style=discord.ButtonStyle.secondary, custom_id='cancel_match')
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_cancel_match(interaction, self.match_id)

class PrivateChatView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
    
    @discord.ui.button(label='🔒 Create Private Chat', style=discord.ButtonStyle.blurple, custom_id='create_private')
    async def create_private_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_create_private_chat(interaction)
    
    @discord.ui.button(label='🗑️ Delete Private Chat', style=discord.ButtonStyle.red, custom_id='delete_private')
    async def delete_private_chat(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_delete_private_chat(interaction)

class TeamSelectionView(discord.ui.View):
    def __init__(self, players, hsm_number):
        super().__init__(timeout=300)  # 5 minute timeout
        self.players = players
        self.hsm_number = hsm_number
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the queued players to select team distribution
        user_id = str(interaction.user.id)
        return any(p['id'] == user_id for p in self.players)
    
    @discord.ui.button(label="🎲 Random Teams", style=discord.ButtonStyle.primary)
    async def random_teams(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_random_team_selection(interaction, self.players, self.hsm_number)
    
    @discord.ui.button(label="👑 Captain Draft", style=discord.ButtonStyle.secondary)
    async def captain_draft(self, interaction: discord.Interaction, button: discord.ui.Button):
        await handle_captain_draft_selection(interaction, self.players, self.hsm_number)

class CaptainDraftView(discord.ui.View):
    def __init__(self, draft_id, captain_turn, available_players):
        super().__init__(timeout=300)  # 5 minute timeout
        self.draft_id = draft_id
        self.captain_turn = captain_turn
        self.available_players = available_players
        
        # Add buttons for each available player
        for i, player in enumerate(available_players):
            button = discord.ui.Button(
                label=f"{player['username']} ({player['mmr']} MMR)",
                style=discord.ButtonStyle.secondary,
                custom_id=f"pick_{player['id']}_{i}"
            )
            # Create a callback for each button with the player ID
            button.callback = self.create_pick_callback(player['id'])
            self.add_item(button)
    
    def create_pick_callback(self, player_id):
        """Create a callback function for the specific player"""
        async def pick_callback(interaction: discord.Interaction):
            print(f"[DEBUG] Button clicked for player {player_id}")
            await handle_captain_pick(interaction, self.draft_id, player_id)
        return pick_callback
    
    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Only allow the current captain to pick
        draft_state = captain_draft_state.get(self.draft_id)
        if not draft_state:
            print(f"[DEBUG] Draft session expired for interaction check: {self.draft_id}")
            await interaction.response.send_message("❌ Draft session expired!", ephemeral=True)
            return False
        
        current_captain = draft_state['captains'][draft_state['current_captain']]
        user_id = str(interaction.user.id)
        print(f"[DEBUG] Interaction check - User: {user_id}, Current captain: {current_captain['id']}")
        
        if user_id != current_captain['id']:
            print(f"[DEBUG] Not user's turn to pick")
            await interaction.response.send_message("❌ It's not your turn to pick!", ephemeral=True)
            return False
        
        print(f"[DEBUG] Interaction check passed")
        return True

# Helper functions for button interactions
async def handle_join_queue(interaction: discord.Interaction):
    """Handle join queue button press"""
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ Please use the #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return
    
    add_or_update_player(interaction.user)
    user_id = str(interaction.user.id)
    
    # Check if player is already in queue
    if any(player['id'] == user_id for player in player_queue):
        await interaction.response.send_message("❌ You are already in the queue!", ephemeral=True)
        return
    
    # Check if player is in an active match
    if any(user_id in match['players'] for match in active_matches.values()):
        await interaction.response.send_message("❌ You are currently in an active match!", ephemeral=True)
        return
    
    # Add player to queue
    c.execute("SELECT username, mmr FROM players WHERE id = ?", (user_id,))
    result = c.fetchone()
    if result:
        username, mmr = result
        player_queue.append({'id': user_id, 'username': username, 'mmr': mmr, 'user': interaction.user})
        
        # Update queue activity for timeout system
        update_queue_activity()
        
        await interaction.response.send_message(f"✅ **{interaction.user.display_name}** joined the queue! ({len(player_queue)}/4)\n⏰ Queue timeout: {QUEUE_TIMEOUT_MINUTES} minutes", ephemeral=True)
        
        # Update the queue display
        await update_queue_display(interaction.channel)
        
        # Check if we have 4 players to start a match
        if len(player_queue) >= 4:
            await create_match(interaction.channel, interaction.guild)

async def handle_leave_queue(interaction: discord.Interaction):
    """Handle leave queue button press"""
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ Please use the #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    
    # Remove player from queue
    global player_queue
    original_length = len(player_queue)
    player_queue = [p for p in player_queue if p['id'] != user_id]
    
    if len(player_queue) == original_length:
        await interaction.response.send_message("❌ You are not in the queue!", ephemeral=True)
        return
    
    # Update queue activity for timeout system
    update_queue_activity()
    
    await interaction.response.send_message(f"✅ **{interaction.user.display_name}** left the queue! ({len(player_queue)}/4)", ephemeral=True)
    
    # Update the queue display
    await update_queue_display(interaction.channel)

async def handle_queue_status(interaction: discord.Interaction):
    """Handle queue status button press"""
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ Please use the #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return
    
    if not player_queue:
        embed = discord.Embed(
            title="📋 Queue Status",
            description="Queue is empty. Click **🎮 Join Queue** to get started!",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="📋 Queue Status",
            description=f"**{len(player_queue)}/4** players in queue",
            color=discord.Color.blue()
        )
        
        queue_text = ""
        for i, player in enumerate(player_queue, 1):
            queue_text += f"{i}. **{player['username']}** ({player['mmr']} MMR)\n"
        
        embed.add_field(name="Players in Queue", value=queue_text, inline=False)
    
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def handle_match_result(interaction: discord.Interaction, team_number: int, match_id: int):
    """Handle match result button press"""
    if match_id not in active_matches:
        await interaction.response.send_message("❌ Match not found or already completed!", ephemeral=True)
        return
    
    match_data = active_matches[match_id]
    
    # Check if user is part of the match
    user_id = str(interaction.user.id)
    if user_id not in match_data['players']:
        await interaction.response.send_message("❌ Only match participants can report results!", ephemeral=True)
        return
    
    # Update match result
    winning_team = match_data['team1'] if team_number == 1 else match_data['team2']
    losing_team = match_data['team2'] if team_number == 1 else match_data['team1']
    
    # Calculate MMR changes
    mmr_changes = calculate_mmr_changes(winning_team, losing_team)
    
    # Update player stats
    for player in winning_team:
        c.execute("UPDATE players SET wins = wins + 1, mmr = mmr + ? WHERE id = ?", 
                 (mmr_changes['winners'], player['id']))
    
    for player in losing_team:
        c.execute("UPDATE players SET losses = losses + 1, mmr = mmr + ? WHERE id = ?", 
                 (mmr_changes['losers'], player['id']))
    
    # Update match record
    c.execute("UPDATE matches SET winner = ?, ended_at = ? WHERE match_id = ?", 
             (team_number, datetime.now().isoformat(), match_id))
    conn.commit()
    
    # Log the match completion
    log_match_event("COMPLETED", f"Match {match_id}", f"Team {team_number} won - MMR changes: Winners +{mmr_changes['winners']}, Losers {mmr_changes['losers']}")
    
    # CRITICAL FIX: Remove players from active match immediately after database update
    # This prevents players from being stuck in "active match" state
    match_data_copy = active_matches[match_id].copy()  # Keep a copy for cleanup
    del active_matches[match_id]  # Remove from active matches immediately
    
    # Send DM notifications to all players
    await send_match_completion_dms(winning_team, losing_team, match_id, mmr_changes)
    
    # Create result embed
    embed = discord.Embed(
        title="🏆 MATCH COMPLETED!",
        description=f"**Match #{match_id}** has ended!",
        color=discord.Color.green()
    )
    
    winner_mentions = ' '.join([p['user'].mention for p in winning_team])
    loser_mentions = ' '.join([p['user'].mention for p in losing_team])
    
    embed.add_field(name="🎉 Winners", value=f"{winner_mentions}\n**+{mmr_changes['winners']} MMR**", inline=True)
    embed.add_field(name="💔 Losers", value=f"{loser_mentions}\n**{mmr_changes['losers']} MMR**", inline=True)
    embed.add_field(name="📬 DMs Sent", value="All players have been notified with detailed results!", inline=False)
    embed.add_field(name="🎮 Queue Status", value="Players can now rejoin the queue!", inline=False)
    
    await interaction.response.send_message(embed=embed)
    
    # Post completed match to results channel with admin controls (use copied data)
    await post_match_to_results_channel_with_data(interaction.guild, match_id, winning_team, losing_team, mmr_changes, match_data_copy)
    
    # Clean up match channels using the copied data
    await cleanup_match_with_data(interaction.guild, match_id, match_data_copy)

async def handle_cancel_match(interaction: discord.Interaction, match_id: int):
    """Handle cancel match button press"""
    if match_id not in active_matches:
        await interaction.response.send_message("❌ Match not found or already completed!", ephemeral=True)
        return
    
    match_data = active_matches[match_id]
    
    # Check if user is part of the match or has admin permissions
    user_id = str(interaction.user.id)
    if user_id not in match_data['players'] and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Only match participants or admins can cancel matches!", ephemeral=True)
        return
    
    # Log the cancellation
    log_match_event("CANCELLED", f"Match {match_id}", f"Cancelled by {interaction.user.display_name}")
    
    # CRITICAL FIX: Remove players from active match immediately
    match_data_copy = active_matches[match_id].copy()  # Keep a copy for cleanup
    del active_matches[match_id]  # Remove from active matches immediately
    
    await interaction.response.send_message(f"🚫 **Match #{match_id}** has been cancelled by {interaction.user.display_name}!\n🎮 Players can now rejoin the queue!")
    
    # Clean up match channels using the copied data
    await cleanup_match_with_data(interaction.guild, match_id, match_data_copy)

# Private chat handler functions
async def handle_create_private_chat(interaction: discord.Interaction):
    """Handle create private chat button press"""
    user_id = str(interaction.user.id)
    
    # Check if user already has an active private chat
    c.execute("SELECT hsm_number FROM private_chats WHERE creator_id = ? AND is_active = 1", (user_id,))
    existing_chat = c.fetchone()
    
    if existing_chat:
        await interaction.response.send_message(f"❌ You already have an active private chat: **HSM{existing_chat[0]}**", ephemeral=True)
        return
    
    # Generate unique HSM number
    hsm_number = generate_hsm_number()
    if not hsm_number:
        await interaction.response.send_message("❌ No available HSM numbers (1-9999 all used)", ephemeral=True)
        return
    
    try:
        # Get or create private chat category
        category = discord.utils.get(interaction.guild.categories, name=PRIVATE_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(
                name=PRIVATE_CATEGORY_NAME,
                reason="HSM Private Chats category"
            )
        
        # Create private text channel
        private_channel = await interaction.guild.create_text_channel(
            name=f"hsm{hsm_number}",
            category=category,
            topic=f"🔒 HSM Private Chat #{hsm_number} - Created by {interaction.user.display_name}",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(read_messages=False),
                interaction.user: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True,
                    manage_channels=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    read_messages=True,
                    send_messages=True,
                    manage_messages=True
                )
            }
        )
        
        # Create private voice channel
        private_voice = await interaction.guild.create_voice_channel(
            name=f"🔒 HSM{hsm_number} Voice",
            category=category,
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(view_channel=False),
                interaction.user: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    speak=True,
                    manage_channels=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    view_channel=True,
                    connect=True,
                    manage_channels=True
                )
            }
        )
        
        # Save to database
        c.execute("""INSERT INTO private_chats (hsm_number, creator_id, channel_id, voice_channel_id, created_at) 
                     VALUES (?, ?, ?, ?, ?)""", 
                  (hsm_number, user_id, str(private_channel.id), str(private_voice.id), datetime.now().isoformat()))
        conn.commit()
        
        # Store in memory
        private_chats[hsm_number] = {
            'creator_id': user_id,
            'channel_id': str(private_channel.id),
            'voice_channel_id': str(private_voice.id),
            'created_at': datetime.now().isoformat()
        }
        used_hsm_numbers.add(hsm_number)
        
        # Send welcome message to private channel
        embed = discord.Embed(
            title=f"🔒 HSM{hsm_number} - Private Chat Created",
            description=f"**Welcome to your private chat, {interaction.user.display_name}!**",
            color=discord.Color.purple()
        )
        embed.add_field(name="HSM Number", value=f"**HSM{hsm_number}**", inline=True)
        embed.add_field(name="Creator", value=interaction.user.mention, inline=True)
        embed.add_field(name="Voice Channel", value=private_voice.mention, inline=True)
        embed.add_field(
            name="🔧 Managing Your Private Chat",
            value="• **Add Members:** Right-click channel → Edit Channel → Permissions → Add members\n• **Voice Access:** Grant voice channel permissions to your friends\n• **Delete Chat:** Use the delete button in the main queue channel",
            inline=False
        )
        embed.set_footer(text="This is your private space - manage permissions as needed!")
        
        await private_channel.send(embed=embed)
        
        # Confirm to user
        await interaction.response.send_message(
            f"✅ **Private chat created successfully!**\n**HSM Number:** HSM{hsm_number}\n**Channel:** {private_channel.mention}\n**Voice:** {private_voice.mention}",
            ephemeral=True
        )
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to create channels!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(f"❌ Error creating private chat: {e}", ephemeral=True)

async def handle_delete_private_chat(interaction: discord.Interaction):
    """Handle delete private chat button press"""
    user_id = str(interaction.user.id)
    
    # Check if user has an active private chat
    c.execute("SELECT hsm_number, channel_id, voice_channel_id FROM private_chats WHERE creator_id = ? AND is_active = 1", (user_id,))
    chat_data = c.fetchone()
    
    if not chat_data:
        await interaction.response.send_message("❌ You don't have any active private chats to delete!", ephemeral=True)
        return
    
    hsm_number, channel_id, voice_channel_id = chat_data
    
    try:
        # Delete text channel
        channel = interaction.guild.get_channel(int(channel_id))
        if channel:
            await channel.delete(reason=f"HSM{hsm_number} private chat deleted by owner")
        
        # Delete voice channel
        voice_channel = interaction.guild.get_channel(int(voice_channel_id))
        if voice_channel:
            await voice_channel.delete(reason=f"HSM{hsm_number} private chat deleted by owner")
        
        # Mark as inactive in database
        c.execute("UPDATE private_chats SET is_active = 0 WHERE hsm_number = ?", (hsm_number,))
        conn.commit()
        
        # Remove from memory
        if hsm_number in private_chats:
            del private_chats[hsm_number]
        used_hsm_numbers.discard(hsm_number)
        
        await interaction.response.send_message(f"✅ **HSM{hsm_number} private chat deleted successfully!**", ephemeral=True)
        
    except Exception as e:
        await interaction.response.send_message(f"❌ Error deleting private chat: {e}", ephemeral=True)

def generate_hsm_number():
    """Generate a unique HSM number from 1 to 9999"""
    # Load existing numbers from database
    c.execute("SELECT hsm_number FROM private_chats WHERE is_active = 1")
    active_numbers = set(row[0] for row in c.fetchall())
    used_hsm_numbers.update(active_numbers)
    
    # Find available number
    for num in range(1, 10000):
        if num not in used_hsm_numbers:
            return num
    
    return None  # All numbers are used

def generate_match_hsm_number():
    """Generate a unique HSM number for match channels from 1 to 9999"""
    # Get all used HSM numbers from both private chats and active matches
    c.execute("SELECT hsm_number FROM private_chats WHERE is_active = 1")
    used_private = {row[0] for row in c.fetchall()}
    
    # Get HSM numbers from active matches
    used_matches = {match.get('hsm_number') for match in active_matches.values() if match.get('hsm_number')}
    
    # Combine all used numbers
    used_numbers = used_private | used_matches
    
    # Find the first available number
    for num in range(1, 10000):
        if num not in used_numbers:
            return num
    
    # If all numbers are used (very unlikely), return None
    return None

# Private match channel functions removed - simplified queue system

# Automatic Queue Timeout System
QUEUE_TIMEOUT_MINUTES = 5

@tasks.loop(minutes=1)
async def check_queue_timeout():
    """Check if queue should be cleared due to inactivity"""
    global player_queue, queue_last_activity
    
    if not player_queue:
        return  # No players in queue
    
    if queue_last_activity is None:
        return  # No activity timestamp recorded
    
    # Check if queue has been inactive for more than 5 minutes
    current_time = datetime.now()
    time_since_activity = current_time - queue_last_activity
    
    if time_since_activity >= timedelta(minutes=QUEUE_TIMEOUT_MINUTES):
        # Queue has been inactive for 5+ minutes, clear it
        await clear_inactive_queue()

async def clear_inactive_queue():
    """Clear queue due to inactivity and notify players"""
    global player_queue, queue_last_activity
    
    if not player_queue:
        return
    
    # Store queue data before clearing
    inactive_players = player_queue.copy()
    queue_count = len(player_queue)
    
    # Clear queue and reset activity
    player_queue.clear()
    queue_last_activity = None
    
    # No need to clean up private match channels since we removed them
    
    # Find queue channel and send notification
    for guild in bot.guilds:
        queue_channel = discord.utils.get(guild.channels, name=QUEUE_CHANNEL_NAME)
        if queue_channel:
            # Create timeout notification embed
            embed = discord.Embed(
                title="⏰ Queue Timeout - Automatic Cleanup",
                description=f"**Queue has been automatically cleared due to {QUEUE_TIMEOUT_MINUTES} minutes of inactivity!**",
                color=discord.Color.orange()
            )
            embed.add_field(name="Players Removed", value=f"**{queue_count}** players", inline=True)
            embed.add_field(name="Reason", value=f"No activity for {QUEUE_TIMEOUT_MINUTES} minutes", inline=True)
            embed.add_field(name="Queue Status", value="**CLEARED**", inline=True)
            
            # List removed players
            if inactive_players:
                player_list = []
                for player in inactive_players:
                    player_list.append(f"• {player['username']} ({player['mmr']} MMR)")
                
                if player_list:
                    embed.add_field(
                        name="Removed Players",
                        value="\n".join(player_list[:10]),  # Limit to 10 players
                        inline=False
                    )
            
            embed.add_field(
                name="💡 Next Steps", 
                value="Players can rejoin the queue using the buttons below.\nQueue will reset its timer when new players join.",
                inline=False
            )
            embed.set_footer(text=f"Automatic cleanup after {QUEUE_TIMEOUT_MINUTES} minutes of inactivity")
            
            await queue_channel.send(embed=embed)
            
            # Update queue display
            await update_queue_display(queue_channel)
            
            print(f"Queue automatically cleared due to inactivity: {queue_count} players removed")
            break

def update_queue_activity():
    """Update the last activity timestamp for queue timeout"""
    global queue_last_activity
    queue_last_activity = datetime.now()

def is_queue_channel(channel):
    """Check if the command is being used in the correct channel"""
    return channel.name == QUEUE_CHANNEL_NAME

# Advanced match creation with voice channels and dedicated channels
async def create_match(queue_channel, guild):
    """Show team selection options when queue is complete"""
    global match_id_counter, player_queue
    
    # Get 4 players from queue
    match_players = player_queue[:4]
    player_queue = player_queue[4:]
    
    # Generate HSM number for the match
    hsm_number = generate_match_hsm_number()
    if not hsm_number:
        await queue_channel.send("❌ No available HSM numbers for match creation!")
        return
    
    # Store team selection data
    pending_team_selection[hsm_number] = {
        'players': match_players,
        'guild': guild,
        'queue_channel': queue_channel,
        'timestamp': datetime.now()
    }
    
    # Create team selection embed
    embed = discord.Embed(
        title="🎮 Queue Complete - Team Selection",
        description=f"**4 players found! Choose your team distribution method:**\n\n**Match: HSM{hsm_number}**",
        color=discord.Color.gold()
    )
    
    # List all players
    player_list = []
    for i, player in enumerate(match_players, 1):
        player_list.append(f"{i}. **{player['username']}** ({player['mmr']} MMR)")
    
    embed.add_field(
        name="👥 Players Found",
        value="\n".join(player_list),
        inline=False
    )
    
    embed.add_field(
        name="🎲 Random Teams",
        value="Bot will randomly distribute players into balanced teams",
        inline=True
    )
    
    embed.add_field(
        name="👑 Captain Draft",
        value="Top 2 MMR players become captains and draft their teams",
        inline=True
    )
    
    embed.add_field(
        name="⏰ Time Limit",
        value="5 minutes to choose or match will use random teams",
        inline=False
    )
    
    embed.set_footer(text="Only the queued players can select the team distribution method")
    
    # Send with team selection buttons
    view = TeamSelectionView(match_players, hsm_number)
    await queue_channel.send(embed=embed, view=view)
    
    # Update queue display
    await update_queue_display(queue_channel)

# Team selection handler functions
async def handle_random_team_selection(interaction: discord.Interaction, players, hsm_number):
    """Handle random team selection"""
    # Check if user is one of the queued players
    user_id = str(interaction.user.id)
    if not any(p['id'] == user_id for p in players):
        await interaction.response.send_message("❌ Only queued players can select team distribution!", ephemeral=True)
        return
    
    # Create teams randomly
    teams = create_balanced_teams(players)
    team1, team2 = teams
    
    await interaction.response.send_message("🎲 Random team distribution selected! Creating match...", ephemeral=True)
    
    # Create the match with the selected teams
    await create_final_match(interaction.guild, players, team1, team2, hsm_number, "🎲 Random Distribution")

async def handle_captain_draft_selection(interaction: discord.Interaction, players, hsm_number):
    """Handle captain draft selection"""
    print(f"[DEBUG] Captain draft selection - Players: {len(players)}, HSM: {hsm_number}")
    
    # Check if user is one of the queued players
    user_id = str(interaction.user.id)
    if not any(p['id'] == user_id for p in players):
        await interaction.response.send_message("❌ Only queued players can select team distribution!", ephemeral=True)
        return
    
    # Sort players by MMR to get captains (top 2 players)
    sorted_players = sorted(players, key=lambda p: p['mmr'], reverse=True)
    captain1 = sorted_players[0]
    captain2 = sorted_players[1]
    available_players = sorted_players[2:]  # Remaining 2 players
    
    print(f"[DEBUG] Captain 1: {captain1['username']} ({captain1['mmr']} MMR)")
    print(f"[DEBUG] Captain 2: {captain2['username']} ({captain2['mmr']} MMR)")
    print(f"[DEBUG] Available players: {[p['username'] for p in available_players]}")
    
    # Create draft state
    draft_id = f"draft_{hsm_number}"
    # For 2v2, we have 2 captains and 2 available players
    # Each captain picks once: [0, 1] for 2 total picks
    pick_order = [0, 1]  # Captain 1 picks first, then Captain 2
    
    captain_draft_state[draft_id] = {
        'hsm_number': hsm_number,
        'captains': [captain1, captain2],
        'current_captain': 0,  # Start with first captain
        'team1': [captain1],
        'team2': [captain2],
        'available_players': available_players,
        'pick_order': pick_order,
        'current_pick': 0,
        'all_players': players
    }
    
    print(f"[DEBUG] Created draft state: {draft_id}")
    
    await interaction.response.send_message("👑 Captain draft selected! Starting draft...", ephemeral=True)
    
    # Create draft embed
    embed = discord.Embed(
        title="👑 Captain Draft - Team Selection",
        description=f"**Match: HSM{hsm_number}**\n\nCaptains will draft their teams!",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="🔴 Team 1 Captain",
        value=f"**{captain1['username']}** ({captain1['mmr']} MMR)",
        inline=True
    )
    
    embed.add_field(
        name="🔵 Team 2 Captain",
        value=f"**{captain2['username']}** ({captain2['mmr']} MMR)",
        inline=True
    )
    
    embed.add_field(
        name="📋 Draft Order",
        value="Captain 1 → Captain 2 (each picks once)",
        inline=False
    )
    
    current_captain = captain_draft_state[draft_id]['captains'][0]
    embed.add_field(
        name="🎯 Current Turn",
        value=f"**{current_captain['username']}** - choose your first teammate!",
        inline=False
    )
    
    # Send draft interface
    try:
        view = CaptainDraftView(draft_id, 0, available_players)
        await interaction.followup.send(embed=embed, view=view)
        print(f"[DEBUG] Draft interface sent successfully")
    except Exception as e:
        print(f"[DEBUG] Error sending draft interface: {e}")
        await interaction.followup.send(f"❌ Error creating draft interface: {e}", ephemeral=True)

async def handle_captain_pick(interaction: discord.Interaction, draft_id, player_id):
    """Handle captain player pick"""
    print(f"[DEBUG] Captain pick - Draft ID: {draft_id}, Player ID: {player_id}")
    
    draft_state = captain_draft_state.get(draft_id)
    if not draft_state:
        print(f"[DEBUG] Draft session not found: {draft_id}")
        await interaction.response.send_message("❌ Draft session not found!", ephemeral=True)
        return
    
    print(f"[DEBUG] Draft state found - Current pick: {draft_state['current_pick']}")
    print(f"[DEBUG] Available players: {[p['username'] for p in draft_state['available_players']]}")
    
    # Find the picked player
    picked_player = None
    for player in draft_state['available_players']:
        if player['id'] == player_id:
            picked_player = player
            break
    
    if not picked_player:
        print(f"[DEBUG] Player not available for picking: {player_id}")
        await interaction.response.send_message("❌ Player not available for picking!", ephemeral=True)
        return
    
    print(f"[DEBUG] Player picked: {picked_player['username']}")
    
    # Add player to current captain's team
    current_captain_idx = draft_state['current_captain']
    if current_captain_idx == 0:
        draft_state['team1'].append(picked_player)
        print(f"[DEBUG] Added {picked_player['username']} to Team 1")
    else:
        draft_state['team2'].append(picked_player)
        print(f"[DEBUG] Added {picked_player['username']} to Team 2")
    
    # Remove from available players
    draft_state['available_players'].remove(picked_player)
    
    # Move to next pick
    draft_state['current_pick'] += 1
    
    print(f"[DEBUG] Current pick now: {draft_state['current_pick']}")
    print(f"[DEBUG] Pick order length: {len(draft_state['pick_order'])}")
    
    # Check if draft is complete
    if draft_state['current_pick'] >= len(draft_state['pick_order']):
        # Draft complete - create match
        print(f"[DEBUG] Draft complete! Creating match...")
        print(f"[DEBUG] Team 1: {[p['username'] for p in draft_state['team1']]}")
        print(f"[DEBUG] Team 2: {[p['username'] for p in draft_state['team2']]}")
        
        await interaction.response.send_message("🎉 Draft complete! Creating match...", ephemeral=True)
        
        # Create the match
        try:
            await create_final_match(
                interaction.guild,
                draft_state['all_players'],
                draft_state['team1'],
                draft_state['team2'],
                draft_state['hsm_number'],
                "👑 Captain Draft"
            )
            print(f"[DEBUG] Match created successfully")
        except Exception as e:
            print(f"[DEBUG] Error creating match: {e}")
            await interaction.followup.send(f"❌ Error creating match: {e}")
            return
        
        # Clean up draft state
        del captain_draft_state[draft_id]
        return
    
    # Continue draft
    draft_state['current_captain'] = draft_state['pick_order'][draft_state['current_pick']]
    current_captain = draft_state['captains'][draft_state['current_captain']]
    
    # Update the draft display
    embed = discord.Embed(
        title="👑 Captain Draft - Team Selection",
        description=f"**Match: HSM{draft_state['hsm_number']}**\n\n**{picked_player['username']}** picked!",
        color=discord.Color.purple()
    )
    
    team1_names = [p['username'] for p in draft_state['team1']]
    team2_names = [p['username'] for p in draft_state['team2']]
    
    embed.add_field(
        name="🔴 Team 1",
        value="\n".join([f"• {name}" for name in team1_names]),
        inline=True
    )
    
    embed.add_field(
        name="🔵 Team 2",
        value="\n".join([f"• {name}" for name in team2_names]),
        inline=True
    )
    
    embed.add_field(
        name="🎯 Current Turn",
        value=f"**{current_captain['username']}** - choose your next teammate!",
        inline=False
    )
    
    # Send updated draft interface
    view = CaptainDraftView(draft_id, draft_state['current_captain'], draft_state['available_players'])
    await interaction.response.edit_message(embed=embed, view=view)

async def create_final_match(guild, all_players, team1, team2, hsm_number, distribution_method):
    """Create the final match with HSM number and private permissions"""
    global match_id_counter
    
    # Create match record
    match_id = match_id_counter
    match_id_counter += 1
    
    # Get or create match category
    category = discord.utils.get(guild.categories, name=MATCH_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(
            name=MATCH_CATEGORY_NAME,
            reason="HeatSeeker match category"
        )
    
    # Create permission overwrites for private match channel
    # Only allow match participants to see the channel
    overwrites = {
        guild.default_role: discord.PermissionOverwrite(read_messages=False),
        guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }
    
    # Add permissions for all match participants
    for player in all_players:
        member = player['user']
        overwrites[member] = discord.PermissionOverwrite(read_messages=True, send_messages=True)
    
    # Create dedicated private text channel for the match
    match_channel = await guild.create_text_channel(
        name=f"hsm{hsm_number}",
        category=category,
        topic=f"HeatSeeker Match HSM{hsm_number} - Private Match Channel",
        overwrites=overwrites
    )
    
    # Create voice channels for each team with same permissions
    team1_voice = await guild.create_voice_channel(
        name=f"🔴 Team 1 - HSM{hsm_number}",
        category=category,
        user_limit=2,
        overwrites=overwrites
    )
    
    team2_voice = await guild.create_voice_channel(
        name=f"🔵 Team 2 - HSM{hsm_number}",
        category=category,
        user_limit=2,
        overwrites=overwrites
    )
    
    # Store match data with HSM number
    active_matches[match_id] = {
        'team1': team1,
        'team2': team2,
        'players': [p['id'] for p in all_players],
        'channel_id': str(match_channel.id),
        'team1_voice_id': str(team1_voice.id),
        'team2_voice_id': str(team2_voice.id),
        'hsm_number': hsm_number,
        'distribution_method': distribution_method,
        'created_at': datetime.now().isoformat()
    }
    
    # Save to database with error handling
    try:
        team1_ids = ','.join([p['id'] for p in team1])
        team2_ids = ','.join([p['id'] for p in team2])
        c.execute("""INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id) 
                     VALUES (?, ?, ?, ?, ?)""", 
                  (match_id, team1_ids, team2_ids, datetime.now().isoformat(), str(match_channel.id)))
        conn.commit()
        print(f"[DEBUG] Match {match_id} saved to database successfully")
    except Exception as e:
        print(f"[DEBUG] Database error saving match: {e}")
        # If database insert fails, try to get a new unique match_id
        c.execute("SELECT MAX(match_id) FROM matches")
        result = c.fetchone()
        if result and result[0] is not None:
            match_id = result[0] + 1
            match_id_counter = match_id + 1
            # Update the active_matches with new match_id
            active_matches[match_id] = active_matches.pop(match_id_counter - 1)
            # Try insert again with new match_id
            try:
                c.execute("""INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id) 
                             VALUES (?, ?, ?, ?, ?)""", 
                          (match_id, team1_ids, team2_ids, datetime.now().isoformat(), str(match_channel.id)))
                conn.commit()
                print(f"[DEBUG] Match {match_id} saved to database successfully (retry)")
            except Exception as e2:
                print(f"[DEBUG] Database error on retry: {e2}")
                raise e2
        else:
            raise e
    
    # Find queue channel to send announcement
    queue_channel = discord.utils.get(guild.channels, name=QUEUE_CHANNEL_NAME)
    if queue_channel:
        # Create professional match announcement
        embed = discord.Embed(
            title="🏆 MATCH CREATED!",
            description=f"**Match HSM{hsm_number}** is ready to begin!\n\n**Match Channel:** {match_channel.mention}\n**Team Distribution:** {distribution_method}",
            color=discord.Color.gold()
        )
        
        # Team 1 info
        team1_mentions = ' '.join([p['user'].mention for p in team1])
        team1_info = '\n'.join([f"• **{p['username']}** ({p['mmr']} MMR)" for p in team1])
        embed.add_field(
            name="🔴 Team 1",
            value=f"{team1_mentions}\n{team1_info}\n**Voice:** {team1_voice.mention}",
            inline=True
        )
        
        # Team 2 info
        team2_mentions = ' '.join([p['user'].mention for p in team2])
        team2_info = '\n'.join([f"• **{p['username']}** ({p['mmr']} MMR)" for p in team2])
        embed.add_field(
            name="🔵 Team 2",
            value=f"{team2_mentions}\n{team2_info}\n**Voice:** {team2_voice.mention}",
            inline=True
        )
        
        # Match stats
        avg_mmr = sum(p['mmr'] for p in all_players) / 4
        embed.add_field(
            name="📊 Match Statistics",
            value=f"**Average MMR:** {avg_mmr:.0f}\n**Match ID:** {match_id}\n**HSM Number:** {hsm_number}",
            inline=False
        )
        
        embed.add_field(
            name="🔒 Private Match",
            value="This match channel is private and only visible to participants.",
            inline=False
        )
        
        embed.set_footer(text="Join your team's voice channel and head to the match channel to start!")
        
        # Send to queue channel
        await queue_channel.send(embed=embed)
        
        # Update queue display
        await update_queue_display(queue_channel)
    
    # Send welcome message to private match channel
    welcome_embed = discord.Embed(
        title=f"🎮 Welcome to Match HSM{hsm_number}!",
        description=f"**Get ready for an epic 2v2 battle!**\n\n**Team Distribution:** {distribution_method}",
        color=discord.Color.purple()
    )
    
    welcome_embed.add_field(
        name="🔴 Team 1",
        value=f"{team1_mentions}\n**Voice Channel:** {team1_voice.mention}",
        inline=True
    )
    
    welcome_embed.add_field(
        name="🔵 Team 2",
        value=f"{team2_mentions}\n**Voice Channel:** {team2_voice.mention}",
        inline=True
    )
    
    welcome_embed.add_field(
        name="📝 How to Report Results",
        value="Click the buttons below when your match is complete!\nOnly match participants can report results.",
        inline=False
    )
    
    welcome_embed.add_field(
        name="🔒 Private Channel",
        value="This channel is private and only visible to match participants.",
        inline=False
    )
    
    # Send with match buttons
    view = MatchView(match_id)
    await match_channel.send(embed=welcome_embed, view=view)
    
    # Clean up pending team selection
    if hsm_number in pending_team_selection:
        del pending_team_selection[hsm_number]
    
    # No need to clean up private match channels since we removed them

async def post_match_to_results_channel_with_data(guild, match_id, winning_team, losing_team, mmr_changes, match_data):
    """Post completed match to results channel with admin modification buttons using provided match data"""
    try:
        # Find the results channel
        results_channel = discord.utils.get(guild.text_channels, name=RESULTS_CHANNEL_NAME)
        if not results_channel:
            print(f"[DEBUG] Results channel not found, skipping results post")
            return
        
        hsm_number = match_data.get('hsm_number', 'N/A')
        distribution_method = match_data.get('distribution_method', 'Unknown')
        
        # Create completed match embed
        embed = discord.Embed(
            title=f"🏆 Match #{match_id} - HSM{hsm_number} Completed",
            description=f"**Match finished!** Team selection: {distribution_method}",
            color=discord.Color.green()
        )
        
        # Winner info
        winner_names = [p['username'] for p in winning_team]
        winner_avg_mmr = sum(p['mmr'] for p in winning_team) / len(winning_team)
        embed.add_field(
            name="🎉 Winners",
            value=f"**Players:** {', '.join(winner_names)}\n**Avg MMR:** {winner_avg_mmr:.0f}\n**MMR Change:** +{mmr_changes['winners']}",
            inline=True
        )
        
        # Loser info
        loser_names = [p['username'] for p in losing_team]
        loser_avg_mmr = sum(p['mmr'] for p in losing_team) / len(losing_team)
        embed.add_field(
            name="💔 Losers",
            value=f"**Players:** {', '.join(loser_names)}\n**Avg MMR:** {loser_avg_mmr:.0f}\n**MMR Change:** {mmr_changes['losers']}",
            inline=True
        )
        
        # Match details
        embed.add_field(
            name="📊 Match Details",
            value=f"**Match ID:** #{match_id}\n**HSM Number:** {hsm_number}\n**Distribution:** {distribution_method}\n**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            inline=False
        )
        
        embed.add_field(
            name="🔧 Admin Controls",
            value="Administrators can modify this match result using the buttons below if needed.",
            inline=False
        )
        
        embed.set_footer(text="Only administrators can modify completed matches")
        
        # Create admin modification buttons
        view = CompletedMatchAdminView(match_id)
        await results_channel.send(embed=embed, view=view)
        
        print(f"[DEBUG] Posted completed match {match_id} to results channel")
        
    except Exception as e:
        print(f"[DEBUG] Error posting match to results channel: {e}")

class CompletedMatchAdminView(discord.ui.View):
    """Admin controls for completed matches in results channel"""
    
    def __init__(self, match_id):
        super().__init__(timeout=None)  # Persistent view
        self.match_id = match_id
    
    @discord.ui.button(label="🔄 Set Team 1 Winner", style=discord.ButtonStyle.primary)
    async def set_team1_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Admin: Set Team 1 as winner"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can modify match results!", ephemeral=True)
            return
        
        await self.modify_match_result(interaction, 1, "Team 1")
    
    @discord.ui.button(label="🔄 Set Team 2 Winner", style=discord.ButtonStyle.primary)
    async def set_team2_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Admin: Set Team 2 as winner"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can modify match results!", ephemeral=True)
            return
        
        await self.modify_match_result(interaction, 2, "Team 2")
    
    @discord.ui.button(label="🤝 Set Tie", style=discord.ButtonStyle.secondary)
    async def set_tie(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Admin: Set match as tie"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can modify match results!", ephemeral=True)
            return
        
        await self.modify_match_result(interaction, 0, "Tie")
    
    @discord.ui.button(label="🚫 Cancel Match", style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        """Admin: Cancel match entirely"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message("❌ Only administrators can modify match results!", ephemeral=True)
            return
        
        await self.modify_match_result(interaction, -1, "Cancelled")
    
    async def modify_match_result(self, interaction: discord.Interaction, winner_team: int, action_name: str):
        """Modify the match result in database and update the embed"""
        try:
            # Get original match data from database
            c.execute("SELECT team1_players, team2_players, winner FROM matches WHERE match_id = ?", (self.match_id,))
            result = c.fetchone()
            
            if not result:
                await interaction.response.send_message("❌ Match not found in database!", ephemeral=True)
                return
            
            team1_ids, team2_ids, current_winner = result
            team1_ids = team1_ids.split(',')
            team2_ids = team2_ids.split(',')
            
            # Revert previous changes first
            if current_winner == 1:  # Team 1 won previously
                for player_id in team1_ids:
                    c.execute("UPDATE players SET wins = wins - 1, mmr = mmr - 25 WHERE id = ?", (player_id,))
                for player_id in team2_ids:
                    c.execute("UPDATE players SET losses = losses - 1, mmr = mmr + 25 WHERE id = ?", (player_id,))
            elif current_winner == 2:  # Team 2 won previously
                for player_id in team2_ids:
                    c.execute("UPDATE players SET wins = wins - 1, mmr = mmr - 25 WHERE id = ?", (player_id,))
                for player_id in team1_ids:
                    c.execute("UPDATE players SET losses = losses - 1, mmr = mmr + 25 WHERE id = ?", (player_id,))
            
            # Apply new changes
            if winner_team == 1:  # Team 1 wins
                for player_id in team1_ids:
                    c.execute("UPDATE players SET wins = wins + 1, mmr = mmr + 25 WHERE id = ?", (player_id,))
                for player_id in team2_ids:
                    c.execute("UPDATE players SET losses = losses + 1, mmr = mmr - 25 WHERE id = ?", (player_id,))
            elif winner_team == 2:  # Team 2 wins
                for player_id in team2_ids:
                    c.execute("UPDATE players SET wins = wins + 1, mmr = mmr + 25 WHERE id = ?", (player_id,))
                for player_id in team1_ids:
                    c.execute("UPDATE players SET losses = losses + 1, mmr = mmr - 25 WHERE id = ?", (player_id,))
            # winner_team == 0 (tie) or -1 (cancelled) = no MMR changes
            
            # Update match record
            cancelled = 1 if winner_team == -1 else 0
            c.execute("UPDATE matches SET winner = ?, admin_modified = 1, cancelled = ? WHERE match_id = ?", 
                     (winner_team, cancelled, self.match_id))
            conn.commit()
            
            # Update the embed
            embed = discord.Embed(
                title=f"🔧 Match #{self.match_id} - Admin Modified",
                description=f"**Match result changed to: {action_name}**\n\nModified by: {interaction.user.mention}",
                color=discord.Color.orange()
            )
            
            embed.add_field(
                name="📝 Action Taken",
                value=f"**Result:** {action_name}\n**Modified By:** {interaction.user.display_name}\n**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False
            )
            
            embed.set_footer(text="Match has been modified by administrator")
            
            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)
            
            print(f"[DEBUG] Admin {interaction.user.display_name} modified match {self.match_id} to {action_name}")
            
        except Exception as e:
            print(f"[DEBUG] Error modifying match {self.match_id}: {e}")
            await interaction.response.send_message(f"❌ Error modifying match: {e}", ephemeral=True)

async def cleanup_match_with_data(guild, match_id, match_data):
    """Clean up match channels and voice channels after match completion using provided match data"""
    hsm_number = match_data.get('hsm_number')
    
    try:
        # Delete match text channel
        match_channel = guild.get_channel(int(match_data['channel_id']))
        if match_channel:
            await match_channel.delete(reason=f"Match HSM{hsm_number} completed")
            log_match_event("CLEANUP", f"Match {match_id}", f"Deleted match channel HSM{hsm_number}")
        
        # Delete voice channels
        team1_voice = guild.get_channel(int(match_data['team1_voice_id']))
        if team1_voice:
            await team1_voice.delete(reason=f"Match HSM{hsm_number} completed")
            log_match_event("CLEANUP", f"Match {match_id}", f"Deleted Team 1 voice channel HSM{hsm_number}")
        
        team2_voice = guild.get_channel(int(match_data['team2_voice_id']))
        if team2_voice:
            await team2_voice.delete(reason=f"Match HSM{hsm_number} completed")
            log_match_event("CLEANUP", f"Match {match_id}", f"Deleted Team 2 voice channel HSM{hsm_number}")
        
        # No need to clean up private match channels since we removed them
        
    except Exception as e:
        print(f"Error cleaning up match {match_id} (HSM{hsm_number}): {e}")
        log_match_event("ERROR", f"Match {match_id}", f"Cleanup error: {e}")

async def cleanup_match(guild, match_id):
    """Clean up match channels and voice channels after match completion (legacy function)"""
    if match_id not in active_matches:
        return
    
    match_data = active_matches[match_id]
    hsm_number = match_data.get('hsm_number')
    
    try:
        # Delete match text channel
        match_channel = guild.get_channel(int(match_data['channel_id']))
        if match_channel:
            await match_channel.delete(reason=f"Match HSM{hsm_number} completed")
        
        # Delete voice channels
        team1_voice = guild.get_channel(int(match_data['team1_voice_id']))
        if team1_voice:
            await team1_voice.delete(reason=f"Match HSM{hsm_number} completed")
        
        team2_voice = guild.get_channel(int(match_data['team2_voice_id']))
        if team2_voice:
            await team2_voice.delete(reason=f"Match HSM{hsm_number} completed")
        
        # No need to clean up private match channels since we removed them
        
    except Exception as e:
        print(f"Error cleaning up match {match_id} (HSM{hsm_number}): {e}")
    
    # Remove from active matches
    del active_matches[match_id]

async def update_queue_display(channel):
    """Update the queue display with current players"""
    # Find and delete ALL bot messages with queue info to prevent duplicates
    messages_to_delete = []
    async for message in channel.history(limit=50):
        if message.author == bot.user and message.embeds:
            embed = message.embeds[0]
            if "Queue Status" in embed.title or "HeatSeeker Queue" in embed.title:
                messages_to_delete.append(message)
    
    # Delete all found queue messages
    for message in messages_to_delete:
        try:
            await message.delete()
        except:
            pass
    
    # Create updated queue display
    if not player_queue:
        embed = discord.Embed(
            title="🎮 HeatSeeker Queue",
            description="**No players in queue**\nClick **🎮 Join Queue** to get started!",
            color=discord.Color.blue()
        )
        embed.add_field(name="⏰ Queue Timeout", value=f"{QUEUE_TIMEOUT_MINUTES} minutes of inactivity", inline=True)
    else:
        embed = discord.Embed(
            title="🎮 HeatSeeker Queue",
            description=f"**{len(player_queue)}/4** players ready",
            color=discord.Color.orange()
        )
        
        queue_text = ""
        for i, player in enumerate(player_queue, 1):
            queue_text += f"{i}. **{player['username']}** ({player['mmr']} MMR)\n"
        
        embed.add_field(name="Players in Queue", value=queue_text, inline=False)
        
        # Show time remaining if there's activity
        if queue_last_activity:
            time_elapsed = datetime.now() - queue_last_activity
            time_remaining = timedelta(minutes=QUEUE_TIMEOUT_MINUTES) - time_elapsed
            if time_remaining.total_seconds() > 0:
                minutes_remaining = int(time_remaining.total_seconds() // 60)
                seconds_remaining = int(time_remaining.total_seconds() % 60)
                embed.add_field(name="⏳ Time Remaining", value=f"{minutes_remaining}m {seconds_remaining}s", inline=True)
            else:
                embed.add_field(name="⏳ Time Remaining", value="Clearing soon...", inline=True)
        
        embed.add_field(name="⏰ Timeout", value=f"{QUEUE_TIMEOUT_MINUTES} min inactivity", inline=True)
    
    view = QueueView()
    await channel.send(embed=embed, view=view)

@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    add_sample_data()
    logger.info("Sample data added to database")
    initialize_match_counter()
    restore_active_matches()
    logger.info(f"Queue system will only work in channel: #{QUEUE_CHANNEL_NAME}")
    
    # Add persistent views
    bot.add_view(QueueView())
    bot.add_view(MatchView(None))  # Add as persistent view
    bot.add_view(PrivateChatView())  # Add private chat view
    logger.info("Persistent views added for queue, match, and private chat systems")
    
    # Start the queue timeout check task
    if not check_queue_timeout.is_running():
        check_queue_timeout.start()
        logger.info(f"Started queue timeout system - {QUEUE_TIMEOUT_MINUTES} minute timeout")
    
    # Sync slash commands
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash commands")
    except Exception as e:
        logger.error(f"Failed to sync commands: {e}")
    
    # Initialize queue displays in all guilds
    for guild in bot.guilds:
        channel = discord.utils.get(guild.channels, name=QUEUE_CHANNEL_NAME)
        if channel:
            # Clear previous queue messages
            async for message in channel.history(limit=100):
                if message.author == bot.user:
                    try:
                        await message.delete()
                    except:
                        pass
            
            # Send professional startup message with buttons
            embed = discord.Embed(
                title="🔥 HeatSeeker Bot - Professional 2v2 Queue System",
                description="**Welcome to the ultimate competitive gaming experience!**\n\nUse the buttons below to interact with the queue system.",
                color=discord.Color.gold()
            )
            
            embed.add_field(
                name="🎮 How It Works",
                value="• Click **🎮 Join Queue** to enter the 2v2 queue\n• When 4 players join, a match will be created automatically\n• Each match gets dedicated text and voice channels\n• Teams are balanced based on MMR for fair gameplay",
                inline=False
            )
            
            embed.add_field(
                name="🏆 Features",
                value="• **Dedicated match channels** for each game\n• **Team voice channels** (2 players max each)\n• **Automatic team balancing** based on skill\n• **Professional MMR tracking** system\n• **Auto-cleanup** after matches complete",
                inline=False
            )
            
            embed.set_footer(text="Ready to play? Click the buttons below to get started!")
            
            # Send initial queue display with buttons
            view = QueueView()
            await channel.send(embed=embed, view=view)
            
            # Send queue status
            await update_queue_display(channel)

# إضافة أو تحديث لاعب
def add_or_update_player(user):
    c.execute("SELECT * FROM players WHERE id = ?", (str(user.id),))
    result = c.fetchone()
    if not result:
        c.execute("INSERT INTO players (id, username) VALUES (?, ?)", (str(user.id), user.name))
        conn.commit()

# أمر عرض الرانك
@bot.tree.command(name='rank', description='Display your current rank and stats')
async def rank(interaction: discord.Interaction):
    """Display your current rank and stats"""
    add_or_update_player(interaction.user)
    c.execute("SELECT mmr, wins, losses FROM players WHERE id = ?", (str(interaction.user.id),))
    result = c.fetchone()
    
    if result:
        mmr, wins, losses = result
        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        
        embed = discord.Embed(
            title=f"🏆 {interaction.user.name}'s Rank",
            color=discord.Color.blue()
        )
        embed.add_field(name="MMR", value=f"**{mmr}**", inline=True)
        embed.add_field(name="Wins", value=f"**{wins}**", inline=True)
        embed.add_field(name="Losses", value=f"**{losses}**", inline=True)
        embed.add_field(name="Win Rate", value=f"**{win_rate:.1f}%**", inline=True)
        embed.add_field(name="Total Games", value=f"**{total_games}**", inline=True)
        
        await interaction.response.send_message(embed=embed)
    else:
        await interaction.response.send_message("❌ Error retrieving your stats. Please try again.")

# Leaderboard pagination view
class LeaderboardView(discord.ui.View):
    def __init__(self, current_page=1):
        super().__init__(timeout=300)
        self.current_page = current_page
        self.items_per_page = 10
    
    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_leaderboard(interaction)
        else:
            await interaction.response.send_message("❌ You're already on the first page!", ephemeral=True)
    
    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction, button: discord.ui.Button):
        # Check if there are more pages
        c.execute("SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0")
        total_active_players = c.fetchone()[0]
        total_pages = (total_active_players + self.items_per_page - 1) // self.items_per_page
        
        if self.current_page < total_pages:
            self.current_page += 1
            await self.update_leaderboard(interaction)
        else:
            await interaction.response.send_message("❌ You're already on the last page!", ephemeral=True)
    
    async def update_leaderboard(self, interaction: discord.Interaction):
        """Update the leaderboard display"""
        # Get only players who have played at least one match
        offset = (self.current_page - 1) * self.items_per_page
        c.execute("""
            SELECT username, mmr, wins, losses 
            FROM players 
            WHERE wins > 0 OR losses > 0 
            ORDER BY mmr DESC 
            LIMIT ? OFFSET ?
        """, (self.items_per_page, offset))
        
        page_players = c.fetchall()
        
        # Get total count for pagination info
        c.execute("SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0")
        total_active_players = c.fetchone()[0]
        total_pages = (total_active_players + self.items_per_page - 1) // self.items_per_page
        
        if page_players:
            embed = discord.Embed(
                title="🏆 HeatSeeker Leaderboard",
                description=f"**Active Players Only** (Page {self.current_page}/{total_pages})",
                color=discord.Color.gold()
            )
            
            leaderboard_text = ""
            for i, (username, mmr, wins, losses) in enumerate(page_players):
                rank = offset + i + 1
                
                # Special medals for top 3 overall
                if rank == 1:
                    medal = "🥇"
                elif rank == 2:
                    medal = "🥈"
                elif rank == 3:
                    medal = "🥉"
                else:
                    medal = f"**{rank}.**"
                
                total_games = wins + losses
                win_rate = (wins / total_games * 100) if total_games > 0 else 0
                
                leaderboard_text += f"{medal} **{username}** - {mmr} MMR\n"
                leaderboard_text += f"     W: {wins} | L: {losses} | WR: {win_rate:.1f}%\n\n"
            
            embed.description += f"\n\n{leaderboard_text}"
            embed.set_footer(text=f"Showing {len(page_players)} players • Only players who have played matches are shown")
            
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="🏆 HeatSeeker Leaderboard",
                description="**No active players found!**\n\nPlay some matches to appear on the leaderboard.",
                color=discord.Color.gold()
            )
            await interaction.response.edit_message(embed=embed, view=None)

# أمر عرض التوب 10
@bot.tree.command(name='top', description='Display leaderboard of active players (paginated)')
async def top(interaction: discord.Interaction):
    """Display leaderboard of active players with pagination"""
    # Get only players who have played at least one match
    c.execute("""
        SELECT username, mmr, wins, losses 
        FROM players 
        WHERE wins > 0 OR losses > 0 
        ORDER BY mmr DESC 
        LIMIT 10
    """)
    
    top_players = c.fetchall()
    
    # Get total count for pagination info
    c.execute("SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0")
    total_active_players = c.fetchone()[0]
    total_pages = (total_active_players + 9) // 10  # Round up for 10 per page
    
    if top_players:
        embed = discord.Embed(
            title="🏆 HeatSeeker Leaderboard",
            description=f"**Active Players Only** (Page 1/{total_pages})",
            color=discord.Color.gold()
        )
        
        leaderboard_text = ""
        for i, (username, mmr, wins, losses) in enumerate(top_players):
            medal = "🥇" if i == 0 else "🥈" if i == 1 else "🥉" if i == 2 else f"**{i+1}.**"
            total_games = wins + losses
            win_rate = (wins / total_games * 100) if total_games > 0 else 0
            
            leaderboard_text += f"{medal} **{username}** - {mmr} MMR\n"
            leaderboard_text += f"     W: {wins} | L: {losses} | WR: {win_rate:.1f}%\n\n"
        
        embed.description += f"\n\n{leaderboard_text}"
        embed.set_footer(text=f"Showing {len(top_players)} players • Only players who have played matches are shown")
        
        # Add pagination view if there are more than 10 players
        if total_active_players > 10:
            view = LeaderboardView(current_page=1)
            await interaction.response.send_message(embed=embed, view=view)
        else:
            await interaction.response.send_message(embed=embed)
    else:
        embed = discord.Embed(
            title="🏆 HeatSeeker Leaderboard",
            description="**No active players found!**\n\nPlay some matches to appear on the leaderboard.\n\nUse `/queue` to join the 2v2 queue and start playing!",
            color=discord.Color.gold()
        )
        embed.set_footer(text="Leaderboard shows only players who have participated in matches")
        await interaction.response.send_message(embed=embed)

# Stats command
@bot.command(name='stats')
async def stats(ctx, member: discord.Member = None):
    """Display stats for a specific player"""
    target_user = member or ctx.author
    
    c.execute("SELECT username, mmr, wins, losses FROM players WHERE id = ?", (str(target_user.id),))
    result = c.fetchone()
    
    if result:
        username, mmr, wins, losses = result
        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0
        
        embed = discord.Embed(
            title=f"📊 {username}'s Statistics",
            color=discord.Color.green()
        )
        embed.add_field(name="MMR", value=f"**{mmr}**", inline=True)
        embed.add_field(name="Wins", value=f"**{wins}**", inline=True)
        embed.add_field(name="Losses", value=f"**{losses}**", inline=True)
        embed.add_field(name="Total Games", value=f"**{total_games}**", inline=True)
        embed.add_field(name="Win Rate", value=f"**{win_rate:.1f}%**", inline=True)
        
        # Calculate rank position
        c.execute("SELECT COUNT(*) FROM players WHERE mmr > ?", (mmr,))
        rank_position = c.fetchone()[0] + 1
        embed.add_field(name="Rank", value=f"**#{rank_position}**", inline=True)
        
        await ctx.send(embed=embed)
    else:
        await ctx.send(f"❌ No stats found for {target_user.mention}. Use `/rank` to initialize your profile.")

# Queue system commands
@bot.tree.command(name='queue', description='Join the 2v2 queue')
async def queue(interaction: discord.Interaction):
    """Join the 2v2 queue"""
    # Check if command is used in correct channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ Please use queue commands in #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return
    
    add_or_update_player(interaction.user)
    user_id = str(interaction.user.id)
    
    # Check if player is already in queue
    if any(player['id'] == user_id for player in player_queue):
        await interaction.response.send_message("❌ You are already in the queue!", ephemeral=True)
        return
    
    # Check if player is in an active match
    if any(user_id in match['players'] for match in active_matches.values()):
        await interaction.response.send_message("❌ You are currently in an active match!", ephemeral=True)
        return
    
    # Add player to queue
    c.execute("SELECT username, mmr FROM players WHERE id = ?", (user_id,))
    result = c.fetchone()
    if result:
        username, mmr = result
        player_queue.append({'id': user_id, 'username': username, 'mmr': mmr, 'user': interaction.user})
        
        embed = discord.Embed(
            title="🎮 Joined Queue",
            description=f"{interaction.user.mention} joined the 2v2 queue!",
            color=discord.Color.green()
        )
        embed.add_field(name="Players in Queue", value=f"{len(player_queue)}/4", inline=True)
        embed.add_field(name="Your MMR", value=f"{mmr}", inline=True)
        
        await interaction.response.send_message(embed=embed)
        
        # Check if we have 4 players to start a match
        if len(player_queue) >= 4:
            await start_match_slash(interaction)

@bot.tree.command(name='leave', description='Leave the 2v2 queue')
async def leave_queue(interaction: discord.Interaction):
    """Leave the queue"""
    # Check if command is used in correct channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ Please use queue commands in #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return
    
    user_id = str(interaction.user.id)
    
    # Remove player from queue
    global player_queue
    player_queue = [p for p in player_queue if p['id'] != user_id]
    
    embed = discord.Embed(
        title="🚪 Left Queue",
        description=f"{interaction.user.mention} left the queue.",
        color=discord.Color.orange()
    )
    embed.add_field(name="Players in Queue", value=f"{len(player_queue)}/4", inline=True)
    
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name='status', description='Show current queue status')
async def queue_status(interaction: discord.Interaction):
    """Show current queue status"""
    # Check if command is used in correct channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ Please use queue commands in #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return
    
    if not player_queue:
        embed = discord.Embed(
            title="📋 Queue Status",
            description="Queue is empty. Use `/queue` to join!",
            color=discord.Color.blue()
        )
    else:
        embed = discord.Embed(
            title="📋 Queue Status",
            description=f"Players in queue: {len(player_queue)}/4",
            color=discord.Color.blue()
        )
        
        queue_text = ""
        for i, player in enumerate(player_queue, 1):
            queue_text += f"{i}. {player['username']} ({player['mmr']} MMR)\n"
        
        embed.add_field(name="Players", value=queue_text, inline=False)
    
    await interaction.response.send_message(embed=embed)

async def start_match(ctx):
    """Start a 2v2 match with balanced teams"""
    global match_id_counter, player_queue
    
    # Get 4 players from queue
    match_players = player_queue[:4]
    player_queue = player_queue[4:]
    
    # Create balanced teams based on MMR
    teams = create_balanced_teams(match_players)
    team1, team2 = teams
    
    # Create match record
    match_id = match_id_counter
    match_id_counter += 1
    
    # Store match data
    active_matches[match_id] = {
        'team1': team1,
        'team2': team2,
        'players': [p['id'] for p in match_players],
        'channel_id': str(ctx.channel.id),
        'created_at': datetime.now().isoformat()
    }
    
    # Save to database
    team1_ids = ','.join([p['id'] for p in team1])
    team2_ids = ','.join([p['id'] for p in team2])
    c.execute("""INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id) 
                 VALUES (?, ?, ?, ?, ?)""", 
              (match_id, team1_ids, team2_ids, datetime.now().isoformat(), str(ctx.channel.id)))
    conn.commit()
    
    # Create match announcement
    embed = discord.Embed(
        title="🏆 MATCH FOUND!",
        description=f"Match #{match_id} is ready to start!",
        color=discord.Color.gold()
    )
    
    # Team 1
    team1_mentions = ' '.join([p['user'].mention for p in team1])
    team1_info = '\n'.join([f"{p['username']} ({p['mmr']} MMR)" for p in team1])
    embed.add_field(name="🔴 Team 1", value=f"{team1_mentions}\n{team1_info}", inline=True)
    
    # Team 2
    team2_mentions = ' '.join([p['user'].mention for p in team2])
    team2_info = '\n'.join([f"{p['username']} ({p['mmr']} MMR)" for p in team2])
    embed.add_field(name="🔵 Team 2", value=f"{team2_mentions}\n{team2_info}", inline=True)
    
    # Average MMR
    avg_mmr = sum(p['mmr'] for p in match_players) / 4
    embed.add_field(name="📊 Average MMR", value=f"{avg_mmr:.0f}", inline=False)
    
    embed.add_field(name="📝 Report Results", 
                   value=f"Use `/win 1` or `/win 2` to report the winning team\nMatch ID: {match_id}", 
                   inline=False)
    
    await ctx.send(embed=embed)

async def start_match_slash(interaction: discord.Interaction):
    """Start a 2v2 match with balanced teams (for slash commands)"""
    global match_id_counter, player_queue
    
    # Get 4 players from queue
    match_players = player_queue[:4]
    player_queue = player_queue[4:]
    
    # Create balanced teams based on MMR
    teams = create_balanced_teams(match_players)
    team1, team2 = teams
    
    # Create match record
    match_id = match_id_counter
    match_id_counter += 1
    
    # Store match data
    active_matches[match_id] = {
        'team1': team1,
        'team2': team2,
        'players': [p['id'] for p in match_players],
        'channel_id': str(interaction.channel.id),
        'created_at': datetime.now().isoformat()
    }
    
    # Save to database
    team1_ids = ','.join([p['id'] for p in team1])
    team2_ids = ','.join([p['id'] for p in team2])
    c.execute("""INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id) 
                 VALUES (?, ?, ?, ?, ?)""", 
              (match_id, team1_ids, team2_ids, datetime.now().isoformat(), str(interaction.channel.id)))
    conn.commit()
    
    # Create match announcement
    embed = discord.Embed(
        title="🏆 MATCH FOUND!",
        description=f"Match #{match_id} is ready to start!",
        color=discord.Color.gold()
    )
    
    # Team 1
    team1_mentions = ' '.join([p['user'].mention for p in team1])
    team1_info = '\n'.join([f"{p['username']} ({p['mmr']} MMR)" for p in team1])
    embed.add_field(name="🔴 Team 1", value=f"{team1_mentions}\n{team1_info}", inline=True)
    
    # Team 2
    team2_mentions = ' '.join([p['user'].mention for p in team2])
    team2_info = '\n'.join([f"{p['username']} ({p['mmr']} MMR)" for p in team2])
    embed.add_field(name="🔵 Team 2", value=f"{team2_mentions}\n{team2_info}", inline=True)
    
    # Average MMR
    avg_mmr = sum(p['mmr'] for p in match_players) / 4
    embed.add_field(name="📊 Average MMR", value=f"{avg_mmr:.0f}", inline=False)
    
    embed.add_field(name="📝 Report Results", 
                   value=f"Use `/win team:1` or `/win team:2` to report the winning team\nMatch ID: {match_id}", 
                   inline=False)
    
    await interaction.followup.send(embed=embed)

def create_balanced_teams(players):
    """Create balanced teams based on MMR"""
    # Sort players by MMR
    sorted_players = sorted(players, key=lambda x: x['mmr'], reverse=True)
    
    # Try different combinations to find the most balanced
    best_diff = float('inf')
    best_teams = None
    
    # Generate all possible team combinations
    for team1_combo in combinations(sorted_players, 2):
        team1 = list(team1_combo)
        team2 = [p for p in sorted_players if p not in team1]
        
        team1_mmr = sum(p['mmr'] for p in team1)
        team2_mmr = sum(p['mmr'] for p in team2)
        diff = abs(team1_mmr - team2_mmr)
        
        if diff < best_diff:
            best_diff = diff
            best_teams = (team1, team2)
    
    return best_teams

async def send_match_completion_dms(winning_team, losing_team, match_id, mmr_changes):
    """Send DM notifications to all players about match completion"""
    # Send to winners
    for player in winning_team:
        try:
            user = bot.get_user(int(player['id']))
            if user:
                embed = discord.Embed(
                    title="🎉 VICTORY!",
                    description=f"**Congratulations on your victory in Match #{match_id}!**",
                    color=discord.Color.green()
                )
                
                embed.add_field(name="🏆 Result", value="**VICTORY**", inline=True)
                embed.add_field(name="📈 MMR Change", value=f"**+{mmr_changes['winners']} MMR**", inline=True)
                embed.add_field(name="🎮 Match ID", value=f"#{match_id}", inline=True)
                
                # Get updated player stats
                c.execute("SELECT mmr, wins, losses FROM players WHERE id = ?", (player['id'],))
                result = c.fetchone()
                if result:
                    mmr, wins, losses = result
                    total_games = wins + losses
                    win_rate = (wins / total_games * 100) if total_games > 0 else 0
                    
                    embed.add_field(name="📊 Your Stats", 
                                  value=f"**MMR:** {mmr}\n**Wins:** {wins}\n**Losses:** {losses}\n**Win Rate:** {win_rate:.1f}%", 
                                  inline=False)
                
                embed.add_field(name="🔥 Motivation", 
                              value="Great job! Your skill and teamwork led to victory. Keep climbing the ranks!", 
                              inline=False)
                
                embed.set_footer(text="Keep playing to improve your rank! Use /queue to find your next match.")
                
                await user.send(embed=embed)
        except Exception as e:
            print(f"Failed to send DM to winner {player['id']}: {e}")
    
    # Send to losers
    for player in losing_team:
        try:
            user = bot.get_user(int(player['id']))
            if user:
                embed = discord.Embed(
                    title="💔 DEFEAT",
                    description=f"**You fought well in Match #{match_id}!**",
                    color=discord.Color.red()
                )
                
                embed.add_field(name="📉 Result", value="**DEFEAT**", inline=True)
                embed.add_field(name="📉 MMR Change", value=f"**{mmr_changes['losers']} MMR**", inline=True)
                embed.add_field(name="🎮 Match ID", value=f"#{match_id}", inline=True)
                
                # Get updated player stats
                c.execute("SELECT mmr, wins, losses FROM players WHERE id = ?", (player['id'],))
                result = c.fetchone()
                if result:
                    mmr, wins, losses = result
                    total_games = wins + losses
                    win_rate = (wins / total_games * 100) if total_games > 0 else 0
                    
                    embed.add_field(name="📊 Your Stats", 
                                  value=f"**MMR:** {mmr}\n**Wins:** {wins}\n**Losses:** {losses}\n**Win Rate:** {win_rate:.1f}%", 
                                  inline=False)
                
                embed.add_field(name="💪 Motivation", 
                              value="Every loss is a learning opportunity! Analyze your gameplay and come back stronger. Champions are made through perseverance!", 
                              inline=False)
                
                embed.set_footer(text="Don't give up! Use /queue to find your next match and prove yourself.")
                
                await user.send(embed=embed)
        except Exception as e:
            print(f"Failed to send DM to loser {player['id']}: {e}")

# Admin Match Control Panel View
class AdminMatchControlView(discord.ui.View):
    def __init__(self, match_id):
        super().__init__(timeout=300)
        self.match_id = match_id
    
    @discord.ui.button(label="🏆 Team 1 Wins", style=discord.ButtonStyle.green)
    async def team1_wins(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_set_winner(interaction, 1)
    
    @discord.ui.button(label="🏆 Team 2 Wins", style=discord.ButtonStyle.green)
    async def team2_wins(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_set_winner(interaction, 2)
    
    @discord.ui.button(label="🤝 Tie/Draw", style=discord.ButtonStyle.secondary)
    async def tie_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_set_tie(interaction)
    
    @discord.ui.button(label="🚫 Cancel Match", style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.admin_cancel_match(interaction)
    
    async def admin_set_winner(self, interaction: discord.Interaction, team_number: int):
        """Admin sets match winner"""
        if self.match_id not in active_matches:
            await interaction.response.send_message("❌ Match not found or already completed!", ephemeral=True)
            return
        
        match_data = active_matches[self.match_id]
        
        # Process match result
        winning_team = match_data['team1'] if team_number == 1 else match_data['team2']
        losing_team = match_data['team2'] if team_number == 1 else match_data['team1']
        
        # Calculate MMR changes
        mmr_changes = calculate_mmr_changes(winning_team, losing_team)
        
        # Update player stats
        for player in winning_team:
            c.execute("UPDATE players SET wins = wins + 1, mmr = mmr + ? WHERE id = ?", 
                     (mmr_changes['winners'], player['id']))
        
        for player in losing_team:
            c.execute("UPDATE players SET losses = losses + 1, mmr = mmr + ? WHERE id = ?", 
                     (mmr_changes['losers'], player['id']))
        
        # Update match record
        c.execute("UPDATE matches SET winner = ?, ended_at = ?, admin_modified = 1 WHERE match_id = ?", 
                 (team_number, datetime.now().isoformat(), self.match_id))
        conn.commit()
        
        # Send DM notifications
        await send_match_completion_dms(winning_team, losing_team, self.match_id, mmr_changes)
        
        # Update admin panel
        embed = discord.Embed(
            title="✅ Match Result Set",
            description=f"**Match #{self.match_id}** completed by admin",
            color=discord.Color.green()
        )
        
        winner_names = [p['username'] for p in winning_team]
        loser_names = [p['username'] for p in losing_team]
        
        embed.add_field(name="🎉 Winners", value=f"{', '.join(winner_names)}\n+{mmr_changes['winners']} MMR", inline=True)
        embed.add_field(name="💔 Losers", value=f"{', '.join(loser_names)}\n{mmr_changes['losers']} MMR", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Clean up match
        await cleanup_match(interaction.guild, self.match_id)
    
    async def admin_set_tie(self, interaction: discord.Interaction):
        """Admin sets match as tie"""
        if self.match_id not in active_matches:
            await interaction.response.send_message("❌ Match not found or already completed!", ephemeral=True)
            return
        
        match_data = active_matches[self.match_id]
        
        # No MMR changes for tie
        c.execute("UPDATE matches SET winner = 0, ended_at = ?, admin_modified = 1 WHERE match_id = ?", 
                 (datetime.now().isoformat(), self.match_id))
        conn.commit()
        
        # Send DM notifications for tie
        all_players = match_data['team1'] + match_data['team2']
        for player in all_players:
            try:
                user = bot.get_user(int(player['id']))
                if user:
                    embed = discord.Embed(
                        title="🤝 MATCH TIED",
                        description=f"**Match #{self.match_id} ended in a tie!**",
                        color=discord.Color.orange()
                    )
                    embed.add_field(name="📊 Result", value="**TIE**", inline=True)
                    embed.add_field(name="📈 MMR Change", value="**No change**", inline=True)
                    embed.add_field(name="🎮 Match ID", value=f"#{self.match_id}", inline=True)
                    embed.add_field(name="💪 Motivation", 
                                  value="A tie shows both teams were evenly matched! Great competition!", 
                                  inline=False)
                    await user.send(embed=embed)
            except Exception as e:
                print(f"Failed to send tie DM to {player['id']}: {e}")
        
        embed = discord.Embed(
            title="🤝 Match Tied",
            description=f"**Match #{self.match_id}** set as tie by admin",
            color=discord.Color.orange()
        )
        embed.add_field(name="Result", value="No MMR changes", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Clean up match
        await cleanup_match(interaction.guild, self.match_id)
    
    async def admin_cancel_match(self, interaction: discord.Interaction):
        """Admin cancels match"""
        if self.match_id not in active_matches:
            await interaction.response.send_message("❌ Match not found or already completed!", ephemeral=True)
            return
        
        match_data = active_matches[self.match_id]
        
        # Mark match as cancelled
        c.execute("UPDATE matches SET cancelled = 1, ended_at = ?, admin_modified = 1 WHERE match_id = ?", 
                 (datetime.now().isoformat(), self.match_id))
        conn.commit()
        
        # Send DM notifications for cancellation
        all_players = match_data['team1'] + match_data['team2']
        for player in all_players:
            try:
                user = bot.get_user(int(player['id']))
                if user:
                    embed = discord.Embed(
                        title="🚫 MATCH CANCELLED",
                        description=f"**Match #{self.match_id} has been cancelled by an administrator.**",
                        color=discord.Color.red()
                    )
                    embed.add_field(name="📊 Result", value="**CANCELLED**", inline=True)
                    embed.add_field(name="📈 MMR Change", value="**No change**", inline=True)
                    embed.add_field(name="🎮 Match ID", value=f"#{self.match_id}", inline=True)
                    embed.add_field(name="💪 Next Steps", 
                                  value="Don't worry! Use /queue to find a new match and continue playing!", 
                                  inline=False)
                    await user.send(embed=embed)
            except Exception as e:
                print(f"Failed to send cancellation DM to {player['id']}: {e}")
        
        embed = discord.Embed(
            title="🚫 Match Cancelled",
            description=f"**Match #{self.match_id}** cancelled by admin",
            color=discord.Color.red()
        )
        embed.add_field(name="Result", value="No changes made", inline=True)
        embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
        
        await interaction.response.edit_message(embed=embed, view=None)
        
        # Clean up match
        await cleanup_match(interaction.guild, self.match_id)

@bot.tree.command(name='win', description='Report the winning team (1 or 2)')
@app_commands.describe(team="Which team won? (1 or 2)")
async def report_win(interaction: discord.Interaction, team: int):
    """Report the winning team (1 or 2) - FIXED: No longer duplicates with button system"""
    await interaction.response.send_message("❌ Please use the match buttons in your dedicated match channel to report results!", ephemeral=True)

def calculate_mmr_changes(winning_team, losing_team):
    """Calculate MMR changes based on team averages"""
    avg_winner_mmr = sum(p['mmr'] for p in winning_team) / len(winning_team)
    avg_loser_mmr = sum(p['mmr'] for p in losing_team) / len(losing_team)
    
    # Basic MMR calculation (can be refined)
    base_change = 25
    mmr_diff = avg_winner_mmr - avg_loser_mmr
    
    if mmr_diff > 0:  # Favorites won
        winner_gain = max(10, base_change - mmr_diff // 10)
        loser_loss = -winner_gain
    else:  # Underdogs won
        winner_gain = min(40, base_change + abs(mmr_diff) // 10)
        loser_loss = -winner_gain
    
    return {'winners': winner_gain, 'losers': loser_loss}

@bot.command(name='cancel')
async def cancel_match(ctx):
    """Cancel an active match"""
    # Check if command is used in correct channel
    if not is_queue_channel(ctx):
        await ctx.send(f"❌ Please use match commands in #{QUEUE_CHANNEL_NAME} channel!")
        return
    
    # Find active match in this channel
    match_id = None
    for mid, match_data in active_matches.items():
        if match_data['channel_id'] == str(ctx.channel.id):
            match_id = mid
            break
    
    if not match_id:
        await ctx.send("❌ No active match found in this channel!")
        return
    
    # Check if user is part of the match
    user_id = str(ctx.author.id)
    if user_id not in active_matches[match_id]['players']:
        await ctx.send("❌ You can only cancel matches you're participating in!")
        return
    
    # Remove match and return players to queue
    match_data = active_matches[match_id]
    all_players = match_data['team1'] + match_data['team2']
    
    # Add players back to queue
    for player in all_players:
        player_queue.append(player)
    
    # Delete from database
    c.execute("DELETE FROM matches WHERE match_id = ?", (match_id,))
    conn.commit()
    
    # Remove from active matches
    del active_matches[match_id]
    
    embed = discord.Embed(
        title="❌ Match Cancelled",
        description=f"Match #{match_id} has been cancelled. Players returned to queue.",
        color=discord.Color.red()
    )
    
    await ctx.send(embed=embed)

def reset_queue():
    """Reset the queue system by clearing all players"""
    global player_queue, queue_last_activity, captain_draft_state, pending_team_selection
    
    # Store current queue size for logging
    queue_size = len(player_queue)
    
    # Clear the queue
    player_queue.clear()
    
    # Reset queue activity timestamp
    queue_last_activity = None
    
    # Clear any active drafts and pending team selections
    captain_draft_state.clear()
    pending_team_selection.clear()
    
    # Log the queue reset
    log_queue_event("RESET", "System", f"Queue cleared ({queue_size} players removed)")
    
    return queue_size

@bot.tree.command(name='reset_queue', description='Reset the queue system (Admin only)')
@app_commands.default_permissions(manage_channels=True)
async def reset_queue_command(interaction: discord.Interaction):
    """Reset the queue system - Admin only command"""
    
    # Check if we're in the queue channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ This command can only be used in #{QUEUE_CHANNEL_NAME}!", ephemeral=True)
        return
    
    # Reset the queue
    queue_size = reset_queue()
    
    # Create confirmation embed
    embed = discord.Embed(
        title="🔄 Queue Reset Complete",
        description=f"**Admin {interaction.user.display_name} has reset the queue system!**",
        color=discord.Color.blue()
    )
    
    embed.add_field(name="Players Removed", value=f"**{queue_size}** players", inline=True)
    embed.add_field(name="Queue Status", value="**RESET**", inline=True)
    embed.add_field(name="Timeout", value="**CLEARED**", inline=True)
    
    embed.add_field(
        name="✅ Reset Operations",
        value="• Player queue cleared\n• Queue activity reset\n• Draft sessions cleared\n• Timeout system reset",
        inline=False
    )
    
    embed.add_field(
        name="📊 Queue Status",
        value="• Player count: 0/4\n• Queue timeout: Reset\n• HSM numbers: Available",
        inline=False
    )
    
    embed.set_footer(text="Players can join the queue immediately using the buttons below")
    
    # Update queue display
    await update_queue_display(interaction.channel)
    
    await interaction.response.send_message(embed=embed)
    
    log_admin_action("QUEUE_RESET", interaction.user.display_name, f"Reset queue via command ({queue_size} players)")

# Admin cancel queue command
@bot.tree.command(name='cancel_queue', description='Cancel the entire queue system (Admin only)')
@app_commands.default_permissions(manage_channels=True)
async def cancel_queue(interaction: discord.Interaction):
    """Cancel the entire queue system - removes all players from queue"""
    # Check if we're in the queue channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(f"❌ This command can only be used in #{QUEUE_CHANNEL_NAME}!", ephemeral=True)
        return
    
    # Count players in queue
    queue_count = len(player_queue)
    
    if queue_count == 0:
        await interaction.response.send_message("❌ The queue is already empty!", ephemeral=True)
        return
    
    # Clear the queue
    queue_players = player_queue.copy()
    player_queue.clear()
    
    # Reset queue activity timer
    global queue_last_activity
    queue_last_activity = None
    
    # Create cancellation embed
    embed = discord.Embed(
        title="🚫 Queue System Cancelled",
        description=f"**Admin {interaction.user.display_name} has cancelled the entire queue system!**",
        color=discord.Color.red()
    )
    embed.add_field(name="Players Removed", value=f"**{queue_count}** players", inline=True)
    embed.add_field(name="Queue Status", value="**CLEARED**", inline=True)
    embed.add_field(name="Action", value="All players removed from queue", inline=True)
    
    # List removed players
    if queue_players:
        player_list = []
        for player in queue_players:
            user = interaction.guild.get_member(int(player['id']))
            if user:
                player_list.append(f"• {user.display_name} ({player['mmr']} MMR)")
        
        if player_list:
            embed.add_field(
                name="Removed Players",
                value="\n".join(player_list[:10]),  # Limit to 10 players
                inline=False
            )
    
    embed.add_field(name="Next Steps", value="Players can rejoin the queue using the buttons below", inline=False)
    embed.set_footer(text="Queue system reset by administrator")
    
    # Update queue display
    await update_queue_display(interaction.channel)
    
    await interaction.response.send_message(embed=embed)

# Enhanced Professional Setup Command
@bot.tree.command(name='setup', description='Create the professional HeatSeeker queue system (Admin only)')
@app_commands.default_permissions(manage_channels=True)
async def setup_channel(interaction: discord.Interaction):
    """Create the professional HeatSeeker queue system (Admin only)"""
    # Check if channel already exists
    existing_channel = discord.utils.get(interaction.guild.channels, name=QUEUE_CHANNEL_NAME)
    if existing_channel:
        embed = discord.Embed(
            title="✅ Queue Channel Already Exists",
            description=f"The #{QUEUE_CHANNEL_NAME} channel is already set up!",
            color=discord.Color.orange()
        )
        embed.add_field(name="Channel", value=existing_channel.mention, inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Create the professional queue system
    try:
        # Create queue channel
        queue_channel = await interaction.guild.create_text_channel(
            name=QUEUE_CHANNEL_NAME,
            topic="🔥 HeatSeeker Professional 2v2 Queue System - Click buttons to join!",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(
                    send_messages=False,  # Only bot messages and buttons
                    read_messages=True,
                    add_reactions=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    send_messages=True,
                    read_messages=True,
                    manage_messages=True,
                    embed_links=True
                )
            }
        )
        
        # Create results channel for completed matches (Admin only)
        results_channel = await interaction.guild.create_text_channel(
            name=RESULTS_CHANNEL_NAME,
            topic="🏆 HeatSeeker Match Results - Admin can modify completed matches here",
            overwrites={
                interaction.guild.default_role: discord.PermissionOverwrite(
                    send_messages=False,
                    read_messages=True,
                    add_reactions=True
                ),
                interaction.guild.me: discord.PermissionOverwrite(
                    send_messages=True,
                    read_messages=True,
                    manage_messages=True,
                    embed_links=True
                )
            }
        )
        
        # Get or create match category
        category = discord.utils.get(interaction.guild.categories, name=MATCH_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(
                name=MATCH_CATEGORY_NAME,
                reason="HeatSeeker match channels category"
            )
        
        # Send professional welcome message to queue channel
        embed = discord.Embed(
            title="🔥 HeatSeeker Bot - Professional 2v2 Queue System",
            description="**Welcome to the ultimate competitive gaming experience!**\n\nUse the buttons below to interact with the queue system.",
            color=discord.Color.gold()
        )
        
        embed.add_field(
            name="🎮 How It Works",
            value="• Click **🎮 Join Queue** to enter the 2v2 queue\n• When 4 players join, a match will be created automatically\n• Each match gets dedicated text and voice channels\n• Teams are balanced based on MMR for fair gameplay",
            inline=False
        )
        
        embed.add_field(
            name="🏆 Features",
            value="• **Dedicated match channels** for each game\n• **Team voice channels** (2 players max each)\n• **Automatic team balancing** based on skill\n• **Professional MMR tracking** system\n• **Auto-cleanup** after matches complete",
            inline=False
        )
        
        embed.set_footer(text="Ready to play? Click the buttons below to get started!")
        
        # Send with buttons
        view = QueueView()
        await queue_channel.send(embed=embed, view=view)
        
        # Send initial queue display
        await update_queue_display(queue_channel)
        
        # Confirmation to admin
        setup_embed = discord.Embed(
            title="🏆 HeatSeeker Setup Complete!",
            description=f"Professional queue system created successfully!",
            color=discord.Color.green()
        )
        setup_embed.add_field(name="Queue Channel", value=queue_channel.mention, inline=True)
        setup_embed.add_field(name="Results Channel", value=results_channel.mention, inline=True)
        setup_embed.add_field(name="Match Category", value=category.name, inline=True)
        setup_embed.add_field(name="Features", value="Button-based queue, voice channels, auto-balancing, admin results controls", inline=False)
        await interaction.response.send_message(embed=setup_embed, ephemeral=True)
        
    except discord.Forbidden:
        await interaction.response.send_message("❌ I don't have permission to create channels!", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(f"❌ Error creating channels: {e}", ephemeral=True)

# Private Chat Management Command
@bot.tree.command(name='private', description='Manage your private HSM chat (create/delete/info)')
async def private_chat_command(interaction: discord.Interaction):
    """Manage your private HSM chat"""
    user_id = str(interaction.user.id)
    
    # Check if user has an active private chat
    c.execute("SELECT hsm_number, channel_id, voice_channel_id FROM private_chats WHERE creator_id = ? AND is_active = 1", (user_id,))
    chat_data = c.fetchone()
    
    embed = discord.Embed(
        title="🔒 HSM Private Chat System",
        description="**Create your own private chat with a unique HSM number!**",
        color=discord.Color.purple()
    )
    
    if chat_data:
        hsm_number, channel_id, voice_channel_id = chat_data
        channel = interaction.guild.get_channel(int(channel_id))
        voice_channel = interaction.guild.get_channel(int(voice_channel_id))
        
        embed.add_field(
            name="📋 Your Active Private Chat",
            value=f"**HSM Number:** HSM{hsm_number}\n**Text Channel:** {channel.mention if channel else 'Deleted'}\n**Voice Channel:** {voice_channel.mention if voice_channel else 'Deleted'}",
            inline=False
        )
        embed.add_field(
            name="🔧 Management Options",
            value="• Use the **🗑️ Delete Private Chat** button to remove your chat\n• Manage permissions by right-clicking your channel",
            inline=False
        )
    else:
        embed.add_field(
            name="🆕 Create Your Private Chat",
            value="• Get a unique HSM number (HSM1 to HSM9999)\n• Private text and voice channels\n• Full control over permissions\n• Perfect for private group discussions",
            inline=False
        )
        embed.add_field(
            name="🎮 How to Create",
            value="Use the **🔒 Create Private Chat** button below!",
            inline=False
        )
    
    embed.set_footer(text="HSM Private Chats - Your own private space in the server!")
    
    view = PrivateChatView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Help command
@bot.tree.command(name='help', description='Show all available commands')
async def help_command(interaction: discord.Interaction):
    """Display available commands"""
    embed = discord.Embed(
        title="🤖 HeatSeeker Bot Commands",
        description="Here are all the available commands:",
        color=discord.Color.purple()
    )
    
    embed.add_field(
        name="📊 Player Stats",
        value="`/rank` - Display your current MMR and statistics\n" +
              "`/top` - Show the top 10 players leaderboard",
        inline=False
    )
    
    embed.add_field(
        name="🎮 Queue System",
        value=f"`/queue` - Join the 2v2 queue (use in #{QUEUE_CHANNEL_NAME})\n" +
              f"`/leave` - Leave the queue (use in #{QUEUE_CHANNEL_NAME})\n" +
              f"`/status` - Show current queue status (use in #{QUEUE_CHANNEL_NAME})",
        inline=False
    )
    
    embed.add_field(
        name="🏆 Match System",
        value=f"`/win team:1` or `/win team:2` - Report the winning team (use in #{QUEUE_CHANNEL_NAME})",
        inline=False
    )
    
    embed.add_field(
        name="🔒 Private Chat System",
        value="`/private` - Create your own private HSM chat (HSM1-HSM9999)\n" +
              "Get your own private text and voice channels!",
        inline=False
    )
    
    embed.add_field(
        name="⚙️ Admin Commands",
        value="`/setup` - Create the professional queue system (Admin only)\n" +
              "`/cancel_queue` - Cancel entire queue system (Admin only)\n" +
              "`/reset_queue` - Reset queue system (Admin only)\n" +
              "`/admin_match` - Admin control panel for match management (Admin only)\n" +
              "`/game_log` - View complete game history and modify all data (Admin only)\n" +
              "`/help` - Show this help message",
        inline=False
    )
    
    embed.set_footer(text="Queue commands only work in the dedicated 2v2 channel!")
    await interaction.response.send_message(embed=embed, ephemeral=True)

# Admin Match Control Panel Command
@bot.tree.command(name='admin_match', description='Admin control panel for active matches (Admin only)')
@app_commands.default_permissions(administrator=True)
async def admin_match_control(interaction: discord.Interaction):
    """Admin control panel for managing active matches"""
    print(f"[DEBUG] Admin match command called by {interaction.user.display_name}")
    print(f"[DEBUG] Active matches: {len(active_matches)}")
    
    if not active_matches:
        embed = discord.Embed(
            title="📋 Admin Match Control Panel",
            description="**No active matches found!**\n\nWhen matches are active, you can use this panel to:\n• Set match winners\n• Mark matches as ties\n• Cancel problematic matches\n• Override match results",
            color=discord.Color.orange()
        )
        embed.add_field(name="📝 How to Create Matches", value="Players need to use `/queue` to create matches first", inline=False)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Create dropdown for match selection
    options = []
    try:
        for match_id, match_data in active_matches.items():
            team1_names = [p['username'] for p in match_data['team1']]
            team2_names = [p['username'] for p in match_data['team2']]
            hsm_number = match_data.get('hsm_number', 'N/A')
            
            description = f"HSM{hsm_number}: {', '.join(team1_names)} vs {', '.join(team2_names)}"
            options.append(discord.SelectOption(
                label=f"Match #{match_id}",
                description=description[:100],  # Discord limit
                value=str(match_id)
            ))
            print(f"[DEBUG] Added option for match {match_id}: {description}")
    except Exception as e:
        print(f"[DEBUG] Error creating options: {e}")
        await interaction.response.send_message(f"❌ Error creating admin panel: {e}", ephemeral=True)
        return
    
    # Create embed
    embed = discord.Embed(
        title="🔧 Admin Match Control Panel",
        description=f"**{len(active_matches)} active match(es) found**\n\nSelect a match below to manage:",
        color=discord.Color.gold()
    )
    
    # Add match details
    for match_id, match_data in list(active_matches.items())[:5]:  # Show first 5 matches
        team1_names = [p['username'] for p in match_data['team1']]
        team2_names = [p['username'] for p in match_data['team2']]
        hsm_number = match_data.get('hsm_number', 'N/A')
        
        embed.add_field(
            name=f"Match #{match_id} (HSM{hsm_number})",
            value=f"🔴 **Team 1:** {', '.join(team1_names)}\n🔵 **Team 2:** {', '.join(team2_names)}",
            inline=False
        )
    
    if len(active_matches) > 5:
        embed.add_field(name="And more...", value=f"Plus {len(active_matches) - 5} more matches", inline=False)
    
    embed.set_footer(text="Select a match to access admin controls")
    
    # Create select menu
    class MatchSelectView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select a match to manage...",
            min_values=1,
            max_values=1,
            options=options
        )
        async def match_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            try:
                match_id = int(select.values[0])
                print(f"[DEBUG] Admin selected match {match_id}")
                
                if match_id not in active_matches:
                    await select_interaction.response.send_message("❌ Match not found or already completed!", ephemeral=True)
                    return
            except Exception as e:
                print(f"[DEBUG] Error in match_select: {e}")
                await select_interaction.response.send_message(f"❌ Error selecting match: {e}", ephemeral=True)
                return
            
            match_data = active_matches[match_id]
            hsm_number = match_data.get('hsm_number', 'N/A')
            
            # Create detailed match embed
            control_embed = discord.Embed(
                title=f"🔧 Admin Control - Match #{match_id}",
                description=f"**HSM{hsm_number}** - Choose your action:",
                color=discord.Color.red()
            )
            
            team1_names = [p['username'] for p in match_data['team1']]
            team2_names = [p['username'] for p in match_data['team2']]
            
            team1_mmr = sum(p['mmr'] for p in match_data['team1']) / len(match_data['team1'])
            team2_mmr = sum(p['mmr'] for p in match_data['team2']) / len(match_data['team2'])
            
            control_embed.add_field(
                name="🔴 Team 1",
                value=f"**Players:** {', '.join(team1_names)}\n**Avg MMR:** {team1_mmr:.0f}",
                inline=True
            )
            
            control_embed.add_field(
                name="🔵 Team 2", 
                value=f"**Players:** {', '.join(team2_names)}\n**Avg MMR:** {team2_mmr:.0f}",
                inline=True
            )
            
            control_embed.add_field(
                name="⚙️ Admin Actions",
                value="• **🏆 Team X Wins** - Set winner and update MMR\n• **🤝 Tie/Draw** - No MMR changes\n• **🚫 Cancel** - Cancel match entirely",
                inline=False
            )
            
            control_embed.set_footer(text="Use buttons below to manage this match")
            
            # Send admin control panel for this match
            admin_view = AdminMatchControlView(match_id)
            await select_interaction.response.send_message(embed=control_embed, view=admin_view, ephemeral=True)
    
    try:
        view = MatchSelectView()
        await interaction.response.send_message(embed=embed, view=view, ephemeral=True)
        print(f"[DEBUG] Admin match panel sent successfully")
    except Exception as e:
        print(f"[DEBUG] Error sending admin match panel: {e}")
        await interaction.response.send_message(f"❌ Error creating admin panel: {e}", ephemeral=True)

# Game Log System - View and Modify All Game Data
@bot.tree.command(name='game_log', description='View complete game history and statistics (Admin only)')
@app_commands.default_permissions(administrator=True)
async def game_log(interaction: discord.Interaction):
    """View complete game history with all details"""
    print(f"[DEBUG] Game log command called by {interaction.user.display_name}")
    
    # Get all matches from database
    c.execute("""
        SELECT match_id, team1_players, team2_players, winner, created_at, ended_at, 
               admin_modified, cancelled
        FROM matches 
        ORDER BY match_id DESC
    """)
    all_matches = c.fetchall()
    
    if not all_matches:
        embed = discord.Embed(
            title="📋 Game Log",
            description="**No matches found in database**",
            color=discord.Color.orange()
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return
    
    # Create main log embed
    embed = discord.Embed(
        title="📋 Complete Game Log",
        description=f"**{len(all_matches)} total matches found**\n\nSelect a match to view details:",
        color=discord.Color.blue()
    )
    
    # Add summary statistics
    completed_matches = [m for m in all_matches if m[3] is not None]
    active_matches_count = len(all_matches) - len(completed_matches)
    
    embed.add_field(
        name="📊 Summary",
        value=f"**Total:** {len(all_matches)}\n**Completed:** {len(completed_matches)}\n**Active:** {active_matches_count}",
        inline=True
    )
    
    # Create dropdown for match selection
    options = []
    for match in all_matches[:25]:  # Discord limit
        match_id, team1_ids, team2_ids, winner, created_at, ended_at, admin_modified, cancelled = match
        
        # Get team names
        team1_names = []
        team2_names = []
        
        if team1_ids:
            for player_id in team1_ids.split(','):
                c.execute("SELECT username FROM players WHERE id = ?", (player_id,))
                result = c.fetchone()
                if result:
                    team1_names.append(result[0])
        
        if team2_ids:
            for player_id in team2_ids.split(','):
                c.execute("SELECT username FROM players WHERE id = ?", (player_id,))
                result = c.fetchone()
                if result:
                    team2_names.append(result[0])
        
        # Status indicators
        status = "🔴 Active"
        if cancelled:
            status = "🚫 Cancelled"
        elif winner == 1:
            status = "🏆 Team 1 Won"
        elif winner == 2:
            status = "🏆 Team 2 Won"
        elif winner == 0:
            status = "🤝 Tie"
        
        if admin_modified:
            status += " (Admin)"
        
        description = f"{status} | {', '.join(team1_names[:2])} vs {', '.join(team2_names[:2])}"
        
        options.append(discord.SelectOption(
            label=f"Match #{match_id}",
            description=description[:100],
            value=str(match_id)
        ))
    
    # Create select menu view
    class GameLogView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=300)
        
        @discord.ui.select(
            placeholder="Select a match to view details...",
            options=options
        )
        async def match_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
            match_id = int(select.values[0])
            
            # Get detailed match data
            c.execute("""
                SELECT match_id, team1_players, team2_players, winner, created_at, ended_at,
                       admin_modified, cancelled, channel_id
                FROM matches WHERE match_id = ?
            """, (match_id,))
            match_data = c.fetchone()
            
            if not match_data:
                await select_interaction.response.send_message("❌ Match not found!", ephemeral=True)
                return
            
            # Create detailed embed
            await self.show_match_details(select_interaction, match_data)
        
        async def show_match_details(self, interaction: discord.Interaction, match_data):
            """Show detailed match information"""
            match_id, team1_ids, team2_ids, winner, created_at, ended_at, admin_modified, cancelled, channel_id = match_data
            
            # Get team player details
            team1_details = []
            team2_details = []
            
            if team1_ids:
                for player_id in team1_ids.split(','):
                    c.execute("SELECT username, mmr, wins, losses FROM players WHERE id = ?", (player_id,))
                    result = c.fetchone()
                    if result:
                        username, mmr, wins, losses = result
                        team1_details.append({
                            'id': player_id,
                            'username': username,
                            'mmr': mmr,
                            'wins': wins,
                            'losses': losses
                        })
            
            if team2_ids:
                for player_id in team2_ids.split(','):
                    c.execute("SELECT username, mmr, wins, losses FROM players WHERE id = ?", (player_id,))
                    result = c.fetchone()
                    if result:
                        username, mmr, wins, losses = result
                        team2_details.append({
                            'id': player_id,
                            'username': username,
                            'mmr': mmr,
                            'wins': wins,
                            'losses': losses
                        })
            
            # Create detailed embed
            embed = discord.Embed(
                title=f"🔍 Match #{match_id} Details",
                color=discord.Color.gold()
            )
            
            # Status
            status = "🔴 Active"
            if cancelled:
                status = "🚫 Cancelled"
            elif winner == 1:
                status = "🏆 Team 1 Victory"
            elif winner == 2:
                status = "🏆 Team 2 Victory"
            elif winner == 0:
                status = "🤝 Tie Game"
            
            if admin_modified:
                status += " (Admin Modified)"
            
            embed.add_field(name="📊 Status", value=status, inline=True)
            embed.add_field(name="🎮 Match ID", value=f"#{match_id}", inline=True)
            embed.add_field(name="📅 Created", value=created_at[:19] if created_at else "N/A", inline=True)
            
            if ended_at:
                embed.add_field(name="⏰ Ended", value=ended_at[:19], inline=True)
            
            # Team 1 details
            if team1_details:
                team1_text = ""
                team1_avg_mmr = sum(p['mmr'] for p in team1_details) / len(team1_details)
                for player in team1_details:
                    total_games = player['wins'] + player['losses']
                    winrate = (player['wins'] / total_games * 100) if total_games > 0 else 0
                    team1_text += f"**{player['username']}**\n"
                    team1_text += f"MMR: {player['mmr']} | W/L: {player['wins']}/{player['losses']} ({winrate:.1f}%)\n\n"
                
                embed.add_field(
                    name=f"🔴 Team 1 (Avg MMR: {team1_avg_mmr:.0f})",
                    value=team1_text,
                    inline=True
                )
            
            # Team 2 details
            if team2_details:
                team2_text = ""
                team2_avg_mmr = sum(p['mmr'] for p in team2_details) / len(team2_details)
                for player in team2_details:
                    total_games = player['wins'] + player['losses']
                    winrate = (player['wins'] / total_games * 100) if total_games > 0 else 0
                    team2_text += f"**{player['username']}**\n"
                    team2_text += f"MMR: {player['mmr']} | W/L: {player['wins']}/{player['losses']} ({winrate:.1f}%)\n\n"
                
                embed.add_field(
                    name=f"🔵 Team 2 (Avg MMR: {team2_avg_mmr:.0f})",
                    value=team2_text,
                    inline=True
                )
            
            # Add modification buttons
            view = MatchModifyView(match_id)
            await interaction.response.edit_message(embed=embed, view=view)
    
    view = GameLogView()
    await interaction.response.send_message(embed=embed, view=view, ephemeral=True)

# Match Modification View
class MatchModifyView(discord.ui.View):
    def __init__(self, match_id):
        super().__init__(timeout=300)
        self.match_id = match_id
    
    @discord.ui.button(label="🏆 Set Team 1 Winner", style=discord.ButtonStyle.green)
    async def set_team1_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.modify_match_winner(interaction, 1)
    
    @discord.ui.button(label="🏆 Set Team 2 Winner", style=discord.ButtonStyle.green)
    async def set_team2_winner(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.modify_match_winner(interaction, 2)
    
    @discord.ui.button(label="🤝 Set Tie", style=discord.ButtonStyle.secondary)
    async def set_tie(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.modify_match_winner(interaction, 0)
    
    @discord.ui.button(label="🚫 Cancel Match", style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.modify_match_winner(interaction, None, cancelled=True)
    
    @discord.ui.button(label="📝 Edit Players", style=discord.ButtonStyle.primary)
    async def edit_players(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_player_editor(interaction)
    
    async def modify_match_winner(self, interaction: discord.Interaction, winner, cancelled=False):
        """Modify match winner"""
        try:
            if cancelled:
                c.execute("""
                    UPDATE matches 
                    SET cancelled = 1, ended_at = ?, admin_modified = 1
                    WHERE match_id = ?
                """, (datetime.now().isoformat(), self.match_id))
                status = "🚫 Match cancelled"
            else:
                c.execute("""
                    UPDATE matches 
                    SET winner = ?, ended_at = ?, admin_modified = 1
                    WHERE match_id = ?
                """, (winner, datetime.now().isoformat(), self.match_id))
                
                if winner == 1:
                    status = "🏆 Team 1 set as winner"
                elif winner == 2:
                    status = "🏆 Team 2 set as winner"
                else:
                    status = "🤝 Match set as tie"
            
            conn.commit()
            
            # Remove from active matches if it exists
            if self.match_id in active_matches:
                del active_matches[self.match_id]
            
            embed = discord.Embed(
                title="✅ Match Updated",
                description=f"**Match #{self.match_id}** - {status}",
                color=discord.Color.green()
            )
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            embed.add_field(name="Timestamp", value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating match: {e}", ephemeral=True)
    
    async def show_player_editor(self, interaction: discord.Interaction):
        """Show player editor interface"""
        # Get all players
        c.execute("SELECT id, username, mmr, wins, losses FROM players ORDER BY mmr DESC")
        players = c.fetchall()
        
        embed = discord.Embed(
            title="📝 Player Editor",
            description="Select a player to modify their stats:",
            color=discord.Color.purple()
        )
        
        # Create player selection dropdown
        options = []
        for player in players[:25]:  # Discord limit
            player_id, username, mmr, wins, losses = player
            total_games = wins + losses
            winrate = (wins / total_games * 100) if total_games > 0 else 0
            
            options.append(discord.SelectOption(
                label=username,
                description=f"MMR: {mmr} | W/L: {wins}/{losses} ({winrate:.1f}%)",
                value=player_id
            ))
        
        class PlayerSelectView(discord.ui.View):
            def __init__(self):
                super().__init__(timeout=300)
            
            @discord.ui.select(
                placeholder="Select a player to edit...",
                options=options
            )
            async def player_select(self, select_interaction: discord.Interaction, select: discord.ui.Select):
                player_id = select.values[0]
                
                # Get player data
                c.execute("SELECT username, mmr, wins, losses FROM players WHERE id = ?", (player_id,))
                player_data = c.fetchone()
                
                if not player_data:
                    await select_interaction.response.send_message("❌ Player not found!", ephemeral=True)
                    return
                
                await self.show_player_modify(select_interaction, player_id, player_data)
            
            async def show_player_modify(self, interaction: discord.Interaction, player_id, player_data):
                """Show player modification interface"""
                username, mmr, wins, losses = player_data
                
                embed = discord.Embed(
                    title=f"📝 Edit Player: {username}",
                    description="Choose what to modify:",
                    color=discord.Color.purple()
                )
                
                total_games = wins + losses
                winrate = (wins / total_games * 100) if total_games > 0 else 0
                
                embed.add_field(name="Current Stats", 
                              value=f"**MMR:** {mmr}\n**Wins:** {wins}\n**Losses:** {losses}\n**Win Rate:** {winrate:.1f}%", 
                              inline=False)
                
                # Create modification buttons
                view = PlayerModifyView(player_id, username)
                await interaction.response.edit_message(embed=embed, view=view)
        
        view = PlayerSelectView()
        await interaction.response.edit_message(embed=embed, view=view)

# Player Modification View
class PlayerModifyView(discord.ui.View):
    def __init__(self, player_id, username):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.username = username
    
    @discord.ui.button(label="⚡ Set MMR", style=discord.ButtonStyle.primary)
    async def set_mmr(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_mmr_modal(interaction)
    
    @discord.ui.button(label="🏆 Set Wins", style=discord.ButtonStyle.green)
    async def set_wins(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_wins_modal(interaction)
    
    @discord.ui.button(label="💔 Set Losses", style=discord.ButtonStyle.red)
    async def set_losses(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.show_losses_modal(interaction)
    
    @discord.ui.button(label="🔄 Reset Stats", style=discord.ButtonStyle.secondary)
    async def reset_stats(self, interaction: discord.Interaction, button: discord.ui.Button):
        await self.reset_player_stats(interaction)
    
    async def show_mmr_modal(self, interaction: discord.Interaction):
        """Show MMR modification modal"""
        modal = PlayerMMRModal(self.player_id, self.username)
        await interaction.response.send_modal(modal)
    
    async def show_wins_modal(self, interaction: discord.Interaction):
        """Show wins modification modal"""
        modal = PlayerWinsModal(self.player_id, self.username)
        await interaction.response.send_modal(modal)
    
    async def show_losses_modal(self, interaction: discord.Interaction):
        """Show losses modification modal"""
        modal = PlayerLossesModal(self.player_id, self.username)
        await interaction.response.send_modal(modal)
    
    async def reset_player_stats(self, interaction: discord.Interaction):
        """Reset player stats to default"""
        try:
            c.execute("UPDATE players SET mmr = 1000, wins = 0, losses = 0 WHERE id = ?", (self.player_id,))
            conn.commit()
            
            embed = discord.Embed(
                title="✅ Player Stats Reset",
                description=f"**{self.username}** stats have been reset to default",
                color=discord.Color.green()
            )
            embed.add_field(name="New Stats", value="MMR: 1000\nWins: 0\nLosses: 0", inline=True)
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            
            await interaction.response.edit_message(embed=embed, view=None)
            
        except Exception as e:
            await interaction.response.send_message(f"❌ Error resetting stats: {e}", ephemeral=True)

# Modals for player stat modification
class PlayerMMRModal(discord.ui.Modal):
    def __init__(self, player_id, username):
        super().__init__(title=f"Set MMR for {username}")
        self.player_id = player_id
        self.username = username
        
        self.mmr_input = discord.ui.TextInput(
            label="New MMR",
            placeholder="Enter new MMR value (e.g., 1200)",
            required=True,
            max_length=5
        )
        self.add_item(self.mmr_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_mmr = int(self.mmr_input.value)
            if new_mmr < 0 or new_mmr > 5000:
                await interaction.response.send_message("❌ MMR must be between 0 and 5000", ephemeral=True)
                return
            
            c.execute("UPDATE players SET mmr = ? WHERE id = ?", (new_mmr, self.player_id))
            conn.commit()
            
            embed = discord.Embed(
                title="✅ MMR Updated",
                description=f"**{self.username}** MMR set to {new_mmr}",
                color=discord.Color.green()
            )
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating MMR: {e}", ephemeral=True)

class PlayerWinsModal(discord.ui.Modal):
    def __init__(self, player_id, username):
        super().__init__(title=f"Set Wins for {username}")
        self.player_id = player_id
        self.username = username
        
        self.wins_input = discord.ui.TextInput(
            label="New Wins",
            placeholder="Enter new wins count (e.g., 15)",
            required=True,
            max_length=5
        )
        self.add_item(self.wins_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_wins = int(self.wins_input.value)
            if new_wins < 0:
                await interaction.response.send_message("❌ Wins cannot be negative", ephemeral=True)
                return
            
            c.execute("UPDATE players SET wins = ? WHERE id = ?", (new_wins, self.player_id))
            conn.commit()
            
            embed = discord.Embed(
                title="✅ Wins Updated",
                description=f"**{self.username}** wins set to {new_wins}",
                color=discord.Color.green()
            )
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating wins: {e}", ephemeral=True)

class PlayerLossesModal(discord.ui.Modal):
    def __init__(self, player_id, username):
        super().__init__(title=f"Set Losses for {username}")
        self.player_id = player_id
        self.username = username
        
        self.losses_input = discord.ui.TextInput(
            label="New Losses",
            placeholder="Enter new losses count (e.g., 8)",
            required=True,
            max_length=5
        )
        self.add_item(self.losses_input)
    
    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_losses = int(self.losses_input.value)
            if new_losses < 0:
                await interaction.response.send_message("❌ Losses cannot be negative", ephemeral=True)
                return
            
            c.execute("UPDATE players SET losses = ? WHERE id = ?", (new_losses, self.player_id))
            conn.commit()
            
            embed = discord.Embed(
                title="✅ Losses Updated",
                description=f"**{self.username}** losses set to {new_losses}",
                color=discord.Color.green()
            )
            embed.add_field(name="Admin", value=interaction.user.mention, inline=True)
            
            await interaction.response.send_message(embed=embed, ephemeral=True)
            
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"❌ Error updating losses: {e}", ephemeral=True)

# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send("❌ Command not found. Use `/help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send("❌ Missing required argument. Use `/help` for command usage.")
    else:
        await ctx.send(f"❌ An error occurred: {error}")

# Run the bot
if __name__ == "__main__":
    token = os.getenv('DISCORD_BOT_TOKEN')
    if not token:
        print("❌ Error: DISCORD_BOT_TOKEN environment variable not found!")
        print("Please set your Discord bot token in the Replit Secrets.")
        exit(1)
    
    print("🤖 Starting Discord Bot with Slash Commands...")
    print("📡 Connecting to Discord...")
    bot.run(token)
