# Discord Bot (Bottrial.py)

A feature-rich, multi-functional Discord bot written in Python using `discord.py`. It includes ticket management, moderation, anti-nuke server security, text-to-speech (TTS) voice playback, AI integration via Google Gemini, minigames, economy & leveling, community utility features, and real-time health metrics.

---

## Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Environment Configuration (.env)](#environment-configuration-env)
- [Database](#database)
- [Command Reference](#command-reference)
  - [Support Tickets](#support-tickets)
  - [Anti-Nuke Protection](#anti-nuke-protection)
  - [Moderation](#moderation)
  - [Text-to-Speech (TTS)](#text-to-speech-tts)
  - [Economy & XP Leveling](#economy--xp-leveling)
  - [Minigames](#minigames)
  - [Community & Utilities](#community--utilities)
  - [AI Assistant](#ai-assistant)
  - [System Health & Info](#system-health--info)
- [License](#license)

---

## Features

- **🎫 Support Ticket System**: Categorized support tickets with interactive modals, claiming system for staff, and transcript logging.
- **🛡️ Anti-Nuke Security**: Rate-limited action detection for channel/role deletions, updates, kicks, and bans with automatic quarantine, kick, or ban responses and server lockdown.
- **🔨 Moderation Tools**: Kick, ban, unban, mute (timeout), deleted message archiving, and automated server audit checks.
- **🗣️ Text-to-Speech (TTS)**: Voice channel reading of member messages using `gTTS` with language, emoji skipping, and character repeat settings.
- **🤖 Gemini AI Integration**: Ask questions and receive responses powered by Google's Gemini models.
- **🎮 Minigames & Economy**:
  - Games: Tic-Tac-Toe, Connect Four (5x5), Rock Paper Scissors, Blackjack, Minefield, Wordle, Hangman, Trivia, Coin Slots, Coinflip, Roulette, Pokemon Guess, Math Race, Unscramble, Emoji Quiz, Dungeon Explorer, and High-Low.
  - Economy: Daily rewards, coin balance, shop, item purchases, and server coin leaderboard.
  - Activity XP: XP progression and role rewards based on message activity.
- **💡 Community Utilities**: Suggestions with upvote/downvote polling, anonymous confessions with staff review, giveaways, reaction role panel, media-only channels, and a join-to-create temporary voice hub.

---

## Prerequisites

- **Python**: 3.8 or higher
- **FFmpeg**: Required for Text-to-Speech (TTS) audio streaming in voice channels.
  - **Linux (Ubuntu/Debian)**: `sudo apt install ffmpeg`
  - **macOS**: `brew install ffmpeg`
  - **Windows**: Install FFmpeg via [ffmpeg.org](https://ffmpeg.org/) or `winget install FFmpeg` and ensure it is added to system `PATH`.

---

## Installation & Setup

1. **Clone the repository and enter directory**:
   ```bash
   git clone <repository-url>
   cd <repository-directory>
   ```

2. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```
   *(Optional packages used if available: `psutil` for enhanced system health metrics, `gTTS` for TTS support, `aiohttp` for Google Safe Browsing URL scanning).*

3. **Configure Environment Variables**:
   Create a `.env` file in the root directory (see [Environment Configuration](#environment-configuration-env)).

4. **Run the Bot**:
   ```bash
   python Bottrial.py
   ```

---

## Environment Configuration (.env)

Define the following environment variables in your `.env` file:

```env
# Bot Authentication
DISCORD_TOKEN=your_discord_bot_token_here

# Core Configuration & Roles
SUPPORT_ROLE_ID=123456789012345678
TICKET_CATEGORY_ID=123456789012345678
SUGGESTION_CHANNEL_ID=123456789012345678
CONFESSION_REVIEW_CHANNEL_ID=123456789012345678
CONFESSION_CHANNEL_ID=123456789012345678
COUNTING_CHANNEL_ID=123456789012345678
VOICE_HUB_CHANNEL_ID=123456789012345678

# Media & Link Security
MEDIA_CHANNEL_IDS=123456789012345678,987654321098765432
SAFE_DOMAINS=example.com,discord.com
BLOCKED_DOMAINS=malicious-domain.com
GOOGLE_SAFE_BROWSING_KEY=your_google_safe_browsing_api_key

# AI Assistant Configuration
GEMINI_API_KEY=your_gemini_api_key
AI_MODEL=gemini-3.6-flash

# Economy & Leveling
XP_PER_MESSAGE=10
REACTION_ROLES=Gamer:123456789012345678,VIP:987654321098765432
RANK_ROLES=5:123456789012345678,10:987654321098765432
```

---

## Database

The bot uses an automated **SQLite3** database (`ticket_bot.sqlite3`) created on launch. It handles persistent state for:
- Users, balances, and shop items
- Tickets, ticket logs, and transcripts
- Deleted message archives
- Anti-nuke limits, modules, events, and whitelists
- Giveaways and entry records
- Suggestions and votes
- Confessions
- Counting game channel state
- Media-only channels and media link permissions
- Temporary voice channels
- TTS settings and configurations

---

## Command Reference

### Support Tickets

| Command | Type | Description |
|---|---|---|
| `/setup-ticket` | Slash | Posts the interactive support ticket panel (Requires `Manage Guild`). |
| `/setup-ticket-log` | Slash | Configures channel for storing closed ticket transcripts (Requires `Administrator`). |
| `!ticketpanel` | Prefix | Alternative prefix command to post the ticket panel. |

### Anti-Nuke Protection

Admin commands to control server anti-nuke safeguards (`/antinuke <subcommand>`):

| Subcommand | Description |
|---|---|
| `/antinuke enable` | Enables anti-nuke protection. |
| `/antinuke disable` | Disables anti-nuke protection. |
| `/antinuke guard` | Enables or disables a specific protection module (`channel_delete`, `role_delete`, `channel_update`, `role_update`, `guild_update`, `member_ban`, `member_kick`). |
| `/antinuke limits` | Sets maximum allowed actions for a module within the time window. |
| `/antinuke lockdown` | Toggles server lockdown mode (disables message sending across channels). |
| `/antinuke punishment` | Sets anti-nuke response (`ban`, `kick`, `quarantine`, `none`). |
| `/antinuke quarantinerole` | Assigns the role to use during quarantine response. |
| `/antinuke recover` | Clears tracked events and disables lockdown. |
| `/antinuke reset` | Resets all anti-nuke configurations to default settings. |
| `/antinuke status` | Displays current anti-nuke status, modules, and limits. |
| `/antinuke timewindow` | Sets time window (in seconds) for detection threshold. |
| `/antinuke whitelist` | Adds or removes a user from the anti-nuke whitelist. |
| `/antinuke setlogs` | Sets log channel for anti-nuke alerts. |

### Moderation

| Command | Type | Description |
|---|---|---|
| `/kick` | Slash | Kicks a specified member with optional reason. |
| `/ban` | Slash | Bans a specified member with optional message deletion window. |
| `/unban` | Slash | Unbans a user by Discord ID. |
| `/mute` | Slash | Times out a member for a specified duration in minutes. |
| `/unmute` | Slash | Removes timeout from a member. |
| `/setup-moderation-role` | Slash | Configures moderation role and posts management control panel. |
| `/setup-deletion-logs` | Slash | Sets channel for deleted message archive logs. |
| `/deleted-logs` | Slash | Views recent deleted messages log. |
| `/audit` | Slash | Audits server roles and unverified bots for common risk factors. |

### Text-to-Speech (TTS)

| Command | Type | Description |
|---|---|---|
| `/tts` | Slash | Joins user's voice channel and begins reading messages from members with specified role. |
| `/tts-set` | Slash | Configures language (`en`, `es`, `fr`, `de`, `it`, `pt`, `ja`, `ko`), emoji skipping, character repetition filter, and bot message ignoring. |
| `/tts-status` | Slash | Views active TTS voice channel status and settings. |
| `/tts-leave` | Slash | Stops TTS and disconnects bot from voice. |
| `-tts @role` | Prefix | Prefix command to start TTS. |
| `-tts-leave` | Prefix | Prefix command to stop TTS and disconnect bot. |

### Economy & XP Leveling

| Command | Type | Description |
|---|---|---|
| `/leaderboard` | Slash | Displays server top 10 coin balance holders. |
| `/shop` | Slash | Displays shop items and coin prices. |
| `/buy` | Slash | Purchases a shop item using coins. |
| `/rank` | Slash | Shows user activity level and XP progress. |
| `!daily` | Prefix | Claims 500 daily coins (24 hour cooldown). |
| `!shop` / `!buy` | Prefix | Prefix equivalents for shop browsing and purchases. |

### Minigames

Games comply with server game channel restrictions when configured via `/setup-game-channel`.

| Command | Type | Description |
|---|---|---|
| `/tic-tac-toe` | Slash | Challenge another member to Tic-Tac-Toe. |
| `/connect-four` | Slash | Challenge another member to Connect Four (5x5). |
| `/rps` | Slash | Rock Paper Scissors against a member or bot. |
| `/blackjack` | Slash | Play blackjack against dealer. |
| `/minefield` | Slash | Clear a 4x4 minefield without hitting mines. |
| `/slot` | Slash | Spin coin slots with customizable coin bet. |
| `/coinflip` | Slash | Bet on coin flip (Heads/Tails). |
| `/roulette` | Slash | Russian Roulette round (1/6 chance of 1-min timeout). |
| `/hangman` | Slash | Guess letters to solve a hidden word. |
| `/wordle` | Slash | 6-try 5-letter word puzzle. |
| `/trivia` | Slash | Answer multiple choice quiz question for coins. |
| `/guess` | Slash | Guess number between 1 and 100 within 60 seconds. |
| `/unscramble` | Slash | Unscramble a scrambled word. |
| `/pokemon-guess` | Slash | Guess Pokemon from a text hint. |
| `/math-race` | Slash | Solve multiplication math problem. |
| `/emoji-quiz` | Slash | Guess movie from emoji combination. |
| `/high-low` | Slash | Guess if next card value is higher or lower. |
| `/explore` | Slash | Dungeon exploration minigame for coins (1-hour cooldown). |
| `/truth-or-dare` | Slash | Receives a random truth or dare prompt. |
| `/roll` | Slash | Rolls a die with customizable sides (d2 to d100). |
| `/setup-game-channel` | Slash | Restricts minigames to a designated text channel. |

### Community & Utilities

| Command | Type | Description |
|---|---|---|
| `/suggest` | Slash | Submits a community suggestion with voting buttons. |
| `/setup-suggestion-channel` | Slash | Sets target channel for suggestions. |
| `/confess` | Slash | Submits an anonymous confession sent to staff review. |
| `/giveaway` | Slash | Creates a timed giveaway with random winner selection. |
| `/setup-reaction-roles` | Slash | Displays reaction role selection dropdown menu. |
| `/mediaonly` | Slash | Toggles media-only requirement for a channel. |
| `/media-role` | Slash | Selects required role to post photo, GIF, and video links. |
| `/role add` | Slash | Grants media link permission role to a member. |

### AI Assistant

| Command | Type | Description |
|---|---|---|
| `/ask` | Slash | Asks the Gemini AI assistant a question (`question:<text>`). |

### System Health & Info

| Command | Type | Description |
|---|---|---|
| `/health` / `/status` | Slash | Inspects bot ping, event loop delay, RSS/Peak memory usage, uptime, guild/member counts, Python version, and system time. |
| `/help` | Slash | Displays interactive command guide categorized by topic. |
| `!health` | Prefix | Text response pointing to `/health` / `/status`. |

---

## License

This project is provided as open-source software. Feel free to modify and customize it for your Discord community.
