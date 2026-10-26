"""Plan et textes du serveur Lab-HTB. Aucun appel à Discord dans ce fichier."""

from dataclasses import dataclass
import os

GUILD_ID = int(os.getenv("GUILD_ID", "0"))
APPLICATION_ID = int(os.getenv("APPLICATION_ID", "0"))
# Co-administrateurs (profs) : mêmes droits que le propriétaire pour les commandes du bot.
EXTRA_ADMIN_IDS = tuple(int(value.strip()) for value in os.getenv("EXTRA_ADMIN_IDS", "").split(",") if value.strip())

STUDENT_ROLE = "Étudiant"
STAFF_ROLE = "Encadrant"
LEVELS = {
    "🟢": ("Débutant", 0x2ECC71),
    "🔵": ("Intermédiaire", 0x3498DB),
    "🟣": ("Avancé", 0x9B59B6),
}

# Difficultés des labs : clé -> (libellé, XP de base). Avec l'IA, l'XP est divisée par 2.
LAB_DIFFICULTIES = {
    "very-easy": ("Very Easy", 10),
    "easy": ("Easy", 20),
    "medium": ("Medium", 30),
    "hard": ("Hard", 40),
    "insane": ("Insane", 50),
}
# XP gagnée pour chaque étape validée d'un module CJCA.
XP_PAR_ETAPE = 5
# Salon réservé aux encadrants : chaque lab déclaré y est soumis à validation par réaction.
LAB_VALIDATION_CHANNEL_ID = int(os.getenv("LAB_VALIDATION_CHANNEL_ID", "0"))
# Rôle donné automatiquement quand les 20 modules CJCA sont terminés.
CJCA_ROLE = "CJCA terminé"
CJCA_ROLE_COLOUR = 0x1ABC9C

WELCOME_CATEGORY = "👋 ACCUEIL"
LAB_CATEGORY = "🧪 LAB HTB"
CHAT_CATEGORY = "💬 DISCUSSIONS"
VOICE_CATEGORY = "🔊 VOCAL"
STAFF_CATEGORY = "🔐 ADMINISTRATION"


@dataclass(frozen=True)
class TextChannelSpec:
    category: str
    name: str
    topic: str
    access: str  # public, student, staff
    writable: bool = True
    reactions: bool = False
    icon: str = "▫️"

    @property
    def discord_name(self) -> str:
        return f"{self.icon}・{self.name}"


@dataclass(frozen=True)
class ChannelGuide:
    icon: str
    title: str
    purpose: str
    usage: str
    example: str
    colour: int


TEXT_CHANNELS = (
    TextChannelSpec(WELCOME_CATEGORY, "bienvenue", "Point de départ du lab et accès aux salons étudiants.", "public", False, icon="👋"),
    TextChannelSpec(WELCOME_CATEGORY, "guide-du-serveur", "Plan complet du serveur et rôle de chaque salon.", "public", False, icon="🧭"),
    TextChannelSpec(WELCOME_CATEGORY, "règles", "Règles de travail et de partage du lab.", "public", False, icon="🛡️"),
    TextChannelSpec(WELCOME_CATEGORY, "annonces", "Informations publiées par les encadrants.", "public", False, icon="📢"),
    TextChannelSpec(WELCOME_CATEGORY, "choix-du-niveau", "Réagis au message du bot pour choisir ton niveau et accéder au lab.", "public", False, True, "🎯"),
    TextChannelSpec(LAB_CATEGORY, "consignes", "Objectifs et consignes du lab Hack The Box.", "student", False, icon="📋"),
    TextChannelSpec(LAB_CATEGORY, "machines", "Liste et informations des machines proposées.", "student", False, icon="🖥️"),
    TextChannelSpec(LAB_CATEGORY, "ressources", "Liens et supports utiles au lab.", "student", False, icon="📚"),
    TextChannelSpec(LAB_CATEGORY, "entraide", "Questions et indices sans divulguer les flags.", "student", True, icon="🧩"),
    TextChannelSpec(LAB_CATEGORY, "progression", "Suivi de l'avancement des étudiants.", "student", True, icon="📈"),
    TextChannelSpec(LAB_CATEGORY, "avance", "Étapes validées par les encadrants, publiées automatiquement par le bot.", "student", False, icon="🚀"),
    TextChannelSpec(LAB_CATEGORY, "classement", "Résultats et points publiés par les encadrants ou le bot.", "student", False, icon="🏆"),
    TextChannelSpec(CHAT_CATEGORY, "général", "Discussion de l'équipe Lab-HTB.", "student", True, icon="💬"),
    TextChannelSpec(STAFF_CATEGORY, "équipe", "Échanges privés entre encadrants.", "staff", True, icon="🔐"),
    TextChannelSpec(STAFF_CATEGORY, "commandes", "Toutes les commandes du bot et ce qu'elles font.", "staff", False, icon="📖"),
    TextChannelSpec(STAFF_CATEGORY, "journal-bot", "Suivi des actions du bot.", "staff", False, icon="🤖"),
)

# Modules du parcours CJCA : clé -> (nom, nombre d'étapes à valider).
ACADEMY_MODULES = {
    "info-securite": ("Introduction to Information Security", 24),
    "fondations-reseau": ("Network Foundations", 12),
    "intro-reseaux": ("Introduction to Networking", 21),
    "linux": ("Linux Fundamentals", 30),
    "bash": ("Introduction to Bash Scripting", 10),
    "windows": ("Windows Fundamentals", 15),
    "windows-cmd": ("Introduction to Windows Command Line", 23),
    "web-requests": ("Web Requests", 8),
    "intro-web": ("Introduction to Web Applications", 17),
    "intro-pentest": ("Introduction to Penetration Testing", 21),
    "pentest-nutshell": ("Pentest in a Nutshell", 24),
    "nmap": ("Network Enumeration with Nmap", 12),
    "footprinting": ("Footprinting", 21),
    "wordpress": ("Hacking WordPress", 16),
    "metasploit": ("Using the Metasploit Framework", 15),
    "trafic-reseau": ("Intro to Network Traffic Analysis", 15),
    "incident": ("Incident Handling Process", 11),
    "windows-logs": ("Windows Event Logs & Finding Evil", 6),
    "siem": ("Security Monitoring & SIEM Fundamentals", 11),
    "threat-hunting": ("Introduction to Threat Hunting", 6),
}

VOICE_CHANNELS = (
    ("Général", "💬・Général"),
    ("Entraide", "🧩・Entraide"),
)


CHANNEL_GUIDES = {
    "bienvenue": ChannelGuide("👋", "Bienvenue dans le Lab HTB", "Le point de départ de tous les membres.", "Lis les informations essentielles, consulte le guide, puis choisis ton niveau.", "Parcours #guide-du-serveur → lis #règles → rends-toi dans #choix-du-niveau.", 0x57F287),
    "guide-du-serveur": ChannelGuide("🧭", "Guide du serveur", "La carte complète de Lab-HTB.", "Retrouve rapidement le bon salon selon ce que tu veux faire.", "Besoin d'un indice ? Le guide t'oriente vers #entraide.", 0x5865F2),
    "règles": ChannelGuide("🛡️", "Règles du lab", "Le cadre de travail commun et les règles de sécurité.", "Lis-les avant de commencer. Elles s'appliquent à tous les membres.", "Ne partage jamais un flag, un mot de passe, un jeton ou une solution complète.", 0xED4245),
    "annonces": ChannelGuide("📢", "Annonces", "Les informations officielles publiées par les encadrants.", "Consulte ce salon pour les dates, changements, nouvelles machines et rappels.", "Ouverture d'une nouvelle machine ou changement d'horaire du lab.", 0xFEE75C),
    "choix-du-niveau": ChannelGuide("🎯", "Choisis ton niveau", "Débloque les salons du lab et affiche ton niveau actuel.", "Réagis au message ci-dessous avec un seul emoji. Tu peux changer plus tard.", "🟢 Débutant · 🔵 Intermédiaire · 🟣 Avancé", 0x9B59B6),
    "consignes": ChannelGuide("📋", "Consignes", "Les objectifs, livrables et étapes du projet.", "Vérifie ce salon avant chaque session pour savoir ce qui est demandé.", "Objectif du jour, format du compte rendu et date de rendu.", 0x3498DB),
    "machines": ChannelGuide("🖥️", "Machines", "Le catalogue des machines autorisées pour le lab.", "Les encadrants y indiquent la cible, la difficulté, le statut et les points.", "Machine : Lame · difficulté : facile · statut : active.", 0x2ECC71),
    "ressources": ChannelGuide("📚", "Ressources", "Les outils, cours, documentations et fiches utiles.", "Consulte les ressources avant de demander de l'aide et partage des liens fiables.", "Documentation Nmap, aide-mémoire Linux ou méthode de prise de notes.", 0x1ABC9C),
    "entraide": ChannelGuide("🧩", "Entraide", "Le salon pour poser une question ou donner un indice.", "Indique la machine, ce que tu as essayé et l'erreur rencontrée, sans révéler la solution.", "Machine Lame — mon scan ne détecte aucun service après telle commande.", 0xE67E22),
    "progression": ChannelGuide("📈", "Progression", "Le suivi des étapes terminées par chaque étudiant.", "Publie une mise à jour courte après une avancée importante.", "Machine Lame : accès initial obtenu, élévation de privilèges en cours.", 0x57F287),
    "avance": ChannelGuide("🚀", "Suivi de l'avancement", "Le mode d'emploi pour enregistrer tes labs et tes modules.", "Utilise /lab pour un lab terminé et /module pour tes étapes CJCA. Le classement est dans #classement.", "/lab nom:Lame difficulte:Easy ia:Non", 0xE67E22),
    "classement": ChannelGuide("🏆", "Classement", "Le tableau des points et résultats du lab.", "Consulte les scores publiés par le bot ou les encadrants.", "Les points récompensent les objectifs validés selon le barème du projet.", 0xF1C40F),
    "général": ChannelGuide("💬", "Discussion générale", "L'espace convivial de l'équipe Lab-HTB.", "Échange sur le projet et l'organisation. Utilise #entraide pour les problèmes techniques.", "Former un groupe de travail ou discuter de la prochaine séance.", 0x5865F2),
    "équipe": ChannelGuide("🔐", "Espace des encadrants", "La coordination privée de l'équipe pédagogique.", "Prépare les activités, échange sur le suivi et organise les annonces.", "Choisir les prochaines machines ou valider les points.", 0xE91E63),
    "commandes": ChannelGuide("📖", "Commandes du bot", "La liste de toutes les commandes et de leur effet.", "Consulte ce salon pour savoir quelle commande utiliser.", "/avance membre:@étudiant pour voir son bilan.", 0x5865F2),
    "journal-bot": ChannelGuide("🤖", "Journal du bot", "L'historique technique des actions importantes du bot.", "Utilise ces informations pour suivre les installations et changements de niveau.", "Installation terminée ou attribution d'un rôle de niveau.", 0x95A5A6),
}

WELCOME_MESSAGE_MARKER = "Bienvenue sur Lab-HTB !"
RULES_MESSAGE_MARKER = "Règles du lab Lab-HTB"
LEVEL_MESSAGE_MARKER = "Lab-HTB • choix du niveau"
