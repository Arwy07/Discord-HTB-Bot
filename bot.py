"""Bot de configuration du serveur Lab-HTB, rôles de niveau et suivi de progression."""

from __future__ import annotations

import asyncio
import csv
import io
import json
import logging
import os
from datetime import datetime, timezone
from pathlib import Path

import discord
from discord import app_commands
from dotenv import load_dotenv

load_dotenv(Path(__file__).with_name(".env"))

from server_plan import (
    ACADEMY_MODULES,
    CHANNEL_GUIDES,
    CHAT_CATEGORY,
    CJCA_ROLE,
    CJCA_ROLE_COLOUR,
    EXTRA_ADMIN_IDS,
    GUILD_ID,
    LAB_CATEGORY,
    LAB_DIFFICULTIES,
    LAB_VALIDATION_CHANNEL_ID,
    LEVEL_MESSAGE_MARKER,
    LEVELS,
    STAFF_CATEGORY,
    STAFF_ROLE,
    STUDENT_ROLE,
    TEXT_CHANNELS,
    VOICE_CATEGORY,
    VOICE_CHANNELS,
    WELCOME_CATEGORY,
    XP_PAR_ETAPE,
)


load_dotenv(Path(__file__).with_name(".env"))
TOKEN = os.getenv("DISCORD_TOKEN", "").strip()
TARGET_GUILD_ID = int(os.getenv("GUILD_ID", str(GUILD_ID)))
MEMBERS_INTENT_ENABLED = os.getenv("DISCORD_MEMBERS_INTENT", "false").strip().lower() in {"1", "true", "yes", "oui"}
STATE_FILE = Path(__file__).with_name("state.json")
REASON = "Installation du lab par /installer_lab"
log = logging.getLogger("lab_htb")


class SetupError(Exception):
    """Erreur explicite à montrer à l'administrateur."""


def find_one(items, name: str, kind: str):
    matches = [item for item in items if item.name == name]
    if len(matches) > 1:
        raise SetupError(f"Plusieurs {kind} portent le nom « {name} ». Renomme les doublons, puis relance la commande.")
    return matches[0] if matches else None


def load_state() -> dict:
    if not STATE_FILE.exists():
        return {}
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        log.warning("state.json illisible ; /installer_lab le reconstruira.")
        return {}


def save_state(state: dict) -> None:
    temp = STATE_FILE.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    temp.replace(STATE_FILE)


def text_overwrites(guild: discord.Guild, roles: dict, bot_member: discord.Member,
                    access: str, writable: bool, reactions: bool = False) -> dict:
    everyone = guild.default_role
    student = roles[STUDENT_ROLE]
    staff = roles[STAFF_ROLE]
    public = access == "public"
    student_access = access == "student"
    staff_access = access == "staff"
    result = {
        everyone: discord.PermissionOverwrite(
            view_channel=public,
            read_message_history=public,
            send_messages=False,
            add_reactions=public and reactions,
        ),
        staff: discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            add_reactions=True,
            manage_messages=True,
        ),
        bot_member: discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=True,
            add_reactions=True,
            manage_messages=True,
        ),
    }
    if student_access:
        result[student] = discord.PermissionOverwrite(
            view_channel=True,
            read_message_history=True,
            send_messages=writable,
            add_reactions=True,
        )
    elif staff_access:
        result[student] = discord.PermissionOverwrite(view_channel=False)
    return result


def voice_overwrites(guild: discord.Guild, roles: dict, bot_member: discord.Member) -> dict:
    return {
        guild.default_role: discord.PermissionOverwrite(view_channel=False, connect=False),
        roles[STUDENT_ROLE]: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
        roles[STAFF_ROLE]: discord.PermissionOverwrite(view_channel=True, connect=True, speak=True),
        bot_member: discord.PermissionOverwrite(view_channel=True, connect=True),
    }


def preflight(guild: discord.Guild, bot_member: discord.Member) -> None:
    if guild.id != TARGET_GUILD_ID:
        raise SetupError("Cette commande est réservée au serveur Lab-HTB configuré dans .env.")
    permissions = bot_member.guild_permissions
    required = {
        "Gérer les salons": permissions.manage_channels,
        "Gérer les rôles": permissions.manage_roles,
        "Voir les salons": permissions.view_channel,
        "Envoyer des messages": permissions.send_messages,
        "Lire l'historique": permissions.read_message_history,
        "Ajouter des réactions": permissions.add_reactions,
        "Gérer les messages": permissions.manage_messages,
    }
    missing = [name for name, enabled in required.items() if not enabled]
    if missing:
        raise SetupError("Permissions manquantes pour le bot : " + ", ".join(missing) + ". Réinvite-le avec le lien du README.")
    managed_names = {STUDENT_ROLE, STAFF_ROLE, CJCA_ROLE, *(name for name, _ in LEVELS.values())}
    for name in managed_names:
        role = find_one(guild.roles, name, "rôles")
        if role is None:
            continue
        if role >= bot_member.top_role:
            raise SetupError(
                f"Le rôle « {name} » est au-dessus du rôle du bot. Dans Discord, place le rôle du bot au-dessus "
                "des rôles Lab-HTB, puis relance /installer_lab. Discord impose cette hiérarchie pour attribuer un rôle."
            )
        if name != STAFF_ROLE and any((
            role.permissions.administrator,
            role.permissions.manage_guild,
            role.permissions.manage_channels,
            role.permissions.manage_roles,
            role.permissions.kick_members,
            role.permissions.ban_members,
            role.permissions.manage_webhooks,
        )):
            raise SetupError(f"Le rôle « {name} » possède des permissions de gestion du serveur. Retire-les avant de l'utiliser pour les étudiants.")


async def ensure_roles(guild: discord.Guild, changes: list[str]) -> dict:
    specs = [
        (STUDENT_ROLE, 0x95A5A6),
        (STAFF_ROLE, 0xF1C40F),
        (CJCA_ROLE, CJCA_ROLE_COLOUR),
        *((name, colour) for name, colour in LEVELS.values()),
    ]
    roles = {}
    for name, colour in specs:
        role = find_one(guild.roles, name, "rôles")
        if role is None:
            role = await guild.create_role(
                name=name,
                permissions=discord.Permissions.none(),
                colour=discord.Colour(colour),
                mentionable=False,
                reason=REASON,
            )
            changes.append(f"rôle {name}")
        roles[name] = role
    return roles


async def ensure_category(guild: discord.Guild, name: str, overwrites: dict,
                          changes: list[str], legacy_names: tuple[str, ...] = ()) -> discord.CategoryChannel:
    category = find_one(guild.categories, name, "catégories")
    if category is None:
        legacy_matches = [item for item in guild.categories if item.name in legacy_names]
        if len(legacy_matches) > 1:
            raise SetupError(f"Plusieurs anciennes catégories correspondent à « {name} ». Renomme les doublons, puis relance la commande.")
        if legacy_matches:
            category = legacy_matches[0]
            old_name = category.name
            updated = await category.edit(name=name, overwrites=overwrites, reason=REASON)
            category = updated or category
            changes.append(f"catégorie {old_name} renommée {name}")
    if category is None:
        category = await guild.create_category(name, overwrites=overwrites, reason=REASON)
        changes.append(f"catégorie {name}")
    elif category.overwrites != overwrites:
        updated = await category.edit(overwrites=overwrites, reason=REASON)
        category = updated or category
        changes.append(f"permissions {name}")
    return category


async def ensure_text_channel(guild: discord.Guild, category: discord.CategoryChannel,
                              spec, overwrites: dict, changes: list[str]) -> discord.TextChannel:
    channels = [c for c in guild.text_channels if c.category_id == category.id]
    matches = [c for c in channels if c.name in {spec.name, spec.discord_name}]
    if len(matches) > 1:
        raise SetupError(f"Plusieurs salons correspondent à « {spec.discord_name} ». Renomme les doublons, puis relance la commande.")
    channel = matches[0] if matches else None
    if channel is None:
        channel = await guild.create_text_channel(
            spec.discord_name, category=category, topic=spec.topic, overwrites=overwrites, reason=REASON
        )
        changes.append(f"#{spec.discord_name}")
    elif channel.name != spec.discord_name or channel.topic != spec.topic or channel.overwrites != overwrites:
        updated = await channel.edit(name=spec.discord_name, topic=spec.topic, overwrites=overwrites, reason=REASON)
        channel = updated or channel
        changes.append(f"réglages #{spec.discord_name}")
    return channel


async def ensure_voice_channel(guild: discord.Guild, category: discord.CategoryChannel,
                               legacy_name: str, name: str, overwrites: dict, changes: list[str]) -> discord.VoiceChannel:
    channels = [c for c in guild.voice_channels if c.category_id == category.id]
    matches = [c for c in channels if c.name in {legacy_name, name}]
    if len(matches) > 1:
        raise SetupError(f"Plusieurs salons vocaux correspondent à « {name} ». Renomme les doublons, puis relance la commande.")
    channel = matches[0] if matches else None
    if channel is None:
        channel = await guild.create_voice_channel(name, category=category, overwrites=overwrites, reason=REASON)
        changes.append(f"vocal {name}")
    elif channel.name != name or channel.overwrites != overwrites:
        updated = await channel.edit(name=name, overwrites=overwrites, reason=REASON)
        channel = updated or channel
        changes.append(f"réglages vocal {name}")
    return channel


def channel_intro_embed(channel_name: str) -> discord.Embed:
    guide = CHANNEL_GUIDES[channel_name]
    embed = discord.Embed(
        title=f"{guide.icon}  {guide.title}",
        description=guide.purpose,
        colour=discord.Colour(guide.colour),
    )
    embed.add_field(name="📌 À quoi sert ce salon ?", value=guide.usage, inline=False)
    embed.add_field(name="💡 Exemple", value=guide.example, inline=False)
    if channel_name == "règles":
        embed.add_field(
            name="✅ Règles essentielles",
            value=(
                "• Travaille uniquement sur les machines et comptes autorisés.\n"
                "• Ne publie aucun flag, mot de passe, jeton ou corrigé complet.\n"
                "• Donne des indices progressifs et respecte les autres membres.\n"
                "• Suis les consignes des encadrants."
            ),
            inline=False,
        )
    elif channel_name == "choix-du-niveau":
        embed.add_field(
            name="Niveaux disponibles",
            value=(
                "🟢 **Débutant** — je découvre encore les bases\n"
                "🔵 **Intermédiaire** — je suis autonome sur les étapes courantes\n"
                "🟣 **Avancé** — je maîtrise les bases et les techniques avancées"
            ),
            inline=False,
        )
        embed.add_field(
            name="Comment faire ?",
            value="Clique sur une réaction sous ce message. Le bot te donnera **Étudiant** et ton rôle de niveau.",
            inline=False,
        )
    embed.set_footer(text=f"Lab-HTB • guide • #{channel_name}")
    return embed


def server_guide_embed(channels: dict, voice_channels: dict) -> discord.Embed:
    def text_link(category: str, name: str) -> str:
        channel = channels[(category, name)]
        return f"{channel.mention} — {CHANNEL_GUIDES[name].purpose}"

    def voice_link(name: str) -> str:
        channel = voice_channels[(VOICE_CATEGORY, name)]
        detail = "Discussions vocales libres." if name == "Général" else "Aide en direct et travail en groupe."
        return f"{channel.mention} — {detail}"

    embed = discord.Embed(
        title="🧭  Guide complet de Lab-HTB",
        description=(
            "Bienvenue dans l'espace du projet **Hack The Box**. Voici le rôle de chaque salon. "
            "Clique sur son nom pour t'y rendre directement."
        ),
        colour=discord.Colour(0x5865F2),
    )
    sections = (
        (WELCOME_CATEGORY, WELCOME_CATEGORY, ("bienvenue", "guide-du-serveur", "règles", "annonces", "choix-du-niveau")),
        (LAB_CATEGORY, LAB_CATEGORY, ("consignes", "machines", "ressources", "entraide", "progression", "avance", "classement")),
        (CHAT_CATEGORY, CHAT_CATEGORY, ("général",)),
    )
    for title, category, names in sections:
        embed.add_field(name=title, value="\n".join(text_link(category, name) for name in names), inline=False)
    embed.add_field(
        name="🔊 VOCAL",
        value="\n".join(voice_link(name) for name, _ in VOICE_CHANNELS),
        inline=False,
    )
    embed.add_field(
        name="🛡️ RÈGLES ESSENTIELLES",
        value=(
            "• Utilise uniquement les machines et comptes autorisés.\n"
            "• Ne partage aucun flag, mot de passe, jeton ou corrigé complet.\n"
            "• Dans l'entraide, donne des indices progressifs et respectueux."
        ),
        inline=False,
    )
    embed.set_footer(text="Lab-HTB • guide général • mis à jour automatiquement")
    return embed


async def ensure_bot_embed(channel: discord.TextChannel, bot_id: int,
                           markers: str | tuple[str, ...], embed: discord.Embed,
                           known_message_id: int | None = None) -> discord.Message:
    markers = (markers,) if isinstance(markers, str) else markers
    if known_message_id:
        try:
            message = await channel.fetch_message(known_message_id)
            if message.author.id == bot_id:
                await message.edit(content=None, embed=embed)
                return message
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
    async for message in channel.history(limit=100):
        footer = message.embeds[0].footer.text if message.embeds and message.embeds[0].footer else ""
        if message.author.id == bot_id and any(
            marker in message.content or marker in (footer or "") for marker in markers
        ):
            await message.edit(content=None, embed=embed)
            return message
    return await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())


def avance_guide_embed() -> discord.Embed:
    embed = discord.Embed(
        title="🚀  Comment suivre ton avancement",
        description=(
            "Tape `/` puis le nom de la commande : Discord t'indique chaque champ à remplir. "
            "Ton avancement est publié dans 📈・progression, et le classement dans 🏆・classement."
        ),
        colour=discord.Colour(0xE67E22),
    )
    embed.add_field(
        name="🧪 /lab",
        value=(
            "Enregistre un lab Hack The Box terminé en entier. Un encadrant doit le valider.\n"
            "• `nom` : le nom du lab\n"
            "• `difficulte` : Very Easy, Easy, Medium, Hard ou Insane\n"
            "• `ia` : Oui si tu as utilisé l'IA\n"
            "Exemple : `/lab nom:Lame difficulte:Easy ia:Non`"
        ),
        inline=False,
    )
    embed.add_field(
        name="📘 /module",
        value=(
            "Enregistre tes étapes faites dans un module CJCA. Chaque étape vaut 5 XP.\n"
            "• `parcours` : CJCA\n"
            "• `module` : choisis le module dans la liste\n"
            "• `etapes` : ton nombre d'étapes faites, par exemple 15 sur 24\n"
            "Exemple : `/module parcours:CJCA module:Footprinting etapes:15`"
        ),
        inline=False,
    )
    embed.add_field(
        name="🎯 Barème XP",
        value=(
            "• Labs : Very Easy 10 · Easy 20 · Medium 30 · Hard 40 · Insane 50 XP\n"
            "• Avec l'IA, l'XP d'un lab est divisée par 2\n"
            "• Modules : 5 XP par étape. Renvoie `/module` pour mettre à jour ton avancement."
        ),
        inline=False,
    )
    embed.set_footer(text="Lab-HTB • mode d'emploi • #avance")
    return embed


def staff_commands_embed() -> discord.Embed:
    embed = discord.Embed(
        title="📖  Commandes du bot Lab-HTB",
        description="Toutes les commandes disponibles. Tape `/` dans Discord pour les remplir pas à pas.",
        colour=discord.Colour(0x5865F2),
    )
    embed.add_field(
        name="🎓 Étudiants",
        value=(
            "**`/lab nom difficulte ia`** : déclare un lab terminé en entier. La demande part dans le salon de "
            "validation (✅ valide, ❌ refuse). L'XP n'est donnée qu'après validation.\n"
            "**`/module parcours module etapes`** : enregistre les étapes faites dans un module CJCA "
            "(ex. 15 sur 24). 5 XP par étape, sans validation. Renvoyer la commande met à jour l'avancement.\n"
            "**`/classement`** : affiche le top 15 par XP."
        ),
        inline=False,
    )
    embed.add_field(
        name="🛡️ Encadrants",
        value=(
            "**`/avance membre`** : bilan privé d'un étudiant (labs avec difficulté, IA et statut, modules, XP).\n"
            "**`/bilan_classe`** : bilan privé de toute la classe, étudiants sans activité inclus, avec CSV.\n"
            "**`/corriger lab membre nom action`** : valide, refuse ou supprime un lab.\n"
            "**`/corriger module membre module etapes`** : corrige les étapes d'un module (0 pour effacer).\n"
            "**`/export`** : fichier CSV de l'avancement de tous les étudiants (ouvrable dans Excel).\n"
            "**`/retard [jours]`** : étudiants sans activité depuis X jours (7 par défaut).\n"
            "**`/stats`** : statistiques des labs (validés, en attente, part avec IA) et des modules."
        ),
        inline=False,
    )
    embed.add_field(
        name="⚙️ Administration",
        value=(
            "**`/installer_lab`** : crée ou répare rôles, salons, permissions et messages du bot "
            "(propriétaire, co-administrateur ou administrateur).\n"
            "**`/nommer_encadrant membre`** : donne le rôle Encadrant (propriétaire ou co-administrateur)."
        ),
        inline=False,
    )
    embed.add_field(
        name="🎯 Règles XP",
        value=(
            "• Labs : Very Easy 10 · Easy 20 · Medium 30 · Hard 40 · Insane 50 XP, divisé par 2 avec l'IA.\n"
            "• Modules : 5 XP par étape.\n"
            "• Les 20 modules CJCA terminés donnent le rôle **CJCA terminé**.\n"
            "• Le classement de 🏆・classement se met à jour automatiquement."
        ),
        inline=False,
    )
    embed.set_footer(text="Lab-HTB • commandes • #commandes")
    return embed


async def post_audit(guild: discord.Guild, text: str) -> None:
    journal_name = next(spec.discord_name for spec in TEXT_CHANNELS if spec.name == "journal-bot")
    channel = discord.utils.get(guild.text_channels, name=journal_name)
    if not isinstance(channel, discord.TextChannel) or channel.category is None or channel.category.name != STAFF_CATEGORY:
        return
    try:
        await channel.send(text, allowed_mentions=discord.AllowedMentions.none())
    except discord.HTTPException:
        log.warning("Impossible d'écrire dans #journal-bot")


async def provision(guild: discord.Guild, bot_member: discord.Member) -> tuple[list[str], discord.Message]:
    changes: list[str] = []
    preflight(guild, bot_member)
    roles = await ensure_roles(guild, changes)
    if any(role >= bot_member.top_role for role in roles.values()):
        raise SetupError("Le rôle du bot doit être au-dessus des rôles Lab-HTB. Déplace-le, puis relance /installer_lab.")

    categories = {}
    category_specs = (
        (WELCOME_CATEGORY, "public", False, ("ACCUEIL",)),
        (LAB_CATEGORY, "student", True, ("LAB HTB",)),
        (CHAT_CATEGORY, "student", True, ("DISCUSSIONS", "Salons textuels")),
        (VOICE_CATEGORY, "student", True, ("VOCAL", "Salons vocaux")),
        (STAFF_CATEGORY, "staff", True, ("ADMINISTRATION",)),
    )
    for name, access, writable, legacy in category_specs:
        overwrites = (
            voice_overwrites(guild, roles, bot_member)
            if name == VOICE_CATEGORY
            else text_overwrites(guild, roles, bot_member, access, writable)
        )
        categories[name] = await ensure_category(guild, name, overwrites, changes, legacy)

    channels = {}
    for spec in TEXT_CHANNELS:
        overwrites = text_overwrites(guild, roles, bot_member, spec.access, spec.writable, spec.reactions)
        channels[(spec.category, spec.name)] = await ensure_text_channel(
            guild, categories[spec.category], spec, overwrites, changes
        )

    voice_channels = {}
    for legacy_name, channel_name in VOICE_CHANNELS:
        voice_channels[(VOICE_CATEGORY, legacy_name)] = await ensure_voice_channel(
            guild, categories[VOICE_CATEGORY], legacy_name, channel_name,
            voice_overwrites(guild, roles, bot_member), changes
        )

    # Ces appels ne suppriment aucun salon ; ils ne font qu'ordonner les catégories gérées.
    await categories[WELCOME_CATEGORY].move(beginning=True, reason=REASON)
    await categories[LAB_CATEGORY].move(after=categories[WELCOME_CATEGORY], reason=REASON)
    await categories[CHAT_CATEGORY].move(after=categories[LAB_CATEGORY], reason=REASON)
    await categories[VOICE_CATEGORY].move(after=categories[CHAT_CATEGORY], reason=REASON)
    await categories[STAFF_CATEGORY].move(after=categories[VOICE_CATEGORY], reason=REASON)

    state = load_state()
    guild_state = state.setdefault(str(guild.id), {})

    # Retire les anciennes cartes descriptives. Le message de niveau et le guide général sont conservés.
    old_guide_messages = guild_state.pop("guide_messages", {})
    keep_message_ids = {guild_state.get("message_id"), guild_state.get("server_guide_message_id")}
    for channel_id, message_id in old_guide_messages.items():
        if message_id in keep_message_ids:
            continue
        channel = guild.get_channel(int(channel_id))
        if not isinstance(channel, discord.TextChannel):
            continue
        try:
            message = await channel.fetch_message(message_id)
            if message.author.id == bot_member.id:
                await message.delete()
                changes.append(f"ancienne présentation retirée de #{channel.name}")
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass

    guide_channel = channels[(WELCOME_CATEGORY, "guide-du-serveur")]
    guide_message = await ensure_bot_embed(
        guide_channel,
        bot_member.id,
        "Lab-HTB • guide général",
        server_guide_embed(channels, voice_channels),
        guild_state.get("server_guide_message_id"),
    )
    guild_state["server_guide_message_id"] = guide_message.id

    level_channel = channels[(WELCOME_CATEGORY, "choix-du-niveau")]
    level_message = await ensure_bot_embed(
        level_channel,
        bot_member.id,
        ("Lab-HTB • guide • #choix-du-niveau", LEVEL_MESSAGE_MARKER),
        channel_intro_embed("choix-du-niveau"),
        guild_state.get("message_id"),
    )
    existing_reactions = {str(reaction.emoji) for reaction in level_message.reactions}
    for emoji in LEVELS:
        if emoji not in existing_reactions:
            await level_message.add_reaction(emoji)

    guild_state["channel_id"] = level_channel.id
    guild_state["message_id"] = level_message.id
    avance_channel = channels[(LAB_CATEGORY, "avance")]
    avance_message = await ensure_bot_embed(
        avance_channel,
        bot_member.id,
        "Lab-HTB • mode d'emploi • #avance",
        avance_guide_embed(),
        guild_state.get("avance_message_id"),
    )
    guild_state["avance_message_id"] = avance_message.id
    guild_state["avance_channel_id"] = avance_channel.id
    guild_state["progression_channel_id"] = channels[(LAB_CATEGORY, "progression")].id
    guild_state["classement_channel_id"] = channels[(LAB_CATEGORY, "classement")].id
    commands_message = await ensure_bot_embed(
        channels[(STAFF_CATEGORY, "commandes")],
        bot_member.id,
        "Lab-HTB • commandes • #commandes",
        staff_commands_embed(),
        guild_state.get("staff_commands_message_id"),
    )
    guild_state["staff_commands_message_id"] = commands_message.id
    save_state(state)
    await post_audit(guild, "Installation Lab-HTB terminée : " + (", ".join(changes) if changes else "configuration vérifiée"))
    return changes, level_message


class LabBot(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = False
        # Optionnel : sans cet intent, /bilan_classe fonctionne sur les étudiants déjà suivis.
        intents.members = MEMBERS_INTENT_ENABLED
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)
        self.setup_locks: dict[int, asyncio.Lock] = {}
        self.member_locks: dict[tuple[int, int], asyncio.Lock] = {}
        self.state = load_state()

    async def setup_hook(self):
        guild = discord.Object(id=TARGET_GUILD_ID)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        log.info("Commandes synchronisées avec le serveur %s", TARGET_GUILD_ID)

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent):
        if payload.guild_id is None or payload.user_id == self.user.id:
            return
        if payload.channel_id == LAB_VALIDATION_CHANNEL_ID:
            await handle_lab_validation(payload)
            return
        saved = self.state.get(str(payload.guild_id), {})
        if payload.message_id != saved.get("message_id") or str(payload.emoji) not in LEVELS:
            return
        guild = self.get_guild(payload.guild_id)
        if guild is None:
            return
        try:
            member = payload.member or await guild.fetch_member(payload.user_id)
        except discord.HTTPException:
            log.warning("Membre %s introuvable pour la réaction", payload.user_id)
            return
        if member.bot:
            return
        key = (guild.id, member.id)
        lock = self.member_locks.setdefault(key, asyncio.Lock())
        async with lock:
            try:
                student = find_one(guild.roles, STUDENT_ROLE, "rôles")
                level_name = LEVELS[str(payload.emoji)][0]
                chosen = find_one(guild.roles, level_name, "rôles")
                if student is None or chosen is None:
                    raise SetupError("Rôles du lab introuvables ; relance /installer_lab.")
                other_levels = [
                    role for role in member.roles
                    if role.name in {name for name, _ in LEVELS.values()} and role.id != chosen.id
                ]
                if other_levels:
                    await member.remove_roles(*other_levels, reason="Changement de niveau Lab-HTB")
                to_add = [role for role in (student, chosen) if role not in member.roles]
                if to_add:
                    await member.add_roles(*to_add, reason="Réaction au niveau Lab-HTB")

                channel = guild.get_channel(saved["channel_id"])
                if isinstance(channel, discord.TextChannel) and other_levels:
                    message = await channel.fetch_message(payload.message_id)
                    for emoji, (name, _) in LEVELS.items():
                        if name != level_name:
                            try:
                                await message.remove_reaction(emoji, member)
                            except discord.Forbidden:
                                log.warning("Impossible de retirer l'ancienne réaction de %s", member.id)
                await post_audit(guild, f"{member.display_name} ({member.id}) a choisi le niveau {level_name}.")
            except (discord.HTTPException, SetupError) as exc:
                log.exception("Attribution du niveau impossible pour %s : %s", member.id, exc)


bot = LabBot()


def is_server_admin(interaction: discord.Interaction) -> bool:
    return (
        interaction.guild is not None
        and interaction.guild.id == TARGET_GUILD_ID
        and isinstance(interaction.user, discord.Member)
        and (
            interaction.user.id == interaction.guild.owner_id
            or interaction.user.id in EXTRA_ADMIN_IDS
            or interaction.user.guild_permissions.administrator
        )
    )


@bot.tree.command(name="installer_lab", description="Installe ou répare les rôles, salons et permissions Lab-HTB.")
@app_commands.guild_only()
async def installer_lab(interaction: discord.Interaction):
    if not is_server_admin(interaction):
        await interaction.response.send_message("Commande réservée au propriétaire ou à un administrateur de Lab-HTB.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild
    lock = bot.setup_locks.setdefault(guild.id, asyncio.Lock())
    if lock.locked():
        await interaction.edit_original_response(content="Une installation est déjà en cours. Réessaie dans un instant.")
        return
    async with lock:
        try:
            bot_member = guild.me or await guild.fetch_member(bot.user.id)
            changes, message = await provision(guild, bot_member)
            bot.state = load_state()
            summary = ", ".join(changes) if changes else "aucun doublon créé ; configuration vérifiée"
            await interaction.edit_original_response(
                content=f"✅ Lab-HTB configuré. {summary}. Message de choix du niveau : {message.jump_url}"
            )
        except (SetupError, discord.Forbidden, discord.HTTPException, OSError) as exc:
            log.exception("Installation Lab-HTB interrompue")
            await interaction.edit_original_response(
                content=f"⚠️ Installation interrompue : {exc}. Les changements déjà faits restent en place ; relance /installer_lab après correction."
            )


@bot.tree.command(name="nommer_encadrant", description="Attribue le rôle Encadrant (propriétaire ou co-administrateur).")
@app_commands.guild_only()
async def nommer_encadrant(interaction: discord.Interaction, membre: discord.Member):
    if (
        interaction.guild is None
        or interaction.guild.id != TARGET_GUILD_ID
        or (interaction.user.id != interaction.guild.owner_id and interaction.user.id not in EXTRA_ADMIN_IDS)
    ):
        await interaction.response.send_message("Seuls le propriétaire et les co-administrateurs de Lab-HTB peuvent nommer un encadrant.", ephemeral=True)
        return
    try:
        role = find_one(interaction.guild.roles, STAFF_ROLE, "rôles")
        if role is None:
            await interaction.response.send_message("Lance d'abord /installer_lab.", ephemeral=True)
            return
        await membre.add_roles(role, reason=f"Nommé encadrant par le propriétaire {interaction.user.id}")
        await interaction.response.send_message(f"✅ {membre.mention} est Encadrant.", ephemeral=True)
    except (discord.HTTPException, SetupError) as exc:
        await interaction.response.send_message(f"Impossible d'attribuer le rôle : {exc}", ephemeral=True)


# ---------------------------------------------------------------------------
# Suivi de progression : labs (validés par un encadrant), modules CJCA, classement XP
# ---------------------------------------------------------------------------


def is_staff_member(member: discord.Member) -> bool:
    return (
        member.guild.id == TARGET_GUILD_ID
        and (
            member.id == member.guild.owner_id
            or member.id in EXTRA_ADMIN_IDS
            or member.guild_permissions.administrator
            or any(role.name == STAFF_ROLE for role in member.roles)
        )
    )


def is_staff(interaction: discord.Interaction) -> bool:
    return interaction.guild is not None and isinstance(interaction.user, discord.Member) and is_staff_member(interaction.user)


def academy_store(state: dict, guild_id: int) -> dict:
    """Données par étudiant : {user_id: {"labs": [...], "modules": {clé: étapes}, "derniere": iso}}."""
    return state.setdefault(str(guild_id), {}).setdefault("academy", {})


def academy_record(state: dict, guild_id: int, user_id: int) -> dict:
    return academy_store(state, guild_id).setdefault(str(user_id), {"labs": [], "modules": {}})


def touch(record: dict) -> None:
    record["derniere"] = datetime.now(timezone.utc).isoformat()


def lab_xp_for(difficulte: str, ia: bool) -> int:
    base = LAB_DIFFICULTIES[difficulte][1]
    return base // 2 if ia else base


def lab_xp(record: dict) -> int:
    return sum(lab["xp"] for lab in record["labs"] if lab["statut"] == "valide")


def module_xp(record: dict) -> int:
    return sum(record["modules"].values()) * XP_PAR_ETAPE


def total_xp(record: dict) -> int:
    return lab_xp(record) + module_xp(record)


def cjca_complete(record: dict) -> bool:
    return all(record["modules"].get(key, 0) == total for key, (_, total) in ACADEMY_MODULES.items())


def find_pending_lab(guild_id: int, message_id: int) -> tuple[str, dict] | None:
    for user_id, record in academy_store(bot.state, guild_id).items():
        for lab in record["labs"]:
            if lab.get("message_id") == message_id:
                return user_id, lab
    return None


def progression_channel(guild: discord.Guild) -> discord.TextChannel | None:
    channel = guild.get_channel(bot.state.get(str(guild.id), {}).get("progression_channel_id", 0))
    return channel if isinstance(channel, discord.TextChannel) else None


def lab_validation_embed(user_id: int, lab: dict, decided_by: str | None = None) -> discord.Embed:
    statut = lab["statut"]
    titles = {"attente": "🧪 Lab à valider", "valide": "✅ Lab validé", "refuse": "❌ Lab refusé"}
    colours = {"attente": 0xFEE75C, "valide": 0x57F287, "refuse": 0xED4245}
    embed = discord.Embed(
        title=titles[statut],
        description=f"<@{user_id}> dit avoir terminé **{lab['nom']}** en entier.",
        colour=discord.Colour(colours[statut]),
    )
    embed.add_field(name="Difficulté", value=LAB_DIFFICULTIES[lab["difficulte"]][0], inline=True)
    embed.add_field(name="IA utilisée", value="Oui" if lab["ia"] else "Non", inline=True)
    embed.add_field(name="XP", value=f"{lab['xp']} XP", inline=True)
    if decided_by:
        embed.add_field(name="Décision", value=f"Par {decided_by}", inline=False)
    footer = "Réagis ✅ pour valider ou ❌ pour refuser." if statut == "attente" else "Décision prise par un encadrant."
    embed.set_footer(text=footer)
    return embed


def classement_embed(guild: discord.Guild) -> discord.Embed:
    scores = sorted(
        (
            (total_xp(record), user_id)
            for user_id, record in academy_store(bot.state, guild.id).items()
            if total_xp(record) > 0
        ),
        reverse=True,
    )
    embed = discord.Embed(title="🏆 Classement du lab", colour=discord.Colour(0xF1C40F))
    embed.description = (
        "\n".join(f"**{rank}.** <@{user_id}> — {xp} XP" for rank, (xp, user_id) in enumerate(scores[:15], start=1))
        or "Aucun XP pour l'instant."
    )
    embed.set_footer(text="Mis à jour automatiquement")
    return embed


async def refresh_classement(guild: discord.Guild) -> None:
    guild_state = bot.state.setdefault(str(guild.id), {})
    channel = guild.get_channel(guild_state.get("classement_channel_id", 0))
    if not isinstance(channel, discord.TextChannel):
        return
    embed = classement_embed(guild)
    message_id = guild_state.get("classement_message_id")
    if message_id:
        try:
            message = await channel.fetch_message(message_id)
            await message.edit(embed=embed)
            return
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            pass
    message = await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())
    guild_state["classement_message_id"] = message.id
    save_state(bot.state)


async def sync_cjca_role(member: discord.Member, record: dict) -> None:
    try:
        role = find_one(member.guild.roles, CJCA_ROLE, "rôles")
        if role is None:
            return
        complete = cjca_complete(record)
        if complete and role not in member.roles:
            await member.add_roles(role, reason="Parcours CJCA terminé")
        elif not complete and role in member.roles:
            await member.remove_roles(role, reason="Parcours CJCA non terminé")
    except (discord.HTTPException, SetupError) as exc:
        log.warning("Rôle CJCA non mis à jour pour %s : %s", member.id, exc)


async def handle_lab_validation(payload: discord.RawReactionActionEvent) -> None:
    emoji = str(payload.emoji)
    if emoji not in {"✅", "❌"}:
        return
    guild = bot.get_guild(payload.guild_id)
    if guild is None:
        return
    channel = guild.get_channel(payload.channel_id)
    if not isinstance(channel, discord.TextChannel):
        return
    try:
        member = payload.member or await guild.fetch_member(payload.user_id)
        message = await channel.fetch_message(payload.message_id)
    except discord.HTTPException:
        return

    if not is_staff_member(member):
        try:
            await message.remove_reaction(payload.emoji, member)
        except discord.HTTPException:
            log.warning("Impossible de retirer la réaction de %s", member.id)
        return

    found = find_pending_lab(guild.id, payload.message_id)
    if found is None:
        return
    user_id, lab = found
    if lab["statut"] != "attente":
        return
    lab["statut"] = "valide" if emoji == "✅" else "refuse"
    touch(academy_record(bot.state, guild.id, int(user_id)))
    save_state(bot.state)

    try:
        await message.edit(embed=lab_validation_embed(int(user_id), lab, decided_by=member.display_name))
    except discord.HTTPException:
        log.warning("Impossible de mettre à jour le message de validation du lab")
    progress = progression_channel(guild)
    if progress is not None:
        if lab["statut"] == "valide":
            texte = f"<@{user_id}> : lab **{lab['nom']}** validé, +{lab['xp']} XP."
        else:
            texte = f"<@{user_id}> : lab **{lab['nom']}** non validé. Parle à un encadrant si besoin."
        await progress.send(texte, allowed_mentions=discord.AllowedMentions.none())
    await refresh_classement(guild)


@bot.tree.command(name="lab", description="Déclare un lab Hack The Box terminé en entier (validé par un encadrant).")
@app_commands.guild_only()
@app_commands.describe(nom="Nom du lab", difficulte="Difficulté du lab", ia="As-tu utilisé l'IA pour ce lab ?")
@app_commands.choices(difficulte=[
    app_commands.Choice(name=label, value=key) for key, (label, _) in LAB_DIFFICULTIES.items()
])
@app_commands.choices(ia=[
    app_commands.Choice(name="Oui", value="oui"),
    app_commands.Choice(name="Non", value="non"),
])
async def enregistrer_lab(interaction: discord.Interaction, nom: app_commands.Range[str, 1, 60],
                          difficulte: app_commands.Choice[str], ia: app_commands.Choice[str]):
    guild = interaction.guild
    validation_channel = guild.get_channel(LAB_VALIDATION_CHANNEL_ID)
    if not isinstance(validation_channel, discord.TextChannel):
        await interaction.response.send_message("Le salon de validation est introuvable. Préviens un encadrant.", ephemeral=True)
        return
    record = academy_record(bot.state, guild.id, interaction.user.id)
    lab_name = nom.strip()
    same_name = [lab for lab in record["labs"] if lab["nom"].lower() == lab_name.lower()]
    if any(lab["statut"] == "valide" for lab in same_name):
        await interaction.response.send_message(f"Tu as déjà validé le lab « {lab_name} ».", ephemeral=True)
        return
    if any(lab["statut"] == "attente" for lab in same_name):
        await interaction.response.send_message(f"Le lab « {lab_name} » est déjà en attente de validation.", ephemeral=True)
        return

    utilise_ia = ia.value == "oui"
    lab = {
        "nom": lab_name,
        "difficulte": difficulte.value,
        "ia": utilise_ia,
        "xp": lab_xp_for(difficulte.value, utilise_ia),
        "statut": "attente",
        "message_id": None,
    }
    try:
        message = await validation_channel.send(
            embed=lab_validation_embed(interaction.user.id, lab),
            allowed_mentions=discord.AllowedMentions.none(),
        )
    except discord.HTTPException:
        await interaction.response.send_message("Impossible d'envoyer la demande de validation. Réessaie ou préviens un encadrant.", ephemeral=True)
        return
    lab["message_id"] = message.id
    for old in same_name:
        record["labs"].remove(old)
    record["labs"].append(lab)
    touch(record)
    save_state(bot.state)
    await message.add_reaction("✅")
    await message.add_reaction("❌")

    base = LAB_DIFFICULTIES[difficulte.value][1]
    calcul = f"{difficulte.name} = {base} XP"
    if utilise_ia:
        calcul += f", divisé par 2 car tu as utilisé l'IA → {lab['xp']} XP"
    await interaction.response.send_message(
        f"🧪 « {lab_name} » envoyé aux encadrants pour validation.\n"
        f"Calcul : {calcul}. Tu recevras cet XP une fois le lab validé.",
        ephemeral=True,
    )


@bot.tree.command(name="module", description="Enregistre ton avancement dans un module CJCA (5 XP par étape).")
@app_commands.guild_only()
@app_commands.describe(parcours="Parcours suivi", module="Module concerné", etapes="Nombre d'étapes faites dans ce module")
@app_commands.choices(parcours=[app_commands.Choice(name="CJCA", value="CJCA")])
@app_commands.choices(module=[
    app_commands.Choice(name=f"{nom} ({total})", value=key) for key, (nom, total) in ACADEMY_MODULES.items()
])
async def enregistrer_module(interaction: discord.Interaction, parcours: app_commands.Choice[str],
                             module: app_commands.Choice[str], etapes: app_commands.Range[int, 0, 100]):
    nom, total = ACADEMY_MODULES[module.value]
    if etapes > total:
        await interaction.response.send_message(f"« {nom} » ne compte que {total} étapes.", ephemeral=True)
        return
    record = academy_record(bot.state, interaction.guild.id, interaction.user.id)
    was_complete = cjca_complete(record)
    if etapes == 0:
        record["modules"].pop(module.value, None)
    else:
        record["modules"][module.value] = etapes
    touch(record)
    save_state(bot.state)

    xp = etapes * XP_PAR_ETAPE
    termine = etapes == total
    await interaction.response.send_message(
        f"✅ {nom} : {etapes}/{total} — {xp} XP sur ce module." + (" Module terminé !" if termine else ""),
        ephemeral=True,
    )
    channel = progression_channel(interaction.guild)
    if channel is not None:
        embed = discord.Embed(
            title=f"📘 Avancement {parcours.value}",
            description=(
                f"{interaction.user.mention} : **{nom}** — {etapes}/{total} ({xp} XP)"
                + (" ✅ terminé" if termine else "")
            ),
            colour=discord.Colour(0x3498DB),
        )
        await channel.send(embed=embed, allowed_mentions=discord.AllowedMentions.none())

    await sync_cjca_role(interaction.user, record)
    if not was_complete and cjca_complete(record) and channel is not None:
        await channel.send(
            f"🎓 {interaction.user.mention} a terminé le parcours CJCA et reçoit le rôle **{CJCA_ROLE}** !",
            allowed_mentions=discord.AllowedMentions.none(),
        )
    await refresh_classement(interaction.guild)


@bot.tree.command(name="classement", description="Affiche le classement XP des étudiants.")
@app_commands.guild_only()
async def classement(interaction: discord.Interaction):
    await interaction.response.send_message(embed=classement_embed(interaction.guild), allowed_mentions=discord.AllowedMentions.none())
    await refresh_classement(interaction.guild)


@bot.tree.command(name="avance", description="Affiche les labs et modules d'un étudiant (encadrants).")
@app_commands.guild_only()
@app_commands.describe(membre="Étudiant à consulter")
async def avance(interaction: discord.Interaction, membre: discord.Member):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    record = academy_store(bot.state, interaction.guild.id).get(str(membre.id), {"labs": [], "modules": {}})
    embed = discord.Embed(
        title=f"📊 Avancement de {membre.display_name}",
        description=f"XP total : **{total_xp(record)}** ({lab_xp(record)} labs · {module_xp(record)} modules)",
        colour=discord.Colour(0x5865F2),
    )

    lab_lines = []
    for lab in record["labs"]:
        statut = {"valide": "validé", "attente": "en attente", "refuse": "refusé"}[lab["statut"]]
        xp = f"{lab['xp']} XP" if lab["statut"] == "valide" else "0 XP"
        lab_lines.append(
            f"• {lab['nom']} — {LAB_DIFFICULTIES[lab['difficulte']][0]} — IA {'oui' if lab['ia'] else 'non'} — {statut} ({xp})"
        )
    embed.add_field(name=f"Labs ({len(record['labs'])})", value=("\n".join(lab_lines) or "Aucun lab déclaré.")[:1024], inline=False)

    module_lines = []
    for key, fait in record["modules"].items():
        nom, total = ACADEMY_MODULES[key]
        icone = "✅" if fait == total else "▶️"
        module_lines.append(f"{icone} {nom} — {fait}/{total} ({fait * XP_PAR_ETAPE} XP)")
    embed.add_field(name="Modules CJCA", value=("\n".join(module_lines) or "Aucun module commencé.")[:1024], inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)


corriger = app_commands.Group(name="corriger", description="Corrige un lab ou un module d'un étudiant (encadrants).", guild_only=True)
bot.tree.add_command(corriger)


@corriger.command(name="lab", description="Valide, refuse ou supprime un lab d'un étudiant.")
@app_commands.describe(membre="Étudiant concerné", nom="Nom du lab", action="Action à appliquer")
@app_commands.choices(action=[
    app_commands.Choice(name="Valider", value="valider"),
    app_commands.Choice(name="Refuser", value="refuser"),
    app_commands.Choice(name="Supprimer", value="supprimer"),
])
async def corriger_lab(interaction: discord.Interaction, membre: discord.Member,
                       nom: app_commands.Range[str, 1, 60], action: app_commands.Choice[str]):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    record = academy_record(bot.state, interaction.guild.id, membre.id)
    lab = next((item for item in record["labs"] if item["nom"].lower() == nom.strip().lower()), None)
    if lab is None:
        await interaction.response.send_message(f"Aucun lab « {nom} » pour {membre.display_name}.", ephemeral=True)
        return
    if action.value == "supprimer":
        record["labs"].remove(lab)
        message = f"Lab « {lab['nom']} » supprimé pour {membre.display_name}."
    else:
        lab["statut"] = "valide" if action.value == "valider" else "refuse"
        message = f"Lab « {lab['nom']} » passé en « {lab['statut']} » pour {membre.display_name}."
    touch(record)
    save_state(bot.state)
    await interaction.response.send_message(message, ephemeral=True)
    await refresh_classement(interaction.guild)


@corriger.command(name="module", description="Corrige le nombre d'étapes faites dans un module.")
@app_commands.describe(membre="Étudiant concerné", module="Module à corriger", etapes="Nouveau nombre d'étapes (0 pour effacer)")
@app_commands.choices(module=[
    app_commands.Choice(name=f"{nom} ({total})", value=key) for key, (nom, total) in ACADEMY_MODULES.items()
])
async def corriger_module(interaction: discord.Interaction, membre: discord.Member,
                          module: app_commands.Choice[str], etapes: app_commands.Range[int, 0, 100]):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    nom, total = ACADEMY_MODULES[module.value]
    if etapes > total:
        await interaction.response.send_message(f"« {nom} » ne compte que {total} étapes.", ephemeral=True)
        return
    record = academy_record(bot.state, interaction.guild.id, membre.id)
    if etapes == 0:
        record["modules"].pop(module.value, None)
    else:
        record["modules"][module.value] = etapes
    touch(record)
    save_state(bot.state)
    await interaction.response.send_message(f"✅ {nom} pour {membre.display_name} : {etapes}/{total}.", ephemeral=True)
    await sync_cjca_role(membre, record)
    await refresh_classement(interaction.guild)


@bot.tree.command(name="export", description="Exporte l'avancement de tous les étudiants en CSV (encadrants).")
@app_commands.guild_only()
async def exporter(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    guild = interaction.guild
    entetes = [
        "membre", "id", "xp_total", "xp_labs", "xp_modules",
        "labs_valides", "labs_en_attente", "labs_refuses", "labs_valides_avec_ia",
        *(f"{nom} ({total})" for nom, total in ACADEMY_MODULES.values()),
    ]
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow(entetes)
    for user_id, record in academy_store(bot.state, guild.id).items():
        member = guild.get_member(int(user_id))
        labs = record["labs"]
        writer.writerow([
            member.display_name if member else "(absent du serveur)",
            user_id,
            total_xp(record),
            lab_xp(record),
            module_xp(record),
            sum(1 for lab in labs if lab["statut"] == "valide"),
            sum(1 for lab in labs if lab["statut"] == "attente"),
            sum(1 for lab in labs if lab["statut"] == "refuse"),
            sum(1 for lab in labs if lab["statut"] == "valide" and lab["ia"]),
            *(record["modules"].get(key, 0) for key in ACADEMY_MODULES),
        ])
    fichier = discord.File(io.BytesIO(buffer.getvalue().encode("utf-8-sig")), filename="avancement-lab.csv")
    await interaction.response.send_message("Export prêt.", file=fichier, ephemeral=True)


def _short_list(items: list[str], empty: str, limit: int = 700) -> str:
    """Liste compacte qui reste sous la limite d'un champ Discord."""
    if not items:
        return empty
    result = ", ".join(items)
    return result if len(result) <= limit else result[:limit - 1].rstrip(", ") + "…"


def class_student_row(member: discord.Member, record: dict) -> dict:
    labs = record.get("labs", [])
    modules = record.get("modules", {})
    validated = sorted(
        (lab["nom"] for lab in labs if lab.get("statut") == "valide"),
        key=str.casefold,
    )
    pending = sum(1 for lab in labs if lab.get("statut") == "attente")
    refused = sum(1 for lab in labs if lab.get("statut") == "refuse")
    completed_modules = sorted(
        (
            name for key, (name, total) in ACADEMY_MODULES.items()
            if modules.get(key, 0) >= total
        ),
        key=str.casefold,
    )
    started_modules = sum(1 for key in ACADEMY_MODULES if modules.get(key, 0) > 0)
    completed_steps = sum(min(modules.get(key, 0), total) for key, (_, total) in ACADEMY_MODULES.items())
    total_steps = sum(total for _, total in ACADEMY_MODULES.values())
    has_activity = bool(labs or modules)
    if not has_activity:
        status = "🔴 aucune activité enregistrée"
    elif pending:
        status = f"🟠 {pending} lab(s) en attente de validation"
    else:
        status = "🟢 activité enregistrée"
    return {
        "member": member,
        "record": record,
        "validated": validated,
        "pending": pending,
        "refused": refused,
        "completed_modules": completed_modules,
        "started_modules": started_modules,
        "completed_steps": completed_steps,
        "total_steps": total_steps,
        "has_activity": has_activity,
        "status": status,
        "xp": total_xp(record),
    }


def class_report_embeds(guild: discord.Guild, rows: list[dict], complete_roster: bool = True) -> list[discord.Embed]:
    active = sum(1 for row in rows if row["has_activity"])
    inactive = len(rows) - active
    total_validated = sum(len(row["validated"]) for row in rows)
    total_completed_modules = sum(len(row["completed_modules"]) for row in rows)
    summary = discord.Embed(
        title="🎓 Bilan de la classe — Lab-HTB",
        description=(
            ("Vue de fin de cours de tous les membres ayant le rôle **Étudiant**. " if complete_roster else
             "Mode test : étudiants déjà présents dans le suivi du bot. ")
            + "Les labs comptés comme faits sont uniquement ceux qui ont été validés par un encadrant."
        ),
        colour=discord.Colour(0x5865F2),
        timestamp=datetime.now(timezone.utc),
    )
    summary.add_field(name="👥 Étudiants", value=str(len(rows)), inline=True)
    summary.add_field(name="✅ Avec activité", value=str(active), inline=True)
    summary.add_field(name="⚠️ Sans activité", value=str(inactive), inline=True)
    summary.add_field(name="🧪 Labs validés", value=str(total_validated), inline=True)
    summary.add_field(name="📘 Modules terminés", value=str(total_completed_modules), inline=True)
    summary.add_field(
        name="⭐ XP moyen",
        value=f"{round(sum(row['xp'] for row in rows) / len(rows)) if rows else 0} XP",
        inline=True,
    )
    summary.set_footer(text=f"{guild.name} • rapport privé • {len(rows)} étudiant(s)")

    embeds = [summary]
    page_size = 5
    for start in range(0, len(rows), page_size):
        page_rows = rows[start:start + page_size]
        page = discord.Embed(
            title=f"📋 Détail des étudiants — page {start // page_size + 1}",
            colour=discord.Colour(0x2B2D31),
        )
        for row in page_rows:
            member = row["member"]
            labs = _short_list(row["validated"], "Aucun lab validé")
            modules = _short_list(row["completed_modules"], "Aucun module terminé", 500)
            page.add_field(
                name=f"{row['status'].split()[0]} {member.display_name}"[:256],
                value=(
                    f"**Labs validés ({len(row['validated'])}) :** {labs}\n"
                    f"**Labs à vérifier :** {row['pending']} en attente · {row['refused']} refusé(s)\n"
                    f"**Modules :** {len(row['completed_modules'])}/{len(ACADEMY_MODULES)} terminés "
                    f"· {row['started_modules']} commencés · {row['completed_steps']}/{row['total_steps']} étapes\n"
                    f"**Terminés :** {modules}\n"
                    f"**Total :** {row['xp']} XP · {row['status']}"
                )[:1024],
                inline=False,
            )
        embeds.append(page)
    return embeds


def class_report_csv(rows: list[dict]) -> discord.File:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=";")
    writer.writerow([
        "etudiant", "discord_id", "statut", "xp", "labs_valides", "noms_labs_valides",
        "labs_en_attente", "labs_refuses", "modules_termines", "modules_commences",
        "etapes_realisees", "etapes_totales", "noms_modules_termines", "derniere_activite",
    ])
    for row in rows:
        member = row["member"]
        writer.writerow([
            member.display_name,
            member.id,
            row["status"],
            row["xp"],
            len(row["validated"]),
            " | ".join(row["validated"]),
            row["pending"],
            row["refused"],
            len(row["completed_modules"]),
            row["started_modules"],
            row["completed_steps"],
            row["total_steps"],
            " | ".join(row["completed_modules"]),
            row["record"].get("derniere", ""),
        ])
    return discord.File(
        io.BytesIO(buffer.getvalue().encode("utf-8-sig")),
        filename="bilan-classe-lab-htb.csv",
    )


@bot.tree.command(name="bilan_classe", description="Bilan privé des labs et modules de toute la classe (encadrants).")
@app_commands.guild_only()
async def bilan_classe(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    await interaction.response.defer(ephemeral=True, thinking=True)
    guild = interaction.guild
    student_role = find_one(guild.roles, STUDENT_ROLE, "rôles")
    if student_role is None:
        await interaction.edit_original_response(content="Le rôle Étudiant est introuvable. Lance d'abord /installer_lab.")
        return
    academy = academy_store(bot.state, guild.id)
    complete_roster = MEMBERS_INTENT_ENABLED
    if complete_roster:
        try:
            all_members = [member async for member in guild.fetch_members(limit=None)]
        except (discord.Forbidden, discord.HTTPException) as exc:
            log.exception("Lecture de la classe impossible : %s", exc)
            await interaction.edit_original_response(
                content=(
                    "Impossible de lire toute la classe. Vérifie **Server Members Intent** dans "
                    "Discord Developer Portal > HTB Bot > Bot, puis redémarre le bot."
                )
            )
            return
        students = [member for member in all_members if not member.bot and student_role in member.roles]
    else:
        students = []
        for user_id in academy:
            try:
                member = guild.get_member(int(user_id)) or await guild.fetch_member(int(user_id))
            except (discord.NotFound, discord.Forbidden, discord.HTTPException):
                continue
            if not member.bot and student_role in member.roles:
                students.append(member)

    empty_record = {"labs": [], "modules": {}}
    rows = [class_student_row(member, academy.get(str(member.id), empty_record)) for member in students]
    # Les étudiants sans activité apparaissent en premier, puis la liste est alphabétique.
    rows.sort(key=lambda row: (row["has_activity"], row["member"].display_name.casefold()))
    embeds = class_report_embeds(guild, rows, complete_roster)
    report_file = class_report_csv(rows)

    chunks = [embeds[index:index + 10] for index in range(0, len(embeds), 10)] or [[]]
    await interaction.edit_original_response(
        content=(
            "Bilan complet généré. Le fichier CSV contient une ligne par étudiant."
            if complete_roster else
            "Bilan de test généré avec les étudiants déjà suivis. Pour inclure les étudiants sans activité, "
            "active Server Members Intent puis ajoute `DISCORD_MEMBERS_INTENT=true` dans `.env`."
        ),
        embeds=chunks[0],
        attachments=[report_file],
        allowed_mentions=discord.AllowedMentions.none(),
    )
    for chunk in chunks[1:]:
        await interaction.followup.send(
            embeds=chunk,
            ephemeral=True,
            allowed_mentions=discord.AllowedMentions.none(),
        )


@bot.tree.command(name="retard", description="Liste les étudiants sans activité depuis X jours (encadrants).")
@app_commands.guild_only()
@app_commands.describe(jours="Nombre de jours sans activité")
async def retard(interaction: discord.Interaction, jours: app_commands.Range[int, 1, 365] = 7):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    guild = interaction.guild
    maintenant = datetime.now(timezone.utc)
    en_retard = []
    for user_id, record in academy_store(bot.state, guild.id).items():
        member = guild.get_member(int(user_id))
        if member is None:
            continue
        derniere = record.get("derniere")
        sans_activite = (maintenant - datetime.fromisoformat(derniere)).days if derniere else None
        if sans_activite is not None and sans_activite < jours:
            continue
        en_retard.append((sans_activite if sans_activite is not None else 10**6, member.display_name, sans_activite))
    en_retard.sort(reverse=True)

    embed = discord.Embed(title=f"⏰ Étudiants sans activité depuis {jours} jour(s)", colour=discord.Colour(0xED4245))
    if en_retard:
        embed.description = "\n".join(
            f"• {nom} — " + (f"{jours_sans} jour(s)" if jours_sans is not None else "aucune activité enregistrée")
            for _, nom, jours_sans in en_retard
        )
    else:
        embed.description = "Aucun étudiant en retard."
    embed.set_footer(text="Seuls les étudiants ayant déjà utilisé /lab ou /module apparaissent ici.")
    await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.tree.command(name="stats", description="Statistiques des labs et modules du lab (encadrants).")
@app_commands.guild_only()
async def statistiques(interaction: discord.Interaction):
    if not is_staff(interaction):
        await interaction.response.send_message("Commande réservée aux encadrants.", ephemeral=True)
        return
    records = list(academy_store(bot.state, interaction.guild.id).values())
    labs = [lab for record in records for lab in record["labs"]]
    valides = [lab for lab in labs if lab["statut"] == "valide"]
    avec_ia = sum(1 for lab in valides if lab["ia"])

    embed = discord.Embed(title="📊 Statistiques du lab", colour=discord.Colour(0x5865F2))
    embed.add_field(name="Étudiants suivis", value=str(len(records)), inline=True)
    embed.add_field(name="XP moyen", value=f"{round(sum(total_xp(r) for r in records) / len(records)) if records else 0} XP", inline=True)
    embed.add_field(
        name="Labs",
        value=(
            f"{len(valides)} validés · "
            f"{sum(1 for lab in labs if lab['statut'] == 'attente')} en attente · "
            f"{sum(1 for lab in labs if lab['statut'] == 'refuse')} refusés"
        ),
        inline=False,
    )
    if valides:
        embed.add_field(name="Labs validés avec IA", value=f"{round(100 * avec_ia / len(valides))} %", inline=True)
    embed.description = "\n".join(
        f"**{nom}** — {sum(1 for r in records if r['modules'].get(key, 0) == total)} terminé(s), "
        f"{sum(1 for r in records if r['modules'].get(key, 0) > 0)} commencé(s)"
        for key, (nom, total) in ACADEMY_MODULES.items()
    )
    await interaction.response.send_message(embed=embed, ephemeral=True)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if not TOKEN or TOKEN.startswith("COLLER_"):
        raise SystemExit("Ajoute DISCORD_TOKEN dans le fichier .env avant de lancer le bot.")
    bot.run(TOKEN, log_handler=None)
