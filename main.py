import discord
from discord import ui
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
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
                    handlers=[
                        logging.FileHandler('heatseeker_bot.log'),
                        logging.StreamHandler()
                    ])
logger = logging.getLogger('HeatSeeker')

# Bot setup with enhanced intents
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True  # إضافة صلاحية الأعضاء للرتب التلقائية
bot = commands.Bot(command_prefix="!", intents=intents)

# Global variables for queue and match system
player_queue = []
active_matches = {}
match_id_counter = 1
queue_timeout_task = None
queue_last_activity = None
pending_team_selection = {}  # Store pending team selection data
captain_draft_state = {}  # Store captain draft state

# Dynamic queue configuration
QUEUE_SIZE = 2  # Default queue size (changed from 4 to 2)
TEAM_SIZE = 1  # Default team size (1v1 instead of 2v2)
leaderboard_task = None  # For auto-updating leaderboard
leaderboard_channel = None  # Store leaderboard channel

# Global variables for private chat system
private_chats = {}  # Store private chat data
used_hsm_numbers = set()  # Track used HSM numbers

# Global variable for ping cooldown system
ping_cooldowns = {}  # Store last ping times by user ID

# Channel configuration
QUEUE_CHANNEL_NAME = "heatseeker-queue"  # Main queue channel
RESULTS_CHANNEL_NAME = "heatseeker-results"  # Results channel for completed matches
MATCH_CATEGORY_NAME = "HeatSeeker Matches"  # Category for match channels
PRIVATE_CATEGORY_NAME = "HSM Private Chats"  # Category for private chats

# Rank system configuration with role names (will auto-create roles)
UNRANK_RANK = {
    "UNRANKED": {
        "role_name": "UNRANKED",
        "min_mmr": 0,
        "max_mmr": 799,
        "name": "UNRANKED",
        "emoji": "<:7UNRANKED:1224327892234670171>",
        "color": 0x4E4E4E
    }
}

RANK_ROLES = {
    "SILVER": {
        "role_name": "SILVER SEEKER",
        "min_mmr": 800,
        "max_mmr": 949,
        "name": "〣 SILVER SEEKER",
        "emoji": "<:1SILVER:1224325616535339041>",
        "color": 0xBDBDBD
    },
    "PLATINUM": {
        "role_name": "PLATINUM SEEKER",
        "min_mmr": 950,
        "max_mmr": 1099,
        "name": "〣 PLATINUM SEEKER",
        "emoji": "<:2PLATINUM:1224327801075925005>",
        "color": 0x3DDBEE
    },
    "CRYSTAL": {
        "role_name": "CRYSTAL SEEKER",
        "min_mmr": 1100,
        "max_mmr": 1249,
        "name": "〣 CRYSTAL SEEKER",
        "emoji": "<:3CRYSTAL:1224327804351545345>",
        "color": 0x9BC2F1
    },
    "ELITE": {
        "role_name": "ELITE SEEKER",
        "min_mmr": 1250,
        "max_mmr": 1449,
        "name": "〣 ELITE SEEKER",
        "emoji": "<:4ELITE:1224327806847160361>",
        "color": 0x3BF695
    },
    "MASTER": {
        "role_name": "MASTER SEEKER",
        "min_mmr": 1450,
        "max_mmr": 1699,
        "name": "〣 MASTER SEEKER",
        "emoji": "<:5Mastermin:1224327858445615204>",
        "color": 0xFF0000
    },
    "LEGENDARY": {
        "role_name": "LEGENDARY SEEKER",
        "min_mmr": 1700,
        "max_mmr": 9999,
        "name": "〣 LEGENDARY SEEKER",
        "emoji": "<:6LEGENDARYmin:1224327860437913610>",
        "color": 0xF3C900
    }
}

# قاعدة البيانات
conn = sqlite3.connect("players.db")
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS players (
    id TEXT PRIMARY KEY,
    username TEXT,
    mmr INTEGER DEFAULT 1000,
    wins INTEGER DEFAULT 0,
    losses INTEGER DEFAULT 0,
    placement_matches_remaining INTEGER DEFAULT 5,
    is_placed INTEGER DEFAULT 0
)''')

# Add new columns for existing players
try:
    c.execute(
        "ALTER TABLE players ADD COLUMN placement_matches_remaining INTEGER DEFAULT 5"
    )
    conn.commit()
    print("[DEBUG] Added placement_matches_remaining column")
except sqlite3.OperationalError:
    # Column already exists
    pass

try:
    c.execute("ALTER TABLE players ADD COLUMN is_placed INTEGER DEFAULT 0")
    conn.commit()
    print("[DEBUG] Added is_placed column")
except sqlite3.OperationalError:
    # Column already exists
    pass

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
    cancelled INTEGER DEFAULT 0,
    hsm_number INTEGER
)''')

# Add hsm_number column if it doesn't exist (for existing databases)
try:
    c.execute("ALTER TABLE matches ADD COLUMN hsm_number INTEGER")
    conn.commit()
    print("[DEBUG] Added hsm_number column to matches table")
except sqlite3.OperationalError:
    # Column already exists
    pass

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
        cancelled_count = 0

        for match_id, team1_ids, team2_ids, created_at, channel_id in db_matches:
            logger.info(
                f"RESTORE: Processing match {match_id} - team1: '{team1_ids}', team2: '{team2_ids}'"
            )

            # Parse team player IDs
            team1_player_ids = team1_ids.split(
                ',') if team1_ids and team1_ids.strip() else []
            team2_player_ids = team2_ids.split(
                ',') if team2_ids and team2_ids.strip() else []

            # Check for empty teams
            if not team1_player_ids or not team2_player_ids:
                logger.warning(
                    f"RESTORE: Match {match_id} has empty team data - cancelling"
                )
                # Cancel this corrupted match
                c.execute(
                    "UPDATE matches SET winner = -1, cancelled = 1 WHERE match_id = ?",
                    (match_id, ))
                conn.commit()
                cancelled_count += 1
                continue

            # Get player data for each team
            team1 = []
            team2 = []

            for player_id in team1_player_ids:
                if player_id.strip():  # Only process non-empty player IDs
                    c.execute("SELECT username, mmr FROM players WHERE id = ?",
                              (player_id.strip(), ))
                    result = c.fetchone()
                    if result:
                        username, mmr = result
                        team1.append({
                            'id': player_id.strip(),
                            'username': username,
                            'mmr': mmr
                        })

            for player_id in team2_player_ids:
                if player_id.strip():  # Only process non-empty player IDs
                    c.execute("SELECT username, mmr FROM players WHERE id = ?",
                              (player_id.strip(), ))
                    result = c.fetchone()
                    if result:
                        username, mmr = result
                        team2.append({
                            'id': player_id.strip(),
                            'username': username,
                            'mmr': mmr
                        })

            # Check if we have valid team data
            expected_team_size = QUEUE_SIZE // 2
            if len(team1) != expected_team_size or len(
                    team2) != expected_team_size:
                logger.warning(
                    f"RESTORE: Match {match_id} has incomplete team data - team1: {len(team1)}, team2: {len(team2)}, expected: {expected_team_size}"
                )
                # Cancel this corrupted match
                c.execute(
                    "UPDATE matches SET winner = -1, cancelled = 1 WHERE match_id = ?",
                    (match_id, ))
                conn.commit()
                cancelled_count += 1
                continue

            # Generate HSM number (simplified - use match_id as HSM number)
            hsm_number = match_id

            active_matches[match_id] = {
                'team1':
                team1,
                'team2':
                team2,
                'players': [
                    p.strip() for p in team1_player_ids + team2_player_ids
                    if p.strip()
                ],
                'channel_id':
                channel_id,
                'hsm_number':
                hsm_number,
                'distribution_method':
                'Restored',
                'created_at':
                created_at
            }
            restored_count += 1
            logger.info(
                f"RESTORE: Successfully restored match {match_id}: HSM{hsm_number}"
            )

        logger.info(
            f"RESTORE: Restored {restored_count} active matches, cancelled {cancelled_count} corrupted matches"
        )
        print(
            f"[DEBUG] Restored {restored_count} active matches from database")

    except Exception as e:
        logger.error(f"RESTORE: Error restoring active matches: {e}")
        print(f"[DEBUG] Error restoring active matches: {e}")
        active_matches = {}


# Add sample data for demonstration
def add_sample_data():
    """Add sample players for demonstration"""
    sample_players = [('123456789', 'Empty', 1200, 15, 5),
                      ('987654321', 'Empty', 1450, 25, 8),
                      ('456789123', 'Empty', 1350, 20, 12),
                      ('789123456', 'Empty', 1100, 18, 15),
                      ('321654987', 'Empty', 1300, 22, 10),
                      ('654321789', 'Empty', 1500, 30, 5),
                      ('147258369', 'Empty', 1250, 16, 9),
                      ('963852741', 'Empty', 1400, 28, 7),
                      ('258741963', 'Empty', 1180, 14, 11),
                      ('741852963', 'Empty', 1600, 35, 3)]

    for player_id, username, mmr, wins, losses in sample_players:
        c.execute("SELECT * FROM players WHERE id = ?", (player_id, ))
        if not c.fetchone():
            c.execute(
                "INSERT INTO players (id, username, mmr, wins, losses) VALUES (?, ?, ?, ?, ?)",
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
    logger.info(
        f"PLAYER UPDATE: {player_name} - MMR: {old_stats['mmr']}->{new_stats['mmr']}, W/L: {old_stats['wins']}/{old_stats['losses']}->{new_stats['wins']}/{new_stats['losses']}"
    )


def get_rank_from_mmr(mmr, is_placed=True):
    """Get rank information based on MMR"""
    # Players in placement matches have no rank
    if not is_placed:
        return {
            'role_name': 'PLACEMENT',
            'min_mmr': 0,
            'max_mmr': 9999,
            'name': 'PLACEMENT MATCHES',
            'emoji': '🔄',
            'color': 0x808080
        }

    for rank_key, rank_data in RANK_ROLES.items():
        if rank_data['min_mmr'] <= mmr <= rank_data['max_mmr']:
            return rank_data
    # Default to UNRANKED if no match found
    return UNRANK_RANK['UNRANKED']


async def update_player_rank_role(guild, user_id, new_mmr):
    """Update player's rank role based on their MMR - نسخة محسّنة مع معالجة أفضل للأخطاء"""
    try:
        member = guild.get_member(int(user_id))
        if not member:
            logger.warning(
                f"RANK SYSTEM: Member {user_id} not found in guild {guild.name}"
            )
            return False

        # Get current rank based on MMR
        new_rank = get_rank_from_mmr(new_mmr)
        if not new_rank:
            logger.error(f"RANK SYSTEM: No rank found for MMR {new_mmr}")
            return False

        # Check if member already has the correct rank
        current_rank_role = None
        for rank_data in RANK_ROLES.values():
            role = discord.utils.get(guild.roles, name=rank_data['role_name'])
            if role and role in member.roles:
                current_rank_role = role
                break

        # If they already have the correct rank, skip
        target_role = discord.utils.get(guild.roles,
                                        name=new_rank['role_name'])
        if current_rank_role == target_role and target_role:
            return True

        # Find or create the new role
        new_role = discord.utils.get(guild.roles, name=new_rank['role_name'])
        if not new_role:
            try:
                # Create the role if it doesn't exist
                new_role = await guild.create_role(
                    name=new_rank['role_name'],
                    color=discord.Color(new_rank['color']),
                    reason=f"Auto-created rank role for HeatSeeker system")
                logger.info(
                    f"RANK SYSTEM: Created new role {new_rank['role_name']} in {guild.name}"
                )
            except discord.Forbidden:
                logger.error(
                    f"RANK SYSTEM: No permission to create role {new_rank['role_name']} in {guild.name}"
                )
                return False
            except discord.HTTPException as e:
                logger.error(
                    f"RANK SYSTEM: HTTP error creating role {new_rank['role_name']}: {e}"
                )
                return False
            except Exception as e:
                logger.error(
                    f"RANK SYSTEM: Unexpected error creating role {new_rank['role_name']}: {e}"
                )
                return False

        # Remove all rank roles from user (cleaned up approach)
        rank_roles_to_remove = []
        for rank_data in RANK_ROLES.values():
            role = discord.utils.get(guild.roles, name=rank_data['role_name'])
            if role and role in member.roles and role != new_role:
                rank_roles_to_remove.append(role)

        # Remove old rank roles
        if rank_roles_to_remove:
            try:
                await member.remove_roles(*rank_roles_to_remove,
                                          reason="Automatic rank update")
                logger.info(
                    f"RANK SYSTEM: Removed {len(rank_roles_to_remove)} old rank roles from {member.display_name}"
                )
            except discord.Forbidden:
                logger.error(
                    f"RANK SYSTEM: No permission to remove roles from {member.display_name}"
                )
                return False
            except Exception as e:
                logger.error(f"RANK SYSTEM: Error removing old roles: {e}")

        # Add new rank role if they don't have it
        if new_role not in member.roles:
            try:
                await member.add_roles(
                    new_role,
                    reason=f"Automatic MMR rank update: {new_mmr} MMR")
                logger.info(
                    f"RANK SYSTEM: Added {new_rank['name']} role to {member.display_name} (MMR: {new_mmr})"
                )

                # Send DM notification about rank change (only for significant changes)
                #if not current_rank_role or current_rank_role.name != new_role.name:
                 #   try:
                  #      embed = discord.Embed(
                   #         title="🎖️ Rank Updated!",
                    #        description=
                     #       f"**Your rank has been updated automatically!**",
                      #      color=discord.Color.gold())
                       # embed.add_field(
                        #    name="New Rank",
                         #   value=f"{new_rank['emoji']} **{new_rank['name']}**",
                          #  inline=True)
                        #embed.add_field(name="Current MMR",
                         #               value=f"**{new_mmr}**",
                          #              inline=True)
                        #embed.add_field(
                         #   name="MMR Range",
                          #  value=
                           # f"{new_rank['min_mmr']} - {new_rank['max_mmr']}",
                            #inline=True)
                        #embed.add_field(
                         #   name="🔄 Auto-Update System",
                          #  value=
                           # "Your rank is automatically updated every 10 minutes!",
                            #inline=False)
                        #embed.set_footer(
                         #   text="Keep playing to climb higher ranks!")

                        #await member.send(embed=embed)
                        #logger.info(
                         #   f"RANK SYSTEM: Sent rank update DM to {member.display_name}"
                    #    )
                   # except discord.Forbidden:
                    #    logger.info(
                    #        f"RANK SYSTEM: Could not send DM to {member.display_name} (DMs disabled)"
                     #   )
                    #except Exception as e:
                     #   logger.warning(
                      #      f"RANK SYSTEM: Failed to send DM to {member.display_name}: {e}"
                       # )

            except discord.Forbidden:
                logger.error(
                    f"RANK SYSTEM: No permission to add role to {member.display_name}"
                )
                return False
            except Exception as e:
                logger.error(f"RANK SYSTEM: Error adding new role: {e}")
                return False

        return True

    except Exception as e:
        logger.error(
            f"RANK SYSTEM: Critical error updating rank for {user_id}: {e}")
        return False


async def sync_all_player_ranks(guild):
    """Sync all players' ranks based on their current MMR (Admin function)"""
    try:
        c.execute("SELECT id, username, mmr FROM players WHERE mmr > 0")
        players = c.fetchall()

        updated_count = 0
        for user_id, username, mmr in players:
            success = await update_player_rank_role(guild, user_id, mmr)
            if success:
                updated_count += 1

        logger.info(
            f"RANK SYSTEM: Synced ranks for {updated_count}/{len(players)} players"
        )
        return updated_count, len(players)

    except Exception as e:
        logger.error(f"RANK SYSTEM: Error syncing player ranks: {e}")
        return 0, 0


# Button Views for Professional Queue System
class QueueView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🎮 Join Queue',
                       style=discord.ButtonStyle.green,
                       custom_id='join_queue')
    async def join_queue(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        await handle_join_queue(interaction)

    @discord.ui.button(label='🚪 Leave Queue',
                       style=discord.ButtonStyle.red,
                       custom_id='leave_queue')
    async def leave_queue(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
        await handle_leave_queue(interaction)

    @discord.ui.button(label='📊 Queue Status',
                       style=discord.ButtonStyle.blurple,
                       custom_id='queue_status')
    async def queue_status(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await handle_queue_status(interaction)

    @discord.ui.button(label='🔔 Ping',
                       style=discord.ButtonStyle.secondary,
                       custom_id='ping_role')
    async def ping_role(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        await handle_ping_role(interaction)


async def handle_ping_role(interaction):
    global ping_cooldowns

    # حط هنا الـ ID الخاص بقناة الكيو فقط
    QUEUE_CHANNEL_ID = 1395514922573758584  # ← استبدل هذا بالـ ID الحقيقي

    # تأكد أننا في الشات الصحيح
    if interaction.channel.id != QUEUE_CHANNEL_ID:
        await interaction.response.send_message("❌ ما تقدر تسوي منشن هنا.",
                                                ephemeral=True)
        return

    # نظام الكولد داون - ساعة كاملة (3600 ثانية)
    user_id = str(interaction.user.id)
    current_time = datetime.now()

    # التحقق من آخر مرة استخدم المنشن
    if user_id in ping_cooldowns:
        last_ping_time = ping_cooldowns[user_id]
        time_diff = (current_time - last_ping_time).total_seconds()

        if time_diff < 3600:  # 3600 ثانية = ساعة كاملة
            remaining_time = int(3600 - time_diff)
            minutes = remaining_time // 60
            seconds = remaining_time % 60

            await interaction.response.send_message(
                f"❌ انتظر {minutes} دقيقة و {seconds} ثانية قبل استخدام المنشن مرة أخرى.",
                ephemeral=True)
            return

    # جلب الرتبة
    role = discord.utils.get(interaction.guild.roles, name="Queue Ping")

    # إذا فيه رتبة باسم "Queue Ping" نمنشنها، إذا لا نستخدم @here
    if role:
        mention = role.mention
    else:
        mention = "@here"

    # إرسال المنشن
    await interaction.response.send_message(f"{mention} تم منشنك لقيّم جديد 🎮")

    # تسجيل وقت آخر منشن
    ping_cooldowns[user_id] = current_time

    # تسجيل العملية في اللوق
    print(f"[LOG] {interaction.user} سوى منشن في {interaction.channel.name}")
    logger.info(
        f"PING: {interaction.user.display_name} used ping in {interaction.channel.name} - Next ping available in 1 hour"
    )


class MatchView(discord.ui.View):

    def __init__(self, match_id):
        super().__init__(timeout=None)
        self.match_id = match_id

    @discord.ui.button(label='🏆 Team 1 Won',
                       style=discord.ButtonStyle.green,
                       custom_id='team1_win')
    async def team1_win(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        try:
            await handle_match_result(interaction, 1, self.match_id)
        except Exception as e:
            logger.error(f"Error in team1_win button: {e}")
            await interaction.response.send_message(
                f"❌ Error processing Team 1 win: {e}", ephemeral=True)

    @discord.ui.button(label='🏆 Team 2 Won',
                       style=discord.ButtonStyle.green,
                       custom_id='team2_win')
    async def team2_win(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        try:
            await handle_match_result(interaction, 2, self.match_id)
        except Exception as e:
            logger.error(f"Error in team2_win button: {e}")
            await interaction.response.send_message(
                f"❌ Error processing Team 2 win: {e}", ephemeral=True)

    @discord.ui.button(label='❌ Cancel Match',
                       style=discord.ButtonStyle.secondary,
                       custom_id='cancel_match')
    async def cancel_match(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        try:
            await handle_cancel_match(interaction, self.match_id)
        except Exception as e:
            logger.error(f"Error in cancel_match button: {e}")
            await interaction.response.send_message(
                f"❌ Error canceling match: {e}", ephemeral=True)


class PrivateChatView(discord.ui.View):

    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label='🔒 Create Private Chat',
                       style=discord.ButtonStyle.blurple,
                       custom_id='create_private')
    async def create_private_chat(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        await handle_create_private_chat(interaction)

    @discord.ui.button(label='🗑️ Delete Private Chat',
                       style=discord.ButtonStyle.red,
                       custom_id='delete_private')
    async def delete_private_chat(self, interaction: discord.Interaction,
                                  button: discord.ui.Button):
        await handle_delete_private_chat(interaction)


class TeamSelectionView(discord.ui.View):

    def __init__(self, players, hsm_number):
        super().__init__(timeout=300)  # 5 minute timeout
        self.players = players
        self.hsm_number = hsm_number

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        # Only allow the queued players to select team distribution
        user_id = str(interaction.user.id)
        return any(p['id'] == user_id for p in self.players)

    @discord.ui.button(label="🎲 Random Teams",
                       style=discord.ButtonStyle.primary)
    async def random_teams(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await handle_random_team_selection(interaction, self.players,
                                           self.hsm_number)

    @discord.ui.button(label="👑 Captain Draft",
                       style=discord.ButtonStyle.secondary)
    async def captain_draft(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        await handle_captain_draft_selection(interaction, self.players,
                                             self.hsm_number)


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
                custom_id=f"pick_{player['id']}_{i}")
            # Create a callback for each button with the player ID
            button.callback = self.create_pick_callback(player['id'])
            self.add_item(button)

    def create_pick_callback(self, player_id):
        """Create a callback function for the specific player"""

        async def pick_callback(interaction: discord.Interaction):
            print(f"[DEBUG] Button clicked for player {player_id}")
            await handle_captain_pick(interaction, self.draft_id, player_id)

        return pick_callback

    async def interaction_check(self,
                                interaction: discord.Interaction) -> bool:
        # Only allow the current captain to pick
        draft_state = captain_draft_state.get(self.draft_id)
        if not draft_state:
            print(
                f"[DEBUG] Draft session expired for interaction check: {self.draft_id}"
            )
            await interaction.response.send_message("❌ Draft session expired!",
                                                    ephemeral=True)
            return False

        current_captain = draft_state['captains'][
            draft_state['current_captain']]
        user_id = str(interaction.user.id)
        print(
            f"[DEBUG] Interaction check - User: {user_id}, Current captain: {current_captain['id']}"
        )

        if user_id != current_captain['id']:
            print(f"[DEBUG] Not user's turn to pick")
            await interaction.response.send_message(
                "❌ It's not your turn to pick!", ephemeral=True)
            return False

        print(f"[DEBUG] Interaction check passed")
        return True


# Helper functions for button interactions
async def handle_join_queue(interaction: discord.Interaction):
    """Handle join queue button press"""
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ Please use the #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return

    add_or_update_player(interaction.user)
    user_id = str(interaction.user.id)

    # Check if player is already in queue
    if any(player['id'] == user_id for player in player_queue):
        await interaction.response.send_message(
            "❌ You are already in the queue!", ephemeral=True)
        return

    # Check if player is in an active match
    if any(user_id in match['players'] for match in active_matches.values()):
        await interaction.response.send_message(
            "❌ You are currently in an active match!", ephemeral=True)
        return

    # Add player to queue
    c.execute("SELECT username, mmr FROM players WHERE id = ?", (user_id, ))
    result = c.fetchone()
    if result:
        username, mmr = result
        player_queue.append({
            'id': user_id,
            'username': username,
            'mmr': mmr,
            'user': interaction.user
        })

        # Update queue activity for timeout system
        update_queue_activity()

        await interaction.response.send_message(
            f"✅ **{interaction.user.display_name}** joined the queue! ({len(player_queue)}/{QUEUE_SIZE})\n⏰ Queue timeout: {QUEUE_TIMEOUT_MINUTES} minutes",
            ephemeral=True)

        # Update the queue display
        await update_queue_display(interaction.channel)

        # Check if we have enough players to start a match
        if len(player_queue) >= QUEUE_SIZE:
            await create_match(interaction.channel, interaction.guild)


async def handle_leave_queue(interaction: discord.Interaction):
    """Handle leave queue button press"""
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ Please use the #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return

    user_id = str(interaction.user.id)

    # Remove player from queue
    global player_queue
    original_length = len(player_queue)
    player_queue = [p for p in player_queue if p['id'] != user_id]

    if len(player_queue) == original_length:
        await interaction.response.send_message("❌ You are not in the queue!",
                                                ephemeral=True)
        return

    # Update queue activity for timeout system
    update_queue_activity()

    await interaction.response.send_message(
        f"✅ **{interaction.user.display_name}** left the queue! ({len(player_queue)}/{QUEUE_SIZE})",
        ephemeral=True)

    # Update the queue display
    await update_queue_display(interaction.channel)


async def handle_queue_status(interaction: discord.Interaction):
    """Handle queue status button press"""
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ Please use the #{QUEUE_CHANNEL_NAME} channel!", ephemeral=True)
        return

    if not player_queue:
        embed = discord.Embed(
            title="📋 Queue Status",
            description=
            "Queue is empty. Click **🎮 Join Queue** to get started!",
            color=discord.Color.blue())
    else:
        embed = discord.Embed(
            title="📋 Queue Status",
            description=
            f"**{len(player_queue)}/{QUEUE_SIZE}** players in queue",
            color=discord.Color.blue())

        queue_text = ""
        for i, player in enumerate(player_queue, 1):
            queue_text += f"{i}. **{player['username']}** ({player['mmr']} MMR)\n"

        embed.add_field(name="Players in Queue",
                        value=queue_text,
                        inline=False)

    await interaction.response.send_message(embed=embed, ephemeral=True)


async def handle_match_result(interaction: discord.Interaction,
                              team_number: int, match_id: int):
    """Handle match result button press"""
    logger.info(
        f"MATCH RESULT: Processing team {team_number} win for match {match_id} by {interaction.user.display_name}"
    )

    try:
        if match_id not in active_matches:
            logger.warning(
                f"MATCH RESULT: Match {match_id} not found in active matches")
            await interaction.response.send_message(
                "❌ Match not found or already completed!", ephemeral=True)
            return

        match_data = active_matches[match_id]

        # Check if user is part of the match
        user_id = str(interaction.user.id)
        if user_id not in match_data['players']:
            logger.warning(
                f"MATCH RESULT: User {interaction.user.display_name} not in match {match_id} players"
            )
            await interaction.response.send_message(
                "❌ Only match participants can report results!",
                ephemeral=True)
            return

        # Validate team number
        if team_number not in [1, 2]:
            logger.error(
                f"MATCH RESULT: Invalid team number {team_number} for match {match_id}"
            )
            await interaction.response.send_message("❌ Invalid team number!",
                                                    ephemeral=True)
            return

        # Validate match data structure
        if 'team1' not in match_data or 'team2' not in match_data:
            logger.error(
                f"MATCH RESULT: Missing team data in match {match_id}")
            await interaction.response.send_message("❌ Match data corrupted!",
                                                    ephemeral=True)
            return

        # Validate team data is not empty
        if not match_data['team1'] or not match_data['team2']:
            logger.error(
                f"MATCH RESULT: Empty team data in match {match_id} - team1: {len(match_data['team1'])}, team2: {len(match_data['team2'])}"
            )
            await interaction.response.send_message(
                "❌ Match has empty team data!", ephemeral=True)
            return

        logger.info(
            f"MATCH RESULT: All validations passed for match {match_id} - team1: {len(match_data['team1'])}, team2: {len(match_data['team2'])}"
        )

    except Exception as e:
        logger.error(
            f"MATCH RESULT: Error in validation for match {match_id}: {e}")
        await interaction.response.send_message(
            f"❌ Error processing match result: {e}", ephemeral=True)
        return

    # Update match result
    winning_team = match_data['team1'] if team_number == 1 else match_data[
        'team2']
    losing_team = match_data['team2'] if team_number == 1 else match_data[
        'team1']

    # Calculate MMR changes
    mmr_changes = calculate_mmr_changes(winning_team, losing_team)

    # Update player stats and ranks with placement matches handling
    for player in winning_team:
        # Get old MMR for rank comparison
        old_mmr = player['mmr']
        new_mmr = old_mmr + mmr_changes['winners']

        # Check if player is in placement matches
        c.execute(
            "SELECT placement_matches_remaining, is_placed FROM players WHERE id = ?",
            (player['id'], ))
        placement_data = c.fetchone()

        if placement_data and placement_data[0] > 0 and placement_data[1] == 0:
            # Player is in placement matches
            remaining = placement_data[0] - 1
            if remaining == 0:
                # Finished placement matches
                c.execute(
                    "UPDATE players SET wins = wins + 1, mmr = mmr + ?, placement_matches_remaining = 0, is_placed = 1 WHERE id = ?",
                    (mmr_changes['winners'], player['id']))
                logger.info(
                    f"PLACEMENT: Player {player['id']} completed placement matches - Final MMR: {new_mmr}"
                )
            else:
                # Still in placement matches
                c.execute(
                    "UPDATE players SET wins = wins + 1, mmr = mmr + ?, placement_matches_remaining = ? WHERE id = ?",
                    (mmr_changes['winners'], remaining, player['id']))
                logger.info(
                    f"PLACEMENT: Player {player['id']} - {remaining} placement matches remaining"
                )
        else:
            # Normal player update
            c.execute(
                "UPDATE players SET wins = wins + 1, mmr = mmr + ? WHERE id = ?",
                (mmr_changes['winners'], player['id']))

        # Update rank role only if placement is complete
        if not placement_data or placement_data[0] <= 1:
            await update_player_rank_role(interaction.guild, player['id'],
                                          new_mmr)

    for player in losing_team:
        # Get old MMR for rank comparison
        old_mmr = player['mmr']
        new_mmr = old_mmr + mmr_changes['losers']

        # Check if player is in placement matches
        c.execute(
            "SELECT placement_matches_remaining, is_placed FROM players WHERE id = ?",
            (player['id'], ))
        placement_data = c.fetchone()

        if placement_data and placement_data[0] > 0 and placement_data[1] == 0:
            # Player is in placement matches
            remaining = placement_data[0] - 1
            if remaining == 0:
                # Finished placement matches
                c.execute(
                    "UPDATE players SET losses = losses + 1, mmr = mmr + ?, placement_matches_remaining = 0, is_placed = 1 WHERE id = ?",
                    (mmr_changes['losers'], player['id']))
                logger.info(
                    f"PLACEMENT: Player {player['id']} completed placement matches - Final MMR: {new_mmr}"
                )
            else:
                # Still in placement matches
                c.execute(
                    "UPDATE players SET losses = losses + 1, mmr = mmr + ?, placement_matches_remaining = ? WHERE id = ?",
                    (mmr_changes['losers'], remaining, player['id']))
                logger.info(
                    f"PLACEMENT: Player {player['id']} - {remaining} placement matches remaining"
                )
        else:
            # Normal player update
            c.execute(
                "UPDATE players SET losses = losses + 1, mmr = mmr + ? WHERE id = ?",
                (mmr_changes['losers'], player['id']))

        # Update rank role only if placement is complete
        if not placement_data or placement_data[0] <= 1:
            await update_player_rank_role(interaction.guild, player['id'],
                                          new_mmr)

    # Update match record
    c.execute("UPDATE matches SET winner = ?, ended_at = ? WHERE match_id = ?",
              (team_number, datetime.now().isoformat(), match_id))
    conn.commit()

    # Log the match completion
    log_match_event(
        "COMPLETED", f"Match {match_id}",
        f"Team {team_number} won - MMR changes: Winners +{mmr_changes['winners']}, Losers {mmr_changes['losers']}"
    )

    # CRITICAL FIX: Remove players from active match immediately after database update
    # This prevents players from being stuck in "active match" state
    match_data_copy = active_matches[match_id].copy(
    )  # Keep a copy for cleanup
    del active_matches[match_id]  # Remove from active matches immediately

    # Send DM notifications to all players
    await send_match_completion_dms(winning_team, losing_team, match_id,
                                    mmr_changes)

    # Create result embed
    embed = discord.Embed(title="🏆 MATCH COMPLETED!",
                          description=f"**Match #{match_id}** has ended!",
                          color=discord.Color.green())

    winner_mentions = ' '.join([p['user'].mention for p in winning_team])
    loser_mentions = ' '.join([p['user'].mention for p in losing_team])

    embed.add_field(
        name="🎉 Winners",
        value=f"{winner_mentions}\n**+{mmr_changes['winners']} MMR**",
        inline=True)
    embed.add_field(name="💔 Losers",
                    value=f"{loser_mentions}\n**{mmr_changes['losers']} MMR**",
                    inline=True)
    embed.add_field(
        name="📬 DMs Sent",
        value="All players have been notified with detailed results!",
        inline=False)
    embed.add_field(name="🎮 Queue Status",
                    value="Players can now rejoin the queue!",
                    inline=False)

    await interaction.response.send_message(embed=embed)

    # Post completed match to results channel with admin controls (use copied data)
    await post_match_to_results_channel_with_data(interaction.guild, match_id,
                                                  winning_team, losing_team,
                                                  mmr_changes, match_data_copy)

    # Clean up match channels using the copied data
    await cleanup_match_with_data(interaction.guild, match_id, match_data_copy)


async def handle_cancel_match(interaction: discord.Interaction, match_id: int):
    """Handle cancel match button press"""
    if match_id not in active_matches:
        await interaction.response.send_message(
            "❌ Match not found or already completed!", ephemeral=True)
        return

    match_data = active_matches[match_id]

    # Check if user is part of the match or has admin permissions
    user_id = str(interaction.user.id)
    if user_id not in match_data[
            'players'] and not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Only match participants or admins can cancel matches!",
            ephemeral=True)
        return

    # Log the cancellation
    log_match_event("CANCELLED", f"Match {match_id}",
                    f"Cancelled by {interaction.user.display_name}")

    # CRITICAL FIX: Remove players from active match immediately
    match_data_copy = active_matches[match_id].copy(
    )  # Keep a copy for cleanup
    del active_matches[match_id]  # Remove from active matches immediately

    await interaction.response.send_message(
        f"🚫 **Match #{match_id}** has been cancelled by {interaction.user.display_name}!\n🎮 Players can now rejoin the queue!"
    )

    # Clean up match channels using the copied data
    await cleanup_match_with_data(interaction.guild, match_id, match_data_copy)


# Private chat handler functions
async def handle_create_private_chat(interaction: discord.Interaction):
    """Handle create private chat button press"""
    user_id = str(interaction.user.id)

    # Check if user already has an active private chat
    c.execute(
        "SELECT hsm_number FROM private_chats WHERE creator_id = ? AND is_active = 1",
        (user_id, ))
    existing_chat = c.fetchone()

    if existing_chat:
        await interaction.response.send_message(
            f"❌ You already have an active private chat: **HSM{existing_chat[0]}**",
            ephemeral=True)
        return

    # Generate unique HSM number
    hsm_number = generate_hsm_number()
    if not hsm_number:
        await interaction.response.send_message(
            "❌ No available HSM numbers (1-9999 all used)", ephemeral=True)
        return

    try:
        # Get or create private chat category
        category = discord.utils.get(interaction.guild.categories,
                                     name=PRIVATE_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(
                name=PRIVATE_CATEGORY_NAME,
                reason="HSM Private Chats category")

        # Create private text channel
        private_channel = await interaction.guild.create_text_channel(
            name=f"hsm{hsm_number}",
            category=category,
            topic=
            f"🔒 HSM Private Chat #{hsm_number} - Created by {interaction.user.display_name}",
            overwrites={
                interaction.guild.default_role:
                discord.PermissionOverwrite(read_messages=False),
                interaction.user:
                discord.PermissionOverwrite(read_messages=True,
                                            send_messages=True,
                                            manage_messages=True,
                                            manage_channels=True),
                interaction.guild.me:
                discord.PermissionOverwrite(read_messages=True,
                                            send_messages=True,
                                            manage_messages=True)
            })

        # Create private voice channel
        private_voice = await interaction.guild.create_voice_channel(
            name=f"🔒 HSM{hsm_number} Voice",
            category=category,
            overwrites={
                interaction.guild.default_role:
                discord.PermissionOverwrite(view_channel=False),
                interaction.user:
                discord.PermissionOverwrite(view_channel=True,
                                            connect=True,
                                            speak=True,
                                            manage_channels=True),
                interaction.guild.me:
                discord.PermissionOverwrite(view_channel=True,
                                            connect=True,
                                            manage_channels=True)
            })

        # Save to database
        c.execute(
            """INSERT INTO private_chats (hsm_number, creator_id, channel_id, voice_channel_id, created_at) 
                     VALUES (?, ?, ?, ?, ?)""",
            (hsm_number, user_id, str(private_channel.id), str(
                private_voice.id), datetime.now().isoformat()))
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
            description=
            f"**Welcome to your private chat, {interaction.user.display_name}!**",
            color=discord.Color.purple())
        embed.add_field(name="HSM Number",
                        value=f"**HSM{hsm_number}**",
                        inline=True)
        embed.add_field(name="Creator",
                        value=interaction.user.mention,
                        inline=True)
        embed.add_field(name="Voice Channel",
                        value=private_voice.mention,
                        inline=True)
        embed.add_field(
            name="🔧 Managing Your Private Chat",
            value=
            "• **Add Members:** Right-click channel → Edit Channel → Permissions → Add members\n• **Voice Access:** Grant voice channel permissions to your friends\n• **Delete Chat:** Use the delete button in the main queue channel",
            inline=False)
        embed.set_footer(
            text="This is your private space - manage permissions as needed!")

        await private_channel.send(embed=embed)

        # Confirm to user
        await interaction.response.send_message(
            f"✅ **Private chat created successfully!**\n**HSM Number:** HSM{hsm_number}\n**Channel:** {private_channel.mention}\n**Voice:** {private_voice.mention}",
            ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to create channels!", ephemeral=True)
    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error creating private chat: {e}", ephemeral=True)


async def handle_delete_private_chat(interaction: discord.Interaction):
    """Handle delete private chat button press"""
    user_id = str(interaction.user.id)

    # Check if user has an active private chat
    c.execute(
        "SELECT hsm_number, channel_id, voice_channel_id FROM private_chats WHERE creator_id = ? AND is_active = 1",
        (user_id, ))
    chat_data = c.fetchone()

    if not chat_data:
        await interaction.response.send_message(
            "❌ You don't have any active private chats to delete!",
            ephemeral=True)
        return

    hsm_number, channel_id, voice_channel_id = chat_data

    try:
        # Delete text channel
        channel = interaction.guild.get_channel(int(channel_id))
        if channel:
            await channel.delete(
                reason=f"HSM{hsm_number} private chat deleted by owner")

        # Delete voice channel
        voice_channel = interaction.guild.get_channel(int(voice_channel_id))
        if voice_channel:
            await voice_channel.delete(
                reason=f"HSM{hsm_number} private chat deleted by owner")

        # Mark as inactive in database
        c.execute(
            "UPDATE private_chats SET is_active = 0 WHERE hsm_number = ?",
            (hsm_number, ))
        conn.commit()

        # Remove from memory
        if hsm_number in private_chats:
            del private_chats[hsm_number]
        used_hsm_numbers.discard(hsm_number)

        await interaction.response.send_message(
            f"✅ **HSM{hsm_number} private chat deleted successfully!**",
            ephemeral=True)

    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error deleting private chat: {e}", ephemeral=True)


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
    """Generate a sequential HSM number for match channels"""
    # Get the highest HSM number from completed matches
    c.execute(
        "SELECT MAX(hsm_number) FROM matches WHERE hsm_number IS NOT NULL")
    result = c.fetchone()

    if result and result[0] is not None:
        # Return the next number in sequence
        return result[0] + 1
    else:
        # First match starts with HSM1
        return 1


# Private match channel functions removed - simplified queue system

# Automatic Queue Timeout System
QUEUE_TIMEOUT_MINUTES = 5


# Automatic Rank Update System - تحديث الرتب كل 10 دقائق
@tasks.loop(minutes=10)
async def auto_update_ranks():
    """تحديث تلقائي للرتب كل 10 دقائق لجميع اللاعبين"""
    logger.info("AUTO RANK UPDATE: Starting automatic rank sync")

    try:
        # الحصول على جميع اللاعبين النشطين
        c.execute(
            "SELECT id, username, mmr FROM players WHERE wins > 0 OR losses > 0"
        )
        active_players = c.fetchall()

        updated_count = 0
        for guild in bot.guilds:
            for player_id, username, mmr in active_players:
                try:
                    # تحديث رتبة اللاعب
                    success = await update_player_rank_role(
                        guild, player_id, mmr)
                    if success:
                        updated_count += 1
                except Exception as e:
                    logger.error(
                        f"AUTO RANK UPDATE: Error updating {username}: {e}")

        logger.info(
            f"AUTO RANK UPDATE: Updated {updated_count} players across all guilds"
        )

    except Exception as e:
        logger.error(f"AUTO RANK UPDATE: System error: {e}")


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
        queue_channel = discord.utils.get(guild.channels,
                                          name=QUEUE_CHANNEL_NAME)
        if queue_channel:
            # Create timeout notification embed
            embed = discord.Embed(
                title="⏰ Queue Timeout - Automatic Cleanup",
                description=
                f"**Queue has been automatically cleared due to {QUEUE_TIMEOUT_MINUTES} minutes of inactivity!**",
                color=discord.Color.orange())
            embed.add_field(name="Players Removed",
                            value=f"**{queue_count}** players",
                            inline=True)
            embed.add_field(
                name="Reason",
                value=f"No activity for {QUEUE_TIMEOUT_MINUTES} minutes",
                inline=True)
            embed.add_field(name="Queue Status",
                            value="**CLEARED**",
                            inline=True)

            # List removed players
            if inactive_players:
                player_list = []
                for player in inactive_players:
                    player_list.append(
                        f"• {player['username']} ({player['mmr']} MMR)")

                if player_list:
                    embed.add_field(
                        name="Removed Players",
                        value="\n".join(
                            player_list[:10]),  # Limit to 10 players
                        inline=False)

            embed.add_field(
                name="💡 Next Steps",
                value=
                "Players can rejoin the queue using the buttons below.\nQueue will reset its timer when new players join.",
                inline=False)
            embed.set_footer(
                text=
                f"Automatic cleanup after {QUEUE_TIMEOUT_MINUTES} minutes of inactivity"
            )

            await queue_channel.send(embed=embed)

            # Update queue display
            await update_queue_display(queue_channel)

            print(
                f"Queue automatically cleared due to inactivity: {queue_count} players removed"
            )
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
    """Create match directly without showing team details in public"""
    global match_id_counter, player_queue

    # Get required players from queue
    match_players = player_queue[:QUEUE_SIZE]
    player_queue = player_queue[QUEUE_SIZE:]

    # Generate HSM number for the match
    hsm_number = generate_match_hsm_number()
    if not hsm_number:
        await queue_channel.send(
            "❌ No available HSM numbers for match creation!")
        return

    # Create teams randomly by default (no team selection in public)
    teams = create_balanced_teams(match_players)
    team1, team2 = teams

    # Create the match directly
    await create_final_match(guild, match_players, team1, team2, hsm_number,
                             "🎲 Automatic Distribution")

    # Update queue display
    await update_queue_display(queue_channel)


# Team selection handler functions
async def handle_random_team_selection(interaction: discord.Interaction,
                                       players, hsm_number):
    """Handle random team selection"""
    # Check if user is one of the queued players
    user_id = str(interaction.user.id)
    if not any(p['id'] == user_id for p in players):
        await interaction.response.send_message(
            "❌ Only queued players can select team distribution!",
            ephemeral=True)
        return

    # Create teams randomly
    teams = create_balanced_teams(players)
    team1, team2 = teams

    await interaction.response.send_message(
        "🎲 Random team distribution selected! Creating match...",
        ephemeral=True)

    # Create the match with the selected teams
    await create_final_match(interaction.guild, players, team1, team2,
                             hsm_number, "🎲 Random Distribution")


async def handle_captain_draft_selection(interaction: discord.Interaction,
                                         players, hsm_number):
    """Handle captain draft selection"""
    print(
        f"[DEBUG] Captain draft selection - Players: {len(players)}, HSM: {hsm_number}"
    )

    # Check if user is one of the queued players
    user_id = str(interaction.user.id)
    if not any(p['id'] == user_id for p in players):
        await interaction.response.send_message(
            "❌ Only queued players can select team distribution!",
            ephemeral=True)
        return

    # Sort players by MMR to get captains (top 2 players)
    sorted_players = sorted(players, key=lambda p: p['mmr'], reverse=True)
    captain1 = sorted_players[0]
    captain2 = sorted_players[1]
    available_players = sorted_players[2:]  # Remaining players

    print(f"[DEBUG] Captain 1: {captain1['username']} ({captain1['mmr']} MMR)")
    print(f"[DEBUG] Captain 2: {captain2['username']} ({captain2['mmr']} MMR)")
    print(
        f"[DEBUG] Available players: {[p['username'] for p in available_players]}"
    )

    # Create draft state
    draft_id = f"draft_{hsm_number}"
    # Dynamic pick order based on team size
    # For 1v1 (2 players total): no picks needed, just captains
    # For 2v2 (4 players total): 2 captains + 2 picks, each captain picks once
    # For 3v3 (6 players total): 2 captains + 4 picks, alternating picks
    if TEAM_SIZE == 1:
        pick_order = []  # No picks needed for 1v1
    elif TEAM_SIZE == 2:
        pick_order = [0, 1]  # Each captain picks once
    elif TEAM_SIZE == 3:
        pick_order = [0, 1, 1, 0]  # Alternating picks
    else:
        # Generate pick order for larger teams
        picks_needed = QUEUE_SIZE - 2  # Total picks needed (excluding captains)
        pick_order = []
        for i in range(picks_needed):
            pick_order.append(i % 2)  # Alternate between captains

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

    await interaction.response.send_message(
        "👑 Captain draft selected! Starting draft...", ephemeral=True)

    # Create draft embed
    embed = discord.Embed(
        title="👑 Captain Draft - Team Selection",
        description=
        f"**Match: HSM{hsm_number}**\n\nCaptains will draft their teams!",
        color=discord.Color.purple())

    embed.add_field(
        name="🔵 Team 1 Captain",
        value=f"**{captain1['username']}** ({captain1['mmr']} MMR)",
        inline=True)

    embed.add_field(
        name="🔴 Team 2 Captain",
        value=f"**{captain2['username']}** ({captain2['mmr']} MMR)",
        inline=True)

    embed.add_field(name="📋 Draft Order",
                    value="Captain 1 → Captain 2 (each picks once)",
                    inline=False)

    current_captain = captain_draft_state[draft_id]['captains'][0]
    embed.add_field(
        name="🎯 Current Turn",
        value=
        f"**{current_captain['username']}** - choose your first teammate!",
        inline=False)

    # Send draft interface
    try:
        view = CaptainDraftView(draft_id, 0, available_players)
        await interaction.followup.send(embed=embed, view=view)
        print(f"[DEBUG] Draft interface sent successfully")
    except Exception as e:
        print(f"[DEBUG] Error sending draft interface: {e}")
        await interaction.followup.send(
            f"❌ Error creating draft interface: {e}", ephemeral=True)


async def handle_captain_pick(interaction: discord.Interaction, draft_id,
                              player_id):
    """Handle captain player pick"""
    print(
        f"[DEBUG] Captain pick - Draft ID: {draft_id}, Player ID: {player_id}")

    draft_state = captain_draft_state.get(draft_id)
    if not draft_state:
        print(f"[DEBUG] Draft session not found: {draft_id}")
        await interaction.response.send_message("❌ Draft session not found!",
                                                ephemeral=True)
        return

    print(
        f"[DEBUG] Draft state found - Current pick: {draft_state['current_pick']}"
    )
    print(
        f"[DEBUG] Available players: {[p['username'] for p in draft_state['available_players']]}"
    )

    # Find the picked player
    picked_player = None
    for player in draft_state['available_players']:
        if player['id'] == player_id:
            picked_player = player
            break

    if not picked_player:
        print(f"[DEBUG] Player not available for picking: {player_id}")
        await interaction.response.send_message(
            "❌ Player not available for picking!", ephemeral=True)
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
        print(
            f"[DEBUG] Team 1: {[p['username'] for p in draft_state['team1']]}")
        print(
            f"[DEBUG] Team 2: {[p['username'] for p in draft_state['team2']]}")

        await interaction.response.send_message(
            "🎉 Draft complete! Creating match...", ephemeral=True)

        # Create the match
        try:
            await create_final_match(interaction.guild,
                                     draft_state['all_players'],
                                     draft_state['team1'],
                                     draft_state['team2'],
                                     draft_state['hsm_number'],
                                     "👑 Captain Draft")
            print(f"[DEBUG] Match created successfully")
        except Exception as e:
            print(f"[DEBUG] Error creating match: {e}")
            await interaction.followup.send(f"❌ Error creating match: {e}")
            return

        # Clean up draft state
        del captain_draft_state[draft_id]
        return

    # Continue draft
    draft_state['current_captain'] = draft_state['pick_order'][
        draft_state['current_pick']]
    current_captain = draft_state['captains'][draft_state['current_captain']]

    # Update the draft display
    embed = discord.Embed(
        title="👑 Captain Draft - Team Selection",
        description=
        f"**Match: HSM{draft_state['hsm_number']}**\n\n**{picked_player['username']}** picked!",
        color=discord.Color.purple())

    team1_names = [p['username'] for p in draft_state['team1']]
    team2_names = [p['username'] for p in draft_state['team2']]

    embed.add_field(name="🔴 Team 2",
                    value="\n".join([f"• {name}" for name in team1_names]),
                    inline=True)

    embed.add_field(name="🔵 Team 1",
                    value="\n".join([f"• {name}" for name in team2_names]),
                    inline=True)

    embed.add_field(
        name="🎯 Current Turn",
        value=f"**{current_captain['username']}** - choose your next teammate!",
        inline=False)

    # Send updated draft interface
    view = CaptainDraftView(draft_id, draft_state['current_captain'],
                            draft_state['available_players'])
    await interaction.response.edit_message(embed=embed, view=view)


async def create_final_match(guild, all_players, team1, team2, hsm_number,
                             distribution_method):
    """Create the final match with HSM number and private permissions"""
    global match_id_counter

    # Create match record
    match_id = match_id_counter
    match_id_counter += 1

    # Get or create match category
    category = discord.utils.get(guild.categories, name=MATCH_CATEGORY_NAME)
    if not category:
        category = await guild.create_category(
            name=MATCH_CATEGORY_NAME, reason="HeatSeeker match category")

    # Create permission overwrites for private match channel
    # Only allow match participants to see the channel
    overwrites = {
        guild.default_role:
        discord.PermissionOverwrite(read_messages=False),
        guild.me:
        discord.PermissionOverwrite(read_messages=True, send_messages=True)
    }

    # Add permissions for all match participants
    for player in all_players:
        member = player['user']
        overwrites[member] = discord.PermissionOverwrite(read_messages=True,
                                                         send_messages=True)

    # Check if channel with this HSM number already exists to prevent duplicates
    existing_channel = discord.utils.get(guild.channels,
                                         name=f"hsm{hsm_number}")
    if existing_channel:
        # Delete the existing channel to prevent duplicates
        await existing_channel.delete(
            reason="Preventing duplicate match channel")

    # Create dedicated private text channel for the match
    match_channel = await guild.create_text_channel(
        name=f"hsm{hsm_number}",
        category=category,
        topic=
        f"HeatSeeker Match HSM{hsm_number} - Private Match Channel - Server: MENA",
        overwrites=overwrites)

    # Check and delete existing voice channels to prevent duplicates
    existing_voice1 = discord.utils.get(guild.channels,
                                        name=f"🔵 Team 1 - HSM{hsm_number}")
    if existing_voice1:
        await existing_voice1.delete(
            reason="Preventing duplicate voice channel")

    existing_voice2 = discord.utils.get(guild.channels,
                                        name=f"🔴 Team 2 - HSM{hsm_number}")
    if existing_voice2:
        await existing_voice2.delete(
            reason="Preventing duplicate voice channel")

    # Create voice channels for each team with same permissions
    team1_voice = await guild.create_voice_channel(
        name=f"🔵 Team 1 - HSM{hsm_number}",
        category=category,
        user_limit=TEAM_SIZE,
        overwrites=overwrites)

    team2_voice = await guild.create_voice_channel(
        name=f"🔴 Team 2 - HSM{hsm_number}",
        category=category,
        user_limit=TEAM_SIZE,
        overwrites=overwrites)

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
        c.execute(
            """INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id, hsm_number) 
                     VALUES (?, ?, ?, ?, ?, ?)""",
            (match_id, team1_ids, team2_ids, datetime.now().isoformat(),
             str(match_channel.id), hsm_number))
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
                c.execute(
                    """INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id, hsm_number) 
                             VALUES (?, ?, ?, ?, ?, ?)""",
                    (match_id, team1_ids, team2_ids,
                     datetime.now().isoformat(), str(
                         match_channel.id), hsm_number))
                conn.commit()
                print(
                    f"[DEBUG] Match {match_id} saved to database successfully (retry)"
                )
            except Exception as e2:
                print(f"[DEBUG] Database error on retry: {e2}")
                raise e2
        else:
            raise e

    # Find queue channel to update display
    queue_channel = discord.utils.get(guild.channels, name=QUEUE_CHANNEL_NAME)
    if queue_channel:
        # Update queue display
        await update_queue_display(queue_channel)

    # Send detailed welcome message to private match channel with all team info
    match_type = f"{TEAM_SIZE}v{TEAM_SIZE}"
    welcome_embed = discord.Embed(
        title=f"🎮 Welcome to Match HSM{hsm_number}!",
        description=
        f"**Get ready for an epic {match_type} battle!**\n\n**Team Distribution:** {distribution_method}",
        color=discord.Color.purple())

    # Team 1 detailed info
    team1_mentions = ' '.join([p['user'].mention for p in team1])
    team1_info = '\n'.join(
        [f"• **{p['username']}** ({p['mmr']} MMR)" for p in team1])
    welcome_embed.add_field(
        name="🔵 Team 1",
        value=
        f"{team1_mentions}\n{team1_info}\n**Voice:** {team1_voice.mention}",
        inline=True)

    # Team 2 detailed info
    team2_mentions = ' '.join([p['user'].mention for p in team2])
    team2_info = '\n'.join(
        [f"• **{p['username']}** ({p['mmr']} MMR)" for p in team2])
    welcome_embed.add_field(
        name="🔴 Team 2",
        value=
        f"{team2_mentions}\n{team2_info}\n**Voice:** {team2_voice.mention}",
        inline=True)

    # Match statistics
    avg_mmr = sum(p['mmr'] for p in all_players) / len(all_players)
    welcome_embed.add_field(
        name="📊 Match Statistics",
        value=
        f"**Average MMR:** {avg_mmr:.0f}\n**Match ID:** {match_id}\n**Server:** MENA",
        inline=True)

    welcome_embed.add_field(
        name="🎮 How to Join Game",
        value=
        f"1. Join your team's voice channel\n2. Type match name: **HSM{hsm_number}**\n3. Start playing!",
        inline=False)

    welcome_embed.add_field(
        name="📝 How to Report Results",
        value=
        "Click the buttons below when your match is complete!\nOnly match participants can report results.",
        inline=False)

    welcome_embed.add_field(
        name="🔒 Private Channel",
        value="This channel is private and only visible to match participants.",
        inline=False)

    # Send with match buttons
    view = MatchView(match_id)
    await match_channel.send(embed=welcome_embed, view=view)

    # Clean up pending team selection
    if hsm_number in pending_team_selection:
        del pending_team_selection[hsm_number]

    # No need to clean up private match channels since we removed them


async def post_match_to_results_channel_with_data(guild, match_id,
                                                  winning_team, losing_team,
                                                  mmr_changes, match_data):
    """Post completed match to results channel with admin modification buttons using provided match data"""
    try:
        # Find the results channel
        results_channel = discord.utils.get(guild.text_channels,
                                            name=RESULTS_CHANNEL_NAME)
        if not results_channel:
            print(f"[DEBUG] Results channel not found, skipping results post")
            return

        hsm_number = match_data.get('hsm_number', 'N/A')
        distribution_method = match_data.get('distribution_method', 'Unknown')

        # Create completed match embed
        embed = discord.Embed(
            title=f"🏆 Match #{match_id} - HSM{hsm_number} Completed",
            description=
            f"**Match finished!** Team selection: {distribution_method}",
            color=discord.Color.green())

        # Winner info
        winner_names = [p['username'] for p in winning_team]
        winner_avg_mmr = sum(p['mmr']
                             for p in winning_team) / len(winning_team)
        embed.add_field(
            name="🎉 Winners",
            value=
            f"**Players:** {', '.join(winner_names)}\n**Avg MMR:** {winner_avg_mmr:.0f}\n**MMR Change:** +{mmr_changes['winners']}",
            inline=True)

        # Loser info
        loser_names = [p['username'] for p in losing_team]
        loser_avg_mmr = sum(p['mmr'] for p in losing_team) / len(losing_team)
        embed.add_field(
            name="💔 Losers",
            value=
            f"**Players:** {', '.join(loser_names)}\n**Avg MMR:** {loser_avg_mmr:.0f}\n**MMR Change:** {mmr_changes['losers']}",
            inline=True)

        # Match details
        embed.add_field(
            name="📊 Match Details",
            value=
            f"**Match ID:** #{match_id}\n**HSM Number:** {hsm_number}\n**Distribution:** {distribution_method}\n**Completed:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            inline=False)

        embed.add_field(
            name="🔧 Admin Controls",
            value=
            "Administrators can modify this match result using the buttons below if needed.",
            inline=False)

        embed.set_footer(
            text="Only administrators can modify completed matches")

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

    @discord.ui.button(label="🔄 Set Team 1 Winner",
                       style=discord.ButtonStyle.primary)
    async def set_team1_winner(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        """Admin: Set Team 1 as winner"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can modify match results!",
                ephemeral=True)
            return

        await self.modify_match_result(interaction, 1, "Team 1")

    @discord.ui.button(label="🔄 Set Team 2 Winner",
                       style=discord.ButtonStyle.primary)
    async def set_team2_winner(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        """Admin: Set Team 2 as winner"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can modify match results!",
                ephemeral=True)
            return

        await self.modify_match_result(interaction, 2, "Team 2")

    @discord.ui.button(label="🤝 Set Tie", style=discord.ButtonStyle.secondary)
    async def set_tie(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        """Admin: Set match as tie"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can modify match results!",
                ephemeral=True)
            return

        await self.modify_match_result(interaction, 0, "Tie")

    @discord.ui.button(label="🚫 Cancel Match",
                       style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        """Admin: Cancel match entirely"""
        if not interaction.user.guild_permissions.administrator:
            await interaction.response.send_message(
                "❌ Only administrators can modify match results!",
                ephemeral=True)
            return

        await self.modify_match_result(interaction, -1, "Cancelled")

    async def modify_match_result(self, interaction: discord.Interaction,
                                  winner_team: int, action_name: str):
        """Modify the match result in database and update the embed"""
        try:
            # Get original match data from database
            c.execute(
                "SELECT team1_players, team2_players, winner FROM matches WHERE match_id = ?",
                (self.match_id, ))
            result = c.fetchone()

            if not result:
                await interaction.response.send_message(
                    "❌ Match not found in database!", ephemeral=True)
                return

            team1_ids, team2_ids, current_winner = result
            team1_ids = team1_ids.split(',')
            team2_ids = team2_ids.split(',')

            # Revert previous changes first
            if current_winner == 1:  # Team 1 won previously
                for player_id in team1_ids:
                    c.execute(
                        "UPDATE players SET wins = wins - 1, mmr = mmr - 25 WHERE id = ?",
                        (player_id, ))
                for player_id in team2_ids:
                    c.execute(
                        "UPDATE players SET losses = losses - 1, mmr = mmr + 25 WHERE id = ?",
                        (player_id, ))
            elif current_winner == 2:  # Team 2 won previously
                for player_id in team2_ids:
                    c.execute(
                        "UPDATE players SET wins = wins - 1, mmr = mmr - 25 WHERE id = ?",
                        (player_id, ))
                for player_id in team1_ids:
                    c.execute(
                        "UPDATE players SET losses = losses - 1, mmr = mmr + 25 WHERE id = ?",
                        (player_id, ))

            # Apply new changes
            if winner_team == 1:  # Team 1 wins
                for player_id in team1_ids:
                    c.execute(
                        "UPDATE players SET wins = wins + 1, mmr = mmr + 25 WHERE id = ?",
                        (player_id, ))
                for player_id in team2_ids:
                    c.execute(
                        "UPDATE players SET losses = losses + 1, mmr = mmr - 25 WHERE id = ?",
                        (player_id, ))
            elif winner_team == 2:  # Team 2 wins
                for player_id in team2_ids:
                    c.execute(
                        "UPDATE players SET wins = wins + 1, mmr = mmr + 25 WHERE id = ?",
                        (player_id, ))
                for player_id in team1_ids:
                    c.execute(
                        "UPDATE players SET losses = losses + 1, mmr = mmr - 25 WHERE id = ?",
                        (player_id, ))
            # winner_team == 0 (tie) or -1 (cancelled) = no MMR changes

            # Update match record
            cancelled = 1 if winner_team == -1 else 0
            c.execute(
                "UPDATE matches SET winner = ?, admin_modified = 1, cancelled = ? WHERE match_id = ?",
                (winner_team, cancelled, self.match_id))
            conn.commit()

            # Update the embed
            embed = discord.Embed(
                title=f"🔧 Match #{self.match_id} - Admin Modified",
                description=
                f"**Match result changed to: {action_name}**\n\nModified by: {interaction.user.mention}",
                color=discord.Color.orange())

            embed.add_field(
                name="📝 Action Taken",
                value=
                f"**Result:** {action_name}\n**Modified By:** {interaction.user.display_name}\n**Time:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                inline=False)

            embed.set_footer(text="Match has been modified by administrator")

            # Update the message
            await interaction.response.edit_message(embed=embed, view=self)

            print(
                f"[DEBUG] Admin {interaction.user.display_name} modified match {self.match_id} to {action_name}"
            )

        except Exception as e:
            print(f"[DEBUG] Error modifying match {self.match_id}: {e}")
            await interaction.response.send_message(
                f"❌ Error modifying match: {e}", ephemeral=True)


async def cleanup_match_with_data(guild, match_id, match_data):
    """Clean up match channels and voice channels after match completion using provided match data"""
    hsm_number = match_data.get('hsm_number')

    try:
        # Delete match text channel
        match_channel = guild.get_channel(int(match_data['channel_id']))
        if match_channel:
            await match_channel.delete(
                reason=f"Match HSM{hsm_number} completed")
            log_match_event("CLEANUP", f"Match {match_id}",
                            f"Deleted match channel HSM{hsm_number}")

        # Delete voice channels
        team1_voice = guild.get_channel(int(match_data['team1_voice_id']))
        if team1_voice:
            await team1_voice.delete(reason=f"Match HSM{hsm_number} completed")
            log_match_event("CLEANUP", f"Match {match_id}",
                            f"Deleted Team 1 voice channel HSM{hsm_number}")

        team2_voice = guild.get_channel(int(match_data['team2_voice_id']))
        if team2_voice:
            await team2_voice.delete(reason=f"Match HSM{hsm_number} completed")
            log_match_event("CLEANUP", f"Match {match_id}",
                            f"Deleted Team 2 voice channel HSM{hsm_number}")

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
            await match_channel.delete(
                reason=f"Match HSM{hsm_number} completed")

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
            description=
            "**No players in queue**\nClick **🎮 Join Queue** to get started!",
            color=discord.Color.blue())
        embed.add_field(name="⏰ Queue Timeout",
                        value=f"{QUEUE_TIMEOUT_MINUTES} minutes of inactivity",
                        inline=True)
    else:
        embed = discord.Embed(
            title="🎮 HeatSeeker Queue",
            description=f"**{len(player_queue)}/{QUEUE_SIZE}** players ready",
            color=discord.Color.orange())

        queue_text = ""
        for i, player in enumerate(player_queue, 1):
            queue_text += f"{i}. **{player['username']}** ({player['mmr']} MMR)\n"

        embed.add_field(name="Players in Queue",
                        value=queue_text,
                        inline=False)

        # Show time remaining if there's activity
        if queue_last_activity:
            time_elapsed = datetime.now() - queue_last_activity
            time_remaining = timedelta(
                minutes=QUEUE_TIMEOUT_MINUTES) - time_elapsed
            if time_remaining.total_seconds() > 0:
                minutes_remaining = int(time_remaining.total_seconds() // 60)
                seconds_remaining = int(time_remaining.total_seconds() % 60)
                embed.add_field(
                    name="⏳ Time Remaining",
                    value=f"{minutes_remaining}m {seconds_remaining}s",
                    inline=True)
            else:
                embed.add_field(name="⏳ Time Remaining",
                                value="Clearing soon...",
                                inline=True)

        embed.add_field(name="⏰ Timeout",
                        value=f"{QUEUE_TIMEOUT_MINUTES} min inactivity",
                        inline=True)

    view = QueueView()
    await channel.send(embed=embed, view=view)


@bot.event
async def on_ready():
    logger.info(f'{bot.user} has connected to Discord!')
    add_sample_data()
    logger.info("Sample data added to database")
    initialize_match_counter()
    restore_active_matches()
    logger.info(
        f"Queue system will only work in channel: #{QUEUE_CHANNEL_NAME}")

    # Add persistent views
    bot.add_view(QueueView())
    bot.add_view(MatchView(None))  # Add as persistent view
    bot.add_view(PrivateChatView())  # Add private chat view
    logger.info(
        "Persistent views added for queue, match, and private chat systems")

    # Start the queue timeout check task
    if not check_queue_timeout.is_running():
        check_queue_timeout.start()
        logger.info(
            f"Started queue timeout system - {QUEUE_TIMEOUT_MINUTES} minute timeout"
        )

    # Start the automatic rank update task
    if not auto_update_ranks.is_running():
        auto_update_ranks.start()
        logger.info(
            "Started automatic rank update system - Updates every 10 minutes")

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
            match_type = f"{TEAM_SIZE}v{TEAM_SIZE}"
            embed = discord.Embed(
                title=
                f"🔥 HeatSeeker Bot - Professional {match_type} Queue System",
                description=
                "**Welcome to the ultimate competitive gaming experience!**\n\nUse the buttons below to interact with the queue system.",
                color=discord.Color.gold())

            embed.add_field(
                name="🎮 How It Works",
                value=
                f"• Click **🎮 Join Queue** to enter the {match_type} queue\n• When {QUEUE_SIZE} players join, a match will be created automatically\n• Each match gets dedicated text and voice channels\n• Teams are balanced based on MMR for fair gameplay",
                inline=False)

            embed.add_field(
                name="🏆 Features",
                value=
                f"• **Dedicated match channels** for each game\n• **Team voice channels** ({TEAM_SIZE} players max each)\n• **Automatic team balancing** based on skill\n• **Professional MMR tracking** system\n• **Auto-cleanup** after matches complete",
                inline=False)

            embed.set_footer(
                text="Ready to play? Click the buttons below to get started!")

            # Send initial queue display with buttons
            view = QueueView()
            await channel.send(embed=embed, view=view)

            # Send queue status
            await update_queue_display(channel)


# إضافة أو تحديث لاعب
def add_or_update_player(user):
    c.execute("SELECT * FROM players WHERE id = ?", (str(user.id), ))
    result = c.fetchone()
    if not result:
        # New player starts with placement matches
        c.execute(
            "INSERT INTO players (id, username, mmr, placement_matches_remaining, is_placed) VALUES (?, ?, ?, ?, ?)",
            (str(user.id), user.display_name, 1250, 5, 0))
        conn.commit()
        logger.info(
            f"NEW PLAYER: {user.display_name} created with 5 placement matches"
        )
    else:
        # Update display name if changed
        c.execute("UPDATE players SET username = ? WHERE id = ?",
                  (user.display_name, str(user.id)))
        conn.commit()

@bot.tree.command(
    name="player_mmr",
    description="Set a player's MMR by ID (Admin only)"
)
@app_commands.default_permissions(administrator=True)
async def player_mmr_command(interaction: discord.Interaction):
    """Admin command to set a player's MMR by ID with step-by-step buttons"""

    class InputPlayerIDView(discord.ui.View):
        def __init__(self):
            super().__init__(timeout=120)
            self.value = None

        @discord.ui.button(label="Input Player ID", style=discord.ButtonStyle.primary)
        async def input_player_id(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user != interaction.user:
                await button_interaction.response.send_message(
                    "❌ Only the admin who used the command can input the ID.", ephemeral=True)
                return

            class PlayerIDModal(discord.ui.Modal, title="Enter Player ID"):
                player_id = discord.ui.TextInput(
                    label="Player Discord ID",
                    placeholder="Enter the Discord user ID",
                    min_length=5,
                    max_length=25,
                    required=True
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    pid = self.player_id.value.strip()
                    # Check if player exists
                    c.execute("SELECT username FROM players WHERE id = ?", (pid,))
                    result = c.fetchone()
                    if not result:
                        await modal_interaction.response.send_message(
                            f"❌ No player found with ID `{pid}`.", ephemeral=True)
                        return

                    username = result[0]
                    # Proceed to next step: set MMR
                    class SetMMRView(discord.ui.View):
                        def __init__(self, pid, username):
                            super().__init__(timeout=120)
                            self.pid = pid
                            self.username = username

                        @discord.ui.button(label="Set Player MMR", style=discord.ButtonStyle.green)
                        async def set_player_mmr(self, mmr_interaction: discord.Interaction, button: discord.ui.Button):
                            if mmr_interaction.user != interaction.user:
                                await mmr_interaction.response.send_message(
                                    "❌ Only the admin who used the command can set the MMR.", ephemeral=True)
                                return

                            class MMRModal(discord.ui.Modal, title=f"Set MMR for {username}"):
                                mmr_value = discord.ui.TextInput(
                                    label="MMR Value",
                                    placeholder="Enter the new MMR (0-5000)",
                                    min_length=1,
                                    max_length=5,
                                    required=True
                                )

                                async def on_submit(self, mmr_modal_interaction: discord.Interaction):
                                    try:
                                        value = int(self.mmr_value.value)
                                        if value < 0 or value > 5000:
                                            await mmr_modal_interaction.response.send_message(
                                                "❌ Please enter a number between 0 and 5000.", ephemeral=True)
                                            return
                                        c.execute("UPDATE players SET mmr = ? WHERE id = ?", (value, pid))
                                        conn.commit()
                                        await mmr_modal_interaction.response.send_message(
                                            f"✅ Set **{username}**'s MMR to **{value}**.", ephemeral=True)
                                    except Exception as e:
                                        await mmr_modal_interaction.response.send_message(
                                            f"❌ Error: {e}", ephemeral=True)

                            await mmr_interaction.response.send_modal(MMRModal())

                    embed2 = discord.Embed(
                        title="Set Player MMR",
                        description=f"Player: **{username}** (`{pid}`)\nClick below to set their MMR.",
                        color=discord.Color.orange()
                    )
                    await modal_interaction.response.send_message(embed=embed2, view=SetMMRView(pid, username), ephemeral=True)

            await button_interaction.response.send_modal(PlayerIDModal())

    embed = discord.Embed(
        title="Set Player MMR",
        description="Please input player ID to begin.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(embed=embed, view=InputPlayerIDView(), ephemeral=True)

# أمر عرض الرانك
@bot.tree.command(name='rank',
                  description='Display your current rank and stats')
async def rank(interaction: discord.Interaction):
    """Display your current rank and stats"""
    add_or_update_player(interaction.user)
    c.execute(
        "SELECT mmr, wins, losses, placement_matches_remaining, is_placed FROM players WHERE id = ?",
        (str(interaction.user.id), ))
    result = c.fetchone()

    if result:
        mmr, wins, losses, placement_remaining, is_placed = result
        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0

        # Check if player is in placement matches
        if placement_remaining > 0 and is_placed == 0:
            # Player is in placement matches
            embed = discord.Embed(
                title=f"🔄 {interaction.user.display_name}'s Placement Matches",
                description=
                f"**Complete your placement matches to get ranked!**",
                color=discord.Color.orange())

            embed.add_field(
                name="🔄 Placement Status",
                value=
                f"**{placement_remaining} matches remaining**\nComplete all 5 to unlock your rank!",
                inline=False)

            embed.add_field(name="🏆 Current MMR",
                            value=f"**{mmr}**",
                            inline=True)
            embed.add_field(name="🎮 Wins", value=f"**{wins}**", inline=True)
            embed.add_field(name="💔 Losses",
                            value=f"**{losses}**",
                            inline=True)
            embed.add_field(name="📈 Win Rate",
                            value=f"**{win_rate:.1f}%**",
                            inline=True)
            embed.add_field(name="🎯 Games Played",
                            value=f"**{total_games}/5**",
                            inline=True)
            embed.add_field(name="🌍 Server", value="**MENA**", inline=True)

            embed.add_field(
                name="💡 Placement Matches Info",
                value=
                "• **Double MMR gains/losses** during placement\n• Your rank will be revealed after 5 matches\n• You won't appear in leaderboards until placed\n• Play strategically - these matches matter more!",
                inline=False)

            embed.add_field(
                name="🎯 What happens next?",
                value=
                f"After **{placement_remaining} more matches**, you'll receive your official rank based on your final MMR!",
                inline=False)

            embed.set_footer(
                text=
                f"Placement matches give double MMR • Current queue: {TEAM_SIZE}v{TEAM_SIZE}"
            )

        else:
            # Player has completed placement matches
            current_rank = get_rank_from_mmr(mmr, is_placed)

            # Calculate rank position (only among placed players)
            c.execute(
                "SELECT COUNT(*) FROM players WHERE mmr > ? AND is_placed = 1",
                (mmr, ))
            rank_position = c.fetchone()[0] + 1

            # Get total placed players
            c.execute("SELECT COUNT(*) FROM players WHERE is_placed = 1")
            total_placed_players = c.fetchone()[0]

            embed = discord.Embed(
                title=f"🎖️ {interaction.user.display_name}'s Rank & Stats",
                description=
                f"**Rank #{rank_position}** out of {total_placed_players} ranked players",
                color=discord.Color.gold())

            # Current Rank
            embed.add_field(
                name="🏅 Current Rank",
                value=
                f"{current_rank['emoji']} **{current_rank['name']}**\nMMR Range: {current_rank['min_mmr']} - {current_rank['max_mmr']}",
                inline=False)

            embed.add_field(name="🏆 MMR", value=f"**{mmr}**", inline=True)
            embed.add_field(name="🎮 Wins", value=f"**{wins}**", inline=True)
            embed.add_field(name="💔 Losses",
                            value=f"**{losses}**",
                            inline=True)
            embed.add_field(name="📈 Win Rate",
                            value=f"**{win_rate:.1f}%**",
                            inline=True)
            embed.add_field(name="🎯 Total Games",
                            value=f"**{total_games}**",
                            inline=True)
            embed.add_field(name="🌍 Server", value="**MENA**", inline=True)

            # Progress to next rank
            next_rank = None
            for rank_key, rank_data in RANK_ROLES.items():
                if rank_data['min_mmr'] > mmr:
                    if next_rank is None or rank_data['min_mmr'] < next_rank[
                            'min_mmr']:
                        next_rank = rank_data

            if next_rank:
                mmr_needed = next_rank['min_mmr'] - mmr
                embed.add_field(
                    name="🎯 Next Rank",
                    value=
                    f"{next_rank['emoji']} **{next_rank['name']}**\nNeed **{mmr_needed}** more MMR",
                    inline=False)
            else:
                embed.add_field(
                    name="🏆 Achievement",
                    value=
                    "**You've reached the highest rank!**\nCongratulations, Legendary Seeker!",
                    inline=False)

            embed.set_footer(
                text=
                f"Placement completed • Current queue: {TEAM_SIZE}v{TEAM_SIZE} • Keep playing to climb ranks!"
            )

            # Auto-sync rank role
            await update_player_rank_role(interaction.guild,
                                          str(interaction.user.id), mmr)

        await interaction.response.send_message(embed=embed)

    else:
        await interaction.response.send_message(
            "❌ Error retrieving your stats. Please try again.")


# Combined leaderboard pagination view
class CombinedLeaderboardView(discord.ui.View):

    def __init__(self, current_page=1):
        super().__init__(timeout=300)
        self.current_page = current_page
        self.items_per_page = 15

    @discord.ui.button(label="◀️ السابق", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_combined_leaderboard(interaction)
        else:
            await interaction.response.send_message(
                "❌ أنت في الصفحة الأولى بالفعل!", ephemeral=True)

    @discord.ui.button(label="▶️ التالي", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        # Check if there are more pages
        c.execute(
            "SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0 OR placement_matches_remaining < 5"
        )
        total_active_players = c.fetchone()[0]
        total_pages = (total_active_players + self.items_per_page -
                       1) // self.items_per_page

        if self.current_page < total_pages:
            self.current_page += 1
            await self.update_combined_leaderboard(interaction)
        else:
            await interaction.response.send_message(
                "❌ أنت في الصفحة الأخيرة بالفعل!", ephemeral=True)

    async def update_combined_leaderboard(self,
                                          interaction: discord.Interaction):
        """Update the combined leaderboard display"""
        offset = (self.current_page - 1) * self.items_per_page
        c.execute(
            """
            SELECT id, username, mmr, wins, losses, placement_matches_remaining, is_placed
            FROM players 
            WHERE wins > 0 OR losses > 0 OR placement_matches_remaining < 5
            ORDER BY 
                CASE WHEN is_placed = 1 THEN 0 ELSE 1 END,
                mmr DESC 
            LIMIT ? OFFSET ?
        """, (self.items_per_page, offset))

        page_players = c.fetchall()

        # Get total counts
        c.execute(
            "SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0 OR placement_matches_remaining < 5"
        )
        total_active_players = c.fetchone()[0]
        total_pages = (total_active_players + self.items_per_page -
                       1) // self.items_per_page

        c.execute("SELECT COUNT(*) FROM players WHERE is_placed = 1")
        total_ranked = c.fetchone()[0]

        c.execute(
            "SELECT COUNT(*) FROM players WHERE placement_matches_remaining > 0 AND is_placed = 0"
        )
        total_placement = c.fetchone()[0]

        if page_players:
            embed = discord.Embed(
                title="🏆 لوحة المتصدرين الشاملة",
                description=
                f"**جميع اللاعبين النشطين** (الصفحة {self.current_page}/{total_pages})",
                color=discord.Color.gold())

            # Separate players
            ranked_players = []
            placement_players = []

            for player_data in page_players:
                if player_data[6] == 1:  # is_placed
                    ranked_players.append(player_data)
                else:
                    placement_players.append(player_data)

            leaderboard_text = ""

            # Show ranked players first
            if ranked_players:
                leaderboard_text += "**🏅 اللاعبين المصنفين:**\n\n"
                for i, (player_id, username, mmr, wins, losses, _,
                        _) in enumerate(ranked_players):
                    # Calculate global rank for medals
                    c.execute(
                        "SELECT COUNT(*) FROM players WHERE mmr > ? AND is_placed = 1",
                        (mmr, ))
                    global_rank = c.fetchone()[0] + 1

                    medal = "🥇" if global_rank == 1 else "🥈" if global_rank == 2 else "🥉" if global_rank == 3 else f"**{global_rank}.**"
                    total_games = wins + losses
                    win_rate = (wins / total_games *
                                100) if total_games > 0 else 0

                    # Get rank info
                    rank_info = get_rank_from_mmr(mmr, True)
                    rank_emoji = rank_info['emoji']

                    # Get display name
                    try:
                        member = interaction.guild.get_member(int(player_id))
                        display_name = member.display_name if member else username
                        if len(display_name) > 12:
                            display_name = display_name[:9] + "..."
                    except:
                        display_name = username
                        if len(display_name) > 12:
                            display_name = display_name[:9] + "..."

                    leaderboard_text += f"{medal} {rank_emoji} **{display_name}** - {mmr} MMR\n"
                    leaderboard_text += f"     W: {wins} | L: {losses} | WR: {win_rate:.1f}%\n\n"

            # Show placement players
            if placement_players:
                leaderboard_text += "**🔄 لاعبين في مباريات التأهيل:**\n\n"
                for player_data in placement_players:
                    player_id, username, mmr, wins, losses, placement_remaining, _ = player_data
                    total_games = wins + losses
                    win_rate = (wins / total_games *
                                100) if total_games > 0 else 0

                    # Get display name
                    try:
                        member = interaction.guild.get_member(int(player_id))
                        display_name = member.display_name if member else username
                        if len(display_name) > 12:
                            display_name = display_name[:9] + "..."
                    except:
                        display_name = username
                        if len(display_name) > 12:
                            display_name = display_name[:9] + "..."

                    leaderboard_text += f"🔄 **{display_name}** - {mmr} MMR\n"
                    leaderboard_text += f"     W: {wins} | L: {losses} | WR: {win_rate:.1f}% | **{placement_remaining} متبقي**\n\n"

            embed.add_field(name="📊 اللاعبين النشطين",
                            value=leaderboard_text,
                            inline=False)

            embed.add_field(
                name="📈 الإحصائيات",
                value=
                f"**مصنفين:** {total_ranked}\n**في التأهيل:** {total_placement}",
                inline=True)

            embed.add_field(name="🎮 الطابور",
                            value=f"**{TEAM_SIZE}v{TEAM_SIZE}**",
                            inline=True)

            embed.set_footer(
                text=
                f"عرض {len(page_players)} لاعب • الصفحة {self.current_page}/{total_pages}"
            )

            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="🏆 لوحة المتصدرين الشاملة",
                description="**لا يوجد لاعبين في هذه الصفحة!**",
                color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=None)


# Legacy leaderboard view for backward compatibility
class LeaderboardView(discord.ui.View):

    def __init__(self, current_page=1):
        super().__init__(timeout=300)
        self.current_page = current_page
        self.items_per_page = 10

    @discord.ui.button(label="◀️ Previous", style=discord.ButtonStyle.primary)
    async def previous_page(self, interaction: discord.Interaction,
                            button: discord.ui.Button):
        if self.current_page > 1:
            self.current_page -= 1
            await self.update_leaderboard(interaction)
        else:
            await interaction.response.send_message(
                "❌ You're already on the first page!", ephemeral=True)

    @discord.ui.button(label="▶️ Next", style=discord.ButtonStyle.primary)
    async def next_page(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        # Check if there are more pages
        c.execute("SELECT COUNT(*) FROM players WHERE wins > 0 OR losses > 0")
        total_active_players = c.fetchone()[0]
        total_pages = (total_active_players + self.items_per_page -
                       1) // self.items_per_page

        if self.current_page < total_pages:
            self.current_page += 1
            await self.update_leaderboard(interaction)
        else:
            await interaction.response.send_message(
                "❌ You're already on the last page!", ephemeral=True)

    async def update_leaderboard(self, interaction: discord.Interaction):
        """Update the leaderboard display"""
        # Get only players who have completed placement matches
        offset = (self.current_page - 1) * self.items_per_page
        c.execute(
            """
            SELECT id, username, mmr, wins, losses 
            FROM players 
            WHERE is_placed = 1
            ORDER BY mmr DESC 
            LIMIT ? OFFSET ?
        """, (self.items_per_page, offset))

        page_players = c.fetchall()

        # Get total count for pagination info
        c.execute("SELECT COUNT(*) FROM players WHERE is_placed = 1")
        total_ranked_players = c.fetchone()[0]
        total_pages = (total_ranked_players + self.items_per_page -
                       1) // self.items_per_page

        if page_players:
            embed = discord.Embed(
                title="🏆 HeatSeeker Leaderboard",
                description=
                f"**Ranked Players Only** (Page {self.current_page}/{total_pages})",
                color=discord.Color.gold())

            leaderboard_text = ""
            for i, (player_id, username, mmr, wins,
                    losses) in enumerate(page_players):
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

                # Get rank info
                rank_info = get_rank_from_mmr(mmr, True)
                rank_emoji = rank_info['emoji']

                # Get the actual Discord member to show display name
                try:
                    member = interaction.guild.get_member(int(player_id))
                    display_name = member.display_name if member else username
                except:
                    display_name = username

                leaderboard_text += f"{medal} {rank_emoji} **{display_name}** - {mmr} MMR\n"
                leaderboard_text += f"     W: {wins} | L: {losses} | WR: {win_rate:.1f}%\n\n"

            embed.description += f"\n\n{leaderboard_text}"
            embed.set_footer(
                text=
                f"Showing {len(page_players)} ranked players • Only players who completed placement matches"
            )

            await interaction.response.edit_message(embed=embed, view=self)
        else:
            embed = discord.Embed(
                title="🏆 HeatSeeker Leaderboard",
                description=
                "**No ranked players found!**\n\nComplete placement matches to appear on the leaderboard.",
                color=discord.Color.gold())
            await interaction.response.edit_message(embed=embed, view=None)


# Traditional command versions for better compatibility
@bot.command(name='queueplayer')
async def queueplayer_cmd(ctx, players: int):
    """Set the number of players for the queue (2=1v1, 4=2v2, 6=3v3, etc.)"""

    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can change queue settings!")
        return

    # Validate player count
    if players < 2 or players > 20:
        await ctx.send("❌ Number of players must be between 2 and 20!")
        return

    if players % 2 != 0:
        await ctx.send("❌ Number of players must be even (2, 4, 6, 8, etc.)!")
        return

    # Update global queue configuration
    global QUEUE_SIZE, TEAM_SIZE
    QUEUE_SIZE = players
    TEAM_SIZE = players // 2

    # Clear current queue if any
    global player_queue
    if player_queue:
        player_queue.clear()

    # Create configuration embed
    embed = discord.Embed(
        title="⚙️ Queue Configuration Updated!",
        description=f"Queue system has been reconfigured successfully",
        color=discord.Color.green())

    embed.add_field(
        name="🎯 New Configuration",
        value=
        f"**Total Players:** {QUEUE_SIZE}\n**Team Size:** {TEAM_SIZE}v{TEAM_SIZE}\n**Teams:** 2 teams",
        inline=True)

    embed.add_field(name="🌍 Server Region",
                    value="**MENA** (Middle East & North Africa)",
                    inline=True)

    embed.add_field(name="📝 Status",
                    value="✅ **Active** - Players can now join the queue",
                    inline=True)

    embed.add_field(
        name="🔄 Queue Reset",
        value=
        "Current queue has been cleared\nPlayers need to rejoin with new configuration",
        inline=False)

    embed.set_footer(
        text=f"Configuration changed by {ctx.author.display_name}")

    await ctx.send(embed=embed)

    # Update queue display if queue channel exists
    queue_channel = discord.utils.get(ctx.guild.channels,
                                      name=QUEUE_CHANNEL_NAME)
    if queue_channel:
        await update_queue_display(queue_channel)

    # Log the change
    logger.info(
        f"Queue configuration changed to {TEAM_SIZE}v{TEAM_SIZE} ({QUEUE_SIZE} players) by {ctx.author.display_name}"
    )


@bot.command(name='setleaderboard')
async def setleaderboard_cmd(ctx):
    """Set the current channel as auto-updating leaderboard"""

    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can set leaderboard channel!")
        return

    global leaderboard_channel
    leaderboard_channel = ctx.channel

    # Start the leaderboard update task
    if not update_leaderboard.is_running():
        update_leaderboard.start()

    embed = discord.Embed(
        title="✅ Leaderboard Channel Set!",
        description=
        "This channel will now display the auto-updating leaderboard",
        color=discord.Color.green())

    embed.add_field(name="📊 Update Frequency",
                    value="**Every 30 minutes** automatically",
                    inline=True)

    embed.add_field(name="🌍 Server Region",
                    value="**MENA** (Middle East & North Africa)",
                    inline=True)

    embed.add_field(
        name="🎯 Current Queue",
        value=f"**{TEAM_SIZE}v{TEAM_SIZE}** ({QUEUE_SIZE} players)",
        inline=True)

    embed.add_field(
        name="📝 Features",
        value=
        "• Top 10 players by MMR\n• Win/Loss statistics\n• Auto-refresh every 30 minutes\n• Shows current queue configuration",
        inline=False)

    embed.set_footer(
        text="First leaderboard update will appear in a few seconds")

    await ctx.send(embed=embed)

    # Trigger immediate update
    await update_leaderboard()

    logger.info(
        f"Leaderboard channel set to {ctx.channel.name} by {ctx.author.display_name}"
    )


@bot.command(name='creatematch')
async def creatematch_cmd(ctx, match_name: str):
    """Create a custom match with specific HSM name"""

    # Check if user is admin
    if not ctx.author.guild_permissions.administrator:
        await ctx.send("❌ Only administrators can create custom matches!")
        return

    # Validate match name format
    if not match_name.upper().startswith('HSM'):
        await ctx.send(
            "❌ Match name must start with 'HSM' (e.g., HSM1, HSM2, HSM3)")
        return

    # Extract HSM number
    try:
        hsm_number = int(match_name.upper().replace('HSM', ''))
        if hsm_number < 1 or hsm_number > 9999:
            await ctx.send("❌ HSM number must be between 1 and 9999")
            return
    except ValueError:
        await ctx.send("❌ Invalid HSM number format. Use HSM1, HSM2, etc.")
        return

    # Check if match with this HSM number already exists
    existing_match = None
    for match_id, match_data in active_matches.items():
        if match_data.get('hsm_number') == hsm_number:
            existing_match = match_id
            break

    if existing_match:
        await ctx.send(
            f"❌ Match HSM{hsm_number} already exists! Use a different number.")
        return

    # Create embed for match creation
    embed = discord.Embed(
        title="🎮 Custom Match Created!",
        description=f"**Match HSM{hsm_number}** is ready for players!",
        color=discord.Color.green())

    embed.add_field(name="🏷️ Match Name",
                    value=f"**HSM{hsm_number}**",
                    inline=True)

    embed.add_field(name="🌍 Server Region",
                    value="**MENA** (Middle East & North Africa)",
                    inline=True)

    embed.add_field(name="📝 Status",
                    value="**Waiting for players**",
                    inline=True)

    embed.add_field(
        name="🎯 How Players Join",
        value=
        f"1. Players type: **HSM{hsm_number}**\n2. Join the match channels\n3. Start playing!",
        inline=False)

    # Get or create match category
    category = discord.utils.get(ctx.guild.categories,
                                 name=MATCH_CATEGORY_NAME)
    if not category:
        category = await ctx.guild.create_category(
            name=MATCH_CATEGORY_NAME, reason="HeatSeeker match category")

    # Create the match channels
    try:
        # Delete existing channels with same name to prevent duplicates
        existing_channel = discord.utils.get(ctx.guild.channels,
                                             name=f"hsm{hsm_number}")
        if existing_channel:
            await existing_channel.delete(reason="Recreating match channel")

        # Create text channel
        match_channel = await ctx.guild.create_text_channel(
            name=f"hsm{hsm_number}",
            category=category,
            topic=
            f"HeatSeeker Match HSM{hsm_number} - Custom Match - Server: MENA")

        # Create voice channel
        voice_channel = await ctx.guild.create_voice_channel(
            name=f"🎮 HSM{hsm_number} - Game Room",
            category=category,
            user_limit=QUEUE_SIZE)

        embed.add_field(
            name="📍 Match Channels",
            value=
            f"**Text:** {match_channel.mention}\n**Voice:** {voice_channel.mention}",
            inline=False)

        embed.set_footer(text="Match channels created successfully!")

        await ctx.send(embed=embed)

        # Send welcome message to match channel
        welcome_embed = discord.Embed(
            title=f"🎮 Welcome to Match HSM{hsm_number}!",
            description=
            "**Custom match created by admin**\n\nPlayers can now join and start playing!",
            color=discord.Color.purple())

        welcome_embed.add_field(name="🌍 Server Region",
                                value="**MENA** (Middle East & North Africa)",
                                inline=True)

        welcome_embed.add_field(name="🎯 Match Name",
                                value=f"**HSM{hsm_number}**",
                                inline=True)

        welcome_embed.add_field(
            name="📝 Instructions",
            value="1. Join the voice channel\n2. Start your game\n3. Have fun!",
            inline=False)

        await match_channel.send(embed=welcome_embed)

    except Exception as e:
        await ctx.send(f"❌ Error creating match channels: {e}")


# Stats command
@bot.command(name='stats')
async def stats(ctx, member: discord.Member = None):
    """Display stats for a specific player"""
    target_user = member or ctx.author

    c.execute("SELECT username, mmr, wins, losses FROM players WHERE id = ?",
              (str(target_user.id), ))
    result = c.fetchone()

    if result:
        username, mmr, wins, losses = result
        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0

        embed = discord.Embed(title=f"📊 {username}'s Statistics",
                              color=discord.Color.green())
        embed.add_field(name="MMR", value=f"**{mmr}**", inline=True)
        embed.add_field(name="Wins", value=f"**{wins}**", inline=True)
        embed.add_field(name="Losses", value=f"**{losses}**", inline=True)
        embed.add_field(name="Total Games",
                        value=f"**{total_games}**",
                        inline=True)
        embed.add_field(name="Win Rate",
                        value=f"**{win_rate:.1f}%**",
                        inline=True)

        # Calculate rank position
        c.execute("SELECT COUNT(*) FROM players WHERE mmr > ?", (mmr, ))
        rank_position = c.fetchone()[0] + 1
        embed.add_field(name="Rank",
                        value=f"**#{rank_position}**",
                        inline=True)

        await ctx.send(embed=embed)
    else:
        await ctx.send(
            f"❌ No stats found for {target_user.mention}. Use `/rank` to initialize your profile."
        )


# Additional traditional commands
@bot.command(name='rank')
async def rank_cmd(ctx):
    """Display your current rank and stats"""
    add_or_update_player(ctx.author)
    user_id = str(ctx.author.id)

    c.execute("SELECT username, mmr, wins, losses FROM players WHERE id = ?",
              (user_id, ))
    result = c.fetchone()

    if result:
        username, mmr, wins, losses = result

        # Get current rank information
        current_rank = get_rank_from_mmr(mmr)

        # Calculate rank position
        c.execute("SELECT COUNT(*) FROM players WHERE mmr > ?", (mmr, ))
        rank_position = c.fetchone()[0] + 1

        # Get total players
        c.execute("SELECT COUNT(*) FROM players")
        total_players = c.fetchone()[0]

        total_games = wins + losses
        win_rate = (wins / total_games * 100) if total_games > 0 else 0

        embed = discord.Embed(
            title=f"🎖️ {username}'s Rank & Stats",
            description=
            f"**Rank #{rank_position}** out of {total_players} players",
            color=discord.Color.gold())

        # Current Rank
        embed.add_field(
            name="🏅 Current Rank",
            value=
            f"{current_rank['emoji']} **{current_rank['name']}**\nMMR Range: {current_rank['min_mmr']} - {current_rank['max_mmr']}",
            inline=False)

        embed.add_field(name="🏆 MMR", value=f"**{mmr}**", inline=True)
        embed.add_field(name="🎮 Wins", value=f"**{wins}**", inline=True)
        embed.add_field(name="💔 Losses", value=f"**{losses}**", inline=True)
        embed.add_field(name="📈 Win Rate",
                        value=f"**{win_rate:.1f}%**",
                        inline=True)
        embed.add_field(name="🎯 Total Games",
                        value=f"**{total_games}**",
                        inline=True)
        embed.add_field(name="🌍 Server", value="**MENA**", inline=True)

        # Progress to next rank
        next_rank = None
        for rank_key, rank_data in RANK_ROLES.items():
            if rank_data['min_mmr'] > mmr:
                if next_rank is None or rank_data['min_mmr'] < next_rank[
                        'min_mmr']:
                    next_rank = rank_data

        if next_rank:
            mmr_needed = next_rank['min_mmr'] - mmr
            embed.add_field(
                name="🎯 Next Rank",
                value=
                f"{next_rank['emoji']} **{next_rank['name']}**\nNeed **{mmr_needed}** more MMR",
                inline=False)

        embed.set_footer(
            text=
            f"Use !top to see the leaderboard • Current queue: {TEAM_SIZE}v{TEAM_SIZE}"
        )

        await ctx.send(embed=embed)

        # Auto-sync rank role
        await update_player_rank_role(ctx.guild, user_id, mmr)


@bot.command(name='commands')
async def help_cmd(ctx):
    """Display all available commands"""
    embed = discord.Embed(
        title="🎮 HeatSeeker Bot Commands",
        description="**Complete Command List - Traditional & Slash Commands**",
        color=discord.Color.blue())

    # Basic commands
    embed.add_field(
        name="📊 Player Commands",
        value=
        "**Traditional:**\n`!rank` - Your rank and stats\n`!stats @user` - Player stats\n`!commands` - Show all commands\n\n**Slash:**\n`/rank` - Your rank and stats\n`/stats @user` - Player stats\n`/help` - Show all commands",
        inline=False)

    # Queue commands
    embed.add_field(
        name="🎯 Queue Commands",
        value=
        "**Use buttons in queue channel or:**\n`/queue` - Join queue\n`/leave` - Leave queue\n`/win team:1` or `/win team:2` - Report match result",
        inline=False)

    # Admin commands
    embed.add_field(
        name="⚙️ Admin Commands",
        value=
        "**Traditional:**\n`!queueplayer 2` - Set to 1v1\n`!queueplayer 4` - Set to 2v2\n`!queueplayer 6` - Set to 3v3\n`!setleaderboard` - Set leaderboard channel\n`!creatematch HSM1` - Create custom match\n\n**Slash:**\n`/queueplayer players:2` - Set queue size\n`/set_leaderboard` - Set leaderboard channel\n`/create_match match_name:HSM1` - Create custom match\n`/setup` - Create queue system\n`/cancel_queue` - Cancel queue\n`/reset_queue` - Reset queue\n`/admin_match` - Admin panel\n`/game_log` - Game history",
        inline=False)

    # Private chat
    embed.add_field(name="🔒 Private Chat",
                    value="`/private` - Create private HSM chat",
                    inline=False)

    # Current configuration
    embed.add_field(
        name="🎮 Current Configuration",
        value=
        f"**Queue Size:** {QUEUE_SIZE} players\n**Team Size:** {TEAM_SIZE}v{TEAM_SIZE}\n**Server:** MENA (Middle East & North Africa)",
        inline=False)

    embed.set_footer(
        text="Use ! for traditional commands or / for slash commands")

    await ctx.send(embed=embed)


# Queue system commands - PUBLIC COMMANDS
@bot.tree.command(name='queue', description='Join the queue')
async def queue(interaction: discord.Interaction):
    """Join the queue"""
    # Check if command is used in correct channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ Please use queue commands in #{QUEUE_CHANNEL_NAME} channel!",
            ephemeral=True)
        return

    add_or_update_player(interaction.user)
    user_id = str(interaction.user.id)

    # Check if player is already in queue
    if any(player['id'] == user_id for player in player_queue):
        await interaction.response.send_message(
            "❌ You are already in the queue!", ephemeral=True)
        return

    # Check if player is in an active match
    if any(user_id in match['players'] for match in active_matches.values()):
        await interaction.response.send_message(
            "❌ You are currently in an active match!", ephemeral=True)
        return

    # Add player to queue
    c.execute("SELECT username, mmr FROM players WHERE id = ?", (user_id, ))
    result = c.fetchone()
    if result:
        username, mmr = result
        player_queue.append({
            'id': user_id,
            'username': username,
            'mmr': mmr,
            'user': interaction.user
        })

        embed = discord.Embed(
            title="🎮 Joined Queue",
            description=f"{interaction.user.mention} joined the queue!",
            color=discord.Color.green())
        embed.add_field(name="Players in Queue",
                        value=f"{len(player_queue)}/{QUEUE_SIZE}",
                        inline=True)
        embed.add_field(name="Your MMR", value=f"{mmr}", inline=True)

        await interaction.response.send_message(embed=embed)

        # Check if we have enough players to start a match
        if len(player_queue) >= QUEUE_SIZE:
            await start_match_slash(interaction)


@bot.tree.command(name='leave', description='Leave the queue')
async def leave_queue(interaction: discord.Interaction):
    """Leave the queue"""
    # Check if command is used in correct channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ Please use queue commands in #{QUEUE_CHANNEL_NAME} channel!",
            ephemeral=True)
        return

    user_id = str(interaction.user.id)

    # Remove player from queue
    global player_queue
    player_queue = [p for p in player_queue if p['id'] != user_id]

    embed = discord.Embed(
        title="🚪 Left Queue",
        description=f"{interaction.user.mention} left the queue.",
        color=discord.Color.orange())
    embed.add_field(name="Players in Queue",
                    value=f"{len(player_queue)}/{QUEUE_SIZE}",
                    inline=True)

    await interaction.response.send_message(embed=embed)


@bot.tree.command(name='status',
                  description='Show current queue status (Admin only)')
@app_commands.default_permissions(administrator=True)
async def queue_status(interaction: discord.Interaction):
    """Show current queue status"""
    # Check if command is used in correct channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ Please use queue commands in #{QUEUE_CHANNEL_NAME} channel!",
            ephemeral=True)
        return

    if not player_queue:
        embed = discord.Embed(
            title="📋 Queue Status",
            description="Queue is empty. Use `/queue` to join!",
            color=discord.Color.blue())
    else:
        embed = discord.Embed(
            title="📋 Queue Status",
            description=f"Players in queue: {len(player_queue)}/4",
            color=discord.Color.blue())

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
    c.execute(
        """INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id) 
                 VALUES (?, ?, ?, ?, ?)""",
        (match_id, team1_ids, team2_ids, datetime.now().isoformat(),
         str(ctx.channel.id)))
    conn.commit()

    # Create match announcement
    embed = discord.Embed(title="🏆 MATCH FOUND!",
                          description=f"Match #{match_id} is ready to start!",
                          color=discord.Color.gold())

    # Team 1
    team1_mentions = ' '.join([p['user'].mention for p in team1])
    team1_info = '\n'.join(
        [f"{p['username']} ({p['mmr']} MMR)" for p in team1])
    embed.add_field(name="🔵 Team 1",
                    value=f"{team1_mentions}\n{team1_info}",
                    inline=True)

    # Team 2
    team2_mentions = ' '.join([p['user'].mention for p in team2])
    team2_info = '\n'.join(
        [f"{p['username']} ({p['mmr']} MMR)" for p in team2])
    embed.add_field(name="🔴 Team 2",
                    value=f"{team2_mentions}\n{team2_info}",
                    inline=True)

    # Average MMR
    avg_mmr = sum(p['mmr'] for p in match_players) / 4
    embed.add_field(name="📊 Average MMR", value=f"{avg_mmr:.0f}", inline=False)

    embed.add_field(
        name="📝 Report Results",
        value=
        f"Use `/win 1` or `/win 2` to report the winning team\nMatch ID: {match_id}",
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
    c.execute(
        """INSERT INTO matches (match_id, team1_players, team2_players, created_at, channel_id) 
                 VALUES (?, ?, ?, ?, ?)""",
        (match_id, team1_ids, team2_ids, datetime.now().isoformat(),
         str(interaction.channel.id)))
    conn.commit()

    # Create match announcement
    embed = discord.Embed(title="🏆 MATCH FOUND!",
                          description=f"Match #{match_id} is ready to start!",
                          color=discord.Color.gold())

    # Team 1
    team1_mentions = ' '.join([p['user'].mention for p in team1])
    team1_info = '\n'.join(
        [f"{p['username']} ({p['mmr']} MMR)" for p in team1])
    embed.add_field(name="🔴 Team 2",
                    value=f"{team1_mentions}\n{team1_info}",
                    inline=True)

    # Team 2
    team2_mentions = ' '.join([p['user'].mention for p in team2])
    team2_info = '\n'.join(
        [f"{p['username']} ({p['mmr']} MMR)" for p in team2])
    embed.add_field(name="🔵 Team 1",
                    value=f"{team2_mentions}\n{team2_info}",
                    inline=True)

    # Average MMR
    avg_mmr = sum(p['mmr'] for p in match_players) / 4
    embed.add_field(name="📊 Average MMR", value=f"{avg_mmr:.0f}", inline=False)

    embed.add_field(
        name="📝 Report Results",
        value=
        f"Use `/win team:1` or `/win team:2` to report the winning team\nMatch ID: {match_id}",
        inline=False)

    await interaction.followup.send(embed=embed)


def create_balanced_teams(players):
    """Create balanced teams based on MMR"""
    # Sort players by MMR
    sorted_players = sorted(players, key=lambda x: x['mmr'], reverse=True)

    # Calculate team size based on queue configuration
    team_size = TEAM_SIZE

    logger.info(
        f"TEAM CREATION: Creating balanced teams with {team_size} players per team from {len(players)} total players"
    )

    # Generate all possible team combinations
    best_diff = float('inf')
    best_teams = None

    for team1_combo in combinations(sorted_players, team_size):
        team1 = list(team1_combo)
        team2 = [p for p in sorted_players if p not in team1]

        team1_mmr = sum(p['mmr'] for p in team1)
        team2_mmr = sum(p['mmr'] for p in team2)
        diff = abs(team1_mmr - team2_mmr)

        if diff < best_diff:
            best_diff = diff
            best_teams = (team1, team2)

    logger.info(f"TEAM CREATION: Best MMR difference: {best_diff}")
    logger.info(
        f"TEAM CREATION: Team1 players: {[p['username'] for p in best_teams[0]]}"
    )
    logger.info(
        f"TEAM CREATION: Team2 players: {[p['username'] for p in best_teams[1]]}"
    )

    return best_teams


async def send_match_completion_dms(winning_team, losing_team, match_id,
                                    mmr_changes):
    """Send DM notifications to all players about match completion with advanced analysis"""

    # Get advanced stats from mmr_changes
    performance_note = mmr_changes.get('performance_note', 'Standard Match')
    expected_probability = mmr_changes.get('expected_probability', 0.5)
    mmr_difference = mmr_changes.get('mmr_difference', 0)
    winner_k_factor = mmr_changes.get('winner_k_factor', 25)
    loser_k_factor = mmr_changes.get('loser_k_factor', 25)

    # Send to winners
    for player in winning_team:
        try:
            user = bot.get_user(int(player['id']))
            if user:
                # Determine victory type
                if "UPSET" in performance_note:
                    title_emoji = "🔥"
                    title_text = "UPSET VICTORY!"
                    color = discord.Color.gold()
                elif "Expected" in performance_note:
                    title_emoji = "🏆"
                    title_text = "EXPECTED VICTORY"
                    color = discord.Color.green()
                else:
                    title_emoji = "🎉"
                    title_text = "VICTORY!"
                    color = discord.Color.green()

                embed = discord.Embed(
                    title=f"{title_emoji} {title_text}",
                    description=
                    f"**Congratulations on your victory in Match #{match_id}!**",
                    color=color)

                embed.add_field(name="🏆 Result",
                                value=f"**{title_text}**",
                                inline=True)
                embed.add_field(name="📈 MMR Change",
                                value=f"**+{mmr_changes['winners']} MMR**",
                                inline=True)
                embed.add_field(name="🎮 Match ID",
                                value=f"#{match_id}",
                                inline=True)

                # Advanced match analysis
                embed.add_field(
                    name="🔍 Match Analysis",
                    value=
                    f"**Performance:** {performance_note}\n**Win Probability:** {expected_probability:.1%}\n**MMR Difference:** {mmr_difference:+.0f}\n**K-Factor:** {winner_k_factor:.1f}",
                    inline=False)

                # Get updated player stats
                c.execute("SELECT mmr, wins, losses FROM players WHERE id = ?",
                          (player['id'], ))
                result = c.fetchone()
                if result:
                    mmr, wins, losses = result
                    total_games = wins + losses
                    win_rate = (wins / total_games *
                                100) if total_games > 0 else 0

                    # Get rank info
                    current_rank = get_rank_from_mmr(mmr)

                    embed.add_field(
                        name="📊 Your Updated Stats",
                        value=
                        f"**MMR:** {mmr} {current_rank['emoji']}\n**Wins:** {wins}\n**Losses:** {losses}\n**Win Rate:** {win_rate:.1f}%",
                        inline=True)

                # Personalized motivation based on performance
                if "UPSET" in performance_note:
                    motivation = "🔥 **INCREDIBLE UPSET!** You defeated a stronger opponent! This victory shows your true potential is higher than your current MMR suggests. Keep this momentum!"
                elif expected_probability < 0.3:
                    motivation = "💪 **UNDERDOG VICTORY!** You proved that skill matters more than numbers. This is how champions are made!"
                elif expected_probability > 0.7:
                    motivation = "✅ **SOLID PERFORMANCE!** You played at your expected level and secured the win. Consistency is key to climbing ranks!"
                else:
                    motivation = "🎯 **BALANCED VICTORY!** You outplayed an evenly matched opponent. Keep developing your skills!"

                embed.add_field(name="🔥 Performance Analysis",
                                value=motivation,
                                inline=False)

                # Strategic advice
                if mmr_difference > 100:
                    advice = "💡 **Tip:** Try to find stronger opponents to maximize your MMR gains!"
                elif mmr_difference < -50:
                    advice = "💡 **Tip:** Great job beating stronger players! This is the fastest way to climb ranks."
                else:
                    advice = "💡 **Tip:** Continue playing against similar-skilled opponents for steady progression."

                embed.add_field(name="📈 Strategy Tip",
                                value=advice,
                                inline=False)

                embed.set_footer(
                    text=
                    "Professional MMR System • Use /queue to find your next challenge"
                )

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
                    color=discord.Color.red())

                embed.add_field(name="📉 Result",
                                value="**DEFEAT**",
                                inline=True)
                embed.add_field(name="📉 MMR Change",
                                value=f"**{mmr_changes['losers']} MMR**",
                                inline=True)
                embed.add_field(name="🎮 Match ID",
                                value=f"#{match_id}",
                                inline=True)

                # Advanced match analysis
                embed.add_field(
                    name="🔍 Match Analysis",
                    value=
                    f"**Performance:** {performance_note}\n**Enemy Win Probability:** {expected_probability:.1%}\n**MMR Difference:** {mmr_difference:+.0f}\n**K-Factor:** {loser_k_factor:.1f}",
                    inline=False)

                # Get updated player stats
                c.execute("SELECT mmr, wins, losses FROM players WHERE id = ?",
                          (player['id'], ))
                result = c.fetchone()
                if result:
                    mmr, wins, losses = result
                    total_games = wins + losses
                    win_rate = (wins / total_games *
                                100) if total_games > 0 else 0

                    # Get rank info
                    current_rank = get_rank_from_mmr(mmr)

                    embed.add_field(
                        name="📊 Your Updated Stats",
                        value=
                        f"**MMR:** {mmr} {current_rank['emoji']}\n**Wins:** {wins}\n**Losses:** {losses}\n**Win Rate:** {win_rate:.1f}%",
                        inline=True)

                # Personalized motivation based on performance
                if "UPSET" in performance_note and mmr_difference < -100:
                    motivation = "😤 **TOUGH LOSS!** You lost to a much weaker opponent. This happens to everyone - analyze what went wrong and bounce back stronger!"
                elif expected_probability > 0.7:
                    motivation = "💪 **FOUGHT THE ODDS!** You faced a stronger opponent and gave it your best. Losses against better players are part of improvement!"
                elif mmr_difference > 0:
                    motivation = "🎯 **LEARNING OPPORTUNITY!** You lost to a weaker opponent - review this match and identify areas for improvement."
                else:
                    motivation = "⚔️ **CLOSE BATTLE!** This was an evenly matched fight. Small improvements in your gameplay will tip the scales next time!"

                embed.add_field(name="💭 Analysis & Motivation",
                                value=motivation,
                                inline=False)

                # Strategic advice for improvement
                if abs(mmr_changes['losers']) > 30:
                    advice = "🎯 **Focus:** High MMR loss indicates room for improvement. Practice your fundamentals!"
                elif abs(mmr_changes['losers']) < 15:
                    advice = "✅ **Good:** Low MMR loss shows you're playing at your level. Small adjustments needed!"
                else:
                    advice = "📊 **Standard:** Normal MMR loss. Keep practicing and you'll win the next one!"

                embed.add_field(name="📈 Improvement Tip",
                                value=advice,
                                inline=False)

                embed.add_field(
                    name="🔄 Next Steps",
                    value=
                    "Every champion has losses! Learn from this match, practice your skills, and come back stronger. The ranking system is designed to help you improve!",
                    inline=False)

                embed.set_footer(
                    text=
                    "Professional MMR System • Don't give up! Use /queue for your comeback"
                )

                await user.send(embed=embed)
        except Exception as e:
            print(f"Failed to send DM to loser {player['id']}: {e}")


# Admin Match Control Panel View
class AdminMatchControlView(discord.ui.View):

    def __init__(self, match_id):
        super().__init__(timeout=300)
        self.match_id = match_id

    @discord.ui.button(label="🏆 Team 1 Wins", style=discord.ButtonStyle.green)
    async def team1_wins(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        await self.admin_set_winner(interaction, 1)

    @discord.ui.button(label="🏆 Team 2 Wins", style=discord.ButtonStyle.green)
    async def team2_wins(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        await self.admin_set_winner(interaction, 2)

    @discord.ui.button(label="🤝 Tie/Draw", style=discord.ButtonStyle.secondary)
    async def tie_match(self, interaction: discord.Interaction,
                        button: discord.ui.Button):
        await self.admin_set_tie(interaction)

    @discord.ui.button(label="🚫 Cancel Match",
                       style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await self.admin_cancel_match(interaction)

    async def admin_set_winner(self, interaction: discord.Interaction,
                               team_number: int):
        """Admin sets match winner"""
        if self.match_id not in active_matches:
            await interaction.response.send_message(
                "❌ Match not found or already completed!", ephemeral=True)
            return

        match_data = active_matches[self.match_id]

        # Process match result
        winning_team = match_data['team1'] if team_number == 1 else match_data[
            'team2']
        losing_team = match_data['team2'] if team_number == 1 else match_data[
            'team1']

        # Calculate MMR changes
        mmr_changes = calculate_mmr_changes(winning_team, losing_team)

        # Update player stats
        for player in winning_team:
            c.execute(
                "UPDATE players SET wins = wins + 1, mmr = mmr + ? WHERE id = ?",
                (mmr_changes['winners'], player['id']))

        for player in losing_team:
            c.execute(
                "UPDATE players SET losses = losses + 1, mmr = mmr + ? WHERE id = ?",
                (mmr_changes['losers'], player['id']))

        # Update match record
        c.execute(
            "UPDATE matches SET winner = ?, ended_at = ?, admin_modified = 1 WHERE match_id = ?",
            (team_number, datetime.now().isoformat(), self.match_id))
        conn.commit()

        # Send DM notifications
        await send_match_completion_dms(winning_team, losing_team,
                                        self.match_id, mmr_changes)

        # Update admin panel
        embed = discord.Embed(
            title="✅ Match Result Set",
            description=f"**Match #{self.match_id}** completed by admin",
            color=discord.Color.green())

        winner_names = [p['username'] for p in winning_team]
        loser_names = [p['username'] for p in losing_team]

        embed.add_field(
            name="🎉 Winners",
            value=f"{', '.join(winner_names)}\n+{mmr_changes['winners']} MMR",
            inline=True)
        embed.add_field(
            name="💔 Losers",
            value=f"{', '.join(loser_names)}\n{mmr_changes['losers']} MMR",
            inline=True)
        embed.add_field(name="Admin",
                        value=interaction.user.mention,
                        inline=True)

        await interaction.response.edit_message(embed=embed, view=None)

        # Clean up match
        await cleanup_match(interaction.guild, self.match_id)

    async def admin_set_tie(self, interaction: discord.Interaction):
        """Admin sets match as tie"""
        if self.match_id not in active_matches:
            await interaction.response.send_message(
                "❌ Match not found or already completed!", ephemeral=True)
            return

        match_data = active_matches[self.match_id]

        # No MMR changes for tie
        c.execute(
            "UPDATE matches SET winner = 0, ended_at = ?, admin_modified = 1 WHERE match_id = ?",
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
                        description=
                        f"**Match #{self.match_id} ended in a tie!**",
                        color=discord.Color.orange())
                    embed.add_field(name="📊 Result",
                                    value="**TIE**",
                                    inline=True)
                    embed.add_field(name="📈 MMR Change",
                                    value="**No change**",
                                    inline=True)
                    embed.add_field(name="🎮 Match ID",
                                    value=f"#{self.match_id}",
                                    inline=True)
                    embed.add_field(
                        name="💪 Motivation",
                        value=
                        "A tie shows both teams were evenly matched! Great competition!",
                        inline=False)
                    await user.send(embed=embed)
            except Exception as e:
                print(f"Failed to send tie DM to {player['id']}: {e}")

        embed = discord.Embed(
            title="🤝 Match Tied",
            description=f"**Match #{self.match_id}** set as tie by admin",
            color=discord.Color.orange())
        embed.add_field(name="Result", value="No MMR changes", inline=True)
        embed.add_field(name="Admin",
                        value=interaction.user.mention,
                        inline=True)

        await interaction.response.edit_message(embed=embed, view=None)

        # Clean up match
        await cleanup_match(interaction.guild, self.match_id)

    async def admin_cancel_match(self, interaction: discord.Interaction):
        """Admin cancels match"""
        if self.match_id not in active_matches:
            await interaction.response.send_message(
                "❌ Match not found or already completed!", ephemeral=True)
            return

        match_data = active_matches[self.match_id]

        # Mark match as cancelled
        c.execute(
            "UPDATE matches SET cancelled = 1, ended_at = ?, admin_modified = 1 WHERE match_id = ?",
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
                        description=
                        f"**Match #{self.match_id} has been cancelled by an administrator.**",
                        color=discord.Color.red())
                    embed.add_field(name="📊 Result",
                                    value="**CANCELLED**",
                                    inline=True)
                    embed.add_field(name="📈 MMR Change",
                                    value="**No change**",
                                    inline=True)
                    embed.add_field(name="🎮 Match ID",
                                    value=f"#{self.match_id}",
                                    inline=True)
                    embed.add_field(
                        name="💪 Next Steps",
                        value=
                        "Don't worry! Use /queue to find a new match and continue playing!",
                        inline=False)
                    await user.send(embed=embed)
            except Exception as e:
                print(f"Failed to send cancellation DM to {player['id']}: {e}")

        embed = discord.Embed(
            title="🚫 Match Cancelled",
            description=f"**Match #{self.match_id}** cancelled by admin",
            color=discord.Color.red())
        embed.add_field(name="Result", value="No changes made", inline=True)
        embed.add_field(name="Admin",
                        value=interaction.user.mention,
                        inline=True)

        await interaction.response.edit_message(embed=embed, view=None)

        # Clean up match
        await cleanup_match(interaction.guild, self.match_id)


@bot.tree.command(name='win', description='Report the winning team (1 or 2)')
@app_commands.describe(team="Which team won? (1 or 2)")
async def report_win(interaction: discord.Interaction, team: int):
    """Report the winning team (1 or 2) - FIXED: No longer duplicates with button system"""
    await interaction.response.send_message(
        "❌ Please use the match buttons in your dedicated match channel to report results!",
        ephemeral=True)


def calculate_mmr_changes(winning_team, losing_team):
    """Calculate MMR changes using professional ELO-based system with placement matches support"""
    logger.info(
        f"MMR CALCULATION: Winning team size={len(winning_team)}, Losing team size={len(losing_team)}"
    )

    # Safety check for empty teams
    if len(winning_team) == 0 or len(losing_team) == 0:
        logger.error(
            f"MMR CALCULATION: Empty team detected! Winning={len(winning_team)}, Losing={len(losing_team)}"
        )
        return {'winners': 25, 'losers': -25}  # Default MMR change

    try:
        # Calculate team averages
        avg_winner_mmr = sum(p['mmr']
                             for p in winning_team) / len(winning_team)
        avg_loser_mmr = sum(p['mmr'] for p in losing_team) / len(losing_team)
        mmr_difference = avg_winner_mmr - avg_loser_mmr

        logger.info(
            f"MMR CALCULATION: Winner avg={avg_winner_mmr:.1f}, Loser avg={avg_loser_mmr:.1f}, Diff={mmr_difference:.1f}"
        )

        # Check for placement matches
        winner_placement_players = []
        loser_placement_players = []

        for player in winning_team:
            c.execute(
                "SELECT placement_matches_remaining, is_placed FROM players WHERE id = ?",
                (player['id'], ))
            result = c.fetchone()
            if result and result[0] > 0 and result[1] == 0:
                winner_placement_players.append(player['id'])

        for player in losing_team:
            c.execute(
                "SELECT placement_matches_remaining, is_placed FROM players WHERE id = ?",
                (player['id'], ))
            result = c.fetchone()
            if result and result[0] > 0 and result[1] == 0:
                loser_placement_players.append(player['id'])

        # Calculate K-factor based on player experience and MMR
        def get_k_factor(player_mmr, total_games, is_placement=False):
            """Get K-factor based on player level and experience"""
            if is_placement:
                return 80  # Double MMR for placement matches
            elif total_games < 10:
                return 40  # New players - fast progression
            elif player_mmr < 800:
                return 30  # Lower skill - moderate progression
            elif player_mmr < 1050:
                return 25  # Average skill - normal progression
            elif player_mmr < 1300:
                return 20  # High skill - slower progression
            else:
                return 15  # Elite players - very stable

        # Calculate average K-factor for each team
        winner_k_factors = []
        loser_k_factors = []

        for player in winning_team:
            c.execute(
                "SELECT wins, losses, placement_matches_remaining, is_placed FROM players WHERE id = ?",
                (player['id'], ))
            result = c.fetchone()
            total_games = (result[0] + result[1]) if result else 0
            is_placement = result[2] > 0 and result[3] == 0 if result else False
            k_factor = get_k_factor(player['mmr'], total_games, is_placement)
            winner_k_factors.append(k_factor)

        for player in losing_team:
            c.execute(
                "SELECT wins, losses, placement_matches_remaining, is_placed FROM players WHERE id = ?",
                (player['id'], ))
            result = c.fetchone()
            total_games = (result[0] + result[1]) if result else 0
            is_placement = result[2] > 0 and result[3] == 0 if result else False
            k_factor = get_k_factor(player['mmr'], total_games, is_placement)
            loser_k_factors.append(k_factor)

        avg_winner_k = sum(winner_k_factors) / len(winner_k_factors)
        avg_loser_k = sum(loser_k_factors) / len(loser_k_factors)

        # Calculate expected probability using ELO formula
        # P(A wins) = 1 / (1 + 10^((RB - RA) / 400))
        expected_winner_probability = 1 / (
            1 + pow(10, (avg_loser_mmr - avg_winner_mmr) / 400))
        expected_loser_probability = 1 - expected_winner_probability

        logger.info(
            f"MMR CALCULATION: Expected win probability - Winner: {expected_winner_probability:.3f}, Loser: {expected_loser_probability:.3f}"
        )

        # Calculate base MMR changes using ELO formula
        # Change = K * (Actual_Score - Expected_Score)
        # Actual_Score: 1 for winner, 0 for loser
        winner_change = avg_winner_k * (1 - expected_winner_probability)
        loser_change = avg_loser_k * (0 - expected_loser_probability)

        # Apply bonus/penalty multipliers based on MMR difference
        if mmr_difference > 100:  # Strong favorite won
            # Reduce gains for beating weaker opponents
            winner_change *= 0.7
            loser_change *= 0.8  # Reduce loss against stronger opponent
            performance_note = "Expected Victory"
        elif mmr_difference < -100:  # Major upset
            # Increase gains for beating stronger opponents
            winner_change *= 1.5
            loser_change *= 1.3  # Increase loss for losing to weaker opponent
            performance_note = "UPSET VICTORY!"
        else:
            performance_note = "Balanced Match"

        # Add placement match indicator
        if winner_placement_players or loser_placement_players:
            placement_count = len(winner_placement_players) + len(
                loser_placement_players)
            performance_note += f" (Placement: {placement_count} players)"

        # Apply skill-based modifiers
        if avg_winner_mmr < 1000 and mmr_difference > 50:
            # Lower skill player beating higher skill - extra reward
            winner_change *= 1.2
            performance_note += " (Skill Growth)"

        if avg_loser_mmr > 1400 and mmr_difference < -50:
            # High skill player losing to lower skill - extra penalty
            loser_change *= 1.2
            performance_note += " (Underperformance)"

        # Ensure minimum and maximum changes
        winner_change = max(15, min(
            100, round(winner_change)))  # Higher max for placement
        loser_change = min(-15, max(
            -100, round(loser_change)))  # Higher max for placement

        # Ensure minimum changes are applied
        if abs(winner_change) < 15:
            winner_change = 20  # Minimum win reward
        if abs(loser_change) < 15:
            loser_change = -20  # Minimum loss penalty

        # Mathematical balance: ensure loser_change is negative
        if loser_change > 0:
            loser_change = -loser_change

        logger.info(
            f"MMR CALCULATION: Final - Winner: +{winner_change}, Loser: {loser_change}, Performance: {performance_note}"
        )
        logger.info(
            f"MMR CALCULATION: K-factors - Winner avg: {avg_winner_k:.1f}, Loser avg: {avg_loser_k:.1f}"
        )
        logger.info(
            f"MMR CALCULATION: Placement players - Winners: {len(winner_placement_players)}, Losers: {len(loser_placement_players)}"
        )

        return {
            'winners': int(winner_change),
            'losers': int(loser_change),
            'performance_note': performance_note,
            'expected_probability': expected_winner_probability,
            'mmr_difference': mmr_difference,
            'winner_k_factor': avg_winner_k,
            'loser_k_factor': avg_loser_k,
            'winner_placement_players': winner_placement_players,
            'loser_placement_players': loser_placement_players
        }

    except Exception as e:
        logger.error(f"MMR CALCULATION ERROR: {e}")
        return {'winners': 25, 'losers': -25}  # Default MMR change


@bot.command(name='cancel')
async def cancel_match(ctx):
    """Cancel an active match"""
    # Check if command is used in correct channel
    if not is_queue_channel(ctx):
        await ctx.send(
            f"❌ Please use match commands in #{QUEUE_CHANNEL_NAME} channel!")
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
        await ctx.send("❌ You can only cancel matches you're participating in!"
                       )
        return

    # Remove match and return players to queue
    match_data = active_matches[match_id]
    all_players = match_data['team1'] + match_data['team2']

    # Add players back to queue
    for player in all_players:
        player_queue.append(player)

    # Delete from database
    c.execute("DELETE FROM matches WHERE match_id = ?", (match_id, ))
    conn.commit()

    # Remove from active matches
    del active_matches[match_id]

    embed = discord.Embed(
        title="❌ Match Cancelled",
        description=
        f"Match #{match_id} has been cancelled. Players returned to queue.",
        color=discord.Color.red())

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
    log_queue_event("RESET", "System",
                    f"Queue cleared ({queue_size} players removed)")

    return queue_size


@bot.tree.command(name='reset_queue',
                  description='Reset the queue system (Admin only)')
@app_commands.default_permissions(manage_channels=True)
async def reset_queue_command(interaction: discord.Interaction):
    """Reset the queue system - Admin only command"""

    # Check if we're in the queue channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ This command can only be used in #{QUEUE_CHANNEL_NAME}!",
            ephemeral=True)
        return

    # Reset the queue
    queue_size = reset_queue()

    # Create confirmation embed
    embed = discord.Embed(
        title="🔄 Queue Reset Complete",
        description=
        f"**Admin {interaction.user.display_name} has reset the queue system!**",
        color=discord.Color.blue())

    embed.add_field(name="Players Removed",
                    value=f"**{queue_size}** players",
                    inline=True)
    embed.add_field(name="Queue Status", value="**RESET**", inline=True)
    embed.add_field(name="Timeout", value="**CLEARED**", inline=True)

    embed.add_field(
        name="✅ Reset Operations",
        value=
        "• Player queue cleared\n• Queue activity reset\n• Draft sessions cleared\n• Timeout system reset",
        inline=False)

    embed.add_field(
        name="📊 Queue Status",
        value=
        "• Player count: 0/4\n• Queue timeout: Reset\n• HSM numbers: Available",
        inline=False)

    embed.set_footer(
        text="Players can join the queue immediately using the buttons below")

    # Update queue display
    await update_queue_display(interaction.channel)

    await interaction.response.send_message(embed=embed)

    log_admin_action("QUEUE_RESET", interaction.user.display_name,
                     f"Reset queue via command ({queue_size} players)")


# Admin cancel queue command
@bot.tree.command(name='cancel_queue',
                  description='Cancel the entire queue system (Admin only)')
@app_commands.default_permissions(manage_channels=True)
async def cancel_queue(interaction: discord.Interaction):
    """Cancel the entire queue system - removes all players from queue"""
    # Check if we're in the queue channel
    if not is_queue_channel(interaction.channel):
        await interaction.response.send_message(
            f"❌ This command can only be used in #{QUEUE_CHANNEL_NAME}!",
            ephemeral=True)
        return

    # Count players in queue
    queue_count = len(player_queue)

    if queue_count == 0:
        await interaction.response.send_message(
            "❌ The queue is already empty!", ephemeral=True)
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
        description=
        f"**Admin {interaction.user.display_name} has cancelled the entire queue system!**",
        color=discord.Color.red())
    embed.add_field(name="Players Removed",
                    value=f"**{queue_count}** players",
                    inline=True)
    embed.add_field(name="Queue Status", value="**CLEARED**", inline=True)
    embed.add_field(name="Action",
                    value="All players removed from queue",
                    inline=True)

    # List removed players
    if queue_players:
        player_list = []
        for player in queue_players:
            user = interaction.guild.get_member(int(player['id']))
            if user:
                player_list.append(
                    f"• {user.display_name} ({player['mmr']} MMR)")

        if player_list:
            embed.add_field(
                name="Removed Players",
                value="\n".join(player_list[:10]),  # Limit to 10 players
                inline=False)

    embed.add_field(
        name="Next Steps",
        value="Players can rejoin the queue using the buttons below",
        inline=False)
    embed.set_footer(text="Queue system reset by administrator")

    # Update queue display
    await update_queue_display(interaction.channel)

    await interaction.response.send_message(embed=embed)


# Enhanced Professional Setup Command - ADMIN ONLY
@bot.tree.command(
    name='setup',
    description='Create the professional HeatSeeker queue system (Admin only)')
@app_commands.default_permissions(administrator=True)
async def setup_channel(interaction: discord.Interaction):
    """Create the professional HeatSeeker queue system (Admin only)"""
    # Check if channel already exists
    existing_channel = discord.utils.get(interaction.guild.channels,
                                         name=QUEUE_CHANNEL_NAME)
    if existing_channel:
        embed = discord.Embed(
            title="✅ Queue Channel Already Exists",
            description=f"The #{QUEUE_CHANNEL_NAME} channel is already set up!",
            color=discord.Color.orange())
        embed.add_field(name="Channel",
                        value=existing_channel.mention,
                        inline=True)
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Create the professional queue system
    try:
        # Create queue channel
        queue_channel = await interaction.guild.create_text_channel(
            name=QUEUE_CHANNEL_NAME,
            topic=
            "🔥 HeatSeeker Professional 2v2 Queue System - Click buttons to join!",
            overwrites={
                interaction.guild.default_role:
                discord.PermissionOverwrite(
                    send_messages=False,  # Only bot messages and buttons
                    read_messages=True,
                    add_reactions=True),
                interaction.guild.me:
                discord.PermissionOverwrite(send_messages=True,
                                            read_messages=True,
                                            manage_messages=True,
                                            embed_links=True)
            })

        # Create results channel for completed matches (Admin only)
        results_channel = await interaction.guild.create_text_channel(
            name=RESULTS_CHANNEL_NAME,
            topic=
            "🏆 HeatSeeker Match Results - Admin can modify completed matches here",
            overwrites={
                interaction.guild.default_role:
                discord.PermissionOverwrite(send_messages=False,
                                            read_messages=True,
                                            add_reactions=True),
                interaction.guild.me:
                discord.PermissionOverwrite(send_messages=True,
                                            read_messages=True,
                                            manage_messages=True,
                                            embed_links=True)
            })

        # Get or create match category
        category = discord.utils.get(interaction.guild.categories,
                                     name=MATCH_CATEGORY_NAME)
        if not category:
            category = await interaction.guild.create_category(
                name=MATCH_CATEGORY_NAME,
                reason="HeatSeeker match channels category")

        # Send professional welcome message to queue channel
        embed = discord.Embed(
            title="🔥 HeatSeeker Bot - Professional 2v2 Queue System",
            description=
            "**Welcome to the ultimate competitive gaming experience!**\n\nUse the buttons below to interact with the queue system.",
            color=discord.Color.gold())

        embed.add_field(
            name="🎮 How It Works",
            value=
            "• Click **🎮 Join Queue** to enter the 2v2 queue\n• When 4 players join, a match will be created automatically\n• Each match gets dedicated text and voice channels\n• Teams are balanced based on MMR for fair gameplay",
            inline=False)

        embed.add_field(
            name="🏆 Features",
            value=
            "• **Dedicated match channels** for each game\n• **Team voice channels** (2 players max each)\n• **Automatic team balancing** based on skill\n• **Professional MMR tracking** system\n• **Auto-cleanup** after matches complete",
            inline=False)

        embed.set_footer(
            text="Ready to play? Click the buttons below to get started!")

        # Send with buttons
        view = QueueView()
        await queue_channel.send(embed=embed, view=view)

        # Send initial queue display
        await update_queue_display(queue_channel)

        # Confirmation to admin
        setup_embed = discord.Embed(
            title="🏆 HeatSeeker Setup Complete!",
            description=f"Professional queue system created successfully!",
            color=discord.Color.green())
        setup_embed.add_field(name="Queue Channel",
                              value=queue_channel.mention,
                              inline=True)
        setup_embed.add_field(name="Results Channel",
                              value=results_channel.mention,
                              inline=True)
        setup_embed.add_field(name="Match Category",
                              value=category.name,
                              inline=True)
        setup_embed.add_field(
            name="Features",
            value=
            "Button-based queue, voice channels, auto-balancing, admin results controls",
            inline=False)
        await interaction.response.send_message(embed=setup_embed,
                                                ephemeral=True)

    except discord.Forbidden:
        await interaction.response.send_message(
            "❌ I don't have permission to create channels!", ephemeral=True)
    except discord.HTTPException as e:
        await interaction.response.send_message(
            f"❌ Error creating channels: {e}", ephemeral=True)


# Private Chat Management Command - ADMIN ONLY
@bot.tree.command(
    name='private',
    description='Manage your private HSM chat (create/delete/info)')
@app_commands.default_permissions(administrator=True)
async def private_chat_command(interaction: discord.Interaction):
    """Manage your private HSM chat"""
    user_id = str(interaction.user.id)

    # Check if user has an active private chat
    c.execute(
        "SELECT hsm_number, channel_id, voice_channel_id FROM private_chats WHERE creator_id = ? AND is_active = 1",
        (user_id, ))
    chat_data = c.fetchone()

    embed = discord.Embed(
        title="🔒 HSM Private Chat System",
        description=
        "**Create your own private chat with a unique HSM number!**",
        color=discord.Color.purple())

    if chat_data:
        hsm_number, channel_id, voice_channel_id = chat_data
        channel = interaction.guild.get_channel(int(channel_id))
        voice_channel = interaction.guild.get_channel(int(voice_channel_id))

        embed.add_field(
            name="📋 Your Active Private Chat",
            value=
            f"**HSM Number:** HSM{hsm_number}\n**Text Channel:** {channel.mention if channel else 'Deleted'}\n**Voice Channel:** {voice_channel.mention if voice_channel else 'Deleted'}",
            inline=False)
        embed.add_field(
            name="🔧 Management Options",
            value=
            "• Use the **🗑️ Delete Private Chat** button to remove your chat\n• Manage permissions by right-clicking your channel",
            inline=False)
    else:
        embed.add_field(
            name="🆕 Create Your Private Chat",
            value=
            "• Get a unique HSM number (HSM1 to HSM9999)\n• Private text and voice channels\n• Full control over permissions\n• Perfect for private group discussions",
            inline=False)
        embed.add_field(
            name="🎮 How to Create",
            value="Use the **🔒 Create Private Chat** button below!",
            inline=False)

    embed.set_footer(
        text="HSM Private Chats - Your own private space in the server!")

    view = PrivateChatView()
    await interaction.response.send_message(embed=embed,
                                            view=view,
                                            ephemeral=True)


# Set Queue Players Command - ADMIN ONLY
@bot.tree.command(
    name='queueplayer',
    description=
    'Set the number of players for the queue (2=1v1, 4=2v2, 6=3v3, etc.)')
@app_commands.default_permissions(administrator=True)
async def set_queue_players(interaction: discord.Interaction, players: int):
    """Set the number of players for the queue system"""

    # Validate player count
    if players < 2 or players > 20:
        await interaction.response.send_message(
            "❌ Number of players must be between 2 and 20!", ephemeral=True)
        return

    if players % 2 != 0:
        await interaction.response.send_message(
            "❌ Number of players must be even (2, 4, 6, 8, etc.)!",
            ephemeral=True)
        return

    # Update global queue configuration
    global QUEUE_SIZE, TEAM_SIZE
    QUEUE_SIZE = players
    TEAM_SIZE = players // 2

    # Clear current queue if any
    global player_queue
    if player_queue:
        player_queue.clear()

    # Create configuration embed
    embed = discord.Embed(
        title="⚙️ Queue Configuration Updated!",
        description=f"Queue system has been reconfigured successfully",
        color=discord.Color.green())

    embed.add_field(
        name="🎯 New Configuration",
        value=
        f"**Total Players:** {QUEUE_SIZE}\n**Team Size:** {TEAM_SIZE}v{TEAM_SIZE}\n**Teams:** 2 teams",
        inline=True)

    embed.add_field(name="🌍 Server Region",
                    value="**MENA** (Middle East & North Africa)",
                    inline=True)

    embed.add_field(name="📝 Status",
                    value="✅ **Active** - Players can now join the queue",
                    inline=True)

    embed.add_field(
        name="🔄 Queue Reset",
        value=
        "Current queue has been cleared\nPlayers need to rejoin with new configuration",
        inline=False)

    embed.set_footer(
        text=f"Configuration changed by {interaction.user.display_name}")

    await interaction.response.send_message(embed=embed)

    # Update queue display if queue channel exists
    queue_channel = discord.utils.get(interaction.guild.channels,
                                      name=QUEUE_CHANNEL_NAME)
    if queue_channel:
        await update_queue_display(queue_channel)

    # Log the change
    logger.info(
        f"Queue configuration changed to {TEAM_SIZE}v{TEAM_SIZE} ({QUEUE_SIZE} players) by {interaction.user.display_name}"
    )


# Create Custom Match Command - ADMIN ONLY
@bot.tree.command(
    name='create_match',
    description='Create a custom match with automatic HSM number')
@app_commands.default_permissions(administrator=True)
async def create_match_command(interaction: discord.Interaction,
                               match_name: str):
    """Create a custom match with automatic sequential HSM number"""

    # Generate next HSM number automatically
    hsm_number = generate_match_hsm_number()
    if not hsm_number:
        await interaction.response.send_message(
            "❌ Unable to generate HSM number!", ephemeral=True)
        return

    # Create embed for match creation
    embed = discord.Embed(
        title="🎮 Custom Match Created!",
        description=f"**Match HSM{hsm_number}** is ready for players!",
        color=discord.Color.green())

    embed.add_field(name="🏷️ Match Name",
                    value=f"**HSM{hsm_number}**",
                    inline=True)

    embed.add_field(name="🌍 Server Region",
                    value="**MENA** (Middle East & North Africa)",
                    inline=True)

    embed.add_field(name="📝 Status",
                    value="**Waiting for players**",
                    inline=True)

    embed.add_field(
        name="🎯 How Players Join",
        value=
        f"1. Players type: **HSM{hsm_number}**\n2. Join the match channels\n3. Start playing!",
        inline=False)

    # Get or create match category
    category = discord.utils.get(interaction.guild.categories,
                                 name=MATCH_CATEGORY_NAME)
    if not category:
        category = await interaction.guild.create_category(
            name=MATCH_CATEGORY_NAME, reason="HeatSeeker match category")

    # Create the match channels
    try:
        # Delete existing channels with same name to prevent duplicates
        existing_channel = discord.utils.get(interaction.guild.channels,
                                             name=f"hsm{hsm_number}")
        if existing_channel:
            await existing_channel.delete(reason="Recreating match channel")

        # Create text channel
        match_channel = await interaction.guild.create_text_channel(
            name=f"hsm{hsm_number}",
            category=category,
            topic=
            f"HeatSeeker Match HSM{hsm_number} - Custom Match - Server: MENA")

        # Create voice channel
        voice_channel = await interaction.guild.create_voice_channel(
            name=f"🎮 HSM{hsm_number} - Game Room",
            category=category,
            user_limit=4)

        embed.add_field(
            name="📍 Match Channels",
            value=
            f"**Text:** {match_channel.mention}\n**Voice:** {voice_channel.mention}",
            inline=False)

        embed.set_footer(text="Match channels created successfully!")

        await interaction.response.send_message(embed=embed)

        # Send welcome message to match channel
        welcome_embed = discord.Embed(
            title=f"🎮 Welcome to Match HSM{hsm_number}!",
            description=
            "**Custom match created by admin**\n\nPlayers can now join and start playing!",
            color=discord.Color.purple())

        welcome_embed.add_field(name="🌍 Server Region",
                                value="**MENA** (Middle East & North Africa)",
                                inline=True)

        welcome_embed.add_field(name="🎯 Match Name",
                                value=f"**HSM{hsm_number}**",
                                inline=True)

        welcome_embed.add_field(
            name="📝 Instructions",
            value="1. Join the voice channel\n2. Start your game\n3. Have fun!",
            inline=False)

        await match_channel.send(embed=welcome_embed)

    except Exception as e:
        await interaction.response.send_message(
            f"❌ Error creating match channels: {e}", ephemeral=True)


# Auto-Leaderboard System
@tasks.loop(minutes=10)  # Updates every 10 minutes
async def update_leaderboard():
    """Automatically update leaderboard in designated channel"""
    global leaderboard_channel

    if not leaderboard_channel:
        return

    try:
        # Get all ranked players (players who have completed placement matches)
        c.execute(
            "SELECT id, username, mmr, wins, losses FROM players WHERE is_placed = 1 ORDER BY mmr DESC LIMIT 20"
        )
        players = c.fetchall()

        if not players:
            embed = discord.Embed(
                title="🏆 لوحة المتصدرين - HeatSeeker",
                description=
                "**لا يوجد لاعبين نشطين حتى الآن!**\n\nانضم إلى الطابور وابدأ تسلق الرتب!",
                color=discord.Color.gold())
            embed.add_field(name="🌍 منطقة الخادم",
                            value="**MENA** (الشرق الأوسط وشمال أفريقيا)",
                            inline=True)
            embed.add_field(
                name="🎯 الطابور الحالي",
                value=f"**{TEAM_SIZE}v{TEAM_SIZE}** ({QUEUE_SIZE} لاعبين)",
                inline=True)
            embed.set_footer(
                text=
                f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            embed = discord.Embed(title="🏆 لوحة المتصدرين",
                                  description="**تحديث تلقائي كل 30 دقيقة**",
                                  color=0x00ffcc)

            leaderboard_text = ""
            for i, (player_id, username, mmr, wins,
                    losses) in enumerate(players[:8],
                                         1):  # Reduced to 8 players
                # Get rank info for each player
                rank_info = get_rank_from_mmr(mmr)
                rank_emoji = rank_info['emoji']

                if i == 1:
                    position_emoji = "🥇"
                elif i == 2:
                    position_emoji = "🥈"
                elif i == 3:
                    position_emoji = "🥉"
                else:
                    position_emoji = f"**{i}.**"

                total_games = wins + losses
                win_rate = (wins / total_games * 100) if total_games > 0 else 0

                # Get the actual Discord member to show display name
                try:
                    member = leaderboard_channel.guild.get_member(
                        int(player_id))
                    display_name = member.display_name if member else username
                    # Limit display name length
                    if len(display_name) > 15:
                        display_name = display_name[:12] + "..."
                except:
                    display_name = username
                    if len(display_name) > 15:
                        display_name = display_name[:12] + "..."

                # Shorter format to fit Discord limits
                leaderboard_text += f"{position_emoji} {rank_emoji} **{display_name}**\n"
                leaderboard_text += f"`{mmr} MMR` • `{wins}W/{losses}L | Games: {total_games}` • `{win_rate:.0f}%`\n\n"

            embed.add_field(name="🎯 أفضل لاعبين",
                            value=leaderboard_text,
                            inline=False)

            embed.set_thumbnail(
                url="https://cdn.discordapp.com/emojis/1234567890123456789.png"
            )  # Trophy icon

            embed.add_field(name="🌍 الخادم", value="**MENA**", inline=True)

            embed.add_field(
                name="🎮 الطابور الحالي",
                value=f"**{TEAM_SIZE}v{TEAM_SIZE}** ({QUEUE_SIZE} لاعبين)",
                inline=True)

            embed.set_footer(
                text=
                f"آخر تحديث: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | يتم التحديث كل 30 دقيقة"
            )

        # Clear previous messages and send new leaderboard
        async for message in leaderboard_channel.history(limit=100):
            if message.author == bot.user:
                await message.delete()

        await leaderboard_channel.send(embed=embed)
        logger.info("Leaderboard updated successfully")

    except Exception as e:
        logger.error(f"Error updating leaderboard: {e}")


# Set Leaderboard Channel Command - ADMIN ONLY
@bot.tree.command(
    name='set_leaderboard',
    description='Set the current channel as auto-updating leaderboard')
@app_commands.default_permissions(administrator=True)
async def set_leaderboard_channel(interaction: discord.Interaction):
    """Set the current channel as leaderboard channel"""

    global leaderboard_channel
    leaderboard_channel = interaction.channel

    # Start the leaderboard update task
    if not update_leaderboard.is_running():
        update_leaderboard.start()

    embed = discord.Embed(
        title="✅ Leaderboard Channel Set!",
        description=
        "This channel will now display the auto-updating leaderboard",
        color=discord.Color.green())

    embed.add_field(name="📊 Update Frequency",
                    value="**Every 10 minutes** automatically",
                    inline=True)

    embed.add_field(name="🌍 Server Region",
                    value="**MENA** (Middle East & North Africa)",
                    inline=True)

    embed.add_field(
        name="🎯 Current Queue",
        value=f"**{TEAM_SIZE}v{TEAM_SIZE}** ({QUEUE_SIZE} players)",
        inline=True)

    embed.add_field(
        name="📝 Features",
        value=
        "• Top 10 players by MMR\n• Win/Loss statistics\n• Auto-refresh every 10 minutes\n• Shows current queue configuration",
        inline=False)

    embed.set_footer(
        text="First leaderboard update will appear in a few seconds")

    await interaction.response.send_message(embed=embed)

    # Trigger immediate update
    await update_leaderboard()

    logger.info(
        f"Leaderboard channel set to {interaction.channel.name} by {interaction.user.display_name}"
    )


# Admin Season Reset Command
@bot.tree.command(name='reset_season',
                  description='إعادة تعيين شاملة للموسم الجديد (Admin only)')
@app_commands.default_permissions(administrator=True)
async def reset_season(interaction: discord.Interaction):
    """إعادة تعيين شاملة للموسم الجديد - Admin only"""

    await interaction.response.defer()

    try:
        # الحصول على الإحصائيات قبل الإعادة
        c.execute("SELECT COUNT(*) FROM players")
        total_players = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM matches")
        total_matches = c.fetchone()[0]

        c.execute(
            "SELECT username, mmr, wins, losses FROM players ORDER BY mmr DESC LIMIT 3"
        )
        top_players = c.fetchall()

        # إنشاء embed تأكيد
        embed = discord.Embed(
            title="⚠️ تأكيد إعادة تعيين الموسم",
            description=
            "**هذا الإجراء سيحذف جميع الإحصائيات ويبدأ موسم جديد!**",
            color=discord.Color.red())

        embed.add_field(
            name="📊 الإحصائيات الحالية",
            value=
            f"**اللاعبين:** {total_players}\n**المباريات:** {total_matches}",
            inline=True)

        if top_players:
            top_3_text = ""
            for i, (username, mmr, wins, losses) in enumerate(top_players, 1):
                top_3_text += f"{i}. {username} ({mmr} MMR)\n"

            embed.add_field(name="🏆 أفضل 3 لاعبين",
                            value=top_3_text,
                            inline=True)

        embed.add_field(
            name="🔄 ما سيحدث",
            value=
            "• جميع اللاعبين → نقطة بداية مخصصة\n• جميع الانتصارات/الهزائم → 0\n• حذف سجل المباريات\n• تنظيف الدردشات الخاصة\n• إعادة تعيين البليسمنت ماتشز",
            inline=False)

        embed.add_field(
            name="⚠️ تحذير مهم",
            value=
            "**لا يمكن التراجع عن هذا الإجراء!**\nسيتم فقدان جميع الإحصائيات نهائياً",
            inline=False)

        # Modal لتحديد نقطة البداية
        class StartingMMRModal(discord.ui.Modal):

            def __init__(self):
                super().__init__(title="تحديد نقطة البداية للموسم الجديد")

                self.starting_mmr = discord.ui.TextInput(
                    label="نقطة البداية (MMR)",
                    placeholder="أدخل النقاط الابتدائية (مثال: 1200)",
                    default="1000",
                    min_length=3,
                    max_length=4,
                    required=True)
                self.add_item(self.starting_mmr)

            async def on_submit(self, modal_interaction: discord.Interaction):
                try:
                    starting_mmr = int(self.starting_mmr.value)

                    # التحقق من النطاق المسموح
                    if starting_mmr < 500 or starting_mmr > 3000:
                        await modal_interaction.response.send_message(
                            "❌ نقطة البداية يجب أن تكون بين 500 و 3000!",
                            ephemeral=True)
                        return

                    await modal_interaction.response.defer()

                    try:
                        # المرحلة 1: إعادة تعيين قاعدة البيانات
                        await modal_interaction.edit_original_response(
                            embed=discord.Embed(
                                title="🔄 جاري إعادة التعيين...",
                                description=
                                "**المرحلة 1/5:** إعادة تعيين قاعدة البيانات...",
                                color=discord.Color.orange()))

                        # إعادة تعيين اللاعبين مع النقطة المحددة
                        c.execute(
                            "UPDATE players SET mmr = ?, wins = 0, losses = 0, placement_matches_remaining = 5, is_placed = 0",
                            (starting_mmr, ))

                        # حذف المباريات
                        c.execute("DELETE FROM matches")
                        c.execute(
                            "DELETE FROM sqlite_sequence WHERE name = 'matches'"
                        )

                        # تنظيف الدردشات
                        c.execute("UPDATE private_chats SET is_active = 0")
                        c.execute("UPDATE private_matches SET is_active = 0")

                        conn.commit()

                        # المرحلة 2: إزالة جميع رتب الرانكات من جميع الأعضاء
                        await modal_interaction.edit_original_response(
                            embed=discord.Embed(
                                title="🔄 جاري إعادة التعيين...",
                                description=
                                "**المرحلة 2/5:** إزالة رتب الرانكات من جميع الأعضاء...",
                                color=discord.Color.orange()))

                        removed_roles_count = 0
                        for member in interaction.guild.members:
                            if member.bot:
                                continue

                            rank_roles_to_remove = []
                            for rank_data in RANK_ROLES.values():
                                role = discord.utils.get(
                                    interaction.guild.roles,
                                    name=rank_data['role_name'])
                                if role and role in member.roles:
                                    rank_roles_to_remove.append(role)

                            if rank_roles_to_remove:
                                try:
                                    await member.remove_roles(
                                        *rank_roles_to_remove,
                                        reason=
                                        "Season reset - removing all rank roles"
                                    )
                                    removed_roles_count += len(
                                        rank_roles_to_remove)
                                    logger.info(
                                        f"SEASON RESET: Removed {len(rank_roles_to_remove)} rank roles from {member.display_name}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"SEASON RESET: Error removing roles from {member.display_name}: {e}"
                                    )

                        # المرحلة 3: إضافة رتبة UNRANKED لجميع الأعضاء
                        await modal_interaction.edit_original_response(
                            embed=discord.Embed(
                                title="🔄 جاري إعادة التعيين...",
                                description=
                                "**المرحلة 3/5:** إضافة رتبة UNRANKED لجميع الأعضاء...",
                                color=discord.Color.orange()))

                        unranked_role_name = UNRANK_RANK['UNRANKED'][
                            'role_name']
                        unranked_role = discord.utils.get(
                            interaction.guild.roles, name=unranked_role_name)

                        if not unranked_role:
                            try:
                                unranked_role = await interaction.guild.create_role(
                                    name=unranked_role_name,
                                    color=discord.Color(
                                        UNRANK_RANK['UNRANKED']['color']),
                                    reason=
                                    "Season reset - creating UNRANKED role")
                                logger.info(
                                    f"SEASON RESET: Created UNRANKED role: {unranked_role_name}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"SEASON RESET: Error creating UNRANKED role: {e}"
                                )

                        unranked_members_count = 0

                        if unranked_role:
                            for member in interaction.guild.members:
                                if member.bot:
                                    continue

                                if unranked_role not in member.roles:
                                    try:
                                        await member.add_roles(
                                            unranked_role,
                                            reason=
                                            "Season reset - adding UNRANKED role"
                                        )
                                        unranked_members_count += 1
                                        logger.info(
                                            f"SEASON RESET: Added UNRANKED role to {member.display_name}"
                                        )
                                    except Exception as e:
                                        logger.error(
                                            f"SEASON RESET: Error adding UNRANKED role to {member.display_name}: {e}"
                                        )
                        else:
                            logger.error(
                                "SEASON RESET: Failed to find or create UNRANKED role"
                            )

                        # المرحلة 4: تنظيف الذاكرة
                        await modal_interaction.edit_original_response(
                            embed=discord.Embed(
                                title="🔄 جاري إعادة التعيين...",
                                description=
                                "**المرحلة 4/5:** تنظيف الطابور والمباريات النشطة...",
                                color=discord.Color.orange()))

                        global active_matches, player_queue, match_id_counter
                        active_matches.clear()
                        player_queue.clear()
                        match_id_counter = 1

                        # المرحلة 5: الانتهاء
                        await modal_interaction.edit_original_response(
                            embed=discord.Embed(
                                title="🔄 جاري إعادة التعيين...",
                                description=
                                "**المرحلة 5/5:** الانتهاء من إعادة التعيين...",
                                color=discord.Color.orange()))

                        rank_info = get_rank_from_mmr(starting_mmr, True)

                        success_embed = discord.Embed(
                            title="🎉 تم إعادة تعيين الموسم بنجاح!",
                            description="**الموسم الجديد جاهز للبدء!**",
                            color=discord.Color.green())

                        success_embed.add_field(
                            name="✅ تم الانتهاء من",
                            value=
                            f"• إعادة تعيين {total_players} لاعب إلى **{starting_mmr} MMR**\n• حذف {total_matches} مباراة\n• تنظيف جميع الدردشات الخاصة\n• إزالة {removed_roles_count} رتبة رانك من جميع الأعضاء\n• إضافة رتبة Unranked لـ {unranked_members_count} عضو\n• مسح الطابور النشط\n• إعادة تعيين البليسمنت ماتشز",
                            inline=False)

                        success_embed.add_field(
                            name="🚀 الموسم الجديد",
                            value=
                            f"• جميع اللاعبين يبدؤون بـ **{starting_mmr} MMR**\n• الرتبة المتوقعة: {rank_info['emoji']} **{rank_info['name']}**\n• سجل نظيف للمباريات\n• منافسة عادلة من البداية\n• جميع اللاعبين يحتاجون 5 مباريات تأهيل",
                            inline=False)

                        success_embed.add_field(
                            name="🎯 نقطة البداية المخصصة",
                            value=
                            f"**{starting_mmr} MMR** - تم اختيارها بواسطة الأدمن",
                            inline=False)

                        success_embed.set_footer(
                            text=
                            f"تم التنفيذ بواسطة {interaction.user.display_name}"
                        )

                        await modal_interaction.edit_original_response(
                            embed=success_embed, view=None)

                        logger.info(
                            f"SEASON RESET: Complete season reset by {interaction.user.display_name} with starting MMR: {starting_mmr}"
                        )
                        logger.info(
                            f"SEASON RESET: {total_players} players reset to {starting_mmr} MMR, {total_matches} matches deleted"
                        )

                        queue_channel = discord.utils.get(
                            interaction.guild.channels,
                            name=QUEUE_CHANNEL_NAME)
                        if queue_channel:
                            await update_queue_display(queue_channel)

                    except Exception as e:
                        error_embed = discord.Embed(
                            title="❌ خطأ في إعادة التعيين",
                            description=
                            f"حدث خطأ أثناء إعادة تعيين الموسم: {e}",
                            color=discord.Color.red())

                        await modal_interaction.edit_original_response(
                            embed=error_embed, view=None)

                except ValueError:
                    await modal_interaction.response.send_message(
                        "❌ يرجى إدخال رقم صحيح للنقاط!", ephemeral=True)
                except Exception as e:
                    await modal_interaction.response.send_message(
                        f"❌ خطأ: {e}", ephemeral=True)

        # إنشاء أزرار التأكيد
        class SeasonResetView(discord.ui.View):

            def __init__(self):
                super().__init__(timeout=60)

            @discord.ui.button(label="⚙️ تحديد نقطة البداية",
                               style=discord.ButtonStyle.primary)
            async def custom_reset(self,
                                   button_interaction: discord.Interaction,
                                   button: discord.ui.Button):
                if button_interaction.user != interaction.user:
                    await button_interaction.response.send_message(
                        "❌ فقط من طلب الأمر يمكنه التأكيد!", ephemeral=True)
                    return

                # إظهار modal لتحديد النقطة
                modal = StartingMMRModal()
                await button_interaction.response.send_modal(modal)

            @discord.ui.button(label="✅ إعادة تعيين (1000 نقطة)",
                               style=discord.ButtonStyle.danger)
            async def default_reset(self,
                                    button_interaction: discord.Interaction,
                                    button: discord.ui.Button):
                if button_interaction.user != interaction.user:
                    await button_interaction.response.send_message(
                        "❌ فقط من طلب الأمر يمكنه التأكيد!", ephemeral=True)
                    return

                await button_interaction.response.defer()

                # تنفيذ إعادة التعيين بالنقطة الافتراضية
                try:
                    # المرحلة 1: إزالة جميع رتب الرانكات من جميع الأعضاء
                    await button_interaction.edit_original_response(
                        embed=discord.Embed(
                            title="🔄 جاري إعادة التعيين...",
                            description=
                            "**المرحلة 1/5:** إزالة رتب الرانكات من جميع الأعضاء...",
                            color=discord.Color.orange()))

                    removed_roles_count = 0
                    for member in interaction.guild.members:
                        if member.bot:
                            continue

                        # العثور على رتب الرانكات التي يملكها العضو
                        rank_roles_to_remove = []
                        for rank_data in RANK_ROLES.values():
                            role = discord.utils.get(
                                interaction.guild.roles,
                                name=rank_data['role_name'])
                            if role and role in member.roles:
                                rank_roles_to_remove.append(role)

                        # إزالة رتب الرانكات
                        if rank_roles_to_remove:
                            try:
                                await member.remove_roles(
                                    *rank_roles_to_remove,
                                    reason=
                                    "Season reset - removing all rank roles")
                                removed_roles_count += len(
                                    rank_roles_to_remove)
                                logger.info(
                                    f"SEASON RESET: Removed {len(rank_roles_to_remove)} rank roles from {member.display_name}"
                                )
                            except Exception as e:
                                logger.error(
                                    f"SEASON RESET: Error removing roles from {member.display_name}: {e}"
                                )

                    # المرحلة 2: إضافة رتبة UNRANKED لجميع الأعضاء
                    await button_interaction.edit_original_response(
                        embed=discord.Embed(
                            title="🔄 جاري إعادة التعيين...",
                            description=
                            "**المرحلة 2/5:** إضافة رتبة UNRANKED لجميع الأعضاء...",
                            color=discord.Color.orange()))

                    # البحث عن رتبة UNRANKED الموجودة أو إنشاؤها
                    unranked_role_name = UNRANK_RANK['UNRANKED']['role_name']
                    unranked_role = discord.utils.get(interaction.guild.roles,
                                                      name=unranked_role_name)

                    # إنشاء رتبة UNRANKED إذا لم تكن موجودة
                    if not unranked_role:
                        try:
                            unranked_role = await interaction.guild.create_role(
                                name=unranked_role_name,
                                color=discord.Color(
                                    UNRANK_RANK['UNRANKED']['color']),
                                reason="Season reset - creating UNRANKED role")
                            logger.info(
                                f"SEASON RESET: Created UNRANKED role: {unranked_role_name}"
                            )
                        except Exception as e:
                            logger.error(
                                f"SEASON RESET: Error creating UNRANKED role: {e}"
                            )

                    unranked_members_count = 0

                    if unranked_role:
                        for member in interaction.guild.members:
                            if member.bot:
                                continue

                            # إضافة رتبة UNRANKED إذا لم يكن يملكها
                            if unranked_role not in member.roles:
                                try:
                                    await member.add_roles(
                                        unranked_role,
                                        reason=
                                        "Season reset - adding UNRANKED role")
                                    unranked_members_count += 1
                                    logger.info(
                                        f"SEASON RESET: Added UNRANKED role to {member.display_name}"
                                    )
                                except Exception as e:
                                    logger.error(
                                        f"SEASON RESET: Error adding UNRANKED role to {member.display_name}: {e}"
                                    )
                    else:
                        logger.error(
                            "SEASON RESET: Failed to find or create UNRANKED role"
                        )

                    # المرحلة 3: إعادة تعيين قاعدة البيانات
                    await button_interaction.edit_original_response(
                        embed=discord.Embed(
                            title="🔄 جاري إعادة التعيين...",
                            description=
                            "**المرحلة 3/5:** إعادة تعيين قاعدة البيانات...",
                            color=discord.Color.orange()))

                    # إعادة تعيين اللاعبين
                    c.execute(
                        "UPDATE players SET mmr = 1000, wins = 0, losses = 0, placement_matches_remaining = 5, is_placed = 0"
                    )

                    # حذف المباريات
                    c.execute("DELETE FROM matches")
                    c.execute(
                        "DELETE FROM sqlite_sequence WHERE name = 'matches'")

                    # تنظيف الدردشات
                    c.execute("UPDATE private_chats SET is_active = 0")
                    c.execute("UPDATE private_matches SET is_active = 0")

                    conn.commit()

                    # المرحلة 4: تنظيف الذاكرة
                    await button_interaction.edit_original_response(
                        embed=discord.Embed(
                            title="🔄 جاري إعادة التعيين...",
                            description=
                            "**المرحلة 4/5:** تنظيف الطابور والمباريات النشطة...",
                            color=discord.Color.orange()))

                    # تنظيف المباريات النشطة في الذاكرة
                    global active_matches, player_queue, match_id_counter
                    active_matches.clear()
                    player_queue.clear()
                    match_id_counter = 1

                    # المرحلة 5: الانتهاء
                    await button_interaction.edit_original_response(
                        embed=discord.Embed(
                            title="🔄 جاري إعادة التعيين...",
                            description=
                            "**المرحلة 5/5:** الانتهاء من إعادة التعيين...",
                            color=discord.Color.orange()))

                    # إنشاء embed النجاح
                    success_embed = discord.Embed(
                        title="🎉 تم إعادة تعيين الموسم بنجاح!",
                        description="**الموسم الجديد جاهز للبدء!**",
                        color=discord.Color.green())

                    success_embed.add_field(
                        name="✅ تم الانتهاء من",
                        value=
                        f"• إزالة {removed_roles_count} رتبة رانك من جميع الأعضاء\n• إضافة رتبة Unranked لـ {unranked_members_count} عضو\n• إعادة تعيين {total_players} لاعب إلى **1000 MMR** (افتراضي)\n• حذف {total_matches} مباراة\n• تنظيف جميع الدردشات الخاصة\n• مسح الطابور النشط\n• إعادة تعيين البليسمنت ماتشز",
                        inline=False)

                    success_embed.add_field(
                        name="🚀 الموسم الجديد",
                        value=
                        "• جميع اللاعبين متساوون (1000 MMR)\n• سجل نظيف للمباريات\n• منافسة عادلة من البداية\n• جميع اللاعبين يحتاجون 5 مباريات تأهيل",
                        inline=False)

                    success_embed.set_footer(
                        text=
                        f"تم التنفيذ بواسطة {interaction.user.display_name}")

                    await button_interaction.edit_original_response(
                        embed=success_embed, view=None)

                    # تسجيل في السجلات
                    logger.info(
                        f"SEASON RESET: Complete season reset by {interaction.user.display_name}"
                    )
                    logger.info(
                        f"SEASON RESET: {total_players} players reset, {total_matches} matches deleted"
                    )

                    # تحديث عرض الطابور إذا كان موجود
                    queue_channel = discord.utils.get(
                        interaction.guild.channels, name=QUEUE_CHANNEL_NAME)
                    if queue_channel:
                        await update_queue_display(queue_channel)

                except Exception as e:
                    error_embed = discord.Embed(
                        title="❌ خطأ في إعادة التعيين",
                        description=f"حدث خطأ أثناء إعادة تعيين الموسم: {e}",
                        color=discord.Color.red())

                    await button_interaction.edit_original_response(
                        embed=error_embed, view=None)

            @discord.ui.button(label="❌ إلغاء",
                               style=discord.ButtonStyle.secondary)
            async def cancel_reset(self,
                                   button_interaction: discord.Interaction,
                                   button: discord.ui.Button):
                if button_interaction.user != interaction.user:
                    await button_interaction.response.send_message(
                        "❌ فقط من طلب الأمر يمكنه الإلغاء!", ephemeral=True)
                    return

                cancel_embed = discord.Embed(
                    title="✅ تم إلغاء إعادة التعيين",
                    description="تم الاحتفاظ بجميع الإحصائيات والمباريات",
                    color=discord.Color.blue())

                await button_interaction.response.edit_message(
                    embed=cancel_embed, view=None)

        view = SeasonResetView()
        await interaction.followup.send(embed=embed, view=view)

    except Exception as e:
        error_embed = discord.Embed(
            title="❌ خطأ",
            description=f"حدث خطأ أثناء تحضير إعادة التعيين: {e}",
            color=discord.Color.red())

        await interaction.followup.send(embed=error_embed)


@bot.tree.command(
    name="set_mmr",
    description="Set the MMR for all members (Admin only)"
)
@app_commands.default_permissions(administrator=True)
async def set_mmr_command(interaction: discord.Interaction):
    """Admin command to set MMR for all members via modal input"""
    class SetMMRView(discord.ui.View):
        @discord.ui.button(label="Set MMR", style=discord.ButtonStyle.primary)
        async def set_mmr_button(self, button_interaction: discord.Interaction, button: discord.ui.Button):
            if button_interaction.user != interaction.user:
                await button_interaction.response.send_message(
                    "❌ Only the admin who used the command can set the MMR.", ephemeral=True)
                return

            class MMRModal(discord.ui.Modal, title="Set MMR for All Members"):
                mmr_value = discord.ui.TextInput(
                    label="MMR Value (0-9999)",
                    placeholder="Enter the MMR to set for all members",
                    min_length=1,
                    max_length=4,
                    required=True
                )

                async def on_submit(self, modal_interaction: discord.Interaction):
                    try:
                        value = int(self.mmr_value.value)
                        if value < 0 or value > 9999:
                            await modal_interaction.response.send_message(
                                "❌ Please enter a number between 0 and 9999.", ephemeral=True)
                            return

                        # Update all players in the database
                        c.execute("UPDATE players SET mmr = ?", (value,))
                        conn.commit()

                        await modal_interaction.response.send_message(
                            f"✅ Set MMR for all members to **{value}**.", ephemeral=True)
                    except Exception as e:
                        await modal_interaction.response.send_message(
                            f"❌ Error: {e}", ephemeral=True)

            await button_interaction.response.send_modal(MMRModal())

    embed = discord.Embed(
        title="Set MMR for All Members",
        description="Choose the MMR you want to set for all members (0-9999).",
        color=discord.Color.orange()
    )
    await interaction.response.send_message(embed=embed, view=SetMMRView(), ephemeral=True)

# Help command - ADMIN ONLY
@bot.tree.command(name='help',
                  description='Show all available commands (Admin only)')
@app_commands.default_permissions(administrator=True)
async def help_command(interaction: discord.Interaction):
    """Display available commands"""
    embed = discord.Embed(title="🤖 HeatSeeker Bot Commands",
                          description="Here are all the available commands:",
                          color=discord.Color.purple())

    embed.add_field(
        name="👥 Public Commands (Everyone)",
        value="`/rank` - Display your current MMR and statistics\n" +
        f"`/queue` - Join the queue (use in #{QUEUE_CHANNEL_NAME})\n" +
        f"`/leave` - Leave the queue (use in #{QUEUE_CHANNEL_NAME})\n" +
        "`/rank_info` - Show rank system information",
        inline=False)

    embed.add_field(
        name="🏆 Match System (Public)",
        value="Match results are reported using buttons in match channels",
        inline=False)

    embed.add_field(
        name="🔒 Private Chat System",
        value="`/private` - Create your own private HSM chat (HSM1-HSM9999)\n"
        + "Get your own private text and voice channels!",
        inline=False)

    embed.add_field(
        name="🎮 Match Creation",
        value=
        "`/create_match` - Create custom match with HSM name (HSM1, HSM2, etc.)\n"
        +
        "Admin only - Create matches for players to join by typing the match name",
        inline=False)

    embed.add_field(
        name="🎖️ Rank System",
        value="`/rank` - View your current rank and stats\n" +
        "`/rank_info` - Show all available ranks and MMR requirements\n" +
        "Ranks are automatically assigned based on your MMR!",
        inline=False)

    embed.add_field(
        name="⚙️ Admin Commands (Administrator Only)",
        value="`/setup` - Create the professional queue system\n" +
        "`/queueplayer` - Set queue size (2=1v1, 4=2v2, 6=3v3)\n" +
        "`/create_match` - Create custom match with HSM name\n" +
        "`/set_leaderboard` - Set auto-updating leaderboard channel\n" +
        "`/cancel_queue` - Cancel entire queue system\n" +
        "`/reset_queue` - Reset queue system\n" +
        "`/admin_match` - Admin control panel for match management\n" +
        "`/game_log` - View complete game history and modify all data\n" +
        "`/sync_ranks` - Sync all player ranks based on MMR\n" +
        "`/create_ranks` - Create all rank roles in server\n" +
        "`/status` - Show current queue status\n" +
        "`/private` - Manage private HSM chats\n" +
        "`/help` - Show this help message",
        inline=False)

    embed.set_footer(
        text="Queue commands only work in the dedicated 2v2 channel!")
    await interaction.response.send_message(embed=embed, ephemeral=True)


# Admin Match Control Panel Command
@bot.tree.command(
    name='admin_match',
    description='Admin control panel for active matches (Admin only)')
@app_commands.default_permissions(administrator=True)
async def admin_match_control(interaction: discord.Interaction):
    """Admin control panel for managing active matches"""
    print(
        f"[DEBUG] Admin match command called by {interaction.user.display_name}"
    )
    print(f"[DEBUG] Active matches: {len(active_matches)}")

    if not active_matches:
        embed = discord.Embed(
            title="📋 Admin Match Control Panel",
            description=
            "**No active matches found!**\n\nWhen matches are active, you can use this panel to:\n• Set match winners\n• Mark matches as ties\n• Cancel problematic matches\n• Override match results",
            color=discord.Color.orange())
        embed.add_field(
            name="📝 How to Create Matches",
            value="Players need to use `/queue` to create matches first",
            inline=False)
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
            options.append(
                discord.SelectOption(
                    label=f"Match #{match_id}",
                    description=description[:100],  # Discord limit
                    value=str(match_id)))
            print(f"[DEBUG] Added option for match {match_id}: {description}")
    except Exception as e:
        print(f"[DEBUG] Error creating options: {e}")
        await interaction.response.send_message(
            f"❌ Error creating admin panel: {e}", ephemeral=True)
        return

    # Create embed
    embed = discord.Embed(
        title="🔧 Admin Match Control Panel",
        description=
        f"**{len(active_matches)} active match(es) found**\n\nSelect a match below to manage:",
        color=discord.Color.gold())

    # Add match details
    for match_id, match_data in list(
            active_matches.items())[:5]:  # Show first 5 matches
        team1_names = [p['username'] for p in match_data['team1']]
        team2_names = [p['username'] for p in match_data['team2']]
        hsm_number = match_data.get('hsm_number', 'N/A')

        embed.add_field(
            name=f"Match #{match_id} (HSM{hsm_number})",
            value=
            f"🔴 **Team 1:** {', '.join(team1_names)}\n🔵 **Team 2:** {', '.join(team2_names)}",
            inline=False)

    if len(active_matches) > 5:
        embed.add_field(name="And more...",
                        value=f"Plus {len(active_matches) - 5} more matches",
                        inline=False)

    embed.set_footer(text="Select a match to access admin controls")

    # Create select menu
    class MatchSelectView(discord.ui.View):

        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.select(placeholder="Select a match to manage...",
                           min_values=1,
                           max_values=1,
                           options=options)
        async def match_select(self, select_interaction: discord.Interaction,
                               select: discord.ui.Select):
            try:
                match_id = int(select.values[0])
                print(f"[DEBUG] Admin selected match {match_id}")

                if match_id not in active_matches:
                    await select_interaction.response.send_message(
                        "❌ Match not found or already completed!",
                        ephemeral=True)
                    return
            except Exception as e:
                print(f"[DEBUG] Error in match_select: {e}")
                await select_interaction.response.send_message(
                    f"❌ Error selecting match: {e}", ephemeral=True)
                return

            match_data = active_matches[match_id]
            hsm_number = match_data.get('hsm_number', 'N/A')

            # Create detailed match embed
            control_embed = discord.Embed(
                title=f"🔧 Admin Control - Match #{match_id}",
                description=f"**HSM{hsm_number}** - Choose your action:",
                color=discord.Color.red())

            team1_names = [p['username'] for p in match_data['team1']]
            team2_names = [p['username'] for p in match_data['team2']]

            team1_mmr = sum(p['mmr'] for p in match_data['team1']) / len(
                match_data['team1'])
            team2_mmr = sum(p['mmr'] for p in match_data['team2']) / len(
                match_data['team2'])

            control_embed.add_field(
                name="🔴 Team 2",
                value=
                f"**Players:** {', '.join(team1_names)}\n**Avg MMR:** {team1_mmr:.0f}",
                inline=True)

            control_embed.add_field(
                name="🔵 Team 1",
                value=
                f"**Players:** {', '.join(team2_names)}\n**Avg MMR:** {team2_mmr:.0f}",
                inline=True)

            control_embed.add_field(
                name="⚙️ Admin Actions",
                value=
                "• **🏆 Team X Wins** - Set winner and update MMR\n• **🤝 Tie/Draw** - No MMR changes\n• **🚫 Cancel** - Cancel match entirely",
                inline=False)

            control_embed.set_footer(
                text="Use buttons below to manage this match")

            # Send admin control panel for this match
            admin_view = AdminMatchControlView(match_id)
            await select_interaction.response.send_message(embed=control_embed,
                                                           view=admin_view,
                                                           ephemeral=True)

    try:
        view = MatchSelectView()
        await interaction.response.send_message(embed=embed,
                                                view=view,
                                                ephemeral=True)
        print(f"[DEBUG] Admin match panel sent successfully")
    except Exception as e:
        print(f"[DEBUG] Error sending admin match panel: {e}")
        await interaction.response.send_message(
            f"❌ Error creating admin panel: {e}", ephemeral=True)


# Game Log System - View and Modify All Game Data
@bot.tree.command(
    name='game_log',
    description='View complete game history and statistics (Admin only)')
@app_commands.default_permissions(administrator=True)
async def game_log(interaction: discord.Interaction):
    """View complete game history with all details"""
    print(
        f"[DEBUG] Game log command called by {interaction.user.display_name}")

    # Get all matches from database
    c.execute("""
        SELECT match_id, team1_players, team2_players, winner, created_at, ended_at, 
               admin_modified, cancelled
        FROM matches 
        ORDER BY match_id DESC
    """)
    all_matches = c.fetchall()

    if not all_matches:
        embed = discord.Embed(title="📋 Game Log",
                              description="**No matches found in database**",
                              color=discord.Color.orange())
        await interaction.response.send_message(embed=embed, ephemeral=True)
        return

    # Create main log embed
    embed = discord.Embed(
        title="📋 Complete Game Log",
        description=
        f"**{len(all_matches)} total matches found**\n\nSelect a match to view details:",
        color=discord.Color.blue())

    # Add summary statistics
    completed_matches = [m for m in all_matches if m[3] is not None]
    active_matches_count = len(all_matches) - len(completed_matches)

    embed.add_field(
        name="📊 Summary",
        value=
        f"**Total:** {len(all_matches)}\n**Completed:** {len(completed_matches)}\n**Active:** {active_matches_count}",
        inline=True)

    # Create dropdown for match selection
    options = []
    for match in all_matches[:25]:  # Discord limit
        match_id, team1_ids, team2_ids, winner, created_at, ended_at, admin_modified, cancelled = match

        # Get team names
        team1_names = []
        team2_names = []

        if team1_ids:
            for player_id in team1_ids.split(','):
                c.execute("SELECT username FROM players WHERE id = ?",
                          (player_id, ))
                result = c.fetchone()
                if result:
                    team1_names.append(result[0])

        if team2_ids:
            for player_id in team2_ids.split(','):
                c.execute("SELECT username FROM players WHERE id = ?",
                          (player_id, ))
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

        options.append(
            discord.SelectOption(label=f"Match #{match_id}",
                                 description=description[:100],
                                 value=str(match_id)))

    # Create select menu view
    class GameLogView(discord.ui.View):

        def __init__(self):
            super().__init__(timeout=300)

        @discord.ui.select(placeholder="Select a match to view details...",
                           options=options)
        async def match_select(self, select_interaction: discord.Interaction,
                               select: discord.ui.Select):
            match_id = int(select.values[0])

            # Get detailed match data
            c.execute(
                """
                SELECT match_id, team1_players, team2_players, winner, created_at, ended_at,
                       admin_modified, cancelled, channel_id
                FROM matches WHERE match_id = ?
            """, (match_id, ))
            match_data = c.fetchone()

            if not match_data:
                await select_interaction.response.send_message(
                    "❌ Match not found!", ephemeral=True)
                return

            # Create detailed embed
            await self.show_match_details(select_interaction, match_data)

        async def show_match_details(self, interaction: discord.Interaction,
                                     match_data):
            """Show detailed match information"""
            match_id, team1_ids, team2_ids, winner, created_at, ended_at, admin_modified, cancelled, channel_id = match_data

            # Get team player details
            team1_details = []
            team2_details = []

            if team1_ids:
                for player_id in team1_ids.split(','):
                    c.execute(
                        "SELECT username, mmr, wins, losses FROM players WHERE id = ?",
                        (player_id, ))
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
                    c.execute(
                        "SELECT username, mmr, wins, losses FROM players WHERE id = ?",
                        (player_id, ))
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
            embed = discord.Embed(title=f"🔍 Match #{match_id} Details",
                                  color=discord.Color.gold())

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
            embed.add_field(name="🎮 Match ID",
                            value=f"#{match_id}",
                            inline=True)
            embed.add_field(name="📅 Created",
                            value=created_at[:19] if created_at else "N/A",
                            inline=True)

            if ended_at:
                embed.add_field(name="⏰ Ended",
                                value=ended_at[:19],
                                inline=True)

            # Team 1 details
            if team1_details:
                team1_text = ""
                team1_avg_mmr = sum(
                    p['mmr'] for p in team1_details) / len(team1_details)
                for player in team1_details:
                    total_games = player['wins'] + player['losses']
                    winrate = (player['wins'] / total_games *
                               100) if total_games > 0 else 0
                    team1_text += f"**{player['username']}**\n"
                    team1_text += f"MMR: {player['mmr']} | W/L: {player['wins']}/{player['losses']} ({winrate:.1f}%)\n\n"

                embed.add_field(
                    name=f"🔴 Team 2 (Avg MMR: {team1_avg_mmr:.0f})",
                    value=team1_text,
                    inline=True)

            # Team 2 details
            if team2_details:
                team2_text = ""
                team2_avg_mmr = sum(
                    p['mmr'] for p in team2_details) / len(team2_details)
                for player in team2_details:
                    total_games = player['wins'] + player['losses']
                    winrate = (player['wins'] / total_games *
                               100) if total_games > 0 else 0
                    team2_text += f"**{player['username']}**\n"
                    team2_text += f"MMR: {player['mmr']} | W/L: {player['wins']}/{player['losses']} ({winrate:.1f}%)\n\n"

                embed.add_field(
                    name=f"🔵 Team 1 (Avg MMR: {team2_avg_mmr:.0f})",
                    value=team2_text,
                    inline=True)

            # Add modification buttons
            view = MatchModifyView(match_id)
            await interaction.response.edit_message(embed=embed, view=view)

    view = GameLogView()
    await interaction.response.send_message(embed=embed,
                                            view=view,
                                            ephemeral=True)


# Match Modification View
class MatchModifyView(discord.ui.View):

    def __init__(self, match_id):
        super().__init__(timeout=300)
        self.match_id = match_id

    @discord.ui.button(label="🏆 Set Team 1 Winner",
                       style=discord.ButtonStyle.green)
    async def set_team1_winner(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        await self.modify_match_winner(interaction, 1)

    @discord.ui.button(label="🏆 Set Team 2 Winner",
                       style=discord.ButtonStyle.green)
    async def set_team2_winner(self, interaction: discord.Interaction,
                               button: discord.ui.Button):
        await self.modify_match_winner(interaction, 2)

    @discord.ui.button(label="🤝 Set Tie", style=discord.ButtonStyle.secondary)
    async def set_tie(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        await self.modify_match_winner(interaction, 0)

    @discord.ui.button(label="🚫 Cancel Match",
                       style=discord.ButtonStyle.danger)
    async def cancel_match(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await self.modify_match_winner(interaction, None, cancelled=True)

    @discord.ui.button(label="📝 Edit Players",
                       style=discord.ButtonStyle.primary)
    async def edit_players(self, interaction: discord.Interaction,
                           button: discord.ui.Button):
        await self.show_player_editor(interaction)

    async def modify_match_winner(self,
                                  interaction: discord.Interaction,
                                  winner,
                                  cancelled=False):
        """Modify match winner"""
        try:
            if cancelled:
                c.execute(
                    """
                    UPDATE matches 
                    SET cancelled = 1, ended_at = ?, admin_modified = 1
                    WHERE match_id = ?
                """, (datetime.now().isoformat(), self.match_id))
                status = "🚫 Match cancelled"
            else:
                c.execute(
                    """
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
                color=discord.Color.green())
            embed.add_field(name="Admin",
                            value=interaction.user.mention,
                            inline=True)
            embed.add_field(name="Timestamp",
                            value=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                            inline=True)

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error updating match: {e}", ephemeral=True)

    async def show_player_editor(self, interaction: discord.Interaction):
        """Show player editor interface"""
        # Get all players
        c.execute(
            "SELECT id, username, mmr, wins, losses FROM players ORDER BY mmr DESC"
        )
        players = c.fetchall()

        embed = discord.Embed(
            title="📝 Player Editor",
            description="Select a player to modify their stats:",
            color=discord.Color.purple())

        # Create player selection dropdown
        options = []
        for player in players[:25]:  # Discord limit
            player_id, username, mmr, wins, losses = player
            total_games = wins + losses
            winrate = (wins / total_games * 100) if total_games > 0 else 0

            options.append(
                discord.SelectOption(
                    label=username,
                    description=
                    f"MMR: {mmr} | W/L: {wins}/{losses} ({winrate:.1f}%)",
                    value=player_id))

        class PlayerSelectView(discord.ui.View):

            def __init__(self):
                super().__init__(timeout=300)

            @discord.ui.select(placeholder="Select a player to edit...",
                               options=options)
            async def player_select(self,
                                    select_interaction: discord.Interaction,
                                    select: discord.ui.Select):
                player_id = select.values[0]

                # Get player data
                c.execute(
                    "SELECT username, mmr, wins, losses FROM players WHERE id = ?",
                    (player_id, ))
                player_data = c.fetchone()

                if not player_data:
                    await select_interaction.response.send_message(
                        "❌ Player not found!", ephemeral=True)
                    return

                await self.show_player_modify(select_interaction, player_id,
                                              player_data)

            async def show_player_modify(self,
                                         interaction: discord.Interaction,
                                         player_id, player_data):
                """Show player modification interface"""
                username, mmr, wins, losses = player_data

                embed = discord.Embed(title=f"📝 Edit Player: {username}",
                                      description="Choose what to modify:",
                                      color=discord.Color.purple())

                total_games = wins + losses
                winrate = (wins / total_games * 100) if total_games > 0 else 0

                embed.add_field(
                    name="Current Stats",
                    value=
                    f"**MMR:** {mmr}\n**Wins:** {wins}\n**Losses:** {losses}\n**Win Rate:** {winrate:.1f}%",
                    inline=False)

                # Create modification buttons
                view = PlayerModifyView(player_id, username)
                await interaction.response.edit_message(embed=embed, view=view)

        view = PlayerSelectView()
        await interaction.response.edit_message(embed=embed, view=view)


# Rank Management Commands
@bot.tree.command(
    name='create_ranks',
    description='Create all rank roles in the server (Admin only)')
@app_commands.default_permissions(administrator=True)
async def create_ranks(interaction: discord.Interaction):
    """Create all rank roles in the server"""
    await interaction.response.defer()

    try:
        created_roles = []
        existing_roles = []

        for rank_key, rank_data in RANK_ROLES.items():
            role_name = rank_data['role_name']

            # Check if role already exists
            existing_role = discord.utils.get(interaction.guild.roles,
                                              name=role_name)
            if existing_role:
                existing_roles.append(role_name)
                continue

            # Create the role
            try:
                new_role = await interaction.guild.create_role(
                    name=role_name,
                    color=discord.Color(rank_data['color']),
                    reason="HeatSeeker rank system setup")
                created_roles.append(role_name)
                logger.info(f"RANK SYSTEM: Created role {role_name}")
            except Exception as e:
                logger.error(
                    f"RANK SYSTEM: Error creating role {role_name}: {e}")

        embed = discord.Embed(title="🎖️ Rank Roles Setup",
                              description="Rank role creation completed!",
                              color=discord.Color.green())

        if created_roles:
            embed.add_field(name="✅ Created Roles",
                            value="\n".join(
                                [f"• {role}" for role in created_roles]),
                            inline=False)

        if existing_roles:
            embed.add_field(name="📋 Existing Roles",
                            value="\n".join(
                                [f"• {role}" for role in existing_roles]),
                            inline=False)

        embed.add_field(
            name="🔄 Next Step",
            value=
            "Use `/sync_ranks` to assign roles to players based on their MMR",
            inline=False)

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error creating rank roles: {e}")


@bot.tree.command(
    name='sync_ranks',
    description='Sync all player ranks based on current MMR (Admin only)')
@app_commands.default_permissions(administrator=True)
async def sync_ranks(interaction: discord.Interaction):
    """Sync all player ranks - Admin only command"""

    await interaction.response.defer(ephemeral=True)

    try:
        updated_count, total_count = await sync_all_player_ranks(
            interaction.guild)

        embed = discord.Embed(
            title="🎖️ Rank Sync Complete",
            description=f"**Successfully synced player ranks!**",
            color=discord.Color.green())

        embed.add_field(name="Players Updated",
                        value=f"**{updated_count}**",
                        inline=True)
        embed.add_field(name="Total Players",
                        value=f"**{total_count}**",
                        inline=True)
        embed.add_field(name="Success Rate",
                        value=f"**{(updated_count/total_count*100):.1f}%**"
                        if total_count > 0 else "**0%**",
                        inline=True)

        embed.add_field(
            name="🏅 Rank System",
            value="All players now have correct rank roles based on their MMR",
            inline=False)

        embed.set_footer(
            text=f"Rank sync performed by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(f"❌ Error syncing ranks: {e}")


@bot.tree.command(name='rank_info', description='Show rank system information')
async def rank_info(interaction: discord.Interaction):
    """Show rank system information"""

    embed = discord.Embed(
        title="🎖️ HeatSeeker Rank System",
        description="**Automatic rank assignment based on MMR**",
        color=discord.Color.purple())

    rank_text = ""
    for rank_data in RANK_ROLES.values():
        if rank_data['max_mmr'] == 9999:
            mmr_range = f"{rank_data['min_mmr']}+"
        else:
            mmr_range = f"{rank_data['min_mmr']}-{rank_data['max_mmr']}"

        rank_text += f"{rank_data['emoji']} **{rank_data['name']}**\n"
        rank_text += f"   MMR: {mmr_range}\n\n"

    embed.add_field(name="🏅 Available Ranks", value=rank_text, inline=False)

    embed.add_field(
        name="🔄 How It Works",
        value=
        "• Ranks are assigned automatically based on your MMR\n• Win matches to gain MMR and climb ranks\n• Roles are updated after each match AND every 10 minutes\n• Use `/rank` to see your current rank",
        inline=False)

    embed.add_field(
        name="⚡ Auto-Update System",
        value=
        "• Ranks update automatically every 10 minutes\n• Instant updates after matches\n• No manual rank requests needed",
        inline=False)

    embed.set_footer(text="Play matches to climb the ranks!")

    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(
    name='force_rank_update',
    description='Force immediate rank update for all players (Admin only)')
@app_commands.default_permissions(administrator=True)
async def force_rank_update(interaction: discord.Interaction):
    """Force immediate rank update for all players - Admin only"""

    await interaction.response.defer()

    try:
        # Get all active players
        c.execute(
            "SELECT id, username, mmr FROM players WHERE wins > 0 OR losses > 0"
        )
        active_players = c.fetchall()

        if not active_players:
            embed = discord.Embed(
                title="📋 Rank Update Complete",
                description="**No active players found to update!**",
                color=discord.Color.orange())
            await interaction.followup.send(embed=embed)
            return

        updated_count = 0
        errors = []

        for player_id, username, mmr in active_players:
            try:
                success = await update_player_rank_role(
                    interaction.guild, player_id, mmr)
                if success:
                    updated_count += 1
                else:
                    errors.append(f"{username}: Update failed")
            except Exception as e:
                errors.append(f"{username}: {str(e)[:50]}")

        embed = discord.Embed(
            title="🎖️ Force Rank Update Complete",
            description=f"**Forced rank update completed by admin!**",
            color=discord.Color.green())

        embed.add_field(name="Players Processed",
                        value=f"**{len(active_players)}**",
                        inline=True)
        embed.add_field(name="Successfully Updated",
                        value=f"**{updated_count}**",
                        inline=True)
        embed.add_field(
            name="Success Rate",
            value=f"**{(updated_count/len(active_players)*100):.1f}%**",
            inline=True)

        if errors and len(errors) <= 5:
            embed.add_field(name="⚠️ Errors",
                            value="\n".join(
                                [f"• {error}" for error in errors[:5]]),
                            inline=False)
        elif len(errors) > 5:
            embed.add_field(
                name="⚠️ Errors",
                value=
                f"• {len(errors)} errors occurred\n• Check logs for details",
                inline=False)

        embed.add_field(name="🔄 Next Auto-Update",
                        value="Automatic updates continue every 10 minutes",
                        inline=False)

        embed.set_footer(
            text=f"Force update performed by {interaction.user.display_name}")

        await interaction.followup.send(embed=embed)

    except Exception as e:
        await interaction.followup.send(
            f"❌ Error during force rank update: {e}")


# Player Modification View
class PlayerModifyView(discord.ui.View):

    def __init__(self, player_id, username):
        super().__init__(timeout=300)
        self.player_id = player_id
        self.username = username

    @discord.ui.button(label="⚡ Set MMR", style=discord.ButtonStyle.primary)
    async def set_mmr(self, interaction: discord.Interaction,
                      button: discord.ui.Button):
        await self.show_mmr_modal(interaction)

    @discord.ui.button(label="🏆 Set Wins", style=discord.ButtonStyle.green)
    async def set_wins(self, interaction: discord.Interaction,
                       button: discord.ui.Button):
        await self.show_wins_modal(interaction)

    @discord.ui.button(label="💔 Set Losses", style=discord.ButtonStyle.red)
    async def set_losses(self, interaction: discord.Interaction,
                         button: discord.ui.Button):
        await self.show_losses_modal(interaction)

    @discord.ui.button(label="🔄 Reset Stats",
                       style=discord.ButtonStyle.secondary)
    async def reset_stats(self, interaction: discord.Interaction,
                          button: discord.ui.Button):
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
            c.execute(
                "UPDATE players SET mmr = 800, wins = 0, losses = 0 WHERE id = ?",
                (self.player_id, ))
            conn.commit()

            embed = discord.Embed(
                title="✅ Player Stats Reset",
                description=
                f"**{self.username}** stats have been reset to default",
                color=discord.Color.green())
            embed.add_field(name="New Stats",
                            value="MMR: 800\nWins: 0\nLosses: 0",
                            inline=True)
            embed.add_field(name="Admin",
                            value=interaction.user.mention,
                            inline=True)

            await interaction.response.edit_message(embed=embed, view=None)

        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error resetting stats: {e}", ephemeral=True)


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
            max_length=5)
        self.add_item(self.mmr_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_mmr = int(self.mmr_input.value)
            if new_mmr < 0 or new_mmr > 5000:
                await interaction.response.send_message(
                    "❌ MMR must be between 0 and 5000", ephemeral=True)
                return

            c.execute("UPDATE players SET mmr = ? WHERE id = ?",
                      (new_mmr, self.player_id))
            conn.commit()

            embed = discord.Embed(
                title="✅ MMR Updated",
                description=f"**{self.username}** MMR set to {new_mmr}",
                color=discord.Color.green())
            embed.add_field(name="Admin",
                            value=interaction.user.mention,
                            inline=True)

            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error updating MMR: {e}", ephemeral=True)


class PlayerWinsModal(discord.ui.Modal):

    def __init__(self, player_id, username):
        super().__init__(title=f"Set Wins for {username}")
        self.player_id = player_id
        self.username = username

        self.wins_input = discord.ui.TextInput(
            label="New Wins",
            placeholder="Enter new wins count (e.g., 15)",
            required=True,
            max_length=5)
        self.add_item(self.wins_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_wins = int(self.wins_input.value)
            if new_wins < 0:
                await interaction.response.send_message(
                    "❌ Wins cannot be negative", ephemeral=True)
                return

            c.execute("UPDATE players SET wins = ? WHERE id = ?",
                      (new_wins, self.player_id))
            conn.commit()

            embed = discord.Embed(
                title="✅ Wins Updated",
                description=f"**{self.username}** wins set to {new_wins}",
                color=discord.Color.green())
            embed.add_field(name="Admin",
                            value=interaction.user.mention,
                            inline=True)

            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error updating wins: {e}", ephemeral=True)


class PlayerLossesModal(discord.ui.Modal):

    def __init__(self, player_id, username):
        super().__init__(title=f"Set Losses for {username}")
        self.player_id = player_id
        self.username = username

        self.losses_input = discord.ui.TextInput(
            label="New Losses",
            placeholder="Enter new losses count (e.g., 8)",
            required=True,
            max_length=5)
        self.add_item(self.losses_input)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            new_losses = int(self.losses_input.value)
            if new_losses < 0:
                await interaction.response.send_message(
                    "❌ Losses cannot be negative", ephemeral=True)
                return

            c.execute("UPDATE players SET losses = ? WHERE id = ?",
                      (new_losses, self.player_id))
            conn.commit()

            embed = discord.Embed(
                title="✅ Losses Updated",
                description=f"**{self.username}** losses set to {new_losses}",
                color=discord.Color.green())
            embed.add_field(name="Admin",
                            value=interaction.user.mention,
                            inline=True)

            await interaction.response.send_message(embed=embed,
                                                    ephemeral=True)

        except ValueError:
            await interaction.response.send_message(
                "❌ Please enter a valid number", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(
                f"❌ Error updating losses: {e}", ephemeral=True)


# Error handling
@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.CommandNotFound):
        await ctx.send(
            "❌ Command not found. Use `/help` to see available commands.")
    elif isinstance(error, commands.MissingRequiredArgument):
        await ctx.send(
            "❌ Missing required argument. Use `/help` for command usage.")
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
