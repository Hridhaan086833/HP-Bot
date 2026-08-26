require('dotenv').config();
const {
	Client, GatewayIntentBits, PermissionsBitField, ChannelType,
	EmbedBuilder, ActionRowBuilder, StringSelectMenuBuilder, ButtonBuilder,
	ButtonStyle, ModalBuilder, TextInputBuilder, TextInputStyle, AttachmentBuilder
} = require('discord.js');

const client = new Client({ intents: [GatewayIntentBits.Guilds, GatewayIntentBits.GuildMessages] });
const categories = {
	store: ['🛒 Store / Purchase Rank', ['Minecraft IGN', 'Proof or purchase links', 'Describe your request']],
	minecraft: ['🐛 Minecraft Issue / Bug', ['Minecraft IGN', 'Server/version', 'Describe the issue']],
	technical: ['🔧 Technical Support', ['Describe the issue', 'Relevant links', 'Additional details']],
	discord: ['💬 Discord Support', ['Describe the issue', 'Relevant links', 'Additional details']],
	report: ['🚨 Report Player / Appeal', ['Your Minecraft IGN', 'Reported player', 'Proof links and details']],
	vip: ['👑 VIP Support', ['Minecraft IGN', 'Describe your request', 'Relevant links']]
};
const staff = () => (process.env.STAFF_ROLE_IDS || '').split(',').map(x => x.trim()).filter(Boolean);
const staffMember = m => m.permissions.has(PermissionsBitField.Flags.ManageChannels) || staff().some(id => m.roles.cache.has(id));
const slug = s => s.toLowerCase().replace(/[^a-z0-9-]/g, '-').slice(0, 20);

function panel() {
	return {
		embeds: [new EmbedBuilder().setColor(process.env.ACCENT_COLOR || 0x5865f2).setTitle('Support Center').setDescription('Choose a category. A short form will open before your private ticket is created.')],
		components: [new ActionRowBuilder().addComponents(
			new StringSelectMenuBuilder()
				.setCustomId('ticket-category')
				.setPlaceholder('Select a category')
				.addOptions(Object.entries(categories).map(([value, [label]]) => ({ value, label })))
		)]
	};
}
function controls() {
	return new ActionRowBuilder().addComponents(
		new ButtonBuilder().setCustomId('close').setLabel('Close Ticket').setStyle(ButtonStyle.Danger),
		new ButtonBuilder().setCustomId('close-reason').setLabel('Close with Reason').setStyle(ButtonStyle.Secondary),
		new ButtonBuilder().setCustomId('transcript').setLabel('Transcript').setStyle(ButtonStyle.Primary),
		new ButtonBuilder().setCustomId('add-member').setLabel('Add Member').setStyle(ButtonStyle.Success)
	);
}

async function createTicket(i, category) {
	const old = i.guild.channels.cache.find(c => c.topic?.includes(`owner:${i.user.id};category:${category}`));
	if (old) return i.editReply(`You already have an active ticket: ${old}`);
	const overwrites = [{ id: i.guild.id, deny: [PermissionsBitField.Flags.ViewChannel] }, { id: i.user.id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] }];
	staff().forEach(id => overwrites.push({ id, allow: [PermissionsBitField.Flags.ViewChannel, PermissionsBitField.Flags.SendMessages, PermissionsBitField.Flags.ReadMessageHistory] }));
	const channel = await i.guild.channels.create({ name: `ticket-${slug(i.user.username)}-${category}`, type: ChannelType.GuildText, topic: `owner:${i.user.id};category:${category}`, permissionOverwrites: overwrites });
	const fields = i.fields.fields.map(f => ({ name: f.customId, value: f.value.slice(0, 1024) || 'Not provided' }));
	await channel.send({ content: `${i.user} ${staff().map(id => `<@&${id}>`).join(' ')}`, embeds: [new EmbedBuilder().setColor(0x57f287).setTitle(categories[category][0]).addFields(fields)], components: [controls()] });
	return i.editReply(`Your ticket is ready: ${channel}`);
}

client.once('ready', () => console.log(`Ready as ${client.user.tag}`));
client.on('interactionCreate', async i => {
	try {
		if (i.isChatInputCommand() && i.commandName === 'setup-ticket') return i.reply(panel());
		if (i.isStringSelectMenu() && i.customId === 'ticket-category') {
			const category = i.values[0];
			const modal = new ModalBuilder().setCustomId(`ticket-form:${category}`).setTitle(categories[category][0].slice(0, 45));
			modal.addComponents(categories[category][1].map((label, n) => new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId(`answer-${n}`).setLabel(label).setStyle(n === 2 ? TextInputStyle.Paragraph : TextInputStyle.Short).setRequired(n === 0))));
			return i.showModal(modal);
		}
		if (i.isModalSubmit() && i.customId.startsWith('ticket-form:')) { await i.deferReply({ ephemeral: true }); return createTicket(i, i.customId.split(':')[1]); }
		if (!i.isButton() || !i.channel?.topic?.startsWith('owner:')) return;
		if (['close', 'close-reason', 'transcript', 'add-member'].includes(i.customId) && !staffMember(i.member)) return i.reply({ content: 'Staff only.', ephemeral: true });
		if (i.customId === 'close-reason') { const m = new ModalBuilder().setCustomId('reason').setTitle('Close ticket').addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('value').setLabel('Closure reason').setStyle(TextInputStyle.Paragraph).setRequired(true))); return i.showModal(m); }
		if (i.customId === 'add-member') { const m = new ModalBuilder().setCustomId('add').setTitle('Add member').addComponents(new ActionRowBuilder().addComponents(new TextInputBuilder().setCustomId('value').setLabel('User ID').setStyle(TextInputStyle.Short).setRequired(true))); return i.showModal(m); }
		if (i.customId === 'transcript') { const messages = await i.channel.messages.fetch({ limit: 100 }); const text = [...messages.values()].reverse().map(m => `${m.author.tag}: ${m.content}`).join('\n'); return i.reply({ files: [new AttachmentBuilder(Buffer.from(text || 'Empty'), { name: 'transcript.txt' })], ephemeral: true }); }
		await i.reply('Ticket closed.'); await i.channel.delete('Ticket closed');
	} catch (e) { console.error(e); if (!i.replied && !i.deferred) i.reply({ content: 'Unexpected error.', ephemeral: true }); }
});

client.login(process.env.DISCORD_TOKEN).catch(console.error);
