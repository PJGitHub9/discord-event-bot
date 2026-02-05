import discord
from discord import app_commands
from discord.ext import commands, tasks
from discord.ui import View, Button
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
from dateutil import parser
import asyncio
import database
import logging
import aiosqlite

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

try:
    GUILD_ID = int(os.getenv('GUILD_ID', '0').strip())
except ValueError:
    print(f"❌ Error: GUILD_ID must be a number! Current value: '{os.getenv('GUILD_ID')}'")
    print("Check your .env file and remove any extra characters (like periods or spaces)")
    exit(1)

try:
    EVENTS_CHANNEL_ID = int(os.getenv('EVENTS_CHANNEL_ID', '0').strip())
except ValueError:
    print(f"❌ Error: EVENTS_CHANNEL_ID must be a number! Current value: '{os.getenv('EVENTS_CHANNEL_ID')}'")
    print("Check your .env file and remove any extra characters (like periods or spaces)")
    exit(1)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
intents.guilds = True

bot = commands.Bot(command_prefix='!', intents=intents)

# Create command group (add once, before on_ready)
event_group = app_commands.Group(name="event", description="Event management commands")

# Helper function for logging with context
def log_event_action(action: str, user, guild, channel, event_name: str = None):
    """Log an event action with full context."""
    guild_name = guild.name if guild else "Unknown"
    channel_name = channel.name if hasattr(channel, 'name') else f"Channel {channel.id}"
    event_info = f' | Event: "{event_name}"' if event_name else ''
    logger.info(f'[{guild_name}] [{channel_name}] {action} by {user}{event_info}')

# Helper function to build attendance embed
async def build_attendance_embed(thread_id: int, guild) -> discord.Embed:
    """Build an attendance embed with current stats."""
    attendance_data = await database.get_attendance_stats(thread_id)
    
    # Organize by response type
    yes_users = []
    maybe_users = []
    no_users = []
    plus_ones = 0
    
    for entry in attendance_data:
        user = guild.get_member(entry['user_id'])
        user_mention = user.mention if user else f"<@{entry['user_id']}>"
        
        plus_one_indicator = " (+1)" if entry['plus_one'] else ""
        
        if entry['response'] == 'yes':
            yes_users.append(user_mention + plus_one_indicator)
            if entry['plus_one']:
                plus_ones += 1
        elif entry['response'] == 'maybe':
            maybe_users.append(user_mention + plus_one_indicator)
            if entry['plus_one']:
                plus_ones += 1
        elif entry['response'] == 'no':
            no_users.append(user_mention)
    
    # Create attendance embed
    attendance_embed = discord.Embed(
        title="📋 Will you be attending?",
        description="Click a button below to update your attendance!",
        color=discord.Color.blurple()
    )
    
    # Add summary
    total_responses = len(attendance_data)
    attendance_embed.add_field(
        name="📊 Summary",
        value=f"Total Responses: **{total_responses}** | Plus Ones: **{plus_ones}**",
        inline=False
    )
    
    # Yes responses
    if yes_users:
        yes_text = "\n".join(yes_users)
        if len(yes_text) > 1024:
            yes_text = yes_text[:1020] + "..."
        attendance_embed.add_field(
            name=f"✅ Yes ({len(yes_users)})",
            value=yes_text,
            inline=False
        )
    else:
        attendance_embed.add_field(
            name="✅ Yes (0)",
            value="*No responses yet*",
            inline=False
        )
    
    # Maybe responses
    if maybe_users:
        maybe_text = "\n".join(maybe_users)
        if len(maybe_text) > 1024:
            maybe_text = maybe_text[:1020] + "..."
        attendance_embed.add_field(
            name=f"❓ Maybe ({len(maybe_users)})",
            value=maybe_text,
            inline=False
        )
    else:
        attendance_embed.add_field(
            name="❓ Maybe (0)",
            value="*No responses yet*",
            inline=False
        )
    
    # No responses
    if no_users:
        no_text = "\n".join(no_users)
        if len(no_text) > 1024:
            no_text = no_text[:1020] + "..."
        attendance_embed.add_field(
            name=f"❌ No ({len(no_users)})",
            value=no_text,
            inline=False
        )
    else:
        attendance_embed.add_field(
            name="❌ No (0)",
            value="*No responses yet*",
            inline=False
        )
    
    return attendance_embed


# Attendance Button View
class AttendanceView(View):
    def __init__(self, event_role_id: int = None, thread_id: int = None):
        super().__init__(timeout=None)  # Buttons don't expire
        self.event_role_id = event_role_id
        self.thread_id = thread_id
    
    @discord.ui.button(label="Yes", style=discord.ButtonStyle.green, custom_id="attend_yes", emoji="✅")
    async def yes_button(self, interaction: discord.Interaction, button: Button):
        await self._handle_attendance(interaction, True, "Yes")
    
    @discord.ui.button(label="Maybe", style=discord.ButtonStyle.gray, custom_id="attend_maybe", emoji="❓")
    async def maybe_button(self, interaction: discord.Interaction, button: Button):
        await self._handle_attendance(interaction, True, "Maybe")
    
    @discord.ui.button(label="No", style=discord.ButtonStyle.red, custom_id="attend_no", emoji="❌")
    async def no_button(self, interaction: discord.Interaction, button: Button):
        await self._handle_attendance(interaction, False, "No")
    
    @discord.ui.button(label="+1", style=discord.ButtonStyle.blurple, custom_id="attend_plus_one", emoji="➕")
    async def plus_one_button(self, interaction: discord.Interaction, button: Button):
        await self._handle_plus_one(interaction)
    
    async def _handle_attendance(self, interaction: discord.Interaction, should_add_role: bool, response_type: str):
        """Handle attendance button clicks."""
        try:
            member = interaction.user
            
            # Record attendance in database
            if self.thread_id:
                await database.record_attendance(
                    thread_id=self.thread_id,
                    user_id=member.id,
                    response=response_type.lower()
                )
            
            # If there's a role, manage it
            if self.event_role_id:
                event_role = interaction.guild.get_role(self.event_role_id)
                if not event_role:
                    await interaction.response.send_message("Event role not found.", ephemeral=True)
                    return
                
                if should_add_role:
                    if event_role not in member.roles:
                        await member.add_roles(event_role)
                        await interaction.response.send_message(
                            f"✅ You've been added to {event_role.mention}! You'll be notified about updates.",
                            ephemeral=True
                        )
                        logger.info(f'{member} joined event via button (added role: {event_role.name})')
                    else:
                        await interaction.response.send_message(
                            f"You already have the {event_role.mention} role!",
                            ephemeral=True
                        )
                else:
                    if event_role in member.roles:
                        await member.remove_roles(event_role)
                        await interaction.response.send_message(
                            f"❌ You've been removed from {event_role.mention}.",
                            ephemeral=True
                        )
                        logger.info(f'{member} left event via button (removed role: {event_role.name})')
                    else:
                        await interaction.response.send_message(
                            "Thanks for letting us know!",
                            ephemeral=True
                        )
            else:
                # No role - just send confirmation
                if response_type == "Yes":
                    await interaction.response.send_message(
                        "✅ Great! Thanks for confirming your attendance!",
                        ephemeral=True
                    )
                elif response_type == "Maybe":
                    await interaction.response.send_message(
                        "❓ Thanks for letting us know you might attend!",
                        ephemeral=True
                    )
                else:
                    await interaction.response.send_message(
                        "❌ Thanks for letting us know!",
                        ephemeral=True
                    )
                logger.info(f'{member} responded "{response_type}" to attendance (no role)')
            
            # Update the attendance embed
            if self.thread_id:
                try:
                    updated_embed = await build_attendance_embed(self.thread_id, interaction.guild)
                    await interaction.message.edit(embed=updated_embed)
                except Exception as e:
                    logger.error(f"Error updating attendance embed: {e}")
                    
        except Exception as e:
            logger.error(f"Error handling attendance button: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )
    
    async def _handle_plus_one(self, interaction: discord.Interaction):
        """Handle +1 button clicks."""
        try:
            member = interaction.user
            
            # Toggle plus one status in database
            if self.thread_id:
                new_status = await database.toggle_plus_one(
                    thread_id=self.thread_id,
                    user_id=member.id
                )
                
                if new_status:
                    await interaction.response.send_message(
                        "➕ Thanks for letting us know you're bringing a +1!",
                        ephemeral=True
                    )
                    logger.info(f'{member} is bringing a +1')
                else:
                    await interaction.response.send_message(
                        "❌ +1 removed.",
                        ephemeral=True
                    )
                    logger.info(f'{member} removed +1')
                
                # Update the attendance embed
                try:
                    updated_embed = await build_attendance_embed(self.thread_id, interaction.guild)
                    await interaction.message.edit(embed=updated_embed)
                except Exception as e:
                    logger.error(f"Error updating attendance embed: {e}")
            else:
                await interaction.response.send_message(
                    "➕ Thanks for letting us know you're bringing a +1!",
                    ephemeral=True
                )
                logger.info(f'{member} indicated they are bringing a +1 (no tracking)')
        except Exception as e:
            logger.error(f"Error handling +1 button: {e}")
            await interaction.response.send_message(
                "❌ An error occurred. Please try again.",
                ephemeral=True
            )


@bot.event
async def on_ready():
    """Called when the bot is ready."""
    logger.info(f'Bot connected as {bot.user} (ID: {bot.user.id})')
    
    # Initialize database
    await database.init_database()
    logger.info('Database initialized successfully')
    
    # Sync commands globally (works on all servers)
    try:
        await bot.tree.sync()
        logger.info(f'Commands synced globally to all servers')
        logger.info(f'Bot is in {len(bot.guilds)} server(s)')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')
    
    # Start background tasks
    if not check_reminders.is_running():
        check_reminders.start()
    if not cleanup_old_events.is_running():
        cleanup_old_events.start()
    if not cleanup_non_thread_messages.is_running():
        cleanup_non_thread_messages.start()
    logger.info('Background tasks started')


@event_group.command(
    name="create",
    description="Create a new event thread"
)
@app_commands.describe(
    event_name="Name of the event",
    event_date="Date of event (YYYY-MM-DD HH:MM) or 'TBD' for poll",
    ping_everyone="Ping @everyone when creating the event?",
    create_role="Create a role for event participants?",
    reminder_days="Days before event to send reminder (0 for no reminder)",
    poll_date_1="First poll date option (required if TBD)",
    poll_date_2="Second poll date option (required if TBD)",
    poll_date_3="Third poll date option (optional)",
    poll_date_4="Fourth poll date option (optional)"
)
@app_commands.choices(ping_everyone=[
    app_commands.Choice(name="Yes", value=1),
    app_commands.Choice(name="No", value=0)
])
@app_commands.choices(create_role=[
    app_commands.Choice(name="Yes", value=1),
    app_commands.Choice(name="No", value=0)
])
async def create_event(
    interaction: discord.Interaction,
    event_name: str,
    event_date: str,
    ping_everyone: app_commands.Choice[int],
    create_role: app_commands.Choice[int],
    reminder_days: int = 0,
    poll_date_1: str = None,
    poll_date_2: str = None,
    poll_date_3: str = None,
    poll_date_4: str = None
):
    """Create a new event thread with the specified parameters."""
    log_event_action(
        f'Event creation requested',
        interaction.user,
        interaction.guild,
        interaction.channel,
        event_name
    )
    logger.info(f'  Date: {event_date} | Reminder: {reminder_days} days')
    
    # Defer the response as this might take a while
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check if command is used in the events channel
        # Note: EVENTS_CHANNEL_ID from .env is optional now - bot works on all servers
        # You can remove this check or set EVENTS_CHANNEL_ID=0 to allow any channel
        if EVENTS_CHANNEL_ID and interaction.channel_id != EVENTS_CHANNEL_ID:
            await interaction.followup.send(
                f"❌ This command should be used in your designated events channel!",
                ephemeral=True
            )
            return
        
        # Check if date is TBD (poll mode)
        is_tbd = event_date.upper() in ['TBD', 'UNKNOWN', 'POLL']
        parsed_date = None
        poll_dates = []
        
        if is_tbd:
            # Validate poll dates
            if not poll_date_1 or not poll_date_2:
                await interaction.followup.send(
                    "❌ When date is TBD, you must provide at least 2 poll date options (poll_date_1 and poll_date_2)!",
                    ephemeral=True
                )
                return
            
            # Parse poll dates
            poll_date_strs = [poll_date_1, poll_date_2, poll_date_3, poll_date_4]
            for pd in poll_date_strs:
                if pd:
                    try:
                        parsed_poll_date = parser.parse(pd)
                        if parsed_poll_date < datetime.now():
                            await interaction.followup.send(
                                f"❌ Poll date '{pd}' must be in the future!",
                                ephemeral=True
                            )
                            return
                        poll_dates.append(parsed_poll_date)
                    except Exception as e:
                        await interaction.followup.send(
                            f"❌ Invalid poll date format: '{pd}'. Please use YYYY-MM-DD HH:MM or YYYY-MM-DD",
                            ephemeral=True
                        )
                        return
            
            logger.info(f'  Poll mode with {len(poll_dates)} date options')
        else:
            # Parse the event date
            try:
                parsed_date = parser.parse(event_date)
            except Exception as e:
                await interaction.followup.send(
                    f"❌ Invalid date format. Please use YYYY-MM-DD HH:MM or YYYY-MM-DD\nExample: 2026-02-15 18:00\nOr use 'TBD' for poll",
                    ephemeral=True
                )
                return
            
            # Check if date is in the future
            if parsed_date < datetime.now():
                await interaction.followup.send(
                    "❌ Event date must be in the future!",
                    ephemeral=True
                )
                return
        
        guild = interaction.guild
        author = interaction.user
        events_channel = interaction.channel
        
        # Create author role for this event
        author_role_name = f"event_{event_name.replace(' ', '_')}_author"
        author_role = await guild.create_role(
            name=author_role_name,
            color=discord.Color.blue(),
            mentionable=False,
            reason=f"Event author role for {event_name}"
        )
        await author.add_roles(author_role)
        
        # Create event role if requested
        event_role = None
        if create_role.value == 1:
            event_role_name = f"event_{event_name.replace(' ', '_')}"
            event_role = await guild.create_role(
                name=event_role_name,
                color=discord.Color.green(),
                mentionable=True,
                reason=f"Event participant role for {event_name}"
            )
        
        # Create the thread
        if is_tbd:
            thread_name = f"📅 {event_name} - TBD (Poll Active)"
        else:
            thread_name = f"📅 {event_name} - {parsed_date.strftime('%Y-%m-%d')}"
        
        # Create initial message for the thread
        initial_message = await events_channel.send(
            f"🎉 **New Event Created!** 🎉"
        )
        
        # Create thread from the message
        thread = await initial_message.create_thread(
            name=thread_name,
            auto_archive_duration=10080  # 7 days
        )
        
# Build event announcement embed
        embed = discord.Embed(
            title=f"🎉 {event_name}",
            color=discord.Color.blue(),
            timestamp=datetime.now(timezone.utc)
        )
        
        if is_tbd:
            embed.add_field(
                name="📅 Date",
                value="TBD - Vote on the poll below!",
                inline=False
            )
        else:
            embed.add_field(
                name="📅 Date",
                value=parsed_date.strftime('%B %d, %Y at %I:%M %p'),
                inline=False
            )
        
        embed.add_field(
            name="👤 Organized by",
            value=author.mention,
            inline=False
        )
        
        if event_role:
            embed.add_field(
                name="🏷️ Event Role",
                value=event_role.mention,
                inline=False
            )
        
        if not is_tbd and reminder_days > 0:
            reminder_date = parsed_date - timedelta(days=reminder_days)
            embed.add_field(
                name="⏰ Reminder",
                value=f"{reminder_days} day(s) before ({reminder_date.strftime('%B %d, %Y')})",
                inline=False
            )
        
        embed.set_footer(text="Use /event help to see available commands")
        
        # Send announcement embed in thread
        await thread.send(embed=embed)
        
        # Create poll if TBD
        if is_tbd:
            poll_text_lines = [
                f"📊 **Vote for the event date!**",
                f"",
                f"React to vote for your preferred date:"
            ]
            
            # Add date options with emojis
            emojis = ["1️⃣", "2️⃣", "3️⃣", "4️⃣"]
            for i, poll_date in enumerate(poll_dates):
                poll_text_lines.append(f"{emojis[i]} {poll_date.strftime('%B %d, %Y at %I:%M %p')}")
            
            poll_text = "\n".join(poll_text_lines)
            poll_msg = await thread.send(poll_text)
            
            # Add reactions for voting
            for i in range(len(poll_dates)):
                await poll_msg.add_reaction(emojis[i])
            
            await poll_msg.pin()
            logger.info(f'Poll created with {len(poll_dates)} date options')
        
        # Always show attendance buttons (with or without role)
        attendance_embed = await build_attendance_embed(thread.id, guild)
        
        attendance_view = AttendanceView(
            event_role_id=event_role.id if event_role else None,
            thread_id=thread.id
        )
        attendance_msg = await thread.send(embed=attendance_embed, view=attendance_view)
        await attendance_msg.pin()
        
        # Delete the "message pinned" system message
        async for message in thread.history(limit=5):
            if message.type == discord.MessageType.pins_add:
                try:
                    await message.delete()
                except:
                    pass
                break
        
        logger.info('Attendance message sent and pinned')
        
        # Save to database
        # For TBD events, use a far future date as placeholder
        db_date = parsed_date if not is_tbd else datetime(2099, 12, 31)
        await database.add_event(
            thread_id=thread.id,
            event_name=event_name,
            event_date=db_date,
            author_id=author.id,
            author_role_id=author_role.id,
            event_role_id=event_role.id if event_role else None,
            reminder_days=reminder_days if not is_tbd else 0
        )
        logger.info(f'Event saved to database - Thread ID: {thread.id} | TBD: {is_tbd}')
        
        # Ping everyone in main channel if requested
        if ping_everyone.value == 1:
            if is_tbd:
                ping_msg = await events_channel.send(
                    f"@everyone\n🎉 New event: **{event_name}** - Date TBD!\n"
                    f"Check out {thread.mention} to vote on the date!",
                    delete_after=57600  # 16 hours
                )
            else:
                ping_msg = await events_channel.send(
                    f"@everyone\n🎉 New event: **{event_name}** on {parsed_date.strftime('%B %d, %Y')}!\n"
                    f"Check out {thread.mention} for details!",
                    delete_after=57600  # 16 hours
                )
            logger.info(f'@everyone ping sent for event "{event_name}" (will delete after 16 hours)')
        
        # Keep the initial message so the thread remains visible in the channel
        # Don't delete it
        
        logger.info(f'✅ Event "{event_name}" created successfully!')
        logger.info(f'  Thread: {thread.name} (ID: {thread.id})')
        logger.info(f'  Author Role: {author_role.name} | Event Role: {event_role.name if event_role else "None"}')
        
        await interaction.followup.send(
            f"✅ Event created successfully! Check out {thread.mention}",
            ephemeral=True
        )
        
    except discord.Forbidden:
        logger.error(f'Permission denied when creating event "{event_name}"')
        await interaction.followup.send(
            "❌ I don't have permission to create threads or roles. Please check my permissions!",
            ephemeral=True
        )
    except Exception as e:
        logger.error(f'Error creating event "{event_name}": {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="ping",
    description="Notify participants or post update in main channel (Author only)"
)
async def ping_event(interaction: discord.Interaction):
    """Ping the event role in the main channel."""
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Log with context
        log_event_action('Ping event', interaction.user, interaction.guild, interaction.channel, event_info['event_name'])
        
        # Check if user is the author
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        if author_role not in interaction.user.roles:
            await interaction.followup.send(
                "❌ Only the event author can use this command!",
                ephemeral=True
            )
            return
        
        # Send ping in main events channel
        # Use the current channel if EVENTS_CHANNEL_ID is not set
        if EVENTS_CHANNEL_ID:
            events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
        else:
            events_channel = interaction.channel.parent if isinstance(interaction.channel, discord.Thread) else interaction.channel
        
        # Check if event has a role to ping
        mention_text = ""
        if event_info['event_role_id']:
            event_role = interaction.guild.get_role(event_info['event_role_id'])
            if event_role:
                mention_text = event_role.mention + "\n"
        
        ping_msg = await events_channel.send(
            f"{mention_text}"
            f"📢 **{event_info['event_name']}** - Check {interaction.channel.mention} for updates!"
        )
        logger.info(f'Event pinged for "{event_info["event_name"]}" by {interaction.user} (role: {"Yes" if mention_text else "No"})')
        
        # Respond immediately
        if mention_text:
            await interaction.followup.send(
                f"✅ Pinged event participants in {events_channel.mention}!",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                f"✅ Posted update in {events_channel.mention}! (No role to ping)",
                ephemeral=True
            )
        
        # Delete after 30 seconds to keep channel clean (in background)
        await asyncio.sleep(30)
        try:
            await ping_msg.delete()
            logger.info(f'Ping message deleted after 30s for "{event_info["event_name"]}"')
        except:
            pass
        
    except Exception as e:
        logger.error(f'Error in ping_event: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="pingeveryone",
    description="Ping @everyone for this event (Author only - use sparingly!)"
)
async def ping_everyone(interaction: discord.Interaction):
    """Ping @everyone for the event."""
    logger.info(f'Ping everyone requested by {interaction.user} in thread {interaction.channel.id}')
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        if author_role not in interaction.user.roles:
            await interaction.followup.send(
                "❌ Only the event author can use this command!",
                ephemeral=True
            )
            return
        
        # Send @everyone ping in main events channel
        # Use the current channel's parent if EVENTS_CHANNEL_ID is not set
        if EVENTS_CHANNEL_ID:
            events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
        else:
            events_channel = interaction.channel.parent if isinstance(interaction.channel, discord.Thread) else interaction.channel
        
        if not events_channel:
            await interaction.followup.send(
                "❌ Could not find the events channel!",
                ephemeral=True
            )
            return
        
        ping_msg = await events_channel.send(
            f"@everyone\n"
            f"📢 **{event_info['event_name']}** - Check {interaction.channel.mention} for updates!"
        )
        logger.info(f'@everyone pinged for "{event_info["event_name"]}" by {interaction.user}')
        
        # Respond immediately
        await interaction.followup.send(
            f"✅ Pinged @everyone in {events_channel.mention}!",
            ephemeral=True
        )
        
        # Delete after 30 seconds to keep channel clean (in background)
        await asyncio.sleep(30)
        try:
            await ping_msg.delete()
            logger.info(f'@everyone ping message deleted after 30s for "{event_info["event_name"]}"')
        except:
            pass
        
    except Exception as e:
        logger.error(f'Error in ping_everyone: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="finalize",
    description="Finalize the event date from poll results (Author only)"
)
@app_commands.describe(
    chosen_date="The final date for the event (YYYY-MM-DD HH:MM)"
)
async def finalize_date(interaction: discord.Interaction, chosen_date: str):
    """Finalize the event date after poll voting."""
    logger.info(f'Finalize date requested by {interaction.user} in thread {interaction.channel.id}')
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        if author_role not in interaction.user.roles:
            await interaction.followup.send(
                "❌ Only the event author can use this command!",
                ephemeral=True
            )
            return
        
        # Parse the chosen date
        try:
            parsed_date = parser.parse(chosen_date)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Invalid date format. Please use YYYY-MM-DD HH:MM or YYYY-MM-DD\nExample: 2026-02-15 18:00",
                ephemeral=True
            )
            return
        
        # Check if date is in the future
        if parsed_date < datetime.now():
            await interaction.followup.send(
                "❌ Event date must be in the future!",
                ephemeral=True
            )
            return
        
        # Update database with the finalized date
        async with aiosqlite.connect(database.DATABASE_PATH) as db:
            await db.execute(
                "UPDATE events SET event_date = ? WHERE thread_id = ?",
                (parsed_date.isoformat(), interaction.channel.id)
            )
            await db.commit()
        
        # Update thread name
        new_thread_name = f"📅 {event_info['event_name']} - {parsed_date.strftime('%Y-%m-%d')}"
        await interaction.channel.edit(name=new_thread_name)
        
        # Send announcement
        await interaction.channel.send(
            f"📅 **Date Finalized!**\n"
            f"The event date has been set to: **{parsed_date.strftime('%B %d, %Y at %I:%M %p')}**\n"
            f"Finalized by {interaction.user.mention}"
        )
        
        logger.info(f'Event "{event_info["event_name"]}" date finalized to {parsed_date}')
        
        await interaction.followup.send(
            f"✅ Event date finalized to {parsed_date.strftime('%B %d, %Y at %I:%M %p')}!",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f'Error in finalize_date: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="updatedate",
    description="Update the event date and time (Author only)"
)
@app_commands.describe(
    new_date="The new date for the event (YYYY-MM-DD HH:MM)",
    ping_participants="Notify participants about the date change?"
)
@app_commands.choices(ping_participants=[
    app_commands.Choice(name="Yes", value=1),
    app_commands.Choice(name="No", value=0)
])
async def update_date(interaction: discord.Interaction, new_date: str, ping_participants: app_commands.Choice[int] = None):
    """Update the event date and time."""
    await interaction.response.defer(ephemeral=True)
    
    # Get event info for logging
    event_info = await database.get_event_by_thread_id(interaction.channel.id)
    event_name = event_info['event_name'] if event_info else None
    log_event_action('Update date', interaction.user, interaction.guild, interaction.channel, event_name)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        if author_role not in interaction.user.roles:
            await interaction.followup.send(
                "❌ Only the event author can use this command!",
                ephemeral=True
            )
            return
        
        # Parse the new date
        try:
            parsed_date = parser.parse(new_date)
        except Exception as e:
            await interaction.followup.send(
                f"❌ Invalid date format. Please use YYYY-MM-DD HH:MM or YYYY-MM-DD\nExample: 2026-02-15 18:00",
                ephemeral=True
            )
            return
        
        # Check if date is in the future
        if parsed_date < datetime.now():
            await interaction.followup.send(
                "❌ Event date must be in the future!",
                ephemeral=True
            )
            return
        
        # Get old date for logging
        old_date = datetime.fromisoformat(event_info['event_date'])
        
        # Update database with the new date
        async with aiosqlite.connect(database.DATABASE_PATH) as db:
            await db.execute(
                "UPDATE events SET event_date = ?, reminder_sent = 0 WHERE thread_id = ?",
                (parsed_date.isoformat(), interaction.channel.id)
            )
            await db.commit()
        
        # Update thread name
        new_thread_name = f"📅 {event_info['event_name']} - {parsed_date.strftime('%Y-%m-%d')}"
        await interaction.channel.edit(name=new_thread_name)
        
        # Send announcement in thread
        await interaction.channel.send(
            f"📅 **Date Updated!**\n"
            f"The event date has been changed:\n"
            f"~~{old_date.strftime('%B %d, %Y at %I:%M %p')}~~ → **{parsed_date.strftime('%B %d, %Y at %I:%M %p')}**\n"
            f"Updated by {interaction.user.mention}"
        )
        
        # Ping participants if requested
        if ping_participants and ping_participants.value == 1:
            # Try to get events channel, fall back to thread parent
            if EVENTS_CHANNEL_ID and EVENTS_CHANNEL_ID != 0:
                events_channel = interaction.guild.get_channel(EVENTS_CHANNEL_ID)
            else:
                events_channel = interaction.channel.parent
            
            if events_channel:
                # If event role exists, ping it, otherwise just post message
                if event_info['event_role_id']:
                    event_role = interaction.guild.get_role(event_info['event_role_id'])
                    if event_role:
                        await events_channel.send(
                            f"{event_role.mention}\n📅 **Date Change:** {event_info['event_name']}\n"
                            f"New date: **{parsed_date.strftime('%B %d, %Y at %I:%M %p')}**\n"
                            f"See {interaction.channel.mention} for details!"
                        )
                        logger.info(f'Pinged {event_role.name} about date change')
                else:
                    await events_channel.send(
                        f"📅 **Date Change:** {event_info['event_name']}\n"
                        f"New date: **{parsed_date.strftime('%B %d, %Y at %I:%M %p')}**\n"
                        f"See {interaction.channel.mention} for details!"
                    )
                    logger.info(f'Posted date change announcement (no role to ping)')
        
        logger.info(f'Event "{event_info["event_name"]}" date updated from {old_date} to {parsed_date}')
        
        await interaction.followup.send(
            f"✅ Event date updated to {parsed_date.strftime('%B %d, %Y at %I:%M %p')}!",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f'Error in update_date: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="updatetitle",
    description="Update the event title/name (Author only)"
)
@app_commands.describe(
    new_title="The new title for the event"
)
async def update_title(interaction: discord.Interaction, new_title: str):
    """Update the event title/name."""
    logger.info(f'Update title requested by {interaction.user} in thread {interaction.channel.id}')
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        if author_role not in interaction.user.roles:
            await interaction.followup.send(
                "❌ Only the event author can use this command!",
                ephemeral=True
            )
            return
        
        # Get old title for logging
        old_title = event_info['event_name']
        
        # Update database with the new title
        async with aiosqlite.connect(database.DATABASE_PATH) as db:
            await db.execute(
                "UPDATE events SET event_name = ? WHERE thread_id = ?",
                (new_title, interaction.channel.id)
            )
            await db.commit()
        
        # Update thread name
        event_date = datetime.fromisoformat(event_info['event_date'])
        # Check if it's a TBD event (year 2099)
        if event_date.year == 2099:
            new_thread_name = f"📅 {new_title} - TBD (Poll Active)"
        else:
            new_thread_name = f"📅 {new_title} - {event_date.strftime('%Y-%m-%d')}"
        
        await interaction.channel.edit(name=new_thread_name)
        
        # Send announcement
        await interaction.channel.send(
            f"🏷️ **Title Updated!**\n"
            f"The event title has been changed:\n"
            f"~~{old_title}~~ → **{new_title}**\n"
            f"Updated by {interaction.user.mention}"
        )
        
        logger.info(f'Event title updated from "{old_title}" to "{new_title}"')
        
        await interaction.followup.send(
            f"✅ Event title updated to \"{new_title}\"!",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f'Error in update_title: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="cancel",
    description="Cancel the event and notify all participants (Author only)"
)
async def cancel_event(interaction: discord.Interaction):
    """Cancel an event and notify all participants."""
    logger.info(f'Cancel event requested by {interaction.user} in thread {interaction.channel.id}')
    await interaction.response.defer(ephemeral=True)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author or has admin permissions
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        is_author = author_role in interaction.user.roles
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_author or is_admin):
            await interaction.followup.send(
                "❌ Only the event author or administrators can cancel this event!",
                ephemeral=True
            )
            return
        
        guild = interaction.guild
        
        # Send cancellation notification in thread
        await interaction.channel.send(
            f"🚫 **EVENT CANCELLED**\n"
            f"This event has been cancelled by {interaction.user.mention}.\n"
            f"Participants have been notified. Event can be reopened with `/event reopen`."
        )
        
        # Ping participants in parent channel
        # Use the thread's parent channel if EVENTS_CHANNEL_ID is not set
        if EVENTS_CHANNEL_ID:
            events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
        else:
            events_channel = interaction.channel.parent if isinstance(interaction.channel, discord.Thread) else interaction.channel
        
        if events_channel:
            # Build mention text
            mention_text = ""
            
            # Add event role if exists
            if event_info['event_role_id']:
                event_role = guild.get_role(event_info['event_role_id'])
                if event_role:
                    mention_text = event_role.mention + "\n"
            
            cancel_msg = await events_channel.send(
                f"{mention_text}"
                f"🚫 **Event Cancelled: {event_info['event_name']}**\n"
                f"This event has been cancelled. Check {interaction.channel.mention} for details."
            )
            logger.info(f'Cancellation notification sent for "{event_info["event_name"]}"')
        
        # Mark as archived in database
        await database.archive_event(interaction.channel.id)
        logger.info(f'Event marked as cancelled/archived in database: "{event_info["event_name"]}"')
        
        # Keep all roles (author and event role) in case event is reopened
        # Don't remove anything
        
        logger.info(f'🚫 Event "{event_info["event_name"]}" cancelled by {interaction.user}')
        logger.info(f'All roles kept in case event is reopened')
        
        await interaction.followup.send(
            "✅ Event cancelled and participants notified! Thread remains visible for reference.",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f'Error in cancel_event: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="reopen",
    description="Reopen a cancelled event and become the new author"
)
async def reopen_event(interaction: discord.Interaction):
    """Reopen a cancelled event."""
    await interaction.response.defer(ephemeral=True)
    
    # Get event info for logging
    event_info = await database.get_event_by_thread_id(interaction.channel.id)
    event_name = event_info['event_name'] if event_info else None
    log_event_action('Reopen event', interaction.user, interaction.guild, interaction.channel, event_name)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if event is archived/cancelled
        if not event_info['archived']:
            await interaction.followup.send(
                "❌ This event is not cancelled! Use `/event close` to close it instead.",
                ephemeral=True
            )
            return
        
        guild = interaction.guild
        
        # Remove old author role from previous author
        old_author_role = guild.get_role(event_info['author_role_id'])
        if old_author_role:
            for member in old_author_role.members:
                await member.remove_roles(old_author_role)
            logger.info(f'Removed old author role from previous author(s)')
        
        # Assign author role to new person
        if old_author_role:
            await interaction.user.add_roles(old_author_role)
        
        # Update database to mark as not archived
        async with aiosqlite.connect(database.DATABASE_PATH) as db:
            await db.execute(
                "UPDATE events SET archived = 0, author_id = ? WHERE thread_id = ?",
                (interaction.user.id, interaction.channel.id)
            )
            await db.commit()
        
        # Send announcement
        await interaction.channel.send(
            f"♻️ **EVENT REOPENED**\n"
            f"This event has been reopened by {interaction.user.mention}.\n"
            f"{interaction.user.mention} is now the event author and can manage this event."
        )
        
        # Notify in parent channel
        if EVENTS_CHANNEL_ID:
            events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
        else:
            events_channel = interaction.channel.parent if isinstance(interaction.channel, discord.Thread) else interaction.channel
        
        if events_channel:
            # Build mention text
            mention_text = ""
            if event_info['event_role_id']:
                event_role = guild.get_role(event_info['event_role_id'])
                if event_role:
                    mention_text = event_role.mention + "\n"
            
            reopen_msg = await events_channel.send(
                f"{mention_text}"
                f"♻️ **Event Reopened: {event_info['event_name']}**\n"
                f"This event has been reopened! Check {interaction.channel.mention} for details."
            )
            logger.info(f'Reopen notification sent for "{event_info["event_name"]}"')
        
        logger.info(f'♻️ Event "{event_info["event_name"]}" reopened by {interaction.user}')
        
        await interaction.followup.send(
            f"✅ Event reopened! You are now the event author.",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f'Error in reopen_event: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="attendance",
    description="Resend attendance message with current stats (Author only)"
)
async def event_attendance(interaction: discord.Interaction):
    """Resend attendance message showing current attendance statistics."""
    await interaction.response.defer(ephemeral=True)
    
    # Get event info for logging
    event_info = await database.get_event_by_thread_id(interaction.channel.id) if isinstance(interaction.channel, discord.Thread) else None
    event_name = event_info['event_name'] if event_info else None
    log_event_action('Attendance command', interaction.user, interaction.guild, interaction.channel, event_name)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        if author_role not in interaction.user.roles:
            await interaction.followup.send(
                "❌ Only the event author can resend the attendance message!",
                ephemeral=True
            )
            return
        
        # Delete old attendance messages (look for messages with the View buttons)
        deleted_count = 0
        async for message in interaction.channel.history(limit=100):
            if message.author == bot.user and message.embeds:
                # Check if it's an attendance embed
                embed = message.embeds[0]
                if "Will you be attending?" in embed.title or "Event Attendance" in embed.title:
                    try:
                        await message.delete()
                        deleted_count += 1
                    except:
                        pass
        
        logger.info(f'Deleted {deleted_count} old attendance message(s)')
        
        # Build new attendance embed with current stats
        attendance_embed = await build_attendance_embed(interaction.channel.id, interaction.guild)
        
        # Create view with buttons
        attendance_view = AttendanceView(
            event_role_id=event_info['event_role_id'],
            thread_id=interaction.channel.id
        )
        
        # Send the new message
        attendance_msg = await interaction.channel.send(embed=attendance_embed, view=attendance_view)
        await attendance_msg.pin()
        
        # Delete the "message pinned" system message
        async for message in interaction.channel.history(limit=5):
            if message.type == discord.MessageType.pins_add:
                try:
                    await message.delete()
                except:
                    pass
                break
        
        await interaction.followup.send(
            f"✅ Attendance message updated! Deleted {deleted_count} old message(s).",
            ephemeral=True
        )
        logger.info(f'Attendance message resent by {interaction.user}')
    
    except Exception as e:
        logger.error(f'Error in event_attendance: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@event_group.command(
    name="help",
    description="Show all available event commands"
)
async def event_help(interaction: discord.Interaction):
    """Display help information for all event commands."""
    await interaction.response.defer(ephemeral=True)
    
    embed = discord.Embed(
        title="📋 Event Bot Commands",
        description="All commands start with `/event`",
        color=discord.Color.blue()
    )
    
    embed.add_field(
        name="📅 Event Creation",
        value="`/event create` - Create a new event with date/poll options",
        inline=False
    )
    
    embed.add_field(
        name="📢 Notifications",
        value=(
            "`/event ping` - Notify event participants\n"
            "`/event pingeveryone` - Ping @everyone in events channel\n"
            "`/event attendance` - Resend attendance message with current stats"
        ),
        inline=False
    )
    
    embed.add_field(
        name="✏️ Event Management",
        value=(
            "`/event updatedate` - Change the event date\n"
            "`/event updatetitle` - Change the event name\n"
            "`/event finalize` - Set final date (for TBD events)"
        ),
        inline=False
    )
    
    embed.add_field(
        name="🔧 Event Status",
        value=(
            "`/event cancel` - Cancel event (keeps roles for reopening)\n"
            "`/event reopen` - Reopen a cancelled event (anyone can do this)\n"
            "`/event close` - Close thread and remove all roles"
        ),
        inline=False
    )
    
    embed.set_footer(text="For detailed help on a specific command, use /event <command> and check the options")
    
    await interaction.followup.send(embed=embed, ephemeral=True)
    logger.info(f'{interaction.user} requested event help')


@event_group.command(
    name="close",
    description="Close the event thread (Author only)"
)
async def close_event(interaction: discord.Interaction):
    """Close and archive an event thread."""
    await interaction.response.defer(ephemeral=True)
    
    # Get event info for logging
    event_info = await database.get_event_by_thread_id(interaction.channel.id)
    event_name = event_info['event_name'] if event_info else None
    log_event_action('Close event', interaction.user, interaction.guild, interaction.channel, event_name)
    
    try:
        # Check if this is a thread
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.followup.send(
                "❌ This command can only be used in event threads!",
                ephemeral=True
            )
            return
        
        # Get event info from database
        event_info = await database.get_event_by_thread_id(interaction.channel.id)
        
        if not event_info:
            await interaction.followup.send(
                "❌ This thread is not associated with an event!",
                ephemeral=True
            )
            return
        
        # Check if user is the author or has admin permissions
        author_role = interaction.guild.get_role(event_info['author_role_id'])
        is_author = author_role in interaction.user.roles
        is_admin = interaction.user.guild_permissions.administrator
        
        if not (is_author or is_admin):
            await interaction.followup.send(
                "❌ Only the event author or administrators can close this event!",
                ephemeral=True
            )
            return
        
        # Mark as archived in database
        await database.archive_event(interaction.channel.id)
        logger.info(f'Event marked as archived in database: "{event_info["event_name"]}"')
        
        # Remove roles from all users and delete them
        guild = interaction.guild
        
        # Remove and delete author role
        author_role = guild.get_role(event_info['author_role_id'])
        if author_role:
            member_count = len(author_role.members)
            # Remove from all members who have it
            for member in author_role.members:
                await member.remove_roles(author_role)
            # Delete the role
            await author_role.delete(reason=f"Event closed: {event_info['event_name']}")
            logger.info(f'Author role deleted: {author_role.name} (removed from {member_count} member(s))')
        
        # Remove and delete event role
        if event_info['event_role_id']:
            event_role = guild.get_role(event_info['event_role_id'])
            if event_role:
                member_count = len(event_role.members)
                # Remove from all members who have it
                for member in event_role.members:
                    await member.remove_roles(event_role)
                # Delete the role
                await event_role.delete(reason=f"Event closed: {event_info['event_name']}")
                logger.info(f'Event role deleted: {event_role.name} (removed from {member_count} member(s))')
        
        # Send closing message
        await interaction.channel.send(
            f"🔒 **Event Closed**\n"
            f"This event has been closed by {interaction.user.mention}.\n"
            f"The thread will remain available for reference.\n"
            f"Event roles have been removed from all participants."
        )
        
        # Don't archive the thread - keep it visible for logs/lookback
        # Just mark it as closed in the database
        
        logger.info(f'✅ Event "{event_info["event_name"]}" closed successfully by {interaction.user}')
        
        await interaction.followup.send(
            "✅ Event closed! Thread remains visible for reference.",
            ephemeral=True
        )
        
    except Exception as e:
        logger.error(f'Error in close_event: {e}', exc_info=True)
        await interaction.followup.send(
            f"❌ An error occurred: {str(e)}",
            ephemeral=True
        )


@bot.event
async def on_raw_reaction_add(payload):
    """Handle reactions for role assignment (legacy - now using buttons)."""
    # Note: This is kept for backwards compatibility with old events that used reactions
    # New events use the attendance button view instead
    # Ignore bot reactions
    if payload.user_id == bot.user.id:
        return
    
    try:
        # Get event info
        event_info = await database.get_event_by_thread_id(payload.channel_id)
        if not event_info or not event_info['event_role_id']:
            return
        
        # Check if reaction is ✅
        if str(payload.emoji) != "✅":
            return
        
        # Get guild, member, and role
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        event_role = guild.get_role(event_info['event_role_id'])
        
        if member and event_role:
            await member.add_roles(event_role)
            logger.info(f'{member} joined event "{event_info["event_name"]}" (added role: {event_role.name} via reaction)')
            
            # Send confirmation in thread
            channel = bot.get_channel(payload.channel_id)
            try:
                await channel.send(
                    f"✅ {member.mention} joined the event!",
                    delete_after=10
                )
            except:
                pass
                
    except Exception as e:
        logger.error(f"Error in on_raw_reaction_add: {e}")


@bot.event
async def on_raw_reaction_remove(payload):
    """Handle reaction removal for role removal (legacy - now using buttons)."""
    # Note: This is kept for backwards compatibility with old events that used reactions
    try:
        # Get event info
        event_info = await database.get_event_by_thread_id(payload.channel_id)
        if not event_info or not event_info['event_role_id']:
            return
        
        # Check if reaction is ✅
        if str(payload.emoji) != "✅":
            return
        
        # Get guild, member, and role
        guild = bot.get_guild(payload.guild_id)
        member = guild.get_member(payload.user_id)
        event_role = guild.get_role(event_info['event_role_id'])
        
        if member and event_role:
            await member.remove_roles(event_role)
            logger.info(f'{member} left event "{event_info["event_name"]}" (removed role: {event_role.name} via reaction)')
                
    except Exception as e:
        logger.error(f"Error in on_raw_reaction_remove: {e}")


@tasks.loop(hours=1)
async def check_reminders():
    """Check for events that need reminders."""
    logger.info('Running reminder check...')
    try:
        events = await database.get_events_needing_reminders()
        logger.info(f'Found {len(events)} event(s) with pending reminders')
        
        for event in events:
            event_date = datetime.fromisoformat(event['event_date'])
            reminder_date = event_date - timedelta(days=event['reminder_days'])
            
            # Check if it's time to send the reminder
            if datetime.now() >= reminder_date:
                # Get thread and send reminder
                thread = bot.get_channel(event['thread_id'])
                if thread:
                    # Prepare mention
                    mention_text = ""
                    if event['event_role_id']:
                        role = thread.guild.get_role(event['event_role_id'])
                        if role:
                            mention_text = role.mention
                    
                    await thread.send(
                        f"{mention_text}\n"
                        f"⏰ **Reminder!**\n"
                        f"The event **{event['event_name']}** is happening in {event['reminder_days']} day(s)!\n"
                        f"📅 {event_date.strftime('%B %d, %Y at %I:%M %p')}"
                    )
                    logger.info(f'⏰ Reminder sent for "{event["event_name"]}" ({event["reminder_days"]} days before)')
                    
                    # Also send reminder in main events channel
                    events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
                    if events_channel:
                        reminder_msg = await events_channel.send(
                            f"{mention_text}\n"
                            f"⏰ Reminder: **{event['event_name']}** is in {event['reminder_days']} day(s)!\n"
                            f"Check {thread.mention} for details!"
                        )
                        await asyncio.sleep(60)
                        await reminder_msg.delete()
                        logger.info(f'Reminder ping sent and deleted in main channel for "{event["event_name"]}"')
                
                # Mark reminder as sent
                await database.mark_reminder_sent(event['thread_id'])
                
    except Exception as e:
        logger.error(f"Error in check_reminders: {e}", exc_info=True)


@tasks.loop(hours=6)
async def cleanup_old_events():
    """Clean up events that have passed - remove roles and mark as archived."""
    logger.info('Running cleanup for past events...')
    try:
        past_events = await database.get_past_events()
        logger.info(f'Found {len(past_events)} past event(s) to clean up')
        
        for event in past_events:
            event_date = datetime.fromisoformat(event['event_date'])
            # Clean up 1 day after the event
            if datetime.now() > event_date + timedelta(days=1):
                thread = bot.get_channel(event['thread_id'])
                if thread:
                    # Remove roles from all users and delete them
                    guild = thread.guild
                    
                    # Remove and delete author role
                    author_role = guild.get_role(event['author_role_id'])
                    if author_role:
                        member_count = len(author_role.members)
                        for member in author_role.members:
                            await member.remove_roles(author_role)
                        await author_role.delete(reason=f"Event completed: {event['event_name']}")
                        logger.info(f'Cleaned up author role for "{event["event_name"]}" (removed from {member_count} member(s))')
                    
                    # Remove and delete event role
                    if event['event_role_id']:
                        event_role = guild.get_role(event['event_role_id'])
                        if event_role:
                            member_count = len(event_role.members)
                            for member in event_role.members:
                                await member.remove_roles(event_role)
                            await event_role.delete(reason=f"Event completed: {event['event_name']}")
                            logger.info(f'Cleaned up event role for "{event["event_name"]}" (removed from {member_count} member(s))')
                    
                    await thread.send(
                        "📅 **Event Completed**\n"
                        "This event has passed. Event roles have been removed from all participants.\n"
                        "Thank you for participating! 🎉"
                    )
                    logger.info(f'📅 Event "{event["event_name"]}" cleaned up - date was {event["event_date"]}')
                
                await database.archive_event(event['thread_id'])
                
    except Exception as e:
        logger.error(f"Error in cleanup_old_events: {e}", exc_info=True)


@tasks.loop(minutes=30)
async def cleanup_non_thread_messages():
    """Delete non-thread messages from the events channel."""
    logger.info('Running non-thread message cleanup...')
    try:
        events_channel = bot.get_channel(EVENTS_CHANNEL_ID)
        if not events_channel:
            return
        
        # Get messages from the last hour
        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        deleted_count = 0
        
        async for message in events_channel.history(limit=50, after=one_hour_ago):
            # Don't delete thread starter messages or bot messages that are recent
            if message.type not in [discord.MessageType.default, discord.MessageType.reply]:
                continue
            
            # Check if message has a thread
            if not message.thread:
                # Delete messages older than 5 minutes
                if datetime.now(timezone.utc) - message.created_at > timedelta(minutes=5):
                    try:
                        await message.delete()
                        deleted_count += 1
                    except:
                        pass
        
        if deleted_count > 0:
            logger.info(f'Deleted {deleted_count} non-thread message(s) from events channel')
                        
    except Exception as e:
        logger.error(f"Error in cleanup_non_thread_messages: {e}", exc_info=True)


# Run the bot
if __name__ == "__main__":
    if not TOKEN:
        logger.error("DISCORD_TOKEN not found in .env file!")
        logger.error("Please create a .env file with your bot token")
    else:
        logger.info("Starting Discord Event Bot...")
        if GUILD_ID:
            logger.info(f"Primary Guild ID: {GUILD_ID}")
        else:
            logger.info("Working on all servers (GUILD_ID not set)")
        
        if EVENTS_CHANNEL_ID:
            logger.info(f"Events Channel ID: {EVENTS_CHANNEL_ID}")
        else:
            logger.info("Events can be created in any channel (EVENTS_CHANNEL_ID not set)")
        
        # Add command group to bot tree
        bot.tree.add_command(event_group)
        
        try:
            bot.run(TOKEN)
        except KeyboardInterrupt:
            logger.info("Bot stopped by user")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
