# Professional Expense Reporting System

## Overview

Professional Expense Reporting System is a comprehensive business tool designed to automate expense reporting and approvals for business executives. The system provides automated approval workflows, comprehensive expense tracking, and data export capabilities. Built with both full-stack JavaScript (Node.js/React) and Python implementations for maximum compatibility.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

The application follows a modern full-stack architecture with the following components:

- **Frontend**: React with TypeScript, TailwindCSS for styling
- **Backend**: Node.js with Express.js REST API
- **Alternative**: Python-based console application for immediate demo
- **Storage**: In-memory storage for demo (easily replaceable with database)
- **UI Components**: Custom shadcn-inspired component library

## Key Components

### Frontend Application (React)
- **Technology**: React 18, TypeScript, Wouter for routing
- **Styling**: TailwindCSS with custom design system
- **State Management**: TanStack Query for server state
- **Forms**: React Hook Form with Zod validation
- **Components**: Custom UI component library

### Backend API (Node.js)
- **Technology**: Express.js with TypeScript
- **Validation**: Zod schemas for request validation
- **Storage**: Pluggable storage interface (currently in-memory)
- **Routes**: RESTful API endpoints for expense management

### Python Demo Application
- **Technology**: Python 3 console application
- **Features**: Interactive CLI for expense management
- **Storage**: In-memory data structures
- **Export**: CSV and JSON export capabilities

## Core Features

### Expense Management
- **Create Expenses**: Submit expense reports with categories and descriptions
- **View Expenses**: List all expenses with filtering and search capabilities
- **Expense Details**: Detailed view with approval history
- **Categories**: Travel, meals, office, software, training, other

### Approval Workflows
- **Pending Review**: Expenses automatically enter pending status
- **Manager Approval**: Designated approvers can approve/reject expenses
- **Approval History**: Track all approval actions with timestamps
- **Rejection Reasons**: Detailed reasons for rejected expenses

### Dashboard & Analytics
- **Statistics**: Total expenses, pending approvals, approved amounts
- **Recent Activity**: Latest expense submissions and approvals
- **Monthly Tracking**: Current month expense totals
- **Visual Indicators**: Status badges and progress indicators

### Data Export
- **CSV Export**: Export expenses to CSV format for analysis
- **JSON Export**: Export structured data for integration
- **Date Range Filtering**: Export expenses within specific date ranges
- **Comprehensive Data**: Include user information and approval details

## Data Schema

### Users
- ID, name, email, role (employee/manager/admin)
- Department and manager hierarchy
- Contact information

### Expenses
- ID, title, description, amount, category
- User association and submission date
- Status tracking (pending/approved/rejected)
- Approval metadata (approver, date, reason)

### Approvals
- Approval history with timestamps
- Approver information and actions
- Rejection reasons and comments

## Recent Changes

### July 12, 2025
- ✓ Created comprehensive Discord bot for MMR tracking and 2v2 queue system
- ✓ Built enhanced rank and leaderboard commands with rich embeds
- ✓ Implemented 2v2 queue system with fair team balancing
- ✓ Added dedicated channel system for queue commands
- ✓ Created automated match creation when 4 players queue
- ✓ Built match result reporting with MMR adjustments
- ✓ Added admin setup command for creating dedicated channels
- ✓ Integrated all features into existing main.py bot
- ✓ Created comprehensive help system and error handling
- ✓ Added match history tracking and cancellation features
- ✓ **CONVERTED ALL COMMANDS TO SLASH COMMANDS** - Bot now uses Discord's native slash command system
- ✓ Successfully synced 8 slash commands with Discord API
- ✓ Configured secure token handling with environment variables
- ✓ Tested and confirmed bot connects and syncs commands properly
- ✓ Created demonstration script showing all slash command functionality
- ✓ **IMPLEMENTED PROFESSIONAL BUTTON-BASED QUEUE SYSTEM** - No more typing needed
- ✓ **ADDED AUTOMATIC VOICE CHANNELS** - Each team gets dedicated voice channel (2 player limit)
- ✓ **CREATED DEDICATED MATCH CHANNELS** - Each match gets private text channel with buttons
- ✓ **ENHANCED CHANNEL MANAGEMENT** - Auto-creates categories, restricts queue channel to buttons only
- ✓ **IMPLEMENTED AUTO-CLEANUP** - Channels and voice rooms delete after match completion
- ✓ **ADDED PERSISTENT BUTTON VIEWS** - Buttons work after bot restarts
- ✓ **CREATED PROFESSIONAL EMBEDS** - Rich formatting with team info and match statistics
- ✓ **ENHANCED ERROR HANDLING** - Ephemeral messages for better user experience
- ✓ **IMPLEMENTED HSM PRIVATE CHAT SYSTEM** - Users can create private chats with unique HSM numbers (HSM1-HSM9999)
- ✓ **ADDED PRIVATE CHANNEL CREATION** - Each private chat gets dedicated text and voice channels
- ✓ **BUILT HSM NUMBER MANAGEMENT** - Database tracks all active HSM numbers with recycling system
- ✓ **CREATED PRIVATE PERMISSIONS SYSTEM** - Full access control for private chat creators
- ✓ **ADDED /private SLASH COMMAND** - Complete management interface for HSM private chats
- ✓ **INTEGRATED WITH EXISTING SYSTEM** - Works alongside queue system with same professional interface
- ✓ **IMPLEMENTED ADMIN CANCEL QUEUE COMMAND** - Admins can instantly clear entire queue with detailed feedback
- ✓ **ADDED PRIVATE MATCH CHANNELS FOR QUEUE PARTICIPANTS** - Each queue joiner gets private preparation channel
- ✓ **ENHANCED RANKING SYSTEM INTEGRATION** - Private match channels fully connected to MMR system
- ✓ **IMPROVED AUTO-CLEANUP SYSTEM** - Comprehensive channel cleanup for all private match channels
- ✓ **EXPANDED TO 10 SLASH COMMANDS** - Complete bot with admin controls and private features
- ✓ **IMPLEMENTED AUTOMATIC QUEUE TIMEOUT SYSTEM** - 5-minute inactivity timer automatically clears stalled queues
- ✓ **ADDED SMART ACTIVITY TRACKING** - Timer resets on any queue activity (join/leave), starts background monitoring
- ✓ **ENHANCED QUEUE DISPLAY** - Shows timeout settings and real-time countdown for remaining time
- ✓ **INTEGRATED COMPREHENSIVE CLEANUP** - Timeout system cleans up all queue-related channels and data
- ✓ **PROFESSIONAL TIMEOUT NOTIFICATIONS** - Detailed feedback when queue times out with player statistics
- ✓ **IMPLEMENTED OPTIONAL TEAM SELECTION SYSTEM** - Players choose Random Teams or Captain Draft when queue completes
- ✓ **ADDED HSM MATCH NUMBERING** - Matches named HSM1-HSM9999 with unique number recycling system
- ✓ **CREATED PRIVATE MATCH CHANNELS** - Only match participants can see match channels with secure permissions
- ✓ **BUILT CAPTAIN DRAFT SYSTEM** - Top 2 MMR players become captains and draft teams interactively
- ✓ **ENHANCED MATCH CREATION** - Professional team selection interface with 5-minute timeout
- ✓ **IMPLEMENTED EMPTY LEADERBOARD SYSTEM** - Leaderboard only shows players who have participated in matches
- ✓ **ADDED PAGINATED LEADERBOARD** - 10 players per page with Previous/Next navigation buttons
- ✓ **CREATED ACTIVE PLAYER FILTERING** - Only players with wins > 0 OR losses > 0 appear on leaderboard
- ✓ **BUILT PROFESSIONAL PAGINATION VIEW** - Interactive Discord buttons for smooth navigation
- ✓ **ENHANCED EMPTY STATE MESSAGING** - Motivational messages encourage players to join queue
- ✓ **IMPLEMENTED AUTOMATED DM NOTIFICATIONS** - Winners and losers receive detailed match completion DMs
- ✓ **CREATED ADMIN CONTROL PANEL** - New /admin_match command for complete match management
- ✓ **FIXED DOUBLE VICTORY BUG** - Removed duplicate /win command, only match buttons process results
- ✓ **ENHANCED DATABASE SCHEMA** - Added admin_modified and cancelled columns for match tracking
- ✓ **BUILT COMPREHENSIVE MATCH OVERRIDE SYSTEM** - Admins can set winners, ties, or cancel matches
- ✓ **ADDED MOTIVATIONAL DM SYSTEM** - Encouraging messages for both winners and losers with stats

### July 13, 2025
- ✓ **STREAMLINED QUEUE SYSTEM** - Removed individual private match channels for cleaner server organization
- ✓ **FIXED QUEUE CANCELLATION** - `/cancel_queue` command now works properly without private channel cleanup
- ✓ **RESET PLAYER POINTS AND GAMES** - All players restored to 1000 MMR with 0-0 win/loss records
- ✓ **SIMPLIFIED QUEUE WORKFLOW** - Only #heatseeker-queue channel needed, match channels created when full
- ✓ **IMPROVED TEAM SELECTION** - Random Teams and Captain Draft system working reliably
- ✓ **ENHANCED RESOURCE MANAGEMENT** - Removed unnecessary private channel functions for better performance
- ✓ **MAINTAINED CORE FEATURES** - All ranking, DM notifications, and admin controls still functional
- ✓ **FIXED CAPTAIN DRAFT SYSTEM** - Button callbacks now properly generate team selection values
- ✓ **IMPROVED DRAFT INTERFACE** - Interactive player selection buttons work reliably
- ✓ **ENHANCED ERROR HANDLING** - Better turn validation and draft session management
- ✓ **FIXED ADMIN MATCH COMMAND** - Debug logging and error handling added for reliable admin controls
- ✓ **IMPROVED ADMIN INTERFACE** - Better match selection dropdown and professional error messages
- ✓ **ENHANCED ADMIN DEBUGGING** - Console logging for troubleshooting admin command issues
- ✓ **FIXED CAPTAIN DRAFT MATCH CREATION** - Pick order logic corrected from [0,1,1,0] to [0,1] for 2v2 scenarios
- ✓ **ENHANCED DRAFT DEBUGGING** - Comprehensive logging for captain draft system troubleshooting
- ✓ **IMPROVED DRAFT COMPLETION** - Draft now completes automatically after 2 picks and creates matches
- ✓ **FIXED DATABASE CONSTRAINT ERROR** - Added match_id_counter initialization to prevent UNIQUE constraint failures
- ✓ **ENHANCED DATABASE ERROR HANDLING** - Added try-catch blocks and automatic retry logic for database operations
- ✓ **IMPROVED STARTUP ROBUSTNESS** - Match counter now initializes from database MAX(match_id) on bot restart
- ✓ **FIXED ADMIN MATCH COMMAND** - Added restore_active_matches() function to populate active_matches from database
- ✓ **ENHANCED MATCH RESTORATION** - Bot now restores all active matches on startup with complete team data
- ✓ **IMPROVED ADMIN CONTROLS** - Admin match command now works properly with restored matches from database
- ✓ **IMPLEMENTED COMPREHENSIVE GAME LOG SYSTEM** - New /game_log command for complete match history and data modification
- ✓ **ADDED MATCH HISTORY VIEWER** - View all matches with status, teams, timestamps, and detailed statistics
- ✓ **BUILT PLAYER EDITOR SYSTEM** - Modify player MMR, wins, losses, and reset stats with admin controls
- ✓ **ENHANCED DATABASE SCHEMA** - Added admin_modified and cancelled columns for complete tracking
- ✓ **CREATED INTERACTIVE MODIFICATION INTERFACE** - Buttons and modals for easy data editing
- ✓ **ADDED COMPREHENSIVE ADMIN LOGGING** - All modifications tracked with timestamps and admin identification
- ✓ **EXPANDED TO 12 SLASH COMMANDS** - Complete administrative control over all game data
- ✓ **IMPLEMENTED RESULTS CHANNEL SYSTEM** - Bot creates dedicated channel for posting completed matches
- ✓ **ADDED ADMIN MODIFICATION BUTTONS** - Administrators can modify match results directly from results channel
- ✓ **ENHANCED SETUP COMMAND** - Now creates both queue and results channels automatically
- ✓ **BUILT PERSISTENT ADMIN CONTROLS** - Results channel posts include buttons for Team 1 Win, Team 2 Win, Tie, Cancel
- ✓ **INTEGRATED MATCH RESULT TRACKING** - All completed matches automatically posted to results channel for admin review
- ✓ **IMPLEMENTED COMPREHENSIVE LOGGING SYSTEM** - Complete event tracking with file and console output
- ✓ **ADDED CATEGORIZED EVENT LOGGING** - QUEUE, MATCH, ADMIN, and PLAYER event categories for organized monitoring
- ✓ **CREATED STRUCTURED LOG FORMAT** - Timestamp, level, logger name, and detailed message format
- ✓ **BUILT AUDIT TRAIL SYSTEM** - All admin actions logged with user identification and timestamps
- ✓ **ENHANCED DEBUGGING CAPABILITIES** - Error tracking, performance monitoring, and comprehensive event history
- ✓ **INTEGRATED REAL-TIME MONITORING** - Console and file logging for immediate feedback and persistent records
- ✓ **FIXED CRITICAL MATCH COMPLETION BUG** - Players can now rejoin queue immediately after matches end
- ✓ **IMPLEMENTED IMMEDIATE ACTIVE MATCH CLEANUP** - Prevents players from being stuck in "active match" state
- ✓ **ENHANCED MATCH RESULT PROCESSING** - Match data copied before cleanup for proper channel management
- ✓ **IMPROVED CANCEL MATCH FUNCTIONALITY** - Same immediate cleanup fix applied to match cancellation
- ✓ **ADDED COMPREHENSIVE MATCH EVENT LOGGING** - All match completions and cancellations properly logged
- ✓ **FIXED DUPLICATE QUEUE DISPLAY BUG** - Bot no longer creates multiple queue displays simultaneously
- ✓ **IMPLEMENTED COMPREHENSIVE QUEUE CLEANUP** - All existing queue messages deleted before creating new display
- ✓ **ELIMINATED RACE CONDITION** - Multiple rapid join requests now properly handled without duplicates
- ✓ **ENHANCED QUEUE DISPLAY MANAGEMENT** - Single queue display maintained at all times for clean user experience
- ✓ **FIXED RESET QUEUE COMMAND BUG** - /reset_queue no longer shows "Application did not respond" error
- ✓ **CORRECTED VARIABLE NAME MISMATCH** - Fixed global variable references in reset_queue() function
- ✓ **ENHANCED RESET FUNCTIONALITY** - Now properly clears captain drafts and pending team selections
- ✓ **IMPROVED ERROR HANDLING** - Reset command now works reliably with proper logging and confirmation
- ✓ **RESOLVED ACTIVE MATCH BLOCKING ISSUE** - Fixed database inconsistency causing players to be stuck in "active match" state
- ✓ **CORRECTED DATABASE SCHEMA** - Updated cancelled matches to have winner = -1 instead of NULL
- ✓ **ELIMINATED QUEUE BLOCKING** - Bot now properly restores 0 active matches on startup instead of cancelled matches
- ✓ **RESTORED QUEUE FUNCTIONALITY** - All players can now join queue without "currently in an active match" errors

### July 15, 2025
- ✓ **CHANGED DEFAULT QUEUE SIZE** - Updated from 4 players (2v2) to 2 players (1v1) as default
- ✓ **ADDED DYNAMIC QUEUE CONFIGURATION** - New /queueplayer command to set queue size (2=1v1, 4=2v2, 6=3v3, etc.)
- ✓ **IMPLEMENTED AUTO-LEADERBOARD SYSTEM** - Automatic leaderboard updates every 30 minutes in designated channel
- ✓ **ADDED /set_leaderboard COMMAND** - Admins can set any channel as auto-updating leaderboard
- ✓ **ENHANCED MATCH CREATION SYSTEM** - Added /create_match command for custom HSM match creation
- ✓ **IMPROVED MENA SERVER DISPLAY** - All match messages now show Server Region: MENA
- ✓ **FIXED DUPLICATE CHANNEL PREVENTION** - Enhanced system to prevent duplicate match channel creation
- ✓ **CREATED CONFIGURATION GUIDE** - Comprehensive guide for manual editing of queue settings
- ✓ **DYNAMIC TEAM BALANCING** - Captain draft system now works with any team size (1v1, 2v2, 3v3, 5v5, etc.)
- ✓ **FLEXIBLE PICK ORDER SYSTEM** - Automatically adjusts captain draft picks based on team size
- ✓ **ENHANCED QUEUE DISPLAY** - All queue messages now show current configuration (1v1, 2v2, etc.)
- ✓ **ADDED QUEUE RESET ON CONFIGURATION CHANGE** - Queue clears when admin changes player count
- ✓ **FIXED MATCH RESULT BUTTONS** - Resolved "This interaction failed" error when determining match winners
- ✓ **CLEANED DATABASE** - Removed corrupted match data (Match 7 with incomplete team data)
- ✓ **ENHANCED ERROR HANDLING** - Added comprehensive try-catch blocks and detailed logging for match interactions
- ✓ **IMPROVED BUTTON VALIDATION** - Added thorough data validation for all match result buttons
- ✓ **ADDED DEBUGGING TOOLS** - Created match_result_fix.py and fix_match_buttons.py for troubleshooting
- ✓ **IMPLEMENTED SEQUENTIAL HSM NUMBERING** - Match names now use sequential numbering (HSM1, HSM2, HSM3, etc.)
- ✓ **FIXED TEAM CREATION LOGIC** - Dynamic team balancing now properly uses TEAM_SIZE variable
- ✓ **UPDATED MATCH WELCOME MESSAGES** - All match displays now show correct game type (1v1, 2v2, etc.)
- ✓ **ENHANCED QUEUE DISPLAY** - Queue counter now shows correct player requirements based on configuration
- ✓ **ADDED HSM_NUMBER DATABASE COLUMN** - Match database now tracks sequential HSM numbers for proper ordering

## Deployment Strategy

### Current State
- Full-stack JavaScript application ready for deployment
- Python demo application for immediate testing
- In-memory storage for rapid prototyping
- Comprehensive UI components and styling

### Production Requirements
- Node.js runtime environment
- Database integration (PostgreSQL/MySQL recommended)
- Authentication system integration
- File upload capabilities for receipts
- Email notification system for approvals

### Development Setup
- TypeScript configuration with path aliases
- TailwindCSS for styling with custom theme
- React Query for state management
- Responsive design with mobile support