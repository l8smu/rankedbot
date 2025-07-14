#!/usr/bin/env python3
"""
Reset Players Script - Resets all player MMR, wins, and losses to starting values
"""

import sqlite3
import logging

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('heatseeker_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('HeatSeeker')

def reset_all_players():
    """Reset all players to starting values"""
    
    print("🔄 RESETTING ALL PLAYER DATA")
    print("=" * 50)
    
    try:
        # Connect to database
        conn = sqlite3.connect('players.db')
        c = conn.cursor()
        
        # Get current player count
        c.execute("SELECT COUNT(*) FROM players")
        player_count = c.fetchone()[0]
        
        print(f"📊 Found {player_count} players in database")
        print()
        
        # Show current stats before reset
        print("📋 BEFORE RESET:")
        print("-" * 30)
        c.execute("SELECT username, mmr, wins, losses FROM players ORDER BY mmr DESC LIMIT 10")
        for row in c.fetchall():
            print(f"  {row[0]}: MMR={row[1]}, W/L={row[2]}/{row[3]}")
        
        # Reset all players to starting values
        print("\n🔄 RESETTING ALL PLAYERS...")
        c.execute("UPDATE players SET mmr = 1000, wins = 0, losses = 0")
        
        # Commit changes
        conn.commit()
        
        # Show stats after reset
        print("\n✅ AFTER RESET:")
        print("-" * 30)
        c.execute("SELECT username, mmr, wins, losses FROM players ORDER BY username LIMIT 10")
        for row in c.fetchall():
            print(f"  {row[0]}: MMR={row[1]}, W/L={row[2]}/{row[3]}")
        
        # Get match count
        c.execute("SELECT COUNT(*) FROM matches")
        match_count = c.fetchone()[0]
        
        print(f"\n📈 STATISTICS:")
        print(f"  • Players reset: {player_count}")
        print(f"  • Starting MMR: 1000")
        print(f"  • Win/Loss records: 0/0")
        print(f"  • Matches in database: {match_count}")
        
        # Log the reset action
        logger.info(f"ADMIN RESET: System - Reset {player_count} players to starting values (MMR: 1000, W/L: 0/0)")
        
        conn.close()
        
        print("\n🎉 PLAYER RESET COMPLETE!")
        print("=" * 50)
        print("✅ All players now have:")
        print("   • MMR: 1000")
        print("   • Wins: 0")
        print("   • Losses: 0")
        print("\n🎮 Players can now start fresh with equal rankings!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        logger.error(f"Player reset failed: {e}")
        return False
    
    return True

def reset_matches():
    """Reset all match data"""
    
    print("\n🔄 RESETTING ALL MATCH DATA")
    print("=" * 50)
    
    try:
        # Connect to database
        conn = sqlite3.connect('players.db')
        c = conn.cursor()
        
        # Get current match count
        c.execute("SELECT COUNT(*) FROM matches")
        match_count = c.fetchone()[0]
        
        print(f"📊 Found {match_count} matches in database")
        
        # Clear all matches
        if match_count > 0:
            print("🗑️ CLEARING ALL MATCHES...")
            c.execute("DELETE FROM matches")
            conn.commit()
            
            # Reset match counter
            c.execute("UPDATE sqlite_sequence SET seq = 0 WHERE name = 'matches'")
            conn.commit()
            
            print(f"✅ Deleted {match_count} matches")
            logger.info(f"ADMIN RESET: System - Deleted {match_count} matches from database")
        else:
            print("ℹ️ No matches to delete")
        
        conn.close()
        
        print("\n🎉 MATCH RESET COMPLETE!")
        print("=" * 50)
        print("✅ Match database is now empty")
        print("🎮 Ready for new matches!")
        
    except Exception as e:
        print(f"❌ ERROR: {e}")
        logger.error(f"Match reset failed: {e}")
        return False
    
    return True

if __name__ == "__main__":
    print("🎮 HEATSEEKER DATABASE RESET")
    print("=" * 50)
    print()
    
    # Reset players
    if reset_all_players():
        print("✅ Player reset successful")
    else:
        print("❌ Player reset failed")
    
    # Reset matches
    if reset_matches():
        print("✅ Match reset successful")
    else:
        print("❌ Match reset failed")
    
    print("\n🎉 DATABASE RESET COMPLETE!")
    print("🎮 The HeatSeeker bot is ready for fresh competition!")