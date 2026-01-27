# Docker Setup for Discord Event Bot

## Option 1: Single Bot (Recommended)

### Build and Run
```bash
# Build the image
docker build -t discord-event-bot .

# Run the container
docker run -d \
  --name pjs-discord-event-bot \
  --restart unless-stopped \
  -v $(pwd)/data:/app/data \
  --env-file .env \
  discord-event-bot
```

### Using Docker Compose (Easier)
```bash
# Start the bot
docker-compose up -d

# View logs
docker-compose logs -f

# Stop the bot
docker-compose down

# Restart the bot
docker-compose restart
```

## Option 2: Multiple Bots in One Container

If you want multiple bots in one container, create a supervisor setup:

1. Install supervisor in Dockerfile
2. Create config for each bot
3. Run supervisor as CMD

**However, this is NOT recommended because:**
- Harder to manage individual bots
- If one crashes, it might affect others
- Can't scale individual bots
- Logs are mixed together
- Updates require restarting all bots

## Option 3: Multiple Bots via Docker Compose (BEST)

Keep each bot in its own directory with its own Dockerfile, then use one docker-compose.yml:

```yaml
# Structure:
# /discord-bots/
#   docker-compose.yml
#   /event-bot/
#     Dockerfile, bot.py, .env
#   /music-bot/
#     Dockerfile, bot.py, .env

version: '3.8'
services:
  event-bot:
    build: ./event-bot
    container_name: pjs-event-bot
    restart: unless-stopped
    volumes:
      - ./event-bot/data:/app/data
    env_file:
      - ./event-bot/.env
  
  music-bot:
    build: ./music-bot
    container_name: pjs-music-bot
    restart: unless-stopped
    volumes:
      - ./music-bot/data:/app/data
    env_file:
      - ./music-bot/.env
```

## Unraid Setup

### Method 1: Docker Compose (via Compose Manager plugin)
1. Install "Compose Manager" plugin from Community Apps
2. Copy your bot folder to `/mnt/user/appdata/discord-bots/`
3. Add compose in Compose Manager
4. Start the stack

### Method 2: Native Unraid Docker
1. Go to Docker tab
2. Click "Add Container"
3. Fill in:
   - **Name**: `pjs-discord-event-bot`
   - **Repository**: `python:3.11-slim`
   - **Post Arguments**: `sh -c "pip install discord.py python-dotenv aiosqlite python-dateutil && python /app/bot.py"`
   - **Path**: `/mnt/user/appdata/discord-event-bot` → `/app`
   - **Environment Variables**: Add DISCORD_TOKEN, GUILD_ID, EVENTS_CHANNEL_ID

### Method 3: Custom Template (Easiest for Unraid)
1. Build image on your PC: `docker build -t pjs/discord-event-bot .`
2. Push to Docker Hub (optional)
3. Create Unraid template
4. Deploy from Community Applications

## Quick Start with Docker

```bash
# 1. Make sure you have .env configured
# 2. Build and start
docker-compose up -d

# 3. View logs
docker-compose logs -f event-scheduler-bot

# 4. Stop
docker-compose down
```

## Updating the Bot

```bash
# Rebuild after code changes
docker-compose down
docker-compose build
docker-compose up -d

# Or if using volume mount (hot reload)
docker-compose restart
```

## Database Persistence

The database is stored in `./data/events.db` and mounted as a volume, so it persists across container restarts.

## Logs

```bash
# Follow logs
docker-compose logs -f

# View last 100 lines
docker-compose logs --tail=100

# View logs for specific time
docker-compose logs --since 10m
```
