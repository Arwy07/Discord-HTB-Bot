# Discord HTB Bot

Bot Python pour organiser un serveur de formation Hack The Box, suivre les labs et modules CJCA, faire valider les labs par des encadrants et afficher un classement XP. Il ne se connecte pas à l'API Hack The Box et ne réalise pas les labs à la place des participants.

## Parcours rapide

1. Récupérer le projet et installer ses dépendances.
2. Créer son application Discord, obtenir son token et inviter le bot.
3. Remplir le fichier `.env` et démarrer le programme.
4. Exécuter `/installer_lab`, vérifier les rôles et régler le salon de validation.
5. Tester un parcours étudiant et une validation par un encadrant.

## 1. Prérequis et téléchargement

- Python 3.11 ou ultérieur avec pip.
- Un compte Discord et un serveur de test sur lequel installer l'application.
- Une connexion Internet et un ordinateur qui reste allumé pendant l'utilisation.
- Un compte GitHub autorisé : ce dépôt est privé.

Avec Git :

```sh
git clone https://github.com/Arwy07/Discord-HTB-Bot.git
cd Discord-HTB-Bot
```

Sans Git : sur GitHub, **Code → Download ZIP**, extraire l'archive et ouvrir un terminal dans le dossier qui contient `bot.py` et `requirements.txt`.

### Windows PowerShell

```powershell
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Si `py` n'existe pas mais que `python --version` affiche Python 3.11 ou plus, remplacer la première commande par `python -m venv .venv`. Ces commandes utilisent directement le Python de l'environnement : pas besoin d'activer un script PowerShell.

### Linux et macOS

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
```

Si `venv` est absent, installer le composant correspondant à sa distribution Python avant de recommencer.

## 2. Créer son application et trouver son token Discord

1. Ouvrir le [Discord Developer Portal](https://discord.com/developers/applications) et se connecter à son propre compte.
2. Cliquer **New Application**, choisir un nom puis ouvrir l'application.
3. Dans **Bot**, utiliser **Reset Token** pour générer un token ; terminer les confirmations demandées par Discord. Copier le token uniquement dans son fichier local `.env`.
4. Dans **General Information**, relever l'**Application ID**.
5. Dans **Installation**, choisir le contexte **Guild Install** et **Discord Provided Link**. Pour l'installation serveur, sélectionner les scopes `bot` et `applications.commands`.
6. Sélectionner les permissions du bot décrites ci-dessous, ouvrir le lien d'installation et choisir son serveur de test.

Le token de la page **Bot** est différent de l'Application ID, de la Public Key et du Client Secret. Ne jamais le mettre dans un message, une capture ou un commit. S'il est perdu ou divulgué, utiliser **Reset Token**, remplacer la valeur locale puis redémarrer le bot. Référence : [démarrage officiel Discord](https://github.com/discord/discord-api-docs/blob/main/developers/quick-start/getting-started.mdx).

### Permissions nécessaires

Sélectionner **Manage Channels**, **Manage Roles**, **View Channels**, **Send Messages**, **Read Message History**, **Add Reactions**, **Manage Messages**, **Embed Links** et **Attach Files**. Les deux dernières servent aux présentations et aux exports. Discord peut afficher les intitulés en français.

Dans **Paramètres du serveur → Rôles**, placer le rôle du bot au-dessus des rôles qu'il attribue : Étudiant, Encadrant, Débutant, Intermédiaire, Avancé et CJCA terminé. Si ces rôles n'existent pas encore, lancer l'installation puis ajuster leur position et relancer la commande si elle le demande.

### Intents

Le code n'utilise pas **Message Content Intent** ni **Presence Intent**. **Server Members Intent** est optionnel : pour inclure tous les étudiants dans le bilan de classe, l'activer dans **Bot → Privileged Gateway Intents** et définir `DISCORD_MEMBERS_INTENT=true`. Sinon conserver `false` ; le bilan porte sur les étudiants déjà suivis.

## 3. Trouver les identifiants et remplir .env

Dans Discord, ouvrir **Paramètres utilisateur → Avancés → Mode développeur**. Ensuite : clic droit sur l'icône du serveur, un salon ou un utilisateur → **Copier l'identifiant**. Le serveur est aussi appelé « guild ». [Aide officielle Discord](https://support-dev.discord.com/hc/en-us/articles/360028717192-Where-can-I-find-my-Application-Team-Server-ID).

Ouvrir `.env` à la racine du projet. Sous Windows, vérifier qu'il ne s'appelle pas `.env.txt`.

| Variable | Valeur |
|---|---|
| `DISCORD_TOKEN` | Token de la page Bot ; obligatoire |
| `GUILD_ID` | Identifiant du serveur où le bot est installé ; remplacer 0 |
| `APPLICATION_ID` | Application ID du portail ; champ informatif conservé dans le plan, non utilisé par la connexion actuelle |
| `LAB_VALIDATION_CHANNEL_ID` | Identifiant d'un salon textuel privé lisible par les encadrants et le bot ; obligatoire avant de déclarer un lab |
| `EXTRA_ADMIN_IDS` | Facultatif : identifiants de coadministrateurs séparés par des virgules, sans crochets ; vide par défaut |
| `DISCORD_MEMBERS_INTENT` | false, ou true si l'option est aussi activée dans le portail |

Le propriétaire dispose déjà de ses droits. Les coadministrateurs configurés ont des privilèges élevés dans le bot : renseigner seulement les personnes prévues pour l'administrer.

### Quel salon mettre pour la validation ?

Deux méthodes possibles :

- Créer manuellement un salon privé `validation-labs`, autoriser le bot et les encadrants à y accéder, puis copier son identifiant dans `.env`.
- Laisser provisoirement `LAB_VALIDATION_CHANNEL_ID=0`, démarrer et lancer `/installer_lab`. Copier ensuite l'identifiant du salon privé `🔐・équipe` créé dans ADMINISTRATION, arrêter le bot, compléter `.env` et redémarrer. Ne pas déclarer de lab avant ce redémarrage.

Le bot doit pouvoir envoyer des messages, intégrer des liens, lire l'historique et ajouter des réactions dans ce salon.

## 4. Démarrer et installer le serveur

Windows :

```powershell
.\.venv\Scripts\python.exe bot.py
```

Linux/macOS :

```sh
.venv/bin/python bot.py
```

Le journal doit annoncer la synchronisation des commandes avec le serveur. Dans Discord, le propriétaire ou un administrateur lance `/installer_lab`.

Cette commande crée ou réutilise les rôles, salons et catégories du plan, applique leurs permissions et publie les présentations nécessaires. Elle peut renommer les catégories par défaut et retirer d'anciennes présentations du bot. Une nouvelle exécution complète une installation interrompue. Corriger les doublons signalés avant de réessayer ; faire le premier essai sur un serveur dédié.

| Espace créé | Contenu | Accès prévu |
|---|---|---|
| ACCUEIL | Bienvenue, guide, règles, annonces, choix du niveau | Lecture publique, publications encadrées |
| LAB HTB | Consignes, machines, ressources, entraide, progression, avance, classement | Étudiants et encadrants |
| DISCUSSIONS | Général | Étudiants et encadrants |
| VOCAL | Général et entraide | Étudiants et encadrants |
| ADMINISTRATION | Équipe, commandes, journal du bot | Encadrants et propriétaire |

Les encadrants doivent compléter les consignes, ressources et machines de leur formation. Le bot prépare l'organisation ; il ne fournit pas les contenus des labs.

## 5. Premier parcours utilisateur

1. Le propriétaire exécute `/nommer_encadrant membre:@personne`.
2. Un étudiant réagit 🟢, 🔵 ou 🟣 dans le salon de choix du niveau. Il reçoit Étudiant et un seul rôle de niveau.
3. Il utilise `/lab`, choisit le nom, la difficulté et le paramètre `ia` présent dans cette version.
4. L'encadrant utilise ✅ ou ❌ sur la demande dans le salon de validation.
5. Le lab validé ajoute ses XP au classement. L'étudiant utilise `/module` pour sa progression CJCA ; l'encadrant contrôle avec `/avance`.

| Commande | Utilité et accès |
|---|---|
| `/installer_lab` | Installation/réparation ; propriétaire, coadministrateur ou administrateur serveur |
| `/nommer_encadrant membre` | Attribuer Encadrant ; propriétaire ou coadministrateur configuré |
| `/lab nom difficulte ia` | Déclarer un lab pour validation |
| `/module parcours module etapes` | Enregistrer les étapes d'un module CJCA |
| `/classement` | Afficher le classement XP |
| `/avance membre` | Bilan privé ; encadrant |
| `/corriger lab`, `/corriger module` | Corriger une déclaration ou des étapes ; encadrant |
| `/export` | Export pédagogique ; encadrant |
| `/bilan_classe` | Rapport et CSV de la classe ; encadrant |
| `/retard` | Repérer l'inactivité ; encadrant |
| `/stats` | Statistiques ; encadrant |

Discord propose les paramètres et valeurs admises lors de la saisie des commandes. Barème de cette version : Very Easy 10, Easy 20, Medium 30, Hard 40 et Insane 50 XP ; moitié pour un lab déclaré avec IA ; 5 XP par étape de module.

## 6. Arrêt, redémarrage, sauvegarde et hébergement

Arrêter avec Ctrl+C. Le bot devient hors ligne lorsque le programme ou l'ordinateur s'arrête. Pour redémarrer, utiliser la même commande depuis le même dossier avec les mêmes fichiers `.env` et `state.json`. Ne pas réinstaller les dépendances à chaque démarrage.

Le fichier `state.json` est créé automatiquement : il contient les références de messages, l'état du serveur et les données de progression. Pour sauvegarder ou déplacer le bot : arrêter le programme, copier l'état et la configuration dans un emplacement privé, préparer les dépendances sur la nouvelle machine, puis lancer une seule instance. Ne pas publier l'état ni les CSV.

Un fonctionnement permanent nécessite une machine restant allumée et un gestionnaire de service adapté. Ce dépôt décrit le lancement local ; il ne fournit pas de déploiement VPS prêt à l'emploi. Ne jamais exécuter deux instances simultanément sur le même état.

## Dépannage

| Problème | Vérification |
|---|---|
| Module Python absent | Installer les dépendances avec le Python de .venv et utiliser ce même Python pour démarrer |
| Token absent ou refusé | Vérifier .env, son extension, le token de Bot et son éventuelle régénération |
| Identifiant invalide / serveur introuvable | Remplacer 0 par le bon Guild ID et vérifier l'installation dans ce serveur |
| PrivilegedIntentsRequired | Aligner l'intent membres dans le portail et .env, ou conserver false |
| Commandes absentes | Vérifier applications.commands, le bon serveur et les journaux de synchronisation ; rouvrir Discord |
| Rôle trop bas | Déplacer le rôle du bot au-dessus des rôles gérés et relancer l'installation |
| Lab non transmis | Vérifier l'identifiant du salon privé, ses permissions et le redémarrage après modification |
| Bilan incomplet | Activer Server Members Intent des deux côtés pour inclure les étudiants sans activité |
| État illisible | Arrêter puis restaurer une copie valide ; garder le fichier défectueux en privé avant réparation |

## Organisation et état du projet

| Fichier | Rôle |
|---|---|
| bot.py | Commandes, contrôles d'accès, validation et persistance |
| server_plan.py | Salons, rôles, modules, textes et barèmes |
| requirements.txt | Dépendances Python |
| .env.example | Paramètres vides à copier localement |
| state.json | Données locales créées à l'exécution, exclues de Git |

Sources issues de l'archive locale PC maj_6. Cette version conserve l'ancien paramètre IA : la demande ultérieure de retrait n'est pas intégrée aux sources retrouvées. Aucun état étudiant n'a été importé ou migré. Voir [VALIDATION.md](VALIDATION.md) : contrôles hors connexion réalisés, recette Discord réelle encore à effectuer.
