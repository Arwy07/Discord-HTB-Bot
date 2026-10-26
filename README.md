# Discord HTB Bot

Bot Discord en Python pour organiser un espace de formation Hack The Box et suivre la progression des participants. Il configure rôles et salons, enregistre les labs et modules CJCA et propose une validation par les encadrants. Il n'utilise pas l'API Hack The Box.

## Fonctionnalités

| Commande | Usage |
|---|---|
| `/installer_lab` | Installation ou remise en place des espaces du serveur |
| `/nommer_encadrant` | Attribution du rôle d'encadrement |
| `/lab` | Déclaration d'un lab pour validation |
| `/module` | Suivi des étapes d'un module CJCA |
| `/classement` | Classement par XP |
| `/avance`, `/corriger` | Consultation et correction par les encadrants |
| `/export`, `/retard`, `/stats` | Suivi pédagogique et export |

## Installation

Prérequis : Python 3.11 ou ultérieur et une application Discord de test.

```sh
git clone https://github.com/Arwy07/Discord-HTB-Bot.git
cd Discord-HTB-Bot
python -m venv .venv
```

Activer l'environnement (`.venv\Scripts\activate` sous Windows ; `source .venv/bin/activate` sous Linux), puis :

```sh
python -m pip install -r requirements.txt
```

Copier `.env.example` en `.env` et renseigner le token, les identifiants du serveur, de l'application et du salon de validation. `EXTRA_ADMIN_IDS` accepte une liste d'identifiants séparés par des virgules ; la liste est vide par défaut. Ne jamais versionner `.env`.

Inviter l'application avec les scopes `bot` et `applications.commands`. Prévoir les permissions correspondant aux fonctions utilisées : gérer les rôles et salons, lire/envoyer des messages, lire l'historique, gérer les messages et ajouter des réactions. Placer son rôle au-dessus des rôles qu'elle doit attribuer. L'intent membres est optionnel : activer `DISCORD_MEMBERS_INTENT=true` uniquement s'il est également autorisé dans le portail Discord.

```sh
python bot.py
```

Tester `/installer_lab` sur un serveur dédié : cette commande applique des permissions et peut renommer des catégories existantes. Configurer ensuite le salon de validation avant de déclarer un lab.

## Organisation et données

- `bot.py` : commandes, permissions, validation et persistance.
- `server_plan.py` : rôles, salons, modules et barèmes.
- `.env.example` : configuration sans valeur réelle.
- `state.json` : créé à l'exécution ; état privé du serveur et progression, exclu de Git.

Les exports CSV et fichiers d'état peuvent contenir des identifiants Discord et des données pédagogiques. Les conserver dans un espace restreint, avec une durée de conservation adaptée. Ce dépôt ne contient aucun état étudiant ni export réel.

## Version et limites

Import issu de la version locale PC `maj_6` du 21 octobre 2026, avec configuration des identifiants externalisée. Cette archive conserve le paramètre d'utilisation de l'IA et son ancien barème : la demande ultérieure de retrait de ce paramètre n'est pas intégrée dans les sources retrouvées. Aucun ancien état n'a été migré ni modifié sur le serveur en service.

Validation hors connexion consignée dans [VALIDATION.md](VALIDATION.md). Une recette Discord sur un serveur de test reste nécessaire. Ne pas exécuter deux instances simultanément sur le même fichier d'état.
