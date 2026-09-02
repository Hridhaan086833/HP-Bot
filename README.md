# HP Bot

## 🌟 Overview

**HP Bot** is designed to be an all-in-one Discord bot solution providing server management, enhanced security, user engagement, and interactive gaming features powered by modern `discord.py` app commands (slash commands) and interactive UI components (buttons, selects, modals).

---

## 🔥 Features

### 🎫 Support & Ticket Management
- **Interactive Ticket Panel**: Post support ticket panels with customized categories (*Store / Purchase Rank*, *Minecraft Issue*, *Technical Support*, *Discord Support*, *Report Player / Appeal*, *VIP Support*).
- **Custom Modals**: Collect details, Minecraft IGN, and proof links directly through modal forms.
- **Claim & Close System**: Ticket staff can claim tickets to handle inquiries.
- **Automated Transcripts & Logs**: Archives entire ticket chat histories with text file transcripts and sends summary logs to a configured transcript channel.

### 🛡️ Moderation & Server Audit
- **Core Moderation**: `/kick`, `/ban`, `/mute` (timeout), `/unmute`, and `/unban`.
- **Deleted Message Logging**: Automatically logs deleted messages (content, attachments, author, and reason) to a database and logs channel. Review recent deleted messages via `/deleted-logs`.
- **Moderation Role Panel**: Interactively grant or revoke moderator roles via `/setup-moderation-role`.
- **Security Audit**: `/audit` scans server roles and bots for elevated management permissions, administrator permissions, or unverified bots.

### 🔒 Anti-Nuke Server Security
- **Action Guard Modules**: Monitors channel creation/deletion/updates, role creation/deletion/updates, guild edits, member bans, and member kicks.
- **Configurable Thresholds**: Set max allowed actions per module within custom time windows.
- **Lockdown Mode**: Automatically locks down text channel permissions during detected attacks or manually via `/antinuke lockdown`.
- **Flexible Punishments**: Choose between `ban`, `kick`, `quarantine`, or `none`.
- **Whitelist & Recovery**: Add trusted admins to an anti-nuke whitelist and use `/antinuke recover` to clear event histories and lift lockdowns.

### 🤖 AI Integration (Google Gemini)
- Ask questions directly to Gemini AI via `/ask question:<text>`.
- Configurable model (defaults to `gemini-3.6-flash`).

### 💰 Economy & Leveling System
- **Currency & Daily Rewards**: Earn coins via games, activity, and daily rewards (`!daily`). Check balances (`!balance_cmd`) and leaderboards (`/leaderboard`).
- **Item Shop**: Browse and buy custom rewards (`/shop`, `/buy`).
- **XP & Leveling**: Earn XP for sending messages with automatic level-up notifications and role rewards (`RANK_ROLES`).

### 🎮 Minigames
- **Multiplayer / Challenge Games**: Tic-Tac-Toe, Connect Four (5x5), Rock Paper Scissors (vs user or bot).
- **Singleplayer & Casino Games**: Blackjack, Coin Slots (`/slot`), Coinflip (`/coinflip`), Russian Roulette, Dice Roll (`/roll`), Minefield.
- **Puzzles & Trivia**: Hangman, Wordle, Trivia, Guess the Number, Pokemon Guess, Math Race, Unscramble, Emoji Quiz, High-Low, Truth or Dare, RPG Dungeon Exploration (`/explore`).
- **Game Channel Restriction**: Restrict games to a specific game channel via `/setup-game-channel`.

### 👥 Community & Utility Features
- **Suggestions System**: Modal input for user suggestions with community upvote/downvote buttons and staff approve/reject controls (`/suggest`, `/setup-suggestion-channel`).
- **Anonymous Confessions**: Review pipeline for anonymous confessions with staff approval before posting (`/confess`).
- **Giveaways**: Create timed giveaways with interactive entry buttons and random winner selection (`/giveaway`).
- **Welcome System**: Configurable welcome channel with customized greeting messages and visual banner cards (`/setup-welcome`).
- **Reaction Roles**: Self-assignable role menu panel (`/setup-reaction-roles`).
- **Media Enforcement**: Set channels to media-only mode (`/mediaonly`) or restrict media links to specific roles (`/media-role`). Safe link scanning detects malicious URLs via Google Safe Browsing API.
- **Counting Channel**: Automated counting channel support with expression evaluation and turn validation.

### ⚡ Real-Time Health Metrics
- Detailed health and diagnostic commands (`/health` and `/status`).
- Monitors WebSocket latency, event loop delay (ms), RSS & Python peak memory usage, bot uptime, guild/member count, `discord.py` version, and Python runtime status.

---

## 🛠️ Prerequisites & Requirements

- **Python**: 3.10 or higher
- **Dependencies**: Listed in `requirements.txt`
  - `discord.py>=2.3,<3`
  - `python-dotenv>=1.0,<2`
  - `google-generativeai>=0.8,<1`
  - `psutil` *(optional, for enhanced system memory statistics)*
  - `aiohttp` *(optional, for Google Safe Browsing URL scanning)*
- **FFmpeg**: System-level FFmpeg installation (required if using voice / TTS features).

---

## 🚀 Setup & Installation

1. **Clone the Repository**
   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

2. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment Variables**
   Create a `.env` file in the root directory (or edit your environment variables):

   ```env
   # Discord Bot Token (Required)
   DISCORD_TOKEN=your_discord_bot_token_here

   # Staff & Support Configuration
   SUPPORT_ROLE_ID=123456789012345678
   TICKET_CATEGORY_ID=123456789012345678

   # Channels
   SUGGESTION_CHANNEL_ID=123456789012345678
   CONFESSION_REVIEW_CHANNEL_ID=123456789012345678
   CONFESSION_CHANNEL_ID=123456789012345678
   COUNTING_CHANNEL_ID=123456789012345678
   MEDIA_CHANNEL_IDS=123456789012345678,987654321098765432

   # Security & URL Scanning
   SAFE_DOMAINS=example.com,youtube.com
   BLOCKED_DOMAINS=badsite.com
   GOOGLE_SAFE_BROWSING_KEY=your_google_safe_browsing_api_key

   # AI Integration
   GEMINI_API_KEY=your_gemini_api_key_here
   AI_MODEL=gemini-3.6-flash

   # Economy & Activity
   XP_PER_MESSAGE=10
   WELCOME_BANNER_URL=https://images.unsplash.com/photo-1511497584788-876760111969?auto=format&fit=crop&w=1200&q=80

   # Role Configuration Syntax Examples
   REACTION_ROLES=Gamer:123456789012345678,VIP:987654321098765432
   RANK_ROLES=5:123456789012345678,10:987654321098765432
   ```

4. **Run HP Bot**
   ```bash
   python Bottrial.py
   ```

---

## 📜 Command Overview

| Command | Description | Permissions |
| :--- | :--- | :--- |
| `/help [category]` | View all available bot commands or filter by category | Everyone |
| `/ask question:<text>` | Ask the Google Gemini AI assistant a question | Everyone |
| `/health` / `/status` | View real-time system metrics (latency, memory, loop delay, uptime) | Everyone |
| `/suggest` | Submit a community suggestion | Everyone |
| `/confess` | Submit an anonymous confession for staff review | Everyone |
| `/rank` | Display your server XP level and progress | Everyone |
| `/leaderboard` | View the top 10 coin balance holders | Everyone |
| `/shop` / `/buy` | Browse or purchase items from the coin shop | Everyone |
| `/setup-ticket` | Post the interactive support ticket panel | Manage Guild |
| `/setup-ticket-log` | Set the transcript log channel for closed tickets | Administrator |
| `/kick` / `/ban` / `/mute` | Moderation commands | Moderation permissions |
| `/deleted-logs` | View recently deleted messages | Manage Messages |
| `/audit` | Perform a server security risk scan | Administrator |
| `/antinuke <subcommand>` | Configure anti-nuke modules, limits, punishment, and lockdown | Administrator |
| `/giveaway` | Start a interactive giveaway | Administrator |
| `/setup-welcome` | Set up welcome greetings and channel | Administrator |
| `/setup-game-channel` | Restrict game commands to a designated channel | Administrator |

---

## 📁 Database & Storage

HP Bot uses an embedded **SQLite** database (`ticket_bot.sqlite3`), automatically initialized on startup to store:
- User balances and shop items
- Active & closed tickets and config
- Anti-nuke settings, event history, and whitelists
- Giveaways & entries
- Suggestions & votes
- Confessions, counting stats, activity XP, and channel configurations

---

## 📄 License

This project is open-source and intended for Discord server administration, security, and community entertainment.
