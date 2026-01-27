# Multi-Server Setup Guide

The bot now works on **all servers** where it's invited! 

## What Changed

✅ Commands are now **global** instead of guild-specific
✅ Bot automatically works on all servers
✅ No need to configure GUILD_ID anymore
✅ Each server can have its own events channel (optional)

## How to Add to Another Server

1. **Use the same invite link** you used before (or generate a new one)
2. **Invite to your new server**
3. **Restart the bot** (commands take up to 1 hour to appear globally)
4. **Start using commands!**

## Configuration

Your `.env` file settings are now **optional**:

```env
# Required
DISCORD_TOKEN=your_bot_token_here

# Optional (set to 0 or leave blank to disable)
GUILD_ID=0
EVENTS_CHANNEL_ID=0
```

### Channel Restrictions

- **EVENTS_CHANNEL_ID = 0**: `/create_event` works in **any channel**
- **EVENTS_CHANNEL_ID = 123456**: `/create_event` only works in that specific channel

## Important Notes

⚠️ **Global commands take up to 1 hour to sync** across all Discord servers
- Guild-specific commands are instant
- Global commands are cached by Discord

💡 **First time setup**: After restarting, wait a few minutes and the commands will appear

🔄 **Already running?** Just restart the bot and invite it to your new server!

## Per-Server Configuration

If you need different settings per server, you have two options:

### Option 1: Run separate bot instances (Docker)
- One container per server
- Different .env for each
- Complete isolation

### Option 2: Dynamic channel detection
- The bot now uses the thread's parent channel for pings if EVENTS_CHANNEL_ID is not set
- This allows it to work naturally in any channel

## Testing

1. Restart the bot
2. Wait 1-2 minutes
3. Type `/` in Discord
4. Commands should appear!

If they don't show up after 5-10 minutes, try:
- Restarting Discord
- Checking bot permissions
- Viewing the bot logs for errors
