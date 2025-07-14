#!/usr/bin/env python3
"""
Captain Draft Debug - Test and debug the captain draft logic
"""

def test_captain_draft_logic():
    """Test the captain draft completion logic"""
    print("🔍 CAPTAIN DRAFT LOGIC DEBUG")
    print("=" * 50)
    
    # Mock draft state
    draft_state = {
        'hsm_number': 1,
        'captains': [
            {'id': '1', 'username': 'Captain1', 'mmr': 1200},
            {'id': '2', 'username': 'Captain2', 'mmr': 1100}
        ],
        'current_captain': 0,
        'team1': [{'id': '1', 'username': 'Captain1', 'mmr': 1200}],
        'team2': [{'id': '2', 'username': 'Captain2', 'mmr': 1100}],
        'available_players': [
            {'id': '3', 'username': 'Player3', 'mmr': 1000},
            {'id': '4', 'username': 'Player4', 'mmr': 900}
        ],
        'pick_order': [0, 1, 1, 0],  # Captain 1 picks first, then alternating
        'current_pick': 0,
        'all_players': [
            {'id': '1', 'username': 'Captain1', 'mmr': 1200},
            {'id': '2', 'username': 'Captain2', 'mmr': 1100},
            {'id': '3', 'username': 'Player3', 'mmr': 1000},
            {'id': '4', 'username': 'Player4', 'mmr': 900}
        ]
    }
    
    print(f"Initial state:")
    print(f"  Team 1: {[p['username'] for p in draft_state['team1']]}")
    print(f"  Team 2: {[p['username'] for p in draft_state['team2']]}")
    print(f"  Available: {[p['username'] for p in draft_state['available_players']]}")
    print(f"  Current pick: {draft_state['current_pick']}")
    print(f"  Pick order: {draft_state['pick_order']}")
    print()
    
    # Simulate picks
    def simulate_pick(picked_player_id, pick_number):
        print(f"PICK {pick_number + 1}:")
        
        # Find player
        picked_player = None
        for player in draft_state['available_players']:
            if player['id'] == picked_player_id:
                picked_player = player
                break
        
        if not picked_player:
            print(f"  ERROR: Player {picked_player_id} not found!")
            return False
        
        print(f"  Player picked: {picked_player['username']}")
        
        # Add to team
        current_captain_idx = draft_state['current_captain']
        if current_captain_idx == 0:
            draft_state['team1'].append(picked_player)
            print(f"  Added to Team 1")
        else:
            draft_state['team2'].append(picked_player)
            print(f"  Added to Team 2")
        
        # Remove from available
        draft_state['available_players'].remove(picked_player)
        
        # Move to next pick
        draft_state['current_pick'] += 1
        
        print(f"  Current pick now: {draft_state['current_pick']}")
        
        # Check if complete
        if draft_state['current_pick'] >= len(draft_state['pick_order']):
            print(f"  DRAFT COMPLETE!")
            return True
        
        # Update captain
        draft_state['current_captain'] = draft_state['pick_order'][draft_state['current_pick']]
        next_captain = draft_state['captains'][draft_state['current_captain']]
        print(f"  Next captain: {next_captain['username']}")
        
        print(f"  Team 1: {[p['username'] for p in draft_state['team1']]}")
        print(f"  Team 2: {[p['username'] for p in draft_state['team2']]}")
        print(f"  Available: {[p['username'] for p in draft_state['available_players']]}")
        print()
        
        return False
    
    # Simulate the draft
    print("SIMULATING DRAFT:")
    print("=" * 50)
    
    # Pick 1: Captain 1 picks Player3
    if simulate_pick('3', 0):
        return
    
    # Pick 2: Captain 2 picks Player4
    if simulate_pick('4', 1):
        return
    
    print("FINAL TEAMS:")
    print("=" * 50)
    print(f"Team 1: {[p['username'] for p in draft_state['team1']]}")
    print(f"Team 2: {[p['username'] for p in draft_state['team2']]}")
    
    # Check pick order logic
    print("\nPICK ORDER ANALYSIS:")
    print("=" * 50)
    print(f"Pick order: {draft_state['pick_order']}")
    print(f"Pick order length: {len(draft_state['pick_order'])}")
    print(f"Expected picks: {len(draft_state['pick_order'])}")
    
    # The issue might be here - with 4 players and 2 captains, we only need 2 picks
    # Pick order should be [0, 1] for 2 picks total
    print(f"\nCORRECT PICK ORDER SHOULD BE:")
    print(f"  Available players: 2")
    print(f"  Total picks needed: 2")
    print(f"  Pick order should be: [0, 1]")
    print(f"  Current pick order: {draft_state['pick_order']} (TOO LONG!)")
    
    print("\n❌ ISSUE IDENTIFIED:")
    print("The pick order [0, 1, 1, 0] is for 4 picks, but we only have 2 available players!")
    print("This means the draft will never complete properly.")
    
    print("\n✅ SOLUTION:")
    print("For 2v2 with 2 captains and 2 available players:")
    print("Pick order should be [0, 1] - each captain picks once")

if __name__ == "__main__":
    test_captain_draft_logic()