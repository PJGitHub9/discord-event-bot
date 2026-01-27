# Discord Event Bot

A feature-rich Discord bot for managing events with threads, role management, polls, and automatic reminders.

![Python](https://img.shields.io/badge/python-3.8+-blue.svg)
![discord.py](https://img.shields.io/badge/discord.py-2.3.2+-blue.svg)
![License](https://img.shields.io/badge/license-MIT-green.svg)

## ✨ Features

- 🎉 **Create Events** - Interactive event creation with threads
- 📊 **Date Polls** - Create events with TBD dates and let users vote
- 🏷️ **Role Management** - Automatic role creation and assignment
- ⏰ **Reminders** - Automatic reminders X days before events
- 📢 **Notifications** - Ping participants or @everyone
- ✏️ **Event Management** - Update title, date, or cancel events
- ♻️ **Reopen Events** - Cancelled events can be reopened by anyone
- 📝 **Full Logging** - Detailed logs of all actions
- 🌐 **Multi-Server** - Works on unlimited Discord servers
- 🐳 **Docker Ready** - Easy containerization with Docker/Docker Compose

## 📋 Commands

All commands are grouped under `/event`:

| Command | Description |
|---------|-------------|
| `/event create` | Create a new event thread with customizable options |
| `/event ping` | Notify participants (pings role if exists) |
| `/event pingeveryone` | Ping @everyone for important updates |
| `/event finalize` | Set final date after poll voting (TBD events) |
| `/event updatedate` | Change the event date |
| `/event updatetitle` | Change the event name |
| `/event cancel` | Cancel event (keeps roles for reopening) |
| `/event reopen` | Reopen a cancelled event (anyone can do this) |
| `/event close` | Close and clean up event (removes all roles) |

## 🚀 Quick Start

### Prerequisites

- Python 3.8 or higher
- Discord Bot Token ([Get one here](https://discord.com/developers/applications))

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/yourusername/discord-event-bot.git
   cd discord-event-bot
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure the bot**
   ```bash
   cp .env.example .env
   # Edit .env and add your DISCORD_TOKEN
   ```

4. **Run the bot**
   ```bash
   python bot.py
   ```

## ⚙️ Configuration

Create a `.env` file based on `.env.example`:

```env
# Required
DISCORD_TOKEN=your_bot_token_here

# Optional (set to 0 for multi-server support)
GUILD_ID=0
EVENTS_CHANNEL_ID=0
```

### Configuration Options

- **DISCORD_TOKEN** (Required): Your bot's authentication token
- **GUILD_ID** (Optional): Set to `0` to work on all servers, or specify a server ID
- **EVENTS_CHANNEL_ID** (Optional): Set to `0` to allow events in any channel, or specify a channel ID

## 🤖 Bot Setup

### 1. Create Bot Application

1. Go to [Discord Developer Portal](https://discord.com/developers/applications)
2. Click "New Application" and give it a name
3. Go to the **Bot** section and click "Add Bot"
4. Copy the bot token (you'll need this for `.env`)

### 2. Enable Intents

In the Bot section, enable:
- ✅ Server Members Intent
- ✅ Message Content Intent

### 3. Invite Bot to Server

1. Go to **OAuth2** → **URL Generator**
2. Select scopes: `bot`, `applications.commands`
3. Select bot permissions:
   - Manage Threads
   - Create Public Threads
   - Send Messages in Threads
   - Manage Messages
   - Manage Roles
   - Read Message History
   - Add Reactions
4. Copy the generated URL and open it in your browser
5. Select your server and authorize

## 🐳 Docker Deployment

### Using Pre-built Image from GHCR (Easiest)

```bash
# Pull the latest image
docker pull ghcr.io/yourusername/discord-event-bot:latest

# Run the container
docker run -d \
  --name discord-event-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  ghcr.io/yourusername/discord-event-bot:latest
```

Or update `docker-compose.yml` to use the pre-built image:
```yaml
services:
  discord-bot:
    image: ghcr.io/yourusername/discord-event-bot:latest
    # ... rest of config
```

### Using Docker Compose (Build Locally)

```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down
```

### Building Docker Image Manually

```bash
# Build the image
docker build -t discord-event-bot .

# Run the container
docker run -d \
  --name discord-event-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  discord-event-bot
```

See [DOCKER.md](DOCKER.md) for detailed Docker documentation.

## 📖 Usage Examples

### Creating an Event with a Fixed Date

1. Use `/event create` in your events channel
2. Fill in:
   - **event_name**: "Game Night"
   - **event_date**: "2026-02-15 18:00"
   - **ping_everyone**: Yes
   - **create_role**: Yes
   - **reminder_days**: 2

### Creating an Event with Date Poll (TBD)

1. Use `/event create`
2. Set **event_date** to "TBD"
3. Fill in poll dates:
   - **poll_date_1**: "2026-02-15 18:00"
   - **poll_date_2**: "2026-02-22 18:00"
   - **poll_date_3**: "2026-03-01 18:00"
4. Users vote by reacting with emojis
5. Author uses `/event finalize` to set the winning date

### Managing Events

- **Update date**: `/event updatedate new_date: 2026-02-20 19:00`
- **Update title**: `/event updatetitle new_title: Super Game Night`
- **Ping participants**: `/event ping`
- **Cancel event**: `/event cancel` (keeps roles for reopening)
- **Reopen event**: `/event reopen` (anyone can reopen)
- **Close event**: `/event close` (removes all roles permanently)

## 🗄️ Database

The bot uses SQLite to persist event data:
- Database file: `events.db` (or `data/events.db` in Docker)
- Automatically created on first run
- Stores event details, dates, roles, and reminder status
- Survives bot restarts

## 📊 Logging

The bot provides detailed logging:
- Event creation and management
- User actions (joining, voting, etc.)
- Role assignments and removals
- Reminder sends and cleanups
- Errors and warnings

View logs in the console or Docker logs.

## 🔧 Development

### Project Structure

```
discord-event-bot/
├── bot.py              # Main bot application
├── database.py         # Database operations
├── requirements.txt    # Python dependencies
├── .env.example        # Environment template
├── Dockerfile          # Docker image
├── docker-compose.yml  # Docker Compose config
├── README.md          # This file
└── DOCKER.md          # Docker documentation
```

### Running in Development

```bash
# Create virtual environment
python -m venv .venv

# Activate virtual environment
# On Windows:
.venv\Scripts\activate
# On Linux/Mac:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run bot
python bot.py
```

## 🌐 Multi-Server Support

The bot works on unlimited servers simultaneously:
- Events are isolated per server (no cross-contamination)
- Same database, different thread IDs
- Each server operates independently
- Invite the bot to multiple servers using the same bot token

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## 📝 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🐛 Known Issues

- Global commands can take up to 1 hour to sync across Discord
- First-time command sync may take a few minutes

## � CI/CD & Automation

The repository includes GitHub Actions automation:

- **Automatic Docker Builds**: Every push to `main` builds and publishes to GHCR
- **Version Tags**: Tag releases with `v1.0.0` format for versioned images
- **Pull Request Checks**: PRs are built (but not published) to verify changes
- **Image Registry**: [ghcr.io/yourusername/discord-event-bot](https://github.com/yourusername/discord-event-bot/pkgs/container/discord-event-bot)

**Using tagged versions:**
```bash
docker pull ghcr.io/yourusername/discord-event-bot:v1.0.0
docker pull ghcr.io/yourusername/discord-event-bot:latest
```

## �🙏 Acknowledgments

- Built with [discord.py](https://github.com/Rapptz/discord.py)
- Inspired by the need for better event management in Discord communities

---

Made with ❤️ for Discord communities
