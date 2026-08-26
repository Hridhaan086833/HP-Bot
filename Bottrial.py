import os
import re
import sqlite3
from datetime import datetime, timezone

import discord  # type: ignore[import-not-found]
from discord.ext import commands
from discord import app_commands

try:
	from dotenv import load_dotenv  # type: ignore[import-not-found]
except ImportError:
	def load_dotenv():
		return False

load_dotenv()


def env_int(name):
	try:
		return int(os.getenv(name, "0"))
	except ValueError:
		return 0


TOKEN = os.getenv("DISCORD_TOKEN", "")
SUPPORT_ROLE_ID = env_int("SUPPORT_ROLE_ID")
TICKET_CATEGORY_ID = env_int("TICKET_CATEGORY_ID")
DB = "ticket_bot.sqlite3"

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
	if not db("SELECT name FROM items", fetch=True):
		db("INSERT INTO items VALUES (?, ?, ?)", [
			("VIP", 500, "VIP server role"),
			("Custom Role", 1000, "A custom color role"),
			("Mystery Box", 250, "A surprise reward"),
		], many=True)


def balance(user_id):
	db("INSERT OR IGNORE INTO users(id) VALUES (?)", (user_id,))
	return db("SELECT balance FROM users WHERE id=?", (user_id,), True)[0][0]


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


class CloseTicketView(discord.ui.View):
	def __init__(self):
		super().__init__(timeout=None)

	@discord.ui.button(label="Close Ticket", emoji="🔒", style=discord.ButtonStyle.red, custom_id="ticket:close")
	async def close_ticket(self, interaction: discord.Interaction, button: discord.ui.Button):
		if not interaction.channel or not interaction.channel.name.startswith("ticket-"):
			return await interaction.response.send_message("This is not a ticket channel.", ephemeral=True)
		db("DELETE FROM tickets WHERE channel_id=?", (interaction.channel.id,))
		await interaction.response.send_message("Closing ticket in 5 seconds...")
		await discord.utils.sleep_until(datetime.now(timezone.utc)) if False else None
		import asyncio
		await asyncio.sleep(5)
		await interaction.channel.delete(reason=f"Closed by {interaction.user}")


class ShopView(discord.ui.View):
	@discord.ui.button(label="Shop", emoji="🛒", style=discord.ButtonStyle.blurple)
	async def shop(self, interaction: discord.Interaction, button: discord.ui.Button):
		rows = db("SELECT name, price, description FROM items", fetch=True)
		embed = discord.Embed(title="🛒 Shop", color=discord.Color.blurple())
		embed.description = "\n".join(f"**{n}** — {p} coins\n{d}\n`!buy {n}`" for n, p, d in rows)
		await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
	init_db()
	bot.add_view(TicketView())
	bot.add_view(CloseTicketView())
	if not getattr(bot, "_commands_synced", False):
		await bot.tree.sync()
		bot._commands_synced = True
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


@bot.command()
@commands.has_permissions(manage_guild=True)
async def ticketpanel(ctx):
	embed = discord.Embed(title="🎫 Support Tickets", description="Press the button below to open a private support ticket.", color=discord.Color.green())
	await ctx.send(embed=embed, view=TicketView())


@bot.command()
async def balance_cmd(ctx):
	await ctx.send(f"{ctx.author.mention}, you have **{balance(ctx.author.id)} coins**.")


@bot.command()
async def shop(ctx):
	rows = db("SELECT name, price, description FROM items", fetch=True)
	embed = discord.Embed(title="🛒 Shop", color=discord.Color.blurple())
	embed.description = "\n".join(f"**{n}** — {p} coins\n{d}\n`!buy {n}`" for n, p, d in rows)
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
	db("UPDATE users SET balance=balance+500 WHERE id=?", (ctx.author.id,))
	await ctx.send(f"🎁 {ctx.author.mention} received 500 daily coins!")


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
