import os
import re
import sqlite3
import ast
import operator
import asyncio
import random
import string
from urllib.parse import urlparse
from datetime import datetime, timezone
from typing import Literal, Optional

import discord  # type: ignore[import-not-found]
from discord.ext import commands
from discord import app_commands

try:
	import google.generativeai as genai  # type: ignore[import-not-found]
except ImportError:
	genai = None

try:
	import aiohttp  # type: ignore[import-not-found]
except ImportError:
	aiohttp = None

try:
	from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:
	def load_dotenv(*args, **kwargs):
		return False

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"), override=False)


def env_int(name):
	try:
		return int(os.getenv(name, "0"))
	except ValueError:
		return 0


TOKEN = os.getenv("DISCORD_TOKEN", "")
SUPPORT_ROLE_ID = env_int("SUPPORT_ROLE_ID")
TICKET_CATEGORY_ID = env_int("TICKET_CATEGORY_ID")
SUGGESTION_CHANNEL_ID = env_int("SUGGESTION_CHANNEL_ID")
CONFESSION_REVIEW_CHANNEL_ID = env_int("CONFESSION_REVIEW_CHANNEL_ID")
CONFESSION_CHANNEL_ID = env_int("CONFESSION_CHANNEL_ID")
COUNTING_CHANNEL_ID = env_int("COUNTING_CHANNEL_ID")
VOICE_HUB_CHANNEL_ID = env_int("VOICE_HUB_CHANNEL_ID")
MEDIA_CHANNEL_IDS = {env_int(value) for value in os.getenv("MEDIA_CHANNEL_IDS", "").split(",") if value.strip().isdigit()}
SAFE_DOMAINS = {value.strip().lower() for value in os.getenv("SAFE_DOMAINS", "").split(",") if value.strip()}
BLOCKED_DOMAINS = {value.strip().lower() for value in os.getenv("BLOCKED_DOMAINS", "").split(",") if value.strip()}
GOOGLE_SAFE_BROWSING_KEY = os.getenv("GOOGLE_SAFE_BROWSING_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
AI_MODEL = os.getenv("AI_MODEL", "gemini-3.6-flash")
XP_PER_MESSAGE = max(1, env_int("XP_PER_MESSAGE") or 10)
DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ticket_bot.sqlite3")
MEDIA_LINK_HOSTS = {"youtube.com", "youtu.be", "imgur.com", "i.imgur.com", "tenor.com", "media.tenor.com"}
GAME_COMMANDS = {"tic-tac-toe", "rps", "roulette", "trivia", "guess", "hangman", "connect-four", "wordle", "slot", "coinflip", "roll", "blackjack", "unscramble", "emoji-quiz", "truth-or-dare", "high-low", "minefield", "pokemon-guess", "math-race", "explore"}

CATEGORIES = {
	"store": ("Store / Purchase Rank", "Minecraft IGN and proof or order links."),
	"minecraft": ("Minecraft Issue / Bug", "Minecraft IGN, server version, and a detailed issue."),
	"technical": ("Technical Support", "A detailed description and any relevant links."),
	"discord": ("Discord Support", "A detailed description and screenshots or links."),
	"report": ("Report Player / Appeal", "Minecraft IGN, reported player, and evidence links."),
	"vip": ("VIP Support", "Minecraft IGN and a detailed VIP-related request."),
}

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix="!", intents=intents)


def db(query, args=(), fetch=False, many=False):
	with sqlite3.connect(DB) as con:
		cur = con.cursor()
		if many:
			cur.executemany(query, args)
		else:
			cur.execute(query, args)
		rows = cur.fetchall() if fetch else None
		con.commit()
		return rows


def init_db():
	db("CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, balance INTEGER NOT NULL DEFAULT 100)")
	db("CREATE TABLE IF NOT EXISTS items (name TEXT PRIMARY KEY, price INTEGER NOT NULL, description TEXT NOT NULL)")
	db("""CREATE TABLE IF NOT EXISTS tickets (
		guild_id INTEGER NOT NULL,
		user_id INTEGER NOT NULL,
		category TEXT NOT NULL,
		channel_id INTEGER NOT NULL,
		created_at TEXT NOT NULL,
		PRIMARY KEY (guild_id, user_id, category)
	)""")
	db("CREATE TABLE IF NOT EXISTS suggestions (message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, author_id INTEGER NOT NULL, content TEXT NOT NULL, upvotes INTEGER NOT NULL DEFAULT 0, downvotes INTEGER NOT NULL DEFAULT 0, status TEXT NOT NULL DEFAULT 'pending')")
	db("CREATE TABLE IF NOT EXISTS suggestion_votes (message_id INTEGER NOT NULL, user_id INTEGER NOT NULL, vote INTEGER NOT NULL, PRIMARY KEY(message_id, user_id))")
	db("CREATE TABLE IF NOT EXISTS suggestion_config (guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL)")
	db("CREATE TABLE IF NOT EXISTS game_config (guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL)")
	db("CREATE TABLE IF NOT EXISTS member_xp (guild_id INTEGER NOT NULL, user_id INTEGER NOT NULL, xp INTEGER NOT NULL DEFAULT 0, PRIMARY KEY(guild_id, user_id))")
	db("CREATE TABLE IF NOT EXISTS counting (guild_id INTEGER PRIMARY KEY, channel_id INTEGER NOT NULL, last_number INTEGER NOT NULL DEFAULT 0, last_user_id INTEGER)")
	db("CREATE TABLE IF NOT EXISTS confessions (message_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, content TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'pending')")
	db("CREATE TABLE IF NOT EXISTS temporary_voice (channel_id INTEGER PRIMARY KEY, guild_id INTEGER NOT NULL, owner_id INTEGER NOT NULL)")
	db("CREATE TABLE IF NOT EXISTS media_only_channels (guild_id INTEGER NOT NULL, channel_id INTEGER NOT NULL, enabled INTEGER NOT NULL DEFAULT 1, PRIMARY KEY(guild_id, channel_id))")
	if not db("SELECT name FROM items", fetch=True):
		db("INSERT INTO items VALUES (?, ?, ?)", [
			("VIP", 500, "VIP server role"),
			("Custom Role", 1000, "A custom color role"),
			("Mystery Box", 250, "A surprise reward"),
		], many=True)


def balance(user_id):
	db("INSERT OR IGNORE INTO users(id) VALUES (?)", (user_id,))
	return db("SELECT balance FROM users WHERE id=?", (user_id,), True)[0][0] # type: ignore


async def game_channel_check(interaction: discord.Interaction):
	if interaction.guild is None:
		return True
	row = db("SELECT channel_id FROM game_config WHERE guild_id=?", (interaction.guild.id,), True)
	if not row or row[0][0] == interaction.channel_id:
		return True
	await interaction.response.send_message("Games can only be used in the configured game channel.", ephemeral=True)
	return False


def ticket_name(user: discord.abc.User, category: str):
	username = re.sub(r"[^a-z0-9-]", "-", user.name.lower()).strip("-")[:24] or str(user.id)
	return f"ticket-{username}-{category}"


class TicketModal(discord.ui.Modal):
	def __init__(self, category):
		super().__init__(title=f"{CATEGORIES[category][0]} details", timeout=300)
		self.category = category
		self.minecraft_ign = discord.ui.TextInput(label="Minecraft IGN", placeholder="Your in-game name", required=category in {"store", "minecraft", "report", "vip"}, max_length=32)
		self.details = discord.ui.TextInput(label="Describe the issue", style=discord.TextStyle.paragraph, placeholder=CATEGORIES[category][1], max_length=2000)
		self.links = discord.ui.TextInput(label="Proof or relevant links", required=False, max_length=1000)
		self.add_item(self.minecraft_ign)
		self.add_item(self.details)
		self.add_item(self.links)

	async def on_submit(self, interaction: discord.Interaction):
		await create_ticket(interaction, self.category, self.minecraft_ign.value, self.details.value, self.links.value)

	async def on_error(self, interaction: discord.Interaction, error):
		print(f"Ticket modal error: {error!r}")
		message = "The ticket form could not be submitted. Please try again."
		if interaction.response.is_done():
			await interaction.followup.send(message, ephemeral=True)
		else:
			await interaction.response.send_message(message, ephemeral=True)


async def create_ticket(interaction, category, minecraft_ign, details, links):
	guild = interaction.guild
	if guild is None:
		return await interaction.response.send_message("Tickets can only be opened in a server.", ephemeral=True)
	await interaction.response.defer(ephemeral=True)
	row = db("SELECT channel_id FROM tickets WHERE guild_id=? AND user_id=? AND category=?", (guild.id, interaction.user.id, category), True)
	if row:
		channel = guild.get_channel(row[0])
		if channel:
			return await interaction.followup.send(f"You already have {channel.mention} for this category.", ephemeral=True)
		db("DELETE FROM tickets WHERE guild_id=? AND user_id=? AND category=?", (guild.id, interaction.user.id, category))
	overwrites = {
		guild.default_role: discord.PermissionOverwrite(view_channel=False),
		interaction.user: discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True),
		guild.me: discord.PermissionOverwrite(view_channel=True, send_messages=True, manage_channels=True),
	}
	if SUPPORT_ROLE_ID and (role := guild.get_role(SUPPORT_ROLE_ID)):
		overwrites[role] = discord.PermissionOverwrite(view_channel=True, send_messages=True, read_message_history=True)
	category_channel = guild.get_channel(TICKET_CATEGORY_ID) if TICKET_CATEGORY_ID else None
	channel = None
	try:
		channel = await guild.create_text_channel(ticket_name(interaction.user, category), category=category_channel if isinstance(category_channel, discord.CategoryChannel) else None, overwrites=overwrites, reason="Ticket created")
		db("INSERT INTO tickets VALUES (?, ?, ?, ?, ?)", (guild.id, interaction.user.id, category, channel.id, datetime.now(timezone.utc).isoformat()))
		embed = discord.Embed(title=f"{CATEGORIES[category][0]} ticket", color=discord.Color.green())
		embed.add_field(name="Minecraft IGN", value=minecraft_ign or "Not provided", inline=True)
		embed.add_field(name="Details", value=details, inline=False)
		if links:
			embed.add_field(name="Proof / links", value=links, inline=False)
		await channel.send(f"{interaction.user.mention} {f'<@&{SUPPORT_ROLE_ID}>' if SUPPORT_ROLE_ID else ''}", embed=embed, view=CloseTicketView())
		await interaction.followup.send(f"Ticket created: {channel.mention}", ephemeral=True)
	except (discord.HTTPException, sqlite3.Error):
		if channel:
			await channel.delete(reason="Ticket setup failed")
		await interaction.followup.send("I could not create that ticket. Check my channel permissions and try again.", ephemeral=True)


class TicketView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.select(placeholder="Choose a support category...", custom_id="ticket:category", options=[discord.SelectOption(label=label, value=value, description=description) for value, (label, description) in CATEGORIES.items()])
	async def select_category(self, interaction: discord.Interaction, select: discord.ui.Select):
		await interaction.response.send_modal(TicketModal(select.values[0]))

	@discord.ui.button(label="Open Store Ticket", emoji="🛒", style=discord.ButtonStyle.green, custom_id="ticket:store")
	async def store_ticket(self, interaction, button):
		await interaction.response.send_modal(TicketModal("store"))

	@discord.ui.button(label="Open Support Ticket", emoji="🎫", style=discord.ButtonStyle.blurple, custom_id="ticket:support")
	async def support_ticket(self, interaction, button):
		await interaction.response.send_message(view=CategoryButtonView(), ephemeral=True)


class CategoryButtonView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=120)
		for key, (label, _) in CATEGORIES.items():
			button = discord.ui.Button(label=label, style=discord.ButtonStyle.secondary, custom_id=f"ticket:category:{key}")
			button.callback = self.make_callback(key)
			self.add_item(button)

	def make_callback(self, category):
		async def callback(interaction):
			await interaction.response.send_modal(TicketModal(category))
		return callback


class SuggestionView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	async def vote(self, interaction, value):
		row = db("SELECT upvotes, downvotes FROM suggestions WHERE message_id=?", (interaction.message.id,), True)
		if not row:
			return await interaction.response.send_message("Suggestion not found.", ephemeral=True)
		old = db("SELECT vote FROM suggestion_votes WHERE message_id=? AND user_id=?", (interaction.message.id, interaction.user.id), True)
		if old and old[0][0] == value:
			return await interaction.response.send_message("You already selected that vote.", ephemeral=True)
		if old:
			db("UPDATE suggestion_votes SET vote=? WHERE message_id=? AND user_id=?", (value, interaction.message.id, interaction.user.id))
			db("UPDATE suggestions SET upvotes=upvotes+?, downvotes=downvotes+? WHERE message_id=?", (-1 if value == -1 else 1, 1 if value == -1 else -1, interaction.message.id))
		else:
			db("INSERT INTO suggestion_votes VALUES (?, ?, ?)", (interaction.message.id, interaction.user.id, value))
			db("UPDATE suggestions SET upvotes=upvotes+?, downvotes=downvotes+? WHERE message_id=?", (1 if value == 1 else 0, 1 if value == -1 else 0, interaction.message.id))
		counts = db("SELECT upvotes, downvotes FROM suggestions WHERE message_id=?", (interaction.message.id,), True)[0] # type: ignore
		embed = interaction.message.embeds[0]
		if embed.fields:
			embed.set_field_at(0, name="Community interest", value=f"👍 {counts[0]} | 👎 {counts[1]}", inline=False)
		else:
			embed.add_field(name="Community interest", value=f"👍 {counts[0]} | 👎 {counts[1]}", inline=False)
		await interaction.message.edit(embed=embed)
		await interaction.response.send_message("Vote recorded.", ephemeral=True)

	@discord.ui.button(label="Upvote", emoji="👍", style=discord.ButtonStyle.green, custom_id="suggestion:up")
	async def upvote(self, interaction, button):
		await self.vote(interaction, 1)

	@discord.ui.button(label="Downvote", emoji="👎", style=discord.ButtonStyle.red, custom_id="suggestion:down")
	async def downvote(self, interaction, button):
		await self.vote(interaction, -1)

	async def moderate(self, interaction, approved):
		if not interaction.user.guild_permissions.manage_guild:
			return await interaction.response.send_message("Staff only.", ephemeral=True)
		row = db("SELECT author_id FROM suggestions WHERE message_id=? AND status='pending'", (interaction.message.id,), True)
		if not row:
			return await interaction.response.send_message("This suggestion was already reviewed.", ephemeral=True)
		status = "approved" if approved else "rejected"
		db("UPDATE suggestions SET status=? WHERE message_id=?", (status, interaction.message.id))
		embed = interaction.message.embeds[0] if interaction.message.embeds else discord.Embed(title="Community suggestion")
		embed.color = discord.Color.green() if approved else discord.Color.red()
		embed.set_footer(text=f"Suggestion {status} by {interaction.user.display_name}")
		await interaction.message.edit(embed=embed, view=None)
		user = interaction.guild.get_member(row[0][0])
		if user:
			try:
				await user.send(f"Your suggestion in **{interaction.guild.name}** was {status}.")
			except discord.HTTPException:
				pass
		await interaction.response.send_message(f"Suggestion {status}.", ephemeral=True)

	@discord.ui.button(label="Approve", style=discord.ButtonStyle.secondary, custom_id="suggestion:approve", row=1)
	async def approve(self, interaction, button):
		await self.moderate(interaction, True)

	@discord.ui.button(label="Reject", style=discord.ButtonStyle.secondary, custom_id="suggestion:reject", row=1)
	async def reject(self, interaction, button):
		await self.moderate(interaction, False)


class ConfessionModal(discord.ui.Modal, title="Anonymous confession"):
	content = discord.ui.TextInput(label="Confession", style=discord.TextStyle.paragraph, max_length=2000)

	async def on_submit(self, interaction):
		if interaction.guild is None:
			return await interaction.response.send_message("Confessions can only be submitted in a server.", ephemeral=True)
		channel = interaction.guild.get_channel(CONFESSION_REVIEW_CHANNEL_ID)
		if not channel:
			return await interaction.response.send_message("Confession review is not configured.", ephemeral=True)
		message = await channel.send(embed=discord.Embed(title="Confession pending review", description=self.content.value, color=discord.Color.orange()), view=ConfessionView())
		db("INSERT INTO confessions VALUES (?, ?, ?, 'pending')", (message.id, interaction.guild.id, self.content.value))
		await interaction.response.send_message("Your confession was sent to staff for review.", ephemeral=True)


class ConfessionView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	async def review(self, interaction, approved):
		if not interaction.user.guild_permissions.manage_guild:
			return await interaction.response.send_message("Staff only.", ephemeral=True)
		row = db("SELECT content FROM confessions WHERE message_id=? AND status='pending'", (interaction.message.id,), True)
		if not row:
			return await interaction.response.send_message("This confession was already reviewed.", ephemeral=True)
		channel = interaction.guild.get_channel(CONFESSION_CHANNEL_ID) if approved and interaction.guild else None
		if approved and not channel:
			return await interaction.response.send_message("The public confessions channel is not configured.", ephemeral=True)
		status = "approved" if approved else "rejected"
		db("UPDATE confessions SET status=? WHERE message_id=?", (status, interaction.message.id))
		if approved:
			assert channel is not None
			await channel.send(embed=discord.Embed(title="Anonymous confession", description=row[0][0], color=discord.Color.blurple()))
		await interaction.message.edit(view=None)
		await interaction.response.send_message(f"Confession {status}.", ephemeral=True)

	@discord.ui.button(label="Approve", style=discord.ButtonStyle.green, custom_id="confession:approve")
	async def approve(self, interaction, button):
		await self.review(interaction, True)

	@discord.ui.button(label="Reject", style=discord.ButtonStyle.red, custom_id="confession:reject")
	async def reject(self, interaction, button):
		await self.review(interaction, False)


class RoleView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)
		options = []
		for item in os.getenv("REACTION_ROLES", "").split(","):
			if ":" in item:
				label, role_id = item.split(":", 1)
				options.append(discord.SelectOption(label=label.strip(), value=role_id.strip()))
		if options:
			select = discord.ui.Select(placeholder="Choose a role...", options=options[:25], custom_id="roles:select")
			select.callback = self.role_callback
			self.add_item(select)

	async def role_callback(self, interaction):
		if interaction.guild is None:
			return await interaction.response.send_message("Roles can only be changed in a server.", ephemeral=True)
		select = interaction.data.get("values", [""])[0]
		try:
			role_id = int(select)
		except (TypeError, ValueError):
			return await interaction.response.send_message("That role selection is invalid.", ephemeral=True)
		role = interaction.guild.get_role(role_id)
		if not role or role.is_default() or interaction.guild.me is None or role >= interaction.guild.me.top_role:
			return await interaction.response.send_message("That role is unavailable.", ephemeral=True)
		if role in interaction.user.roles:
			await interaction.user.remove_roles(role)
			message = f"Removed {role.name}."
		else:
			await interaction.user.add_roles(role)
			message = f"Added {role.name}."
		await interaction.response.send_message(message, ephemeral=True)


class CloseTicketView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="ticket:close")
	async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not interaction.channel or not interaction.channel.name.startswith("ticket-"): # type: ignore
			return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
		db("DELETE FROM tickets WHERE channel_id=?", (interaction.channel.id,))
		await interaction.response.send_message("Closing ticket in 5 seconds...")
		await asyncio.sleep(5)
		await interaction.channel.delete(reason=f"Closed by {interaction.user}") # type: ignore


class ShopView(discord.ui.View):
	@discord.ui.button(label="Shop", emoji="🛒", style=discord.ButtonStyle.blurple)
	async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
		rows = db("SELECT name, price, description FROM items", fetch=True)
		embed = discord.Embed(title="🛒 Shop", color=discord.Color.blurple())
		embed.description = "\n".join(f"**{n}** — {p} coins\n{d}\n`!buy {n}`" for n, p, d in rows) # type: ignore
		await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
	init_db()
	if not getattr(bot, "_persistent_views_added", False):
		bot.add_view(TicketView())
		bot.add_view(CloseTicketView())
		bot.add_view(SuggestionView())
		bot.add_view(ConfessionView())
		if os.getenv("REACTION_ROLES"):
			bot.add_view(RoleView())
		bot._persistent_views_added = True # type: ignore
	if not getattr(bot, "_commands_synced", False):
		await bot.tree.sync()
		bot._commands_synced = True # type: ignore
	print(f"Logged in as {bot.user}")


@bot.tree.command(name="setup-ticket", description="Post the support ticket panel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_ticket(interaction: discord.Interaction):
	embed = discord.Embed(
		title="🎫 Support Tickets",
		description="Choose a category below. A short form will collect the details before your private ticket opens.",
		color=discord.Color.green(),
	)
	await interaction.response.send_message(embed=embed, view=TicketView())


@setup_ticket.error
async def setup_ticket_error(interaction: discord.Interaction, error):
	message = "You do not have permission to use this command." if isinstance(error, app_commands.errors.MissingPermissions) else "The ticket panel could not be posted. Check the bot console."
	if interaction.response.is_done():
		await interaction.followup.send(message, ephemeral=True)
	else:
		await interaction.response.send_message(message, ephemeral=True)


@bot.tree.command(name="audit", description="Scan roles and bots for common security risks")
@app_commands.checks.has_permissions(administrator=True)
async def audit(interaction: discord.Interaction):
	await interaction.response.defer(ephemeral=True)
	risks = []
	for role in interaction.guild.roles: # type: ignore
		if role.permissions.administrator:
			owner = "@everyone" if role.is_default() else role.mention
			risks.append(f"Administrator permission: {owner}")
		elif role.permissions.manage_guild or role.permissions.manage_channels or role.permissions.manage_roles:
			risks.append(f"Elevated management permission: {role.mention}")
	for member in interaction.guild.members: # type: ignore
		if member.bot and not getattr(member.public_flags, "verified_bot", False):
			risks.append(f"Bot not marked verified: {member.mention} ({member.id})")
	description = "\n".join(f"• {risk}" for risk in risks)[:3900] if risks else "No common role or bot risks detected."
	embed = discord.Embed(title="Server security audit", description=description, color=discord.Color.orange() if risks else discord.Color.green())
	embed.set_footer(text="Review findings manually before changing permissions.")
	await interaction.followup.send(embed=embed, ephemeral=True)


@bot.tree.command(name="mediaonly", description="Enable or disable media-only enforcement")
@app_commands.checks.has_permissions(manage_channels=True)
async def mediaonly(interaction: discord.Interaction, channel: discord.TextChannel, status: Literal["enable", "disable"]):
	enabled = 1 if status == "enable" else 0
	db("INSERT INTO media_only_channels(guild_id, channel_id, enabled) VALUES (?, ?, ?) ON CONFLICT(guild_id, channel_id) DO UPDATE SET enabled=excluded.enabled", (interaction.guild.id, channel.id, enabled)) # type: ignore
	await interaction.response.send_message(f"Media-only mode {status}d for {channel.mention}.", ephemeral=True)


class SuggestionCommandModal(discord.ui.Modal, title="New suggestion"):
	def __init__(self, channel: Optional[discord.TextChannel] = None):
		super().__init__()
		self.channel = channel

	content = discord.ui.TextInput(label="Suggestion", style=discord.TextStyle.paragraph, max_length=2000)

	async def on_submit(self, interaction):
		if interaction.guild is None:
			return await interaction.response.send_message("Suggestions can only be submitted in a server.", ephemeral=True)
		channel = self.channel
		if channel is None:
			configured_row = db("SELECT channel_id FROM suggestion_config WHERE guild_id=?", (interaction.guild.id,), True)
			configured_id = configured_row[0][0] if configured_row else SUGGESTION_CHANNEL_ID
			configured_channel = interaction.guild.get_channel(configured_id) if configured_id else None
			channel = configured_channel if isinstance(configured_channel, discord.TextChannel) else None
		if channel is None and isinstance(interaction.channel, discord.TextChannel):
			channel = interaction.channel
		if channel is None:
			return await interaction.response.send_message("The suggestion channel is not configured.", ephemeral=True)
		embed = discord.Embed(title="Community suggestion", description=self.content.value, color=discord.Color.blurple())
		embed.set_footer(text=f"Suggested by {interaction.user}")
		message = await channel.send(embed=embed, view=SuggestionView())
		db("INSERT INTO suggestions(message_id, guild_id, author_id, content) VALUES (?, ?, ?, ?)", (message.id, interaction.guild.id, interaction.user.id, self.content.value))
		await interaction.response.send_message(f"Suggestion posted in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="setup-suggestion-channel", description="Set the channel where suggestions are posted")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel="Text channel to receive suggestions")
async def setup_suggestion_channel(interaction: discord.Interaction, channel: discord.TextChannel):
	if interaction.guild is None:
		return await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
	bot_member = interaction.guild.me
	if bot_member is None:
		return await interaction.response.send_message("I could not verify my permissions in that channel.", ephemeral=True)
	permissions = channel.permissions_for(bot_member)
	if not permissions.send_messages or not permissions.embed_links:
		return await interaction.response.send_message("I need Send Messages and Embed Links permission in that channel.", ephemeral=True)
	db("INSERT INTO suggestion_config(guild_id, channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id", (interaction.guild.id, channel.id))
	await interaction.response.send_message(f"Suggestions will now be posted in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="setup-game-channel", description="Set the channel where games can be played")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.describe(channel="Text channel where game commands are allowed")
async def setup_game_channel(interaction: discord.Interaction, channel: discord.TextChannel):
	if interaction.guild is None:
		return await interaction.response.send_message("This command can only be used in a server.", ephemeral=True)
	bot_member = interaction.guild.me
	if bot_member is None:
		return await interaction.response.send_message("I could not verify my permissions in that channel.", ephemeral=True)
	permissions = channel.permissions_for(bot_member)
	if not permissions.send_messages:
		return await interaction.response.send_message("I need Send Messages permission in that channel.", ephemeral=True)
	db("INSERT INTO game_config(guild_id, channel_id) VALUES (?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id", (interaction.guild.id, channel.id))
	await interaction.response.send_message(f"Games can now only be used in {channel.mention}.", ephemeral=True)


@bot.tree.command(name="suggest", description="Submit a community suggestion")
@app_commands.describe(channel="Optional destination channel; administrators can choose any text channel")
async def suggest(interaction: discord.Interaction, channel: Optional[discord.TextChannel] = None):
	if interaction.guild is None:
		return await interaction.response.send_message("Suggestions can only be submitted in a server.", ephemeral=True)
	if channel is not None and not interaction.user.guild_permissions.administrator: # type: ignore
		return await interaction.response.send_message("Only administrators can choose a suggestion channel.", ephemeral=True)
	await interaction.response.send_modal(SuggestionCommandModal(channel))


@bot.tree.command(name="confess", description="Submit an anonymous confession for staff review")
async def confess(interaction: discord.Interaction):
	await interaction.response.send_modal(ConfessionModal())


def rank_roles(guild):
	roles = []
	for item in os.getenv("RANK_ROLES", "").split(","):
		if ":" in item:
			level, role_id = item.split(":", 1)
			if level.isdigit() and (role := guild.get_role(env_int_value(role_id))):
				roles.append((int(level), role))
	return sorted(roles)


def env_int_value(value):
	try:
		return int(value)
	except ValueError:
		return 0


async def award_xp(member, amount=XP_PER_MESSAGE):
	db("INSERT OR IGNORE INTO member_xp VALUES (?, ?, 0)", (member.guild.id, member.id))
	db("UPDATE member_xp SET xp=xp+? WHERE guild_id=? AND user_id=?", (amount, member.guild.id, member.id))
	points = db("SELECT xp FROM member_xp WHERE guild_id=? AND user_id=?", (member.guild.id, member.id), True)[0][0] # type: ignore
	level = points // 100
	for minimum, role in rank_roles(member.guild):
		if level >= minimum and role not in member.roles:
			try:
				await member.add_roles(role, reason="Level reward")
			except discord.HTTPException:
				pass
	return points


@bot.tree.command(name="rank", description="Show your server activity rank")
async def rank(interaction: discord.Interaction):
	row = db("SELECT xp FROM member_xp WHERE guild_id=? AND user_id=?", (interaction.guild.id, interaction.user.id), True) # type: ignore
	points = row[0][0] if row else 0
	level = points // 100
	embed = discord.Embed(title=f"{interaction.user.display_name}'s rank", color=discord.Color.gold())
	embed.set_thumbnail(url=interaction.user.display_avatar.url)
	embed.add_field(name="Level", value=str(level))
	embed.add_field(name="XP", value=f"{points % 100}/100 toward level {level + 1}")
	await interaction.response.send_message(embed=embed)


@bot.tree.command(name="setup-reaction-roles", description="Post the self-assignable role panel")
@app_commands.checks.has_permissions(manage_guild=True)
async def setup_reaction_roles(interaction: discord.Interaction):
	if not os.getenv("REACTION_ROLES"):
		return await interaction.response.send_message("Set REACTION_ROLES first.", ephemeral=True)
	view = RoleView()
	if not view.children:
		return await interaction.response.send_message("REACTION_ROLES has no valid role entries.", ephemeral=True)
	await interaction.response.send_message("Choose your roles below.", view=view)


@bot.tree.command(name="ask", description="Ask the AI assistant a question")
async def ask(interaction: discord.Interaction, question: str):
	if genai is None:
		return await interaction.response.send_message("The Gemini package is missing. Install it with `pip install -r requirements.txt`.", ephemeral=True)
	if not GEMINI_API_KEY or GEMINI_API_KEY.lower() in {"your_gemini_api_key", "your-gemini-api-key"}:
		return await interaction.response.send_message("AI chat is not configured. Add GEMINI_API_KEY to the bot's .env file and restart the bot.", ephemeral=True)
	await interaction.response.defer()
	try:
		genai.configure(api_key=os.getenv("GEMINI_API_KEY")) # type: ignore
		model = genai.GenerativeModel(AI_MODEL) # type: ignore
		result = await asyncio.to_thread(model.generate_content, question)
		await interaction.followup.send(result.text[:2000])
	except Exception as error:
		print(f"Gemini request failed: {error!r}")
		await interaction.followup.send("Gemini could not answer right now. Check the bot console and Gemini API key.")


@bot.command()
@commands.has_permissions(manage_guild=True)
async def ticketpanel(ctx):
	embed = discord.Embed(title="🎫 Support Tickets", description="Press the button below to open a private support ticket.", color=discord.Color.green())
	await ctx.send(embed=embed, view=TicketView())


@bot.command()
async def balance_cmd(ctx):
	await ctx.send(f"{ctx.author.mention}, you have **{balance(ctx.author.id)} coins**.")


@bot.tree.command(name="leaderboard", description="Show the top 10 members with the most coins")
async def leaderboard(interaction: discord.Interaction):
	if interaction.guild is None:
		return await interaction.response.send_message("The leaderboard can only be viewed in a server.", ephemeral=True)
	members = [member for member in interaction.guild.members if not member.bot]
	ranked = sorted(((balance(member.id), member) for member in members), key=lambda entry: entry[0], reverse=True)[:10]
	if not ranked:
		return await interaction.response.send_message("No member coin data is available yet.", ephemeral=True)
	lines = [f"**{position}.** {member.mention} — **{coins:,} coins**" for position, (coins, member) in enumerate(ranked, 1)]
	embed = discord.Embed(title=f"{interaction.guild.name} Coin Leaderboard", description="\n".join(lines), color=discord.Color.gold())
	embed.set_footer(text="Top 10 members")
	await interaction.response.send_message(embed=embed)


@bot.tree.command(name="shop", description="View items available for your coins")
async def shop_slash(interaction: discord.Interaction):
	rows = db("SELECT name, price, description FROM items ORDER BY price", fetch=True)
	if not rows:
		return await interaction.response.send_message("The shop is empty.", ephemeral=True)
	embed = discord.Embed(title="Coin Shop", description="Use `/buy` with an item name to purchase something useful.", color=discord.Color.blurple())
	embed.add_field(name="Your balance", value=f"**{balance(interaction.user.id):,} coins**", inline=False)
	for name, price, description in rows:
		embed.add_field(name=f"{name} — {price:,} coins", value=description, inline=False)
	await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="buy", description="Spend coins on an item from the shop")
@app_commands.describe(item="The exact item name to purchase")
async def buy_slash(interaction: discord.Interaction, item: str):
	row = db("SELECT name, price, description FROM items WHERE lower(name)=lower(?)", (item.strip(),), True)
	if not row:
		return await interaction.response.send_message("That item does not exist. Use `/shop` to see available items.", ephemeral=True)
	name, price, description = row[0]
	current_balance = balance(interaction.user.id)
	if current_balance < price:
		return await interaction.response.send_message(f"You need {price - current_balance:,} more coins to buy **{name}**.", ephemeral=True)
	db("UPDATE users SET balance=balance-? WHERE id=?", (price, interaction.user.id))
	await interaction.response.send_message(f"You bought **{name}** for **{price:,} coins**. {description} Your balance is now **{current_balance - price:,} coins**.")


@bot.command()
async def shop(ctx):
	rows = db("SELECT name, price, description FROM items", fetch=True)
	embed = discord.Embed(title="🛒 Shop", color=discord.Color.blurple())
	embed.description = "\n".join(f"**{n}** — {p} coins\n{d}\n`!buy {n}`" for n, p, d in rows) # type: ignore
	await ctx.send(embed=embed, view=ShopView())


@bot.command()
async def buy(ctx, *, item: str):
	row = db("SELECT name, price FROM items WHERE lower(name)=lower(?)", (item,), True)
	if not row:
		return await ctx.send("That item does not exist. Use `!shop`.")
	name, price = row[0]
	if balance(ctx.author.id) < price:
		return await ctx.send(f"You need {price - balance(ctx.author.id)} more coins.")
	db("UPDATE users SET balance=balance-? WHERE id=?", (price, ctx.author.id))
	await ctx.send(f"✅ {ctx.author.mention} bought **{name}** for {price} coins!")


@bot.command()
@commands.cooldown(1, 86400, commands.BucketType.user)
async def daily(ctx):
	balance(ctx.author.id)
	db("UPDATE users SET balance=balance+500 WHERE id=?", (ctx.author.id,))
	await ctx.send(f"🎁 {ctx.author.mention} received 500 daily coins!")


def calculate_count(text):
	try:
		node = ast.parse(text, mode="eval").body
		operators = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv}
		def evaluate(value):
			if isinstance(value, ast.Constant) and isinstance(value.value, (int, float)):
				return value.value
			if isinstance(value, ast.BinOp) and type(value.op) in operators:
				left, right = evaluate(value.left), evaluate(value.right)
				if abs(right) > 1000000 or abs(left) > 1000000:
					raise ValueError
				return operators[type(value.op)](left, right)
			raise ValueError
		result = evaluate(node)
		return int(result) if int(result) == result else None
	except (ValueError, TypeError, ZeroDivisionError, SyntaxError):
		return None


URL_PATTERN = re.compile(r"https?://[^\s<>()]+", re.IGNORECASE)


async def malicious_url(url):
	host = (urlparse(url).hostname or "").lower().rstrip(".")
	if not host or any(host == domain or host.endswith(f".{domain}") for domain in SAFE_DOMAINS):
		return False
	if any(host == domain or host.endswith(f".{domain}") for domain in BLOCKED_DOMAINS):
		return True
	if not GOOGLE_SAFE_BROWSING_KEY or not aiohttp:
		return False
	payload = {"client": {"clientId": "discord-support-bot", "clientVersion": "1.0"}, "threatInfo": {"threatTypes": ["MALWARE", "SOCIAL_ENGINEERING", "UNWANTED_SOFTWARE"], "platformTypes": ["ANY_PLATFORM"], "threatEntryTypes": ["URL"], "threatEntries": [{"url": url}]}}
	try:
		endpoint = f"https://safebrowsing.googleapis.com/v4/threatMatches:find?key={GOOGLE_SAFE_BROWSING_KEY}"
		timeout = aiohttp.ClientTimeout(total=4)
		async with aiohttp.ClientSession(timeout=timeout) as session:
			async with session.post(endpoint, json=payload) as response:
				return response.status == 200 and bool((await response.json()).get("matches"))
	except (aiohttp.ClientError, ValueError, TimeoutError):
		return False


async def scan_message_links(message):
	for url in URL_PATTERN.findall(message.content):
		if await malicious_url(url):
			await message.delete()
			try:
				await message.channel.send(f"{message.author.mention}, that link was blocked as potentially unsafe.", delete_after=8)
			except discord.HTTPException:
				pass
			return True
	return False


def has_media(message):
	if message.attachments:
		return True
	for url in URL_PATTERN.findall(message.content):
		host = (urlparse(url).hostname or "").lower().rstrip(".")
		if any(host == domain or host.endswith(f".{domain}") for domain in MEDIA_LINK_HOSTS):
			return True
	return False


def media_only_enabled(guild_id, channel_id):
	if channel_id in MEDIA_CHANNEL_IDS:
		return True
	row = db("SELECT enabled FROM media_only_channels WHERE guild_id=? AND channel_id=?", (guild_id, channel_id), True)
	return bool(row and row[0][0])


async def warn_media_only(message):
	warning = "This channel is media-only. Please post an image, video, file, or supported media link."
	try:
		await message.author.send(f"{warning} Your message in **{message.guild.name}** was removed.")
	except discord.HTTPException:
		try:
			await message.channel.send(f"{message.author.mention}, {warning}", delete_after=8)
		except discord.HTTPException:
			pass


async def create_voice_room(member):
	hub = member.guild.get_channel(VOICE_HUB_CHANNEL_ID)
	if not isinstance(hub, discord.VoiceChannel):
		return
	overwrites = {member.guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False), member: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True, manage_channels=True)}
	if SUPPORT_ROLE_ID and (role := member.guild.get_role(SUPPORT_ROLE_ID)):
		overwrites[role] = discord.PermissionOverwrite(view_channel=True, connect=True, speak=True)
	channel = await member.guild.create_voice_channel(f"{member.display_name}'s room", category=hub.category, overwrites=overwrites, reason="Join-to-create room")
	db("INSERT INTO temporary_voice VALUES (?, ?, ?)", (channel.id, member.guild.id, member.id))
	await member.move_to(channel)


async def remove_empty_voice(channel):
	if not isinstance(channel, discord.VoiceChannel) or channel.members:
		return
	row = db("SELECT channel_id FROM temporary_voice WHERE channel_id=?", (channel.id,), True)
	if row:
		db("DELETE FROM temporary_voice WHERE channel_id=?", (channel.id,))
		try:
			await channel.delete(reason="Temporary voice room empty")
		except discord.NotFound:
			pass


class TicTacToeView(discord.ui.View):
	def __init__(self, first, second=None):
		super().__init__(timeout=180)
		self.players = [first, second]
		self.board = [" "] * 9
		self.turn = 0
		for index in range(9):
			button = discord.ui.Button(label="·", style=discord.ButtonStyle.secondary, row=index // 3, custom_id=f"ttt:{index}")
			button.callback = self.make_callback(index)
			self.add_item(button)

	def make_callback(self, index):
		async def callback(interaction):
			if interaction.user != self.players[self.turn]:
				if self.players[1] is None:
					self.players[1] = interaction.user
				else:
					return await interaction.response.send_message("Wait for your turn.", ephemeral=True)
			if self.board[index] != " ":
				return await interaction.response.send_message("That square is occupied.", ephemeral=True)
			self.board[index] = "X" if self.turn == 0 else "O"
			button = self.children[index]
			button.label = self.board[index]
			button.disabled = True
			winner = self.winner()
			if winner or " " not in self.board:
				for item in self.children:
					item.disabled = True # type: ignore
				return await interaction.response.edit_message(content=winner or "Draw!", view=self)
			self.turn = 1 - self.turn
			await interaction.response.edit_message(content=f"Turn: {self.players[self.turn].mention}", view=self)
		return callback

	def winner(self):
		for line in ((0, 1, 2), (3, 4, 5), (6, 7, 8), (0, 3, 6), (1, 4, 7), (2, 5, 8), (0, 4, 8), (2, 4, 6)):
			if self.board[line[0]] != " " and len({self.board[i] for i in line}) == 1:
				return f"{self.board[line[0]]} wins!"
		return None


class RPSView(discord.ui.View):
	def __init__(self, challenger, opponent):
		super().__init__(timeout=60)
		self.challenger, self.opponent, self.moves = challenger, opponent, {}
		for label, move in (("Rock", "rock"), ("Paper", "paper"), ("Scissors", "scissors")):
			button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary, custom_id=f"rps:{move}")
			button.callback = self.make_callback(move)
			self.add_item(button)

	def make_callback(self, move):
		async def callback(interaction):
			await self.choose(interaction, move)
		return callback

	async def choose(self, interaction, move):
		if interaction.user not in (self.challenger, self.opponent):
			return await interaction.response.send_message("This game is not for you.", ephemeral=True)
		self.moves[interaction.user.id] = move
		if self.opponent == bot.user:
			self.moves[self.opponent.id] = random.choice(("rock", "paper", "scissors"))
		await interaction.response.send_message("Move locked in.", ephemeral=True)
		if len(self.moves) == 2:
			first, second = self.moves[self.challenger.id], self.moves[self.opponent.id]
			winner = self.challenger if first != second and (first, second) in (("rock", "scissors"), ("scissors", "paper"), ("paper", "rock")) else self.opponent if first != second else None
			for item in self.children:
				item.disabled = True # type: ignore
			await interaction.message.edit(content=f"{winner.mention + ' wins!' if winner else 'Draw!'}", view=self)

class BlackjackView(discord.ui.View):
	def __init__(self, interaction):
		super().__init__(timeout=120)
		self.user = interaction.user
		self.hand = [random.randint(1, 11), random.randint(1, 11)]
		self.dealer = random.randint(1, 11)

	def total(self):
		return sum(self.hand)

	@discord.ui.button(label="Hit", style=discord.ButtonStyle.green)
	async def hit(self, interaction, button):
		if interaction.user != self.user:
			return await interaction.response.send_message("This hand is not yours.", ephemeral=True)
		self.hand.append(random.randint(1, 11))
		if self.total() >= 21:
			button.disabled = True
			self.stand.disabled = True
		await interaction.response.edit_message(content=f"Your hand: {self.hand} ({self.total()})", view=self)

	@discord.ui.button(label="Stand", style=discord.ButtonStyle.red)
	async def stand(self, interaction, button):
		if interaction.user != self.user:
			return await interaction.response.send_message("This hand is not yours.", ephemeral=True)
		dealer = self.dealer
		while dealer < 17:
			dealer += random.randint(1, 11)
		result = "You win!" if self.total() <= 21 and (dealer > 21 or self.total() > dealer) else "Dealer wins."
		await interaction.response.edit_message(content=f"Your {self.total()} vs dealer {dealer}: {result}", view=None)


class MinefieldView(discord.ui.View):
	def __init__(self, user):
		super().__init__(timeout=120)
		self.user, self.mines, self.safe = user, set(random.sample(range(16), 4)), 0
		for index in range(16):
			button = discord.ui.Button(label="?", style=discord.ButtonStyle.secondary, row=index // 4)
			button.callback = self.make_callback(index)
			self.add_item(button)

	def make_callback(self, index):
		async def callback(interaction):
			if interaction.user != self.user:
				return await interaction.response.send_message("This minefield is not yours.", ephemeral=True)
			button = self.children[index]
			button.disabled = True
			if index in self.mines:
				for item in self.children:
					item.disabled = True # type: ignore
				return await interaction.response.edit_message(content="💥 You hit a mine!", view=self)
			self.safe += 1
			button.label = "💎"
			await interaction.response.edit_message(content=f"Safe tiles: {self.safe}/12", view=self)
		return callback


def change_balance(user_id, amount):
	balance(user_id)
	db("UPDATE users SET balance=balance+? WHERE id=?", (amount, user_id))


@bot.tree.command(name="tic-tac-toe", description="Play interactive Tic-Tac-Toe")
@app_commands.check(game_channel_check)
async def tic_tac_toe(interaction: discord.Interaction, opponent: discord.Member = None): # type: ignore
	if opponent is None or opponent == interaction.user or opponent.bot:
		return await interaction.response.send_message("Choose another human player.", ephemeral=True)
	await interaction.response.send_message(f"Turn: {interaction.user.mention}", view=TicTacToeView(interaction.user, opponent))


@bot.tree.command(name="rps", description="Play Rock Paper Scissors")
@app_commands.check(game_channel_check)
async def rps(interaction: discord.Interaction, opponent: discord.Member = None): # type: ignore
	opponent = opponent or bot.user
	if opponent == interaction.user:
		return await interaction.response.send_message("Choose another player.", ephemeral=True)
	if opponent == bot.user:
		return await interaction.response.send_message(f"Choose privately. The bot chose after you.", view=RPSView(interaction.user, bot.user))
	await interaction.response.send_message(f"{interaction.user.mention} challenged {opponent.mention}.", view=RPSView(interaction.user, opponent))


@bot.tree.command(name="roulette", description="Play a harmless Russian Roulette round")
@app_commands.check(game_channel_check)
async def roulette(interaction: discord.Interaction):
	if random.randrange(6) == 0:
		await interaction.response.send_message(f"💥 {interaction.user.mention} was eliminated and timed out for one minute.")
		try:
			await interaction.user.timeout(datetime.now(timezone.utc) + __import__("datetime").timedelta(minutes=1), reason="Russian Roulette game") # type: ignore
		except discord.HTTPException:
			pass
	else:
		await interaction.response.send_message(f"Click... {interaction.user.mention} is safe.")


@bot.tree.command(name="trivia", description="Answer a random quiz question")
@app_commands.check(game_channel_check)
async def trivia(interaction: discord.Interaction):
	questions = [("What planet is known as the Red Planet?", ["Mars", "Venus", "Jupiter", "Saturn"], "Mars"), ("What is H2O?", ["Oxygen", "Water", "Hydrogen", "Salt"], "Water")]
	question, answers, correct = random.choice(questions)
	view = discord.ui.View(timeout=30)
	for answer in answers:
		button = discord.ui.Button(label=answer, style=discord.ButtonStyle.primary)
		async def callback(button_interaction, selected=answer):
			if selected == correct:
				change_balance(button_interaction.user.id, 25)
				result = f"Correct! {button_interaction.user.mention} earns 25 coins."
			else:
				result = f"Not quite. The answer was **{correct}**."
			await button_interaction.response.edit_message(content=result, view=None)
		button.callback = callback # type: ignore
		view.add_item(button)
	await interaction.response.send_message(f"**{question}**", view=view)


async def timed_guess(interaction, title, answer):
	await interaction.response.send_message(f"{title}\nFirst correct answer wins. You have 30 seconds.")
		
	try:
		message = await bot.wait_for("message", timeout=30, check=lambda item: item.channel.id == interaction.channel.id and not item.author.bot and item.content.lower().strip() == answer.lower())
		change_balance(message.author.id, 20)
		await interaction.channel.send(f"{message.author.mention} wins 20 coins!")
	except asyncio.TimeoutError:
		await interaction.channel.send(f"Time's up. The answer was **{answer}**.")


@bot.tree.command(name="guess", description="Guess a number from 1 to 100")
@app_commands.check(game_channel_check)
async def guess(interaction: discord.Interaction):
	await interaction.response.send_message("Guess a number from 1 to 100 in this channel. You have 60 seconds.")
	secret = random.randint(1, 100)
	end = asyncio.get_running_loop().time() + 60
	while asyncio.get_running_loop().time() < end:
		try:
			message = await bot.wait_for("message", timeout=max(0.1, end - asyncio.get_running_loop().time()), check=lambda item: item.channel.id == interaction.channel.id and item.content.isdigit()) # type: ignore
		except asyncio.TimeoutError:
			return await interaction.channel.send(f"Time's up. The number was {secret}.") # type: ignore
		value = int(message.content)
		if value == secret:
			change_balance(message.author.id, 30)
			return await interaction.channel.send(f"{message.author.mention} guessed it and wins 30 coins!") # type: ignore
		await message.reply("Higher!" if value < secret else "Lower!", delete_after=5)


@bot.tree.command(name="hangman", description="Start a hangman word game")
@app_commands.check(game_channel_check)
async def hangman(interaction: discord.Interaction):
	word = random.choice(["python", "discord", "support", "diamond"])
	await interaction.response.send_message(f"Hangman: {' '.join('_' for _ in word)} | 6 lives. Guess letters in chat.")


@bot.tree.command(name="connect-four", description="Start a Connect Four match")
@app_commands.check(game_channel_check)
async def connect_four(interaction: discord.Interaction):
	await interaction.response.send_message("Connect Four is ready: challenge another player with `/tic-tac-toe`; the full board expansion is reserved for the next game update.")


@bot.tree.command(name="wordle", description="Play a five-letter Wordle round")
@app_commands.check(game_channel_check)
async def wordle(interaction: discord.Interaction):
	await interaction.response.send_message("Wordle started. Guess a five-letter word in chat within six attempts.")


@bot.tree.command(name="slot", description="Spin the coin slots")
@app_commands.check(game_channel_check)
async def slot(interaction: discord.Interaction, bet: app_commands.Range[int, 1, 1000] = 10):
	starting_balance = balance(interaction.user.id)
	if starting_balance < bet:
		return await interaction.response.send_message("You cannot cover that bet.", ephemeral=True)
	icons = ["🍒", "🍋", "🔔", "💎"]
	result = [random.choice(icons) for _ in range(3)]
	win = bet * (10 if len(set(result)) == 1 else 2 if len(set(result)) == 2 else 0)
	change_balance(interaction.user.id, win - bet)
	ending_balance = starting_balance + win - bet
	jackpot = len(set(result)) == 1
	if jackpot:
		status = "JACKPOT!"
		color = discord.Color.gold()
	elif win:
		status = "WIN!"
		color = discord.Color.green()
	else:
		status = "No match"
		color = discord.Color.red()
	embed = discord.Embed(title="🎰 Coin Slots", description=f"# | {result[0]} | {result[1]} | {result[2]} |\n\n**{status}**", color=color)
	embed.add_field(name="Bet", value=f"{bet:,} coins", inline=True)
	embed.add_field(name="Payout", value=f"{win:,} coins", inline=True)
	embed.add_field(name="Balance", value=f"{ending_balance:,} coins", inline=True)
	embed.set_footer(text="Three matching symbols = 10x payout • Two matching symbols = 2x payout")
	await interaction.response.send_message(embed=embed)


@bot.tree.command(name="coinflip", description="Flip a coin")
@app_commands.check(game_channel_check)
async def coinflip(interaction: discord.Interaction):
	await interaction.response.send_message(f"🪙 {random.choice(('Heads', 'Tails'))}")


@bot.tree.command(name="roll", description="Roll a die")
@app_commands.check(game_channel_check)
async def roll(interaction: discord.Interaction, sides: app_commands.Range[int, 2, 100] = 6):
	await interaction.response.send_message(f"🎲 {random.randint(1, sides)} (d{sides})")


@bot.tree.command(name="blackjack", description="Play blackjack against the dealer")
@app_commands.check(game_channel_check)
async def blackjack(interaction: discord.Interaction):
	view = BlackjackView(interaction)
	await interaction.response.send_message(f"Your hand: {view.hand} ({view.total()})", view=view)


@bot.tree.command(name="unscramble", description="Solve a scrambled word")
@app_commands.check(game_channel_check)
async def unscramble(interaction: discord.Interaction):
	word = random.choice(["python", "server", "button", "channel"])
	await timed_guess(interaction, f"Unscramble: **{' '.join(random.sample(list(word), len(word)))}**", word)


@bot.tree.command(name="emoji-quiz", description="Guess the movie from emojis")
@app_commands.check(game_channel_check)
async def emoji_quiz(interaction: discord.Interaction):
	await timed_guess(interaction, "Emoji quiz: 🦁 👑", "the lion king")


@bot.tree.command(name="truth-or-dare", description="Get a truth or dare prompt")
@app_commands.check(game_channel_check)
async def truth_or_dare(interaction: discord.Interaction):
	await interaction.response.send_message(random.choice(["Truth: What skill would you like to learn?", "Dare: Send a wholesome compliment to someone here."]))


@bot.tree.command(name="high-low", description="Guess whether the next card is higher or lower")
@app_commands.check(game_channel_check)
async def high_low(interaction: discord.Interaction, guess: str):
	first, second = random.randint(1, 13), random.randint(1, 13)
	correct = (guess.lower() == "high" and second > first) or (guess.lower() == "low" and second < first)
	await interaction.response.send_message(f"Card {first}, then {second}: {'Correct!' if correct else 'Wrong.'}")


@bot.tree.command(name="minefield", description="Clear a clickable minefield")
@app_commands.check(game_channel_check)
async def minefield(interaction: discord.Interaction):
	await interaction.response.send_message("Clear the field without hitting a mine.", view=MinefieldView(interaction.user))


@bot.tree.command(name="pokemon-guess", description="Guess the Pokemon from a hint")
@app_commands.check(game_channel_check)
async def pokemon_guess(interaction: discord.Interaction):
	questions = [
		("It is a yellow electric mouse.", "pikachu"),
		("It evolves from Charmander and has flames on its tail.", "charizard"),
		("It is a small blue water Pokemon that can hide in its shell.", "squirtle"),
		("It is a pink Pokemon known for singing opponents to sleep.", "jigglypuff"),
		("It is a sleepy Pokemon often found blocking paths.", "snorlax"),
		("It is a fox-like fire Pokemon with nine tails when fully evolved.", "ninetales"),
		("It is a ghost and poison Pokemon shaped like a ball with a mischievous grin.", "gengar"),
		("It is a small green Pokemon that evolves into Ivysaur.", "bulbasaur"),
		("It is a rare blue dragon Pokemon known for its powerful water attacks.", "gyarados"),
		("It is a yellow Pokemon with long ears and a lightning-shaped tail.", "pikachu"),
		("It is a psychic Pokemon with spoon-shaped weapons.", "alakazam"),
		("It is a fire Pokemon that resembles a pony.", "ponyta"),
		("It is a rock and ground Pokemon that looks like a boulder with arms.", "geodude"),
		("It is a water Pokemon that looks like a starfish.", "staryu"),
		("It is a butterfly-like bug and flying Pokemon with colorful wings.", "butterfree"),
		("It is a small electric Pokemon shaped like a mouse and has red cheeks.", "pichu"),
		("It is a fighting Pokemon famous for its spinning kicks.", "hitmonlee"),
		("It is an Eevee evolution with a blue body and water-based powers.", "vaporeon"),
		("It is an Eevee evolution with a black body and yellow rings.", "umbreon"),
		("It is a legendary ice Pokemon that resembles a large bird.", "articuno"),
	]
	hint, answer = random.choice(questions)
	await timed_guess(interaction, f"Who's that Pokemon? Hint: {hint}", answer)


@bot.tree.command(name="math-race", description="Solve a fast math problem")
@app_commands.check(game_channel_check)
async def math_race(interaction: discord.Interaction):
	left, right = random.randint(2, 20), random.randint(2, 20)
	await timed_guess(interaction, f"Math race: **{left} * {right}**", str(left * right))


@bot.tree.command(name="explore", description="Explore a text RPG dungeon")
@app_commands.check(game_channel_check)
@app_commands.checks.cooldown(1, 3600.0, key=lambda interaction: (interaction.guild_id, interaction.user.id))
async def explore(interaction: discord.Interaction):
	monster = random.choice(["slime", "skeleton", "cave bat"])
	reward = random.randint(20, 80)
	change_balance(interaction.user.id, reward)
	await interaction.response.send_message(f"You defeated a **{monster}** and found **{reward} coins**.")


@bot.event
async def on_message(message):
	if message.author.bot or not message.guild:
		return await bot.process_commands(message)
	if await scan_message_links(message):
		return
	if media_only_enabled(message.guild.id, message.channel.id) and not has_media(message):
		await message.delete()
		await warn_media_only(message)
		return
	if COUNTING_CHANNEL_ID and message.channel.id == COUNTING_CHANNEL_ID:
		row = db("SELECT last_number, last_user_id FROM counting WHERE guild_id=?", (message.guild.id,), True)
		last_number, last_user = row[0] if row else (0, None)
		value = calculate_count(message.content.strip())
		if value != last_number + 1 or last_user == message.author.id:
			await message.delete()
			return
		db("INSERT INTO counting(guild_id, channel_id, last_number, last_user_id) VALUES (?, ?, ?, ?) ON CONFLICT(guild_id) DO UPDATE SET channel_id=excluded.channel_id, last_number=excluded.last_number, last_user_id=excluded.last_user_id", (message.guild.id, message.channel.id, value, message.author.id))
	await award_xp(message.author)
	await bot.process_commands(message)


@bot.event
async def on_voice_state_update(member, before, after):
	if member.bot:
		return
	if after.channel and after.channel.id == VOICE_HUB_CHANNEL_ID:
		try:
			await create_voice_room(member)
		except discord.HTTPException as error:
			print(f"Voice room creation failed: {error!r}")
	if before.channel and before.channel.id != VOICE_HUB_CHANNEL_ID:
		await remove_empty_voice(before.channel)
	if before.channel != after.channel:
		await award_xp(member, 2)


@bot.event
async def on_command_error(ctx, error):
	if isinstance(error, commands.CommandOnCooldown):
		await ctx.send(f"Try again in {error.retry_after / 3600:.1f} hours.")
	elif isinstance(error, commands.MissingPermissions):
		await ctx.send("You do not have permission to use that command.")
	elif isinstance(error, commands.CommandNotFound):
		return
	else:
		await ctx.send("Something went wrong. Check the bot console.")
		raise error


if not TOKEN:
	raise RuntimeError("Set the DISCORD_TOKEN environment variable first.")
bot.run(TOKEN)
