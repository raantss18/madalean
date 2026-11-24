var e=`madalean-manual/1`,t=`docs/manual`,n=`https://raantss18.github.io/madalean/`,r=[`fr`,`en`],i={fr:[{id:`start`,title:`Démarrer`},{id:`use`,title:`Travailler`},{id:`research`,title:`Recherche`},{id:`settings`,title:`Réglages et sécurité`},{id:`help`,title:`Aide`},{id:`reference`,title:`Référence`}],en:[{id:`start`,title:`Getting started`},{id:`use`,title:`Working`},{id:`research`,title:`Research`},{id:`settings`,title:`Settings and security`},{id:`help`,title:`Help`},{id:`reference`,title:`Reference`}]},a={install:`download.html`,download:`download.html`,updates:`../updates/index.html`,search:`search.html`},o=[{id:`index`,lang:`fr`,title:`Manuel de Madalean`,order:0,section:`start`,audience:`all`,summary:`Ce que fait Madalean, ce qu'il ne fait pas, et le plan de ce manuel.`,source:`fr/index.md`,site_path:`fr/index.html`,headings:[{level:1,text:`Manuel de Madalean`,id:`manuel-de-madalean`},{level:2,text:`Ce que Madalean ne fait pas`,id:`ce-que-madalean-ne-fait-pas`},{level:2,text:`Plan du manuel`,id:`plan-du-manuel`},{level:2,text:`Conventions de ce manuel`,id:`conventions-de-ce-manuel`}],images:[{src:`img/home.png`,exists:!0}],verify:[],body:`# Manuel de Madalean

Madalean est un assistant de démonstration pour **Lean 4** et **Mathlib**. Vous écrivez un énoncé en langage
courant (formules LaTeX entre dollars acceptées), des modèles d'IA le traduisent en Lean, cherchent une preuve et
l'expliquent ; **Lean tranche**. Rien n'est jamais présenté comme prouvé si Lean ne l'a pas accepté selon le verdict
strict : aucune erreur, aucun \`sorry\`, aucun axiome autre que les trois axiomes standard de Lean
(\`propext\`, \`Classical.choice\`, \`Quot.sound\`).

Un seul ordinateur, l'**ordinateur hôte**, fait tout le travail : Lean, modèles locaux, stockage. Tous les écrans
(cet ordinateur, un autre PC, une tablette, un téléphone) affichent la **même interface web** et restent
synchronisés. Les appareils joignent l'hôte uniquement par votre réseau privé Tailscale.

![Accueil de Madalean](img/home.png)

## Ce que Madalean ne fait pas

- Il ne garantit pas que la traduction en Lean dit ce que vous vouliez dire. Lean vérifie la preuve **de l'énoncé
  Lean**, pas de votre phrase. Relisez toujours la traduction : voir [Lire un énoncé Lean](reading-lean.md).
- Il ne trouve pas toutes les preuves. « Pas de preuve trouvée » ne veut pas dire que l'énoncé est faux.
- Il n'envoie rien sur Internet en mode **Local**. Dans les autres modes, ce qui part et vers qui est décrit dans
  [Modèles et clés](models-keys.md).

## Plan du manuel

- **Démarrer** : [Installer Madalean](install.md) · [Ce qu'installe Madalean](components.md) ·
  [Première configuration](first-config.md) · [Premier démarrage](first-run.md) ·
  [Relier un téléphone, une tablette, un PC](pairing.md) · [Tailscale](tailscale.md)
- **Travailler** : [De l'énoncé à la preuve](workflow.md) · [Lire un énoncé Lean](reading-lean.md) ·
  [Demandes de suivi et versions](follow-ups.md) · [Projets et dossiers en parallèle](projects.md) ·
  [Plans de preuve et lemmes](proof-plans.md)
- **Recherche** : [Atelier de conjectures](conjectures.md) · [Sources et questions ancrées](sources.md) ·
  [Bibliographie, article, blueprint](articles.md) · [Notes](notes.md) · [Jupyter et Sage](jupyter.md) ·
  [Publier un projet](publish.md)
- **Réglages et sécurité** : [Modèles et clés](models-keys.md) · [Mises à jour](updates.md) ·
  [Sécurité](security.md)
- **Référence** : [Dépannage](troubleshooting.md) · [Glossaire Lean](glossary.md) ·
  [Premières tactiques](tactics.md) · [Raccourcis clavier](shortcuts.md) · [Mesures](measures.md)

## Conventions de ce manuel

- Les noms entre guillemets (« Envoyer », « Réglages › Appareils ») sont ceux des boutons et menus de l'interface.
- Les blocs de code \`lean\` sont du Lean 4 avec Mathlib. Ils suivent la version de Mathlib de l'espace de travail
  « Prouveur » (Lean 4.9) sauf mention contraire ; quelques notations ont changé depuis, elles sont signalées.
- Les pages marquées *apprenant* s'adressent à qui découvre Lean ; *chercheur* à qui l'utilise pour un projet de
  recherche. La plupart concernent tout le monde.
`,text:`Manuel de Madalean Madalean est un assistant de démonstration pour Lean 4 et Mathlib. Vous écrivez un énoncé en langage courant (formules LaTeX entre dollars acceptées), des modèles d'IA le traduisent en Lean, cherchent une preuve et l'expliquent ; Lean tranche. Rien n'est jamais présenté comme prouvé si Lean ne l'a pas accepté selon le verdict strict : aucune erreur, aucun sorry, aucun axiome autre que les trois axiomes standard de Lean (propext, Classical.choice, Quot.sound). Un seul ordinateur, l'ordinateur hôte, fait tout le travail : Lean, modèles locaux, stockage. Tous les écrans (cet ordinateur, un autre PC, une tablette, un téléphone) affichent la même interface web et restent synchronisés. Les appareils joignent l'hôte uniquement par votre réseau privé Tailscale. Accueil de Madalean Ce que Madalean ne fait pas - Il ne garantit pas que la traduction en Lean dit ce que vous vouliez dire. Lean vérifie la preuve de l'énoncé Lean, pas de votre phrase. Relisez toujours la traduction : voir Lire un énoncé Lean. - Il ne trouve pas toutes les preuves. « Pas de preuve trouvée » ne veut pas dire que l'énoncé est faux. - Il n'envoie rien sur Internet en mode Local. Dans les autres modes, ce qui part et vers qui est décrit dans Modèles et clés. Plan du manuel - Démarrer : Installer Madalean · Ce qu'installe Madalean · Première configuration · Premier démarrage · Relier un téléphone, une tablette, un PC · Tailscale - Travailler : De l'énoncé à la preuve · Lire un énoncé Lean · Demandes de suivi et versions · Projets et dossiers en parallèle · Plans de preuve et lemmes - Recherche : Atelier de conjectures · Sources et questions ancrées · Bibliographie, article, blueprint · Notes · Jupyter et Sage · Publier un projet - Réglages et sécurité : Modèles et clés · Mises à jour · Sécurité - Référence : Dépannage · Glossaire Lean · Premières tactiques · Raccourcis clavier · Mesures Conventions de ce manuel - Les noms entre guillemets (« Envoyer », « Réglages › Appareils ») sont ceux des boutons et menus de l'interface. - Les blocs de code lean sont du Lean 4 avec Mathlib. Ils suivent la version de Mathlib de l'espace de travail « Prouveur » (Lean 4.9) sauf mention contraire ; quelques notations ont changé depuis, elles sont signalées. - Les pages marquées apprenant s'adressent à qui découvre Lean ; chercheur à qui l'utilise pour un projet de recherche. La plupart concernent tout le monde.`},{id:`install`,lang:`fr`,title:`Installer Madalean`,order:10,section:`start`,audience:`all`,summary:`Ce qu'il faut comme machine, les trois façons d'installer (installateur graphique, assistant en terminal, installation automatique), ce que fait install.sh, ses options, la mise à jour et la désinstallation.`,source:`fr/install.md`,site_path:`fr/install.html`,headings:[{level:1,text:`Installer Madalean`,id:`installer-madalean`},{level:2,text:`Ce qu'il faut avant de commencer`,id:`ce-quil-faut-avant-de-commencer`},{level:2,text:`Trois façons d'installer`,id:`trois-facons-dinstaller`},{level:3,text:`Avec l'installateur graphique (conseillé)`,id:`avec-linstallateur-graphique-conseille`},{level:3,text:`Depuis les sources, avec l'assistant en terminal`,id:`depuis-les-sources-avec-lassistant-en-terminal`},{level:3,text:`Sans question (installation automatique)`,id:`sans-question-installation-automatique`},{level:2,text:`Ce que fait install.sh, étape par étape`,id:`ce-que-fait-installsh-etape-par-etape`},{level:2,text:`Ce qui est déjà sur votre machine`,id:`ce-qui-est-deja-sur-votre-machine`},{level:2,text:`Options de install.sh`,id:`options-de-installsh`},{level:2,text:`Où sont enregistrés vos choix`,id:`ou-sont-enregistres-vos-choix`},{level:2,text:`Où sont les choses`,id:`ou-sont-les-choses`},{level:2,text:`Démarrer et arrêter`,id:`demarrer-et-arreter`},{level:2,text:`Installer sans réseau`,id:`installer-sans-reseau`},{level:2,text:`Mettre à jour`,id:`mettre-a-jour`},{level:2,text:`Désinstaller`,id:`desinstaller`}],images:[],verify:[],body:`# Installer Madalean

Madalean s'installe sur **un seul ordinateur**, l'**ordinateur hôte** : c'est lui qui fait tourner le serveur, Lean,
les modèles locaux et qui garde vos données. Vos autres appareils (un autre PC, une tablette, un téléphone)
n'installent qu'une application légère, ou rien du tout : un navigateur suffit. Voir [Relier un appareil](pairing.md).

Cette page décrit l'installation elle-même. Deux pages la complètent :

- [Ce qu'installe Madalean, composant par composant](components.md) : à quoi sert chaque pièce (Lean, SageMath,
  LaTeX, modèles locaux…), sa taille, et s'il vaut mieux réutiliser ce qui est déjà sur votre machine ;
- [Première configuration](first-config.md) : les clés des fournisseurs en ligne, le mode de travail des modèles et
  les comportements automatiques, à régler une fois l'installation terminée.

## Ce qu'il faut avant de commencer

| | Minimum | Conseillé |
|---|---|---|
| Système | Linux 64 bits (x86_64), n'importe quelle distribution récente | — |
| Mémoire vive | 8 Go | 16 Go ou plus |
| Carte graphique | aucune | NVIDIA avec au moins 8 Go de mémoire graphique, pour faire tourner le prouveur local |
| Disque | ≈ 6 Go libres sans modèles locaux ni SageMath | un SSD, avec la place indiquée ci-dessous |

Place sur le disque, selon ce que vous installez :

| Élément | Place |
|---|---|
| Madalean et ses composants de base (Python, JupyterLab, LaTeX, polices, Lean, moteur des modèles) | ≈ 6 Go |
| Les trois modèles locaux (dans \`~/models\`) | ≈ 15 Go de plus, soit ≈ 25 Go en tout avec la base et une marge |
| SageMath (écran « Calcul ») | ≈ 5 Go de plus |
| Chaque espace de travail Lean/Mathlib construit sur la machine | ≈ 5 Go |

**Sans carte NVIDIA**, tout fonctionne : les modèles en ligne (gratuits, ou avec une clé) ne dépendent pas de votre
carte graphique, et ce sont eux que Madalean utilise par défaut. Seuls les modèles locaux seraient trop lents sur le
processeur ; l'installation ne les propose alors pas (voir [Les modèles locaux](components.md#modeles-locaux)).

**Avec une carte NVIDIA**, seul le **pilote NVIDIA** doit être installé, par vous, avec les outils de votre
distribution. Madalean ne touche jamais aux pilotes et n'a pas besoin du « CUDA Toolkit ». Si le pilote est trop
ancien, il installe le moteur des modèles pour le processeur.

Il faut enfin une connexion Internet pendant l'installation (sauf [installation hors ligne](#installer-sans-reseau)),
et les commandes de base \`bash\`, \`curl\`, \`tar\` et \`sha256sum\`, présentes sur toutes les distributions courantes.

## Trois façons d'installer

| Façon | Pour qui | Questions posées |
|---|---|---|
| [Installateur graphique](#avec-linstallateur-graphique-conseille) (conseillée) | tout le monde | dans une page de votre navigateur, avec un plan recommandé |
| [Depuis les sources, assistant en terminal](#depuis-les-sources-avec-lassistant-en-terminal) | qui préfère le terminal ou veut suivre le code | dans le terminal, avec le même plan recommandé |
| [Installation automatique](#sans-question-installation-automatique) | installation répétée, script, machine distante | aucune : les choix par défaut |

Les trois aboutissent à la même installation, faite par le même programme (\`install.sh\`). Aucune ne demande votre
mot de passe : rien n'est installé hors de votre dossier personnel.

### Avec l'installateur graphique (conseillé)

1. **Téléchargez** le fichier \`Madalean-installer.run\` : le lien
   <https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run> mène toujours à la
   dernière version. La
   [page de téléchargement](site:install) du site donne aussi ce lien.
2. **Rendez-le exécutable.** Un fichier téléchargé par un navigateur ne peut pas être lancé tel quel : c'est une
   protection de Linux. Au choix :
   - dans le gestionnaire de fichiers : clic droit sur le fichier › « Propriétés » › onglet « Permissions » › cochez
     « Autoriser l'exécution du fichier comme un programme » (le libellé varie selon le bureau : « Exécutable »,
     « Est exécutable »…) ;
   - ou dans un terminal, dans le dossier du fichier :

     \`\`\`bash
     chmod +x Madalean-installer.run
     \`\`\`
3. **Lancez-le** : double-clic sur le fichier, ou dans le terminal :

   \`\`\`bash
   ./Madalean-installer.run
   \`\`\`

Ce qui se passe ensuite :

- Le fichier **vérifie d'abord sa propre intégrité** (empreinte SHA-256) avant de décompresser quoi que ce soit. Un
  fichier abîmé pendant le téléchargement est refusé avec un message clair : téléchargez-le de nouveau.
- Il ouvre ensuite un **assistant d'installation dans votre navigateur**. Cette page est servie par l'installateur
  lui-même, sur votre machine seulement (adresse \`127.0.0.1\`, protégée par une clé à usage unique) : elle n'est
  joignable par aucun autre ordinateur.
- L'assistant vous mène en six écrans :
  1. **Bienvenue** : ce qui va être installé et où.
  2. **Examen de la machine** : système, mémoire, carte graphique, place libre, et les outils déjà présents (Lean,
     SageMath, TeX Live, Tailscale, Ollama, bubblewrap…).
  3. **Plan recommandé** : pour chaque élément (modèles locaux, SageMath, LaTeX, espaces Lean…), le choix conseillé
     pour votre machine et la raison ; vous pouvez changer chaque choix.
  4. **Installation** : la progression en direct, étape par étape.
  5. **Première configuration** : ce qu'il reste à régler dans Madalean (clé de modèle en ligne, mode de travail,
     comportements automatiques, appareils) et un bouton « Ouvrir Madalean » (\`http://127.0.0.1:11500\`), où
     l'assistant de premier démarrage prend le relais (voir [Première configuration](first-config.md)).
  6. **Terminé** : l'adresse de Madalean ; « Fermer l'assistant » arrête la petite page locale (elle s'arrête
     aussi d'elle-même après 30 minutes sans activité, jamais pendant une installation).
- En cas d'erreur, l'écran d'installation montre les dernières lignes, « Voir le détail » le journal complet, et
  « Réessayer » reprend là où l'installation s'est arrêtée.
- **Sans session graphique** (par exemple sur une machine à laquelle vous êtes connecté par \`ssh\`), l'installateur
  passe tout seul à l'assistant en terminal décrit ci-dessous.


### Depuis les sources, avec l'assistant en terminal

Si vous préférez le terminal, ou si vous voulez installer la version de développement :

\`\`\`bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh
\`\`\`

Lancé dans un terminal, \`install.sh\` :

1. examine la machine (système, mémoire, carte graphique, place libre, outils déjà installés) ;
2. affiche un **tableau récapitulatif** de ce qu'il a trouvé ;
3. propose un **plan recommandé** (le même que l'installateur graphique) ;
4. vous laisse l'**accepter** tel quel ou **changer chaque élément**, puis installe.

Pour seulement voir ce plan sans rien installer : \`./install.sh --dry-run\`.

### Sans question (installation automatique)

\`\`\`bash
./install.sh --yes
\`\`\`

\`--yes\` (ou \`-y\`) installe avec les choix par défaut, sans poser de question. C'est aussi ce qui se passe quand
\`install.sh\` n'est pas lancé dans un terminal (depuis un autre script, par exemple). Vous pouvez y ajouter les
options du [tableau ci-dessous](#options-de-installsh), ou réutiliser un plan enregistré avec \`--plan FICHIER\`.

## Ce que fait install.sh, étape par étape

Le script affiche neuf étapes, numérotées de \`1/9\` à \`9/9\`. Il est **relançable sans risque** : s'il est interrompu
(coupure de réseau, machine éteinte), relancez-le ; il reprend où il s'était arrêté, sans refaire ce qui est déjà
fait. Chaque fichier téléchargé est vérifié par son **empreinte SHA-256** (une sorte de signature numérique du
contenu) : un fichier altéré est refusé.

| Étape | Ce qui est fait |
|---|---|
| 1. Vérifications | Linux x86_64 ? outils de base présents ? place libre sur le disque |
| 2. Madalean | le code de Madalean et son interface web sont copiés dans \`~/.local/share/madalean/versions/<version>\` ; un lien \`current\` désigne la version en service |
| 3. Environnement | le petit gestionnaire de paquets **micromamba** est téléchargé, puis il installe l'environnement principal, figé à l'avance : Python 3.13, JupyterLab, le moteur LaTeX tectonic, poppler (lecture des PDF), git… Chaque paquet est vérifié par son empreinte SHA-256 |
| 4. Composants vérifiés | polices (DejaVu Sans Mono, Noto Sans Math), paquet TeX (pour composer les PDF sans réseau), **elan** (le gestionnaire de versions de Lean), **llama.cpp** (moteur des modèles locaux, pour votre carte NVIDIA ou pour le processeur), **madalean-net** (le nœud Tailscale intégré, qui permet à vos appareils de joindre l'hôte) |
| 5. Espaces Lean | les espaces Lean déjà construits sur la machine sont repris (par liens physiques : aucune place en plus) ; sinon, avec \`--build-workspace\`, l'espace « Lean actuel » est construit |
| 6. Modèles locaux | les modèles retenus par le plan sont téléchargés dans \`~/models\` ; ceux qui y sont déjà sont réutilisés, jamais déplacés |
| 7. Service | le service utilisateur systemd \`madalean\` est installé et démarré : Madalean tourne en arrière-plan dès l'ouverture de votre session |
| 8. Menu | l'application **« Madalean Server »** est ajoutée au menu des applications (icône Madalean avec un petit badge serveur) : la fenêtre de Madalean sur cet ordinateur, avec l'état du serveur et les boutons Démarrer / Arrêter / Redémarrer, les journaux. Sans la bibliothèque système webkit2gtk-4.1, l'entrée ouvre une fenêtre de Chromium (ou de Chrome, Brave, Edge, Vivaldi), sinon votre navigateur ; le bilan final le dit |
| 9. Contrôle | un bilan de santé de chaque composant, puis un essai de connexion au serveur |

À la fin, le script affiche la durée, la place occupée et l'adresse à ouvrir : \`http://127.0.0.1:11500\`. Le journal
complet est dans \`~/.local/share/madalean/install.log\`.

## Ce qui est déjà sur votre machine

Madalean **n'utilise jamais \`sudo\`** et **ne lance jamais le gestionnaire de paquets de votre distribution**
(\`pacman\`, \`apt\`, \`dnf\`, \`zypper\`…). Il ne modifie aucun programme du système. Pour ce qu'il trouve déjà installé :

| Déjà présent | Ce que fait Madalean |
|---|---|
| Des espaces Lean construits, des versions de Lean dans \`~/.elan\` | repris **en lecture seule** pour l'import ; \`~/.elan\` n'est jamais modifié |
| Des modèles dans \`~/models\` | réutilisés (vérifiés par empreinte), jamais déplacés |
| SageMath du système | réutilisé s'il est compatible et si vous le choisissez ; sinon Madalean installe sa propre copie à la demande |
| TeX Live | utilisé en secours, ou en premier si vous le choisissez |
| Python du système | jamais modifié ; le serveur utilise son propre Python |
| Tailscale, Ollama | laissés en place ; aucun conflit |

Le détail, et ce qu'il vaut mieux choisir dans chaque cas : [Ce qu'installe Madalean](components.md).

Quand quelque chose ne peut venir que de votre distribution — c'est le cas de **bubblewrap**, qui isole les
compilations et les calculs dans un « bac à sable » —, le script **affiche la commande exacte** à lancer vous-même,
par exemple \`sudo pacman -S bubblewrap\` sur Arch Linux ou \`sudo apt install bubblewrap\` sur Debian et Ubuntu. Les
commandes pour chaque distribution sont dans [Ce qu'installe Madalean › bubblewrap](components.md#bubblewrap-le-bac-a-sable).

## Options de install.sh

\`./install.sh --help\` les affiche toutes.

| Option | Effet |
|---|---|
| \`--yes\`, \`-y\` | aucune question : les choix par défaut |
| \`--assistant\` | force l'assistant en terminal (même quand il ne serait pas proposé) |
| \`--plan FICHIER\` | installe selon un plan enregistré par l'assistant ou par l'installateur graphique |
| \`--dry-run\` | examine la machine et affiche le plan, sans rien installer |
| \`--models all\\|prover\\|none\` | modèles locaux : les trois, seulement le prouveur, ou aucun (sans question : les trois ; l'assistant conseille selon la carte graphique) |
| \`--sage later\\|now\\|system\` | SageMath : à la première utilisation de « Calcul » (défaut), tout de suite, ou celui du système |
| \`--tex own\\|system\` | LaTeX : celui de Madalean (défaut) ou le TeX Live du système en premier |
| \`--cpu\` \\| \`--gpu\` | moteur des modèles pour le processeur, ou pour la carte NVIDIA (défaut : la carte si le pilote convient) |
| \`--no-models\` | ne télécharge aucun modèle local (les fichiers déjà dans \`~/models\` restent utilisés) |
| \`--no-workspaces\` | n'installe aucun espace Lean |
| \`--build-workspace\` | construit l'espace « Lean actuel » si aucun n'est trouvé (≈ 5 Go, réseau nécessaire) |
| \`--build-net\` | construit le nœud Tailscale \`madalean-net\` à partir des sources (il doit donner exactement l'empreinte attendue) |
| \`--offline DOSSIER\` | installe sans réseau, depuis un export fait avec \`./export_offline.sh\` |
| \`--prefix DOSSIER\` | dossier d'installation (défaut \`~/.local/share/madalean\`) |
| \`--config-dir DOSSIER\` | dossier des réglages et des données (défaut \`~/.config/madalean\`) |
| \`--cache-dir DOSSIER\` | dossier des caches (défaut \`~/.cache/madalean\`) |
| \`--no-systemd\` | n'installe pas le service systemd (lancez alors Madalean vous-même) |
| \`--no-desktop\` | n'ajoute pas d'entrée au menu des applications |
| \`--port N\`, \`--remote-port N\` | ports du serveur : interface locale (défaut 11500) et accès des appareils reliés (défaut 11501) |


## Où sont enregistrés vos choix

Les choix faits à l'installation (modèles locaux, SageMath, LaTeX…) sont écrits dans
\`~/.config/madalean/setup.json\`. Madalean lit ce fichier au premier démarrage et applique les réglages qui en
découlent, par exemple \`sage_source\` (quel SageMath utiliser) et \`tex_engine\` (quel LaTeX utiliser) ; vous pouvez
les changer à tout moment (l'application les lit aussi par \`GET /api/setup\`). Voir
[Première configuration › Choix faits à l'installation](first-config.md#choix-faits-a-linstallation).

Au premier démarrage dans le navigateur de l'hôte, l'assistant [« Premiers pas »](first-config.md#lassistant-premiers-pas)
montre de nouveau ces choix (choix conseillé et raison pour cette machine) et permet de les changer.

## Où sont les choses

| Quoi | Où |
|---|---|
| Madalean et tous ses composants | \`~/.local/share/madalean/\` |
| Journal d'installation | \`~/.local/share/madalean/install.log\` |
| Réglages, choix d'installation, projets, dossiers, appareils reliés, clés (si pas de trousseau) | \`~/.config/madalean/\` |
| Index de recherche, caches | \`~/.cache/madalean/\` |
| Modèles locaux | \`~/models/\` |
| Carnets Jupyter | \`~/Documents/Madalean/notebooks/\` |
| Service systemd | \`~/.config/systemd/user/madalean.service\` |

Au premier démarrage, si vous aviez Lean AI Station 1.x, le serveur **copie** (sans jamais les déplacer) vos
réglages, dossiers et bibliothèque depuis \`~/.config/lean-ai-station/\`.

## Démarrer et arrêter

Le service démarre avec votre session. Ouvrez l'interface sur l'hôte : **« Madalean Server »** dans le menu des
applications, ou \`http://127.0.0.1:11500\` dans un navigateur.

« Madalean Server » est l'application de l'ordinateur hôte : elle montre Madalean dans sa propre fenêtre (sans code
d'appairage : c'est cet ordinateur) et, dans son menu **Serveur** (ou son icône près de l'horloge), l'état du
serveur, **Démarrer**, **Arrêter**, **Redémarrer**, **Ouvrir les journaux** et **Ouvrir dans le navigateur**. Quand
le serveur s'arrête, la fenêtre affiche le panneau du serveur ; quand il repart, elle revient d'elle-même sur
Madalean. Si le service n'est pas installé, le panneau le dit et donne la commande pour le réinstaller.
L'application « Madalean » (AppImage, sans badge) est pour les **autres** ordinateurs : voir
[Relier un appareil](pairing.md).

En terminal, si besoin :

\`\`\`bash
systemctl --user status madalean      # état
systemctl --user restart madalean     # redémarrer
journalctl --user -u madalean -e      # journal
\`\`\`

Ensuite : [Première configuration](first-config.md), puis [Premier démarrage](first-run.md) pour un premier énoncé.

## Installer sans réseau

Pour un ordinateur sans accès à Internet : sur une machine connectée où Madalean est installé, \`./export_offline.sh\`
prépare un dossier contenant tout ce qu'il faut (paquets, composants, espaces Lean, modèles). Copiez ce dossier sur
l'autre machine (clé USB, disque), puis :

\`\`\`bash
./install.sh --offline /chemin/vers/l-export
\`\`\`

Les empreintes SHA-256 sont vérifiées comme pour une installation en ligne.

## Mettre à jour

Madalean se met à jour **depuis l'application**, dans « Réglages › Mises à jour » : chaque nouvelle version est
**signée**, vérifiée, installée à côté de l'ancienne, puis mise en service ; la version précédente est gardée pour
revenir en arrière. Il n'est pas nécessaire de relancer \`install.sh\`. Le détail : [Mises à jour](updates.md).

## Désinstaller

Depuis le dossier des sources (ou \`~/.local/share/madalean/current\`) :

\`\`\`bash
./uninstall.sh
\`\`\`

Le script **liste d'abord** exactement ce qui sera supprimé, avec la taille de chaque élément, puis **demande
confirmation**. Il arrête d'abord le service et tous ses processus.

| Supprimé | Conservé |
|---|---|
| \`~/.local/share/madalean\` (environnement, composants, espaces Lean installés par Madalean, paquet TeX, état du nœud Tailscale, versions de Madalean) | \`~/.config/madalean\` : vos réglages, projets, dossiers, appareils reliés et clés |
| \`~/.cache/madalean\` | \`~/models\` : vos modèles |
| le service systemd et l'entrée du menu | \`~/Documents/Madalean\` : vos carnets |
| | jamais touchés : \`~/.elan\`, les paquets du système, le Tailscale du système |

Options :

| Option | Effet |
|---|---|
| \`--purge\` | propose en plus, avec une question pour chacun, de supprimer \`~/.config/madalean\` et \`~/models\` |
| \`--yes\` | ne demande pas la confirmation générale (les questions de \`--purge\` restent posées) |
| \`--prefix\`, \`--config-dir\`, \`--cache-dir\` | à donner si vous les aviez changés à l'installation |

Les clés enregistrées dans le trousseau du système restent dans le trousseau : supprimez-les d'abord dans
« Réglages › Fournisseurs » (« Retirer la clé ») si vous voulez les effacer.
`,text:`Installer Madalean Madalean s'installe sur un seul ordinateur, l'ordinateur hôte : c'est lui qui fait tourner le serveur, Lean, les modèles locaux et qui garde vos données. Vos autres appareils (un autre PC, une tablette, un téléphone) n'installent qu'une application légère, ou rien du tout : un navigateur suffit. Voir Relier un appareil. Cette page décrit l'installation elle-même. Deux pages la complètent : - Ce qu'installe Madalean, composant par composant : à quoi sert chaque pièce (Lean, SageMath, LaTeX, modèles locaux…), sa taille, et s'il vaut mieux réutiliser ce qui est déjà sur votre machine ; - Première configuration : les clés des fournisseurs en ligne, le mode de travail des modèles et les comportements automatiques, à régler une fois l'installation terminée. Ce qu'il faut avant de commencer Minimum Conseillé Système Linux 64 bits (x8664), n'importe quelle distribution récente — Mémoire vive 8 Go 16 Go ou plus Carte graphique aucune NVIDIA avec au moins 8 Go de mémoire graphique, pour faire tourner le prouveur local Disque ≈ 6 Go libres sans modèles locaux ni SageMath un SSD, avec la place indiquée ci-dessous Place sur le disque, selon ce que vous installez : Élément Place Madalean et ses composants de base (Python, JupyterLab, LaTeX, polices, Lean, moteur des modèles) ≈ 6 Go Les trois modèles locaux (dans ~/models) ≈ 15 Go de plus, soit ≈ 25 Go en tout avec la base et une marge SageMath (écran « Calcul ») ≈ 5 Go de plus Chaque espace de travail Lean/Mathlib construit sur la machine ≈ 5 Go Sans carte NVIDIA, tout fonctionne : les modèles en ligne (gratuits, ou avec une clé) ne dépendent pas de votre carte graphique, et ce sont eux que Madalean utilise par défaut. Seuls les modèles locaux seraient trop lents sur le processeur ; l'installation ne les propose alors pas (voir Les modèles locaux). Avec une carte NVIDIA, seul le pilote NVIDIA doit être installé, par vous, avec les outils de votre distribution. Madalean ne touche jamais aux pilotes et n'a pas besoin du « CUDA Toolkit ». Si le pilote est trop ancien, il installe le moteur des modèles pour le processeur. Il faut enfin une connexion Internet pendant l'installation (sauf installation hors ligne), et les commandes de base bash, curl, tar et sha256sum, présentes sur toutes les distributions courantes. Trois façons d'installer Façon Pour qui Questions posées Installateur graphique (conseillée) tout le monde dans une page de votre navigateur, avec un plan recommandé Depuis les sources, assistant en terminal qui préfère le terminal ou veut suivre le code dans le terminal, avec le même plan recommandé Installation automatique installation répétée, script, machine distante aucune : les choix par défaut Les trois aboutissent à la même installation, faite par le même programme (install.sh). Aucune ne demande votre mot de passe : rien n'est installé hors de votre dossier personnel. Avec l'installateur graphique (conseillé) 1. Téléchargez le fichier Madalean-installer.run : le lien <https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run> mène toujours à la dernière version. La page de téléchargement du site donne aussi ce lien. 2. Rendez-le exécutable. Un fichier téléchargé par un navigateur ne peut pas être lancé tel quel : c'est une protection de Linux. Au choix : - dans le gestionnaire de fichiers : clic droit sur le fichier › « Propriétés » › onglet « Permissions » › cochez « Autoriser l'exécution du fichier comme un programme » (le libellé varie selon le bureau : « Exécutable », « Est exécutable »…) ; - ou dans un terminal, dans le dossier du fichier : 3. Lancez-le : double-clic sur le fichier, ou dans le terminal : Ce qui se passe ensuite : - Le fichier vérifie d'abord sa propre intégrité (empreinte SHA-256) avant de décompresser quoi que ce soit. Un fichier abîmé pendant le téléchargement est refusé avec un message clair : téléchargez-le de nouveau. - Il ouvre ensuite un assistant d'installation dans votre navigateur. Cette page est servie par l'installateur lui-même, sur votre machine seulement (adresse 127.0.0.1, protégée par une clé à usage unique) : elle n'est joignable par aucun autre ordinateur. - L'assistant vous mène en six écrans : 1. Bienvenue : ce qui va être installé et où. 2. Examen de la machine : système, mémoire, carte graphique, place libre, et les outils déjà présents (Lean, SageMath, TeX Live, Tailscale, Ollama, bubblewrap…). 3. Plan recommandé : pour chaque élément (modèles locaux, SageMath, LaTeX, espaces Lean…), le choix conseillé pour votre machine et la raison ; vous pouvez changer chaque choix. 4. Installation : la progression en direct, étape par étape. 5. Première configuration : ce qu'il reste à régler dans Madalean (clé de modèle en ligne, mode de travail, comportements automatiques, appareils) et un bouton « Ouvrir Madalean » (http://127.0.0.1:11500), où l'assistant de premier démarrage prend le relais (voir Première configuration). 6. Terminé : l'adresse de Madalean ; « Fermer l'assistant » arrête la petite page locale (elle s'arrête aussi d'elle-même après 30 minutes sans activité, jamais pendant une installation). - En cas d'erreur, l'écran d'installation montre les dernières lignes, « Voir le détail » le journal complet, et « Réessayer » reprend là où l'installation s'est arrêtée. - Sans session graphique (par exemple sur une machine à laquelle vous êtes connecté par ssh), l'installateur passe tout seul à l'assistant en terminal décrit ci-dessous. Depuis les sources, avec l'assistant en terminal Si vous préférez le terminal, ou si vous voulez installer la version de développement : Lancé dans un terminal, install.sh : 1. examine la machine (système, mémoire, carte graphique, place libre, outils déjà installés) ; 2. affiche un tableau récapitulatif de ce qu'il a trouvé ; 3. propose un plan recommandé (le même que l'installateur graphique) ; 4. vous laisse l'accepter tel quel ou changer chaque élément, puis installe. Pour seulement voir ce plan sans rien installer : ./install.sh --dry-run. Sans question (installation automatique) --yes (ou -y) installe avec les choix par défaut, sans poser de question. C'est aussi ce qui se passe quand install.sh n'est pas lancé dans un terminal (depuis un autre script, par exemple). Vous pouvez y ajouter les options du tableau ci-dessous, ou réutiliser un plan enregistré avec --plan FICHIER. Ce que fait install.sh, étape par étape Le script affiche neuf étapes, numérotées de 1/9 à 9/9. Il est relançable sans risque : s'il est interrompu (coupure de réseau, machine éteinte), relancez-le ; il reprend où il s'était arrêté, sans refaire ce qui est déjà fait. Chaque fichier téléchargé est vérifié par son empreinte SHA-256 (une sorte de signature numérique du contenu) : un fichier altéré est refusé. Étape Ce qui est fait 1. Vérifications Linux x8664 ? outils de base présents ? place libre sur le disque 2. Madalean le code de Madalean et son interface web sont copiés dans ~/.local/share/madalean/versions/<version> ; un lien current désigne la version en service 3. Environnement le petit gestionnaire de paquets micromamba est téléchargé, puis il installe l'environnement principal, figé à l'avance : Python 3.13, JupyterLab, le moteur LaTeX tectonic, poppler (lecture des PDF), git… Chaque paquet est vérifié par son empreinte SHA-256 4. Composants vérifiés polices (DejaVu Sans Mono, Noto Sans Math), paquet TeX (pour composer les PDF sans réseau), elan (le gestionnaire de versions de Lean), llama.cpp (moteur des modèles locaux, pour votre carte NVIDIA ou pour le processeur), madalean-net (le nœud Tailscale intégré, qui permet à vos appareils de joindre l'hôte) 5. Espaces Lean les espaces Lean déjà construits sur la machine sont repris (par liens physiques : aucune place en plus) ; sinon, avec --build-workspace, l'espace « Lean actuel » est construit 6. Modèles locaux les modèles retenus par le plan sont téléchargés dans ~/models ; ceux qui y sont déjà sont réutilisés, jamais déplacés 7. Service le service utilisateur systemd madalean est installé et démarré : Madalean tourne en arrière-plan dès l'ouverture de votre session 8. Menu l'application « Madalean Server » est ajoutée au menu des applications (icône Madalean avec un petit badge serveur) : la fenêtre de Madalean sur cet ordinateur, avec l'état du serveur et les boutons Démarrer / Arrêter / Redémarrer, les journaux. Sans la bibliothèque système webkit2gtk-4.1, l'entrée ouvre une fenêtre de Chromium (ou de Chrome, Brave, Edge, Vivaldi), sinon votre navigateur ; le bilan final le dit 9. Contrôle un bilan de santé de chaque composant, puis un essai de connexion au serveur À la fin, le script affiche la durée, la place occupée et l'adresse à ouvrir : http://127.0.0.1:11500. Le journal complet est dans ~/.local/share/madalean/install.log. Ce qui est déjà sur votre machine Madalean n'utilise jamais sudo et ne lance jamais le gestionnaire de paquets de votre distribution (pacman, apt, dnf, zypper…). Il ne modifie aucun programme du système. Pour ce qu'il trouve déjà installé : Déjà présent Ce que fait Madalean Des espaces Lean construits, des versions de Lean dans ~/.elan repris en lecture seule pour l'import ; ~/.elan n'est jamais modifié Des modèles dans ~/models réutilisés (vérifiés par empreinte), jamais déplacés SageMath du système réutilisé s'il est compatible et si vous le choisissez ; sinon Madalean installe sa propre copie à la demande TeX Live utilisé en secours, ou en premier si vous le choisissez Python du système jamais modifié ; le serveur utilise son propre Python Tailscale, Ollama laissés en place ; aucun conflit Le détail, et ce qu'il vaut mieux choisir dans chaque cas : Ce qu'installe Madalean. Quand quelque chose ne peut venir que de votre distribution — c'est le cas de bubblewrap, qui isole les compilations et les calculs dans un « bac à sable » —, le script affiche la commande exacte à lancer vous-même, par exemple sudo pacman -S bubblewrap sur Arch Linux ou sudo apt install bubblewrap sur Debian et Ubuntu. Les commandes pour chaque distribution sont dans Ce qu'installe Madalean › bubblewrap. Options de install.sh ./install.sh --help les affiche toutes. Option Effet --yes, -y aucune question : les choix par défaut --assistant force l'assistant en terminal (même quand il ne serait pas proposé) --plan FICHIER installe selon un plan enregistré par l'assistant ou par l'installateur graphique --dry-run examine la machine et affiche le plan, sans rien installer --models all prover none modèles locaux : les trois, seulement le prouveur, ou aucun (sans question : les trois ; l'assistant conseille selon la carte graphique) --sage later now system SageMath : à la première utilisation de « Calcul » (défaut), tout de suite, ou celui du système --tex own system LaTeX : celui de Madalean (défaut) ou le TeX Live du système en premier --cpu --gpu moteur des modèles pour le processeur, ou pour la carte NVIDIA (défaut : la carte si le pilote convient) --no-models ne télécharge aucun modèle local (les fichiers déjà dans ~/models restent utilisés) --no-workspaces n'installe aucun espace Lean --build-workspace construit l'espace « Lean actuel » si aucun n'est trouvé (≈ 5 Go, réseau nécessaire) --build-net construit le nœud Tailscale madalean-net à partir des sources (il doit donner exactement l'empreinte attendue) --offline DOSSIER installe sans réseau, depuis un export fait avec ./exportoffline.sh --prefix DOSSIER dossier d'installation (défaut ~/.local/share/madalean) --config-dir DOSSIER dossier des réglages et des données (défaut ~/.config/madalean) --cache-dir DOSSIER dossier des caches (défaut ~/.cache/madalean) --no-systemd n'installe pas le service systemd (lancez alors Madalean vous-même) --no-desktop n'ajoute pas d'entrée au menu des applications --port N, --remote-port N ports du serveur : interface locale (défaut 11500) et accès des appareils reliés (défaut 11501) Où sont enregistrés vos choix Les choix faits à l'installation (modèles locaux, SageMath, LaTeX…) sont écrits dans ~/.config/madalean/setup.json. Madalean lit ce fichier au premier démarrage et applique les réglages qui en découlent, par exemple sagesource (quel SageMath utiliser) et texengine (quel LaTeX utiliser) ; vous pouvez les changer à tout moment (l'application les lit aussi par GET /api/setup). Voir Première configuration › Choix faits à l'installation. Au premier démarrage dans le navigateur de l'hôte, l'assistant « Premiers pas » montre de nouveau ces choix (choix conseillé et raison pour cette machine) et permet de les changer. Où sont les choses Quoi Où Madalean et tous ses composants ~/.local/share/madalean/ Journal d'installation ~/.local/share/madalean/install.log Réglages, choix d'installation, projets, dossiers, appareils reliés, clés (si pas de trousseau) ~/.config/madalean/ Index de recherche, caches ~/.cache/madalean/ Modèles locaux ~/models/ Carnets Jupyter ~/Documents/Madalean/notebooks/ Service systemd ~/.config/systemd/user/madalean.service Au premier démarrage, si vous aviez Lean AI Station 1.x, le serveur copie (sans jamais les déplacer) vos réglages, dossiers et bibliothèque depuis ~/.config/lean-ai-station/. Démarrer et arrêter Le service démarre avec votre session. Ouvrez l'interface sur l'hôte : « Madalean Server » dans le menu des applications, ou http://127.0.0.1:11500 dans un navigateur. « Madalean Server » est l'application de l'ordinateur hôte : elle montre Madalean dans sa propre fenêtre (sans code d'appairage : c'est cet ordinateur) et, dans son menu Serveur (ou son icône près de l'horloge), l'état du serveur, Démarrer, Arrêter, Redémarrer, Ouvrir les journaux et Ouvrir dans le navigateur. Quand le serveur s'arrête, la fenêtre affiche le panneau du serveur ; quand il repart, elle revient d'elle-même sur Madalean. Si le service n'est pas installé, le panneau le dit et donne la commande pour le réinstaller. L'application « Madalean » (AppImage, sans badge) est pour les autres ordinateurs : voir Relier un appareil. En terminal, si besoin : Ensuite : Première configuration, puis Premier démarrage pour un premier énoncé. Installer sans réseau Pour un ordinateur sans accès à Internet : sur une machine connectée où Madalean est installé, ./exportoffline.sh prépare un dossier contenant tout ce qu'il faut (paquets, composants, espaces Lean, modèles). Copiez ce dossier sur l'autre machine (clé USB, disque), puis : Les empreintes SHA-256 sont vérifiées comme pour une installation en ligne. Mettre à jour Madalean se met à jour depuis l'application, dans « Réglages › Mises à jour » : chaque nouvelle version est signée, vérifiée, installée à côté de l'ancienne, puis mise en service ; la version précédente est gardée pour revenir en arrière. Il n'est pas nécessaire de relancer install.sh. Le détail : Mises à jour. Désinstaller Depuis le dossier des sources (ou ~/.local/share/madalean/current) : Le script liste d'abord exactement ce qui sera supprimé, avec la taille de chaque élément, puis demande confirmation. Il arrête d'abord le service et tous ses processus. Supprimé Conservé ~/.local/share/madalean (environnement, composants, espaces Lean installés par Madalean, paquet TeX, état du nœud Tailscale, versions de Madalean) ~/.config/madalean : vos réglages, projets, dossiers, appareils reliés et clés ~/.cache/madalean ~/models : vos modèles le service systemd et l'entrée du menu ~/Documents/Madalean : vos carnets jamais touchés : ~/.elan, les paquets du système, le Tailscale du système Options : Option Effet --purge propose en plus, avec une question pour chacun, de supprimer ~/.config/madalean et ~/models --yes ne demande pas la confirmation générale (les questions de --purge restent posées) --prefix, --config-dir, --cache-dir à donner si vous les aviez changés à l'installation Les clés enregistrées dans le trousseau du système restent dans le trousseau : supprimez-les d'abord dans « Réglages › Fournisseurs » (« Retirer la clé ») si vous voulez les effacer.`},{id:`components`,lang:`fr`,title:`Ce qu'installe Madalean, composant par composant`,order:12,section:`start`,audience:`all`,summary:`Lean, SageMath, JupyterLab, modèles locaux, LaTeX, Python, Tailscale, Ollama, bubblewrap — à quoi sert chacun, s'il est obligatoire, sa taille, où il se trouve, s'il vaut mieux réutiliser ce qui est déjà installé, et comment le réparer ou le retirer.`,source:`fr/components.md`,site_path:`fr/components.html`,headings:[{level:1,text:`Ce qu'installe Madalean, composant par composant`,id:`ce-quinstalle-madalean-composant-par-composant`},{level:2,text:`Vue d'ensemble`,id:`vue-densemble`},{level:2,text:`Réparer, installer plus tard, retirer`,id:`reparer-installer-plus-tard-retirer`},{level:2,text:`Lean, elan et les espaces Mathlib`,id:`lean-elan-et-les-espaces-mathlib`},{level:2,text:`SageMath`,id:`sagemath`},{level:2,text:`JupyterLab`,id:`jupyterlab`},{level:2,text:`Modèles locaux`,id:`modeles-locaux`},{level:2,text:`LaTeX`,id:`latex`},{level:2,text:`Python`,id:`python`},{level:2,text:`Tailscale`,id:`tailscale`},{level:2,text:`Ollama`,id:`ollama`},{level:2,text:`bubblewrap, le bac à sable`,id:`bubblewrap-le-bac-a-sable`}],images:[],verify:[],body:`# Ce qu'installe Madalean, composant par composant

Madalean s'appuie sur plusieurs programmes : Lean pour vérifier les preuves, SageMath pour calculer, LaTeX pour
composer les PDF, des modèles d'IA… Cette page dit, pour chacun, **à quoi il sert**, s'il est **obligatoire**, **la
place qu'il prend**, **où il se trouve**, et s'il vaut mieux **réutiliser** une version déjà installée sur votre
machine ou laisser Madalean installer **sa propre copie**.

Un principe vaut pour tous : Madalean installe ses composants dans **son propre dossier**,
\`~/.local/share/madalean\` (appelé ci-dessous « le dossier de Madalean »). Il ne modifie jamais les programmes de
votre système, ne lance jamais \`sudo\` ni le gestionnaire de paquets de votre distribution. Quand il réutilise un
programme déjà installé, c'est **en lecture seule**.

## Vue d'ensemble

| Composant | Sert à | Obligatoire | Place | Où |
|---|---|---|---|---|
| [Lean, elan, espaces Mathlib](#lean-elan-et-les-espaces-mathlib) | vérifier chaque preuve | oui | ≈ 5 Go par espace construit | dossier de Madalean |
| [SageMath](#sagemath) | l'écran « Calcul », les expériences | non | ≈ 5 Go (copie de Madalean) | dossier de Madalean, ou celui du système |
| [JupyterLab](#jupyterlab) | les carnets | oui (inclus) | compris dans l'environnement principal | dossier de Madalean |
| [Modèles locaux](#modeles-locaux) | travailler sans Internet | non | ≈ 5 Go par modèle | \`~/models\` |
| [LaTeX](#latex) | l'export PDF | oui (inclus) | ≈ 50 Mo pour le paquet TeX | dossier de Madalean, ou TeX Live du système |
| [Python](#python) | faire tourner Madalean | oui (inclus) | compris dans l'environnement principal | dossier de Madalean |
| [Tailscale](#tailscale) | joindre l'hôte depuis vos appareils | oui (inclus) | ≈ 25 Mo | dossier de Madalean |
| [Ollama](#ollama) | — (facultatif, déjà chez vous) | non | — | celui du système |
| [bubblewrap](#bubblewrap-le-bac-a-sable) | isoler compilations et calculs | conseillé | < 1 Mo | paquet du système |

L'environnement principal (Python, JupyterLab, tectonic, poppler, git…) occupe ≈ 1,3 Go une fois installé.

## Réparer, installer plus tard, retirer

**Dans l'application.** « Réglages › Système », partie « État de santé », vérifie chaque composant (espaces Lean,
serveur de modèles local, modèles, LaTeX, polices, Jupyter, SageMath, bac à sable, disque). Une ligne en problème
porte un bouton « Réparer » quand une réparation existe ; « Revérifier » relance le contrôle. Les réparations se
lancent depuis l'ordinateur hôte. « Réglages › Mises à jour », partie « Composants suivis », montre la version
installée de Lean, Mathlib, SageMath et LaTeX, et la partie « Composants du système » les programmes que vous
installez vous-même (comme bubblewrap), avec la commande exacte et le bouton « Ouvrir un terminal avec la commande ».

L'étape « Outils » de l'assistant [« Premiers pas »](first-config.md#lassistant-premiers-pas) (menu du logo ›
« Premiers pas ») liste les mêmes composants, chacun avec son état (installé, installé à la première utilisation,
absent, nouvelle version prête) et un bouton « Installer », « Installer maintenant » ou « Mettre à jour » qui montre
l'étape et le pourcentage pendant l'installation.

**En terminal**, sur l'hôte, le même outil que celui qu'utilise \`install.sh\` :

\`\`\`bash
cd ~/.local/share/madalean/current
~/.local/share/madalean/env/bin/python -m madalean.deps health           # état de chaque composant
~/.local/share/madalean/env/bin/python -m madalean.deps install sage     # installer ou réparer un composant
~/.local/share/madalean/env/bin/python -m madalean.deps list             # composants connus, versions
\`\`\`

Les noms de composants sont \`micromamba\`, \`env\` (l'environnement principal), \`sage\`, \`fonts\`, \`tex-bundle\`, \`elan\`,
\`llama.cpp\` et \`madalean-net\`. \`rollback <composant>\` revient à la version précédente d'un composant.
Relancer \`./install.sh\` répare aussi tout ce qui manque, sans refaire ce qui est en ordre.

**Retirer** un composant obligatoire n'a pas de sens ; tout disparaît avec la [désinstallation](install.md#desinstaller).
Les composants facultatifs se retirent comme indiqué dans leur partie.

## Lean, elan et les espaces Mathlib

**À quoi ça sert.** Lean est le vérificateur de preuves : c'est lui qui tranche, rien n'est déclaré prouvé sans son
accord. Mathlib est la grande bibliothèque de mathématiques écrite en Lean. Un **espace de travail** (ou espace Lean)
est une version de Lean accompagnée d'une Mathlib déjà compilée, prête à l'emploi. **elan** est le petit programme
qui installe et choisit les versions de Lean.

**Obligatoire** : oui.

**Les espaces.**

| Espace | Contenu | Rôle |
|---|---|---|
| « Lean actuel » (\`lean-current\`) | une version récente de Lean (v4.34.1 à l'écriture de cette page) et la Mathlib correspondante | l'espace par défaut, suivi par les mises à jour |
| « Prouveur » (\`lean-prover49\`) | Lean 4.9 et la Mathlib de l'époque | celle sur laquelle les modèles Goedel ont été entraînés ; jamais mis à jour |

**Place** : ≈ 5 Go par espace construit ; elan lui-même pèse ≈ 5 Mo.

**Où** : \`~/.local/share/madalean/workspaces/\` et \`~/.local/share/madalean/elan/\`.

**Réutiliser ou non.** Si des espaces Lean sont déjà construits sur la machine (par exemple ceux de Lean AI
Station 1.x), \`install.sh\` les **reprend par liens physiques** : les fichiers ne sont pas copiés, aucune place en
plus. Les versions de Lean déjà présentes dans votre \`~/.elan\` sont lues pour cet import, **sans jamais être
modifiées**. C'est la solution conseillée quand elle est possible. Sinon, \`./install.sh --build-workspace\`
construit l'espace « Lean actuel » (≈ 5 Go, réseau nécessaire, comptez de longues minutes). L'espace « Prouveur »
n'est pas construit par le script : il est repris s'il existe.

**Installer plus tard, réparer** : « Réglages › Espaces Lean » donne l'état de chaque espace ; relancez
\`./install.sh --build-workspace\` si aucun n'est installé. Les nouvelles versions de Lean et de Mathlib s'installent
depuis « Réglages › Mises à jour » (voir [Mises à jour](updates.md)).

## SageMath

**À quoi ça sert.** SageMath est un logiciel libre de calcul mathématique (algèbre, théorie des nombres,
combinatoire, graphiques…). Madalean l'utilise dans l'écran « Calcul », pour les expériences de l'atelier de
conjectures et pour les exemples et figures d'un article. Voir [Calcul](calcul.md).

**Obligatoire** : non. Sans SageMath, les carnets Python fonctionnent et le reste de Madalean aussi.

**Deux possibilités.**

| | Copie de Madalean | SageMath de votre système |
|---|---|---|
| Version | SageMath 10.10 | la vôtre, **10.0 ou plus récente** |
| Place | ≈ 1,4 Go à télécharger, ≈ 5 Go sur le disque | aucune en plus |
| Mise à jour | par Madalean (« Composants suivis ») | par votre distribution |
| Condition | aucune | le noyau Jupyter \`sagemath\` doit être installé (par exemple dans \`/usr/share/jupyter/kernels/sagemath\`) |

**Ce qui est conseillé.** Si votre système a déjà un SageMath compatible (version ≥ 10.0 **et** son noyau Jupyter
\`sagemath\`), réutilisez-le : vous économisez 5 Go et votre distribution le tient à jour. Sinon, laissez Madalean
installer sa propre copie. Dans les deux cas, le calcul tourne dans **le même bac à sable** : sans réseau, sans accès
à votre dossier personnel (voir [bubblewrap](#bubblewrap-le-bac-a-sable)).

**Le réglage \`sage_source\`** fixe ce choix :

| Valeur | Effet |
|---|---|
| \`auto\` (défaut) | la copie de Madalean si elle est installée, sinon celui du système |
| \`own\` | toujours la copie de Madalean |
| \`system\` | toujours celui du système |

Il est écrit à l'installation (\`--sage\`, ou le choix fait dans l'installateur graphique) et se change ensuite dans
l'application, dans l'étape « Outils » de l'assistant « Premiers pas » (menu du logo, ou « Réglages », lien
« Premiers pas »), qui indique le choix conseillé avec sa raison et la copie utilisée en ce moment. « Celui du
système » n'y est proposé que si un SageMath compatible est présent.

**Installer plus tard.** Par défaut (\`--sage later\`), la copie de Madalean s'installe **à la première utilisation** :
dans un carnet SageMath de l'écran « Calcul », bouton « Installer SageMath », sur l'ordinateur hôte ; l'écran
affiche l'étape et le pourcentage. Pour l'installer tout de suite : \`./install.sh --sage now\`, ou
\`python -m madalean.deps install sage\` (voir [plus haut](#reparer-installer-plus-tard-retirer)).

**Retirer la copie de Madalean** : arrêtez Madalean (\`systemctl --user stop madalean\`), supprimez
\`~/.local/share/madalean/envs/sage\` et les dossiers \`~/.local/share/madalean/envs/sage-…\`, puis redémarrez.
L'application n'a pas de bouton pour cela. Ensuite, SageMath apparaît de nouveau comme « installé à la première
utilisation », et avec \`sage_source\` sur \`auto\` le SageMath du système est utilisé s'il existe.

## JupyterLab

**À quoi ça sert.** JupyterLab est l'environnement de carnets (« notebooks ») : des cellules de code et leurs
résultats. Madalean l'utilise pour les carnets de l'écran « Calcul » et pour l'écran « Carnet » (voir
[Jupyter et Sage](jupyter.md)).

**Obligatoire** : oui, il fait partie de l'environnement principal de Madalean ; il n'y a rien à choisir.

**Où** : dans l'environnement principal, \`~/.local/share/madalean/env/\`. Les carnets eux-mêmes sont rangés dans
\`~/Documents/Madalean/notebooks/\`.

**Accès depuis vos autres appareils** : désactivé par défaut. Le réglage \`remote_jupyter\` (« Réglages › Carnet et
accès » › « Ouvrir le carnet aux appareils reliés », sur l'hôte seulement) l'ouvre aux appareils reliés. Un carnet
exécute du code sur l'hôte : ne l'activez que si vous faites confiance à vos appareils.

**Réparer** : ligne « Jupyter » de l'« État de santé », bouton « Réparer ».

## Modèles locaux

**À quoi ça sert.** Des modèles d'IA qui tournent **sur l'ordinateur hôte**, sans rien envoyer sur Internet. Ils
servent en mode *Local* (rien ne quitte la machine) et, en mode *Automatique*, quand Internet manque. Voir
[Modèles et clés](models-keys.md).

**Obligatoire** : non. Sans modèle local, Madalean utilise les modèles en ligne (gratuits, ou avec vos clés).

**Le moteur, llama.cpp.** C'est le programme qui fait tourner les modèles. \`install.sh\` choisit la version adaptée
à votre machine d'après le pilote NVIDIA : une version pour la carte graphique (CUDA) si le pilote convient, sinon
une version pour le processeur (\`--cpu\` / \`--gpu\` forcent le choix). Il est installé dans le dossier de Madalean
(≈ 25 Mo pour le processeur, ≈ 650 Mo avec les bibliothèques CUDA), même si vous ne prenez aucun modèle.

**Les trois modèles** (fichiers GGUF, quantification Q4_K_M), dans \`~/models\` :

| Fichier | Rôle | Taille |
|---|---|---|
| \`Goedel-Prover-V2-8B.Q4_K_M.gguf\` | le **prouveur** : écrit les preuves Lean | ≈ 5 Go |
| \`Goedel-Formalizer-V2-8B.Q4_K_M.gguf\` | le **traducteur** : met les énoncés en Lean | ≈ 5 Go |
| \`Qwen3-8B-Q4_K_M.gguf\` | l'**explicateur** : explications et preuves rédigées | ≈ 5 Go |

**Quand cela vaut la peine.** Un modèle local n'est utile que s'il tourne sur une carte graphique assez grande. Le
plan recommandé suit cette règle :

| Votre machine | Conseil |
|---|---|
| carte NVIDIA avec 10 Go de mémoire graphique ou plus, et 16 Go de mémoire vive ou plus | les trois modèles (\`--models all\`) |
| carte NVIDIA avec 8 à 10 Go de mémoire graphique | le prouveur seulement (\`--models prover\`) |
| moins de 8 Go, ou pas de carte NVIDIA | **pas de modèle local conseillé** (\`--models none\`) |

Sans carte adaptée, un modèle local tourne sur le processeur : une seule réponse peut prendre de nombreuses
minutes, alors que les modèles en ligne sont à la fois plus rapides et meilleurs. Pour donner un ordre de grandeur,
le prouveur est réglé pour un contexte de 24 000 jetons, ce qui occupe environ 7 Go de mémoire graphique.

**Réutiliser ou non.** Des fichiers déjà présents dans \`~/models\` (avec leur empreinte \`.sha256\`) sont réutilisés et
jamais déplacés.

**Ajouter un modèle plus tard** : relancez \`./install.sh --models all\` (seuls les fichiers manquants sont
téléchargés), ou téléchargez un modèle précis depuis le dossier des sources :

\`\`\`bash
./scripts/download_model.sh Q4_K_M formalizer explainer   # prouveur, traducteur, explicateur
\`\`\`

(n'importe quel sous-ensemble ; \`Q4_K_M\` désigne le prouveur). Chaque fichier est vérifié par son empreinte.

**Libérer la carte graphique.** Le modèle local est arrêté après 10 minutes sans travail, pour rendre la mémoire
graphique aux autres programmes (réglage \`local_idle_unload_minutes\`, 0 = jamais ; voir
[Première configuration](first-config.md#comportements-automatiques-et-manuels)).

**Retirer un modèle** : supprimez son fichier (et le \`.sha256\` qui l'accompagne) dans \`~/models\`. Madalean cesse de
le proposer ; la désinstallation, elle, garde \`~/models\`.

## LaTeX

**À quoi ça sert.** LaTeX compose les documents PDF : export d'un dossier, d'une preuve rédigée, d'un article.

**Obligatoire** : oui, et inclus. Sans LaTeX, Madalean ouvre une version HTML à imprimer depuis le navigateur.

**Deux possibilités.**

| | LaTeX de Madalean (conseillé) | TeX Live de votre système |
|---|---|---|
| Programme | **tectonic**, dans l'environnement principal | \`xelatex\` ou \`lualatex\`, avec \`latexmk\` |
| Paquets LaTeX | un paquet TeX figé (version v33, ≈ 50 Mo), téléchargé une fois à l'installation | tous ceux de votre installation |
| Réseau | aucun après l'installation | aucun |
| Bac à sable | oui | oui |

**Ce qui est conseillé.** Le LaTeX de Madalean : il donne **le même résultat sur toutes les machines** (le paquet TeX
est figé et vérifié), fonctionne **hors ligne** et tourne dans le bac à sable. Un TeX Live déjà installé est de toute
façon utilisé **en secours** si tectonic échoue. Choisissez de l'utiliser **en premier** si vous avez besoin de
paquets LaTeX absents du paquet TeX de Madalean ; il faut alors TeX Live 2022 ou plus récent, avec \`fontspec\`.

**Le réglage \`tex_engine\`** :

| Valeur | Effet |
|---|---|
| \`auto\` (défaut) | tectonic d'abord, TeX Live du système en secours |
| \`tectonic\` | tectonic seulement |
| \`system\` | TeX Live du système d'abord |

Il est écrit à l'installation (\`--tex own\` ou \`--tex system\`, ou le choix fait dans l'installateur graphique), et se
change dans l'étape « Outils » de l'assistant « Premiers pas ». Avec \`system\`, l'export essaie XeLaTeX puis
LuaLaTeX du système, et tectonic en dernier ; avec \`tectonic\`, seulement tectonic (ce choix est refusé tant que le
tectonic de Madalean n'est pas installé).

**Réparer** : ligne « LaTeX (export PDF) » de l'« État de santé », bouton « Réparer », ou
\`python -m madalean.deps install tex-bundle\`. Les polices utilisées dans les PDF (DejaVu Sans Mono, Noto Sans Math)
sont installées avec Madalean et vérifiées au même endroit.

## Python

Madalean a **son propre Python** (3.13), dans son environnement principal (\`~/.local/share/madalean/env/\`). Le
Python de votre système n'est **jamais modifié**, et le serveur ne s'en sert pas. Seul le lanceur des noyaux
d'expériences peut le trouver sur votre système, s'il y en a un, pour démarrer un noyau Python dans le bac à sable.
Rien à choisir, rien à installer.

## Tailscale

**À quoi ça sert.** Tailscale crée un réseau privé chiffré entre vos appareils (votre « tailnet »). Madalean s'en
sert pour que votre téléphone, votre tablette ou un autre PC joignent l'ordinateur hôte, sans rien ouvrir sur
Internet.

**Inclus** : Madalean fournit **son propre nœud Tailscale**, \`madalean-net\` (≈ 25 Mo, dans le dossier de Madalean).
Il apparaît sous le nom « madalean » dans votre tailnet. Il ne demande ni \`sudo\` ni service système.

**Un Tailscale déjà installé** sur l'hôte peut rester en place : aucun conflit, les deux coexistent.

**Configurer** : il faut approuver le nœud une fois dans votre compte Tailscale, puis relier chaque appareil. Voir
[Relier un appareil](pairing.md) et [Tailscale](tailscale.md).

## Ollama

Ollama est un autre programme qui fait tourner des modèles en local. Madalean **ne l'installe pas** et n'en a pas
besoin. S'il est déjà installé et en marche sur l'hôte, ses modèles apparaissent parmi les modèles locaux disponibles
et peuvent être choisis ; les deux programmes coexistent sans conflit.

**Partage de la carte graphique avec Ollama** (« Réglages › Modèles », partie « Modèles locaux » ; activé par
défaut, utile seulement quand Ollama est lancé). Les deux programmes ne tiennent pas ensemble sur une carte de 8 Go.
Quand le modèle local de Madalean ne tient pas, Madalean demande à Ollama de décharger ses modèles (la demande prévue
par Ollama : rien n'est arrêté, Ollama les recharge seul à sa prochaine demande, en 3 secondes environ), charge le
sien, puis rend la carte après \`local_idle_unload_minutes\` sans travail. **Jamais pendant qu'Ollama répond à une autre
application** : Madalean attend qu'il ait fini (30 s au plus, réglable), puis, selon le réglage, charge son modèle
avec la mémoire libre (en partie sur le processeur, plus lent) ou passe au modèle suivant (en ligne). Le panneau
d'état (bouton en haut à droite) et « Réglages › Système › État de santé » disent en clair qui tient la carte.

## bubblewrap, le bac à sable

**À quoi ça sert.** bubblewrap est un petit outil de Linux qui enferme un programme dans un **bac à sable** : sans
réseau, sans accès à votre dossier personnel, avec Lean et Mathlib en lecture seule. Madalean l'utilise pour chaque
compilation Lean, chaque compilation LaTeX et chaque calcul (SageMath, Python). C'est une protection importante, car
le code compilé ou exécuté peut venir d'un modèle d'IA. Voir [Sécurité](security.md).

**Obligatoire** : non, mais **fortement conseillé**. Sans bubblewrap, compilations et calculs tournent sans cette
isolation ; « Réglages › Système » indique si le bac à sable est actif.

**Installer** : c'est un paquet de votre distribution, que Madalean ne peut pas installer à votre place (il faudrait
\`sudo\`). Lancez vous-même la commande correspondant à votre système :

| Distribution | Commande |
|---|---|
| Arch Linux, Manjaro | \`sudo pacman -S bubblewrap\` |
| Debian, Ubuntu, Linux Mint | \`sudo apt install bubblewrap\` |
| Fedora | \`sudo dnf install bubblewrap\` |
| openSUSE | \`sudo zypper install bubblewrap\` |

Puis « Revérifier » dans « Réglages › Système » : la ligne du bac à sable doit passer en ordre.
`,text:`Ce qu'installe Madalean, composant par composant Madalean s'appuie sur plusieurs programmes : Lean pour vérifier les preuves, SageMath pour calculer, LaTeX pour composer les PDF, des modèles d'IA… Cette page dit, pour chacun, à quoi il sert, s'il est obligatoire, la place qu'il prend, où il se trouve, et s'il vaut mieux réutiliser une version déjà installée sur votre machine ou laisser Madalean installer sa propre copie. Un principe vaut pour tous : Madalean installe ses composants dans son propre dossier, ~/.local/share/madalean (appelé ci-dessous « le dossier de Madalean »). Il ne modifie jamais les programmes de votre système, ne lance jamais sudo ni le gestionnaire de paquets de votre distribution. Quand il réutilise un programme déjà installé, c'est en lecture seule. Vue d'ensemble Composant Sert à Obligatoire Place Où Lean, elan, espaces Mathlib vérifier chaque preuve oui ≈ 5 Go par espace construit dossier de Madalean SageMath l'écran « Calcul », les expériences non ≈ 5 Go (copie de Madalean) dossier de Madalean, ou celui du système JupyterLab les carnets oui (inclus) compris dans l'environnement principal dossier de Madalean Modèles locaux travailler sans Internet non ≈ 5 Go par modèle ~/models LaTeX l'export PDF oui (inclus) ≈ 50 Mo pour le paquet TeX dossier de Madalean, ou TeX Live du système Python faire tourner Madalean oui (inclus) compris dans l'environnement principal dossier de Madalean Tailscale joindre l'hôte depuis vos appareils oui (inclus) ≈ 25 Mo dossier de Madalean Ollama — (facultatif, déjà chez vous) non — celui du système bubblewrap isoler compilations et calculs conseillé < 1 Mo paquet du système L'environnement principal (Python, JupyterLab, tectonic, poppler, git…) occupe ≈ 1,3 Go une fois installé. Réparer, installer plus tard, retirer Dans l'application. « Réglages › Système », partie « État de santé », vérifie chaque composant (espaces Lean, serveur de modèles local, modèles, LaTeX, polices, Jupyter, SageMath, bac à sable, disque). Une ligne en problème porte un bouton « Réparer » quand une réparation existe ; « Revérifier » relance le contrôle. Les réparations se lancent depuis l'ordinateur hôte. « Réglages › Mises à jour », partie « Composants suivis », montre la version installée de Lean, Mathlib, SageMath et LaTeX, et la partie « Composants du système » les programmes que vous installez vous-même (comme bubblewrap), avec la commande exacte et le bouton « Ouvrir un terminal avec la commande ». L'étape « Outils » de l'assistant « Premiers pas » (menu du logo › « Premiers pas ») liste les mêmes composants, chacun avec son état (installé, installé à la première utilisation, absent, nouvelle version prête) et un bouton « Installer », « Installer maintenant » ou « Mettre à jour » qui montre l'étape et le pourcentage pendant l'installation. En terminal, sur l'hôte, le même outil que celui qu'utilise install.sh : Les noms de composants sont micromamba, env (l'environnement principal), sage, fonts, tex-bundle, elan, llama.cpp et madalean-net. rollback <composant> revient à la version précédente d'un composant. Relancer ./install.sh répare aussi tout ce qui manque, sans refaire ce qui est en ordre. Retirer un composant obligatoire n'a pas de sens ; tout disparaît avec la désinstallation. Les composants facultatifs se retirent comme indiqué dans leur partie. Lean, elan et les espaces Mathlib À quoi ça sert. Lean est le vérificateur de preuves : c'est lui qui tranche, rien n'est déclaré prouvé sans son accord. Mathlib est la grande bibliothèque de mathématiques écrite en Lean. Un espace de travail (ou espace Lean) est une version de Lean accompagnée d'une Mathlib déjà compilée, prête à l'emploi. elan est le petit programme qui installe et choisit les versions de Lean. Obligatoire : oui. Les espaces. Espace Contenu Rôle « Lean actuel » (lean-current) une version récente de Lean (v4.34.1 à l'écriture de cette page) et la Mathlib correspondante l'espace par défaut, suivi par les mises à jour « Prouveur » (lean-prover49) Lean 4.9 et la Mathlib de l'époque celle sur laquelle les modèles Goedel ont été entraînés ; jamais mis à jour Place : ≈ 5 Go par espace construit ; elan lui-même pèse ≈ 5 Mo. Où : ~/.local/share/madalean/workspaces/ et ~/.local/share/madalean/elan/. Réutiliser ou non. Si des espaces Lean sont déjà construits sur la machine (par exemple ceux de Lean AI Station 1.x), install.sh les reprend par liens physiques : les fichiers ne sont pas copiés, aucune place en plus. Les versions de Lean déjà présentes dans votre ~/.elan sont lues pour cet import, sans jamais être modifiées. C'est la solution conseillée quand elle est possible. Sinon, ./install.sh --build-workspace construit l'espace « Lean actuel » (≈ 5 Go, réseau nécessaire, comptez de longues minutes). L'espace « Prouveur » n'est pas construit par le script : il est repris s'il existe. Installer plus tard, réparer : « Réglages › Espaces Lean » donne l'état de chaque espace ; relancez ./install.sh --build-workspace si aucun n'est installé. Les nouvelles versions de Lean et de Mathlib s'installent depuis « Réglages › Mises à jour » (voir Mises à jour). SageMath À quoi ça sert. SageMath est un logiciel libre de calcul mathématique (algèbre, théorie des nombres, combinatoire, graphiques…). Madalean l'utilise dans l'écran « Calcul », pour les expériences de l'atelier de conjectures et pour les exemples et figures d'un article. Voir Calcul. Obligatoire : non. Sans SageMath, les carnets Python fonctionnent et le reste de Madalean aussi. Deux possibilités. Copie de Madalean SageMath de votre système Version SageMath 10.10 la vôtre, 10.0 ou plus récente Place ≈ 1,4 Go à télécharger, ≈ 5 Go sur le disque aucune en plus Mise à jour par Madalean (« Composants suivis ») par votre distribution Condition aucune le noyau Jupyter sagemath doit être installé (par exemple dans /usr/share/jupyter/kernels/sagemath) Ce qui est conseillé. Si votre système a déjà un SageMath compatible (version ≥ 10.0 et son noyau Jupyter sagemath), réutilisez-le : vous économisez 5 Go et votre distribution le tient à jour. Sinon, laissez Madalean installer sa propre copie. Dans les deux cas, le calcul tourne dans le même bac à sable : sans réseau, sans accès à votre dossier personnel (voir bubblewrap). Le réglage sagesource fixe ce choix : Valeur Effet auto (défaut) la copie de Madalean si elle est installée, sinon celui du système own toujours la copie de Madalean system toujours celui du système Il est écrit à l'installation (--sage, ou le choix fait dans l'installateur graphique) et se change ensuite dans l'application, dans l'étape « Outils » de l'assistant « Premiers pas » (menu du logo, ou « Réglages », lien « Premiers pas »), qui indique le choix conseillé avec sa raison et la copie utilisée en ce moment. « Celui du système » n'y est proposé que si un SageMath compatible est présent. Installer plus tard. Par défaut (--sage later), la copie de Madalean s'installe à la première utilisation : dans un carnet SageMath de l'écran « Calcul », bouton « Installer SageMath », sur l'ordinateur hôte ; l'écran affiche l'étape et le pourcentage. Pour l'installer tout de suite : ./install.sh --sage now, ou python -m madalean.deps install sage (voir plus haut). Retirer la copie de Madalean : arrêtez Madalean (systemctl --user stop madalean), supprimez ~/.local/share/madalean/envs/sage et les dossiers ~/.local/share/madalean/envs/sage-…, puis redémarrez. L'application n'a pas de bouton pour cela. Ensuite, SageMath apparaît de nouveau comme « installé à la première utilisation », et avec sagesource sur auto le SageMath du système est utilisé s'il existe. JupyterLab À quoi ça sert. JupyterLab est l'environnement de carnets (« notebooks ») : des cellules de code et leurs résultats. Madalean l'utilise pour les carnets de l'écran « Calcul » et pour l'écran « Carnet » (voir Jupyter et Sage). Obligatoire : oui, il fait partie de l'environnement principal de Madalean ; il n'y a rien à choisir. Où : dans l'environnement principal, ~/.local/share/madalean/env/. Les carnets eux-mêmes sont rangés dans ~/Documents/Madalean/notebooks/. Accès depuis vos autres appareils : désactivé par défaut. Le réglage remotejupyter (« Réglages › Carnet et accès » › « Ouvrir le carnet aux appareils reliés », sur l'hôte seulement) l'ouvre aux appareils reliés. Un carnet exécute du code sur l'hôte : ne l'activez que si vous faites confiance à vos appareils. Réparer : ligne « Jupyter » de l'« État de santé », bouton « Réparer ». Modèles locaux À quoi ça sert. Des modèles d'IA qui tournent sur l'ordinateur hôte, sans rien envoyer sur Internet. Ils servent en mode Local (rien ne quitte la machine) et, en mode Automatique, quand Internet manque. Voir Modèles et clés. Obligatoire : non. Sans modèle local, Madalean utilise les modèles en ligne (gratuits, ou avec vos clés). Le moteur, llama.cpp. C'est le programme qui fait tourner les modèles. install.sh choisit la version adaptée à votre machine d'après le pilote NVIDIA : une version pour la carte graphique (CUDA) si le pilote convient, sinon une version pour le processeur (--cpu / --gpu forcent le choix). Il est installé dans le dossier de Madalean (≈ 25 Mo pour le processeur, ≈ 650 Mo avec les bibliothèques CUDA), même si vous ne prenez aucun modèle. Les trois modèles (fichiers GGUF, quantification Q4KM), dans ~/models : Fichier Rôle Taille Goedel-Prover-V2-8B.Q4KM.gguf le prouveur : écrit les preuves Lean ≈ 5 Go Goedel-Formalizer-V2-8B.Q4KM.gguf le traducteur : met les énoncés en Lean ≈ 5 Go Qwen3-8B-Q4KM.gguf l'explicateur : explications et preuves rédigées ≈ 5 Go Quand cela vaut la peine. Un modèle local n'est utile que s'il tourne sur une carte graphique assez grande. Le plan recommandé suit cette règle : Votre machine Conseil carte NVIDIA avec 10 Go de mémoire graphique ou plus, et 16 Go de mémoire vive ou plus les trois modèles (--models all) carte NVIDIA avec 8 à 10 Go de mémoire graphique le prouveur seulement (--models prover) moins de 8 Go, ou pas de carte NVIDIA pas de modèle local conseillé (--models none) Sans carte adaptée, un modèle local tourne sur le processeur : une seule réponse peut prendre de nombreuses minutes, alors que les modèles en ligne sont à la fois plus rapides et meilleurs. Pour donner un ordre de grandeur, le prouveur est réglé pour un contexte de 24 000 jetons, ce qui occupe environ 7 Go de mémoire graphique. Réutiliser ou non. Des fichiers déjà présents dans ~/models (avec leur empreinte .sha256) sont réutilisés et jamais déplacés. Ajouter un modèle plus tard : relancez ./install.sh --models all (seuls les fichiers manquants sont téléchargés), ou téléchargez un modèle précis depuis le dossier des sources : (n'importe quel sous-ensemble ; Q4KM désigne le prouveur). Chaque fichier est vérifié par son empreinte. Libérer la carte graphique. Le modèle local est arrêté après 10 minutes sans travail, pour rendre la mémoire graphique aux autres programmes (réglage localidleunloadminutes, 0 = jamais ; voir Première configuration). Retirer un modèle : supprimez son fichier (et le .sha256 qui l'accompagne) dans ~/models. Madalean cesse de le proposer ; la désinstallation, elle, garde ~/models. LaTeX À quoi ça sert. LaTeX compose les documents PDF : export d'un dossier, d'une preuve rédigée, d'un article. Obligatoire : oui, et inclus. Sans LaTeX, Madalean ouvre une version HTML à imprimer depuis le navigateur. Deux possibilités. LaTeX de Madalean (conseillé) TeX Live de votre système Programme tectonic, dans l'environnement principal xelatex ou lualatex, avec latexmk Paquets LaTeX un paquet TeX figé (version v33, ≈ 50 Mo), téléchargé une fois à l'installation tous ceux de votre installation Réseau aucun après l'installation aucun Bac à sable oui oui Ce qui est conseillé. Le LaTeX de Madalean : il donne le même résultat sur toutes les machines (le paquet TeX est figé et vérifié), fonctionne hors ligne et tourne dans le bac à sable. Un TeX Live déjà installé est de toute façon utilisé en secours si tectonic échoue. Choisissez de l'utiliser en premier si vous avez besoin de paquets LaTeX absents du paquet TeX de Madalean ; il faut alors TeX Live 2022 ou plus récent, avec fontspec. Le réglage texengine : Valeur Effet auto (défaut) tectonic d'abord, TeX Live du système en secours tectonic tectonic seulement system TeX Live du système d'abord Il est écrit à l'installation (--tex own ou --tex system, ou le choix fait dans l'installateur graphique), et se change dans l'étape « Outils » de l'assistant « Premiers pas ». Avec system, l'export essaie XeLaTeX puis LuaLaTeX du système, et tectonic en dernier ; avec tectonic, seulement tectonic (ce choix est refusé tant que le tectonic de Madalean n'est pas installé). Réparer : ligne « LaTeX (export PDF) » de l'« État de santé », bouton « Réparer », ou python -m madalean.deps install tex-bundle. Les polices utilisées dans les PDF (DejaVu Sans Mono, Noto Sans Math) sont installées avec Madalean et vérifiées au même endroit. Python Madalean a son propre Python (3.13), dans son environnement principal (~/.local/share/madalean/env/). Le Python de votre système n'est jamais modifié, et le serveur ne s'en sert pas. Seul le lanceur des noyaux d'expériences peut le trouver sur votre système, s'il y en a un, pour démarrer un noyau Python dans le bac à sable. Rien à choisir, rien à installer. Tailscale À quoi ça sert. Tailscale crée un réseau privé chiffré entre vos appareils (votre « tailnet »). Madalean s'en sert pour que votre téléphone, votre tablette ou un autre PC joignent l'ordinateur hôte, sans rien ouvrir sur Internet. Inclus : Madalean fournit son propre nœud Tailscale, madalean-net (≈ 25 Mo, dans le dossier de Madalean). Il apparaît sous le nom « madalean » dans votre tailnet. Il ne demande ni sudo ni service système. Un Tailscale déjà installé sur l'hôte peut rester en place : aucun conflit, les deux coexistent. Configurer : il faut approuver le nœud une fois dans votre compte Tailscale, puis relier chaque appareil. Voir Relier un appareil et Tailscale. Ollama Ollama est un autre programme qui fait tourner des modèles en local. Madalean ne l'installe pas et n'en a pas besoin. S'il est déjà installé et en marche sur l'hôte, ses modèles apparaissent parmi les modèles locaux disponibles et peuvent être choisis ; les deux programmes coexistent sans conflit. Partage de la carte graphique avec Ollama (« Réglages › Modèles », partie « Modèles locaux » ; activé par défaut, utile seulement quand Ollama est lancé). Les deux programmes ne tiennent pas ensemble sur une carte de 8 Go. Quand le modèle local de Madalean ne tient pas, Madalean demande à Ollama de décharger ses modèles (la demande prévue par Ollama : rien n'est arrêté, Ollama les recharge seul à sa prochaine demande, en 3 secondes environ), charge le sien, puis rend la carte après localidleunloadminutes sans travail. Jamais pendant qu'Ollama répond à une autre application : Madalean attend qu'il ait fini (30 s au plus, réglable), puis, selon le réglage, charge son modèle avec la mémoire libre (en partie sur le processeur, plus lent) ou passe au modèle suivant (en ligne). Le panneau d'état (bouton en haut à droite) et « Réglages › Système › État de santé » disent en clair qui tient la carte. bubblewrap, le bac à sable À quoi ça sert. bubblewrap est un petit outil de Linux qui enferme un programme dans un bac à sable : sans réseau, sans accès à votre dossier personnel, avec Lean et Mathlib en lecture seule. Madalean l'utilise pour chaque compilation Lean, chaque compilation LaTeX et chaque calcul (SageMath, Python). C'est une protection importante, car le code compilé ou exécuté peut venir d'un modèle d'IA. Voir Sécurité. Obligatoire : non, mais fortement conseillé. Sans bubblewrap, compilations et calculs tournent sans cette isolation ; « Réglages › Système » indique si le bac à sable est actif. Installer : c'est un paquet de votre distribution, que Madalean ne peut pas installer à votre place (il faudrait sudo). Lancez vous-même la commande correspondant à votre système : Distribution Commande Arch Linux, Manjaro sudo pacman -S bubblewrap Debian, Ubuntu, Linux Mint sudo apt install bubblewrap Fedora sudo dnf install bubblewrap openSUSE sudo zypper install bubblewrap Puis « Revérifier » dans « Réglages › Système » : la ligne du bac à sable doit passer en ordre.`},{id:`first-config`,lang:`fr`,title:`Première configuration`,order:15,section:`start`,audience:`all`,summary:`Après l'installation — les clés des fournisseurs en ligne (où les obtenir, ce qui est gratuit, ce que cela coûte), Claude comme chef d'orchestre et renfort payant, les modes Local / Automatique / En ligne, Apprendre ou Recherche, et chaque comportement automatique avec son réglage par défaut.`,source:`fr/first-config.md`,site_path:`fr/first-config.html`,headings:[{level:1,text:`Première configuration`,id:`premiere-configuration`},{level:2,text:`L'assistant « Premiers pas »`,id:`lassistant-premiers-pas`},{level:2,text:`Clés des fournisseurs en ligne`,id:`cles-des-fournisseurs-en-ligne`},{level:3,text:`Ajouter une clé`,id:`ajouter-une-cle`},{level:3,text:`Où les clés sont gardées`,id:`ou-les-cles-sont-gardees`},{level:3,text:`Par où commencer`,id:`par-ou-commencer`},{level:3,text:`Les fournisseurs, un par un`,id:`les-fournisseurs-un-par-un`},{level:3,text:`Jeton Hugging Face : Goedel-Prover 32B en ligne`,id:`jeton-hugging-face-goedel-prover-32b-en-ligne`},{level:3,text:`Claude : chef d'orchestre et renfort payant`,id:`claude-chef-dorchestre-et-renfort-payant`},{level:2,text:`Où travaillent les modèles`,id:`ou-travaillent-les-modeles`},{level:2,text:`Apprendre ou Recherche`,id:`apprendre-ou-recherche`},{level:2,text:`Comportements automatiques et manuels`,id:`comportements-automatiques-et-manuels`},{level:2,text:`Choix faits à l'installation`,id:`choix-faits-a-linstallation`},{level:2,text:`Liste de vérification`,id:`liste-de-verification`}],images:[{src:`img/wizard-tools.png`,exists:!0},{src:`img/settings-keys.png`,exists:!0},{src:`img/settings-models.png`,exists:!0}],verify:[],body:`# Première configuration

Une fois Madalean installé (voir [Installer Madalean](install.md)), il **fonctionne tout de suite, sans aucune
clé** : des fournisseurs en ligne gratuits sans compte et, si vous les avez installés, les modèles locaux suffisent
pour commencer. Cette page passe en revue ce qu'il est utile de régler ensuite, dans l'ordre où vous le
rencontrerez :

1. les **clés** des fournisseurs en ligne, qui donnent accès à des modèles plus forts ;
2. **où travaillent les modèles** : *Local*, *Automatique* ou *En ligne* ;
3. **Apprendre** ou **Recherche**, et votre profil ;
4. les **comportements automatiques**, que vous pouvez rendre manuels.

Tout se trouve dans « Réglages » (l'icône d'engrenage en haut à droite). Une [liste de vérification](#liste-de-verification)
récapitule le tout à la fin de la page.

## L'assistant « Premiers pas »

Quand vous ouvrez Madalean pour la première fois **sur l'ordinateur hôte**, l'assistant « Premiers pas » s'affiche
en plein écran et vous guide à travers ces mêmes choix, dans l'ordre de cette page. Vos appareils reliés (téléphone,
tablette, autre PC) ne le voient jamais : il ne s'ouvre que là où Madalean est installé.

![Premiers pas : les outils](img/wizard-tools.png)

| Étape | Ce que vous y faites | Pour en savoir plus |
|---|---|---|
| Bienvenue | voir ce qui vous attend, les ressources de la machine, choisir la langue | — |
| Outils | voir les composants installés ou absents, les **installer ou les réparer** (avec la progression) ; choisir quel SageMath (\`sage_source\`) et quel LaTeX (\`tex_engine\`) utiliser, avec le choix conseillé et sa raison ; la commande à taper vous-même pour bubblewrap | [Composants](components.md) |
| Modèle local | aucun, le modèle de preuve ou les trois, selon votre carte graphique (choix conseillé et taille à télécharger) ; « Télécharger » récupère les fichiers manquants, vérifiés | [Modèles locaux](components.md#modeles-locaux) |
| Clés gratuites | une carte par fournisseur (Groq, Gemini, Tavily d'abord) : à quoi il sert, ce qui est gratuit, où créer la clé ; collez-la, « Enregistrer », « Tester » | [Clés](#cles-des-fournisseurs-en-ligne) |
| Hugging Face | le jeton pour Goedel-Prover 32B en ligne, et l'interrupteur \`hf_goedel\` | [plus bas](#jeton-hugging-face-goedel-prover-32b-en-ligne) |
| Claude | la clé Anthropic, les plafonds par demande, par preuve et par mois, le renfort payant | [plus bas](#claude-chef-dorchestre-et-renfort-payant) |
| Modes | *Local*, *Automatique* ou *En ligne* (choix conseillé pour la machine) ; Apprendre ou Recherche | [plus bas](#ou-travaillent-les-modeles) |
| Automatique ou manuel | expériences sans approbation, chef d'orchestre, étapes en parallèle, Lean prêt d'avance, pause après la traduction, mises à jour | [plus bas](#comportements-automatiques-et-manuels) |
| Appareils | relier un téléphone ou un autre PC (le même écran que « Réglages › Appareils ») | [Relier un appareil](pairing.md) |
| Récapitulatif | la [liste de vérification](#liste-de-verification), vérifiée de nouveau, et vos choix ; « Terminer » | — |

- Chaque étape a un lien « Aide » vers la page du manuel qui l'explique.
- Chaque étape se **passe** (« Passer cette étape ») ; chaque choix est **enregistré tout de suite**, sauf les clés,
  qui ne sont enregistrées (et testées) que par leur bouton « Enregistrer ».
- « **Plus tard** » ferme l'assistant. Il ne se rouvre plus tout seul, mais une carte « Premiers pas » reste sur
  l'accueil jusqu'à ce que vous l'ayez terminé (« Reprendre », ou « Ne plus afficher »). L'assistant reprend **là où
  vous vous êtes arrêté** : depuis cette carte, depuis le menu (le logo), entrée « Premiers pas », ou depuis
  « Réglages », lien « Premiers pas : l'assistant de configuration ».
- Après une mise à jour depuis la version 2.0.0, l'assistant ne s'ouvre pas tout seul (votre travail est déjà là) :
  la carte de l'accueil le propose.
- La visite en quatre étapes de l'écran d'accueil ([Premier démarrage](first-run.md)) est distincte : elle montre
  comment prouver un premier énoncé.

## Clés des fournisseurs en ligne

Une **clé d'API** (ou « jeton ») est un mot de passe propre à un service en ligne : elle permet à Madalean d'utiliser
les modèles de ce service en votre nom. Elle se crée en deux minutes sur le site du fournisseur.

### Ajouter une clé

« Réglages › Fournisseurs » range les services en ligne par usage (preuves Lean, rédaction, code, recherche
Internet…), avec pour chacun ce qui est gratuit et où partent vos données. Sur la carte d'un fournisseur :

1. « Créer une clé » ouvre la page de clés du fournisseur ; créez un compte si besoin, puis créez une clé et
   copiez-la (elle n'est souvent montrée qu'une seule fois) ;
2. collez-la sur la carte : Madalean la **teste aussitôt** et dit combien de modèles elle donne, ou pourquoi elle est
   refusée ;
3. « Retirer la clé » la supprime en un clic.

![Réglages › Fournisseurs](img/settings-keys.png)

### Où les clés sont gardées

- Dans le **trousseau du système** (le coffre à mots de passe de votre bureau : GNOME Keyring, KWallet…), quand
  l'outil \`secret-tool\` est disponible ;
- sinon dans le fichier \`~/.config/madalean/keys.json\`, lisible par vous seul (droits \`0600\`).

Une clé n'est **jamais affichée** de nouveau, jamais écrite dans le journal, et **jamais transmise à vos appareils
reliés** : le serveur dit seulement si une clé est enregistrée. Elle n'est envoyée qu'à **son** fournisseur ;
Madalean refuse de la joindre à une autre adresse.

### Par où commencer

Pour un bon départ gratuit, sans carte bancaire pour les deux premiers : **Groq** (modèles rapides), **Google
Gemini** (les plus forts des modèles gratuits) et **Tavily** (recherche Internet). Ajoutez ensuite, selon vos
besoins, un jeton **Hugging Face** pour le meilleur prouveur Lean ouvert, et une clé **Anthropic** si vous acceptez
de payer Claude à l'usage, dans des plafonds que vous fixez.

### Les fournisseurs, un par un

Les offres gratuites changent souvent ; chaque carte de « Réglages › Fournisseurs » indique la date à laquelle elles
ont été vérifiées. Les informations ci-dessous sont celles de cette version de Madalean.

**Preuves Lean**

| Fournisseur | À quoi il sert | Gratuit ? | Où créer la clé |
|---|---|---|---|
| Hugging Face (Goedel-Prover-V2-32B) | le meilleur prouveur Lean ouvert, servi en ligne ; il ouvre chaque preuve | non : payé au jeton avec des crédits Hugging Face (compte gratuit : pas de crédit inclus ; compte PRO : 2 $ par mois) | <https://huggingface.co/settings/tokens> |
| Mistral (Leanstral) | agent de preuve Lean de Mistral, mis en tête du tournoi **si** votre clé Mistral le propose | annoncé gratuit, mais retiré par Mistral le 30/09/2026 ; Madalean le détecte tout seul s'il revient | même clé que Mistral, ci-dessous |

**Rédaction, explications, raisonnement**

| Fournisseur | À quoi il sert | Gratuit ? | Où créer la clé |
|---|---|---|---|
| Google Gemini | les plus forts des modèles gratuits pour rédiger (LaTeX, explications) et raisonner | oui, avec des limites par projet ; l'offre gratuite peut servir à Google pour améliorer ses produits : rien de confidentiel | <https://aistudio.google.com/apikey> |
| Mistral AI | très bon en français ; Codestral pour le code | la facturation doit être activée pour créer une clé ; une clé existante reste valable | <https://console.mistral.ai/api-keys> |
| Anthropic (Claude) | le plus fort en Lean et en rédaction ; chef d'orchestre et renfort payant (voir [plus bas](#claude-chef-dorchestre-et-renfort-payant)) | non : payant à l'usage | <https://console.anthropic.com/settings/keys> |

**Code (Sage, Python) et petites tâches**

| Fournisseur | À quoi il sert | Gratuit ? | Où créer la clé |
|---|---|---|---|
| Groq | très rapide : code Sage/Python, petites tâches, routage | oui, sans carte (30 requêtes par minute, 1 000 par jour et par modèle) | <https://console.groq.com/keys> |
| Cerebras | très rapide : code, calcul, raisonnement | essai : 5 $ offerts une fois, après ajout d'une carte | <https://cloud.cerebras.ai> |
| SambaNova Cloud | modèle de secours gratuit (code, maths) | oui, sans carte (20 requêtes par jour et par modèle) | <https://cloud.sambanova.ai/apis> |

**Modèles généraux de secours, et modèles payants au choix**

| Fournisseur | À quoi il sert | Gratuit ? | Où créer la clé |
|---|---|---|---|
| OpenRouter | des modèles « :free » | oui (50 requêtes par jour ; certains modèles gratuits exigent d'accepter l'entraînement sur vos données) | <https://openrouter.ai/settings/keys> |
| NVIDIA NIM | catalogue d'essai, en secours | essai gratuit limité, réservé aux tests ; pas de travail confidentiel | <https://build.nvidia.com> |
| OpenAI | GPT, seulement si vous le choisissez | non : payant | <https://platform.openai.com/api-keys> |
| DeepSeek | bon en maths et en code, peu cher, seulement si vous le choisissez (serveurs en Chine) | non : payant | <https://platform.deepseek.com/api_keys> |

**Recherche Internet** (pour la recherche documentaire, jamais en mode *Local* ; seule la requête est envoyée)

| Fournisseur | Gratuit ? | Où créer la clé |
|---|---|---|
| Tavily | 1 000 recherches par mois, sans carte | <https://app.tavily.com> |
| Exa | 10 $ de crédits offerts chaque mois | <https://dashboard.exa.ai/api-keys> |
| Brave Search | 5 $ de crédits offerts par mois ; carte exigée | <https://api-dashboard.search.brave.com> |

**Sans clé**, toujours disponibles : les modèles gratuits LLM7, OVHcloud, Kilo et Pollinations (ce que vous leur
envoyez peut être conservé : pour un travail confidentiel, utilisez le mode *Local*), Wikipedia pour la recherche
Internet, arXiv, zbMATH, Crossref, OpenAlex et Semantic Scholar pour la bibliographie, LeanSearch et Loogle pour
chercher dans Mathlib.

**GitHub** a aussi une carte : son jeton sert **seulement** à « Publier » (envoyer le site d'un projet sur votre dépôt
GitHub), jamais à des modèles. Voir [Publier un projet](publish.md).

Un modèle payant n'est jamais utilisé à votre insu : seulement si vous l'avez choisi pour une tâche, ou en renfort
dans vos plafonds (Claude, Goedel 32B en ligne). Ce que reçoit chaque modèle, et les tarifs :
[Modèles et clés](models-keys.md).

### Jeton Hugging Face : Goedel-Prover 32B en ligne

Avec un jeton Hugging Face, **Goedel-Prover-V2-32B** ouvre chaque preuve : la même méthode que le prouveur local,
avec un modèle quatre fois plus grand, sans occuper votre carte graphique.

1. Créez un compte sur Hugging Face et ajoutez des crédits (les appels sont payés au jeton).
2. Sur la carte Hugging Face, « Créer une clé » ouvre la page des jetons, prête à créer un jeton avec la permission
   « Make calls to Inference Providers » ; le jeton commence par \`hf_\`.
3. Collez-le : Madalean le vérifie sans rien facturer et dit si Goedel 32B est disponible.

Réglage \`hf_goedel\` (activé par défaut) : « Réglages › Modèles › Réglages avancés », case « Goedel-Prover 32B en
ligne (Hugging Face) ouvre chaque preuve quand le jeton est enregistré ». Ses dépenses comptent dans le plafond
mensuel décrit ci-dessous. Une tentative coûte au plus ≈ 0,11 $ (estimation prudente de Madalean).

### Claude : chef d'orchestre et renfort payant

Avec une clé Anthropic, Claude peut jouer deux rôles, réglés dans « Réglages › Modèles », partie « Claude en renfort
payant » :

| Rôle | Réglage | Défaut | Ce qu'il fait |
|---|---|---|---|
| **Chef d'orchestre** | \`conductor\` : « Laisser Claude diriger chaque demande » | activé | Claude lit chaque demande, choisit le meilleur modèle pour chaque étape, corrige ce que Lean refuse et vérifie à la fin que l'énoncé, la preuve et l'explication concordent. Sans clé Anthropic, le meilleur modèle gratuit prend ce rôle. Lean reste le seul juge des preuves |
| | \`conductor_cap_usd\` : « Plafond par demande » | 1 $ | une fois atteint, Madalean vous demande s'il faut continuer avec Claude, pour 0,50 $ de plus |
| **Renfort payant** | \`claude_reinforce\` : « Faire appel à Claude quand les modèles gratuits échouent » | activé | Claude entre **en dernier** dans le tournoi d'une preuve, seulement si les modèles gratuits ont tous échoué |
| | \`claude_cap_proof_usd\` : « Plafond par preuve » | 1 $ | au-delà, l'appel n'est pas fait et la preuve le signale |
| | \`claude_cap_month_usd\` : « Plafond par mois » | 20 $ | pour **tous** les appels payants du mois civil (Claude et Goedel 32B sur Hugging Face) |
| | \`claude_model\` : « Modèle Claude » | Automatique | le meilleur modèle Claude pour prouver, ou celui que vous imposez |

Avant chaque appel, Madalean estime son coût au tarif public et ne le fait pas s'il dépasserait un plafond ; après
l'appel, le coût réel est noté. Le total du mois et les derniers appels sont affichés sous les plafonds. La facture
d'Anthropic fait foi. Sans clé Anthropic, aucun de ces réglages ne coûte quoi que ce soit.

## Où travaillent les modèles

« Réglages › Modèles », partie « Où travaillent les modèles » (réglage \`mode\`). L'indicateur en haut de l'écran
rappelle à tout moment le mode en cours et qui reçoit votre travail.

![Réglages › Modèles](img/settings-models.png)

| Mode | Ce qui se passe | Pour qui |
|---|---|---|
| *Local* | rien ne quitte l'ordinateur : seuls les modèles installés sur l'hôte travaillent ; toute connexion vers Internet est refusée avant d'être ouverte | travail confidentiel, machine sans Internet ; suppose des [modèles locaux](components.md#modeles-locaux) et une bonne carte graphique |
| *Automatique* (défaut) | les modèles en ligne ; les modèles locaux **seulement** sans Internet, ou si aucun modèle en ligne ne peut travailler | le meilleur choix pour presque tout le monde : rapide, et la carte graphique reste libre |
| *En ligne* | uniquement des modèles en ligne ; sans réseau, le travail échoue avec un message clair | machine sans modèle local |

Un dossier précis peut avoir un autre mode que le mode général (« Options de ce dossier », sur l'accueil). Juste en
dessous, « Méthode de recherche de preuve » choisit entre *Automatique* (un agent avec le meilleur modèle en ligne
si le mode le permet, sinon Goedel), *Agent* et *Goedel*. Le détail de ce qui part et vers qui :
[Modèles et clés](models-keys.md).

## Apprendre ou Recherche

Le bouton en haut à droite bascule entre deux manières de travailler ; le choix est gardé **sur chaque appareil**
et se change à tout moment :

- **Apprendre** (par défaut) : guidé — indices avant la preuve, glossaire au survol, explications ligne par ligne,
  un tuteur qui vous fait expliquer avec vos mots. Pour qui découvre Lean, étudiant ou enseignant.
- **Recherche** : dense, pensé pour le clavier, rien de pédagogique sur le chemin. Pour qui utilise Lean dans un
  projet de recherche.

**Votre profil** (« Réglages › Profil », réglage \`profile\`) dit à Madalean à qui il s'adresse : public visé,
niveau, notations préférées. Il est lu avant chaque traduction et chaque explication. Voir aussi
[Premier démarrage](first-run.md).

## Comportements automatiques et manuels

Par défaut, Madalean enchaîne seul les étapes d'une preuve, mais **n'exécute jamais sans votre accord** du code
écrit par un modèle, et n'ouvre rien à vos autres appareils sans que vous le décidiez sur l'hôte. Voici chaque
comportement, son réglage, sa valeur par défaut et où le changer. Les réglages marqués **hôte** ne se changent que
depuis l'ordinateur hôte (ils ouvrent la machine à d'autres appareils).

Quelques réglages n'ont pas d'interrupteur dans l'interface : ils se changent dans le fichier
\`~/.config/madalean/settings.json\`, Madalean arrêté (\`systemctl --user stop madalean\`, modifier, puis
\`systemctl --user start madalean\`).

**Chaîne de preuve** — « Réglages › Modèles › Réglages avancés »

| Réglage | Défaut | Libellé dans l'application, et effet |
|---|---|---|
| \`pause_after_translation\` | non | « Faire une pause après la traduction (pour relire) » : activé, Madalean s'arrête après la traduction en Lean et attend que vous la validiez ; sinon la chaîne est entièrement automatique |
| \`statement_check\` | oui | « Vérifier chaque énoncé avant de le prouver (fidélité, contre-exemples) » |
| \`mathlib_first\` | oui | « Chercher d'abord le théorème dans Mathlib » |
| \`tournament_enabled\` | oui | « Tournoi de modèles pour les preuves » : les meilleurs modèles d'abord, puis une course entre d'autres ; avec \`tournament_contestants\` (3 modèles par course), \`tournament_max_rounds\` (3 courses), \`tournament_max_minutes\` (40 min au plus par preuve), \`tournament_attempts_per_model\` (4 essais du meilleur modèle) |
| \`lean_warm\` | oui | « Garder Lean prêt d'avance pendant une preuve » : les essais sont vérifiés en une fraction de seconde, au prix d'environ 3,4 Go de mémoire vive par espace Lean en service |
| \`lean_warm_idle_minutes\` | 10 | « Arrêter Lean prêt d'avance après (min sans essai) » |
| \`parallel_stages\` | oui | *pas d'interrupteur* : une fois l'énoncé accepté par Lean, lecture guidée, vérification de l'énoncé, recherche dans Mathlib et recherche de preuve avancent en même temps ; désactivé (ou en mode *Local*), une étape après l'autre |

**Claude** — « Réglages › Modèles », partie « Claude en renfort payant » : \`conductor\`, \`conductor_cap_usd\`,
\`claude_reinforce\`, \`claude_cap_proof_usd\`, \`claude_cap_month_usd\`, \`claude_model\`, décrits
[plus haut](#claude-chef-dorchestre-et-renfort-payant).

**Code et calcul** — « Réglages › Carnet et accès »

| Réglage | Défaut | Libellé dans l'application, et effet |
|---|---|---|
| \`experiments_auto\` | non (hôte) | « Lancer les expériences sans approbation » : par défaut, le code écrit par un modèle (Sage, Python) **attend votre accord** avant de s'exécuter ; déconseillé de l'activer |
| \`experiments_remote\` | non (hôte) | « Autoriser les expériences depuis les appareils reliés » (le code s'exécute toujours sur l'hôte, dans le bac à sable) |
| \`agent_exec\` | non (hôte) | « Laisser l'agent exécuter du code » : l'agent peut alors lancer des calculs dans le dossier du projet |
| \`remote_jupyter\` | non (hôte) | « Ouvrir le carnet aux appareils reliés » |
| \`lan_listener\` | non (hôte) | « Accès depuis le réseau local (sans Tailscale) » : pour un réseau domestique sans Tailscale ; les appareils doivent quand même être reliés |

**Ressources de la machine** — sans interrupteur (fichier \`settings.json\`)

| Réglage | Défaut | Effet |
|---|---|---|
| \`local_idle_unload_minutes\` | 10 | le modèle local s'arrête après ce temps sans travail, pour rendre la mémoire graphique (0 = jamais) |
| \`gpu_share_ollama\` | oui (hôte) | partage de la carte graphique avec Ollama : faire décharger ses modèles quand la place manque, jamais pendant qu'il répond |
| \`gpu_share_busy_wait_s\` | 30 (hôte) | attente maximale quand Ollama répond à une autre application |
| \`gpu_share_busy_fallback\` | \`cpu\` (hôte) | ensuite : \`cpu\` (mémoire libre, en partie sur le processeur) ou \`online\` (modèle suivant, en ligne) |
| \`calcul_idle_minutes\` | 30 | le noyau d'un carnet de « Calcul » s'arrête après ce temps sans activité (0 = jamais) |
| \`browser_session_idle_minutes\` | 120 (hôte) | une session ouverte dans un navigateur depuis un autre appareil se ferme après ce temps d'inactivité |

**Réseau et mises à jour**

| Réglage | Défaut | Où, et effet |
|---|---|---|
| \`check_updates\` | oui | « Réglages › Mises à jour » › « Chercher les mises à jour chaque semaine » (jamais en mode *Local*) |
| \`updates_auto\` | oui (hôte) | « Réglages › Mises à jour » › « Installer automatiquement quand rien ne tourne » : décoché, vous êtes prévenu avant chaque installation. Voir [Mises à jour](updates.md) |
| \`web_search\` | oui | « Réglages › Fournisseurs » › « Recherche Internet pour la recherche documentaire » (jamais en mode *Local* ; seule la requête est envoyée) |
| \`offline\` | — | ancien réglage de Lean AI Station 1.x, remplacé par le mode *Local* ; il ne sert plus qu'à la reprise des réglages de la version 1 |

## Choix faits à l'installation

L'installateur (graphique ou en terminal) écrit vos choix dans \`~/.config/madalean/setup.json\` ; Madalean les
applique au premier démarrage. Deux d'entre eux deviennent des réglages :

| Réglage | Valeurs | Défaut | Effet |
|---|---|---|---|
| \`sage_source\` | \`auto\`, \`own\`, \`system\` | \`auto\` | quel SageMath utiliser : \`auto\` = la copie de Madalean si elle est installée, sinon celui du système ; \`system\` = celui du système seulement ; \`own\` = la copie de Madalean seulement (voir [SageMath](components.md#sagemath)) |
| \`tex_engine\` | \`auto\`, \`tectonic\`, \`system\` | \`auto\` | quel LaTeX utiliser : tectonic d'abord, le TeX Live du système en secours (voir [LaTeX](components.md#latex)) |

Les modèles locaux choisis à l'installation sont simplement les fichiers présents dans \`~/models\`.

Dans l'application, \`sage_source\` et \`tex_engine\` se voient et se changent dans l'étape « Outils » de l'assistant
« Premiers pas » (menu du logo, ou « Réglages », lien « Premiers pas »). Madalean vérifie le choix avant de
l'enregistrer : « Celui du système » demande un SageMath compatible (10.0 ou plus, avec son noyau Jupyter
« sagemath ») ou un TeX Live (XeLaTeX ou LuaLaTeX), « tectonic seulement » le tectonic de Madalean ; sinon le choix
est refusé avec la raison. L'étape dit aussi quelle copie est utilisée en ce moment.

## Liste de vérification

| À faire | Où | Indispensable ? |
|---|---|---|
| Suivre l'assistant « Premiers pas » (ou le reprendre) | s'ouvre au premier démarrage ; menu du logo › « Premiers pas » | conseillé |
| Ouvrir Madalean et vérifier que tout est en ordre | « Réglages › Système », partie « État de santé » | oui |
| Installer bubblewrap si le bac à sable est signalé inactif | terminal, voir [bubblewrap](components.md#bubblewrap-le-bac-a-sable) | fortement conseillé |
| Ajouter une ou deux clés gratuites (Groq, Gemini) | « Réglages › Fournisseurs » | conseillé |
| Ajouter une clé de recherche Internet (Tavily) | « Réglages › Fournisseurs » | pour la recherche documentaire |
| Jeton Hugging Face, clé Anthropic, et leurs plafonds | « Réglages › Fournisseurs », puis « Réglages › Modèles » | facultatif, payant |
| Choisir où travaillent les modèles | « Réglages › Modèles » | le défaut *Automatique* convient presque toujours |
| Choisir Apprendre ou Recherche, remplir le profil | bouton en haut à droite ; « Réglages › Profil » | conseillé |
| Décider des comportements automatiques | « Réglages › Modèles › Réglages avancés », « Réglages › Carnet et accès » | les défauts sont prudents |
| Relier un téléphone ou un autre PC | « Réglages › Appareils », voir [Relier un appareil](pairing.md) | si vous en avez besoin |
| Faire un premier essai | l'accueil, voir [Premier démarrage](first-run.md) | — |
`,text:`Première configuration Une fois Madalean installé (voir Installer Madalean), il fonctionne tout de suite, sans aucune clé : des fournisseurs en ligne gratuits sans compte et, si vous les avez installés, les modèles locaux suffisent pour commencer. Cette page passe en revue ce qu'il est utile de régler ensuite, dans l'ordre où vous le rencontrerez : 1. les clés des fournisseurs en ligne, qui donnent accès à des modèles plus forts ; 2. où travaillent les modèles : Local, Automatique ou En ligne ; 3. Apprendre ou Recherche, et votre profil ; 4. les comportements automatiques, que vous pouvez rendre manuels. Tout se trouve dans « Réglages » (l'icône d'engrenage en haut à droite). Une liste de vérification récapitule le tout à la fin de la page. L'assistant « Premiers pas » Quand vous ouvrez Madalean pour la première fois sur l'ordinateur hôte, l'assistant « Premiers pas » s'affiche en plein écran et vous guide à travers ces mêmes choix, dans l'ordre de cette page. Vos appareils reliés (téléphone, tablette, autre PC) ne le voient jamais : il ne s'ouvre que là où Madalean est installé. Premiers pas : les outils Étape Ce que vous y faites Pour en savoir plus Bienvenue voir ce qui vous attend, les ressources de la machine, choisir la langue — Outils voir les composants installés ou absents, les installer ou les réparer (avec la progression) ; choisir quel SageMath (sagesource) et quel LaTeX (texengine) utiliser, avec le choix conseillé et sa raison ; la commande à taper vous-même pour bubblewrap Composants Modèle local aucun, le modèle de preuve ou les trois, selon votre carte graphique (choix conseillé et taille à télécharger) ; « Télécharger » récupère les fichiers manquants, vérifiés Modèles locaux Clés gratuites une carte par fournisseur (Groq, Gemini, Tavily d'abord) : à quoi il sert, ce qui est gratuit, où créer la clé ; collez-la, « Enregistrer », « Tester » Clés Hugging Face le jeton pour Goedel-Prover 32B en ligne, et l'interrupteur hfgoedel plus bas Claude la clé Anthropic, les plafonds par demande, par preuve et par mois, le renfort payant plus bas Modes Local, Automatique ou En ligne (choix conseillé pour la machine) ; Apprendre ou Recherche plus bas Automatique ou manuel expériences sans approbation, chef d'orchestre, étapes en parallèle, Lean prêt d'avance, pause après la traduction, mises à jour plus bas Appareils relier un téléphone ou un autre PC (le même écran que « Réglages › Appareils ») Relier un appareil Récapitulatif la liste de vérification, vérifiée de nouveau, et vos choix ; « Terminer » — - Chaque étape a un lien « Aide » vers la page du manuel qui l'explique. - Chaque étape se passe (« Passer cette étape ») ; chaque choix est enregistré tout de suite, sauf les clés, qui ne sont enregistrées (et testées) que par leur bouton « Enregistrer ». - « Plus tard » ferme l'assistant. Il ne se rouvre plus tout seul, mais une carte « Premiers pas » reste sur l'accueil jusqu'à ce que vous l'ayez terminé (« Reprendre », ou « Ne plus afficher »). L'assistant reprend là où vous vous êtes arrêté : depuis cette carte, depuis le menu (le logo), entrée « Premiers pas », ou depuis « Réglages », lien « Premiers pas : l'assistant de configuration ». - Après une mise à jour depuis la version 2.0.0, l'assistant ne s'ouvre pas tout seul (votre travail est déjà là) : la carte de l'accueil le propose. - La visite en quatre étapes de l'écran d'accueil (Premier démarrage) est distincte : elle montre comment prouver un premier énoncé. Clés des fournisseurs en ligne Une clé d'API (ou « jeton ») est un mot de passe propre à un service en ligne : elle permet à Madalean d'utiliser les modèles de ce service en votre nom. Elle se crée en deux minutes sur le site du fournisseur. Ajouter une clé « Réglages › Fournisseurs » range les services en ligne par usage (preuves Lean, rédaction, code, recherche Internet…), avec pour chacun ce qui est gratuit et où partent vos données. Sur la carte d'un fournisseur : 1. « Créer une clé » ouvre la page de clés du fournisseur ; créez un compte si besoin, puis créez une clé et copiez-la (elle n'est souvent montrée qu'une seule fois) ; 2. collez-la sur la carte : Madalean la teste aussitôt et dit combien de modèles elle donne, ou pourquoi elle est refusée ; 3. « Retirer la clé » la supprime en un clic. Réglages › Fournisseurs Où les clés sont gardées - Dans le trousseau du système (le coffre à mots de passe de votre bureau : GNOME Keyring, KWallet…), quand l'outil secret-tool est disponible ; - sinon dans le fichier ~/.config/madalean/keys.json, lisible par vous seul (droits 0600). Une clé n'est jamais affichée de nouveau, jamais écrite dans le journal, et jamais transmise à vos appareils reliés : le serveur dit seulement si une clé est enregistrée. Elle n'est envoyée qu'à son fournisseur ; Madalean refuse de la joindre à une autre adresse. Par où commencer Pour un bon départ gratuit, sans carte bancaire pour les deux premiers : Groq (modèles rapides), Google Gemini (les plus forts des modèles gratuits) et Tavily (recherche Internet). Ajoutez ensuite, selon vos besoins, un jeton Hugging Face pour le meilleur prouveur Lean ouvert, et une clé Anthropic si vous acceptez de payer Claude à l'usage, dans des plafonds que vous fixez. Les fournisseurs, un par un Les offres gratuites changent souvent ; chaque carte de « Réglages › Fournisseurs » indique la date à laquelle elles ont été vérifiées. Les informations ci-dessous sont celles de cette version de Madalean. Preuves Lean Fournisseur À quoi il sert Gratuit ? Où créer la clé Hugging Face (Goedel-Prover-V2-32B) le meilleur prouveur Lean ouvert, servi en ligne ; il ouvre chaque preuve non : payé au jeton avec des crédits Hugging Face (compte gratuit : pas de crédit inclus ; compte PRO : 2 $ par mois) <https://huggingface.co/settings/tokens> Mistral (Leanstral) agent de preuve Lean de Mistral, mis en tête du tournoi si votre clé Mistral le propose annoncé gratuit, mais retiré par Mistral le 30/09/2026 ; Madalean le détecte tout seul s'il revient même clé que Mistral, ci-dessous Rédaction, explications, raisonnement Fournisseur À quoi il sert Gratuit ? Où créer la clé Google Gemini les plus forts des modèles gratuits pour rédiger (LaTeX, explications) et raisonner oui, avec des limites par projet ; l'offre gratuite peut servir à Google pour améliorer ses produits : rien de confidentiel <https://aistudio.google.com/apikey> Mistral AI très bon en français ; Codestral pour le code la facturation doit être activée pour créer une clé ; une clé existante reste valable <https://console.mistral.ai/api-keys> Anthropic (Claude) le plus fort en Lean et en rédaction ; chef d'orchestre et renfort payant (voir plus bas) non : payant à l'usage <https://console.anthropic.com/settings/keys> Code (Sage, Python) et petites tâches Fournisseur À quoi il sert Gratuit ? Où créer la clé Groq très rapide : code Sage/Python, petites tâches, routage oui, sans carte (30 requêtes par minute, 1 000 par jour et par modèle) <https://console.groq.com/keys> Cerebras très rapide : code, calcul, raisonnement essai : 5 $ offerts une fois, après ajout d'une carte <https://cloud.cerebras.ai> SambaNova Cloud modèle de secours gratuit (code, maths) oui, sans carte (20 requêtes par jour et par modèle) <https://cloud.sambanova.ai/apis> Modèles généraux de secours, et modèles payants au choix Fournisseur À quoi il sert Gratuit ? Où créer la clé OpenRouter des modèles « :free » oui (50 requêtes par jour ; certains modèles gratuits exigent d'accepter l'entraînement sur vos données) <https://openrouter.ai/settings/keys> NVIDIA NIM catalogue d'essai, en secours essai gratuit limité, réservé aux tests ; pas de travail confidentiel <https://build.nvidia.com> OpenAI GPT, seulement si vous le choisissez non : payant <https://platform.openai.com/api-keys> DeepSeek bon en maths et en code, peu cher, seulement si vous le choisissez (serveurs en Chine) non : payant <https://platform.deepseek.com/apikeys> Recherche Internet (pour la recherche documentaire, jamais en mode Local ; seule la requête est envoyée) Fournisseur Gratuit ? Où créer la clé Tavily 1 000 recherches par mois, sans carte <https://app.tavily.com> Exa 10 $ de crédits offerts chaque mois <https://dashboard.exa.ai/api-keys> Brave Search 5 $ de crédits offerts par mois ; carte exigée <https://api-dashboard.search.brave.com> Sans clé, toujours disponibles : les modèles gratuits LLM7, OVHcloud, Kilo et Pollinations (ce que vous leur envoyez peut être conservé : pour un travail confidentiel, utilisez le mode Local), Wikipedia pour la recherche Internet, arXiv, zbMATH, Crossref, OpenAlex et Semantic Scholar pour la bibliographie, LeanSearch et Loogle pour chercher dans Mathlib. GitHub a aussi une carte : son jeton sert seulement à « Publier » (envoyer le site d'un projet sur votre dépôt GitHub), jamais à des modèles. Voir Publier un projet. Un modèle payant n'est jamais utilisé à votre insu : seulement si vous l'avez choisi pour une tâche, ou en renfort dans vos plafonds (Claude, Goedel 32B en ligne). Ce que reçoit chaque modèle, et les tarifs : Modèles et clés. Jeton Hugging Face : Goedel-Prover 32B en ligne Avec un jeton Hugging Face, Goedel-Prover-V2-32B ouvre chaque preuve : la même méthode que le prouveur local, avec un modèle quatre fois plus grand, sans occuper votre carte graphique. 1. Créez un compte sur Hugging Face et ajoutez des crédits (les appels sont payés au jeton). 2. Sur la carte Hugging Face, « Créer une clé » ouvre la page des jetons, prête à créer un jeton avec la permission « Make calls to Inference Providers » ; le jeton commence par hf. 3. Collez-le : Madalean le vérifie sans rien facturer et dit si Goedel 32B est disponible. Réglage hfgoedel (activé par défaut) : « Réglages › Modèles › Réglages avancés », case « Goedel-Prover 32B en ligne (Hugging Face) ouvre chaque preuve quand le jeton est enregistré ». Ses dépenses comptent dans le plafond mensuel décrit ci-dessous. Une tentative coûte au plus ≈ 0,11 $ (estimation prudente de Madalean). Claude : chef d'orchestre et renfort payant Avec une clé Anthropic, Claude peut jouer deux rôles, réglés dans « Réglages › Modèles », partie « Claude en renfort payant » : Rôle Réglage Défaut Ce qu'il fait Chef d'orchestre conductor : « Laisser Claude diriger chaque demande » activé Claude lit chaque demande, choisit le meilleur modèle pour chaque étape, corrige ce que Lean refuse et vérifie à la fin que l'énoncé, la preuve et l'explication concordent. Sans clé Anthropic, le meilleur modèle gratuit prend ce rôle. Lean reste le seul juge des preuves conductorcapusd : « Plafond par demande » 1 $ une fois atteint, Madalean vous demande s'il faut continuer avec Claude, pour 0,50 $ de plus Renfort payant claudereinforce : « Faire appel à Claude quand les modèles gratuits échouent » activé Claude entre en dernier dans le tournoi d'une preuve, seulement si les modèles gratuits ont tous échoué claudecapproofusd : « Plafond par preuve » 1 $ au-delà, l'appel n'est pas fait et la preuve le signale claudecapmonthusd : « Plafond par mois » 20 $ pour tous les appels payants du mois civil (Claude et Goedel 32B sur Hugging Face) claudemodel : « Modèle Claude » Automatique le meilleur modèle Claude pour prouver, ou celui que vous imposez Avant chaque appel, Madalean estime son coût au tarif public et ne le fait pas s'il dépasserait un plafond ; après l'appel, le coût réel est noté. Le total du mois et les derniers appels sont affichés sous les plafonds. La facture d'Anthropic fait foi. Sans clé Anthropic, aucun de ces réglages ne coûte quoi que ce soit. Où travaillent les modèles « Réglages › Modèles », partie « Où travaillent les modèles » (réglage mode). L'indicateur en haut de l'écran rappelle à tout moment le mode en cours et qui reçoit votre travail. Réglages › Modèles Mode Ce qui se passe Pour qui Local rien ne quitte l'ordinateur : seuls les modèles installés sur l'hôte travaillent ; toute connexion vers Internet est refusée avant d'être ouverte travail confidentiel, machine sans Internet ; suppose des modèles locaux et une bonne carte graphique Automatique (défaut) les modèles en ligne ; les modèles locaux seulement sans Internet, ou si aucun modèle en ligne ne peut travailler le meilleur choix pour presque tout le monde : rapide, et la carte graphique reste libre En ligne uniquement des modèles en ligne ; sans réseau, le travail échoue avec un message clair machine sans modèle local Un dossier précis peut avoir un autre mode que le mode général (« Options de ce dossier », sur l'accueil). Juste en dessous, « Méthode de recherche de preuve » choisit entre Automatique (un agent avec le meilleur modèle en ligne si le mode le permet, sinon Goedel), Agent et Goedel. Le détail de ce qui part et vers qui : Modèles et clés. Apprendre ou Recherche Le bouton en haut à droite bascule entre deux manières de travailler ; le choix est gardé sur chaque appareil et se change à tout moment : - Apprendre (par défaut) : guidé — indices avant la preuve, glossaire au survol, explications ligne par ligne, un tuteur qui vous fait expliquer avec vos mots. Pour qui découvre Lean, étudiant ou enseignant. - Recherche : dense, pensé pour le clavier, rien de pédagogique sur le chemin. Pour qui utilise Lean dans un projet de recherche. Votre profil (« Réglages › Profil », réglage profile) dit à Madalean à qui il s'adresse : public visé, niveau, notations préférées. Il est lu avant chaque traduction et chaque explication. Voir aussi Premier démarrage. Comportements automatiques et manuels Par défaut, Madalean enchaîne seul les étapes d'une preuve, mais n'exécute jamais sans votre accord du code écrit par un modèle, et n'ouvre rien à vos autres appareils sans que vous le décidiez sur l'hôte. Voici chaque comportement, son réglage, sa valeur par défaut et où le changer. Les réglages marqués hôte ne se changent que depuis l'ordinateur hôte (ils ouvrent la machine à d'autres appareils). Quelques réglages n'ont pas d'interrupteur dans l'interface : ils se changent dans le fichier ~/.config/madalean/settings.json, Madalean arrêté (systemctl --user stop madalean, modifier, puis systemctl --user start madalean). Chaîne de preuve — « Réglages › Modèles › Réglages avancés » Réglage Défaut Libellé dans l'application, et effet pauseaftertranslation non « Faire une pause après la traduction (pour relire) » : activé, Madalean s'arrête après la traduction en Lean et attend que vous la validiez ; sinon la chaîne est entièrement automatique statementcheck oui « Vérifier chaque énoncé avant de le prouver (fidélité, contre-exemples) » mathlibfirst oui « Chercher d'abord le théorème dans Mathlib » tournamentenabled oui « Tournoi de modèles pour les preuves » : les meilleurs modèles d'abord, puis une course entre d'autres ; avec tournamentcontestants (3 modèles par course), tournamentmaxrounds (3 courses), tournamentmaxminutes (40 min au plus par preuve), tournamentattemptspermodel (4 essais du meilleur modèle) leanwarm oui « Garder Lean prêt d'avance pendant une preuve » : les essais sont vérifiés en une fraction de seconde, au prix d'environ 3,4 Go de mémoire vive par espace Lean en service leanwarmidleminutes 10 « Arrêter Lean prêt d'avance après (min sans essai) » parallelstages oui pas d'interrupteur : une fois l'énoncé accepté par Lean, lecture guidée, vérification de l'énoncé, recherche dans Mathlib et recherche de preuve avancent en même temps ; désactivé (ou en mode Local), une étape après l'autre Claude — « Réglages › Modèles », partie « Claude en renfort payant » : conductor, conductorcapusd, claudereinforce, claudecapproofusd, claudecapmonthusd, claudemodel, décrits plus haut. Code et calcul — « Réglages › Carnet et accès » Réglage Défaut Libellé dans l'application, et effet experimentsauto non (hôte) « Lancer les expériences sans approbation » : par défaut, le code écrit par un modèle (Sage, Python) attend votre accord avant de s'exécuter ; déconseillé de l'activer experimentsremote non (hôte) « Autoriser les expériences depuis les appareils reliés » (le code s'exécute toujours sur l'hôte, dans le bac à sable) agentexec non (hôte) « Laisser l'agent exécuter du code » : l'agent peut alors lancer des calculs dans le dossier du projet remotejupyter non (hôte) « Ouvrir le carnet aux appareils reliés » lanlistener non (hôte) « Accès depuis le réseau local (sans Tailscale) » : pour un réseau domestique sans Tailscale ; les appareils doivent quand même être reliés Ressources de la machine — sans interrupteur (fichier settings.json) Réglage Défaut Effet localidleunloadminutes 10 le modèle local s'arrête après ce temps sans travail, pour rendre la mémoire graphique (0 = jamais) gpushareollama oui (hôte) partage de la carte graphique avec Ollama : faire décharger ses modèles quand la place manque, jamais pendant qu'il répond gpusharebusywaits 30 (hôte) attente maximale quand Ollama répond à une autre application gpusharebusyfallback cpu (hôte) ensuite : cpu (mémoire libre, en partie sur le processeur) ou online (modèle suivant, en ligne) calculidleminutes 30 le noyau d'un carnet de « Calcul » s'arrête après ce temps sans activité (0 = jamais) browsersessionidleminutes 120 (hôte) une session ouverte dans un navigateur depuis un autre appareil se ferme après ce temps d'inactivité Réseau et mises à jour Réglage Défaut Où, et effet checkupdates oui « Réglages › Mises à jour » › « Chercher les mises à jour chaque semaine » (jamais en mode Local) updatesauto oui (hôte) « Réglages › Mises à jour » › « Installer automatiquement quand rien ne tourne » : décoché, vous êtes prévenu avant chaque installation. Voir Mises à jour websearch oui « Réglages › Fournisseurs » › « Recherche Internet pour la recherche documentaire » (jamais en mode Local ; seule la requête est envoyée) offline — ancien réglage de Lean AI Station 1.x, remplacé par le mode Local ; il ne sert plus qu'à la reprise des réglages de la version 1 Choix faits à l'installation L'installateur (graphique ou en terminal) écrit vos choix dans ~/.config/madalean/setup.json ; Madalean les applique au premier démarrage. Deux d'entre eux deviennent des réglages : Réglage Valeurs Défaut Effet sagesource auto, own, system auto quel SageMath utiliser : auto = la copie de Madalean si elle est installée, sinon celui du système ; system = celui du système seulement ; own = la copie de Madalean seulement (voir SageMath) texengine auto, tectonic, system auto quel LaTeX utiliser : tectonic d'abord, le TeX Live du système en secours (voir LaTeX) Les modèles locaux choisis à l'installation sont simplement les fichiers présents dans ~/models. Dans l'application, sagesource et texengine se voient et se changent dans l'étape « Outils » de l'assistant « Premiers pas » (menu du logo, ou « Réglages », lien « Premiers pas »). Madalean vérifie le choix avant de l'enregistrer : « Celui du système » demande un SageMath compatible (10.0 ou plus, avec son noyau Jupyter « sagemath ») ou un TeX Live (XeLaTeX ou LuaLaTeX), « tectonic seulement » le tectonic de Madalean ; sinon le choix est refusé avec la raison. L'étape dit aussi quelle copie est utilisée en ce moment. Liste de vérification À faire Où Indispensable ? Suivre l'assistant « Premiers pas » (ou le reprendre) s'ouvre au premier démarrage ; menu du logo › « Premiers pas » conseillé Ouvrir Madalean et vérifier que tout est en ordre « Réglages › Système », partie « État de santé » oui Installer bubblewrap si le bac à sable est signalé inactif terminal, voir bubblewrap fortement conseillé Ajouter une ou deux clés gratuites (Groq, Gemini) « Réglages › Fournisseurs » conseillé Ajouter une clé de recherche Internet (Tavily) « Réglages › Fournisseurs » pour la recherche documentaire Jeton Hugging Face, clé Anthropic, et leurs plafonds « Réglages › Fournisseurs », puis « Réglages › Modèles » facultatif, payant Choisir où travaillent les modèles « Réglages › Modèles » le défaut Automatique convient presque toujours Choisir Apprendre ou Recherche, remplir le profil bouton en haut à droite ; « Réglages › Profil » conseillé Décider des comportements automatiques « Réglages › Modèles › Réglages avancés », « Réglages › Carnet et accès » les défauts sont prudents Relier un téléphone ou un autre PC « Réglages › Appareils », voir Relier un appareil si vous en avez besoin Faire un premier essai l'accueil, voir Premier démarrage —`},{id:`first-run`,lang:`fr`,title:`Premier démarrage`,order:20,section:`start`,audience:`all`,summary:`Visite guidée, choix du mode, premier énoncé, mode démo.`,source:`fr/first-run.md`,site_path:`fr/first-run.html`,headings:[{level:1,text:`Premier démarrage`,id:`premier-demarrage`},{level:2,text:`Trois choix à faire`,id:`trois-choix-a-faire`},{level:2,text:`Un premier énoncé`,id:`un-premier-enonce`},{level:2,text:`Essayer sans modèles ni Lean : le mode démo`,id:`essayer-sans-modeles-ni-lean-le-mode-demo`}],images:[],verify:[],body:`# Premier démarrage

Sur l'ordinateur hôte, la toute première ouverture commence par l'assistant « Premiers pas » (outils, modèle local,
clés, modes… ; voir [Première configuration](first-config.md#lassistant-premiers-pas)). Ensuite, à la première
ouverture de l'accueil (en mode *Apprendre*, celui par défaut), une courte visite en quatre étapes présente les
idées de l'interface : écrire un énoncé, vérifier la traduction, Lean vérifie chaque preuve, vous gardez la main.
« Passer la visite » la ferme.

L'état de l'installation (espaces Lean, modèles, TeX, polices, bac à sable, disque) se lit dans « Réglages ›
Système », partie « État de santé » : chaque problème y est signalé, avec un bouton « Réparer » quand une réparation
existe (à lancer depuis l'ordinateur hôte).

## Trois choix à faire

Ces choix, les clés des fournisseurs et chaque comportement automatique sont détaillés dans
[Première configuration](first-config.md).


1. **Où travaillent les modèles** (« Réglages › Modèles ») :
   - *Local* : rien ne quitte l'ordinateur hôte ; seuls les modèles installés ici travaillent.
   - *Automatique* (par défaut) : le meilleur modèle disponible, en ligne d'abord, les modèles locaux si le réseau
     manque.
   - *En ligne* : uniquement des modèles en ligne.

   Ce que chaque mode envoie, et à qui : [Modèles et clés](models-keys.md).
2. **Apprendre ou Recherche** (bouton en haut à droite) : *Apprendre* propose des indices avant la preuve, un
   glossaire au survol et des explications ligne par ligne ; *Recherche* est dense, pensé pour le clavier, sans rien
   de pédagogique sur le chemin. Vous pouvez changer à tout moment.
3. **Votre profil** (« Réglages › Profil ») : public visé, niveau, notations préférées. Il est lu avant chaque
   traduction et chaque explication.

## Un premier énoncé

Sur l'accueil, écrivez par exemple :

> Montrer que la somme de deux entiers pairs est paire.

puis « Traduire et prouver ». Les étapes s'enchaînent seules : compréhension, traduction en Lean, recherche de preuve, explication.
La suite est décrite dans [De l'énoncé à la preuve](workflow.md).

## Essayer sans modèles ni Lean : le mode démo

\`\`\`bash
~/madalean/bin/madalean serve --demo --port 11600 --remote-port 11601
\`\`\`

puis ouvrez \`http://127.0.0.1:11600\`. Les modèles et Lean sont **simulés** : un bandeau le rappelle et rien n'y est
vraiment vérifié. Le mode démo sert à découvrir l'interface ; ses données sont séparées des vôtres
(\`~/.config/madalean-demo\`).
`,text:`Premier démarrage Sur l'ordinateur hôte, la toute première ouverture commence par l'assistant « Premiers pas » (outils, modèle local, clés, modes… ; voir Première configuration). Ensuite, à la première ouverture de l'accueil (en mode Apprendre, celui par défaut), une courte visite en quatre étapes présente les idées de l'interface : écrire un énoncé, vérifier la traduction, Lean vérifie chaque preuve, vous gardez la main. « Passer la visite » la ferme. L'état de l'installation (espaces Lean, modèles, TeX, polices, bac à sable, disque) se lit dans « Réglages › Système », partie « État de santé » : chaque problème y est signalé, avec un bouton « Réparer » quand une réparation existe (à lancer depuis l'ordinateur hôte). Trois choix à faire Ces choix, les clés des fournisseurs et chaque comportement automatique sont détaillés dans Première configuration. 1. Où travaillent les modèles (« Réglages › Modèles ») : - Local : rien ne quitte l'ordinateur hôte ; seuls les modèles installés ici travaillent. - Automatique (par défaut) : le meilleur modèle disponible, en ligne d'abord, les modèles locaux si le réseau manque. - En ligne : uniquement des modèles en ligne. Ce que chaque mode envoie, et à qui : Modèles et clés. 2. Apprendre ou Recherche (bouton en haut à droite) : Apprendre propose des indices avant la preuve, un glossaire au survol et des explications ligne par ligne ; Recherche est dense, pensé pour le clavier, sans rien de pédagogique sur le chemin. Vous pouvez changer à tout moment. 3. Votre profil (« Réglages › Profil ») : public visé, niveau, notations préférées. Il est lu avant chaque traduction et chaque explication. Un premier énoncé Sur l'accueil, écrivez par exemple : > Montrer que la somme de deux entiers pairs est paire. puis « Traduire et prouver ». Les étapes s'enchaînent seules : compréhension, traduction en Lean, recherche de preuve, explication. La suite est décrite dans De l'énoncé à la preuve. Essayer sans modèles ni Lean : le mode démo puis ouvrez http://127.0.0.1:11600. Les modèles et Lean sont simulés : un bandeau le rappelle et rien n'y est vraiment vérifié. Le mode démo sert à découvrir l'interface ; ses données sont séparées des vôtres (~/.config/madalean-demo).`},{id:`pairing`,lang:`fr`,title:`Relier un téléphone, une tablette ou un autre PC`,order:30,section:`start`,audience:`all`,summary:`Pas à pas pour relier un appareil à l'ordinateur hôte par un code à 6 chiffres, et pour le délier.`,source:`fr/pairing.md`,site_path:`fr/pairing.html`,headings:[{level:1,text:`Relier un téléphone, une tablette ou un autre PC`,id:`relier-un-telephone-une-tablette-ou-un-autre-pc`},{level:2,text:`Étape 1 — Mettre l'hôte sur votre réseau Tailscale (une fois)`,id:`etape-1-mettre-lhote-sur-votre-reseau-tailscale-une-fois`},{level:2,text:`Étape 2 — Afficher un code sur l'hôte`,id:`etape-2-afficher-un-code-sur-lhote`},{level:2,text:`Étape 3 — Sur l'appareil`,id:`etape-3-sur-lappareil`},{level:3,text:`Téléphone ou tablette Android`,id:`telephone-ou-tablette-android`},{level:3,text:`iPhone, iPad, ou tout appareil avec un navigateur`,id:`iphone-ipad-ou-tout-appareil-avec-un-navigateur`},{level:3,text:`Autre ordinateur Linux`,id:`autre-ordinateur-linux`},{level:2,text:`Ce qui se passe au moment de la liaison`,id:`ce-qui-se-passe-au-moment-de-la-liaison`},{level:2,text:`Délier un appareil`,id:`delier-un-appareil`},{level:2,text:`Si ça ne marche pas`,id:`si-ca-ne-marche-pas`}],images:[{src:`img/devices-add.png`,exists:!0},{src:`img/pair-phone.png`,exists:!0}],verify:[],body:`# Relier un téléphone, une tablette ou un autre PC

Un appareil relié affiche la même interface que l'ordinateur hôte et reste synchronisé avec lui : ce que vous
lancez au téléphone apparaît sur le PC, et inversement. Tout le calcul reste sur l'hôte.

Il faut trois choses :

1. l'ordinateur hôte allumé, Madalean démarré ;
2. l'hôte et l'appareil sur **votre réseau Tailscale** (voir [Tailscale](tailscale.md)) ;
3. un **code à 6 chiffres** affiché par l'hôte.

Sur l'ordinateur hôte lui-même, aucun code n'est nécessaire.

**Application ou navigateur ?**

- Les **applications Madalean** (Android, bureau Linux) se relient **une seule fois** : ensuite elles se reconnectent
  toutes seules, même après un redémarrage de l'hôte.
- Depuis un **navigateur** (iPhone, iPad, autre PC sans l'application), il faut un **code à chaque connexion** :
  l'accès dure le temps de la session, se ferme après **2 h sans activité** (réglable sur l'hôte) et au plus tard
  après **12 h**, et aussi quand l'hôte redémarre.

## Étape 1 — Mettre l'hôte sur votre réseau Tailscale (une fois)

Madalean apporte **son propre nœud Tailscale** : sur votre tailnet, l'hôte apparaît comme une machine à part,
nommée \`madalean\`, à l'adresse \`https://madalean.tailXXXX.ts.net\` (port HTTPS normal, aucun numéro de port à taper).
Il n'y a rien à installer sur l'hôte pour cela : ni Tailscale du système, ni \`tailscale serve\`.

La première fois, ce nœud doit être **approuvé** dans votre compte Tailscale (Madalean n'approuve jamais rien
lui-même) : ouvrez le lien de connexion Tailscale qu'il fournit, connectez-vous et acceptez la machine \`madalean\`.
Pour l'instant, ce lien se lit sur l'hôte, dans un terminal :

\`\`\`bash
curl -s http://127.0.0.1:11500/api/net
\`\`\`

(ligne \`auth_url\`). Une fois le nœud approuvé, la même commande indique \`"state": "running"\` et le nom complet de
l'hôte (\`dns_name\`). Le tailnet doit avoir les certificats HTTPS activés : voir
[Tailscale › Activer HTTPS](tailscale.md#activer-https).

Si vous préférez passer par le Tailscale déjà installé sur l'hôte, voir
[Tailscale › Autre possibilité](tailscale.md#autre-possibilite-le-tailscale-du-systeme).

## Étape 2 — Afficher un code sur l'hôte

Sur l'ordinateur hôte : « Réglages › Appareils », partie « Ajouter un appareil », bouton « Afficher un code ». Un
code à 6 chiffres s'affiche, valable **5 minutes**, utilisable **une seule fois**, avec un QR code.

![Réglages › Appareils : code et QR code](img/devices-add.png)

Le champ « Adresse de cet ordinateur vue des autres appareils » se remplit tout seul quand le nœud Tailscale de
Madalean tourne (par exemple \`madalean.tail1234.ts.net\`). Il sert à fabriquer le QR code. Le QR code contient aussi
des adresses de secours, que l'application Android essaie si le nom ne répond pas : l'adresse IP Tailscale de l'hôte
et, si l'accès depuis le réseau local est activé, son adresse sur le réseau local (port 11502 par défaut, voir
[Tailscale › Sans Tailscale](tailscale.md#sans-tailscale)).

## Étape 3 — Sur l'appareil

### Téléphone ou tablette Android

1. Installez l'application **Tailscale** (Play Store) et connectez-vous avec **le même compte** que sur l'hôte.
2. Installez l'application **Madalean** depuis la [page d'installation](site:install) (fichier APK ; Android
   demande d'autoriser l'installation depuis votre navigateur, une fois).
3. Ouvrez Madalean et touchez « Scanner le QR code », puis visez le QR code affiché sur l'hôte : l'adresse et le code
   se remplissent tout seuls. L'application demande l'accès à l'appareil photo, seulement pour lire ce QR code.
   Sinon, « Ou saisir l'adresse et le code » permet de les taper à la main.
4. Donnez un nom à l'appareil (« Pixel de Marie ») et touchez « Appairer et ouvrir ».

![Écran de liaison sur un téléphone](img/pair-phone.png)

### iPhone, iPad, ou tout appareil avec un navigateur

Il n'y a pas d'application iOS. Installez Tailscale (App Store), puis ouvrez dans le navigateur l'adresse de l'hôte,
par exemple \`https://madalean.tail1234.ts.net\`. La page « Relier cet appareil » demande le code et un nom d'appareil,
puis « Relier ». Scanner le QR code de l'hôte avec l'appareil photo ouvre directement cette page, code rempli.
**Code à saisir à chaque connexion depuis un navigateur** : à la visite suivante (ou après 2 h sans activité),
affichez un nouveau code sur l'hôte.

### Autre ordinateur Linux

Installez Tailscale, puis soit un navigateur (comme ci-dessus), soit l'application de bureau **Madalean**
(AppImage, [page d'installation](site:install)) qui garde le jeton dans le trousseau du système et se reconnecte
seule.

## Ce qui se passe au moment de la liaison

- **Application** : l'appareil envoie le code ; l'hôte lui remet un **jeton** secret (256 bits), rangé dans le
  trousseau du système, qui l'identifie ensuite. L'hôte ne garde qu'une empreinte de ce jeton, jamais le jeton
  lui-même.
- **Navigateur** : l'hôte ouvre une **session temporaire** (un cookie de session, effacé à la fermeture du
  navigateur, qu'aucune page ne peut lire) ; elle n'est jamais transformée en jeton permanent et n'est gardée qu'en
  mémoire par l'hôte.

Cinq codes faux d'affilée bloquent la liaison 10 minutes. Détails : [Sécurité](security.md).

## Délier un appareil

- Depuis l'hôte : « Réglages › Appareils », bouton « Délier » en face de l'appareil. La page montre deux listes :
  « Applications (connexion automatique) » et « Navigateurs (session temporaire) ». L'accès est coupé
  **immédiatement** : une page déjà ouverte perd aussitôt sa connexion en direct, la réponse en cours d'écriture pour
  elle est arrêtée, et elle revient à l'écran de liaison. Il en va de même quand une session de navigateur se termine
  (inactivité, limite de 12 h) et quand l'appareil se délie lui-même.
- Depuis l'appareil lui-même : « Réglages › Appareils › Délier cet appareil ». Dans l'application Android,
  « Oublier » retire aussi un serveur enregistré de l'écran de connexion.

Délier un téléphone perdu est la première chose à faire ; votre compte Tailscale permet aussi de retirer l'appareil
du réseau privé.

## Si ça ne marche pas

| Message | Que faire |
|---|---|
| « Code incorrect » | Retapez les 6 chiffres affichés sur l'hôte. |
| « Ce code a expiré » | « Nouveau code » sur l'hôte (validité 5 minutes). |
| « Trop d'essais : la liaison est bloquée N min » | Attendez, puis demandez un nouveau code. |
| L'adresse ne répond pas | Tailscale est-il connecté sur les deux appareils ? Voir [Dépannage](troubleshooting.md#lappareil-ne-joint-pas-lhote). |
`,text:`Relier un téléphone, une tablette ou un autre PC Un appareil relié affiche la même interface que l'ordinateur hôte et reste synchronisé avec lui : ce que vous lancez au téléphone apparaît sur le PC, et inversement. Tout le calcul reste sur l'hôte. Il faut trois choses : 1. l'ordinateur hôte allumé, Madalean démarré ; 2. l'hôte et l'appareil sur votre réseau Tailscale (voir Tailscale) ; 3. un code à 6 chiffres affiché par l'hôte. Sur l'ordinateur hôte lui-même, aucun code n'est nécessaire. Application ou navigateur ? - Les applications Madalean (Android, bureau Linux) se relient une seule fois : ensuite elles se reconnectent toutes seules, même après un redémarrage de l'hôte. - Depuis un navigateur (iPhone, iPad, autre PC sans l'application), il faut un code à chaque connexion : l'accès dure le temps de la session, se ferme après 2 h sans activité (réglable sur l'hôte) et au plus tard après 12 h, et aussi quand l'hôte redémarre. Étape 1 — Mettre l'hôte sur votre réseau Tailscale (une fois) Madalean apporte son propre nœud Tailscale : sur votre tailnet, l'hôte apparaît comme une machine à part, nommée madalean, à l'adresse https://madalean.tailXXXX.ts.net (port HTTPS normal, aucun numéro de port à taper). Il n'y a rien à installer sur l'hôte pour cela : ni Tailscale du système, ni tailscale serve. La première fois, ce nœud doit être approuvé dans votre compte Tailscale (Madalean n'approuve jamais rien lui-même) : ouvrez le lien de connexion Tailscale qu'il fournit, connectez-vous et acceptez la machine madalean. Pour l'instant, ce lien se lit sur l'hôte, dans un terminal : (ligne authurl). Une fois le nœud approuvé, la même commande indique "state": "running" et le nom complet de l'hôte (dnsname). Le tailnet doit avoir les certificats HTTPS activés : voir Tailscale › Activer HTTPS. Si vous préférez passer par le Tailscale déjà installé sur l'hôte, voir Tailscale › Autre possibilité. Étape 2 — Afficher un code sur l'hôte Sur l'ordinateur hôte : « Réglages › Appareils », partie « Ajouter un appareil », bouton « Afficher un code ». Un code à 6 chiffres s'affiche, valable 5 minutes, utilisable une seule fois, avec un QR code. Réglages › Appareils : code et QR code Le champ « Adresse de cet ordinateur vue des autres appareils » se remplit tout seul quand le nœud Tailscale de Madalean tourne (par exemple madalean.tail1234.ts.net). Il sert à fabriquer le QR code. Le QR code contient aussi des adresses de secours, que l'application Android essaie si le nom ne répond pas : l'adresse IP Tailscale de l'hôte et, si l'accès depuis le réseau local est activé, son adresse sur le réseau local (port 11502 par défaut, voir Tailscale › Sans Tailscale). Étape 3 — Sur l'appareil Téléphone ou tablette Android 1. Installez l'application Tailscale (Play Store) et connectez-vous avec le même compte que sur l'hôte. 2. Installez l'application Madalean depuis la page d'installation (fichier APK ; Android demande d'autoriser l'installation depuis votre navigateur, une fois). 3. Ouvrez Madalean et touchez « Scanner le QR code », puis visez le QR code affiché sur l'hôte : l'adresse et le code se remplissent tout seuls. L'application demande l'accès à l'appareil photo, seulement pour lire ce QR code. Sinon, « Ou saisir l'adresse et le code » permet de les taper à la main. 4. Donnez un nom à l'appareil (« Pixel de Marie ») et touchez « Appairer et ouvrir ». Écran de liaison sur un téléphone iPhone, iPad, ou tout appareil avec un navigateur Il n'y a pas d'application iOS. Installez Tailscale (App Store), puis ouvrez dans le navigateur l'adresse de l'hôte, par exemple https://madalean.tail1234.ts.net. La page « Relier cet appareil » demande le code et un nom d'appareil, puis « Relier ». Scanner le QR code de l'hôte avec l'appareil photo ouvre directement cette page, code rempli. Code à saisir à chaque connexion depuis un navigateur : à la visite suivante (ou après 2 h sans activité), affichez un nouveau code sur l'hôte. Autre ordinateur Linux Installez Tailscale, puis soit un navigateur (comme ci-dessus), soit l'application de bureau Madalean (AppImage, page d'installation) qui garde le jeton dans le trousseau du système et se reconnecte seule. Ce qui se passe au moment de la liaison - Application : l'appareil envoie le code ; l'hôte lui remet un jeton secret (256 bits), rangé dans le trousseau du système, qui l'identifie ensuite. L'hôte ne garde qu'une empreinte de ce jeton, jamais le jeton lui-même. - Navigateur : l'hôte ouvre une session temporaire (un cookie de session, effacé à la fermeture du navigateur, qu'aucune page ne peut lire) ; elle n'est jamais transformée en jeton permanent et n'est gardée qu'en mémoire par l'hôte. Cinq codes faux d'affilée bloquent la liaison 10 minutes. Détails : Sécurité. Délier un appareil - Depuis l'hôte : « Réglages › Appareils », bouton « Délier » en face de l'appareil. La page montre deux listes : « Applications (connexion automatique) » et « Navigateurs (session temporaire) ». L'accès est coupé immédiatement : une page déjà ouverte perd aussitôt sa connexion en direct, la réponse en cours d'écriture pour elle est arrêtée, et elle revient à l'écran de liaison. Il en va de même quand une session de navigateur se termine (inactivité, limite de 12 h) et quand l'appareil se délie lui-même. - Depuis l'appareil lui-même : « Réglages › Appareils › Délier cet appareil ». Dans l'application Android, « Oublier » retire aussi un serveur enregistré de l'écran de connexion. Délier un téléphone perdu est la première chose à faire ; votre compte Tailscale permet aussi de retirer l'appareil du réseau privé. Si ça ne marche pas Message Que faire « Code incorrect » Retapez les 6 chiffres affichés sur l'hôte. « Ce code a expiré » « Nouveau code » sur l'hôte (validité 5 minutes). « Trop d'essais : la liaison est bloquée N min » Attendez, puis demandez un nouveau code. L'adresse ne répond pas Tailscale est-il connecté sur les deux appareils ? Voir Dépannage.`},{id:`tailscale`,lang:`fr`,title:`Tailscale, le réseau privé de vos appareils`,order:40,section:`start`,audience:`all`,summary:`Ce qu'est Tailscale, pourquoi Madalean l'utilise, comment l'installer, et ce qu'il ne fait pas.`,source:`fr/tailscale.md`,site_path:`fr/tailscale.html`,headings:[{level:1,text:`Tailscale, le réseau privé de vos appareils`,id:`tailscale-le-reseau-prive-de-vos-appareils`},{level:2,text:`Ce que c'est`,id:`ce-que-cest`},{level:2,text:`Ce que Madalean fait, et ne fait pas, avec Tailscale`,id:`ce-que-madalean-fait-et-ne-fait-pas-avec-tailscale`},{level:2,text:`Installer Tailscale`,id:`installer-tailscale`},{level:2,text:`Activer HTTPS`,id:`activer-https`},{level:2,text:`Autre possibilité : le Tailscale du système`,id:`autre-possibilite-le-tailscale-du-systeme`},{level:2,text:`Sans Tailscale`,id:`sans-tailscale`}],images:[],verify:[],body:`# Tailscale, le réseau privé de vos appareils

## Ce que c'est

[Tailscale](https://tailscale.com/) relie **vos** appareils entre eux par des liaisons chiffrées (protocole
WireGuard), où qu'ils soient : même Wi-Fi, 4G, autre ville. L'ensemble forme un réseau privé, le *tailnet*. Chaque
appareil y reçoit un nom stable, par exemple \`nitro.tail1234.ts.net\`. Seuls les appareils connectés à **votre**
compte Tailscale font partie de ce réseau.

Madalean l'utilise pour une seule chose : que vos appareils joignent l'ordinateur hôte. Il ne se sert d'aucun
serveur de Madalean sur Internet (il n'y en a pas) et le site web de Madalean ne joue aucun rôle dans la
synchronisation.

## Ce que Madalean fait, et ne fait pas, avec Tailscale

- Madalean installe et lance **son propre nœud Tailscale**. Sur votre tailnet, l'hôte apparaît comme une machine à
  part, \`madalean\`, joignable en HTTPS à \`https://madalean.<tailnet>.ts.net\` (port HTTPS normal, sans numéro de port).
  Ce nœud est arrêté avec Madalean et n'envoie aucun journal à Tailscale.
- L'hôte n'a besoin ni du Tailscale du système ni de \`tailscale serve\`. S'il y en a un, Madalean n'y touche pas : les
  deux cohabitent.
- Madalean n'active **jamais Funnel**, la fonction de Tailscale qui ouvrirait l'accès à tout Internet.
- Être sur le tailnet **ne suffit pas** : chaque appareil doit en plus être relié par un code
  ([Relier un appareil](pairing.md)).

## Installer Tailscale

**Sur l'ordinateur hôte**, rien à installer : le nœud de Madalean est installé par \`./install.sh\`. La première fois,
il faut l'approuver dans votre compte Tailscale (voir [Relier un appareil › Étape 1](pairing.md)).

**Sur un téléphone, une tablette ou un autre ordinateur** : l'application Tailscale (App Store, Play Store, ou le
site de Tailscale pour un ordinateur), connectée au **même compte**.

Le compte Tailscale se crée avec un fournisseur d'identité (Google, Microsoft, GitHub, Apple…). Les offres et leurs
limites sont décrites sur le site de Tailscale ; un usage personnel avec quelques appareils entre en général dans
l'offre gratuite, mais vérifiez-le sur ce site.

## Activer HTTPS

Les appareils joignent l'hôte en HTTPS, avec un certificat que Tailscale émet pour le nom
\`madalean.<tailnet>.ts.net\`. Il faut, une fois, dans la console d'administration de Tailscale, activer **MagicDNS**
et les **certificats HTTPS** (les menus exacts sont décrits dans l'aide de Tailscale). La première connexion HTTPS
peut prendre quelques secondes, le temps que le certificat soit émis.

## Autre possibilité : le Tailscale du système

Si vous préférez utiliser le Tailscale déjà installé sur l'hôte (le service \`tailscaled\`, connecté à votre compte),
le script \`scripts/tailscale_setup.sh\` publie Madalean par lui, sur le port 10500 :
\`https://nom-du-pc.<tailnet>.ts.net:10500\`. Il ajoute **une seule** règle \`tailscale serve\`, ne touche à aucune
autre règle de la machine et n'active jamais Funnel. Il faut une fois \`sudo tailscale set --operator=$USER\` pour
qu'il agisse sans \`sudo\`. \`--status\` montre l'état, \`--print\` montre les commandes sans rien changer, \`--remove\`
retire la règle. Dans ce cas, tapez cette adresse (sans \`https://\`) dans le champ « Adresse de cet ordinateur vue des
autres appareils » de « Réglages › Appareils ».

## Sans Tailscale

« Réglages › Carnet et accès › Accès depuis le réseau local (sans Tailscale) » fait aussi écouter Madalean sur le
réseau local (« Port réseau local », 11502 par défaut ; désactivé par défaut). Les appareils doivent quand même être
reliés par un code, mais le trafic passe alors en HTTP simple, **non chiffré** : à réserver à un réseau de
confiance. Ce réglage ne se change que depuis l'hôte et prend effet au prochain démarrage de Madalean.
`,text:`Tailscale, le réseau privé de vos appareils Ce que c'est Tailscale relie vos appareils entre eux par des liaisons chiffrées (protocole WireGuard), où qu'ils soient : même Wi-Fi, 4G, autre ville. L'ensemble forme un réseau privé, le tailnet. Chaque appareil y reçoit un nom stable, par exemple nitro.tail1234.ts.net. Seuls les appareils connectés à votre compte Tailscale font partie de ce réseau. Madalean l'utilise pour une seule chose : que vos appareils joignent l'ordinateur hôte. Il ne se sert d'aucun serveur de Madalean sur Internet (il n'y en a pas) et le site web de Madalean ne joue aucun rôle dans la synchronisation. Ce que Madalean fait, et ne fait pas, avec Tailscale - Madalean installe et lance son propre nœud Tailscale. Sur votre tailnet, l'hôte apparaît comme une machine à part, madalean, joignable en HTTPS à https://madalean.<tailnet>.ts.net (port HTTPS normal, sans numéro de port). Ce nœud est arrêté avec Madalean et n'envoie aucun journal à Tailscale. - L'hôte n'a besoin ni du Tailscale du système ni de tailscale serve. S'il y en a un, Madalean n'y touche pas : les deux cohabitent. - Madalean n'active jamais Funnel, la fonction de Tailscale qui ouvrirait l'accès à tout Internet. - Être sur le tailnet ne suffit pas : chaque appareil doit en plus être relié par un code (Relier un appareil). Installer Tailscale Sur l'ordinateur hôte, rien à installer : le nœud de Madalean est installé par ./install.sh. La première fois, il faut l'approuver dans votre compte Tailscale (voir Relier un appareil › Étape 1). Sur un téléphone, une tablette ou un autre ordinateur : l'application Tailscale (App Store, Play Store, ou le site de Tailscale pour un ordinateur), connectée au même compte. Le compte Tailscale se crée avec un fournisseur d'identité (Google, Microsoft, GitHub, Apple…). Les offres et leurs limites sont décrites sur le site de Tailscale ; un usage personnel avec quelques appareils entre en général dans l'offre gratuite, mais vérifiez-le sur ce site. Activer HTTPS Les appareils joignent l'hôte en HTTPS, avec un certificat que Tailscale émet pour le nom madalean.<tailnet>.ts.net. Il faut, une fois, dans la console d'administration de Tailscale, activer MagicDNS et les certificats HTTPS (les menus exacts sont décrits dans l'aide de Tailscale). La première connexion HTTPS peut prendre quelques secondes, le temps que le certificat soit émis. Autre possibilité : le Tailscale du système Si vous préférez utiliser le Tailscale déjà installé sur l'hôte (le service tailscaled, connecté à votre compte), le script scripts/tailscalesetup.sh publie Madalean par lui, sur le port 10500 : https://nom-du-pc.<tailnet>.ts.net:10500. Il ajoute une seule règle tailscale serve, ne touche à aucune autre règle de la machine et n'active jamais Funnel. Il faut une fois sudo tailscale set --operator=$USER pour qu'il agisse sans sudo. --status montre l'état, --print montre les commandes sans rien changer, --remove retire la règle. Dans ce cas, tapez cette adresse (sans https://) dans le champ « Adresse de cet ordinateur vue des autres appareils » de « Réglages › Appareils ». Sans Tailscale « Réglages › Carnet et accès › Accès depuis le réseau local (sans Tailscale) » fait aussi écouter Madalean sur le réseau local (« Port réseau local », 11502 par défaut ; désactivé par défaut). Les appareils doivent quand même être reliés par un code, mais le trafic passe alors en HTTP simple, non chiffré : à réserver à un réseau de confiance. Ce réglage ne se change que depuis l'hôte et prend effet au prochain démarrage de Madalean.`},{id:`workflow`,lang:`fr`,title:`De l'énoncé à la preuve`,order:100,section:`use`,audience:`all`,summary:`Un dossier en un seul fil — comprendre, traduire, prouver, vérifier — puis l'explication et l'export.`,source:`fr/workflow.md`,site_path:`fr/workflow.html`,headings:[{level:1,text:`De l'énoncé à la preuve`,id:`de-lenonce-a-la-preuve`},{level:3,text:`Vos deux accords`,id:`vos-deux-accords`},{level:3,text:`« Mal compris »`,id:`mal-compris`},{level:2,text:`1. Écrire l'énoncé`,id:`1-ecrire-lenonce`},{level:2,text:`2. La traduction en Lean`,id:`2-la-traduction-en-lean`},{level:2,text:`3. La preuve`,id:`3-la-preuve`},{level:2,text:`4. L'explication`,id:`4-lexplication`},{level:2,text:`5. Exporter`,id:`5-exporter`},{level:2,text:`Et ensuite`,id:`et-ensuite`}],images:[{src:`img/lean-statement.png`,exists:!0},{src:`img/hint-ladder.png`,exists:!0}],verify:[],body:`# De l'énoncé à la preuve

Chaque problème vit dans un **dossier**. En haut de l'écran, quatre étapes disent où vous en êtes :
**Comprendre › Traduire › Prouver › Vérifier**, chacune « pas commencé », « en cours », « vous attend », « fait » ou
« échec ». Juste dessous, une seule ligne **« En ce moment »** dit ce que fait Madalean, le numéro de l'essai, le
modèle, depuis combien de temps et ce qui tourne à côté ; « Arrêter » est toujours là. Si c'est à vous de répondre,
elle le dit et vous y mène ; en cas d'échec, elle mène à ce qui a été essayé, à la dernière cause et aux suites possibles.

Au centre, le **fil** raconte tout dans l'ordre : vos demandes, puis chaque phase, ses essais (repliés), les réponses
des modèles en direct, les sous-dossiers là où ils ont été créés. Des filtres montrent seulement vos demandes, les
résultats, les contrôles ou les essais. Le champ du bas dit **à propos de** quoi porte votre demande.

À côté, le **volet** garde les références : Énoncé, Lean, Preuve, Sous-lemmes (arbre, plan et graphe), Littérature,
Calculs, Versions. « Séparer » met une partie dans sa propre fenêtre ou dans une colonne, « Remettre » la ramène. Le
volet se redimensionne et se masque ; sur téléphone, le bouton « Références » l'ouvre par-dessus le fil.

### Vos deux accords

Avant toute preuve, Madalean vous montre ce qu'il a **compris** (texte reformulé, objets, hypothèses, affirmation, ce
qu'on en sait avec les citations), puis l'**énoncé Lean** avec sa relecture en langage courant. Pour chacun :
« Approuver », « Corriger » ou « Refuser ». « Lean comprend le code » ne veut dire ni « fidèle » ni « prouvé ». Un
problème ouvert est annoncé comme tel ; les résultats connus autour deviennent des sous-dossiers qu'une seule carte
permet d'approuver. Le statut « d'après un modèle, à vérifier » n'a pas de référence.

### « Mal compris »

Sur le sens, l'énoncé, la preuve ou un message, « Mal compris » signale une mauvaise interprétation : une raison, un
mot d'explication, et l'étape est refaite avec votre remarque.

## 1. Écrire l'énoncé

Écrivez avec vos mots, en français ou en anglais. Les formules LaTeX entre dollars sont lues : \`$a^2+b^2 \\ge 2ab$\`.
Un aperçu montre comment l'énoncé sera compris. Vous pouvez aussi :

- **importer un fichier \`.tex\`** : Madalean en extrait les environnements de type théorème et vous choisissez
  lequel prouver ;
- **coller directement un énoncé Lean** : l'étape de traduction est alors sautée.

Un énoncé précis se traduit mieux : nommez les ensembles ($n \\in \\mathbb{N}$, $x \\in \\mathbb{R}$), les hypothèses
et la conclusion.

## 2. La traduction en Lean

Un premier modèle reformule votre demande en énoncé mathématique précis (« théorème de la base incomplète » devient
« toute famille libre d'un espace vectoriel de dimension finie se complète en une base »). Un second la traduit en
Lean ; **Lean vérifie que l'énoncé est bien formé** avant d'aller plus loin. La mention « Lean comprend le code »
signifie seulement que l'énoncé a un sens pour Lean, pas qu'il est vrai, ni qu'il dit ce que vous vouliez.

![Énoncé Lean à côté du texte d'origine](img/lean-statement.png)

**Relisez cette traduction.** C'est le seul point où une erreur passe inaperçue : Lean prouvera exactement l'énoncé
Lean. Les pièges courants (division entière, soustraction tronquée sur $\\mathbb{N}$, division par zéro) sont dans
[Lire un énoncé Lean](reading-lean.md). En mode *Apprendre*, le panneau « Comprendre » explique l'énoncé ligne par
ligne et chaque mot Lean au survol.

Pour corriger : « Modifier à la main » (vous éditez le code, Lean le revérifie), ou « Corriger l'énoncé… » (vous
décrivez la correction, le modèle réécrit).

## 3. La preuve

Madalean cherche une preuve selon la méthode choisie dans « Réglages › Modèles » :

| Méthode | Fonctionnement |
|---|---|
| *goedel* | le modèle local Goedel-Prover écrit une preuve ; si Lean la refuse, il lit l'erreur et corrige, plusieurs fois |
| *agent* | un modèle qui sait utiliser des outils compile lui-même des essais avec Lean et cherche des lemmes dans Mathlib |
| *auto* (défaut) | agent avec le meilleur modèle en ligne autorisé, sinon goedel ; goedel aussi en secours si l'agent échoue |

Quelle que soit la méthode, la preuve finale est **revérifiée par le serveur** avec le verdict strict. Le badge
« Preuve vérifiée par Lean » donne la version de Lean, la révision de Mathlib, la durée, le nombre d'essais, le
modèle qui l'a écrite et les axiomes utilisés.

Pendant la recherche, le texte des modèles arrive en direct à la fin du fil, avec chaque essai compilé. « Arrêter » coupe
tout, à tout moment (requête au modèle et compilation Lean).

En mode *Apprendre*, la preuve n'est pas montrée tout de suite : une échelle d'indices (coup de pouce, stratégie,
lemme clé, étape suivante, preuve complète) vous laisse chercher d'abord. Le dernier niveau est toujours la preuve
vérifiée par Lean, jamais un texte de modèle.

![Échelle d'indices en mode Apprendre](img/hint-ladder.png)

## 4. L'explication

Une fois la preuve acceptée, un modèle l'explique en langage courant et rédige une **preuve en langage naturel**
(celle qui ira dans le PDF). Ces textes sont des brouillons modifiables : vous pouvez les corriger à la main, et une
modification manuelle n'est jamais écrasée sans votre accord.

## 5. Exporter

« Exporter » propose :

| Format | Contenu |
|---|---|
| PDF | titre, énoncé en langage naturel, énoncé Lean et sa glose, preuve rédigée, preuve Lean, tampon de vérification (version de Lean, révision de Mathlib, date, axiomes, modèle), explication tactique par tactique en annexe |
| LaTeX (\`.tex\`) | le même document, à compiler avec XeLaTeX (par exemple sur Overleaf) |
| Lean (\`.lean\`) | le fichier qui compile |
| Markdown (\`.md\`) | texte et formules \`$…$\` |
| Tout (\`.zip\`) | tout cela, avec \`refs.bib\` si le dossier cite des sources |

Un dossier non prouvé est exporté avec la mention « Non prouvé » et sans tampon. Si aucun moteur TeX n'est installé
sur l'hôte, Madalean ouvre une version HTML : utilisez « Imprimer › Enregistrer en PDF » du navigateur.

## Et ensuite

- Affiner : [Demandes de suivi et versions](follow-ups.md).
- Plusieurs résultats liés : [Projets et dossiers en parallèle](projects.md).
- Un résultat trop gros pour une seule preuve : [Plans de preuve et lemmes](proof-plans.md).
- Chaque résultat prouvé entre dans la **Bibliothèque** et sert de lemme aux preuves suivantes du même espace Lean.
`,text:`De l'énoncé à la preuve Chaque problème vit dans un dossier. En haut de l'écran, quatre étapes disent où vous en êtes : Comprendre › Traduire › Prouver › Vérifier, chacune « pas commencé », « en cours », « vous attend », « fait » ou « échec ». Juste dessous, une seule ligne « En ce moment » dit ce que fait Madalean, le numéro de l'essai, le modèle, depuis combien de temps et ce qui tourne à côté ; « Arrêter » est toujours là. Si c'est à vous de répondre, elle le dit et vous y mène ; en cas d'échec, elle mène à ce qui a été essayé, à la dernière cause et aux suites possibles. Au centre, le fil raconte tout dans l'ordre : vos demandes, puis chaque phase, ses essais (repliés), les réponses des modèles en direct, les sous-dossiers là où ils ont été créés. Des filtres montrent seulement vos demandes, les résultats, les contrôles ou les essais. Le champ du bas dit à propos de quoi porte votre demande. À côté, le volet garde les références : Énoncé, Lean, Preuve, Sous-lemmes (arbre, plan et graphe), Littérature, Calculs, Versions. « Séparer » met une partie dans sa propre fenêtre ou dans une colonne, « Remettre » la ramène. Le volet se redimensionne et se masque ; sur téléphone, le bouton « Références » l'ouvre par-dessus le fil. Vos deux accords Avant toute preuve, Madalean vous montre ce qu'il a compris (texte reformulé, objets, hypothèses, affirmation, ce qu'on en sait avec les citations), puis l'énoncé Lean avec sa relecture en langage courant. Pour chacun : « Approuver », « Corriger » ou « Refuser ». « Lean comprend le code » ne veut dire ni « fidèle » ni « prouvé ». Un problème ouvert est annoncé comme tel ; les résultats connus autour deviennent des sous-dossiers qu'une seule carte permet d'approuver. Le statut « d'après un modèle, à vérifier » n'a pas de référence. « Mal compris » Sur le sens, l'énoncé, la preuve ou un message, « Mal compris » signale une mauvaise interprétation : une raison, un mot d'explication, et l'étape est refaite avec votre remarque. 1. Écrire l'énoncé Écrivez avec vos mots, en français ou en anglais. Les formules LaTeX entre dollars sont lues : $a^2+b^2 \\ge 2ab$. Un aperçu montre comment l'énoncé sera compris. Vous pouvez aussi : - importer un fichier .tex : Madalean en extrait les environnements de type théorème et vous choisissez lequel prouver ; - coller directement un énoncé Lean : l'étape de traduction est alors sautée. Un énoncé précis se traduit mieux : nommez les ensembles ($n \\in \\mathbb{N}$, $x \\in \\mathbb{R}$), les hypothèses et la conclusion. 2. La traduction en Lean Un premier modèle reformule votre demande en énoncé mathématique précis (« théorème de la base incomplète » devient « toute famille libre d'un espace vectoriel de dimension finie se complète en une base »). Un second la traduit en Lean ; Lean vérifie que l'énoncé est bien formé avant d'aller plus loin. La mention « Lean comprend le code » signifie seulement que l'énoncé a un sens pour Lean, pas qu'il est vrai, ni qu'il dit ce que vous vouliez. Énoncé Lean à côté du texte d'origine Relisez cette traduction. C'est le seul point où une erreur passe inaperçue : Lean prouvera exactement l'énoncé Lean. Les pièges courants (division entière, soustraction tronquée sur $\\mathbb{N}$, division par zéro) sont dans Lire un énoncé Lean. En mode Apprendre, le panneau « Comprendre » explique l'énoncé ligne par ligne et chaque mot Lean au survol. Pour corriger : « Modifier à la main » (vous éditez le code, Lean le revérifie), ou « Corriger l'énoncé… » (vous décrivez la correction, le modèle réécrit). 3. La preuve Madalean cherche une preuve selon la méthode choisie dans « Réglages › Modèles » : Méthode Fonctionnement goedel le modèle local Goedel-Prover écrit une preuve ; si Lean la refuse, il lit l'erreur et corrige, plusieurs fois agent un modèle qui sait utiliser des outils compile lui-même des essais avec Lean et cherche des lemmes dans Mathlib auto (défaut) agent avec le meilleur modèle en ligne autorisé, sinon goedel ; goedel aussi en secours si l'agent échoue Quelle que soit la méthode, la preuve finale est revérifiée par le serveur avec le verdict strict. Le badge « Preuve vérifiée par Lean » donne la version de Lean, la révision de Mathlib, la durée, le nombre d'essais, le modèle qui l'a écrite et les axiomes utilisés. Pendant la recherche, le texte des modèles arrive en direct à la fin du fil, avec chaque essai compilé. « Arrêter » coupe tout, à tout moment (requête au modèle et compilation Lean). En mode Apprendre, la preuve n'est pas montrée tout de suite : une échelle d'indices (coup de pouce, stratégie, lemme clé, étape suivante, preuve complète) vous laisse chercher d'abord. Le dernier niveau est toujours la preuve vérifiée par Lean, jamais un texte de modèle. Échelle d'indices en mode Apprendre 4. L'explication Une fois la preuve acceptée, un modèle l'explique en langage courant et rédige une preuve en langage naturel (celle qui ira dans le PDF). Ces textes sont des brouillons modifiables : vous pouvez les corriger à la main, et une modification manuelle n'est jamais écrasée sans votre accord. 5. Exporter « Exporter » propose : Format Contenu PDF titre, énoncé en langage naturel, énoncé Lean et sa glose, preuve rédigée, preuve Lean, tampon de vérification (version de Lean, révision de Mathlib, date, axiomes, modèle), explication tactique par tactique en annexe LaTeX (.tex) le même document, à compiler avec XeLaTeX (par exemple sur Overleaf) Lean (.lean) le fichier qui compile Markdown (.md) texte et formules $…$ Tout (.zip) tout cela, avec refs.bib si le dossier cite des sources Un dossier non prouvé est exporté avec la mention « Non prouvé » et sans tampon. Si aucun moteur TeX n'est installé sur l'hôte, Madalean ouvre une version HTML : utilisez « Imprimer › Enregistrer en PDF » du navigateur. Et ensuite - Affiner : Demandes de suivi et versions. - Plusieurs résultats liés : Projets et dossiers en parallèle. - Un résultat trop gros pour une seule preuve : Plans de preuve et lemmes. - Chaque résultat prouvé entre dans la Bibliothèque et sert de lemme aux preuves suivantes du même espace Lean.`},{id:`reading-lean`,lang:`fr`,title:`Lire un énoncé Lean`,order:110,section:`use`,audience:`learner`,summary:`Décoder un énoncé Lean morceau par morceau, et repérer les traductions qui changent le sens.`,source:`fr/reading-lean.md`,site_path:`fr/reading-lean.html`,headings:[{level:1,text:`Lire un énoncé Lean`,id:`lire-un-enonce-lean`},{level:2,text:`L'anatomie d'un énoncé`,id:`lanatomie-dun-enonce`},{level:2,text:`L'en-tête`,id:`len-tete`},{level:2,text:`Les types : de quels nombres parle-t-on ?`,id:`les-types-de-quels-nombres-parle-t-on`},{level:2,text:`Les pièges qui changent le sens`,id:`les-pieges-qui-changent-le-sens`},{level:2,text:`Une méthode de relecture`,id:`une-methode-de-relecture`}],images:[],verify:[],body:"# Lire un énoncé Lean\n\nLean prouve **exactement** l'énoncé Lean, pas la phrase que vous aviez en tête. Cette page apprend à lire un énoncé\nassez bien pour juger une traduction, sans savoir écrire de preuves.\n\n## L'anatomie d'un énoncé\n\n```lean\ntheorem somme_pairs (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  sorry\n```\n\n| Morceau | Lecture |\n|---|---|\n| `theorem somme_pairs` | un théorème, et son nom (choisi par Madalean, unique) |\n| `(a b : ℕ)` | « soient $a$ et $b$ des entiers naturels » |\n| `(ha : Even a)` | hypothèse nommée `ha` : « $a$ est pair » |\n| `(hb : Even b)` | hypothèse `hb` : « $b$ est pair » |\n| `: Even (a + b)` | après le dernier `:` hors parenthèses vient la **conclusion** : « $a+b$ est pair » |\n| `:= by sorry` | « la preuve suit, en mode tactique » ; `sorry` = preuve à compléter |\n\nTout ce qui est entre parenthèses avant le dernier `:` est **supposé** ; ce qui vient après est **à prouver**.\nUn énoncé avec `sorry` est un énoncé sans preuve : Lean l'accepte comme énoncé, jamais comme théorème prouvé.\n\nLa même chose peut s'écrire avec des quantificateurs dans la conclusion ; c'est équivalent :\n\n```lean\ntheorem somme_pairs' : ∀ a b : ℕ, Even a → Even b → Even (a + b) := by\n  sorry\n```\n\n`→` se lit « implique » ; `∀ a b : ℕ,` « pour tous entiers naturels $a$, $b$ ».\n\n## L'en-tête\n\nLes énoncés de l'espace « Prouveur » commencent par un en-tête fixe :\n\n```lean\nimport Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\nopen BigOperators Real Nat Topology Rat\n```\n\n`import Mathlib` charge la bibliothèque mathématique ; `set_option maxHeartbeats` augmente le temps de calcul\nautorisé ; `open …` permet d'écrire `π` ou `√` sans préfixe. Cet en-tête ne change pas le sens de l'énoncé, mais\n`open Nat Real` rend certains noms ambigus (`sqrt` existe dans les deux) : regardez les types.\n\n## Les types : de quels nombres parle-t-on ?\n\n| Lean | Mathématiques | Attention |\n|---|---|---|\n| `ℕ` | $\\mathbb{N} = \\{0, 1, 2, \\dots\\}$ | contient 0 ; soustraction et division tronquées (voir plus bas) |\n| `ℤ` | $\\mathbb{Z}$ | `/` est la division euclidienne : le reste `%` est toujours $\\ge 0$, `-7 / 2 = -4` |\n| `ℚ`, `ℝ`, `ℂ` | $\\mathbb{Q}$, $\\mathbb{R}$, $\\mathbb{C}$ | division par zéro définie et égale à 0 |\n| `Finset ℕ` | ensemble fini d'entiers | `Finset.range n` $= \\{0, \\dots, n-1\\}$ |\n| `Set ℝ` | partie de $\\mathbb{R}$ | |\n| `ℕ → ℝ` | suite réelle | `u n` est le terme $u_n$ |\n\nQuand un même énoncé mélange plusieurs types, Lean insère des **conversions** : `(n : ℝ)` ou `↑n` désigne l'entier\n$n$ vu comme réel. Un énoncé comme `(n : ℝ) / 2` n'a pas le même sens que `n / 2` sur `ℕ`.\n\n## Les pièges qui changent le sens\n\nCes traductions sont acceptées par Lean, mais ne disent pas ce que l'on croit.\n\n1. **Soustraction sur ℕ** : `2 - 5 = 0` dans `ℕ`. Un énoncé sur $a - b$ avec $a < b$ possible doit être écrit dans\n   `ℤ` ou `ℝ`.\n2. **Division sur ℕ et ℤ** : `7 / 2 = 3`. « $n/2$ » en mathématiques est souvent un rationnel.\n3. **Division par zéro** : dans `ℝ`, `x / 0 = 0` par convention. Un énoncé `x / y * y = x` est faux pour\n   `y = 0`, et une traduction qui oublie l'hypothèse `y ≠ 0` peut devenir fausse… ou triviale.\n4. **Fonctions totales** : `Real.sqrt (-1) = 0`, `Real.log 0 = 0`. Une hypothèse oubliée ($x > 0$) ne provoque\n   pas d'erreur.\n5. **Hypothèses contradictoires** : si les hypothèses ne peuvent pas être toutes vraies, *n'importe quelle*\n   conclusion se prouve. Une preuve très courte d'un énoncé difficile est un signal d'alarme.\n6. **Indices** : `Finset.range n` commence à 0. $\\sum_{k=1}^{n} k$ se traduit\n   `∑ k in Finset.Icc 1 n, k` ; avec `Finset.range n` on somme de 0 à $n-1$.\n7. **Quantificateurs** : l'ordre compte. `∀ ε > 0, ∃ N, …` n'est pas `∃ N, ∀ ε > 0, …`.\n8. **« Il existe un unique »** s'écrit `∃! x, P x` ; `∃ x, P x` n'affirme pas l'unicité.\n\nNotation : dans les versions récentes de Mathlib, la somme s'écrit `∑ k ∈ Finset.Icc 1 n, k` ; l'espace\n« Prouveur » (Lean 4.9) utilise encore `∑ k in …`.\n\n## Une méthode de relecture\n\n1. Lisez la conclusion seule : est-ce bien ce que vous voulez prouver ?\n2. Listez les hypothèses : en manque-t-il ? y en a-t-il de trop (une hypothèse superflue rend l'énoncé plus faible) ?\n3. Vérifiez le type de chaque variable.\n4. Cherchez une division, une soustraction, une racine, un logarithme : sont-ils dans le bon type, avec les bonnes\n   hypothèses ?\n5. Essayez de nier l'énoncé sur un petit exemple. Si l'énoncé Lean est vrai et le vôtre faux (ou l'inverse), la\n   traduction est fausse.\n\nLe panneau « Comprendre » (mode *Apprendre*) donne une glose ligne par ligne, écrite par un modèle : elle aide à lire,\nmais elle peut se tromper aussi ; le code fait foi. Le vocabulaire est dans le [Glossaire](glossary.md).\n",text:`Lire un énoncé Lean Lean prouve exactement l'énoncé Lean, pas la phrase que vous aviez en tête. Cette page apprend à lire un énoncé assez bien pour juger une traduction, sans savoir écrire de preuves. L'anatomie d'un énoncé Morceau Lecture theorem sommepairs un théorème, et son nom (choisi par Madalean, unique) (a b : ℕ) « soient $a$ et $b$ des entiers naturels » (ha : Even a) hypothèse nommée ha : « $a$ est pair » (hb : Even b) hypothèse hb : « $b$ est pair » : Even (a + b) après le dernier : hors parenthèses vient la conclusion : « $a+b$ est pair » := by sorry « la preuve suit, en mode tactique » ; sorry = preuve à compléter Tout ce qui est entre parenthèses avant le dernier : est supposé ; ce qui vient après est à prouver. Un énoncé avec sorry est un énoncé sans preuve : Lean l'accepte comme énoncé, jamais comme théorème prouvé. La même chose peut s'écrire avec des quantificateurs dans la conclusion ; c'est équivalent : → se lit « implique » ; ∀ a b : ℕ, « pour tous entiers naturels $a$, $b$ ». L'en-tête Les énoncés de l'espace « Prouveur » commencent par un en-tête fixe : import Mathlib charge la bibliothèque mathématique ; setoption maxHeartbeats augmente le temps de calcul autorisé ; open … permet d'écrire π ou √ sans préfixe. Cet en-tête ne change pas le sens de l'énoncé, mais open Nat Real rend certains noms ambigus (sqrt existe dans les deux) : regardez les types. Les types : de quels nombres parle-t-on ? Lean Mathématiques Attention ℕ $\\mathbb{N} = \\{0, 1, 2, \\dots\\}$ contient 0 ; soustraction et division tronquées (voir plus bas) ℤ $\\mathbb{Z}$ / est la division euclidienne : le reste % est toujours $\\ge 0$, -7 / 2 = -4 ℚ, ℝ, ℂ $\\mathbb{Q}$, $\\mathbb{R}$, $\\mathbb{C}$ division par zéro définie et égale à 0 Finset ℕ ensemble fini d'entiers Finset.range n $= \\{0, \\dots, n-1\\}$ Set ℝ partie de $\\mathbb{R}$ ℕ → ℝ suite réelle u n est le terme $un$ Quand un même énoncé mélange plusieurs types, Lean insère des conversions : (n : ℝ) ou ↑n désigne l'entier $n$ vu comme réel. Un énoncé comme (n : ℝ) / 2 n'a pas le même sens que n / 2 sur ℕ. Les pièges qui changent le sens Ces traductions sont acceptées par Lean, mais ne disent pas ce que l'on croit. 1. Soustraction sur ℕ : 2 - 5 = 0 dans ℕ. Un énoncé sur $a - b$ avec $a < b$ possible doit être écrit dans ℤ ou ℝ. 2. Division sur ℕ et ℤ : 7 / 2 = 3. « $n/2$ » en mathématiques est souvent un rationnel. 3. Division par zéro : dans ℝ, x / 0 = 0 par convention. Un énoncé x / y y = x est faux pour y = 0, et une traduction qui oublie l'hypothèse y ≠ 0 peut devenir fausse… ou triviale. 4. Fonctions totales : Real.sqrt (-1) = 0, Real.log 0 = 0. Une hypothèse oubliée ($x > 0$) ne provoque pas d'erreur. 5. Hypothèses contradictoires : si les hypothèses ne peuvent pas être toutes vraies, n'importe quelle conclusion se prouve. Une preuve très courte d'un énoncé difficile est un signal d'alarme. 6. Indices : Finset.range n commence à 0. $\\sum{k=1}^{n} k$ se traduit ∑ k in Finset.Icc 1 n, k ; avec Finset.range n on somme de 0 à $n-1$. 7. Quantificateurs : l'ordre compte. ∀ ε > 0, ∃ N, … n'est pas ∃ N, ∀ ε > 0, …. 8. « Il existe un unique » s'écrit ∃! x, P x ; ∃ x, P x n'affirme pas l'unicité. Notation : dans les versions récentes de Mathlib, la somme s'écrit ∑ k ∈ Finset.Icc 1 n, k ; l'espace « Prouveur » (Lean 4.9) utilise encore ∑ k in …. Une méthode de relecture 1. Lisez la conclusion seule : est-ce bien ce que vous voulez prouver ? 2. Listez les hypothèses : en manque-t-il ? y en a-t-il de trop (une hypothèse superflue rend l'énoncé plus faible) ? 3. Vérifiez le type de chaque variable. 4. Cherchez une division, une soustraction, une racine, un logarithme : sont-ils dans le bon type, avec les bonnes hypothèses ? 5. Essayez de nier l'énoncé sur un petit exemple. Si l'énoncé Lean est vrai et le vôtre faux (ou l'inverse), la traduction est fausse. Le panneau « Comprendre » (mode Apprendre) donne une glose ligne par ligne, écrite par un modèle : elle aide à lire, mais elle peut se tromper aussi ; le code fait foi. Le vocabulaire est dans le Glossaire.`},{id:`validation`,lang:`fr`,title:`Valider le sens et l'énoncé`,order:115,section:`use`,audience:`all`,summary:`Madalean montre ce qu'il a compris, puis l'énoncé Lean, et attend votre accord avant toute preuve.`,source:`fr/validation.md`,site_path:`fr/validation.html`,headings:[{level:1,text:`Valider le sens et l'énoncé`,id:`valider-le-sens-et-lenonce`},{level:2,text:`Problème ouvert ou faux`,id:`probleme-ouvert-ou-faux`},{level:2,text:`« Mal compris »`,id:`mal-compris`},{level:2,text:`Prouver sans valider`,id:`prouver-sans-valider`}],images:[],verify:[],body:`# Valider le sens et l'énoncé

Avant toute recherche de preuve, Madalean vous demande deux accords.

1. **Le sens** : l'énoncé reformulé, ses objets, ses hypothèses, ce qui est affirmé, et le statut connu. Un statut
   appuyé par un passage trouvé dans la littérature est cité mot pour mot ; sinon il est écrit « d'après un modèle, à
   vérifier ».
2. **L'énoncé Lean** : une ou deux traductions faites par des modèles différents, chacune relue par un modèle qui ne
   voit pas votre problème. Les objets ou les nombres absents sont signalés.

Vous pouvez accepter, corriger avec vos mots, ou écrire l'énoncé Lean vous-même. Les validations restent en attente
même si Madalean redémarre.

## Problème ouvert ou faux

Madalean le dit d'abord. Votre énoncé reste la cible du dossier. Les résultats connus voisins sont ouverts comme
sous-dossiers, jusqu'à leur propre validation ; une seule carte permet d'en accepter plusieurs.

Une correction qui change votre énoncé est marquée ainsi. Si les corrections tournent en rond, Madalean cesse d'en
proposer et l'explique.

## « Mal compris »

Signalez une étape mal comprise et dites pourquoi. Le travail qui en dépend s'arrête, l'étape est refaite avec votre
remarque, et la remarque sert aux problèmes semblables. Vous pouvez l'effacer dans les leçons (Réglages).

## Prouver sans valider

« Prouver quand même » accepte l'énoncé tel quel. Le réglage « Valider avant la preuve » peut être désactivé.
`,text:`Valider le sens et l'énoncé Avant toute recherche de preuve, Madalean vous demande deux accords. 1. Le sens : l'énoncé reformulé, ses objets, ses hypothèses, ce qui est affirmé, et le statut connu. Un statut appuyé par un passage trouvé dans la littérature est cité mot pour mot ; sinon il est écrit « d'après un modèle, à vérifier ». 2. L'énoncé Lean : une ou deux traductions faites par des modèles différents, chacune relue par un modèle qui ne voit pas votre problème. Les objets ou les nombres absents sont signalés. Vous pouvez accepter, corriger avec vos mots, ou écrire l'énoncé Lean vous-même. Les validations restent en attente même si Madalean redémarre. Problème ouvert ou faux Madalean le dit d'abord. Votre énoncé reste la cible du dossier. Les résultats connus voisins sont ouverts comme sous-dossiers, jusqu'à leur propre validation ; une seule carte permet d'en accepter plusieurs. Une correction qui change votre énoncé est marquée ainsi. Si les corrections tournent en rond, Madalean cesse d'en proposer et l'explique. « Mal compris » Signalez une étape mal comprise et dites pourquoi. Le travail qui en dépend s'arrête, l'étape est refaite avec votre remarque, et la remarque sert aux problèmes semblables. Vous pouvez l'effacer dans les leçons (Réglages). Prouver sans valider « Prouver quand même » accepte l'énoncé tel quel. Le réglage « Valider avant la preuve » peut être désactivé.`},{id:`follow-ups`,lang:`fr`,title:`Demandes de suivi et versions`,order:120,section:`use`,audience:`all`,summary:`Continuer la discussion sur un dossier, choisir l'étape à refaire, revenir à une version antérieure.`,source:`fr/follow-ups.md`,site_path:`fr/follow-ups.html`,headings:[{level:1,text:`Demandes de suivi et versions`,id:`demandes-de-suivi-et-versions`},{level:2,text:`Quelle étape est refaite ?`,id:`quelle-etape-est-refaite`},{level:2,text:`Les versions`,id:`les-versions`},{level:2,text:`Ce que l'assistant retient`,id:`ce-que-lassistant-retient`}],images:[],verify:[],body:`# Demandes de suivi et versions

Un dossier n'est jamais figé. Dans le fil du dossier, la zone « Une précision, une correction ? » accepte une
demande en langage courant :

- « ajoute l'hypothèse $n > 0$ »
- « et la réciproque ? »
- « une preuve plus courte »
- « explique l'étape 2 »
- « sans utiliser \`nlinarith\` »

\`Ctrl+Entrée\` envoie.

## Quelle étape est refaite ?

Le menu à côté de « Envoyer » choisit ce qui doit changer :

| Choix | Effet |
|---|---|
| *Automatique* | un modèle lit la demande et choisit l'étape ; à défaut, des mots-clés décident |
| *Énoncé* | nouvel énoncé Lean (selon la demande) → nouvelle preuve → nouvelle explication |
| *Preuve* | nouvelle preuve du même énoncé → nouvelle explication |
| *Explication* | nouvelle explication seulement |

Si la demande change l'énoncé, l'ancienne preuve ne s'applique plus : Madalean en cherche une nouvelle. Les boutons
sous la preuve (« Preuve plus simple », « Autre méthode », « Expliquer plus en détail », « Découper en lemmes ») sont
des demandes toutes faites.

## Les versions

Chaque énoncé, chaque preuve, chaque explication produit une **nouvelle version** ; rien n'est effacé. Chaque
version indique sa source (modèle, avec son nom, ou vous), la demande qui l'a produite et, pour une preuve, son
verdict Lean.

« Revenir à cette version » rend une version courante sans supprimer les autres. Revenir à une preuve ramène aussi
l'énoncé qu'elle prouve. Une preuve ne compte comme preuve du dossier que si elle prouve l'énoncé **courant**.

## Ce que l'assistant retient

- **Votre profil** (« Réglages › Profil ») : lu avant chaque traduction et chaque explication.
- **Le fil du dossier** : chaque correction s'appuie sur les versions précédentes.
- **La bibliothèque** : chaque résultat prouvé est proposé comme lemme aux preuves suivantes du même espace Lean.
- Les noms de lemmes que Lean a déjà refusés dans ce dossier ne sont plus proposés.
`,text:`Demandes de suivi et versions Un dossier n'est jamais figé. Dans le fil du dossier, la zone « Une précision, une correction ? » accepte une demande en langage courant : - « ajoute l'hypothèse $n > 0$ » - « et la réciproque ? » - « une preuve plus courte » - « explique l'étape 2 » - « sans utiliser nlinarith » Ctrl+Entrée envoie. Quelle étape est refaite ? Le menu à côté de « Envoyer » choisit ce qui doit changer : Choix Effet Automatique un modèle lit la demande et choisit l'étape ; à défaut, des mots-clés décident Énoncé nouvel énoncé Lean (selon la demande) → nouvelle preuve → nouvelle explication Preuve nouvelle preuve du même énoncé → nouvelle explication Explication nouvelle explication seulement Si la demande change l'énoncé, l'ancienne preuve ne s'applique plus : Madalean en cherche une nouvelle. Les boutons sous la preuve (« Preuve plus simple », « Autre méthode », « Expliquer plus en détail », « Découper en lemmes ») sont des demandes toutes faites. Les versions Chaque énoncé, chaque preuve, chaque explication produit une nouvelle version ; rien n'est effacé. Chaque version indique sa source (modèle, avec son nom, ou vous), la demande qui l'a produite et, pour une preuve, son verdict Lean. « Revenir à cette version » rend une version courante sans supprimer les autres. Revenir à une preuve ramène aussi l'énoncé qu'elle prouve. Une preuve ne compte comme preuve du dossier que si elle prouve l'énoncé courant. Ce que l'assistant retient - Votre profil (« Réglages › Profil ») : lu avant chaque traduction et chaque explication. - Le fil du dossier : chaque correction s'appuie sur les versions précédentes. - La bibliothèque : chaque résultat prouvé est proposé comme lemme aux preuves suivantes du même espace Lean. - Les noms de lemmes que Lean a déjà refusés dans ce dossier ne sont plus proposés.`},{id:`projects`,lang:`fr`,title:`Projets et dossiers en parallèle`,order:130,section:`use`,audience:`all`,summary:`Regrouper des dossiers en projets, lancer plusieurs travaux à la fois, comprendre la file d'attente.`,source:`fr/projects.md`,site_path:`fr/projects.html`,headings:[{level:1,text:`Projets et dossiers en parallèle`,id:`projets-et-dossiers-en-parallele`},{level:2,text:`Se repérer`,id:`se-reperer`},{level:2,text:`Projets`,id:`projets`},{level:2,text:`Plusieurs dossiers à la fois`,id:`plusieurs-dossiers-a-la-fois`},{level:2,text:`Sur tous les appareils`,id:`sur-tous-les-appareils`},{level:2,text:`Espaces Lean`,id:`espaces-lean`}],images:[{src:`img/navigation.png`,exists:!0},{src:`img/activity.png`,exists:!0}],verify:[],body:`# Projets et dossiers en parallèle

## Se repérer

Tout se trouve au même endroit sur un ordinateur, une tablette ou un téléphone :

- **Le logo Madal∃an**, en haut à gauche, ouvre le menu : « Accueil » en premier, puis Activité, Bibliothèque,
  Glossaire, Carnet, Aide, Réglages, le choix *Apprendre* / *Recherche* et la barre du projet. Un second clic sur
  le logo, menu ouvert, ramène à l'accueil.
- **Le nom du projet** (et, dans un dossier, celui du dossier) à côté du logo est le seul endroit où l'on change de
  projet ou de dossier : à gauche les projets (« Nouveau projet… », « Vue d'ensemble du projet »), à droite les
  dossiers du projet choisi, avec leur état. Les noms sont écrits en entier.
- **La barre du projet**, sous la barre du haut : Dossiers · Sources · Notes · Graphe · Blueprint · Article ·
  Conjectures · Calcul · Publier. \`Ctrl+Maj+1\` la masque ou la remet.
- **Le bouton d'état**, en haut à droite (nuage : en ligne ; puce : local) : le mode, le modèle qui reçoit votre
  travail, les ressources de l'ordinateur hôte (processeur, mémoire, carte graphique), les tokens et le coût
  (cette demande, aujourd'hui, ce mois-ci), les travaux en cours. Ces mesures ne sont prises que panneau ouvert.

Un menu ou un volet se ferme d'un clic ailleurs ou avec \`Échap\`. **Tout s'enregistre tout seul** : titre et énoncé
d'un dossier, notes, article, cellules de Calcul, code des expériences, plan, description du projet, réglages. Un petit
« Enregistré » le confirme ; « Non enregistré — réessai » signale un problème de réseau (Madalean réessaie, votre
texte reste à l'écran).

![Le menu du logo](img/navigation.png)

## Projets

Un **projet** regroupe des dossiers : un chapitre de cours, un article en préparation, une série d'exercices. Le
nom du projet en haut à gauche (« Tous les projets ») permet d'en choisir un ; la page « Dossiers » montre alors ses
dossiers. Un projet a son espace Lean, sa bibliographie, ses sources, ses notes, son plan d'article ; son titre et
sa description se modifient sur sa page (« Vue d'ensemble du projet »).

Supprimer un projet le met à la corbeille : « Annuler » le restaure. Ses dossiers ne sont pas supprimés.

## Plusieurs dossiers à la fois

Vous pouvez lancer autant de dossiers que vous voulez ; ils avancent en parallèle, limités par les ressources de
l'hôte :

| Ressource | Places | Utilisée par |
|---|---|---|
| carte graphique | 1 | un modèle local à la fois (Madalean change de modèle selon l'étape) |
| en ligne | 3 | appels aux modèles en ligne |
| Lean | 2 | compilations |

Un travail n'attend que la ressource de l'étape en cours ; vos travaux passent avant les relances automatiques.
L'écran « Activité » montre ce qui tourne, ce qui attend et pourquoi (« en attente : carte graphique »).

![Activité : travaux en parallèle](img/activity.png)

Un dossier n'a qu'un travail actif à la fois ; une nouvelle demande sur un dossier occupé est refusée avec un
message clair. Tout travail s'arrête à la demande.

## Sur tous les appareils

Tous les appareils reliés voient les mêmes projets, les mêmes dossiers et les mêmes travaux en direct. Lancez une
preuve depuis le téléphone, suivez-la sur le PC. Après une coupure réseau, l'appareil se resynchronise seul.

## Espaces Lean

Chaque projet utilise un **espace de travail** Lean (« Réglages › Espaces Lean ») :

- *Prouveur* : Lean 4.9 et la Mathlib d'entraînement des modèles Goedel. Épinglé : il n'est jamais mis à jour,
  pour que les modèles locaux restent efficaces.
- *Lean actuel* : dernière Mathlib, mise à jour automatiquement (voir [Mises à jour](updates.md)).

Un résultat de la bibliothèque n'est réutilisable que dans l'espace où il a été prouvé.
`,text:`Projets et dossiers en parallèle Se repérer Tout se trouve au même endroit sur un ordinateur, une tablette ou un téléphone : - Le logo Madal∃an, en haut à gauche, ouvre le menu : « Accueil » en premier, puis Activité, Bibliothèque, Glossaire, Carnet, Aide, Réglages, le choix Apprendre / Recherche et la barre du projet. Un second clic sur le logo, menu ouvert, ramène à l'accueil. - Le nom du projet (et, dans un dossier, celui du dossier) à côté du logo est le seul endroit où l'on change de projet ou de dossier : à gauche les projets (« Nouveau projet… », « Vue d'ensemble du projet »), à droite les dossiers du projet choisi, avec leur état. Les noms sont écrits en entier. - La barre du projet, sous la barre du haut : Dossiers · Sources · Notes · Graphe · Blueprint · Article · Conjectures · Calcul · Publier. Ctrl+Maj+1 la masque ou la remet. - Le bouton d'état, en haut à droite (nuage : en ligne ; puce : local) : le mode, le modèle qui reçoit votre travail, les ressources de l'ordinateur hôte (processeur, mémoire, carte graphique), les tokens et le coût (cette demande, aujourd'hui, ce mois-ci), les travaux en cours. Ces mesures ne sont prises que panneau ouvert. Un menu ou un volet se ferme d'un clic ailleurs ou avec Échap. Tout s'enregistre tout seul : titre et énoncé d'un dossier, notes, article, cellules de Calcul, code des expériences, plan, description du projet, réglages. Un petit « Enregistré » le confirme ; « Non enregistré — réessai » signale un problème de réseau (Madalean réessaie, votre texte reste à l'écran). Le menu du logo Projets Un projet regroupe des dossiers : un chapitre de cours, un article en préparation, une série d'exercices. Le nom du projet en haut à gauche (« Tous les projets ») permet d'en choisir un ; la page « Dossiers » montre alors ses dossiers. Un projet a son espace Lean, sa bibliographie, ses sources, ses notes, son plan d'article ; son titre et sa description se modifient sur sa page (« Vue d'ensemble du projet »). Supprimer un projet le met à la corbeille : « Annuler » le restaure. Ses dossiers ne sont pas supprimés. Plusieurs dossiers à la fois Vous pouvez lancer autant de dossiers que vous voulez ; ils avancent en parallèle, limités par les ressources de l'hôte : Ressource Places Utilisée par carte graphique 1 un modèle local à la fois (Madalean change de modèle selon l'étape) en ligne 3 appels aux modèles en ligne Lean 2 compilations Un travail n'attend que la ressource de l'étape en cours ; vos travaux passent avant les relances automatiques. L'écran « Activité » montre ce qui tourne, ce qui attend et pourquoi (« en attente : carte graphique »). Activité : travaux en parallèle Un dossier n'a qu'un travail actif à la fois ; une nouvelle demande sur un dossier occupé est refusée avec un message clair. Tout travail s'arrête à la demande. Sur tous les appareils Tous les appareils reliés voient les mêmes projets, les mêmes dossiers et les mêmes travaux en direct. Lancez une preuve depuis le téléphone, suivez-la sur le PC. Après une coupure réseau, l'appareil se resynchronise seul. Espaces Lean Chaque projet utilise un espace de travail Lean (« Réglages › Espaces Lean ») : - Prouveur : Lean 4.9 et la Mathlib d'entraînement des modèles Goedel. Épinglé : il n'est jamais mis à jour, pour que les modèles locaux restent efficaces. - Lean actuel : dernière Mathlib, mise à jour automatiquement (voir Mises à jour). Un résultat de la bibliothèque n'est réutilisable que dans l'espace où il a été prouvé.`},{id:`proof-plans`,lang:`fr`,title:`Plans de preuve et lemmes`,order:140,section:`use`,audience:`researcher`,summary:`Découper un résultat en lemmes prouvés en parallèle, admettre provisoirement, et ce que « prouvé modulo » veut dire.`,source:`fr/proof-plans.md`,site_path:`fr/proof-plans.html`,headings:[{level:1,text:`Plans de preuve et lemmes`,id:`plans-de-preuve-et-lemmes`},{level:2,text:`Découper en lemmes (rapide)`,id:`decouper-en-lemmes-rapide`},{level:2,text:`Plan de preuve en carte mentale (la voie principale)`,id:`plan-de-preuve-en-carte-mentale-la-voie-principale`},{level:2,text:`Admettre provisoirement`,id:`admettre-provisoirement`},{level:2,text:`Bon usage`,id:`bon-usage`}],images:[],verify:[],body:`# Plans de preuve et lemmes

Un énoncé trop gros pour une preuve d'un seul tenant se découpe. Madalean propose deux outils.

## Découper en lemmes (rapide)

« Découper en lemmes » sur un dossier : un modèle propose jusqu'à quatre lemmes en Lean (ou vous les écrivez, un par
paragraphe). Chaque lemme devient un **sous-dossier** lancé aussitôt, en parallèle. Quand tous sont terminés et
qu'au moins un est prouvé, le dossier parent est relancé automatiquement avec les lemmes prouvés à sa disposition.

## Plan de preuve en carte mentale (la voie principale)

Onglet « Plan » d'un dossier (aussi depuis le fil et après un échec de preuve). Un seul chemin :

1. **« Découper ce théorème »** (une piste pour l'IA est facultative). Le modèle propose 2 à 6 lemmes, de préférence
   indépendants, avec pour chacun son énoncé en mots, son énoncé Lean et pourquoi il aide, plus la **combinaison** :
   la preuve Lean du théorème à partir des lemmes. Il garde jusqu'à deux **autres pistes** (stratégies différentes),
   en pointillé sur la carte.
2. Avant de vous montrer le plan, **Lean vérifie** que chaque énoncé compile et que le théorème découle des lemmes ;
   sinon le plan est redemandé une fois avec les erreurs de Lean. Une combinaison non vérifiée est marquée
   « à vérifier ». Un lemme fermé par une tactique simple (\`simp\`, \`omega\`, \`exact?\`…) est **évident** : prouvé
   tout de suite, jamais redécoupé. Un lemme qui redit le théorème lui-même est **refusé** (garde-fou contre les
   boucles).
3. Relisez, modifiez si besoin (tout nœud se modifie à la main, chaque changement est une version), puis
   **« Valider le plan »** et **« Prouver le plan »** : chaque lemme devient un sous-dossier prouvé automatiquement
   (Mathlib d'abord, puis le tournoi de modèles) ; quand tous les lemmes d'un nœud sont prouvés, la combinaison est
   compilée avec les vraies preuves, verdict strict.
4. Madalean ne revient vers vous que si un lemme **échoue**, et propose dans l'ordre : une **autre piste**, le
   **redécouper** un niveau plus bas, ou **laisser un trou** (\`sorry\`).

En haut, une ligne « où en est-on » dit ce qu'il reste à faire. Chaque nœud a un état écrit (à valider, en cours,
prouvé, échoué, piste abandonnée, trou) et un chemin depuis le théorème. Limites : 3 niveaux de découpage
(réglable), 6 lemmes par piste, 2 autres pistes, 30 nœuds par plan, et une durée totale (Réglages › Modèles ›
avancé). Sur téléphone, la liste repliable est la vue principale, la carte est à un appui.

## Admettre provisoirement

Un nœud dont l'énoncé Lean est accepté peut être marqué « admis pour l'instant ». La preuve du parent peut alors
s'appuyer dessus : Lean compile le parent avec le lemme admis écrit \`sorry\`.

Le résultat est **prouvé modulo** les lemmes admis. Ce n'est **pas** une preuve vérifiée :

- il n'est pas enregistré comme preuve du dossier, qui reste « non prouvé » ;
- les axiomes listés contiennent \`sorryAx\`, la trace Lean d'un \`sorry\` ;
- le plan affiche « prouvé modulo N lemmes admis » avec leurs noms.

Quand chaque lemme admis reçoit ensuite une vraie preuve, Madalean remplace les \`sorry\` par les vrais lemmes et
revérifie le parent avec le verdict strict. Alors seulement le dossier est prouvé.

## Bon usage

- Énoncez les lemmes en Lean dès que possible : un nœud sans énoncé Lean accepté ne peut être ni prouvé ni admis.
- Préférez des lemmes **généraux** et courts ; ils entrent dans la bibliothèque et resservent.
- Un lemme refusé plusieurs fois est souvent mal énoncé (hypothèse manquante) plutôt que difficile : relisez-le
  comme dans [Lire un énoncé Lean](reading-lean.md).
`,text:`Plans de preuve et lemmes Un énoncé trop gros pour une preuve d'un seul tenant se découpe. Madalean propose deux outils. Découper en lemmes (rapide) « Découper en lemmes » sur un dossier : un modèle propose jusqu'à quatre lemmes en Lean (ou vous les écrivez, un par paragraphe). Chaque lemme devient un sous-dossier lancé aussitôt, en parallèle. Quand tous sont terminés et qu'au moins un est prouvé, le dossier parent est relancé automatiquement avec les lemmes prouvés à sa disposition. Plan de preuve en carte mentale (la voie principale) Onglet « Plan » d'un dossier (aussi depuis le fil et après un échec de preuve). Un seul chemin : 1. « Découper ce théorème » (une piste pour l'IA est facultative). Le modèle propose 2 à 6 lemmes, de préférence indépendants, avec pour chacun son énoncé en mots, son énoncé Lean et pourquoi il aide, plus la combinaison : la preuve Lean du théorème à partir des lemmes. Il garde jusqu'à deux autres pistes (stratégies différentes), en pointillé sur la carte. 2. Avant de vous montrer le plan, Lean vérifie que chaque énoncé compile et que le théorème découle des lemmes ; sinon le plan est redemandé une fois avec les erreurs de Lean. Une combinaison non vérifiée est marquée « à vérifier ». Un lemme fermé par une tactique simple (simp, omega, exact?…) est évident : prouvé tout de suite, jamais redécoupé. Un lemme qui redit le théorème lui-même est refusé (garde-fou contre les boucles). 3. Relisez, modifiez si besoin (tout nœud se modifie à la main, chaque changement est une version), puis « Valider le plan » et « Prouver le plan » : chaque lemme devient un sous-dossier prouvé automatiquement (Mathlib d'abord, puis le tournoi de modèles) ; quand tous les lemmes d'un nœud sont prouvés, la combinaison est compilée avec les vraies preuves, verdict strict. 4. Madalean ne revient vers vous que si un lemme échoue, et propose dans l'ordre : une autre piste, le redécouper un niveau plus bas, ou laisser un trou (sorry). En haut, une ligne « où en est-on » dit ce qu'il reste à faire. Chaque nœud a un état écrit (à valider, en cours, prouvé, échoué, piste abandonnée, trou) et un chemin depuis le théorème. Limites : 3 niveaux de découpage (réglable), 6 lemmes par piste, 2 autres pistes, 30 nœuds par plan, et une durée totale (Réglages › Modèles › avancé). Sur téléphone, la liste repliable est la vue principale, la carte est à un appui. Admettre provisoirement Un nœud dont l'énoncé Lean est accepté peut être marqué « admis pour l'instant ». La preuve du parent peut alors s'appuyer dessus : Lean compile le parent avec le lemme admis écrit sorry. Le résultat est prouvé modulo les lemmes admis. Ce n'est pas une preuve vérifiée : - il n'est pas enregistré comme preuve du dossier, qui reste « non prouvé » ; - les axiomes listés contiennent sorryAx, la trace Lean d'un sorry ; - le plan affiche « prouvé modulo N lemmes admis » avec leurs noms. Quand chaque lemme admis reçoit ensuite une vraie preuve, Madalean remplace les sorry par les vrais lemmes et revérifie le parent avec le verdict strict. Alors seulement le dossier est prouvé. Bon usage - Énoncez les lemmes en Lean dès que possible : un nœud sans énoncé Lean accepté ne peut être ni prouvé ni admis. - Préférez des lemmes généraux et courts ; ils entrent dans la bibliothèque et resservent. - Un lemme refusé plusieurs fois est souvent mal énoncé (hypothèse manquante) plutôt que difficile : relisez-le comme dans Lire un énoncé Lean.`},{id:`proof-graph`,lang:`fr`,title:`Graphe du problème, recherche raisonnée et leçons`,order:145,section:`use`,audience:`researcher`,summary:`Madalean garde la mémoire de chaque problème en graphe de lemmes, cherche une preuve avec des garde-fous, explique la démonstration avec sa bibliographie et retient ses erreurs.`,source:`fr/proof-graph.md`,site_path:`fr/proof-graph.html`,headings:[{level:1,text:`Graphe du problème, recherche raisonnée et leçons`,id:`graphe-du-probleme-recherche-raisonnee-et-lecons`},{level:2,text:`Les statuts`,id:`les-statuts`},{level:2,text:`La recherche raisonnée`,id:`la-recherche-raisonnee`},{level:2,text:`Expliquer la démonstration`,id:`expliquer-la-demonstration`},{level:2,text:`Sous-dossiers`,id:`sous-dossiers`},{level:2,text:`Adapter une méthode`,id:`adapter-une-methode`},{level:2,text:`Ce que Madalean a appris`,id:`ce-que-madalean-a-appris`}],images:[],verify:[],body:`# Graphe du problème, recherche raisonnée et leçons

Chaque dossier a un **graphe du problème** : la **cible** (le théorème ou la conjecture), les **résultats connus**
(Mathlib, votre bibliothèque, la littérature, les pièces jointes) et les **lemmes à prouver**, avec ce qui a été
essayé et pourquoi. Il prolonge le [plan de preuve](proof-plans.md) : onglet « Plan », affichage « Graphe ».

## Les statuts

Chaque nœud porte une icône, un mot et un style de bordure (jamais la couleur seule) :

| Statut | Sens |
| --- | --- |
| vérifié par Lean | prouvé par Lean (verdict strict), ou dans Mathlib, ou par un certificat |
| conditionnel | cité ou fourni sans preuve Lean, ou prouvé en utilisant un tel résultat |
| à prouver | encore ouvert |
| réfuté | Lean a prouvé la négation (contre-exemple) |
| abandonné | la raison est gardée ; la piste n'est pas réessayée tant que rien n'a changé |

Une preuve qui repose sur un résultat cité mais non prouvé en Lean est **toujours** « conditionnelle, repose sur … »,
jamais « vérifiée ». Elle devient vérifiée quand Lean prouve ce résultat.

Un même sous-lemme utilisé par deux lemmes n'existe qu'une fois : il est rangé sous le premier, l'autre affiche
« utilisé aussi par … ». Deux énoncés qui ne diffèrent que par une hypothèse restent distincts ; deux énoncés qui ne
diffèrent que par les noms des variables ou des hypothèses (\`n\` ou \`k\`, \`hn\` ou \`h\`) sont le même nœud (Lean le
confirme en cas de doute). Changer l'ordre des variables donne un autre nœud.

**Liste ou dessin.** Sur un écran large, « Dessin » montre le graphe dessiné : la cible en haut, chaque lemme sous
ceux qui l'utilisent, un sous-lemme partagé dessiné une seule fois. Glisser pour déplacer, molette ou + / − pour
zoomer ; Tab parcourt les nœuds dans l'ordre de la liste et Entrée ouvre le détail. Sur un téléphone, la liste reste
la seule vue.

## La recherche raisonnée

« Recherche raisonnée » essaie de prouver la cible seule, puis découpe en lemmes quand c'est utile. Avant de
travailler sur une piste, Madalean l'évalue (« Pourquoi cette piste ? ») : déjà prouvée ailleurs, déjà abandonnée,
proche d'une piste qui a échoué, même erreur de Lean deux fois, profondeur… et, si un modèle est disponible, un court
avis du modèle, toujours marqué comme tel. Les lemmes proposés sont d'abord vérifiés par Lean (énoncés, combinaison),
et Madalean cherche un contre-exemple : d'abord en calculant l'énoncé sur de petites valeurs quand c'est possible
(entiers de 0 à 12, rationnels simples — son propre calcul exact, jamais du code écrit par un modèle), puis Lean
essaie de prouver la négation. Un contre-exemple trouvé n'est retenu que si Lean le confirme : le lemme est alors
réfuté, avec le témoin. Sinon le détail du nœud indique « Testé sur n ∈ 0..12 : aucun contre-exemple », ce qui compte
un peu dans sa viabilité.

Garde-fous : limites de temps, d'essais, de profondeur, de jetons et de dépense (jamais au-delà du plafond du chef
d'orchestre), arrêt quand rien ne progresse, refus des boucles (un lemme qui utiliserait ce qui l'utilise). À la fin,
un résumé dit pourquoi la recherche s'est arrêtée et ce qui a été essayé. « Arrêter cette piste » et « Reprendre »
sont dans le détail de chaque nœud.

## Expliquer la démonstration

« Expliquer la démonstration » construit le récit **uniquement à partir de ce qui a été enregistré** : la piste
choisie et pourquoi, les autres pistes, les lemmes et leur statut, les tactiques employées et ce que fait chacune, ce
qui a échoué, et la bibliographie (déclarations Mathlib avec lien, ouvrages cités avec leur référence vérifiée,
BibTeX). Aucun modèle n'écrit ce texte. « Expliquer ligne par ligne » montre les buts de Lean après chaque tactique.
Exports : note du projet, LaTeX avec \`\\cite\`, BibTeX.

## Sous-dossiers

« Ouvrir comme sous-dossier » fait d'un lemme un dossier complet (son fil, son propre graphe, Calcul, notes,
certificats), rangé sous son parent : « Projet › Dossier › Lemme ». Son verdict remonte au parent (prouvé →
prouvé ; conditionnel → conditionnel). La profondeur est bornée par « Profondeur max. du découpage ». Archiver,
déplacer ou supprimer un dossier fait de même pour ses sous-dossiers (« Annuler » les ramène ensemble).

## Adapter une méthode

Sur un résultat dont la méthode est connue (sa preuve Lean, ou le passage cité), « Adapter la méthode » propose un
énoncé généralisé et les lemmes de la preuve adaptée. Ce sont des **propositions** : leurs énoncés sont vérifiés par
Lean, et seule une preuve Lean les validera.

## Ce que Madalean a appris

Réglages › « Ce que Madalean a appris » : des leçons tirées **seulement de preuves vérifiées**, quel que soit le
modèle — un nom Mathlib qui n'existe pas et celui qui marche (appliqué sans modèle puis revérifié par Lean), ce qui a
corrigé une erreur de Lean, les pistes sans issue, les stratégies qui marchent. Chaque leçon montre ses preuves et ses
compteurs ; celles qui ne servent plus disparaissent. Vous pouvez en supprimer, tout oublier, exporter ou importer
un fichier.
`,text:`Graphe du problème, recherche raisonnée et leçons Chaque dossier a un graphe du problème : la cible (le théorème ou la conjecture), les résultats connus (Mathlib, votre bibliothèque, la littérature, les pièces jointes) et les lemmes à prouver, avec ce qui a été essayé et pourquoi. Il prolonge le plan de preuve : onglet « Plan », affichage « Graphe ». Les statuts Chaque nœud porte une icône, un mot et un style de bordure (jamais la couleur seule) : Statut Sens vérifié par Lean prouvé par Lean (verdict strict), ou dans Mathlib, ou par un certificat conditionnel cité ou fourni sans preuve Lean, ou prouvé en utilisant un tel résultat à prouver encore ouvert réfuté Lean a prouvé la négation (contre-exemple) abandonné la raison est gardée ; la piste n'est pas réessayée tant que rien n'a changé Une preuve qui repose sur un résultat cité mais non prouvé en Lean est toujours « conditionnelle, repose sur … », jamais « vérifiée ». Elle devient vérifiée quand Lean prouve ce résultat. Un même sous-lemme utilisé par deux lemmes n'existe qu'une fois : il est rangé sous le premier, l'autre affiche « utilisé aussi par … ». Deux énoncés qui ne diffèrent que par une hypothèse restent distincts ; deux énoncés qui ne diffèrent que par les noms des variables ou des hypothèses (n ou k, hn ou h) sont le même nœud (Lean le confirme en cas de doute). Changer l'ordre des variables donne un autre nœud. Liste ou dessin. Sur un écran large, « Dessin » montre le graphe dessiné : la cible en haut, chaque lemme sous ceux qui l'utilisent, un sous-lemme partagé dessiné une seule fois. Glisser pour déplacer, molette ou + / − pour zoomer ; Tab parcourt les nœuds dans l'ordre de la liste et Entrée ouvre le détail. Sur un téléphone, la liste reste la seule vue. La recherche raisonnée « Recherche raisonnée » essaie de prouver la cible seule, puis découpe en lemmes quand c'est utile. Avant de travailler sur une piste, Madalean l'évalue (« Pourquoi cette piste ? ») : déjà prouvée ailleurs, déjà abandonnée, proche d'une piste qui a échoué, même erreur de Lean deux fois, profondeur… et, si un modèle est disponible, un court avis du modèle, toujours marqué comme tel. Les lemmes proposés sont d'abord vérifiés par Lean (énoncés, combinaison), et Madalean cherche un contre-exemple : d'abord en calculant l'énoncé sur de petites valeurs quand c'est possible (entiers de 0 à 12, rationnels simples — son propre calcul exact, jamais du code écrit par un modèle), puis Lean essaie de prouver la négation. Un contre-exemple trouvé n'est retenu que si Lean le confirme : le lemme est alors réfuté, avec le témoin. Sinon le détail du nœud indique « Testé sur n ∈ 0..12 : aucun contre-exemple », ce qui compte un peu dans sa viabilité. Garde-fous : limites de temps, d'essais, de profondeur, de jetons et de dépense (jamais au-delà du plafond du chef d'orchestre), arrêt quand rien ne progresse, refus des boucles (un lemme qui utiliserait ce qui l'utilise). À la fin, un résumé dit pourquoi la recherche s'est arrêtée et ce qui a été essayé. « Arrêter cette piste » et « Reprendre » sont dans le détail de chaque nœud. Expliquer la démonstration « Expliquer la démonstration » construit le récit uniquement à partir de ce qui a été enregistré : la piste choisie et pourquoi, les autres pistes, les lemmes et leur statut, les tactiques employées et ce que fait chacune, ce qui a échoué, et la bibliographie (déclarations Mathlib avec lien, ouvrages cités avec leur référence vérifiée, BibTeX). Aucun modèle n'écrit ce texte. « Expliquer ligne par ligne » montre les buts de Lean après chaque tactique. Exports : note du projet, LaTeX avec \\cite, BibTeX. Sous-dossiers « Ouvrir comme sous-dossier » fait d'un lemme un dossier complet (son fil, son propre graphe, Calcul, notes, certificats), rangé sous son parent : « Projet › Dossier › Lemme ». Son verdict remonte au parent (prouvé → prouvé ; conditionnel → conditionnel). La profondeur est bornée par « Profondeur max. du découpage ». Archiver, déplacer ou supprimer un dossier fait de même pour ses sous-dossiers (« Annuler » les ramène ensemble). Adapter une méthode Sur un résultat dont la méthode est connue (sa preuve Lean, ou le passage cité), « Adapter la méthode » propose un énoncé généralisé et les lemmes de la preuve adaptée. Ce sont des propositions : leurs énoncés sont vérifiés par Lean, et seule une preuve Lean les validera. Ce que Madalean a appris Réglages › « Ce que Madalean a appris » : des leçons tirées seulement de preuves vérifiées, quel que soit le modèle — un nom Mathlib qui n'existe pas et celui qui marche (appliqué sans modèle puis revérifié par Lean), ce qui a corrigé une erreur de Lean, les pistes sans issue, les stratégies qui marchent. Chaque leçon montre ses preuves et ses compteurs ; celles qui ne servent plus disparaissent. Vous pouvez en supprimer, tout oublier, exporter ou importer un fichier.`},{id:`library`,lang:`fr`,title:`Bibliothèque de résultats`,order:150,section:`use`,audience:`all`,summary:`Vos résultats prouvés, rangés par domaine, projet ou étiquette, avec leur statut, qui les a prouvés, ce qu'ils utilisent et l'export.`,source:`fr/library.md`,site_path:`fr/library.html`,headings:[{level:1,text:`Bibliothèque de résultats`,id:`bibliotheque-de-resultats`}],images:[],verify:[],body:`# Bibliothèque de résultats

Chaque preuve acceptée par Lean entre dans la **Bibliothèque** ; ces résultats sont ensuite proposés comme lemmes à
vos prochaines preuves (même version de Lean et de Mathlib).

- **Ranger par** domaine (classé automatiquement d'après l'énoncé, modifiable), projet ou étiquette.
- **Cartes** ou **Tableau** : le choix est mémorisé sur cet appareil.
- **Statut** : *Vérifié* (Lean a accepté la preuve, verdict strict) ou *Conditionnel* (preuve obtenue en admettant
  des lemmes d'un plan de preuve : rien n'est vérifié tant qu'ils ne sont pas prouvés).
- Pour chaque résultat : l'énoncé en mots et en Lean, le modèle (ou vous) qui l'a prouvé, les axiomes, ce qu'il
  **utilise** et ce qui **l'utilise**.
- **Exporter** : tout en Markdown ou JSON ; un résultat seul en \`.lean\` (avec les résultats dont il dépend).

Le domaine et les étiquettes sont partagés entre vos appareils. Retirer un résultat se fait avec annulation possible.
`,text:`Bibliothèque de résultats Chaque preuve acceptée par Lean entre dans la Bibliothèque ; ces résultats sont ensuite proposés comme lemmes à vos prochaines preuves (même version de Lean et de Mathlib). - Ranger par domaine (classé automatiquement d'après l'énoncé, modifiable), projet ou étiquette. - Cartes ou Tableau : le choix est mémorisé sur cet appareil. - Statut : Vérifié (Lean a accepté la preuve, verdict strict) ou Conditionnel (preuve obtenue en admettant des lemmes d'un plan de preuve : rien n'est vérifié tant qu'ils ne sont pas prouvés). - Pour chaque résultat : l'énoncé en mots et en Lean, le modèle (ou vous) qui l'a prouvé, les axiomes, ce qu'il utilise et ce qui l'utilise. - Exporter : tout en Markdown ou JSON ; un résultat seul en .lean (avec les résultats dont il dépend). Le domaine et les étiquettes sont partagés entre vos appareils. Retirer un résultat se fait avec annulation possible.`},{id:`conjectures`,lang:`fr`,title:`Atelier de conjectures`,order:200,section:`research`,audience:`researcher`,summary:`Proposer des conjectures, les tester (Lean sur petits cas, Sage, contre-exemples) avant d'y croire, et les promouvoir par une preuve.`,source:`fr/conjectures.md`,site_path:`fr/conjectures.html`,headings:[{level:1,text:`Atelier de conjectures`,id:`atelier-de-conjectures`},{level:2,text:`D'où viennent les conjectures`,id:`dou-viennent-les-conjectures`},{level:2,text:`Explorer : le moteur de conjectures`,id:`explorer-le-moteur-de-conjectures`},{level:2,text:`Les états d'une conjecture`,id:`les-etats-dune-conjecture`},{level:2,text:`Tester avant de croire`,id:`tester-avant-de-croire`},{level:2,text:`Le journal des indices`,id:`le-journal-des-indices`},{level:2,text:`Promouvoir`,id:`promouvoir`}],images:[],verify:[],body:`# Atelier de conjectures

Une conjecture est un dossier d'un genre particulier, avec un **journal des indices** : tout ce qui a été tenté pour
l'éprouver. Une conjecture ne devient un théorème que par une preuve Lean.

## D'où viennent les conjectures

Tout se passe dans l'écran « Conjectures » du projet.

- « Écrire une conjecture » : vous l'écrivez en langage courant ; « Traduire en Lean » en propose ensuite un énoncé
  Lean, ou vous l'écrivez vous-même (« Vérifier et enregistrer l'énoncé »).
- « Proposer » : à partir des notes, des résultats prouvés et des sources du projet, un modèle en propose quelques-unes
  avec leur motivation ; « Garder cette conjecture » retient celles qui vous intéressent. Les propositions déjà
  connues (doublon, déjà un dossier, déjà dans la bibliothèque, déjà dans Mathlib) sont écartées et listées à part
  avec la raison.

## Explorer : le moteur de conjectures

Le bouton « Explorer » de l'écran « Conjectures » ouvre une démarche guidée pour **trouver quoi prouver**. Vous
posez une question en mots ou par une formule (« la somme des n premiers nombres impairs », « n^2 + n + 41 », une
liste de termes, « graphes connexes à n sommets »), puis les étapes s'enchaînent sous vos yeux ; chacune peut être
arrêtée, et tout est noté.

1. **Explorer.** Madalean calcule un tableau de données avec Sage, dans le carnet « Explorations (conjectures) » du
   projet (le même espace protégé que Calcul). Quand la demande est reconnue, le code est écrit sans modèle,
   toujours le même pour la même demande. Sinon un modèle l'écrit : **ce code vous est montré et ne s'exécute
   qu'après votre accord sur ce code exact**, comme dans [Calcul](calcul.md) ; une modification annule l'accord.
   Des termes donnés à la main ne demandent aucun calcul.
2. **Reconnaître.** Les données sont comparées à l'OEIS (l'encyclopédie des suites d'entiers) et passées par des
   chercheurs de motifs qui tournent sur votre ordinateur, sans réseau : formule polynomiale ou rationnelle,
   récurrence, série génératrice, multiplicativité, périodicité, congruences, ordre de grandeur, inégalités et
   relations entre quantités. Une formule est ajustée sur une partie des termes puis **validée sur des termes gardés
   à part** ; un motif qui échoue est écarté, et le journal dit sur quel terme. En mode Local, l'OEIS n'est pas
   interrogé : rien ne sort de l'ordinateur. La base LMFDB n'est pas interrogée (elle ne permet pas de chercher par
   une liste de termes).
3. **Énoncer.** Chaque motif retenu devient une conjecture précise, en mots et en formules, avec un énoncé Lean
   quand c'est possible (il doit être accepté par Lean) et une mention honnête : « vérifié jusqu'à n = 59 (60 cas),
   pas démontré », « heuristique », « coïncide sur 14 termes ». Jamais « vrai ».
4. **Attaquer.** « Chercher un contre-exemple » reprend le calcul plus loin et par sondage. Un contre-exemple n'est
   retenu qu'après un recalcul dans un noyau neuf et, s'il y a un énoncé Lean, la vérification par Lean : la
   conjecture est alors gardée comme « réfutée », avec son contre-exemple. Si elle résiste, « Tenter la preuve »
   l'envoie dans la chaîne habituelle (un dossier), ou « Garder comme conjecture ouverte » la range dans le projet.
5. **Journal.** Tout ce qui a été essayé — motifs retenus, motifs écartés et pourquoi, recherches, chasses — reste
   dans le journal de l'exploration, que vous pouvez exporter vers une note ou vers l'article. Une conjecture déjà
   présente dans le projet est signalée comme doublon.

Exemple du mode démo : « n^2 + n + 41 jusqu'à 30 » donne « toujours premier », vérifié jusqu'à n = 30 ; la chasse
trouve n = 40, et la conjecture est gardée, réfutée.

## Les états d'une conjecture

| État | Signification |
|---|---|
| proposée | énoncée, rien de testé |
| testée sur des cas | des cas particuliers ont tenu (Lean ou expériences) |
| énoncé Lean accepté | un énoncé Lean est accepté par Lean |
| prouvée | la preuve courante du dossier passe le verdict strict |
| réfutée | un contre-exemple a été **revérifié** indépendamment |

## Tester avant de croire

**Petits cas en Lean** (« Tester les petits cas avec Lean »). Madalean écrit un \`example\` par cas (par défaut $n = 0, \\dots, 9$ pour la première variable
entière) et tente de le fermer par calcul (\`norm_num\`, \`decide\`, \`simp\`, \`omega\`). Option : un énoncé borné
\`∀ n < K, …\` fermé par \`decide\`. Ces tests ne prouvent rien au-delà des cas testés.

**Expériences Sage ou Python.** Le modèle écrit (ou vous écrivez) un programme en deux parties : un prédicat
\`holds(...)\` et une recherche qui appelle \`report(...)\`. **Le code vous est montré et ne s'exécute qu'après votre
accord sur ce code exact** (« J'ai lu ce code : approuver et lancer ») ; une modification annule l'accord. Les
expériences ne se lancent que depuis l'ordinateur hôte. Les exécutions sont confinées (voir
[Sécurité](security.md#code-execute-sur-lhote)) et limitées en temps et en mémoire.

**Contre-exemple.** Un contre-exemple annoncé n'est pas cru sur parole : le prédicat seul est réévalué au témoin
dans un noyau neuf et, si la conjecture a un énoncé Lean, Lean doit accepter la négation de l'énoncé au témoin.
Alors seulement la conjecture passe à « réfutée ».

**Littérature.** « Chercher dans la littérature » interroge les bases bibliographiques (voir
[Sources](sources.md)) pour savoir si l'énoncé est connu.

## Le journal des indices

Dans l'écran, il s'appelle « Journal des preuves et essais ». Chaque test, expérience, vérification ou recherche ajoute une entrée datée (avec le code exécuté, la sortie, le
modèle et l'appareil). Le journal est **en ajout seul** et ses entrées sont chaînées par empreintes SHA-256 :
une entrée modifiée après coup se voit (« journal intact » / « journal altéré ! »).

## Promouvoir

Quand la conjecture est prouvée, « Promouvoir en théorème » change son genre ; l'historique est gardé.

Exemple du mode démo : « $n^2 + n + 41$ est premier pour tout $n$ » tient pour $n = 0, \\dots, 9$ en Lean, puis une
expérience trouve $n = 40$ ($40^2 + 40 + 41 = 41^2$), revérifié : réfutée.
`,text:`Atelier de conjectures Une conjecture est un dossier d'un genre particulier, avec un journal des indices : tout ce qui a été tenté pour l'éprouver. Une conjecture ne devient un théorème que par une preuve Lean. D'où viennent les conjectures Tout se passe dans l'écran « Conjectures » du projet. - « Écrire une conjecture » : vous l'écrivez en langage courant ; « Traduire en Lean » en propose ensuite un énoncé Lean, ou vous l'écrivez vous-même (« Vérifier et enregistrer l'énoncé »). - « Proposer » : à partir des notes, des résultats prouvés et des sources du projet, un modèle en propose quelques-unes avec leur motivation ; « Garder cette conjecture » retient celles qui vous intéressent. Les propositions déjà connues (doublon, déjà un dossier, déjà dans la bibliothèque, déjà dans Mathlib) sont écartées et listées à part avec la raison. Explorer : le moteur de conjectures Le bouton « Explorer » de l'écran « Conjectures » ouvre une démarche guidée pour trouver quoi prouver. Vous posez une question en mots ou par une formule (« la somme des n premiers nombres impairs », « n^2 + n + 41 », une liste de termes, « graphes connexes à n sommets »), puis les étapes s'enchaînent sous vos yeux ; chacune peut être arrêtée, et tout est noté. 1. Explorer. Madalean calcule un tableau de données avec Sage, dans le carnet « Explorations (conjectures) » du projet (le même espace protégé que Calcul). Quand la demande est reconnue, le code est écrit sans modèle, toujours le même pour la même demande. Sinon un modèle l'écrit : ce code vous est montré et ne s'exécute qu'après votre accord sur ce code exact, comme dans Calcul ; une modification annule l'accord. Des termes donnés à la main ne demandent aucun calcul. 2. Reconnaître. Les données sont comparées à l'OEIS (l'encyclopédie des suites d'entiers) et passées par des chercheurs de motifs qui tournent sur votre ordinateur, sans réseau : formule polynomiale ou rationnelle, récurrence, série génératrice, multiplicativité, périodicité, congruences, ordre de grandeur, inégalités et relations entre quantités. Une formule est ajustée sur une partie des termes puis validée sur des termes gardés à part ; un motif qui échoue est écarté, et le journal dit sur quel terme. En mode Local, l'OEIS n'est pas interrogé : rien ne sort de l'ordinateur. La base LMFDB n'est pas interrogée (elle ne permet pas de chercher par une liste de termes). 3. Énoncer. Chaque motif retenu devient une conjecture précise, en mots et en formules, avec un énoncé Lean quand c'est possible (il doit être accepté par Lean) et une mention honnête : « vérifié jusqu'à n = 59 (60 cas), pas démontré », « heuristique », « coïncide sur 14 termes ». Jamais « vrai ». 4. Attaquer. « Chercher un contre-exemple » reprend le calcul plus loin et par sondage. Un contre-exemple n'est retenu qu'après un recalcul dans un noyau neuf et, s'il y a un énoncé Lean, la vérification par Lean : la conjecture est alors gardée comme « réfutée », avec son contre-exemple. Si elle résiste, « Tenter la preuve » l'envoie dans la chaîne habituelle (un dossier), ou « Garder comme conjecture ouverte » la range dans le projet. 5. Journal. Tout ce qui a été essayé — motifs retenus, motifs écartés et pourquoi, recherches, chasses — reste dans le journal de l'exploration, que vous pouvez exporter vers une note ou vers l'article. Une conjecture déjà présente dans le projet est signalée comme doublon. Exemple du mode démo : « n^2 + n + 41 jusqu'à 30 » donne « toujours premier », vérifié jusqu'à n = 30 ; la chasse trouve n = 40, et la conjecture est gardée, réfutée. Les états d'une conjecture État Signification proposée énoncée, rien de testé testée sur des cas des cas particuliers ont tenu (Lean ou expériences) énoncé Lean accepté un énoncé Lean est accepté par Lean prouvée la preuve courante du dossier passe le verdict strict réfutée un contre-exemple a été revérifié indépendamment Tester avant de croire Petits cas en Lean (« Tester les petits cas avec Lean »). Madalean écrit un example par cas (par défaut $n = 0, \\dots, 9$ pour la première variable entière) et tente de le fermer par calcul (normnum, decide, simp, omega). Option : un énoncé borné ∀ n < K, … fermé par decide. Ces tests ne prouvent rien au-delà des cas testés. Expériences Sage ou Python. Le modèle écrit (ou vous écrivez) un programme en deux parties : un prédicat holds(...) et une recherche qui appelle report(...). Le code vous est montré et ne s'exécute qu'après votre accord sur ce code exact (« J'ai lu ce code : approuver et lancer ») ; une modification annule l'accord. Les expériences ne se lancent que depuis l'ordinateur hôte. Les exécutions sont confinées (voir Sécurité) et limitées en temps et en mémoire. Contre-exemple. Un contre-exemple annoncé n'est pas cru sur parole : le prédicat seul est réévalué au témoin dans un noyau neuf et, si la conjecture a un énoncé Lean, Lean doit accepter la négation de l'énoncé au témoin. Alors seulement la conjecture passe à « réfutée ». Littérature. « Chercher dans la littérature » interroge les bases bibliographiques (voir Sources) pour savoir si l'énoncé est connu. Le journal des indices Dans l'écran, il s'appelle « Journal des preuves et essais ». Chaque test, expérience, vérification ou recherche ajoute une entrée datée (avec le code exécuté, la sortie, le modèle et l'appareil). Le journal est en ajout seul et ses entrées sont chaînées par empreintes SHA-256 : une entrée modifiée après coup se voit (« journal intact » / « journal altéré ! »). Promouvoir Quand la conjecture est prouvée, « Promouvoir en théorème » change son genre ; l'historique est gardé. Exemple du mode démo : « $n^2 + n + 41$ est premier pour tout $n$ » tient pour $n = 0, \\dots, 9$ en Lean, puis une expérience trouve $n = 40$ ($40^2 + 40 + 41 = 41^2$), revérifié : réfutée.`},{id:`calcul`,lang:`fr`,title:`Calcul (Sage et Python)`,order:205,section:`research`,audience:`researcher`,summary:`Des carnets Sage ou Python dans un bac à sable hors ligne, un modèle qui écrit le code sur demande, et un clic pour transformer un résultat en conjecture, note, dossier Lean ou bloc d'article.`,source:`fr/calcul.md`,site_path:`fr/calcul.html`,headings:[{level:1,text:`Calcul (Sage et Python)`,id:`calcul-sage-et-python`},{level:2,text:`Qui peut exécuter quoi`,id:`qui-peut-executer-quoi`},{level:2,text:`Demander au modèle`,id:`demander-au-modele`},{level:2,text:`Sorties`,id:`sorties`},{level:2,text:`Utiliser un résultat`,id:`utiliser-un-resultat`},{level:2,text:`SageMath pas encore installé`,id:`sagemath-pas-encore-installe`}],images:[],verify:[],body:`# Calcul (Sage et Python)

L'écran **Calcul** (menu du projet) contient les **carnets** du projet (« Nouveau carnet », SageMath ou Python).
Un carnet est une suite de cellules qui partagent un même noyau : les variables restent d'une cellule à l'autre. Le
fichier est un carnet Jupyter ordinaire : « Ouvrir dans JupyterLab » l'ouvre tel quel, « Télécharger (.ipynb) » en
donne une copie. Le code s'exécute sur l'ordinateur hôte dans le **même bac à sable** que les expériences de
l'atelier de conjectures : pas d'accès au réseau, pas d'accès à vos clés ni à vos fichiers personnels, temps et
sortie limités.

## Qui peut exécuter quoi

- **Vos cellules** (celles que vous tapez) s'exécutent avec **Exécuter** (ou Ctrl+Entrée, Maj+Entrée pour passer à
  la suivante). « Tout exécuter » relance le carnet entier.
- **Le code écrit par le modèle** est marqué « À relire » : il ne s'exécute qu'après **Approuver et exécuter**.
  L'accord porte sur ce code précis : s'il change, il faut le relire et l'approuver à nouveau.
- Depuis un téléphone ou une tablette reliés, vous pouvez lire et écrire les cellules ; leur exécution n'est permise
  que si l'hôte a coché « Autoriser les expériences depuis les appareils reliés » (« Réglages › Carnet et accès »,
  réglage réservé à l'hôte).

## Demander au modèle

Le bouton **+** sous la dernière cellule ajoute une cellule (une cellule vide apparaît aussi après l'exécution de
la dernière). Tapez du code Sage, ou décrivez le calcul en mots (« les racines de x^5+x^3+x+1 dans F_16 ») : la
cellule reconnaît ce que vous avez tapé et l'indique par « Code / Demande » — un clic corrige si elle se trompe.
Maj+Entrée exécute le code ou envoie la demande. Le type de la cellule (Code, Demande, Texte, Figure) se choisit dans
le petit menu en tête de cellule.

Pour une demande, le modèle écrit le code en quelques secondes ; il s'affiche pendant qu'il s'écrit, vérifié avant
d'être montré pour la version de Sage installée. « Réécrire », juste sous la demande, relance l'écriture à tout
moment ; « Approuver et exécuter » est juste sous le code. Quand le code utilise des noms définis plus haut, la
cellule le dit (« Utilise F, f des cellules précédentes »). Si l'exécution échoue, le modèle corrige automatiquement
(trois fois au plus) : chaque correction est une version de la cellule (« Revenir à la version précédente ») et reste
à approuver, sauf si l'hôte a choisi d'exécuter le code du modèle sans accord.

Sur une erreur, « Expliquer l'erreur » dit en mots simples ce qui ne va pas et propose une correction, que vous
appliquez d'un clic (elle reste à approuver). Dans « ⋯ », « Expliquer ligne par ligne » commente chaque ligne.
Les demandes qui ont fonctionné deviennent des **recettes apprises** : une demande semblable est écrite aussitôt
(« ⋯ » du carnet › « Recettes apprises » pour les voir ou les supprimer). Un calcul
ne prouve rien en général : il vérifie des cas.

## Sorties

Texte, formules (affichées comme en LaTeX) et graphiques. Une sortie devenue « Périmé » (code ou cellule au-dessus
modifiés depuis) est signalée. Chaque cellule garde les versions de son code (« Historique »).

## Utiliser un résultat

Dans « Plus d'actions » d'une cellule qui a une sortie :

| Action | Effet |
|---|---|
| Créer une conjecture | crée une conjecture du projet ; le code et sa sortie sont joints comme motivation |
| Ajouter à une note | copie le code et sa sortie dans une nouvelle note |
| Créer un dossier Lean | ouvre un dossier avec l'énoncé à prouver, prérempli depuis le résultat (à corriger si besoin) |
| Insérer dans l'article | le résultat entre dans l'article ; le code va dans la section « Calculs » en fin d'article |

Un graphique PNG de Calcul peut aussi être inséré comme figure de l'article (« Insérer › Figure… › Depuis Calcul »
dans l'éditeur d'article).

## SageMath pas encore installé

Les carnets Python fonctionnent tout de suite. SageMath s'installe à la demande (environ 1,5 Go à télécharger, près
de 5 Go sur le disque) : bouton **Installer Sage** dans un carnet Sage, sur l'ordinateur hôte. L'écran affiche
l'étape en cours et le pourcentage.
`,text:`Calcul (Sage et Python) L'écran Calcul (menu du projet) contient les carnets du projet (« Nouveau carnet », SageMath ou Python). Un carnet est une suite de cellules qui partagent un même noyau : les variables restent d'une cellule à l'autre. Le fichier est un carnet Jupyter ordinaire : « Ouvrir dans JupyterLab » l'ouvre tel quel, « Télécharger (.ipynb) » en donne une copie. Le code s'exécute sur l'ordinateur hôte dans le même bac à sable que les expériences de l'atelier de conjectures : pas d'accès au réseau, pas d'accès à vos clés ni à vos fichiers personnels, temps et sortie limités. Qui peut exécuter quoi - Vos cellules (celles que vous tapez) s'exécutent avec Exécuter (ou Ctrl+Entrée, Maj+Entrée pour passer à la suivante). « Tout exécuter » relance le carnet entier. - Le code écrit par le modèle est marqué « À relire » : il ne s'exécute qu'après Approuver et exécuter. L'accord porte sur ce code précis : s'il change, il faut le relire et l'approuver à nouveau. - Depuis un téléphone ou une tablette reliés, vous pouvez lire et écrire les cellules ; leur exécution n'est permise que si l'hôte a coché « Autoriser les expériences depuis les appareils reliés » (« Réglages › Carnet et accès », réglage réservé à l'hôte). Demander au modèle Le bouton + sous la dernière cellule ajoute une cellule (une cellule vide apparaît aussi après l'exécution de la dernière). Tapez du code Sage, ou décrivez le calcul en mots (« les racines de x^5+x^3+x+1 dans F16 ») : la cellule reconnaît ce que vous avez tapé et l'indique par « Code / Demande » — un clic corrige si elle se trompe. Maj+Entrée exécute le code ou envoie la demande. Le type de la cellule (Code, Demande, Texte, Figure) se choisit dans le petit menu en tête de cellule. Pour une demande, le modèle écrit le code en quelques secondes ; il s'affiche pendant qu'il s'écrit, vérifié avant d'être montré pour la version de Sage installée. « Réécrire », juste sous la demande, relance l'écriture à tout moment ; « Approuver et exécuter » est juste sous le code. Quand le code utilise des noms définis plus haut, la cellule le dit (« Utilise F, f des cellules précédentes »). Si l'exécution échoue, le modèle corrige automatiquement (trois fois au plus) : chaque correction est une version de la cellule (« Revenir à la version précédente ») et reste à approuver, sauf si l'hôte a choisi d'exécuter le code du modèle sans accord. Sur une erreur, « Expliquer l'erreur » dit en mots simples ce qui ne va pas et propose une correction, que vous appliquez d'un clic (elle reste à approuver). Dans « ⋯ », « Expliquer ligne par ligne » commente chaque ligne. Les demandes qui ont fonctionné deviennent des recettes apprises : une demande semblable est écrite aussitôt (« ⋯ » du carnet › « Recettes apprises » pour les voir ou les supprimer). Un calcul ne prouve rien en général : il vérifie des cas. Sorties Texte, formules (affichées comme en LaTeX) et graphiques. Une sortie devenue « Périmé » (code ou cellule au-dessus modifiés depuis) est signalée. Chaque cellule garde les versions de son code (« Historique »). Utiliser un résultat Dans « Plus d'actions » d'une cellule qui a une sortie : Action Effet Créer une conjecture crée une conjecture du projet ; le code et sa sortie sont joints comme motivation Ajouter à une note copie le code et sa sortie dans une nouvelle note Créer un dossier Lean ouvre un dossier avec l'énoncé à prouver, prérempli depuis le résultat (à corriger si besoin) Insérer dans l'article le résultat entre dans l'article ; le code va dans la section « Calculs » en fin d'article Un graphique PNG de Calcul peut aussi être inséré comme figure de l'article (« Insérer › Figure… › Depuis Calcul » dans l'éditeur d'article). SageMath pas encore installé Les carnets Python fonctionnent tout de suite. SageMath s'installe à la demande (environ 1,5 Go à télécharger, près de 5 Go sur le disque) : bouton Installer Sage dans un carnet Sage, sur l'ordinateur hôte. L'écran affiche l'étape en cours et le pourcentage.`},{id:`news`,lang:`fr`,title:`Actualités`,order:205,section:`research`,audience:`all`,summary:`Suivre ce qui est nouveau en mathématiques — articles par domaine, problèmes ouverts, Lean et Mathlib, IA pour les maths — et l'envoyer vers un projet.`,source:`fr/news.md`,site_path:`fr/news.html`,headings:[{level:1,text:`Actualités`,id:`actualites`},{level:2,text:`Ce que vous y trouvez`,id:`ce-que-vous-y-trouvez`},{level:2,text:`Trier et chercher`,id:`trier-et-chercher`},{level:2,text:`Envoyer vers un projet`,id:`envoyer-vers-un-projet`},{level:2,text:`Résumé en français`,id:`resume-en-francais`},{level:2,text:`Mise à jour`,id:`mise-a-jour`},{level:2,text:`Réglages › Actualités`,id:`reglages-actualites`},{level:2,text:`Ce qui quitte votre ordinateur`,id:`ce-qui-quitte-votre-ordinateur`},{level:2,text:`Vérifier vous-même`,id:`verifier-vous-meme`}],images:[],verify:[],body:`# Actualités

L'écran **Actualités** (menu du logo) rassemble ce qui est nouveau en mathématiques. Madalean va le chercher pour
vous, de temps en temps, à des adresses publiques ; tout est gardé sur l'ordinateur hôte et se lit sans Internet.

## Ce que vous y trouvez

| Rubrique | Sources |
|---|---|
| Nouveaux articles | arXiv, toutes les catégories de mathématiques et la logique informatique |
| Problèmes ouverts | les problèmes d'Erdős (changements d'état), les questions « open-problems » de MathOverflow, le blog Polymath |
| Lean et Mathlib | les versions de Lean, les derniers ajouts à Mathlib, le blog de la communauté Lean, le blog Xena |
| IA pour les maths | les articles d'arXiv sur la preuve automatique, la formalisation et le raisonnement mathématique |
| Annonces, prix et vulgarisation | l'AMS, Quanta Magazine, Images des mathématiques, le blog de Terence Tao |
| Vos flux | les adresses RSS ou Atom que vous ajoutez vous-même |

Chaque élément montre sa source, sa date, ses auteurs, son résumé et un lien vers la page d'origine, qui s'ouvre dans
le navigateur. Madalean ne garde que le titre, un extrait et le lien : le texte complet se lit sur le site d'origine.

## Trier et chercher

- **Chercher** : un mot, un auteur ; les accents ne comptent pas.
- **Domaine** : algèbre, théorie des nombres, géométrie, topologie, analyse, équations aux dérivées partielles,
  probabilités, statistique, combinatoire, logique, théorie des catégories, analyse numérique, optimisation, physique
  mathématique, histoire et enseignement. Le domaine vient de la catégorie donnée par la source, sinon des mots du
  titre et du résumé.
- **Non lus**, **Enregistrés**, **Problèmes ouverts**.
- **Mes domaines** : seulement les domaines cochés dans Réglages › Actualités.
- **Pour mes projets** : les éléments qui partagent des mots rares avec vos projets (titres, énoncés des dossiers,
  titres des notes et des sources). Les mots en commun sont affichés. Ce tri se fait sur votre ordinateur : rien de
  vos projets n'est envoyé.

Ouvrir un élément le marque comme lu. « Enregistrer » le garde sans limite de durée.

## Envoyer vers un projet

Dans un élément ouvert, quatre boutons l'envoient vers le projet choisi dans la barre du haut :

- **Ajouter aux Sources du projet** (articles arXiv) : l'article entre dans la bibliothèque du projet, comme si vous
  aviez donné son identifiant dans l'écran Sources.
- **Créer une conjecture** : le titre et le résumé deviennent l'énoncé d'une conjecture, avec le lien d'origine.
- **Créer un dossier à partir de ce problème** : un dossier est créé avec ce texte comme énoncé. Rien n'est lancé :
  relisez et corrigez l'énoncé d'abord.
- **Envoyer dans une note** : une note avec la citation, les auteurs, le lien et la date.

## Résumé en français

« Résumer en français » demande à un modèle gratuit en ligne un résumé de deux ou trois phrases. Le texte d'origine
reste toujours affiché en dessous : le résumé est une aide de lecture, pas une source. Le bouton n'apparaît que pour
les sources dont la licence le permet (arXiv, MathOverflow, Mathlib, vos propres flux) ; pour un blog, un magazine ou
une société savante, Madalean s'en tient au titre, à l'extrait et au lien. Le réglage « Résumer
automatiquement » le fait pour quelques nouveautés de vos domaines à chaque mise à jour.

Un texte venu d'Internet peut contenir des phrases écrites pour tromper un programme. Madalean le traite comme un
texte à lire, jamais comme une consigne ; s'il repère de telles phrases, il l'indique et n'envoie pas ce texte à un
modèle.

## Mise à jour

Par défaut toutes les 6 heures, tant que l'ordinateur hôte est allumé et relié à Internet. « Mettre à jour » le fait
tout de suite. Une source qui ne répond pas est réessayée plus tard, de moins en moins souvent.

En **mode Local**, Madalean ne va rien chercher : vous lisez ce qui est déjà enregistré.

Le nombre de non lus apparaît sur l'accueil (« Nouveautés ») et dans le menu. Aucun message ne s'affiche tout seul.

## Réglages › Actualités

- les domaines suivis ;
- chaque source, à activer ou arrêter, avec sa licence et ses conditions ;
- vos propres flux RSS ou Atom (une adresse en \`https\` d'un site public) ;
- la fréquence, la durée de conservation, les résumés automatiques, l'affichage du nombre de non lus.

## Ce qui quitte votre ordinateur

Seulement des lectures anonymes des adresses listées dans Réglages › Actualités : pas de compte, pas de clé, pas de
nom, pas d'adresse e-mail. Si vous demandez un résumé, le titre et le résumé public de l'élément sont envoyés au
modèle en ligne, et rien d'autre. Voir aussi [Sécurité et vie privée](security.md).

## Vérifier vous-même

1. Menu du logo › Actualités : la liste se remplit après « Mettre à jour » (hors mode Local).
2. Cochez « Problèmes ouverts » : il ne reste que des questions MathOverflow et des problèmes d'Erdős ouverts.
3. Passez en mode Local, puis « Mettre à jour » : le bouton est inactif et la liste reste lisible.
`,text:`Actualités L'écran Actualités (menu du logo) rassemble ce qui est nouveau en mathématiques. Madalean va le chercher pour vous, de temps en temps, à des adresses publiques ; tout est gardé sur l'ordinateur hôte et se lit sans Internet. Ce que vous y trouvez Rubrique Sources Nouveaux articles arXiv, toutes les catégories de mathématiques et la logique informatique Problèmes ouverts les problèmes d'Erdős (changements d'état), les questions « open-problems » de MathOverflow, le blog Polymath Lean et Mathlib les versions de Lean, les derniers ajouts à Mathlib, le blog de la communauté Lean, le blog Xena IA pour les maths les articles d'arXiv sur la preuve automatique, la formalisation et le raisonnement mathématique Annonces, prix et vulgarisation l'AMS, Quanta Magazine, Images des mathématiques, le blog de Terence Tao Vos flux les adresses RSS ou Atom que vous ajoutez vous-même Chaque élément montre sa source, sa date, ses auteurs, son résumé et un lien vers la page d'origine, qui s'ouvre dans le navigateur. Madalean ne garde que le titre, un extrait et le lien : le texte complet se lit sur le site d'origine. Trier et chercher - Chercher : un mot, un auteur ; les accents ne comptent pas. - Domaine : algèbre, théorie des nombres, géométrie, topologie, analyse, équations aux dérivées partielles, probabilités, statistique, combinatoire, logique, théorie des catégories, analyse numérique, optimisation, physique mathématique, histoire et enseignement. Le domaine vient de la catégorie donnée par la source, sinon des mots du titre et du résumé. - Non lus, Enregistrés, Problèmes ouverts. - Mes domaines : seulement les domaines cochés dans Réglages › Actualités. - Pour mes projets : les éléments qui partagent des mots rares avec vos projets (titres, énoncés des dossiers, titres des notes et des sources). Les mots en commun sont affichés. Ce tri se fait sur votre ordinateur : rien de vos projets n'est envoyé. Ouvrir un élément le marque comme lu. « Enregistrer » le garde sans limite de durée. Envoyer vers un projet Dans un élément ouvert, quatre boutons l'envoient vers le projet choisi dans la barre du haut : - Ajouter aux Sources du projet (articles arXiv) : l'article entre dans la bibliothèque du projet, comme si vous aviez donné son identifiant dans l'écran Sources. - Créer une conjecture : le titre et le résumé deviennent l'énoncé d'une conjecture, avec le lien d'origine. - Créer un dossier à partir de ce problème : un dossier est créé avec ce texte comme énoncé. Rien n'est lancé : relisez et corrigez l'énoncé d'abord. - Envoyer dans une note : une note avec la citation, les auteurs, le lien et la date. Résumé en français « Résumer en français » demande à un modèle gratuit en ligne un résumé de deux ou trois phrases. Le texte d'origine reste toujours affiché en dessous : le résumé est une aide de lecture, pas une source. Le bouton n'apparaît que pour les sources dont la licence le permet (arXiv, MathOverflow, Mathlib, vos propres flux) ; pour un blog, un magazine ou une société savante, Madalean s'en tient au titre, à l'extrait et au lien. Le réglage « Résumer automatiquement » le fait pour quelques nouveautés de vos domaines à chaque mise à jour. Un texte venu d'Internet peut contenir des phrases écrites pour tromper un programme. Madalean le traite comme un texte à lire, jamais comme une consigne ; s'il repère de telles phrases, il l'indique et n'envoie pas ce texte à un modèle. Mise à jour Par défaut toutes les 6 heures, tant que l'ordinateur hôte est allumé et relié à Internet. « Mettre à jour » le fait tout de suite. Une source qui ne répond pas est réessayée plus tard, de moins en moins souvent. En mode Local, Madalean ne va rien chercher : vous lisez ce qui est déjà enregistré. Le nombre de non lus apparaît sur l'accueil (« Nouveautés ») et dans le menu. Aucun message ne s'affiche tout seul. Réglages › Actualités - les domaines suivis ; - chaque source, à activer ou arrêter, avec sa licence et ses conditions ; - vos propres flux RSS ou Atom (une adresse en https d'un site public) ; - la fréquence, la durée de conservation, les résumés automatiques, l'affichage du nombre de non lus. Ce qui quitte votre ordinateur Seulement des lectures anonymes des adresses listées dans Réglages › Actualités : pas de compte, pas de clé, pas de nom, pas d'adresse e-mail. Si vous demandez un résumé, le titre et le résumé public de l'élément sont envoyés au modèle en ligne, et rien d'autre. Voir aussi Sécurité et vie privée. Vérifier vous-même 1. Menu du logo › Actualités : la liste se remplit après « Mettre à jour » (hors mode Local). 2. Cochez « Problèmes ouverts » : il ne reste que des questions MathOverflow et des problèmes d'Erdős ouverts. 3. Passez en mode Local, puis « Mettre à jour » : le bouton est inactif et la liste reste lisible.`},{id:`certificates`,lang:`fr`,title:`Certificats : Sage calcule, Lean vérifie`,order:207,section:`research`,audience:`researcher`,summary:`Pour les énoncés qui s'y prêtent, Sage cherche un témoin et Lean ne fait que le vérifier — sans modèle, sans coût, en quelques secondes.`,source:`fr/certificates.md`,site_path:`fr/certificates.html`,headings:[{level:1,text:`Certificats : Sage calcule, Lean vérifie`,id:`certificats-sage-calcule-lean-verifie`},{level:2,text:`Ce qui est couvert`,id:`ce-qui-est-couvert`},{level:2,text:`Où les trouver`,id:`ou-les-trouver`},{level:2,text:`Limites`,id:`limites`}],images:[],verify:[],body:`# Certificats : Sage calcule, Lean vérifie

Un **certificat** est un témoin facile à vérifier : un facteur, un inverse, une somme de carrés, un contre-exemple…
Sage le cherche (cela peut être difficile), puis Lean le **vérifie** (c'est facile et sûr). Si le témoin est faux,
Lean le refuse : un certificat ne peut jamais faire passer une erreur pour une preuve.

## Ce qui est couvert

| Famille | Exemple d'énoncé | Ce que Lean vérifie |
|---|---|---|
| Primalité | « 1 000 003 est premier » | un certificat de Pratt |
| Nombre composé | « 2³² + 1 n'est pas premier » | un facteur |
| Arithmétique | pgcd, ppcm, divisibilité, congruences, factorielles | le calcul |
| Puissance modulaire | « 3^1000000 mod 7 = … » | le calcul pas à pas |
| Identité | une égalité polynomiale | \`ring\` |
| Idéal | « f est dans l'idéal engendré par g et h » | les cofacteurs (base de Gröbner) |
| Arithmétique linéaire | un système d'inégalités sans solution | la combinaison de Farkas |
| Somme de carrés | « x² + y² ≥ 2xy » | l'écriture comme somme de carrés |
| Existence | « ∃ x, 17x ≡ 1 (mod 3120) » | le témoin (x = 2753) |
| Contre-exemple | « n² + n + 41 est premier pour tout n » | le contre-exemple (n = 40) |
| Borne numérique | « √2 < 1,415 », bornes sur π, e, log 2 | l'encadrement |
| Cas finis | « pour tout n ≤ 20, … » | l'énumération |

Lean vérifie tout dans son noyau, sans passer par du code compilé (\`native_decide\` n'est jamais utilisé).

## Où les trouver

1. **Dans une preuve** — la stratégie « certificat » se lance seule, à côté de la recherche dans Mathlib, quand
   l'énoncé a une forme reconnue. Le fil du dossier affiche « témoin calculé par Sage, vérifié par Lean » avec le
   témoin. Elle se règle dans **Réglages › Modèles › Certificats** (activée par défaut).
2. **Pour les modèles qui prouvent** — ils peuvent demander un témoin à Sage pendant leur recherche. Ils envoient un
   énoncé, jamais du code.
3. **Dans Calcul** — sur une cellule qui a donné un résultat (factorisation, primalité, pgcd, puissance modulaire,
   inverse, binomial…), menu ⋯ › **Certifier avec Lean** : Madalean crée un dossier avec l'énoncé et sa preuve.

## Limites

Pas encore : graphes comme témoins, intégrales et arithmétique d'intervalles générale, sommes de carrés au-delà de
4 variables ou du degré 8, structures abstraites (anneaux quelconques, sommes ∑, nombres complexes). Sans SageMath
installé, seules l'arithmétique, les puissances modulaires, les identités, les cas finis et les petits nombres
premiers fonctionnent.
`,text:`Certificats : Sage calcule, Lean vérifie Un certificat est un témoin facile à vérifier : un facteur, un inverse, une somme de carrés, un contre-exemple… Sage le cherche (cela peut être difficile), puis Lean le vérifie (c'est facile et sûr). Si le témoin est faux, Lean le refuse : un certificat ne peut jamais faire passer une erreur pour une preuve. Ce qui est couvert Famille Exemple d'énoncé Ce que Lean vérifie Primalité « 1 000 003 est premier » un certificat de Pratt Nombre composé « 2³² + 1 n'est pas premier » un facteur Arithmétique pgcd, ppcm, divisibilité, congruences, factorielles le calcul Puissance modulaire « 3^1000000 mod 7 = … » le calcul pas à pas Identité une égalité polynomiale ring Idéal « f est dans l'idéal engendré par g et h » les cofacteurs (base de Gröbner) Arithmétique linéaire un système d'inégalités sans solution la combinaison de Farkas Somme de carrés « x² + y² ≥ 2xy » l'écriture comme somme de carrés Existence « ∃ x, 17x ≡ 1 (mod 3120) » le témoin (x = 2753) Contre-exemple « n² + n + 41 est premier pour tout n » le contre-exemple (n = 40) Borne numérique « √2 < 1,415 », bornes sur π, e, log 2 l'encadrement Cas finis « pour tout n ≤ 20, … » l'énumération Lean vérifie tout dans son noyau, sans passer par du code compilé (nativedecide n'est jamais utilisé). Où les trouver 1. Dans une preuve — la stratégie « certificat » se lance seule, à côté de la recherche dans Mathlib, quand l'énoncé a une forme reconnue. Le fil du dossier affiche « témoin calculé par Sage, vérifié par Lean » avec le témoin. Elle se règle dans Réglages › Modèles › Certificats (activée par défaut). 2. Pour les modèles qui prouvent — ils peuvent demander un témoin à Sage pendant leur recherche. Ils envoient un énoncé, jamais du code. 3. Dans Calcul — sur une cellule qui a donné un résultat (factorisation, primalité, pgcd, puissance modulaire, inverse, binomial…), menu ⋯ › Certifier avec Lean : Madalean crée un dossier avec l'énoncé et sa preuve. Limites Pas encore : graphes comme témoins, intégrales et arithmétique d'intervalles générale, sommes de carrés au-delà de 4 variables ou du degré 8, structures abstraites (anneaux quelconques, sommes ∑, nombres complexes). Sans SageMath installé, seules l'arithmétique, les puissances modulaires, les identités, les cas finis et les petits nombres premiers fonctionnent.`},{id:`literature`,lang:`fr`,title:`Littérature d'abord : résultats publiés et pièces jointes`,order:208,section:`research`,audience:`researcher`,summary:`Pendant la preuve, Madalean cherche les résultats publiés liés à l'énoncé, les cite mot pour mot et les énonce en Lean ; un résultat cité mais non prouvé en Lean ne rend jamais une preuve « vérifiée ».`,source:`fr/literature.md`,site_path:`fr/literature.html`,headings:[{level:1,text:`Littérature d'abord : résultats publiés et pièces jointes`,id:`litterature-dabord-resultats-publies-et-pieces-jointes`},{level:2,text:`Ce que vous voyez`,id:`ce-que-vous-voyez`},{level:2,text:`Preuve conditionnelle`,id:`preuve-conditionnelle`},{level:2,text:`Pièces jointes`,id:`pieces-jointes`},{level:2,text:`Réglages et confidentialité`,id:`reglages-et-confidentialite`}],images:[],verify:[],body:`# Littérature d'abord : résultats publiés et pièces jointes

Quand la preuve d'un énoncé commence, Madalean cherche en parallèle, dans les bases savantes, les résultats publiés
qui s'y rapportent : **zbMATH Open** (littérature relue, avec ses recensions), **OpenAlex**, **arXiv**, et vos
**Sources**. La recherche ne retarde jamais la preuve.

## Ce que vous voyez

Dans l'étape **Preuve**, le panneau **Littérature** :

- chaque **référence** vient d'une base savante (jamais d'un modèle) ; un badge dit si elle est **publiée dans une
  revue (relue par des pairs)** ou une **prépublication (non relue)** ;
- l'**énoncé cité mot pour mot**, avec sa place (« résumé, phrase 2 », « recension zbMATH », « Theorem 2.1, p. 5 ») ;
- son **énoncé en Lean** quand un modèle a pu le traduire (à relire) et son état : **Dans Mathlib**, **Prouvé en
  Lean**, **À prouver (conditionnel)** ou **Pas d'énoncé Lean** ;
- les boutons **Ajouter aux Sources**, **Ajouter à la bibliographie de l'article**, **Prouver ce lemme**, et la notice
  BibTeX.

Si rien de fiable n'est trouvé, c'est écrit tel quel : Madalean n'invente jamais une référence ni une citation.

## Preuve conditionnelle

Si un résultat cité permet de conclure mais n'est pas prouvé en Lean, Madalean l'indique : **« Preuve conditionnelle
— pas vérifiée »**, avec la référence dont elle dépend. Elle n'entre ni dans les preuves du dossier ni dans la
bibliothèque, et l'export l'écrit en toutes lettres. Cliquez sur **Prouver ce lemme** : dès que Lean accepte la preuve
du résultat cité, la preuve est revérifiée strictement et devient **vérifiée**.

## Pièces jointes

Le trombone du fil du dossier (et le panneau **Littérature**) joint une **image**, un **PDF**, un fichier **LaTeX**
ou **BibTeX**, ou une **adresse web**. La pièce jointe devient une Source du projet et n'est **lue qu'une seule fois** :
Madalean en garde un résumé (la référence, les énoncés cités mot pour mot, leur énoncé Lean). Joindre le même fichier
dans un autre dossier du projet ne le relit pas. Une image est lue par un modèle capable de lire les images (sinon elle
reste « non lue ») ; sa transcription est marquée comme telle, l'original reste dans les Sources. **Relire** relit la
pièce jointe si vous le demandez.

Dans le fil, vous pouvez écrire par exemple « d'après la pièce jointe 2, lemme 3.1, conclure » : Madalean cite ce
lemme tel qu'il est écrit dans la pièce jointe.

Dans **Calcul**, une cellule « Demande » a aussi son trombone : le fichier rejoint les Sources du projet (lu une seule
fois, comme ci-dessus) et la cellule affiche ses pièces jointes. Une demande comme « d'après la pièce jointe 1,
lemme 1, vérifier pour p = 7 » transmet au modèle la citation exacte (jamais le document entier) ; le code écrit
reste à approuver avant de s'exécuter.

## Réglages et confidentialité

**Réglages › Modèles › Options avancées** : « Chercher dans la littérature » (activé par défaut) et sa profondeur
(rapide ≈ 45 s, approfondie ≈ 2 min 30). En **mode local**, aucune recherche n'est envoyée sur le réseau : seules
vos Sources et Mathlib sont consultées. Ce qui quitte l'ordinateur : les mots de recherche tirés de l'énoncé et les
identifiants (DOI, arXiv) à vérifier ; jamais votre fichier Lean, vos notes, une clé ou votre nom.
`,text:`Littérature d'abord : résultats publiés et pièces jointes Quand la preuve d'un énoncé commence, Madalean cherche en parallèle, dans les bases savantes, les résultats publiés qui s'y rapportent : zbMATH Open (littérature relue, avec ses recensions), OpenAlex, arXiv, et vos Sources. La recherche ne retarde jamais la preuve. Ce que vous voyez Dans l'étape Preuve, le panneau Littérature : - chaque référence vient d'une base savante (jamais d'un modèle) ; un badge dit si elle est publiée dans une revue (relue par des pairs) ou une prépublication (non relue) ; - l'énoncé cité mot pour mot, avec sa place (« résumé, phrase 2 », « recension zbMATH », « Theorem 2.1, p. 5 ») ; - son énoncé en Lean quand un modèle a pu le traduire (à relire) et son état : Dans Mathlib, Prouvé en Lean, À prouver (conditionnel) ou Pas d'énoncé Lean ; - les boutons Ajouter aux Sources, Ajouter à la bibliographie de l'article, Prouver ce lemme, et la notice BibTeX. Si rien de fiable n'est trouvé, c'est écrit tel quel : Madalean n'invente jamais une référence ni une citation. Preuve conditionnelle Si un résultat cité permet de conclure mais n'est pas prouvé en Lean, Madalean l'indique : « Preuve conditionnelle — pas vérifiée », avec la référence dont elle dépend. Elle n'entre ni dans les preuves du dossier ni dans la bibliothèque, et l'export l'écrit en toutes lettres. Cliquez sur Prouver ce lemme : dès que Lean accepte la preuve du résultat cité, la preuve est revérifiée strictement et devient vérifiée. Pièces jointes Le trombone du fil du dossier (et le panneau Littérature) joint une image, un PDF, un fichier LaTeX ou BibTeX, ou une adresse web. La pièce jointe devient une Source du projet et n'est lue qu'une seule fois : Madalean en garde un résumé (la référence, les énoncés cités mot pour mot, leur énoncé Lean). Joindre le même fichier dans un autre dossier du projet ne le relit pas. Une image est lue par un modèle capable de lire les images (sinon elle reste « non lue ») ; sa transcription est marquée comme telle, l'original reste dans les Sources. Relire relit la pièce jointe si vous le demandez. Dans le fil, vous pouvez écrire par exemple « d'après la pièce jointe 2, lemme 3.1, conclure » : Madalean cite ce lemme tel qu'il est écrit dans la pièce jointe. Dans Calcul, une cellule « Demande » a aussi son trombone : le fichier rejoint les Sources du projet (lu une seule fois, comme ci-dessus) et la cellule affiche ses pièces jointes. Une demande comme « d'après la pièce jointe 1, lemme 1, vérifier pour p = 7 » transmet au modèle la citation exacte (jamais le document entier) ; le code écrit reste à approuver avant de s'exécuter. Réglages et confidentialité Réglages › Modèles › Options avancées : « Chercher dans la littérature » (activé par défaut) et sa profondeur (rapide ≈ 45 s, approfondie ≈ 2 min 30). En mode local, aucune recherche n'est envoyée sur le réseau : seules vos Sources et Mathlib sont consultées. Ce qui quitte l'ordinateur : les mots de recherche tirés de l'énoncé et les identifiants (DOI, arXiv) à vérifier ; jamais votre fichier Lean, vos notes, une clé ou votre nom.`},{id:`sources`,lang:`fr`,title:`Sources, recherche bibliographique et questions ancrées`,order:210,section:`research`,audience:`researcher`,summary:`La bibliothèque de sources (articles, livres), la recherche dans les bases, le lecteur annoté, et les réponses citant vos sources.`,source:`fr/sources.md`,site_path:`fr/sources.html`,headings:[{level:1,text:`Sources, recherche bibliographique et questions ancrées`,id:`sources-recherche-bibliographique-et-questions-ancrees`},{level:2,text:`La bibliothèque de sources`,id:`la-bibliotheque-de-sources`},{level:2,text:`Recherche bibliographique`,id:`recherche-bibliographique`},{level:2,text:`Lire et annoter`,id:`lire-et-annoter`},{level:2,text:`Questions ancrées dans vos sources`,id:`questions-ancrees-dans-vos-sources`},{level:2,text:`Ce qui part sur Internet`,id:`ce-qui-part-sur-internet`}],images:[],verify:[],body:`# Sources, recherche bibliographique et questions ancrées

## La bibliothèque de sources

L'écran « Sources » du projet a trois onglets : « Bibliothèque », « Recherche bibliographique » et « Poser une
question ». Articles, livres, notes de cours y sont rangés par **étagère** : une par projet, une étagère générale, et
l'étagère *Mathlib* (lecture seule, tirée de la bibliographie de Mathlib). Pour ajouter une source, « Ajouter »
propose trois façons : « Identifiant », « Fichier », « Coller ».

| Par | Ce que fait Madalean |
|---|---|
| « Identifiant » : DOI, identifiant arXiv, ISBN, \`Zbl …\`, identifiant OpenAlex | récupère les métadonnées vérifiées ; pour arXiv, aussi les sources TeX et le PDF ; pour un DOI, le PDF seulement s'il est en accès ouvert |
| « Identifiant » : adresse web | métadonnées de la page seulement |
| « Fichier » : PDF, source TeX (\`.tex\`, \`.tar.gz\`, \`.zip\`) | cherche un identifiant dans les premières pages ; sinon métadonnées devinées, marquées **non vérifiées** |
| « Fichier » ou « Coller » : BibTeX, RIS, CSL-JSON, export Zotero (RDF, ou \`.zip\` avec les fichiers joints) | importe les références et les fichiers joints de l'archive |

Les doublons (même DOI, même arXiv, même titre) sont signalés. Chaque source a des étiquettes, un état de lecture,
des annotations, et sa clé BibTeX. Le bouton « BibTeX » exporte l'étagère.

Les métadonnées devinées à partir d'un fichier restent marquées « métadonnées à vérifier » tant que vous ne les avez
pas confirmées (« Elles sont justes » dans le lecteur).

## Recherche bibliographique

L'onglet « Recherche bibliographique » interroge arXiv, zbMATH Open, Crossref, OpenAlex et Semantic Scholar et
fusionne les résultats. **Seule votre requête est envoyée.** Un service qui ne répond pas est marqué
« indisponible », sans bloquer les autres. « Ajouter » range un résultat dans vos sources.

En mode *Local*, ces recherches sont refusées : elles demandent le réseau.

## Lire et annoter

Le lecteur affiche le PDF à côté du texte extrait. « Surligner » un passage, ajouter une « Note en marge » : les
annotations sont ancrées à la page et à la position, et retrouvables dans la recherche.

Le texte intégral de chaque source est indexé **localement**, découpé en passages avec leur page et leur section.
Pour un PDF sans couche texte (scan), une reconnaissance de caractères existe, mais les formules lues ainsi ne sont
pas fiables.

## Questions ancrées dans vos sources

Posez une question (onglet « Poser une question », ou « Questions sur ce texte » dans le lecteur) : la réponse cite
des **passages** précis.

- Chaque citation renvoie au passage (clic : la page s'ouvre au bon endroit).
- La citation est vérifiée par le code : le passage cité doit contenir le texte cité. Une phrase sans citation
  valide est affichée barrée ou grisée.
- Si aucun passage pertinent n'est trouvé, la réponse le dit, **sans appeler de modèle**.
- Une partie « connaissances générales », facultative (« Compléter avec des connaissances générales »), est séparée
  et marquée comme telle, sans citation.

Ce que la vérification garantit : le passage cité existe et contient la citation. Ce qu'elle ne garantit pas : que le
passage *justifie* la phrase. Lisez le passage pour les points importants.

Autres demandes : « Résumer » (ce que prouve l'article, ses définitions, ses dépendances) et « Comparer » plusieurs
sources (« Comparer avec… » dans le lecteur).

## Ce qui part sur Internet

Les requêtes de recherche, les identifiants (DOI, arXiv…) et le téléchargement des fichiers en accès ouvert. Les
questions sur vos sources passent par le modèle choisi, avec les passages retenus : en mode *Local*, uniquement par
un modèle local. Voir [Modèles et clés](models-keys.md#ce-qui-part-et-vers-qui).
`,text:`Sources, recherche bibliographique et questions ancrées La bibliothèque de sources L'écran « Sources » du projet a trois onglets : « Bibliothèque », « Recherche bibliographique » et « Poser une question ». Articles, livres, notes de cours y sont rangés par étagère : une par projet, une étagère générale, et l'étagère Mathlib (lecture seule, tirée de la bibliographie de Mathlib). Pour ajouter une source, « Ajouter » propose trois façons : « Identifiant », « Fichier », « Coller ». Par Ce que fait Madalean « Identifiant » : DOI, identifiant arXiv, ISBN, Zbl …, identifiant OpenAlex récupère les métadonnées vérifiées ; pour arXiv, aussi les sources TeX et le PDF ; pour un DOI, le PDF seulement s'il est en accès ouvert « Identifiant » : adresse web métadonnées de la page seulement « Fichier » : PDF, source TeX (.tex, .tar.gz, .zip) cherche un identifiant dans les premières pages ; sinon métadonnées devinées, marquées non vérifiées « Fichier » ou « Coller » : BibTeX, RIS, CSL-JSON, export Zotero (RDF, ou .zip avec les fichiers joints) importe les références et les fichiers joints de l'archive Les doublons (même DOI, même arXiv, même titre) sont signalés. Chaque source a des étiquettes, un état de lecture, des annotations, et sa clé BibTeX. Le bouton « BibTeX » exporte l'étagère. Les métadonnées devinées à partir d'un fichier restent marquées « métadonnées à vérifier » tant que vous ne les avez pas confirmées (« Elles sont justes » dans le lecteur). Recherche bibliographique L'onglet « Recherche bibliographique » interroge arXiv, zbMATH Open, Crossref, OpenAlex et Semantic Scholar et fusionne les résultats. Seule votre requête est envoyée. Un service qui ne répond pas est marqué « indisponible », sans bloquer les autres. « Ajouter » range un résultat dans vos sources. En mode Local, ces recherches sont refusées : elles demandent le réseau. Lire et annoter Le lecteur affiche le PDF à côté du texte extrait. « Surligner » un passage, ajouter une « Note en marge » : les annotations sont ancrées à la page et à la position, et retrouvables dans la recherche. Le texte intégral de chaque source est indexé localement, découpé en passages avec leur page et leur section. Pour un PDF sans couche texte (scan), une reconnaissance de caractères existe, mais les formules lues ainsi ne sont pas fiables. Questions ancrées dans vos sources Posez une question (onglet « Poser une question », ou « Questions sur ce texte » dans le lecteur) : la réponse cite des passages précis. - Chaque citation renvoie au passage (clic : la page s'ouvre au bon endroit). - La citation est vérifiée par le code : le passage cité doit contenir le texte cité. Une phrase sans citation valide est affichée barrée ou grisée. - Si aucun passage pertinent n'est trouvé, la réponse le dit, sans appeler de modèle. - Une partie « connaissances générales », facultative (« Compléter avec des connaissances générales »), est séparée et marquée comme telle, sans citation. Ce que la vérification garantit : le passage cité existe et contient la citation. Ce qu'elle ne garantit pas : que le passage justifie la phrase. Lisez le passage pour les points importants. Autres demandes : « Résumer » (ce que prouve l'article, ses définitions, ses dépendances) et « Comparer » plusieurs sources (« Comparer avec… » dans le lecteur). Ce qui part sur Internet Les requêtes de recherche, les identifiants (DOI, arXiv…) et le téléchargement des fichiers en accès ouvert. Les questions sur vos sources passent par le modèle choisi, avec les passages retenus : en mode Local, uniquement par un modèle local. Voir Modèles et clés.`},{id:`articles`,lang:`fr`,title:`Bibliographie, article et blueprint`,order:220,section:`research`,audience:`researcher`,summary:`Citer dans les preuves, rédiger un article à partir d'un projet, transformer un article en blueprint de dossiers Lean, et ce qui est fiable.`,source:`fr/articles.md`,site_path:`fr/articles.html`,headings:[{level:1,text:`Bibliographie, article et blueprint`,id:`bibliographie-article-et-blueprint`},{level:2,text:`Ce qui est fiable, et ce qui ne l'est pas`,id:`ce-qui-est-fiable-et-ce-qui-ne-lest-pas`},{level:2,text:`Citer`,id:`citer`},{level:2,text:`Rédiger l'article`,id:`rediger-larticle`},{level:2,text:`D'un article à un blueprint`,id:`dun-article-a-un-blueprint`},{level:2,text:`Du blueprint au plan formel`,id:`du-blueprint-au-plan-formel`},{level:2,text:`Publier`,id:`publier`}],images:[],verify:[],body:`# Bibliographie, article et blueprint

## Ce qui est fiable, et ce qui ne l'est pas

| Fonction | Fiabilité | Comment |
|---|---|---|
| Bibliographie dans les preuves et les exports | Élevée | Un fichier BibTeX par projet. Ajout par DOI, arXiv, zbMATH, BibTeX collé, ou depuis la bibliographie de Mathlib. Un modèle ne peut citer que des clés existantes : une référence inventée est retirée par le code, jamais imprimée. |
| Lean → article | Élevée pour la structure, dépend du modèle pour la prose | Projet → article LaTeX (amsart) : résumé, sections, chaque dossier en théorème + preuve rédigée, annexe Lean facultative, bibliographie, tableau de vérification. Un énoncé non prouvé est composé comme conjecture ou affirmation, marqué — jamais comme théorème. |
| Article → énoncés structurés | Élevée depuis les sources LaTeX (arXiv), moyenne depuis un PDF | Sources arXiv d'abord ; PDF par sa couche texte, et un modèle qui lit les PDF quand une clé le permet ; les formules d'un PDF scanné ne sont pas fiables sans relecture. Résultat : un **blueprint**, un dossier par définition, lemme ou théorème, avec le texte d'origine, sa place dans l'article et ses dépendances. |
| Article → énoncés Lean | Moyenne (niveau manuel, master), faible (recherche avec des objets absents de Mathlib) | Chaque nœud passe par compréhension → traduction avec recherche de lemmes ; les définitions manquantes sont détectées et deviennent des nœuds « à définir ». Toujours relu par vous : le texte de l'article est affiché à côté de l'énoncé Lean. |
| Article → preuves Lean | Faible à moyenne | La preuve de l'article est donnée au prouveur comme indice. Les lemmes élémentaires sont souvent prouvés, les résultats profonds rarement. Le graphe montre honnêtement ce qui est prouvé, seulement énoncé, ou bloqué. |

**Aucun résultat n'est présenté comme vérifié si Lean n'a pas accepté sa preuve et celles de toutes ses
dépendances.**

## Citer

Dans tout texte (énoncé, preuve rédigée, explication, note, section d'article), une citation s'écrit avec la clé
BibTeX : \`[@hardy-wright]\`, \`[@hardy-wright, Thm 2.1]\`, \`[voir @a, p. 3; @b]\`. L'autocomplétion propose les clés du
projet. Les exports n'impriment que les références citées : PDF avec biblatex et biber s'ils sont installés, sinon
BibTeX ; le \`.zip\` contient \`refs.bib\`.

## Rédiger l'article

L'écran « Article » du projet est un éditeur LaTeX visuel : le texte affiché *est* la source LaTeX (formules
rendues, encadrés de théorèmes, citations, figures), et « Source LaTeX » montre le même texte brut. À la première
ouverture, Madalean prépare l'article à partir du projet : introduction et un bloc par dossier. Le plan est à
gauche, l'« Aperçu PDF » à droite sur un grand écran ; « Compiler » produit le PDF. L'assistant (« Réécrire »,
« Raccourcir », « Formaliser »…) ne fait que des suggestions, que vous acceptez ou refusez dans le texte.

À la compilation, Madalean ajoute la bibliographie (seulement les références citées), la **table de vérification
Lean** (pour chaque résultat : nom Lean, vérifié ou non, versions de Lean et de Mathlib, axiomes) et, si vous le
demandez dans « Options avancées », une annexe avec le code Lean. Un théorème lié à un dossier dont la preuve n'est
pas vérifiée par Lean est imprimé comme affirmation, jamais comme théorème.

Sous « Plus d'actions » : « Versions » (une version automatique au plus toutes les 2 minutes d'écriture, et les
vôtres), « Télécharger le PDF », et « Overleaf… » pour envoyer le projet vers Overleaf (ou télécharger le projet en
\`.zip\`) puis le reprendre.

## D'un article à un blueprint

1. Ajoutez l'article à vos sources (de préférence par son identifiant arXiv : les sources LaTeX donnent un bien
   meilleur résultat que le PDF).
2. Dans le lecteur de la source, « Extraire le blueprint » : définitions, lemmes, théorèmes, avec leur numéro (« Lemme 2.3 »), leur texte, leur
   preuve, et les dépendances repérées dans les preuves (\`\\ref\`, « par le lemme 2.3 »).
3. Les dépendances écrites en prose (« par le lemme précédent ») échappent souvent à l'extraction : une passe de
   modèle facultative propose des liens marqués **« proposé (à confirmer) »**, que vous confirmez (« Confirmer ») ou
   écartez (« Écarter »).
4. « Créer les dossiers » : chaque nœud devient un dossier relié à la source et à son emplacement dans l'article.
5. L'écran « Blueprint » colore chaque résultat selon son état : pas de dossier, énoncé en mots, énoncé Lean
   accepté, défini, prouvé (dépendances non vérifiées), vérifié (prouvé et toutes ses dépendances vérifiées),
   bloqué (utilise une définition sans énoncé Lean accepté), échec. « Ouvrir le dossier » ouvre le dossier.

Mesure honnête (trois articles arXiv courts, vérifiés à la main) : énoncés trouvés 12 sur 12 depuis le TeX comme
depuis le PDF ; preuves 10 sur 11 depuis le TeX, 8 sur 11 depuis le PDF ; dépendances écrites en prose : 2 sur 7
sans passe de modèle. Ces chiffres viennent d'un petit échantillon.

## Du blueprint au plan formel

L'onglet « Plan formel » de l'écran « Blueprint » transforme l'article en plan de travail Lean, pas à pas :

1. Cochez les théorèmes voulus (le résultat principal, par exemple). Le bouton indique combien d'énoncés compte leur
   **fermeture par dépendances** : tout ce qu'ils utilisent d'après les références explicites de l'article
   (\`\\ref\`, « Proof of Theorem 3 », « par le lemme 2.3 » dans un PDF), et les liens proposés par un modèle seulement
   une fois que vous les avez confirmés. Une dépendance inconnue reste inconnue : rien n'est inventé.
2. « Formaliser la sélection et ses dépendances » : dépendances d'abord, chaque énoncé **cité mot pour mot** depuis
   l'article (avec les définitions qu'il utilise) part au traducteur ; Lean vérifie l'énoncé ; puis Madalean regarde
   si Mathlib (ou votre bibliothèque) le prouve déjà. Une passe s'arrête après le nombre d'énoncés choisi
   (« Énoncés par passe ») ou quand vous cliquez « Arrêter » ; relancez-la pour **reprendre** là où elle s'est
   arrêtée.
3. Quand toute la fermeture est traitée, Madalean ouvre un dossier pour le théorème principal et, dans son graphe du
   problème, un nœud par résultat utilisé : ceux de Mathlib sont vérifiés, les autres sont **conditionnels**
   (l'article les affirme, Lean ne les a pas prouvés) et chacun de ceux à prouver devient un **sous-dossier**. Rien
   n'est lancé : vous lancez les prouveurs depuis les dossiers.

Chaque résultat a un état : *prouvé (Lean)*, *dans Mathlib*, *à prouver*, *énoncé formalisé*, *non formalisé* ;
« Conditionnel : repose sur … » liste ce qui n'est pas encore prouvé. Le compteur donne les résultats du plan prouvés
ou dans Mathlib. Un clic sur un résultat montre son texte dans l'article (mot pour mot, avec sa place : numéro,
section, ligne ou page) à côté de l'énoncé Lean — une traduction par un modèle, acceptée par Lean, à relire.
« Exporter (LaTeX) » écrit un blueprint au format de \`leanblueprint\` (\`\\lean\`, \`\\leanok\`, \`\\mathlibok\`, \`\\uses\`),
« Exporter (HTML) » une page de synthèse. Les définitions ne sont pas encore formalisées.

## Publier

Un projet peut être publié sous forme de site statique vérifiable par tous : voir [Publier un projet](publish.md).
`,text:`Bibliographie, article et blueprint Ce qui est fiable, et ce qui ne l'est pas Fonction Fiabilité Comment Bibliographie dans les preuves et les exports Élevée Un fichier BibTeX par projet. Ajout par DOI, arXiv, zbMATH, BibTeX collé, ou depuis la bibliographie de Mathlib. Un modèle ne peut citer que des clés existantes : une référence inventée est retirée par le code, jamais imprimée. Lean → article Élevée pour la structure, dépend du modèle pour la prose Projet → article LaTeX (amsart) : résumé, sections, chaque dossier en théorème + preuve rédigée, annexe Lean facultative, bibliographie, tableau de vérification. Un énoncé non prouvé est composé comme conjecture ou affirmation, marqué — jamais comme théorème. Article → énoncés structurés Élevée depuis les sources LaTeX (arXiv), moyenne depuis un PDF Sources arXiv d'abord ; PDF par sa couche texte, et un modèle qui lit les PDF quand une clé le permet ; les formules d'un PDF scanné ne sont pas fiables sans relecture. Résultat : un blueprint, un dossier par définition, lemme ou théorème, avec le texte d'origine, sa place dans l'article et ses dépendances. Article → énoncés Lean Moyenne (niveau manuel, master), faible (recherche avec des objets absents de Mathlib) Chaque nœud passe par compréhension → traduction avec recherche de lemmes ; les définitions manquantes sont détectées et deviennent des nœuds « à définir ». Toujours relu par vous : le texte de l'article est affiché à côté de l'énoncé Lean. Article → preuves Lean Faible à moyenne La preuve de l'article est donnée au prouveur comme indice. Les lemmes élémentaires sont souvent prouvés, les résultats profonds rarement. Le graphe montre honnêtement ce qui est prouvé, seulement énoncé, ou bloqué. Aucun résultat n'est présenté comme vérifié si Lean n'a pas accepté sa preuve et celles de toutes ses dépendances. Citer Dans tout texte (énoncé, preuve rédigée, explication, note, section d'article), une citation s'écrit avec la clé BibTeX : [@hardy-wright], [@hardy-wright, Thm 2.1], [voir @a, p. 3; @b]. L'autocomplétion propose les clés du projet. Les exports n'impriment que les références citées : PDF avec biblatex et biber s'ils sont installés, sinon BibTeX ; le .zip contient refs.bib. Rédiger l'article L'écran « Article » du projet est un éditeur LaTeX visuel : le texte affiché est la source LaTeX (formules rendues, encadrés de théorèmes, citations, figures), et « Source LaTeX » montre le même texte brut. À la première ouverture, Madalean prépare l'article à partir du projet : introduction et un bloc par dossier. Le plan est à gauche, l'« Aperçu PDF » à droite sur un grand écran ; « Compiler » produit le PDF. L'assistant (« Réécrire », « Raccourcir », « Formaliser »…) ne fait que des suggestions, que vous acceptez ou refusez dans le texte. À la compilation, Madalean ajoute la bibliographie (seulement les références citées), la table de vérification Lean (pour chaque résultat : nom Lean, vérifié ou non, versions de Lean et de Mathlib, axiomes) et, si vous le demandez dans « Options avancées », une annexe avec le code Lean. Un théorème lié à un dossier dont la preuve n'est pas vérifiée par Lean est imprimé comme affirmation, jamais comme théorème. Sous « Plus d'actions » : « Versions » (une version automatique au plus toutes les 2 minutes d'écriture, et les vôtres), « Télécharger le PDF », et « Overleaf… » pour envoyer le projet vers Overleaf (ou télécharger le projet en .zip) puis le reprendre. D'un article à un blueprint 1. Ajoutez l'article à vos sources (de préférence par son identifiant arXiv : les sources LaTeX donnent un bien meilleur résultat que le PDF). 2. Dans le lecteur de la source, « Extraire le blueprint » : définitions, lemmes, théorèmes, avec leur numéro (« Lemme 2.3 »), leur texte, leur preuve, et les dépendances repérées dans les preuves (\\ref, « par le lemme 2.3 »). 3. Les dépendances écrites en prose (« par le lemme précédent ») échappent souvent à l'extraction : une passe de modèle facultative propose des liens marqués « proposé (à confirmer) », que vous confirmez (« Confirmer ») ou écartez (« Écarter »). 4. « Créer les dossiers » : chaque nœud devient un dossier relié à la source et à son emplacement dans l'article. 5. L'écran « Blueprint » colore chaque résultat selon son état : pas de dossier, énoncé en mots, énoncé Lean accepté, défini, prouvé (dépendances non vérifiées), vérifié (prouvé et toutes ses dépendances vérifiées), bloqué (utilise une définition sans énoncé Lean accepté), échec. « Ouvrir le dossier » ouvre le dossier. Mesure honnête (trois articles arXiv courts, vérifiés à la main) : énoncés trouvés 12 sur 12 depuis le TeX comme depuis le PDF ; preuves 10 sur 11 depuis le TeX, 8 sur 11 depuis le PDF ; dépendances écrites en prose : 2 sur 7 sans passe de modèle. Ces chiffres viennent d'un petit échantillon. Du blueprint au plan formel L'onglet « Plan formel » de l'écran « Blueprint » transforme l'article en plan de travail Lean, pas à pas : 1. Cochez les théorèmes voulus (le résultat principal, par exemple). Le bouton indique combien d'énoncés compte leur fermeture par dépendances : tout ce qu'ils utilisent d'après les références explicites de l'article (\\ref, « Proof of Theorem 3 », « par le lemme 2.3 » dans un PDF), et les liens proposés par un modèle seulement une fois que vous les avez confirmés. Une dépendance inconnue reste inconnue : rien n'est inventé. 2. « Formaliser la sélection et ses dépendances » : dépendances d'abord, chaque énoncé cité mot pour mot depuis l'article (avec les définitions qu'il utilise) part au traducteur ; Lean vérifie l'énoncé ; puis Madalean regarde si Mathlib (ou votre bibliothèque) le prouve déjà. Une passe s'arrête après le nombre d'énoncés choisi (« Énoncés par passe ») ou quand vous cliquez « Arrêter » ; relancez-la pour reprendre là où elle s'est arrêtée. 3. Quand toute la fermeture est traitée, Madalean ouvre un dossier pour le théorème principal et, dans son graphe du problème, un nœud par résultat utilisé : ceux de Mathlib sont vérifiés, les autres sont conditionnels (l'article les affirme, Lean ne les a pas prouvés) et chacun de ceux à prouver devient un sous-dossier. Rien n'est lancé : vous lancez les prouveurs depuis les dossiers. Chaque résultat a un état : prouvé (Lean), dans Mathlib, à prouver, énoncé formalisé, non formalisé ; « Conditionnel : repose sur … » liste ce qui n'est pas encore prouvé. Le compteur donne les résultats du plan prouvés ou dans Mathlib. Un clic sur un résultat montre son texte dans l'article (mot pour mot, avec sa place : numéro, section, ligne ou page) à côté de l'énoncé Lean — une traduction par un modèle, acceptée par Lean, à relire. « Exporter (LaTeX) » écrit un blueprint au format de leanblueprint (\\lean, \\leanok, \\mathlibok, \\uses), « Exporter (HTML) » une page de synthèse. Les définitions ne sont pas encore formalisées. Publier Un projet peut être publié sous forme de site statique vérifiable par tous : voir Publier un projet.`},{id:`notes`,lang:`fr`,title:`Notes`,order:230,section:`research`,audience:`all`,summary:`Notes liées en Markdown, LaTeX et Lean ; liens, rétroliens, graphe, versions et édition sur plusieurs appareils.`,source:`fr/notes.md`,site_path:`fr/notes.html`,headings:[{level:1,text:`Notes`,id:`notes`},{level:2,text:`Liens`,id:`liens`},{level:2,text:`Lean dans les notes`,id:`lean-dans-les-notes`},{level:2,text:`Journal de recherche`,id:`journal-de-recherche`},{level:2,text:`Versions et plusieurs appareils`,id:`versions-et-plusieurs-appareils`},{level:2,text:`Export`,id:`export`}],images:[],verify:[],body:`# Notes

Les notes sont propres à Madalean (ce n'est pas un coffre Obsidian) et rangées par projet. On y écrit en Markdown,
avec des formules \`$…$\` et \`$$…$$\` et des blocs de code Lean.

## Liens

| Écriture | Cible |
|---|---|
| \`[[Titre]]\`, \`[[Titre\\|texte affiché]]\` | une note du même projet (titre sans distinction de casse) |
| \`[[dossier:Titre]]\` ou \`[[dossier:ID]]\` | un dossier (théorème, conjecture, lemme…) |
| \`[[@clé]]\`, \`[[@clé#p12]]\` | une source, éventuellement à une page |
| \`[[passage:ID]]\` | un passage précis d'une source |
| \`[[lib:Nom]]\` | un résultat de la bibliothèque (nom Lean) |

Chaque note montre ses **liens entrants** (les notes qui pointent vers elle). Le **graphe** du projet (bouton
« Graphe ») relie notes, dossiers et sources ; il se filtre par étiquette. Les étiquettes s'écrivent \`#étiquette\` dans le texte.

Renommer une note met à jour les liens \`[[Ancien titre]]\` des autres notes du projet.

## Lean dans les notes

Sous l'éditeur, la partie « Blocs Lean » liste chaque bloc \`lean\` de la note. « Tout vérifier avec Lean » les
compile tous dans l'espace du projet (« Vérifier avec Lean » sur un bloc ne vérifie que celui-là) ; chaque bloc
affiche « Lean accepte » ou « Lean refuse », avec les erreurs à la bonne ligne. « En faire un dossier » ouvre un
dossier avec l'énoncé du bloc et ajoute un lien vers lui sous le bloc.

## Journal de recherche

« Note du jour » crée (ou ouvre) la note « Journal de recherche » datée du jour, avec la liste des dossiers
travaillés ce jour-là.

## Versions et plusieurs appareils

Chaque enregistrement crée une révision ; toutes sont gardées. On peut comparer deux révisions et restaurer une
ancienne (ce qui crée une nouvelle révision : rien n'est perdu). Une note supprimée va à la corbeille.

Si la même note est modifiée sur deux appareils, les changements de lignes différentes sont fusionnés
automatiquement. Si les deux appareils ont modifié les mêmes lignes, Madalean montre les deux versions de chaque
passage en conflit et vous choisissez.

## Export

Le bouton « .md » de l'éditeur télécharge la note en Markdown.
`,text:`Notes Les notes sont propres à Madalean (ce n'est pas un coffre Obsidian) et rangées par projet. On y écrit en Markdown, avec des formules $…$ et $$…$$ et des blocs de code Lean. Liens Écriture Cible [[Titre]], [[Titre texte affiché]] une note du même projet (titre sans distinction de casse) [[dossier:Titre]] ou [[dossier:ID]] un dossier (théorème, conjecture, lemme…) [[@clé]], [[@clé#p12]] une source, éventuellement à une page [[passage:ID]] un passage précis d'une source [[lib:Nom]] un résultat de la bibliothèque (nom Lean) Chaque note montre ses liens entrants (les notes qui pointent vers elle). Le graphe du projet (bouton « Graphe ») relie notes, dossiers et sources ; il se filtre par étiquette. Les étiquettes s'écrivent #étiquette dans le texte. Renommer une note met à jour les liens [[Ancien titre]] des autres notes du projet. Lean dans les notes Sous l'éditeur, la partie « Blocs Lean » liste chaque bloc lean de la note. « Tout vérifier avec Lean » les compile tous dans l'espace du projet (« Vérifier avec Lean » sur un bloc ne vérifie que celui-là) ; chaque bloc affiche « Lean accepte » ou « Lean refuse », avec les erreurs à la bonne ligne. « En faire un dossier » ouvre un dossier avec l'énoncé du bloc et ajoute un lien vers lui sous le bloc. Journal de recherche « Note du jour » crée (ou ouvre) la note « Journal de recherche » datée du jour, avec la liste des dossiers travaillés ce jour-là. Versions et plusieurs appareils Chaque enregistrement crée une révision ; toutes sont gardées. On peut comparer deux révisions et restaurer une ancienne (ce qui crée une nouvelle révision : rien n'est perdu). Une note supprimée va à la corbeille. Si la même note est modifiée sur deux appareils, les changements de lignes différentes sont fusionnés automatiquement. Si les deux appareils ont modifié les mêmes lignes, Madalean montre les deux versions de chaque passage en conflit et vous choisissez. Export Le bouton « .md » de l'éditeur télécharge la note en Markdown.`},{id:`jupyter`,lang:`fr`,title:`Jupyter et Sage`,order:240,section:`research`,audience:`researcher`,summary:`JupyterLab intégré avec les noyaux Python et SageMath, l'assistant à côté du carnet, et qui peut y accéder.`,source:`fr/jupyter.md`,site_path:`fr/jupyter.html`,headings:[{level:1,text:`Jupyter et Sage`,id:`jupyter-et-sage`},{level:2,text:`Noyaux`,id:`noyaux`},{level:2,text:`L'assistant à côté du carnet`,id:`lassistant-a-cote-du-carnet`},{level:2,text:`Qui peut y accéder`,id:`qui-peut-y-acceder`}],images:[],verify:[],body:`# Jupyter et Sage

L'écran « Carnet » ouvre **JupyterLab**, démarré à la demande par l'ordinateur hôte, derrière la même connexion que
le reste de Madalean. Les carnets sont rangés dans \`~/Documents/Madalean/notebooks/\`.

## Noyaux

| Noyau | Disponible si |
|---|---|
| Python 3 | toujours (avec JupyterLab) |
| SageMath | la copie de Madalean est installée, ou le SageMath du système est compatible |
| Lean 4 | non fourni : aucun noyau Lean 4 n'est assez fiable aujourd'hui. Utilisez les dossiers ou les blocs \`lean\` des [notes](notes.md). |

Madalean installe sa propre copie de SageMath à la demande, ou réutilise celui de votre système s'il est compatible :
voir [Ce qu'installe Madalean › SageMath](components.md#sagemath).

## L'assistant à côté du carnet

Le panneau d'assistant lit le carnet ouvert (cellules et sorties) et peut **ajouter une cellule** à la fin, que vous
exécutez vous-même. Il répond avec le modèle du mode courant ; en mode *Local*, uniquement un modèle local.

## Qui peut y accéder

Un noyau Jupyter exécute n'importe quel code sur l'ordinateur hôte. Pour cette raison :

- sur l'hôte, le carnet est toujours disponible ;
- depuis un appareil relié, il n'est accessible que si l'hôte l'a autorisé (« Réglages › Carnet et accès »), réglage
  modifiable **seulement depuis l'hôte** ;
- le jeton interne de Jupyter ne quitte jamais le serveur.

Les expériences de l'[atelier de conjectures](conjectures.md) utilisent des noyaux confinés distincts, et ne
s'exécutent qu'après votre accord.
`,text:`Jupyter et Sage L'écran « Carnet » ouvre JupyterLab, démarré à la demande par l'ordinateur hôte, derrière la même connexion que le reste de Madalean. Les carnets sont rangés dans ~/Documents/Madalean/notebooks/. Noyaux Noyau Disponible si Python 3 toujours (avec JupyterLab) SageMath la copie de Madalean est installée, ou le SageMath du système est compatible Lean 4 non fourni : aucun noyau Lean 4 n'est assez fiable aujourd'hui. Utilisez les dossiers ou les blocs lean des notes. Madalean installe sa propre copie de SageMath à la demande, ou réutilise celui de votre système s'il est compatible : voir Ce qu'installe Madalean › SageMath. L'assistant à côté du carnet Le panneau d'assistant lit le carnet ouvert (cellules et sorties) et peut ajouter une cellule à la fin, que vous exécutez vous-même. Il répond avec le modèle du mode courant ; en mode Local, uniquement un modèle local. Qui peut y accéder Un noyau Jupyter exécute n'importe quel code sur l'ordinateur hôte. Pour cette raison : - sur l'hôte, le carnet est toujours disponible ; - depuis un appareil relié, il n'est accessible que si l'hôte l'a autorisé (« Réglages › Carnet et accès »), réglage modifiable seulement depuis l'hôte ; - le jeton interne de Jupyter ne quitte jamais le serveur. Les expériences de l'atelier de conjectures utilisent des noyaux confinés distincts, et ne s'exécutent qu'après votre accord.`},{id:`publish`,lang:`fr`,title:`Publier un projet`,order:250,section:`research`,audience:`researcher`,summary:`Publier un projet vérifié en site statique sur un dépôt GitHub de votre choix, revérifié indépendamment par lake build.`,source:`fr/publish.md`,site_path:`fr/publish.html`,headings:[{level:1,text:`Publier un projet`,id:`publier-un-projet`},{level:2,text:`Ce qui part, et seulement avec votre accord`,id:`ce-qui-part-et-seulement-avec-votre-accord`},{level:2,text:`Ce que montre le site`,id:`ce-que-montre-le-site`}],images:[],verify:[],body:`# Publier un projet

L'écran « Publier » (menu du projet) transforme un projet en **site statique** que n'importe qui peut lire et
revérifier :

- l'article (HTML, et le PDF si vous le joignez) ;
- le **graphe des dépendances**, avec l'état de chaque résultat ;
- une page par résultat : énoncé en langage naturel, code Lean coloré, preuve rédigée, informations de vérification
  (version de Lean, révision de Mathlib, axiomes) ;
- la table de vérification et la bibliographie ;
- le **projet Lean (Lake)** complet à télécharger, et, si vous le demandez, vos calculs (Calcul).

Un résultat publié emmène avec lui tout ce dont il dépend : un résultat n'est jamais montré sans ce sur quoi il
s'appuie.

Le site est envoyé sur un dépôt GitHub **que vous choisissez**, avec une action GitHub qui relance \`lake build\` sur
le projet Lean publié. Le badge de vérification affiché par le site vient de cette action, indépendante de votre
ordinateur : un lecteur n'a pas à croire Madalean sur parole.

## Ce qui part, et seulement avec votre accord

1. **« Ce que vous publiez »** : cochez les résultats, les notes (aucune par défaut), « Joindre le PDF de
   l'article », « Joindre les calculs (Calcul) », et choisissez la licence du site.
2. **« Préparer la liste exacte »** : rien n'est envoyé à cette étape. L'écran liste **exactement** ce qui quittera
   l'ordinateur (« Ce qui quittera cet ordinateur ») : chaque fichier, son type, son origine et sa taille, ce qui est
   écarté, et ce qui n'est jamais publié (vos clés, vos notes privées, les PDF des articles d'autres auteurs, vos
   réglages).
3. **« Aperçu local »** construit le site sur l'ordinateur ; « Ouvrir l'aperçu » le montre avant toute publication.
4. **« Envoyer sur GitHub »** : indiquez le dépôt (\`compte/nom\`), cochez au besoin « Créer le dépôt s'il n'existe
   pas » (et « Dépôt privé »), puis « Publier » et confirmez par « Oui, publier ». Il faut une clé GitHub (jeton),
   enregistrée dans les réglages des clés (l'écran y mène par un lien) ; à défaut, la connexion de l'outil \`gh\`,
   s'il est installé sur l'hôte, est utilisée. Madalean active ensuite le site GitHub Pages du dépôt ; s'il n'y
   arrive pas, il donne le lien pour l'activer à la main.

La publication se lance depuis l'ordinateur hôte. Si la liste change entre sa préparation et l'envoi, Madalean
demande de la préparer de nouveau. Une nouvelle publication ajoute un commit au dépôt ; rien n'est envoyé si rien
n'a changé.

## Ce que montre le site

Chaque état a une couleur, une forme de bordure et un libellé écrit (jamais la couleur seule) :

| Marque | Libellé sur le site |
|---|---|
| ✓ | vérifié par Lean (preuve acceptée par Lean, et toutes ses dépendances vérifiées) |
| (✓) | prouvé, dépendances non vérifiées |
| ≔ | définition acceptée par Lean |
| ◇ | énoncé Lean accepté, sans preuve |
| … | énoncé en langage naturel seulement |
| ✕ | bloqué : dépend d'une définition non formalisée |

Un théorème non vérifié n'est jamais présenté comme théorème : il est titré « Affirmation », avec un avertissement.
Le site n'utilise ni traceur, ni police ou script externe.
`,text:`Publier un projet L'écran « Publier » (menu du projet) transforme un projet en site statique que n'importe qui peut lire et revérifier : - l'article (HTML, et le PDF si vous le joignez) ; - le graphe des dépendances, avec l'état de chaque résultat ; - une page par résultat : énoncé en langage naturel, code Lean coloré, preuve rédigée, informations de vérification (version de Lean, révision de Mathlib, axiomes) ; - la table de vérification et la bibliographie ; - le projet Lean (Lake) complet à télécharger, et, si vous le demandez, vos calculs (Calcul). Un résultat publié emmène avec lui tout ce dont il dépend : un résultat n'est jamais montré sans ce sur quoi il s'appuie. Le site est envoyé sur un dépôt GitHub que vous choisissez, avec une action GitHub qui relance lake build sur le projet Lean publié. Le badge de vérification affiché par le site vient de cette action, indépendante de votre ordinateur : un lecteur n'a pas à croire Madalean sur parole. Ce qui part, et seulement avec votre accord 1. « Ce que vous publiez » : cochez les résultats, les notes (aucune par défaut), « Joindre le PDF de l'article », « Joindre les calculs (Calcul) », et choisissez la licence du site. 2. « Préparer la liste exacte » : rien n'est envoyé à cette étape. L'écran liste exactement ce qui quittera l'ordinateur (« Ce qui quittera cet ordinateur ») : chaque fichier, son type, son origine et sa taille, ce qui est écarté, et ce qui n'est jamais publié (vos clés, vos notes privées, les PDF des articles d'autres auteurs, vos réglages). 3. « Aperçu local » construit le site sur l'ordinateur ; « Ouvrir l'aperçu » le montre avant toute publication. 4. « Envoyer sur GitHub » : indiquez le dépôt (compte/nom), cochez au besoin « Créer le dépôt s'il n'existe pas » (et « Dépôt privé »), puis « Publier » et confirmez par « Oui, publier ». Il faut une clé GitHub (jeton), enregistrée dans les réglages des clés (l'écran y mène par un lien) ; à défaut, la connexion de l'outil gh, s'il est installé sur l'hôte, est utilisée. Madalean active ensuite le site GitHub Pages du dépôt ; s'il n'y arrive pas, il donne le lien pour l'activer à la main. La publication se lance depuis l'ordinateur hôte. Si la liste change entre sa préparation et l'envoi, Madalean demande de la préparer de nouveau. Une nouvelle publication ajoute un commit au dépôt ; rien n'est envoyé si rien n'a changé. Ce que montre le site Chaque état a une couleur, une forme de bordure et un libellé écrit (jamais la couleur seule) : Marque Libellé sur le site ✓ vérifié par Lean (preuve acceptée par Lean, et toutes ses dépendances vérifiées) (✓) prouvé, dépendances non vérifiées ≔ définition acceptée par Lean ◇ énoncé Lean accepté, sans preuve … énoncé en langage naturel seulement ✕ bloqué : dépend d'une définition non formalisée Un théorème non vérifié n'est jamais présenté comme théorème : il est titré « Affirmation », avec un avertissement. Le site n'utilise ni traceur, ni police ou script externe.`},{id:`mathlib-contrib`,lang:`fr`,title:`Contribuer à Mathlib`,order:255,section:`research`,audience:`researcher`,summary:`D'un résultat vérifié à une proposition d'ajout à Mathlib — vérifiée avec la Mathlib actuelle, nommée, contrôlée, relue par vous ; rien n'est envoyé sans deux clics de votre part.`,source:`fr/mathlib-contrib.md`,site_path:`fr/mathlib-contrib.html`,headings:[{level:1,text:`Contribuer à Mathlib`,id:`contribuer-a-mathlib`},{level:2,text:`Où trouver le bouton`,id:`ou-trouver-le-bouton`},{level:2,text:`Les étapes`,id:`les-etapes`},{level:2,text:`La liste de contrôle`,id:`la-liste-de-controle`},{level:2,text:`Envoyer`,id:`envoyer`}],images:[],verify:[],body:`# Contribuer à Mathlib

Mathlib est la grande bibliothèque de mathématiques de Lean. Quand un
de vos résultats y manque, Madalean prépare tout ce qu'il faut pour le proposer : le fichier, le nom, la liste des
contrôles, le texte de la demande. **Vous relisez tout** ; rien ne part sans vous.

## Où trouver le bouton

- dans la **Bibliothèque** : ouvrez un résultat vérifié, puis « Préparer pour Mathlib » ;
- dans un **dossier** : sous la preuve vérifiée, « Préparer pour Mathlib ».

Indiquez votre nom (il figure en tête du fichier, comme l'exige Mathlib), puis « Lancer la préparation ».

## Les étapes

1. **Vérifier avec la Mathlib actuelle.** Mathlib n'accepte que du code à jour. Si la preuve a été trouvée avec le
   Lean du prouveur (Lean 4.9), Madalean remplace d'abord les noms qui ont changé depuis (ceux que Lean signale
   comme périmés, ceux appris de vos preuves, une petite table vérifiée) puis la fait revérifier par Lean 4.36.
   Si cela ne suffit pas, « Relancer la preuve dans Lean actuel » ouvre un nouveau dossier, avec l'ancienne preuve
   comme indice.
2. **Chercher si Mathlib le contient déjà.** Si un lemme de Mathlib donne directement le résultat, Madalean le
   dit, avec son nom, et s'arrête : pas de contribution en double.
3. **Proposer un nom.** Mathlib nomme un théorème d'après son énoncé, lu de gauche à droite : \`a + b ≤ c\` donne
   \`add_le\`, \`0 ≤ x\` donne \`x_nonneg\`, une hypothèse ajoute \`_of_…\`. Madalean explique chaque mot du nom et vérifie
   qu'il est libre.
4. **Réduire les imports.** Au lieu de tout Mathlib, seulement les fichiers nécessaires — puis Lean revérifie.
5. **Vérifier le fichier final** et lancer les **contrôles de style** de Mathlib (\`#lint\` et ses vérifications
   automatiques).

## La liste de contrôle

Chaque règle est marquée *bon*, *à revoir*, *bloquant* ou *non vérifié* : en-tête de copyright, présentation du
fichier, phrase d'explication pour chaque théorème, lignes de 100 caractères au plus, pas de \`sorry\`, pas de limite
de temps relevée, \`simp\` seulement en fin de preuve, ≤ plutôt que ≥, variables déduites des hypothèses entre
accolades, aucun nom périmé, nom libre, imports réduits. La phrase d'explication est écrite automatiquement à
partir de l'énoncé : relisez-la.

## Envoyer

- **Copier** ou **Télécharger le fichier** : toujours possible, rien ne quitte l'ordinateur.
- **Créer une branche sur mon fork…** : seulement avec une clé GitHub enregistrée dans Réglages → Clés, et depuis
  l'ordinateur hôte. Madalean montre d'abord **exactement** ce qui sera envoyé (chaque requête, le contenu du
  fichier) ; rien ne part avant « Confirmer ».
- **Ouvrir la PR…** : une seconde confirmation, séparée. La demande est ouverte en **brouillon** : vous la relisez
  sur GitHub avant de la proposer aux relecteurs.

Les guides de Mathlib (contribuer, nommage, style, documentation) sont liés en bas du panneau. Les relecteurs de
Mathlib demandent souvent de raccourcir une preuve ou de généraliser un énoncé : c'est normal.
`,text:`Contribuer à Mathlib Mathlib est la grande bibliothèque de mathématiques de Lean. Quand un de vos résultats y manque, Madalean prépare tout ce qu'il faut pour le proposer : le fichier, le nom, la liste des contrôles, le texte de la demande. Vous relisez tout ; rien ne part sans vous. Où trouver le bouton - dans la Bibliothèque : ouvrez un résultat vérifié, puis « Préparer pour Mathlib » ; - dans un dossier : sous la preuve vérifiée, « Préparer pour Mathlib ». Indiquez votre nom (il figure en tête du fichier, comme l'exige Mathlib), puis « Lancer la préparation ». Les étapes 1. Vérifier avec la Mathlib actuelle. Mathlib n'accepte que du code à jour. Si la preuve a été trouvée avec le Lean du prouveur (Lean 4.9), Madalean remplace d'abord les noms qui ont changé depuis (ceux que Lean signale comme périmés, ceux appris de vos preuves, une petite table vérifiée) puis la fait revérifier par Lean 4.36. Si cela ne suffit pas, « Relancer la preuve dans Lean actuel » ouvre un nouveau dossier, avec l'ancienne preuve comme indice. 2. Chercher si Mathlib le contient déjà. Si un lemme de Mathlib donne directement le résultat, Madalean le dit, avec son nom, et s'arrête : pas de contribution en double. 3. Proposer un nom. Mathlib nomme un théorème d'après son énoncé, lu de gauche à droite : a + b ≤ c donne addle, 0 ≤ x donne xnonneg, une hypothèse ajoute of…. Madalean explique chaque mot du nom et vérifie qu'il est libre. 4. Réduire les imports. Au lieu de tout Mathlib, seulement les fichiers nécessaires — puis Lean revérifie. 5. Vérifier le fichier final et lancer les contrôles de style de Mathlib (#lint et ses vérifications automatiques). La liste de contrôle Chaque règle est marquée bon, à revoir, bloquant ou non vérifié : en-tête de copyright, présentation du fichier, phrase d'explication pour chaque théorème, lignes de 100 caractères au plus, pas de sorry, pas de limite de temps relevée, simp seulement en fin de preuve, ≤ plutôt que ≥, variables déduites des hypothèses entre accolades, aucun nom périmé, nom libre, imports réduits. La phrase d'explication est écrite automatiquement à partir de l'énoncé : relisez-la. Envoyer - Copier ou Télécharger le fichier : toujours possible, rien ne quitte l'ordinateur. - Créer une branche sur mon fork… : seulement avec une clé GitHub enregistrée dans Réglages → Clés, et depuis l'ordinateur hôte. Madalean montre d'abord exactement ce qui sera envoyé (chaque requête, le contenu du fichier) ; rien ne part avant « Confirmer ». - Ouvrir la PR… : une seconde confirmation, séparée. La demande est ouverte en brouillon : vous la relisez sur GitHub avant de la proposer aux relecteurs. Les guides de Mathlib (contribuer, nommage, style, documentation) sont liés en bas du panneau. Les relecteurs de Mathlib demandent souvent de raccourcir une preuve ou de généraliser un énoncé : c'est normal.`},{id:`memory`,lang:`fr`,title:`Mémoire — exporter, importer, sauvegarder`,order:146,section:`settings`,audience:`researcher`,summary:`Tout ce que Madalean a appris (bibliothèque, leçons, recettes, graphes, résumés) dans un seul fichier, revérifié par Lean à l'import ; sauvegardes automatiques ; jeu de données vérifiées.`,source:`fr/memory.md`,site_path:`fr/memory.html`,headings:[{level:1,text:`Mémoire — exporter, importer, sauvegarder`,id:`memoire-exporter-importer-sauvegarder`},{level:2,text:`Exporter`,id:`exporter`},{level:2,text:`Importer`,id:`importer`},{level:2,text:`Sauvegardes automatiques`,id:`sauvegardes-automatiques`},{level:2,text:`Jeu de données d'entraînement`,id:`jeu-de-donnees-dentrainement`}],images:[],verify:[],body:`# Mémoire — exporter, importer, sauvegarder

Madalean apprend sans entraîner de modèle : la **bibliothèque** des résultats prouvés, les **leçons** tirées de ses
erreurs, les **recettes** de calcul, les **graphes** de vos problèmes, les **résumés** des pièces jointes. Réglages ›
« Mémoire » met tout cela dans un seul fichier \`.madalean-memory\`, à garder ou à transporter sur un autre ordinateur.

## Exporter

Cochez les parties à inclure et, si vous voulez, seulement certains projets, puis « Exporter la mémoire ».

- Les **résumés de sources protégées** (©, ou licence inconnue) sont laissés de côté par défaut : leur licence peut
  interdire de les redistribuer. Le fichier dit ce qui manque. Cochez « Inclure les résumés de sources protégées »
  pour une copie strictement personnelle.
- Les **fichiers d'origine** des pièces jointes (PDF, images…) ne sont inclus que si vous le cochez.
- Le fichier porte l'empreinte (SHA-256) de chaque partie et les versions de Lean et de Mathlib de vos espaces.

## Importer

Sur l'ordinateur hôte seulement. Choisissez un fichier : Madalean montre d'abord un **aperçu** — ce qui serait
ajouté, vérifié, ignoré, et pourquoi — sans rien écrire. « Importer » applique.

Rien n'est cru sur parole :

- chaque **preuve** est revérifiée ici par Lean, dans un espace qui a **les mêmes versions de Lean et de Mathlib**.
  Acceptée, elle entre dans la bibliothèque. Sinon elle reste dans « Importées, non vérifiées » avec la raison
  (aucun espace de même version, Lean refuse la preuve, un résultat utilisé manque…) et ne sert à rien. Après avoir
  installé le bon espace, « Revérifier » ;
- les **recettes** de calcul sont relues par Sage ou Python (sans être exécutées) ; un code qui touche au système est
  refusé ; une recette importée ne remplace jamais la vôtre ;
- les **leçons** gardent leurs preuves mais repartent de zéro : elles ne comptent qu'une fois utiles ici ;
- les **graphes** venus d'ailleurs restent des **références** en lecture seule (l'aperçu dit combien de leurs lemmes
  sont déjà dans vos graphes) ; vos graphes ne sont jamais modifiés ;
- les **résumés** rejoignent le projet du même identifiant s'il existe (comme « résultats fournis » : jamais des
  preuves), sinon des références ;
- les doublons (même énoncé à un renommage près, même leçon, même code) sont ignorés ;
- un texte qui s'adresse à un modèle (« ignore les instructions… ») est refusé ; un fichier modifié (empreinte
  différente) est refusé en entier.

## Sauvegardes automatiques

Cochez « Sauvegarder automatiquement », choisissez la fréquence (jour, semaine, mois), le nombre de copies gardées
et le dossier (par défaut \`~/.config/madalean/backups\`). Les copies restent sur cet ordinateur ; seules les plus
anciennes copies de Madalean sont effacées, jamais vos autres fichiers. « Sauvegarder maintenant » en écrit une tout
de suite. Pour restaurer : « Importer » une copie.

## Jeu de données d'entraînement

« Exporter le jeu de données » écrit un fichier JSONL des paires **vérifiées par Lean** (énoncé → preuve, erreur →
correction), avec la licence et la provenance de chaque ligne. Il prépare un éventuel affinage d'un modèle local plus
tard (désactivé, non fourni) : Madalean n'entraîne aucun modèle.

Pour aller plus loin : [Graphe du problème et leçons](proof-graph.md) · [Bibliothèque](library.md) ·
[Sécurité](security.md).
`,text:`Mémoire — exporter, importer, sauvegarder Madalean apprend sans entraîner de modèle : la bibliothèque des résultats prouvés, les leçons tirées de ses erreurs, les recettes de calcul, les graphes de vos problèmes, les résumés des pièces jointes. Réglages › « Mémoire » met tout cela dans un seul fichier .madalean-memory, à garder ou à transporter sur un autre ordinateur. Exporter Cochez les parties à inclure et, si vous voulez, seulement certains projets, puis « Exporter la mémoire ». - Les résumés de sources protégées (©, ou licence inconnue) sont laissés de côté par défaut : leur licence peut interdire de les redistribuer. Le fichier dit ce qui manque. Cochez « Inclure les résumés de sources protégées » pour une copie strictement personnelle. - Les fichiers d'origine des pièces jointes (PDF, images…) ne sont inclus que si vous le cochez. - Le fichier porte l'empreinte (SHA-256) de chaque partie et les versions de Lean et de Mathlib de vos espaces. Importer Sur l'ordinateur hôte seulement. Choisissez un fichier : Madalean montre d'abord un aperçu — ce qui serait ajouté, vérifié, ignoré, et pourquoi — sans rien écrire. « Importer » applique. Rien n'est cru sur parole : - chaque preuve est revérifiée ici par Lean, dans un espace qui a les mêmes versions de Lean et de Mathlib. Acceptée, elle entre dans la bibliothèque. Sinon elle reste dans « Importées, non vérifiées » avec la raison (aucun espace de même version, Lean refuse la preuve, un résultat utilisé manque…) et ne sert à rien. Après avoir installé le bon espace, « Revérifier » ; - les recettes de calcul sont relues par Sage ou Python (sans être exécutées) ; un code qui touche au système est refusé ; une recette importée ne remplace jamais la vôtre ; - les leçons gardent leurs preuves mais repartent de zéro : elles ne comptent qu'une fois utiles ici ; - les graphes venus d'ailleurs restent des références en lecture seule (l'aperçu dit combien de leurs lemmes sont déjà dans vos graphes) ; vos graphes ne sont jamais modifiés ; - les résumés rejoignent le projet du même identifiant s'il existe (comme « résultats fournis » : jamais des preuves), sinon des références ; - les doublons (même énoncé à un renommage près, même leçon, même code) sont ignorés ; - un texte qui s'adresse à un modèle (« ignore les instructions… ») est refusé ; un fichier modifié (empreinte différente) est refusé en entier. Sauvegardes automatiques Cochez « Sauvegarder automatiquement », choisissez la fréquence (jour, semaine, mois), le nombre de copies gardées et le dossier (par défaut ~/.config/madalean/backups). Les copies restent sur cet ordinateur ; seules les plus anciennes copies de Madalean sont effacées, jamais vos autres fichiers. « Sauvegarder maintenant » en écrit une tout de suite. Pour restaurer : « Importer » une copie. Jeu de données d'entraînement « Exporter le jeu de données » écrit un fichier JSONL des paires vérifiées par Lean (énoncé → preuve, erreur → correction), avec la licence et la provenance de chaque ligne. Il prépare un éventuel affinage d'un modèle local plus tard (désactivé, non fourni) : Madalean n'entraîne aucun modèle. Pour aller plus loin : Graphe du problème et leçons · Bibliothèque · Sécurité.`},{id:`models-keys`,lang:`fr`,title:`Modèles et clés`,order:300,section:`settings`,audience:`all`,summary:`Les modes Local / Automatique / En ligne, ce qui part et vers qui, comment obtenir une clé Anthropic ou Gemini, et ce que cela coûte.`,source:`fr/models-keys.md`,site_path:`fr/models-keys.html`,headings:[{level:1,text:`Modèles et clés`,id:`modeles-et-cles`},{level:2,text:`Les trois modes`,id:`les-trois-modes`},{level:2,text:`Ce qui part, et vers qui`,id:`ce-qui-part-et-vers-qui`},{level:2,text:`Ajouter une clé`,id:`ajouter-une-cle`},{level:3,text:`Clé Anthropic (Claude)`,id:`cle-anthropic-claude`},{level:3,text:`Clé Google Gemini`,id:`cle-google-gemini`},{level:3,text:`Jeton Hugging Face (Goedel-Prover 32B en ligne)`,id:`jeton-hugging-face-goedel-prover-32b-en-ligne`},{level:2,text:`Ce que cela coûte`,id:`ce-que-cela-coute`},{level:2,text:`Claude en renfort payant, avec plafonds`,id:`claude-en-renfort-payant-avec-plafonds`},{level:2,text:`Choisir un modèle par rôle`,id:`choisir-un-modele-par-role`}],images:[{src:`img/settings-keys.png`,exists:!0}],verify:[],body:`# Modèles et clés

Madalean fonctionne **sans aucune clé** : modèles locaux installés sur l'hôte et fournisseurs en ligne gratuits sans
compte. Une clé ajoute les modèles d'un fournisseur, souvent plus forts. La liste des fournisseurs, avec pour
chacun ce qui est gratuit et où créer la clé, est dans [Première configuration](first-config.md#cles-des-fournisseurs-en-ligne) ;
les modèles locaux sont décrits dans [Ce qu'installe Madalean](components.md#modeles-locaux).

## Les trois modes

| Mode | Qui travaille | Réseau |
|---|---|---|
| *Local* | seulement les modèles de l'ordinateur hôte (Goedel-Prover, Goedel-Formalizer, Qwen3, et Ollama s'il tourne) | rien ne quitte l'hôte ; toute connexion non locale est refusée avant d'être ouverte |
| *Automatique* (défaut) | les modèles en ligne (avec un jeton Hugging Face, Goedel-Prover 32B ouvre chaque preuve) | les modèles locaux **seulement** sans Internet, ou quand aucun modèle en ligne ne peut travailler (tous en panne, en pause ou refusés) ; sinon le modèle local n'est pas chargé et la carte graphique reste libre |
| *En ligne* | uniquement des modèles en ligne | sans réseau, le travail échoue avec un message clair |

Madalean distingue « pas d'Internet » (une sonde rapide, mise en cache) d'un « fournisseur en panne » (Internet
répond mais pas lui) : sans Internet, il passe aussitôt aux modèles locaux ; un fournisseur en panne est seulement
sauté pendant une minute. En mode *Automatique*, une preuve que les modèles en ligne ont cherchée sans la trouver
n'est **pas** relancée sur le modèle local (le Goedel 32B en ligne est plus fort que le 8B local).

Pour un dossier précis, « Options de ce dossier » (sur l'accueil) permet de choisir un autre mode que le mode
général. Le bouton d'état en haut à droite de l'écran
(son panneau « Qui reçoit quoi ») dit à chaque instant quel modèle reçoit votre travail, avec les tokens et le coût dépensés. Chaque texte produit par un modèle
indique son nom.

## Ce qui part, et vers qui

| Étape | Ce que reçoit le modèle |
|---|---|
| Compréhension | votre énoncé en langage courant |
| Traduction en Lean | votre énoncé et sa reformulation |
| Preuve | l'énoncé Lean, les messages d'erreur de Lean, des lemmes de Mathlib trouvés pour l'énoncé |
| Explication, preuve rédigée | l'énoncé et la preuve Lean |
| Questions sur les sources | votre question et les passages retenus de vos sources |
| Calcul (cellule « Demander ») | votre demande et les noms déjà définis dans le carnet (pas les sorties complètes) |

Ce qui n'est **jamais** envoyé à un modèle : vos clés d'API, vos jetons d'appareils, vos autres dossiers, vos
fichiers. Une clé n'est envoyée qu'à **son** fournisseur : Madalean refuse de joindre une clé à une adresse qui n'est
pas celle de ce fournisseur.

Les fournisseurs gratuits sans compte livrés avec Madalean (LLM7.io, OVHcloud AI Endpoints, Kilo Code,
Pollinations) appliquent leurs propres conditions ; supposez que ce que vous leur envoyez peut être conservé. Pour un
travail confidentiel, utilisez le mode *Local*.

## Ajouter une clé

« Réglages › Fournisseurs » range les services en ligne par usage, avec ce qui est gratuit et où partent vos
données. Sur la carte d'un fournisseur, « Créer une clé » ouvre sa page de clés ; collez la clé, Madalean la
**teste aussitôt** (« Ça marche : N modèles disponibles », ou la
raison du refus). La clé est gardée dans le trousseau de l'ordinateur hôte (sinon dans un fichier lisible par vous
seul) et ne s'affiche plus jamais. « Retirer la clé » la supprime en un clic.

![Réglages › Fournisseurs](img/settings-keys.png)

### Clé Anthropic (Claude)

1. Sur la carte Anthropic, « Créer une clé » ouvre la page des clés de la console d'Anthropic ; créez un compte si
   besoin.
2. Claude est payant à l'usage : suivez les indications d'Anthropic pour ajouter un moyen de paiement ou des
   crédits.
3. Créez une clé et copiez-la (elle commence par \`sk-ant-\`). Elle n'est en général montrée qu'une fois.
4. Collez-la sur la carte Anthropic.

Conseil : si la console d'Anthropic le permet, fixez-y aussi une limite de dépense ; Madalean a de toute façon ses
propres plafonds (voir plus bas).

### Clé Google Gemini

1. Sur la carte Google Gemini, « Créer une clé » ouvre la page des clés de Google AI Studio (avec un compte
   Google).
2. Créez une clé et copiez-la.
3. Collez-la sur la carte Google Gemini.

L'offre gratuite de Gemini a des quotas ; quand ils sont atteints, Madalean passe au modèle suivant. Les conditions
d'utilisation des données diffèrent selon l'offre et peuvent changer : lisez celles de Google avant d'envoyer un
travail non publié avec une clé gratuite.

### Jeton Hugging Face (Goedel-Prover 32B en ligne)

Avec un jeton Hugging Face, **Goedel-Prover-V2-32B** (servi en ligne par un fournisseur partenaire d'Hugging
Face) ouvre chaque preuve : c'est la même boucle que le Goedel local — mêmes prompts, ≤ 2 corrections par
piste, mêmes réglages d'échantillonnage —, avec le modèle 32B au lieu du 8B, sans occuper la carte graphique. S'il
échoue, les modèles gratuits prennent le relais (tournoi). Le Goedel-Formalizer est utilisé de même dès qu'un
fournisseur le sert en ligne.

1. Créez un compte sur le site de Hugging Face (\`huggingface.co\`). Les appels sont payés avec des crédits Hugging Face (les
   conditions de l'offre sont sur le site d'Hugging Face).
2. Sur la carte Hugging Face, « Créer une clé » ouvre la page des jetons d'Hugging Face, prête à créer un jeton avec
   la permission « Make calls to Inference Providers » ; créez le jeton (il commence par \`hf_\`).
3. Collez-le : Madalean vérifie le jeton (sans rien facturer) et dit si Goedel 32B est disponible en ligne.

Le jeton n'est envoyé qu'à \`router.huggingface.co\` (les calculs) et \`huggingface.co\` (la vérification du jeton).
La liste des modèles Goedel servis en ligne est lue sur l'API publique de Hugging Face, **sans** le jeton.
Désactivable dans « Réglages › Modèles › Réglages avancés » (« Goedel-Prover 32B en ligne (Hugging Face) ouvre
chaque preuve quand le jeton est enregistré »).

## Ce que cela coûte

Les fournisseurs payants facturent au nombre de *tokens* (≈ ¾ de mot) envoyés et reçus. Tarifs publics d'Anthropic
qu'utilise cette version de Madalean pour ses estimations, par million de tokens (entrée / sortie) ; les prix en
vigueur sont ceux du site d'Anthropic :

| Modèle | Entrée | Sortie |
|---|---|---|
| Claude Opus 5.5 | 4 $ | 20 $ |
| Claude Sonnet 5.5 | 2 $ | 10 $ |
| Claude Haiku 5.5 | 0,10 $ | 0,50 $ |

Le coût d'une preuve dépend de l'énoncé et du nombre d'essais ; il est borné par le plafond par preuve (voir plus
bas), et chaque appel payant est affiché avec son coût sous les plafonds. Les limites (étapes et durée de l'agent,
essais, durée d'une preuve) se règlent dans « Réglages › Modèles › Réglages avancés ». Un modèle payant n'est utilisé
que si vous l'avez choisi pour une tâche, ou en renfort (Claude, ci-dessous).

**Goedel-Prover 32B en ligne (Hugging Face).** Le fournisseur ne publie pas de prix par jeton pour ce modèle :
Madalean utilise une **estimation prudente** de 1,00 $ (entrée) / 3,20 $ (sortie) par million de tokens, remplacée
par le prix publié dès qu'Hugging Face en donne un. Une tentative Goedel (jusqu'à 32 768 tokens de réponse) coûte donc
au plus ≈ 0,11 $ ; les 4 tentatives du premier round d'une preuve, au plus ≈ 0,45 $. Le coût réel se voit dans
l'espace de facturation de votre compte Hugging Face.

## Claude en renfort payant, avec plafonds

Avec une clé Anthropic, Claude peut entrer **en dernier** dans le tournoi d'une preuve, seulement quand les modèles
gratuits ont tous échoué (« Réglages › Modèles », partie « Claude en renfort payant », case « Faire appel à Claude
quand les modèles gratuits échouent », cochée par défaut).
Deux plafonds, modifiables au même endroit :

- « Plafond par preuve » (1,00 $ par défaut) ;
- « Plafond par mois », par mois civil (20 $ par défaut), pour tous les appels payants — Claude, y compris dans un rôle où vous l'avez
  choisi, et Goedel en ligne sur Hugging Face (mêmes plafonds, même registre).

Avant chaque appel, Madalean estime le coût au tarif public (taille de la demande et longueur de réponse permise) et
réduit la longueur de réponse si besoin ; si même une réponse courte dépasserait un plafond, l'appel **n'est pas
fait** et la preuve le signale. Après l'appel, le coût réel est calculé d'après l'usage renvoyé par Anthropic (jetons
d'entrée, de sortie, lus et écrits en cache) et noté dans un petit registre privé de l'hôte. Le total du mois
(« Dépensé en … ») et les derniers appels sont affichés sous les plafonds. Ce total est calculé au tarif public : la
facture d'Anthropic fait foi.

## Choisir un modèle par rôle

« Réglages › Modèles », partie « Modèle par tâche », montre, pour chaque tâche (comprendre l'énoncé, traduire en
Lean, prouver, expliquer, assistant…), le classement des modèles disponibles et la raison du classement
(« Pourquoi ? »). « Automatique » laisse le routeur choisir ; vous pouvez imposer
un modèle. Un modèle en erreur (quota, clé refusée, surcharge) est mis en pause et le suivant prend le relais.
`,text:`Modèles et clés Madalean fonctionne sans aucune clé : modèles locaux installés sur l'hôte et fournisseurs en ligne gratuits sans compte. Une clé ajoute les modèles d'un fournisseur, souvent plus forts. La liste des fournisseurs, avec pour chacun ce qui est gratuit et où créer la clé, est dans Première configuration ; les modèles locaux sont décrits dans Ce qu'installe Madalean. Les trois modes Mode Qui travaille Réseau Local seulement les modèles de l'ordinateur hôte (Goedel-Prover, Goedel-Formalizer, Qwen3, et Ollama s'il tourne) rien ne quitte l'hôte ; toute connexion non locale est refusée avant d'être ouverte Automatique (défaut) les modèles en ligne (avec un jeton Hugging Face, Goedel-Prover 32B ouvre chaque preuve) les modèles locaux seulement sans Internet, ou quand aucun modèle en ligne ne peut travailler (tous en panne, en pause ou refusés) ; sinon le modèle local n'est pas chargé et la carte graphique reste libre En ligne uniquement des modèles en ligne sans réseau, le travail échoue avec un message clair Madalean distingue « pas d'Internet » (une sonde rapide, mise en cache) d'un « fournisseur en panne » (Internet répond mais pas lui) : sans Internet, il passe aussitôt aux modèles locaux ; un fournisseur en panne est seulement sauté pendant une minute. En mode Automatique, une preuve que les modèles en ligne ont cherchée sans la trouver n'est pas relancée sur le modèle local (le Goedel 32B en ligne est plus fort que le 8B local). Pour un dossier précis, « Options de ce dossier » (sur l'accueil) permet de choisir un autre mode que le mode général. Le bouton d'état en haut à droite de l'écran (son panneau « Qui reçoit quoi ») dit à chaque instant quel modèle reçoit votre travail, avec les tokens et le coût dépensés. Chaque texte produit par un modèle indique son nom. Ce qui part, et vers qui Étape Ce que reçoit le modèle Compréhension votre énoncé en langage courant Traduction en Lean votre énoncé et sa reformulation Preuve l'énoncé Lean, les messages d'erreur de Lean, des lemmes de Mathlib trouvés pour l'énoncé Explication, preuve rédigée l'énoncé et la preuve Lean Questions sur les sources votre question et les passages retenus de vos sources Calcul (cellule « Demander ») votre demande et les noms déjà définis dans le carnet (pas les sorties complètes) Ce qui n'est jamais envoyé à un modèle : vos clés d'API, vos jetons d'appareils, vos autres dossiers, vos fichiers. Une clé n'est envoyée qu'à son fournisseur : Madalean refuse de joindre une clé à une adresse qui n'est pas celle de ce fournisseur. Les fournisseurs gratuits sans compte livrés avec Madalean (LLM7.io, OVHcloud AI Endpoints, Kilo Code, Pollinations) appliquent leurs propres conditions ; supposez que ce que vous leur envoyez peut être conservé. Pour un travail confidentiel, utilisez le mode Local. Ajouter une clé « Réglages › Fournisseurs » range les services en ligne par usage, avec ce qui est gratuit et où partent vos données. Sur la carte d'un fournisseur, « Créer une clé » ouvre sa page de clés ; collez la clé, Madalean la teste aussitôt (« Ça marche : N modèles disponibles », ou la raison du refus). La clé est gardée dans le trousseau de l'ordinateur hôte (sinon dans un fichier lisible par vous seul) et ne s'affiche plus jamais. « Retirer la clé » la supprime en un clic. Réglages › Fournisseurs Clé Anthropic (Claude) 1. Sur la carte Anthropic, « Créer une clé » ouvre la page des clés de la console d'Anthropic ; créez un compte si besoin. 2. Claude est payant à l'usage : suivez les indications d'Anthropic pour ajouter un moyen de paiement ou des crédits. 3. Créez une clé et copiez-la (elle commence par sk-ant-). Elle n'est en général montrée qu'une fois. 4. Collez-la sur la carte Anthropic. Conseil : si la console d'Anthropic le permet, fixez-y aussi une limite de dépense ; Madalean a de toute façon ses propres plafonds (voir plus bas). Clé Google Gemini 1. Sur la carte Google Gemini, « Créer une clé » ouvre la page des clés de Google AI Studio (avec un compte Google). 2. Créez une clé et copiez-la. 3. Collez-la sur la carte Google Gemini. L'offre gratuite de Gemini a des quotas ; quand ils sont atteints, Madalean passe au modèle suivant. Les conditions d'utilisation des données diffèrent selon l'offre et peuvent changer : lisez celles de Google avant d'envoyer un travail non publié avec une clé gratuite. Jeton Hugging Face (Goedel-Prover 32B en ligne) Avec un jeton Hugging Face, Goedel-Prover-V2-32B (servi en ligne par un fournisseur partenaire d'Hugging Face) ouvre chaque preuve : c'est la même boucle que le Goedel local — mêmes prompts, ≤ 2 corrections par piste, mêmes réglages d'échantillonnage —, avec le modèle 32B au lieu du 8B, sans occuper la carte graphique. S'il échoue, les modèles gratuits prennent le relais (tournoi). Le Goedel-Formalizer est utilisé de même dès qu'un fournisseur le sert en ligne. 1. Créez un compte sur le site de Hugging Face (huggingface.co). Les appels sont payés avec des crédits Hugging Face (les conditions de l'offre sont sur le site d'Hugging Face). 2. Sur la carte Hugging Face, « Créer une clé » ouvre la page des jetons d'Hugging Face, prête à créer un jeton avec la permission « Make calls to Inference Providers » ; créez le jeton (il commence par hf). 3. Collez-le : Madalean vérifie le jeton (sans rien facturer) et dit si Goedel 32B est disponible en ligne. Le jeton n'est envoyé qu'à router.huggingface.co (les calculs) et huggingface.co (la vérification du jeton). La liste des modèles Goedel servis en ligne est lue sur l'API publique de Hugging Face, sans le jeton. Désactivable dans « Réglages › Modèles › Réglages avancés » (« Goedel-Prover 32B en ligne (Hugging Face) ouvre chaque preuve quand le jeton est enregistré »). Ce que cela coûte Les fournisseurs payants facturent au nombre de tokens (≈ ¾ de mot) envoyés et reçus. Tarifs publics d'Anthropic qu'utilise cette version de Madalean pour ses estimations, par million de tokens (entrée / sortie) ; les prix en vigueur sont ceux du site d'Anthropic : Modèle Entrée Sortie Claude Opus 5.5 4 $ 20 $ Claude Sonnet 5.5 2 $ 10 $ Claude Haiku 5.5 0,10 $ 0,50 $ Le coût d'une preuve dépend de l'énoncé et du nombre d'essais ; il est borné par le plafond par preuve (voir plus bas), et chaque appel payant est affiché avec son coût sous les plafonds. Les limites (étapes et durée de l'agent, essais, durée d'une preuve) se règlent dans « Réglages › Modèles › Réglages avancés ». Un modèle payant n'est utilisé que si vous l'avez choisi pour une tâche, ou en renfort (Claude, ci-dessous). Goedel-Prover 32B en ligne (Hugging Face). Le fournisseur ne publie pas de prix par jeton pour ce modèle : Madalean utilise une estimation prudente de 1,00 $ (entrée) / 3,20 $ (sortie) par million de tokens, remplacée par le prix publié dès qu'Hugging Face en donne un. Une tentative Goedel (jusqu'à 32 768 tokens de réponse) coûte donc au plus ≈ 0,11 $ ; les 4 tentatives du premier round d'une preuve, au plus ≈ 0,45 $. Le coût réel se voit dans l'espace de facturation de votre compte Hugging Face. Claude en renfort payant, avec plafonds Avec une clé Anthropic, Claude peut entrer en dernier dans le tournoi d'une preuve, seulement quand les modèles gratuits ont tous échoué (« Réglages › Modèles », partie « Claude en renfort payant », case « Faire appel à Claude quand les modèles gratuits échouent », cochée par défaut). Deux plafonds, modifiables au même endroit : - « Plafond par preuve » (1,00 $ par défaut) ; - « Plafond par mois », par mois civil (20 $ par défaut), pour tous les appels payants — Claude, y compris dans un rôle où vous l'avez choisi, et Goedel en ligne sur Hugging Face (mêmes plafonds, même registre). Avant chaque appel, Madalean estime le coût au tarif public (taille de la demande et longueur de réponse permise) et réduit la longueur de réponse si besoin ; si même une réponse courte dépasserait un plafond, l'appel n'est pas fait et la preuve le signale. Après l'appel, le coût réel est calculé d'après l'usage renvoyé par Anthropic (jetons d'entrée, de sortie, lus et écrits en cache) et noté dans un petit registre privé de l'hôte. Le total du mois (« Dépensé en … ») et les derniers appels sont affichés sous les plafonds. Ce total est calculé au tarif public : la facture d'Anthropic fait foi. Choisir un modèle par rôle « Réglages › Modèles », partie « Modèle par tâche », montre, pour chaque tâche (comprendre l'énoncé, traduire en Lean, prouver, expliquer, assistant…), le classement des modèles disponibles et la raison du classement (« Pourquoi ? »). « Automatique » laisse le routeur choisir ; vous pouvez imposer un modèle. Un modèle en erreur (quota, clé refusée, surcharge) est mis en pause et le suivant prend le relais.`},{id:`updates`,lang:`fr`,title:`Mises à jour`,order:310,section:`settings`,audience:`all`,summary:`Ce qui se met à jour tout seul, ce qui demande un clic, comment une mise à jour est vérifiée, et comment revenir en arrière.`,source:`fr/updates.md`,site_path:`fr/updates.html`,headings:[{level:1,text:`Mises à jour`,id:`mises-a-jour`},{level:2,text:`Ce qui est mis à jour, et comment`,id:`ce-qui-est-mis-a-jour-et-comment`},{level:2,text:`Pourquoi une mise à jour de Madalean est sûre`,id:`pourquoi-une-mise-a-jour-de-madalean-est-sure`},{level:2,text:`Après une mise à jour de Lean ou de Mathlib`,id:`apres-une-mise-a-jour-de-lean-ou-de-mathlib`},{level:2,text:`Revenir en arrière`,id:`revenir-en-arriere`}],images:[],verify:[],body:`# Mises à jour

Tout se met à jour depuis Madalean, sans terminal, selon une règle unique : **installer à côté, vérifier, basculer,
puis supprimer l'ancienne version**. Un échec ne change rien et vous est signalé.

## Ce qui est mis à jour, et comment

Tout se règle dans « Réglages › Mises à jour ».

| Composant | Comportement par défaut |
|---|---|
| Madalean (serveur et interface), partie « Madalean lui-même » | cherché chaque semaine (sauf en mode *Local*), téléchargé, vérifié, installé à un moment calme (aucun travail en cours), puis redémarré ; « Installer » et « Redémarrer maintenant » le font tout de suite. La version précédente est gardée pour revenir en arrière |
| Application de bureau (AppImage) | se remplace elle-même après vérification ; la nouvelle version s'ouvre au prochain démarrage (ou tout de suite avec « Redémarrer ») |
| Application Android | réglage « Mises à jour automatiques » de l'application : elle vérifie au plus deux fois par jour, télécharge et contrôle la signature ; l'installation demande toujours votre confirmation (règle d'Android) |
| Lean, Mathlib, paquets Lean de l'espace « Lean actuel », SageMath, LaTeX (partie « Composants suivis ») | automatique : installé à côté, vérifié (théorème de test et revérification des dossiers prouvés), basculé |
| Modèles Goedel, catalogue des modèles en ligne | automatique, empreintes vérifiées |
| Espace « Prouveur » (Lean 4.9) | **jamais** : épinglé, c'est l'environnement d'entraînement des modèles |
| llama.cpp | notification seulement ; sa version épinglée change avec les versions de Madalean |
| Programmes installés sur le système hors de Madalean (partie « Composants du système ») | notification seulement, avec la commande exacte et un bouton « Ouvrir un terminal avec la commande » ; vous tapez votre mot de passe. Madalean ne lance jamais \`sudo\`, \`pacman\`, \`apt\` ou \`dnf\` lui-même. |

Décochez « Installer automatiquement quand rien ne tourne » pour être prévenu avant chaque installation au lieu de
l'installation automatique. « Chercher chaque semaine (rien ne s'installe sans votre clic) » règle la recherche
automatique ; « Chercher des mises à jour » la lance tout de suite.

## Pourquoi une mise à jour de Madalean est sûre

Chaque version publiée est accompagnée d'une liste d'empreintes (\`SHA256SUMS\`) **signée** avec une clé Ed25519 gardée
hors de GitHub. La clé publique est inscrite dans Madalean. Une version dont la signature ne correspond pas est
refusée, **même si le compte GitHub était compromis**. Le canal de mise à jour
(\`updates/stable.json\`, sur le site) est signé de la même façon.

Vérifier vous-même un téléchargement : voir la [page d'installation](site:install#verify).

## Après une mise à jour de Lean ou de Mathlib

Les dossiers prouvés de l'espace concerné sont revérifiés automatiquement (partie « Revérification des preuves »,
bouton « Revérifier maintenant »). Un dossier
dont la preuve ne passe plus (un lemme renommé, une tactique changée) est signalé ; son ancien verdict n'est jamais
affiché seul.

## Revenir en arrière

Pour Madalean : « Réglages › Mises à jour », partie « Madalean lui-même », bouton « Revenir à … » (avec le numéro de
la version précédente). Pour Lean et Mathlib, l'ancienne version n'est remplacée qu'après une vérification réussie ;
en cas d'échec, rien ne change.
`,text:`Mises à jour Tout se met à jour depuis Madalean, sans terminal, selon une règle unique : installer à côté, vérifier, basculer, puis supprimer l'ancienne version. Un échec ne change rien et vous est signalé. Ce qui est mis à jour, et comment Tout se règle dans « Réglages › Mises à jour ». Composant Comportement par défaut Madalean (serveur et interface), partie « Madalean lui-même » cherché chaque semaine (sauf en mode Local), téléchargé, vérifié, installé à un moment calme (aucun travail en cours), puis redémarré ; « Installer » et « Redémarrer maintenant » le font tout de suite. La version précédente est gardée pour revenir en arrière Application de bureau (AppImage) se remplace elle-même après vérification ; la nouvelle version s'ouvre au prochain démarrage (ou tout de suite avec « Redémarrer ») Application Android réglage « Mises à jour automatiques » de l'application : elle vérifie au plus deux fois par jour, télécharge et contrôle la signature ; l'installation demande toujours votre confirmation (règle d'Android) Lean, Mathlib, paquets Lean de l'espace « Lean actuel », SageMath, LaTeX (partie « Composants suivis ») automatique : installé à côté, vérifié (théorème de test et revérification des dossiers prouvés), basculé Modèles Goedel, catalogue des modèles en ligne automatique, empreintes vérifiées Espace « Prouveur » (Lean 4.9) jamais : épinglé, c'est l'environnement d'entraînement des modèles llama.cpp notification seulement ; sa version épinglée change avec les versions de Madalean Programmes installés sur le système hors de Madalean (partie « Composants du système ») notification seulement, avec la commande exacte et un bouton « Ouvrir un terminal avec la commande » ; vous tapez votre mot de passe. Madalean ne lance jamais sudo, pacman, apt ou dnf lui-même. Décochez « Installer automatiquement quand rien ne tourne » pour être prévenu avant chaque installation au lieu de l'installation automatique. « Chercher chaque semaine (rien ne s'installe sans votre clic) » règle la recherche automatique ; « Chercher des mises à jour » la lance tout de suite. Pourquoi une mise à jour de Madalean est sûre Chaque version publiée est accompagnée d'une liste d'empreintes (SHA256SUMS) signée avec une clé Ed25519 gardée hors de GitHub. La clé publique est inscrite dans Madalean. Une version dont la signature ne correspond pas est refusée, même si le compte GitHub était compromis. Le canal de mise à jour (updates/stable.json, sur le site) est signé de la même façon. Vérifier vous-même un téléchargement : voir la page d'installation. Après une mise à jour de Lean ou de Mathlib Les dossiers prouvés de l'espace concerné sont revérifiés automatiquement (partie « Revérification des preuves », bouton « Revérifier maintenant »). Un dossier dont la preuve ne passe plus (un lemme renommé, une tactique changée) est signalé ; son ancien verdict n'est jamais affiché seul. Revenir en arrière Pour Madalean : « Réglages › Mises à jour », partie « Madalean lui-même », bouton « Revenir à … » (avec le numéro de la version précédente). Pour Lean et Mathlib, l'ancienne version n'est remplacée qu'après une vérification réussie ; en cas d'échec, rien ne change.`},{id:`security`,lang:`fr`,title:`Sécurité, expliquée simplement`,order:320,section:`settings`,audience:`all`,summary:`Qui peut accéder à Madalean, comment les appareils sont reliés et déliés, où sont les clés, et ce que Madalean ne fait jamais.`,source:`fr/security.md`,site_path:`fr/security.html`,headings:[{level:1,text:`Sécurité, expliquée simplement`,id:`securite-expliquee-simplement`},{level:2,text:`Qui peut parler à Madalean`,id:`qui-peut-parler-a-madalean`},{level:2,text:`Les appareils et les codes`,id:`les-appareils-et-les-codes`},{level:2,text:`Ce qu'un appareil relié ne peut pas faire`,id:`ce-quun-appareil-relie-ne-peut-pas-faire`},{level:2,text:`Vos clés d'API`,id:`vos-cles-dapi`},{level:2,text:`Code exécuté sur l'hôte`,id:`code-execute-sur-lhote`},{level:2,text:`Documents venant de l'extérieur`,id:`documents-venant-de-lexterieur`},{level:2,text:`Ce que Madalean ne fait jamais`,id:`ce-que-madalean-ne-fait-jamais`}],images:[],verify:[],body:`# Sécurité, expliquée simplement

## Qui peut parler à Madalean

Madalean écoute à deux portes, toutes deux fermées vers l'extérieur de l'ordinateur hôte :

1. **La porte locale** (\`127.0.0.1:11500\`), utilisée par le navigateur ou l'application de bureau **de l'hôte**.
   Elle n'accepte que des requêtes venant de l'hôte lui-même.
2. **La porte des appareils** (\`127.0.0.1:11501\`), publiée sur votre réseau privé Tailscale. Toute requête doit
   présenter le **jeton** d'un appareil relié, sauf la page de liaison elle-même.

Une troisième porte, sur le réseau local (port 11502), n'existe que si vous l'ouvrez depuis l'hôte (voir
[Tailscale › Sans Tailscale](tailscale.md#sans-tailscale)) ; elle exige aussi le jeton d'un appareil relié, mais son
trafic n'est pas chiffré.

Il n'y a pas de compte Madalean, pas de serveur Madalean sur Internet, pas de télémétrie.

## Les appareils et les codes

- Relier un appareil demande un **code à 6 chiffres** affiché sur l'hôte : valable 5 minutes, utilisable une fois.
  Cinq codes faux bloquent la liaison 10 minutes ; les essais rapprochés sont freinés.
- L'appareil reçoit alors un **jeton** de 256 bits. L'hôte n'en garde qu'une empreinte (SHA-256) : même quelqu'un
  qui lirait les fichiers de l'hôte ne pourrait pas en tirer le jeton.
- Sur le téléphone, le jeton est dans le stockage protégé d'Android ; sur un PC, dans le trousseau du système ; dans
  un navigateur, dans un cookie inaccessible aux scripts de la page.
- **Délier** un appareil (« Réglages › Appareils ») coupe son accès immédiatement.

Un appareil perdu ou volé : déliez-le depuis l'hôte, et retirez-le de votre réseau Tailscale.

## Ce qu'un appareil relié ne peut pas faire

Certains réglages ouvriraient la machine ; ils ne se changent **que depuis l'hôte** (cadenas dans l'interface) :

- écouter sur le réseau local ;
- ouvrir Jupyter (qui exécute du code) aux appareils reliés ;
- autoriser l'exécution d'expériences depuis un appareil relié, ou sans accord préalable.

## Vos clés d'API

Gardées dans le trousseau de l'hôte (sinon dans un fichier lisible par vous seul). Jamais renvoyées à l'interface
(elle sait seulement si une clé est enregistrée), jamais écrites dans un journal, jamais envoyées à un autre
fournisseur que le leur.

## Code exécuté sur l'hôte

- **Lean** compile les preuves écrites par les modèles. Les constructions interdites (\`sorry\`, nouveaux axiomes,
  commandes de recherche) sont refusées avant compilation.
- **Lean peut aussi exécuter du code** pendant qu'il lit un fichier : \`#eval\`, \`initialize\`, \`run_cmd\`, des
  tactiques, macros, notations ou élaborateurs définis dans le fichier (\`elab\`, \`macro\`, \`syntax\`, \`notation\`…),
  des attributs qui enregistrent du code, \`unsafe\`, \`implemented_by\`, \`IO\`, \`native_decide\`. Comme le code Lean peut
  venir d'un modèle, du texte d'un article ou d'un appareil relié, Madalean **refuse de compiler** tout fichier qui
  contient l'une de ces constructions (« Refusé avant compilation : … »). Les \`import\` sont limités à Mathlib,
  Aesop, Batteries, Std, Qq, ProofWidgets et Plausible. Le contrôle porte sur les mots, hors commentaires et
  chaînes : il peut refuser à tort un fichier légitime (une variable nommée \`prefix\`, par exemple) ; le message de
  refus indique le genre de construction en cause.
- Ce filtre n'est qu'une première barrière. **Chaque compilation Lean tourne dans un bac à sable** (bubblewrap) :
  sans réseau, sans accès à votre dossier personnel, avec Lean et Mathlib en lecture seule. Les compilations LaTeX
  aussi. « Réglages › Système » indique si le bac à sable est actif ; sans bubblewrap (ou si le système ne le
  permet pas), elles tournent sans cette isolation.
- **Expériences de l'atelier de conjectures** : le code vous est montré, et ne s'exécute qu'après votre accord sur
  **ce code exact**. Il tourne avec des limites de temps, de mémoire et de taille de fichiers, sans vos clés ni
  variables secrètes ; dans le bac à sable, **sans réseau**, avec un système de fichiers en lecture seule où votre
  dossier de configuration, \`~/.ssh\`, vos trousseaux et l'état de Tailscale sont masqués. Les carnets de Calcul
  tournent dans le même bac à sable.
- **Jupyter** (JupyterLab ouvert à part) exécute ce que vous y tapez, comme sur n'importe quelle installation de
  Jupyter : ses noyaux ne sont pas dans le bac à sable.
- Le texte d'un modèle ne devient jamais une commande système.

## Documents venant de l'extérieur

PDF, sources TeX, fichiers BibTeX et réponses de sites peuvent être piégés. Madalean ne compile jamais le TeX d'un
article (il le lit seulement), compile ses propres exports TeX sans aucun accès au shell, limite la taille et le
contenu des archives, et traite le texte des sources comme des **données** : un passage qui dirait « ignore tes
instructions » n'a pas d'effet sur les outils, parce que les réponses fondées sur vos sources n'ont accès à aucun
outil.

## Ce que Madalean ne fait jamais

- Ouvrir un port sur Internet (pas de Funnel Tailscale, pas de redirection de port).
- Lancer \`sudo\`, ou installer un paquet système à votre place.
- Envoyer vos données à un service que vous n'avez pas choisi, ou quoi que ce soit en mode *Local*.
- Afficher une preuve comme vérifiée sans le verdict strict de Lean.
- Publier quoi que ce soit sans que vous ayez validé, élément par élément, ce qui part.
- Installer une mise à jour dont la signature n'est pas valide.

Madalean 2.0 a fait l'objet d'une revue de sécurité indépendante avant sa première publication (ses auteurs n'ont
pas fait la revue) ; ses conclusions et les risques acceptés sont dans \`docs/SECURITY.md\` du dépôt.
`,text:`Sécurité, expliquée simplement Qui peut parler à Madalean Madalean écoute à deux portes, toutes deux fermées vers l'extérieur de l'ordinateur hôte : 1. La porte locale (127.0.0.1:11500), utilisée par le navigateur ou l'application de bureau de l'hôte. Elle n'accepte que des requêtes venant de l'hôte lui-même. 2. La porte des appareils (127.0.0.1:11501), publiée sur votre réseau privé Tailscale. Toute requête doit présenter le jeton d'un appareil relié, sauf la page de liaison elle-même. Une troisième porte, sur le réseau local (port 11502), n'existe que si vous l'ouvrez depuis l'hôte (voir Tailscale › Sans Tailscale) ; elle exige aussi le jeton d'un appareil relié, mais son trafic n'est pas chiffré. Il n'y a pas de compte Madalean, pas de serveur Madalean sur Internet, pas de télémétrie. Les appareils et les codes - Relier un appareil demande un code à 6 chiffres affiché sur l'hôte : valable 5 minutes, utilisable une fois. Cinq codes faux bloquent la liaison 10 minutes ; les essais rapprochés sont freinés. - L'appareil reçoit alors un jeton de 256 bits. L'hôte n'en garde qu'une empreinte (SHA-256) : même quelqu'un qui lirait les fichiers de l'hôte ne pourrait pas en tirer le jeton. - Sur le téléphone, le jeton est dans le stockage protégé d'Android ; sur un PC, dans le trousseau du système ; dans un navigateur, dans un cookie inaccessible aux scripts de la page. - Délier un appareil (« Réglages › Appareils ») coupe son accès immédiatement. Un appareil perdu ou volé : déliez-le depuis l'hôte, et retirez-le de votre réseau Tailscale. Ce qu'un appareil relié ne peut pas faire Certains réglages ouvriraient la machine ; ils ne se changent que depuis l'hôte (cadenas dans l'interface) : - écouter sur le réseau local ; - ouvrir Jupyter (qui exécute du code) aux appareils reliés ; - autoriser l'exécution d'expériences depuis un appareil relié, ou sans accord préalable. Vos clés d'API Gardées dans le trousseau de l'hôte (sinon dans un fichier lisible par vous seul). Jamais renvoyées à l'interface (elle sait seulement si une clé est enregistrée), jamais écrites dans un journal, jamais envoyées à un autre fournisseur que le leur. Code exécuté sur l'hôte - Lean compile les preuves écrites par les modèles. Les constructions interdites (sorry, nouveaux axiomes, commandes de recherche) sont refusées avant compilation. - Lean peut aussi exécuter du code pendant qu'il lit un fichier : #eval, initialize, runcmd, des tactiques, macros, notations ou élaborateurs définis dans le fichier (elab, macro, syntax, notation…), des attributs qui enregistrent du code, unsafe, implementedby, IO, nativedecide. Comme le code Lean peut venir d'un modèle, du texte d'un article ou d'un appareil relié, Madalean refuse de compiler tout fichier qui contient l'une de ces constructions (« Refusé avant compilation : … »). Les import sont limités à Mathlib, Aesop, Batteries, Std, Qq, ProofWidgets et Plausible. Le contrôle porte sur les mots, hors commentaires et chaînes : il peut refuser à tort un fichier légitime (une variable nommée prefix, par exemple) ; le message de refus indique le genre de construction en cause. - Ce filtre n'est qu'une première barrière. Chaque compilation Lean tourne dans un bac à sable (bubblewrap) : sans réseau, sans accès à votre dossier personnel, avec Lean et Mathlib en lecture seule. Les compilations LaTeX aussi. « Réglages › Système » indique si le bac à sable est actif ; sans bubblewrap (ou si le système ne le permet pas), elles tournent sans cette isolation. - Expériences de l'atelier de conjectures : le code vous est montré, et ne s'exécute qu'après votre accord sur ce code exact. Il tourne avec des limites de temps, de mémoire et de taille de fichiers, sans vos clés ni variables secrètes ; dans le bac à sable, sans réseau, avec un système de fichiers en lecture seule où votre dossier de configuration, ~/.ssh, vos trousseaux et l'état de Tailscale sont masqués. Les carnets de Calcul tournent dans le même bac à sable. - Jupyter (JupyterLab ouvert à part) exécute ce que vous y tapez, comme sur n'importe quelle installation de Jupyter : ses noyaux ne sont pas dans le bac à sable. - Le texte d'un modèle ne devient jamais une commande système. Documents venant de l'extérieur PDF, sources TeX, fichiers BibTeX et réponses de sites peuvent être piégés. Madalean ne compile jamais le TeX d'un article (il le lit seulement), compile ses propres exports TeX sans aucun accès au shell, limite la taille et le contenu des archives, et traite le texte des sources comme des données : un passage qui dirait « ignore tes instructions » n'a pas d'effet sur les outils, parce que les réponses fondées sur vos sources n'ont accès à aucun outil. Ce que Madalean ne fait jamais - Ouvrir un port sur Internet (pas de Funnel Tailscale, pas de redirection de port). - Lancer sudo, ou installer un paquet système à votre place. - Envoyer vos données à un service que vous n'avez pas choisi, ou quoi que ce soit en mode Local. - Afficher une preuve comme vérifiée sans le verdict strict de Lean. - Publier quoi que ce soit sans que vous ayez validé, élément par élément, ce qui part. - Installer une mise à jour dont la signature n'est pas valide. Madalean 2.0 a fait l'objet d'une revue de sécurité indépendante avant sa première publication (ses auteurs n'ont pas fait la revue) ; ses conclusions et les risques acceptés sont dans docs/SECURITY.md du dépôt.`},{id:`mcp`,lang:`fr`,title:`Outils MCP : relier Madalean à d'autres assistants`,order:325,section:`settings`,audience:`all`,summary:`Laisser un autre assistant de cet ordinateur utiliser les outils de Madalean, et donner aux modèles de Madalean des outils d'autres programmes — éteint tant que vous ne l'allumez pas.`,source:`fr/mcp.md`,site_path:`fr/mcp.html`,headings:[{level:1,text:`Outils MCP : relier Madalean à d'autres assistants`,id:`outils-mcp-relier-madalean-a-dautres-assistants`},{level:2,text:`Madalean comme serveur MCP`,id:`madalean-comme-serveur-mcp`},{level:2,text:`Serveurs MCP externes`,id:`serveurs-mcp-externes`},{level:3,text:`Exemple : un serveur MCP pour Lean`,id:`exemple-un-serveur-mcp-pour-lean`},{level:2,text:`Le journal des appels`,id:`le-journal-des-appels`}],images:[],verify:[],body:`# Outils MCP : relier Madalean à d'autres assistants

**MCP** (*Model Context Protocol*) est une façon commune, pour les assistants d'IA, d'utiliser les outils d'autres
programmes. Madalean le parle dans les deux sens. Tout se règle dans **Réglages › Outils (MCP)**, sur l'ordinateur
hôte seulement, et tout est **éteint** au départ.

## Madalean comme serveur MCP

Un autre assistant de cet ordinateur (Claude Code, Claude Desktop…) peut alors :

- **chercher dans Mathlib** les noms exacts de la version installée ;
- **vérifier avec Lean** un énoncé, ou une preuve de cet énoncé — avec le verdict strict de Madalean (pas de
  \`sorry\`, pas d'axiome ajouté) ; l'énoncé ne peut pas être changé par la preuve ;
- **certifier** un énoncé calculatoire (Sage calcule un témoin, Lean le vérifie) ;
- **expliquer** une erreur Lean, ou un code ligne par ligne ;
- **chercher dans votre bibliothèque** et voir **l'état de vos dossiers**.

Ces outils **n'enregistrent rien** : pas de dossier créé, pas de résultat ajouté à la bibliothèque.

Pour le brancher :

1. allumez **« Autoriser les applications de cet ordinateur »** ;
2. copiez la commande affichée (Claude Code) ou le bloc JSON (Claude Desktop et les autres clients) ;
3. redémarrez le client. Madalean doit être en marche.

Deux interrupteurs de plus :

- **« Aussi par une adresse locale (HTTP) »** : pour les clients qui se branchent par une adresse
  \`http://127.0.0.1:…\`. Elle n'est ouverte qu'à cet ordinateur ;
- **« Autoriser les calculs Sage »** : le client décrit un calcul en mots (« factoriser x⁴ − 1 sur F₅ ») ; Madalean
  n'exécute que **son propre code vérifié**, dans le noyau isolé. Un code envoyé par le client n'est jamais exécuté.

Les appareils appairés (téléphone, autre ordinateur) n'y ont **jamais** accès.

## Serveurs MCP externes

À l'inverse, vous pouvez donner aux modèles de Madalean des outils d'autres programmes, par exemple un serveur MCP
du langage Lean. Ajoutez-le par sa **commande** (Madalean la lance) ou son **adresse**, puis :

1. **Tester** : Madalean le démarre, lit la liste de ses outils et l'arrête ;
2. **l'activer** ;
3. **cocher** les outils que les modèles peuvent appeler pendant une preuve. Rien n'est coché au départ.

Ce que Madalean fait pour vous protéger :

- les réponses de ces outils sont lues comme des **données**, jamais comme des ordres ; un texte qui essaie de donner
  des ordres au modèle est signalé et mis à l'écart ;
- un outil dont la description donne des ordres au modèle est **refusé** (on ne peut pas le cocher) ;
- le programme ne reçoit **aucune clé d'API**, aucun mot de passe ; chaque appel a une durée et une taille limitées ;
- seul **Lean** décide qu'une preuve est juste : un outil externe ne peut jamais faire passer une preuve.

Un serveur lancé par commande tourne avec **vos droits** : n'ajoutez que des programmes de confiance.

### Exemple : un serveur MCP pour Lean

Le projet \`lean-lsp-mcp\` (à installer vous-même, sans droits d'administrateur, par exemple avec \`uv\`) donne accès au
serveur de langage de Lean. Commande à ajouter : \`uvx lean-lsp-mcp\`. Il lit les fichiers d'un projet Lean : lancez-le
depuis le projet ou indiquez-le dans sa propre configuration (voir sa documentation).

## Le journal des appels

Chaque appel, dans un sens ou dans l'autre, est noté : quand, quel outil, réussi ou non, en combien de temps. Le
journal est en bas de la page, et dans \`logs/mcp-activity.jsonl\` du dossier de configuration.
`,text:`Outils MCP : relier Madalean à d'autres assistants MCP (Model Context Protocol) est une façon commune, pour les assistants d'IA, d'utiliser les outils d'autres programmes. Madalean le parle dans les deux sens. Tout se règle dans Réglages › Outils (MCP), sur l'ordinateur hôte seulement, et tout est éteint au départ. Madalean comme serveur MCP Un autre assistant de cet ordinateur (Claude Code, Claude Desktop…) peut alors : - chercher dans Mathlib les noms exacts de la version installée ; - vérifier avec Lean un énoncé, ou une preuve de cet énoncé — avec le verdict strict de Madalean (pas de sorry, pas d'axiome ajouté) ; l'énoncé ne peut pas être changé par la preuve ; - certifier un énoncé calculatoire (Sage calcule un témoin, Lean le vérifie) ; - expliquer une erreur Lean, ou un code ligne par ligne ; - chercher dans votre bibliothèque et voir l'état de vos dossiers. Ces outils n'enregistrent rien : pas de dossier créé, pas de résultat ajouté à la bibliothèque. Pour le brancher : 1. allumez « Autoriser les applications de cet ordinateur » ; 2. copiez la commande affichée (Claude Code) ou le bloc JSON (Claude Desktop et les autres clients) ; 3. redémarrez le client. Madalean doit être en marche. Deux interrupteurs de plus : - « Aussi par une adresse locale (HTTP) » : pour les clients qui se branchent par une adresse http://127.0.0.1:…. Elle n'est ouverte qu'à cet ordinateur ; - « Autoriser les calculs Sage » : le client décrit un calcul en mots (« factoriser x⁴ − 1 sur F₅ ») ; Madalean n'exécute que son propre code vérifié, dans le noyau isolé. Un code envoyé par le client n'est jamais exécuté. Les appareils appairés (téléphone, autre ordinateur) n'y ont jamais accès. Serveurs MCP externes À l'inverse, vous pouvez donner aux modèles de Madalean des outils d'autres programmes, par exemple un serveur MCP du langage Lean. Ajoutez-le par sa commande (Madalean la lance) ou son adresse, puis : 1. Tester : Madalean le démarre, lit la liste de ses outils et l'arrête ; 2. l'activer ; 3. cocher les outils que les modèles peuvent appeler pendant une preuve. Rien n'est coché au départ. Ce que Madalean fait pour vous protéger : - les réponses de ces outils sont lues comme des données, jamais comme des ordres ; un texte qui essaie de donner des ordres au modèle est signalé et mis à l'écart ; - un outil dont la description donne des ordres au modèle est refusé (on ne peut pas le cocher) ; - le programme ne reçoit aucune clé d'API, aucun mot de passe ; chaque appel a une durée et une taille limitées ; - seul Lean décide qu'une preuve est juste : un outil externe ne peut jamais faire passer une preuve. Un serveur lancé par commande tourne avec vos droits : n'ajoutez que des programmes de confiance. Exemple : un serveur MCP pour Lean Le projet lean-lsp-mcp (à installer vous-même, sans droits d'administrateur, par exemple avec uv) donne accès au serveur de langage de Lean. Commande à ajouter : uvx lean-lsp-mcp. Il lit les fichiers d'un projet Lean : lancez-le depuis le projet ou indiquez-le dans sa propre configuration (voir sa documentation). Le journal des appels Chaque appel, dans un sens ou dans l'autre, est noté : quand, quel outil, réussi ou non, en combien de temps. Le journal est en bas de la page, et dans logs/mcp-activity.jsonl du dossier de configuration.`},{id:`troubleshooting`,lang:`fr`,title:`Dépannage`,order:400,section:`help`,audience:`all`,summary:`Les messages d'erreur en clair, leur cause et quoi faire.`,source:`fr/troubleshooting.md`,site_path:`fr/troubleshooting.html`,headings:[{level:1,text:`Dépannage`,id:`depannage`},{level:2,text:`Installation`,id:`installation`},{level:3,text:`L'installateur .run ne démarre pas`,id:`linstallateur-run-ne-demarre-pas`},{level:3,text:`Aucun navigateur ne s'ouvre`,id:`aucun-navigateur-ne-souvre`},{level:3,text:`Le disque est plein`,id:`le-disque-est-plein`},{level:3,text:`« Échec de micromamba »`,id:`echec-de-micromamba`},{level:3,text:`« Empreinte SHA-256 incorrecte : … »`,id:`empreinte-sha-256-incorrecte`},{level:3,text:`Pas de carte NVIDIA, ou pilote trop ancien`,id:`pas-de-carte-nvidia-ou-pilote-trop-ancien`},{level:3,text:`Le SageMath du système n'est pas retenu`,id:`le-sagemath-du-systeme-nest-pas-retenu`},{level:3,text:`L'export LaTeX échoue`,id:`lexport-latex-echoue`},{level:3,text:`Le service ne démarre pas`,id:`le-service-ne-demarre-pas`},{level:3,text:`Le bac à sable est signalé inactif`,id:`le-bac-a-sable-est-signale-inactif`},{level:2,text:`Connexion et appareils`,id:`connexion-et-appareils`},{level:3,text:`L'appareil ne joint pas l'hôte`,id:`lappareil-ne-joint-pas-lhote`},{level:3,text:`« Cet appareil n'est pas (ou plus) relié »`,id:`cet-appareil-nest-pas-ou-plus-relie`},{level:3,text:`Le certificat HTTPS est refusé, ou la première connexion est très lente`,id:`le-certificat-https-est-refuse-ou-la-premiere-connexion-est-tres-lente`},{level:3,text:`« Réservé à l'ordinateur hôte »`,id:`reserve-a-lordinateur-hote`},{level:2,text:`Modèles`,id:`modeles`},{level:3,text:`« Aucun modèle disponible »`,id:`aucun-modele-disponible`},{level:3,text:`« Le fournisseur refuse la clé »`,id:`le-fournisseur-refuse-la-cle`},{level:3,text:`Le modèle local est lent, ou « mémoire graphique insuffisante »`,id:`le-modele-local-est-lent-ou-memoire-graphique-insuffisante`},{level:3,text:`« Pause : quota atteint » sur un fournisseur gratuit`,id:`pause-quota-atteint-sur-un-fournisseur-gratuit`},{level:2,text:`Lean`,id:`lean`},{level:3,text:`« Lean refuse l'énoncé »`,id:`lean-refuse-lenonce`},{level:3,text:`« Refusé avant compilation : … »`,id:`refuse-avant-compilation`},{level:3,text:`« Pas de preuve trouvée »`,id:`pas-de-preuve-trouvee`},{level:3,text:`« Preuve refusée : contient sorry » ou « axiome non standard »`,id:`preuve-refusee-contient-sorry-ou-axiome-non-standard`},{level:3,text:`« Délai de compilation dépassé »`,id:`delai-de-compilation-depasse`},{level:3,text:`« Espace Lean introuvable » ou « espace non prêt »`,id:`espace-lean-introuvable-ou-espace-non-pret`},{level:3,text:`« Ce dossier a déjà un travail en cours »`,id:`ce-dossier-a-deja-un-travail-en-cours`},{level:2,text:`Export`,id:`export`},{level:3,text:`« Pas de LaTeX sur l'ordinateur hôte : la version HTML s'ouvre »`,id:`pas-de-latex-sur-lordinateur-hote-la-version-html-souvre`},{level:3,text:`Des symboles manquent dans le PDF`,id:`des-symboles-manquent-dans-le-pdf`},{level:2,text:`Jupyter`,id:`jupyter`},{level:3,text:`« Jupyter n'est pas disponible »`,id:`jupyter-nest-pas-disponible`},{level:3,text:`« Jupyter n'est accessible que depuis l'hôte »`,id:`jupyter-nest-accessible-que-depuis-lhote`},{level:2,text:`Quand rien ne va`,id:`quand-rien-ne-va`}],images:[],verify:[],body:`# Dépannage

« Réglages › Système », partie « État de santé », montre l'état de chaque composant (espaces Lean, modèles, TeX,
polices, Jupyter, bac à sable, disque) avec un bouton « Réparer » quand il en existe un. Commencez par là.

## Installation

Le journal complet de l'installation est dans \`~/.local/share/madalean/install.log\`. \`install.sh\` peut être relancé
sans risque : il reprend où il s'était arrêté. Voir [Installer Madalean](install.md).

### L'installateur .run ne démarre pas

- **Rien ne se passe au double-clic, ou « Permission non accordée »** : le fichier n'est pas exécutable. Clic droit ›
  « Propriétés » › « Permissions » › « Autoriser l'exécution du fichier comme un programme », ou dans un terminal
  \`chmod +x Madalean-installer.run\`, puis relancez-le.
- **Le double-clic ouvre le fichier dans un éditeur de texte** : lancez-le depuis un terminal,
  \`./Madalean-installer.run\`.
- **« Fichier abîmé ou modifié (empreinte SHA-256 incorrecte) »** : le fichier a été abîmé pendant le
  téléchargement, ou il est incomplet. Supprimez-le et **téléchargez-le de nouveau** depuis la page des versions ;
  ne contournez jamais ce contrôle.


### Aucun navigateur ne s'ouvre

Sans session graphique, l'installateur passe tout seul à l'assistant en terminal. S'il y a bien un bureau mais
qu'aucun navigateur ne s'ouvre, l'installateur affiche dans le terminal l'adresse de sa page
(\`http://127.0.0.1:…\`, avec sa clé à usage unique) : copiez-la dans un navigateur de la **même** machine. Vous pouvez
aussi forcer l'assistant en terminal : \`./Madalean-installer.run --terminal\` (ou, depuis les sources,
\`./install.sh --assistant\`).

### Le disque est plein

L'étape 1 affiche la place libre. Prévoyez ≈ 6 Go sans modèle local ni SageMath, ≈ 25 Go avec les modèles locaux,
5 Go de plus pour SageMath (voir [Installer Madalean](install.md#ce-quil-faut-avant-de-commencer)). Libérez de la
place, ou réduisez le plan : \`--models none\` (ou \`--models prover\`), \`--sage later\`. Relancez ensuite
\`install.sh\` : ce qui est déjà installé n'est pas refait. Les téléchargements en cours sont gardés dans
\`~/.local/share/madalean/downloads/\` et repris.

### « Échec de micromamba »

L'installation de l'environnement principal (étape 3) a échoué, le plus souvent à cause d'une coupure de réseau ou
d'un disque plein. Les dernières lignes du journal sont affichées ; le détail est dans
\`~/.local/share/madalean/install.log\`. Vérifiez la connexion et la place libre, puis relancez \`install.sh\`.

### « Empreinte SHA-256 incorrecte : … »

Un fichier téléchargé ne correspond pas à l'empreinte attendue : il a été tronqué ou altéré en route. Le fichier
fautif est supprimé ; relancez \`install.sh\`, qui le télécharge de nouveau. Si l'erreur se répète, un proxy ou un
filtre de votre réseau modifie peut-être les téléchargements.

### Pas de carte NVIDIA, ou pilote trop ancien

Ce n'est pas une erreur : Madalean installe alors le moteur des modèles pour le processeur et ne conseille aucun
modèle local. Les modèles en ligne fonctionnent normalement. Si vous avez bien une carte NVIDIA, vérifiez que le
pilote est installé (\`nvidia-smi\` doit répondre), puis relancez \`./install.sh --gpu\`. Voir
[Modèles locaux](components.md#modeles-locaux).

### Le SageMath du système n'est pas retenu

Pour être réutilisé, le SageMath de votre système doit être en version 10.0 ou plus récente **et** fournir son noyau
Jupyter \`sagemath\` (par exemple \`/usr/share/jupyter/kernels/sagemath\`). Sinon, Madalean utilise sa propre copie
(≈ 5 Go). Installez le noyau Jupyter avec votre distribution, ou laissez Madalean installer sa copie. Voir
[SageMath](components.md#sagemath).

### L'export LaTeX échoue

« Réglages › Système », partie « État de santé », ligne « LaTeX (export PDF) » : « Réparer » réinstalle le paquet
TeX. Si vous utilisez le TeX Live du système en premier (\`tex_engine = system\`), il doit être en version 2022 ou plus
récente, avec \`fontspec\`. Voir aussi [Export](#export) plus bas et [LaTeX](components.md#latex).

### Le service ne démarre pas

À la fin de l'installation, « Le serveur ne répond pas encore » signifie que le service n'a pas démarré à temps.
Regardez son journal :

\`\`\`bash
systemctl --user status madalean
journalctl --user -u madalean -e
\`\`\`

Le journal donne la cause (port 11500 déjà pris par un autre programme, composant manquant…). Si \`systemctl --user\`
n'est pas disponible (certains conteneurs ou sessions sans systemd), lancez Madalean à la main :
\`~/.local/share/madalean/current/bin/madalean serve\`.

### Le bac à sable est signalé inactif

bubblewrap n'est pas installé : c'est un paquet de votre distribution, à installer vous-même (par exemple
\`sudo apt install bubblewrap\`). Voir [bubblewrap](components.md#bubblewrap-le-bac-a-sable).

## Connexion et appareils

### L'appareil ne joint pas l'hôte

1. L'ordinateur hôte est-il allumé, et pas en veille ?
2. Tailscale est-il **connecté** sur l'appareil, avec le même compte que l'hôte ? (application Tailscale :
   interrupteur actif.)
3. Le serveur tourne-t-il ? Sur l'hôte : \`systemctl --user status madalean\`.
4. Le nœud Tailscale de Madalean est-il approuvé et en marche ? Sur l'hôte : \`curl -s http://127.0.0.1:11500/api/net\`
   doit indiquer \`"state": "running"\` (sinon, voir [Relier un appareil › Étape 1](pairing.md)). Si vous utilisez le
   Tailscale du système à la place : \`scripts/tailscale_setup.sh --status\`.
5. L'adresse tapée est-elle complète, \`madalean.tailXXXX.ts.net\` (ou \`nom-du-pc.tailXXXX.ts.net:10500\` avec le
   Tailscale du système) ?

### « Cet appareil n'est pas (ou plus) relié »

L'appareil a été délié, ou ses données ont été effacées. Demandez un nouveau code sur l'hôte et reliez-le de nouveau.

### Le certificat HTTPS est refusé, ou la première connexion est très lente

HTTPS n'est pas activé sur votre tailnet : voir [Tailscale › Activer HTTPS](tailscale.md#activer-https). La toute
première connexion peut prendre quelques secondes, le temps d'émettre le certificat.

### « Réservé à l'ordinateur hôte »

Ce réglage ouvre la machine à d'autres appareils ; il ne se change que sur l'hôte. Voir [Sécurité](security.md).

## Modèles

### « Aucun modèle disponible »

- Mode *Local* : aucun modèle local n'est installé ou chargeable. « Réglages › Système » indique lequel manque ;
  \`./install.sh\` télécharge les modèles.
- Mode *En ligne* : pas de réseau, ou tous les fournisseurs sont en pause (quotas). Passez en *Automatique* pour
  utiliser les modèles locaux en secours.

### « Le fournisseur refuse la clé »

La clé a été mal copiée (espace en trop), révoquée, ou le compte n'a plus de crédit. Recréez-la sur le site du
fournisseur et collez-la de nouveau (« Réglages › Fournisseurs ») : Madalean la teste aussitôt. Après un refus de
clé, Madalean met le fournisseur en pause 12 h (« En pause pour l'instant (clé refusée (vérifiez-la)) »). Pour
Hugging Face, un nouveau jeton qui passe le test lève la pause tout de suite ; pour les autres fournisseurs, la pause
va à son terme, puis la nouvelle clé sert normalement.

### Le modèle local est lent, ou « mémoire graphique insuffisante »

Un autre programme occupe la carte graphique (jeu, autre IA). « Réglages › Système » montre la mémoire utilisée par
application. Sans carte NVIDIA, les modèles locaux tournent sur le processeur : comptez des minutes par réponse.

### « Pause : quota atteint » sur un fournisseur gratuit

Normal : Madalean passe au modèle suivant et réessaie le fournisseur plus tard (après l'heure indiquée par le
fournisseur, ou le lendemain pour un quota journalier).

## Lean

### « Lean refuse l'énoncé »

La traduction n'est pas du Lean valide pour cet espace (nom inconnu, notation d'une autre version de Mathlib). Le
message de Lean est affiché sous l'énoncé. « Corriger l'énoncé… » relance la traduction avec l'erreur ; ou
« Modifier à la main ».

### « Refusé avant compilation : … »

Le code contient une construction qui pourrait exécuter du code sur l'hôte (\`#eval\`, \`macro\`, \`elab\`, \`unsafe\`,
\`native_decide\`…) ou un \`import\` hors de Mathlib et de ses dépendances : Madalean refuse de le compiler (voir
[Sécurité](security.md#code-execute-sur-lhote)). Le message donne le genre de construction trouvée, par exemple
« méta-programmation (élaborateur, macro, syntaxe) », « accès au système (IO, unsafe) » ou « import d'un module non
autorisé ». Retirez-la. Si le mot en cause est un simple nom de variable (\`prefix\`, \`syntax\`, \`IO\`…), renommez la
variable.

### « Pas de preuve trouvée »

Les essais sont épuisés. Ce n'est pas une preuve que l'énoncé est faux. Essayez : relire l'énoncé (hypothèse
manquante ?), « Autre méthode », un modèle plus fort (une clé), « Découper en lemmes », ou un indice dans une demande
de suivi (« utilise une récurrence sur $n$ »).

### « Preuve refusée : contient sorry » ou « axiome non standard »

Le verdict strict refuse une preuve incomplète ou qui ajoute un axiome. Seuls \`propext\`, \`Classical.choice\` et
\`Quot.sound\` sont admis.

### « Délai de compilation dépassé »

La compilation a dépassé le temps maximal (« Réglages › Modèles », 10 à 1800 s). Une tactique comme \`simp\` ou
\`nlinarith\` peut chercher longtemps ; une preuve plus explicite compile plus vite.

### « Espace Lean introuvable » ou « espace non prêt »

L'espace de travail n'est pas installé ou sa compilation n'est pas terminée. « Réglages › Espaces Lean » donne son
état ; relancez \`./install.sh\` si besoin.

### « Ce dossier a déjà un travail en cours »

Un dossier n'a qu'un travail actif. Attendez la fin, ou « Arrêter ».

## Export

### « Pas de LaTeX sur l'ordinateur hôte : la version HTML s'ouvre »

Le moteur LaTeX de Madalean (installé par \`./install.sh\`) est absent ou n'a pas pu composer le document, et aucun
LaTeX du système ne l'a remplacé. Le HTML s'imprime en PDF depuis le navigateur. Pour le vrai PDF : « Réglages ›
Système », partie « État de santé », ligne LaTeX, bouton « Réparer » (ou relancez \`./install.sh\`).

### Des symboles manquent dans le PDF

Les polices DejaVu Sans Mono et Noto Sans Math sont installées avec Madalean ; « Réglages › Système » vérifie
qu'elles sont présentes. Relancez \`./install.sh\` si l'une manque.

## Jupyter

### « Jupyter n'est pas disponible »

JupyterLab (installé avec Madalean) est absent ou n'a pas démarré. « Réglages › Système » donne la cause, avec un
bouton « Réparer ».

### « Jupyter n'est accessible que depuis l'hôte »

L'hôte n'a pas ouvert Jupyter aux appareils reliés (« Réglages › Carnet et accès », sur l'hôte).

## Quand rien ne va

\`\`\`bash
systemctl --user restart madalean
journalctl --user -u madalean -e
\`\`\`

Le journal ne contient ni clé, ni jeton : vous pouvez le joindre à un signalement de problème.
`,text:`Dépannage « Réglages › Système », partie « État de santé », montre l'état de chaque composant (espaces Lean, modèles, TeX, polices, Jupyter, bac à sable, disque) avec un bouton « Réparer » quand il en existe un. Commencez par là. Installation Le journal complet de l'installation est dans ~/.local/share/madalean/install.log. install.sh peut être relancé sans risque : il reprend où il s'était arrêté. Voir Installer Madalean. L'installateur .run ne démarre pas - Rien ne se passe au double-clic, ou « Permission non accordée » : le fichier n'est pas exécutable. Clic droit › « Propriétés » › « Permissions » › « Autoriser l'exécution du fichier comme un programme », ou dans un terminal chmod +x Madalean-installer.run, puis relancez-le. - Le double-clic ouvre le fichier dans un éditeur de texte : lancez-le depuis un terminal, ./Madalean-installer.run. - « Fichier abîmé ou modifié (empreinte SHA-256 incorrecte) » : le fichier a été abîmé pendant le téléchargement, ou il est incomplet. Supprimez-le et téléchargez-le de nouveau depuis la page des versions ; ne contournez jamais ce contrôle. Aucun navigateur ne s'ouvre Sans session graphique, l'installateur passe tout seul à l'assistant en terminal. S'il y a bien un bureau mais qu'aucun navigateur ne s'ouvre, l'installateur affiche dans le terminal l'adresse de sa page (http://127.0.0.1:…, avec sa clé à usage unique) : copiez-la dans un navigateur de la même machine. Vous pouvez aussi forcer l'assistant en terminal : ./Madalean-installer.run --terminal (ou, depuis les sources, ./install.sh --assistant). Le disque est plein L'étape 1 affiche la place libre. Prévoyez ≈ 6 Go sans modèle local ni SageMath, ≈ 25 Go avec les modèles locaux, 5 Go de plus pour SageMath (voir Installer Madalean). Libérez de la place, ou réduisez le plan : --models none (ou --models prover), --sage later. Relancez ensuite install.sh : ce qui est déjà installé n'est pas refait. Les téléchargements en cours sont gardés dans ~/.local/share/madalean/downloads/ et repris. « Échec de micromamba » L'installation de l'environnement principal (étape 3) a échoué, le plus souvent à cause d'une coupure de réseau ou d'un disque plein. Les dernières lignes du journal sont affichées ; le détail est dans ~/.local/share/madalean/install.log. Vérifiez la connexion et la place libre, puis relancez install.sh. « Empreinte SHA-256 incorrecte : … » Un fichier téléchargé ne correspond pas à l'empreinte attendue : il a été tronqué ou altéré en route. Le fichier fautif est supprimé ; relancez install.sh, qui le télécharge de nouveau. Si l'erreur se répète, un proxy ou un filtre de votre réseau modifie peut-être les téléchargements. Pas de carte NVIDIA, ou pilote trop ancien Ce n'est pas une erreur : Madalean installe alors le moteur des modèles pour le processeur et ne conseille aucun modèle local. Les modèles en ligne fonctionnent normalement. Si vous avez bien une carte NVIDIA, vérifiez que le pilote est installé (nvidia-smi doit répondre), puis relancez ./install.sh --gpu. Voir Modèles locaux. Le SageMath du système n'est pas retenu Pour être réutilisé, le SageMath de votre système doit être en version 10.0 ou plus récente et fournir son noyau Jupyter sagemath (par exemple /usr/share/jupyter/kernels/sagemath). Sinon, Madalean utilise sa propre copie (≈ 5 Go). Installez le noyau Jupyter avec votre distribution, ou laissez Madalean installer sa copie. Voir SageMath. L'export LaTeX échoue « Réglages › Système », partie « État de santé », ligne « LaTeX (export PDF) » : « Réparer » réinstalle le paquet TeX. Si vous utilisez le TeX Live du système en premier (texengine = system), il doit être en version 2022 ou plus récente, avec fontspec. Voir aussi Export plus bas et LaTeX. Le service ne démarre pas À la fin de l'installation, « Le serveur ne répond pas encore » signifie que le service n'a pas démarré à temps. Regardez son journal : Le journal donne la cause (port 11500 déjà pris par un autre programme, composant manquant…). Si systemctl --user n'est pas disponible (certains conteneurs ou sessions sans systemd), lancez Madalean à la main : ~/.local/share/madalean/current/bin/madalean serve. Le bac à sable est signalé inactif bubblewrap n'est pas installé : c'est un paquet de votre distribution, à installer vous-même (par exemple sudo apt install bubblewrap). Voir bubblewrap. Connexion et appareils L'appareil ne joint pas l'hôte 1. L'ordinateur hôte est-il allumé, et pas en veille ? 2. Tailscale est-il connecté sur l'appareil, avec le même compte que l'hôte ? (application Tailscale : interrupteur actif.) 3. Le serveur tourne-t-il ? Sur l'hôte : systemctl --user status madalean. 4. Le nœud Tailscale de Madalean est-il approuvé et en marche ? Sur l'hôte : curl -s http://127.0.0.1:11500/api/net doit indiquer "state": "running" (sinon, voir Relier un appareil › Étape 1). Si vous utilisez le Tailscale du système à la place : scripts/tailscalesetup.sh --status. 5. L'adresse tapée est-elle complète, madalean.tailXXXX.ts.net (ou nom-du-pc.tailXXXX.ts.net:10500 avec le Tailscale du système) ? « Cet appareil n'est pas (ou plus) relié » L'appareil a été délié, ou ses données ont été effacées. Demandez un nouveau code sur l'hôte et reliez-le de nouveau. Le certificat HTTPS est refusé, ou la première connexion est très lente HTTPS n'est pas activé sur votre tailnet : voir Tailscale › Activer HTTPS. La toute première connexion peut prendre quelques secondes, le temps d'émettre le certificat. « Réservé à l'ordinateur hôte » Ce réglage ouvre la machine à d'autres appareils ; il ne se change que sur l'hôte. Voir Sécurité. Modèles « Aucun modèle disponible » - Mode Local : aucun modèle local n'est installé ou chargeable. « Réglages › Système » indique lequel manque ; ./install.sh télécharge les modèles. - Mode En ligne : pas de réseau, ou tous les fournisseurs sont en pause (quotas). Passez en Automatique pour utiliser les modèles locaux en secours. « Le fournisseur refuse la clé » La clé a été mal copiée (espace en trop), révoquée, ou le compte n'a plus de crédit. Recréez-la sur le site du fournisseur et collez-la de nouveau (« Réglages › Fournisseurs ») : Madalean la teste aussitôt. Après un refus de clé, Madalean met le fournisseur en pause 12 h (« En pause pour l'instant (clé refusée (vérifiez-la)) »). Pour Hugging Face, un nouveau jeton qui passe le test lève la pause tout de suite ; pour les autres fournisseurs, la pause va à son terme, puis la nouvelle clé sert normalement. Le modèle local est lent, ou « mémoire graphique insuffisante » Un autre programme occupe la carte graphique (jeu, autre IA). « Réglages › Système » montre la mémoire utilisée par application. Sans carte NVIDIA, les modèles locaux tournent sur le processeur : comptez des minutes par réponse. « Pause : quota atteint » sur un fournisseur gratuit Normal : Madalean passe au modèle suivant et réessaie le fournisseur plus tard (après l'heure indiquée par le fournisseur, ou le lendemain pour un quota journalier). Lean « Lean refuse l'énoncé » La traduction n'est pas du Lean valide pour cet espace (nom inconnu, notation d'une autre version de Mathlib). Le message de Lean est affiché sous l'énoncé. « Corriger l'énoncé… » relance la traduction avec l'erreur ; ou « Modifier à la main ». « Refusé avant compilation : … » Le code contient une construction qui pourrait exécuter du code sur l'hôte (#eval, macro, elab, unsafe, nativedecide…) ou un import hors de Mathlib et de ses dépendances : Madalean refuse de le compiler (voir Sécurité). Le message donne le genre de construction trouvée, par exemple « méta-programmation (élaborateur, macro, syntaxe) », « accès au système (IO, unsafe) » ou « import d'un module non autorisé ». Retirez-la. Si le mot en cause est un simple nom de variable (prefix, syntax, IO…), renommez la variable. « Pas de preuve trouvée » Les essais sont épuisés. Ce n'est pas une preuve que l'énoncé est faux. Essayez : relire l'énoncé (hypothèse manquante ?), « Autre méthode », un modèle plus fort (une clé), « Découper en lemmes », ou un indice dans une demande de suivi (« utilise une récurrence sur $n$ »). « Preuve refusée : contient sorry » ou « axiome non standard » Le verdict strict refuse une preuve incomplète ou qui ajoute un axiome. Seuls propext, Classical.choice et Quot.sound sont admis. « Délai de compilation dépassé » La compilation a dépassé le temps maximal (« Réglages › Modèles », 10 à 1800 s). Une tactique comme simp ou nlinarith peut chercher longtemps ; une preuve plus explicite compile plus vite. « Espace Lean introuvable » ou « espace non prêt » L'espace de travail n'est pas installé ou sa compilation n'est pas terminée. « Réglages › Espaces Lean » donne son état ; relancez ./install.sh si besoin. « Ce dossier a déjà un travail en cours » Un dossier n'a qu'un travail actif. Attendez la fin, ou « Arrêter ». Export « Pas de LaTeX sur l'ordinateur hôte : la version HTML s'ouvre » Le moteur LaTeX de Madalean (installé par ./install.sh) est absent ou n'a pas pu composer le document, et aucun LaTeX du système ne l'a remplacé. Le HTML s'imprime en PDF depuis le navigateur. Pour le vrai PDF : « Réglages › Système », partie « État de santé », ligne LaTeX, bouton « Réparer » (ou relancez ./install.sh). Des symboles manquent dans le PDF Les polices DejaVu Sans Mono et Noto Sans Math sont installées avec Madalean ; « Réglages › Système » vérifie qu'elles sont présentes. Relancez ./install.sh si l'une manque. Jupyter « Jupyter n'est pas disponible » JupyterLab (installé avec Madalean) est absent ou n'a pas démarré. « Réglages › Système » donne la cause, avec un bouton « Réparer ». « Jupyter n'est accessible que depuis l'hôte » L'hôte n'a pas ouvert Jupyter aux appareils reliés (« Réglages › Carnet et accès », sur l'hôte). Quand rien ne va Le journal ne contient ni clé, ni jeton : vous pouvez le joindre à un signalement de problème.`},{id:`glossary`,lang:`fr`,title:`Glossaire Lean`,order:410,section:`reference`,audience:`learner`,summary:`Le vocabulaire de Lean et de Mathlib nécessaire pour lire les énoncés et les preuves.`,source:`fr/glossary.md`,site_path:`fr/glossary.html`,headings:[{level:1,text:`Glossaire Lean`,id:`glossaire-lean`},{level:2,text:`Logique et notations`,id:`logique-et-notations`},{level:2,text:`Déclarations`,id:`declarations`},{level:2,text:`Arguments`,id:`arguments`},{level:2,text:`Types et univers`,id:`types-et-univers`},{level:2,text:`Preuves`,id:`preuves`},{level:2,text:`Écosystème`,id:`ecosysteme`}],images:[],verify:[],body:"# Glossaire Lean\n\nLes termes sont groupés par thème. Pour les tactiques, voir [Premières tactiques](tactics.md).\n\nDans l'application, l'écran **Glossaire** reprend ces termes et bien d'autres (environ 250, classés par catégorie\net par niveau débutant / intermédiaire / avancé), avec pour chacun le sens, la forme Lean, un petit exemple, les\nentrées liées, les déclarations Mathlib correspondantes et vos dossiers qui l'utilisent. Il sert aussi d'aide au\nsurvol des énoncés en mode Apprendre.\n\n## Logique et notations\n\n| Lean | Se lit | Remarque |\n|---|---|---|\n| `∀ x, P x` | pour tout $x$, $P(x)$ | `∀ x > 0, …` abrège `∀ x, x > 0 → …` |\n| `∃ x, P x` | il existe $x$ tel que $P(x)$ | `∃! x, P x` : il existe un unique $x$ |\n| `P → Q` | $P$ implique $Q$ | aussi le type des fonctions de `P` vers `Q` |\n| `P ↔ Q` | $P$ si et seulement si $Q$ | |\n| `P ∧ Q`, `P ∨ Q` | et, ou | |\n| `¬ P` | non $P$ | défini comme `P → False` |\n| `a ≠ b` | $a \\neq b$ | abrège `¬ (a = b)` |\n| `True`, `False` | le vrai, le faux | propositions |\n| `a ∣ b` | $a$ divise $b$ | barre verticale spéciale, tapée `\\mid` ; ce n'est pas la barre `\\|` du clavier |\n| `a % b` | reste de la division | |\n| `x⁻¹` | inverse | `0⁻¹ = 0` dans un corps |\n| `↑n`, `(n : ℝ)` | $n$ vu dans un autre type | conversion (*coercion*) |\n| `fun x => e` | $x \\mapsto e$ | aussi écrit `λ x => e` ou `fun x ↦ e` |\n| `f x` | $f(x)$ | l'application s'écrit sans parenthèses |\n| `∑ i in s, f i` | $\\sum_{i \\in s} f(i)$ | `∑ i ∈ s, f i` dans les versions récentes |\n| `∏ i in s, f i` | $\\prod_{i \\in s} f(i)$ | idem |\n| `Finset.range n` | $\\{0, \\dots, n-1\\}$ | |\n| `Finset.Icc a b` | $\\{a, \\dots, b\\}$ | aussi `Ico`, `Ioc`, `Ioo` |\n| `\\|x\\|` | valeur absolue | |\n| `⌊x⌋`, `⌈x⌉` | partie entière, plafond | `Int.floor`, `Int.ceil` |\n\n## Déclarations\n\n| Terme | Sens |\n|---|---|\n| `theorem`, `lemma` | un énoncé avec sa preuve (Madalean normalise `lemma` en `theorem`) |\n| `example` | un théorème sans nom |\n| `def` | une définition |\n| `abbrev` | une définition que Lean déplie volontiers |\n| `structure`, `class`, `instance` | types à champs ; classes de types (« ℝ est un corps ») et leurs instances |\n| `axiom` | un énoncé admis sans preuve ; interdit dans une preuve acceptée par Madalean |\n| `sorry` | « preuve à compléter » : Lean accepte provisoirement, mais signale un trou |\n| `variable` | déclare des variables communes à plusieurs énoncés |\n| `namespace X … end X` | préfixe les noms : `X.foo` |\n| `open X` | permet d'écrire `foo` au lieu de `X.foo` |\n| `import` | charge une bibliothèque (`import Mathlib`) |\n| `#check e` | affiche le type de `e` |\n| `#eval e` | calcule `e` |\n\n## Arguments\n\n| Écriture | Sens |\n|---|---|\n| `(x : α)` | argument explicite, à donner |\n| `{x : α}` | argument implicite, deviné par Lean |\n| `[inst : Field α]` | argument d'instance, trouvé par Lean (« α est un corps ») |\n| `(h : P)` | une hypothèse nommée `h` ; une preuve de `P` |\n\n## Types et univers\n\n| Terme | Sens |\n|---|---|\n| `Prop` | le type des propositions ; une preuve de `P : Prop` est un terme de type `P` |\n| `Type` | le type des types « ordinaires » (`ℕ : Type`) |\n| `ℕ`, `ℤ`, `ℚ`, `ℝ`, `ℂ` | entiers naturels (avec 0), relatifs, rationnels, réels, complexes |\n| `Fin n` | $\\{0, \\dots, n-1\\}$ comme type |\n| `Set α`, `Finset α` | parties de `α` ; parties finies (calculables) |\n| `α × β` | produit cartésien ; `p.1`, `p.2` les composantes |\n| `List α` | listes |\n| `Polynomial R` (`R[X]`) | polynômes à coefficients dans `R` |\n| `Matrix m n R` | matrices |\n\n## Preuves\n\n| Terme | Sens |\n|---|---|\n| but (*goal*) | ce qu'il reste à prouver, affiché `⊢ P` |\n| hypothèse | ce qui est supposé, au-dessus du `⊢` |\n| tactique | une instruction qui transforme le but (`intro`, `simp`…) |\n| `by` | passe en mode tactique |\n| mode terme | une preuve écrite comme un terme : `fun h => h.1` |\n| `h.1`, `h.2` | les deux parties d'une hypothèse `h : P ∧ Q` |\n| `⟨a, b⟩` | construit un couple, une conjonction, ou un témoin avec sa preuve |\n| `·` | ouvre le traitement d'un des buts |\n| `<;>` | applique la tactique suivante à tous les buts produits |\n| `rfl` | « par définition » : les deux côtés sont égaux après calcul |\n\n## Écosystème\n\n| Terme | Sens |\n|---|---|\n| Lean 4 | le langage et le vérificateur de preuves |\n| Mathlib | la bibliothèque mathématique de la communauté (≈ 290 000 déclarations dans une version récente) |\n| noyau (*kernel*) | la petite partie de Lean qui vérifie réellement les preuves |\n| axiomes standard | `propext`, `Classical.choice`, `Quot.sound` : admis par Mathlib et par Madalean |\n| Lake | l'outil de construction des projets Lean (`lake build`) |\n| elan | le gestionnaire de versions de Lean |\n| toolchain | une version précise de Lean, fixée par le fichier `lean-toolchain` d'un projet |\n| espace de travail | dans Madalean, un projet Lake avec une version de Lean et de Mathlib |\n| blueprint | le graphe des énoncés d'un projet de formalisation et de leurs dépendances |\n",text:`Glossaire Lean Les termes sont groupés par thème. Pour les tactiques, voir Premières tactiques. Dans l'application, l'écran Glossaire reprend ces termes et bien d'autres (environ 250, classés par catégorie et par niveau débutant / intermédiaire / avancé), avec pour chacun le sens, la forme Lean, un petit exemple, les entrées liées, les déclarations Mathlib correspondantes et vos dossiers qui l'utilisent. Il sert aussi d'aide au survol des énoncés en mode Apprendre. Logique et notations Lean Se lit Remarque ∀ x, P x pour tout $x$, $P(x)$ ∀ x > 0, … abrège ∀ x, x > 0 → … ∃ x, P x il existe $x$ tel que $P(x)$ ∃! x, P x : il existe un unique $x$ P → Q $P$ implique $Q$ aussi le type des fonctions de P vers Q P ↔ Q $P$ si et seulement si $Q$ P ∧ Q, P ∨ Q et, ou ¬ P non $P$ défini comme P → False a ≠ b $a \\neq b$ abrège ¬ (a = b) True, False le vrai, le faux propositions a ∣ b $a$ divise $b$ barre verticale spéciale, tapée \\mid ; ce n'est pas la barre du clavier a % b reste de la division x⁻¹ inverse 0⁻¹ = 0 dans un corps ↑n, (n : ℝ) $n$ vu dans un autre type conversion (coercion) fun x => e $x \\mapsto e$ aussi écrit λ x => e ou fun x ↦ e f x $f(x)$ l'application s'écrit sans parenthèses ∑ i in s, f i $\\sum{i \\in s} f(i)$ ∑ i ∈ s, f i dans les versions récentes ∏ i in s, f i $\\prod{i \\in s} f(i)$ idem Finset.range n $\\{0, \\dots, n-1\\}$ Finset.Icc a b $\\{a, \\dots, b\\}$ aussi Ico, Ioc, Ioo x valeur absolue ⌊x⌋, ⌈x⌉ partie entière, plafond Int.floor, Int.ceil Déclarations Terme Sens theorem, lemma un énoncé avec sa preuve (Madalean normalise lemma en theorem) example un théorème sans nom def une définition abbrev une définition que Lean déplie volontiers structure, class, instance types à champs ; classes de types (« ℝ est un corps ») et leurs instances axiom un énoncé admis sans preuve ; interdit dans une preuve acceptée par Madalean sorry « preuve à compléter » : Lean accepte provisoirement, mais signale un trou variable déclare des variables communes à plusieurs énoncés namespace X … end X préfixe les noms : X.foo open X permet d'écrire foo au lieu de X.foo import charge une bibliothèque (import Mathlib) #check e affiche le type de e #eval e calcule e Arguments Écriture Sens (x : α) argument explicite, à donner {x : α} argument implicite, deviné par Lean [inst : Field α] argument d'instance, trouvé par Lean (« α est un corps ») (h : P) une hypothèse nommée h ; une preuve de P Types et univers Terme Sens Prop le type des propositions ; une preuve de P : Prop est un terme de type P Type le type des types « ordinaires » (ℕ : Type) ℕ, ℤ, ℚ, ℝ, ℂ entiers naturels (avec 0), relatifs, rationnels, réels, complexes Fin n $\\{0, \\dots, n-1\\}$ comme type Set α, Finset α parties de α ; parties finies (calculables) α × β produit cartésien ; p.1, p.2 les composantes List α listes Polynomial R (R[X]) polynômes à coefficients dans R Matrix m n R matrices Preuves Terme Sens but (goal) ce qu'il reste à prouver, affiché ⊢ P hypothèse ce qui est supposé, au-dessus du ⊢ tactique une instruction qui transforme le but (intro, simp…) by passe en mode tactique mode terme une preuve écrite comme un terme : fun h => h.1 h.1, h.2 les deux parties d'une hypothèse h : P ∧ Q ⟨a, b⟩ construit un couple, une conjonction, ou un témoin avec sa preuve · ouvre le traitement d'un des buts <;> applique la tactique suivante à tous les buts produits rfl « par définition » : les deux côtés sont égaux après calcul Écosystème Terme Sens Lean 4 le langage et le vérificateur de preuves Mathlib la bibliothèque mathématique de la communauté (≈ 290 000 déclarations dans une version récente) noyau (kernel) la petite partie de Lean qui vérifie réellement les preuves axiomes standard propext, Classical.choice, Quot.sound : admis par Mathlib et par Madalean Lake l'outil de construction des projets Lean (lake build) elan le gestionnaire de versions de Lean toolchain une version précise de Lean, fixée par le fichier lean-toolchain d'un projet espace de travail dans Madalean, un projet Lake avec une version de Lean et de Mathlib blueprint le graphe des énoncés d'un projet de formalisation et de leurs dépendances`},{id:`tactics`,lang:`fr`,title:`Premières tactiques`,order:420,section:`reference`,audience:`learner`,summary:`Ce que font les tactiques les plus courantes de Lean 4 et Mathlib, avec un exemple chacune, et quand elles échouent.`,source:`fr/tactics.md`,site_path:`fr/tactics.html`,headings:[{level:1,text:`Premières tactiques`,id:`premieres-tactiques`},{level:2,text:`Structurer`,id:`structurer`},{level:2,text:`Récurrence et cas`,id:`recurrence-et-cas`},{level:2,text:`Réécrire et simplifier`,id:`reecrire-et-simplifier`},{level:2,text:`Arithmétique et inégalités`,id:`arithmetique-et-inegalites`},{level:2,text:`Chercher`,id:`chercher`},{level:2,text:`Lire une erreur`,id:`lire-une-erreur`}],images:[],verify:[],body:"# Premières tactiques\n\nUne preuve en mode tactique (`:= by …`) est une suite d'instructions qui transforment le **but** (ce qui reste à\nprouver, affiché après `⊢`) jusqu'à ce qu'il n'en reste plus. Les exemples supposent `import Mathlib`. Le\ncomportement exact d'une tactique dépend de la version de Mathlib ; ce qui suit vaut pour les deux espaces de\nMadalean, sauf mention.\n\n## Structurer\n\n| Tactique | Effet | Exemple de but |\n|---|---|---|\n| `intro x` | introduit une variable ou une hypothèse : pour `∀ x, P x` ou `P → Q` | `⊢ ∀ n : ℕ, n + 0 = n` → `intro n` |\n| `exact e` | ferme le but avec un terme exactement du bon type | `exact ha` quand `ha : P` et `⊢ P` |\n| `apply f` | réduit le but aux hypothèses de `f` | `⊢ 0 < a * b` → `apply mul_pos` laisse `0 < a` et `0 < b` |\n| `refine ⟨?_, ?_⟩` | comme `exact`, avec des trous `?_` qui deviennent des buts | |\n| `constructor` | découpe `P ∧ Q` (deux buts) ou `P ↔ Q` (les deux sens) | |\n| `use 3` | fournit le témoin d'un `∃` | `⊢ ∃ n : ℕ, n * n = 9` → `use 3` |\n| `obtain ⟨x, hx⟩ := h` | déballe `h : ∃ x, P x` (ou `h : P ∧ Q`) | |\n| `rcases h with h1 \\| h2` | cas d'une disjonction `h : P ∨ Q` | |\n| `left`, `right` | choisit un côté d'un `∨` à prouver | |\n| `have h : P := by …` | prouve un résultat intermédiaire et l'ajoute aux hypothèses | |\n| `show P` | réécrit le but sous une forme égale par définition (lisibilité) | |\n| `specialize h 2` | applique une hypothèse universelle à une valeur | |\n| `exfalso` | remplace le but par `False` | |\n| `by_contra h` | raisonnement par l'absurde : ajoute la négation du but | |\n| `push_neg` | pousse les négations vers l'intérieur : `¬ ∀ x, P x` devient `∃ x, ¬ P x` | |\n| `contradiction` | ferme le but si les hypothèses se contredisent directement | `h : P` et `h' : ¬ P` |\n\n## Récurrence et cas\n\n```lean\ntheorem somme_impairs (n : ℕ) : ∑ i in Finset.range n, (2 * i + 1) = n ^ 2 := by\n  induction n with\n  | zero => simp\n  | succ n ih =>\n    rw [Finset.sum_range_succ, ih]\n    ring\n```\n\n`induction n with | zero => … | succ n ih => …` produit le cas de base et l'hérédité ; `ih` est l'hypothèse de\nrécurrence. `rcases`/`cases` traitent les cas d'un type inductif ou d'une disjonction ; `interval_cases n` énumère\nles valeurs d'un entier borné par les hypothèses. (Dans l'espace « Lean actuel », écrivez `∑ i ∈ Finset.range n`.)\n\n## Réécrire et simplifier\n\n| Tactique | Effet | Échoue quand |\n|---|---|---|\n| `rw [h]` | remplace le membre gauche de `h : a = b` par le membre droit dans le but ; `rw [← h]` dans l'autre sens ; `rw [h] at h'` dans une hypothèse | le motif n'apparaît pas tel quel dans le but |\n| `simp` | simplifie avec les lemmes marqués `@[simp]` de Mathlib ; ferme le but s'il devient trivial | il n'y a rien à simplifier |\n| `simp only [a, b]` | simplifie avec ces lemmes seulement : plus prévisible et plus rapide | |\n| `simp at h` | simplifie une hypothèse | |\n| `norm_num` | calcule sur des nombres explicites : `2 ^ 10 = 1024`, `(7 : ℝ) / 2 > 3`, `Nat.Prime 97` | le but contient des variables qu'il ne sait pas éliminer |\n| `field_simp` | chasse les dénominateurs dans un corps (demande souvent `h : x ≠ 0`) | |\n| `unfold f` | déplie une définition | |\n| `ext x` | égalité de fonctions ou d'ensembles : se ramène à tout `x` | |\n\n## Arithmétique et inégalités\n\n| Tactique | Domaine | Ne fait pas |\n|---|---|---|\n| `ring` | égalités dans un anneau commutatif : `(a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2` | les inégalités ; les égalités qui demandent une hypothèse |\n| `linarith` | combinaisons **linéaires** d'hypothèses et d'inégalités, sur un corps ordonné (`ℚ`, `ℝ`) ; marche aussi souvent sur `ℕ` et `ℤ` | les produits de variables |\n| `nlinarith` | comme `linarith`, en ajoutant des produits d'hypothèses ; on l'aide en donnant des faits : `nlinarith [sq_nonneg (a - b)]` | garantie : c'est une heuristique |\n| `positivity` | buts `0 < e`, `0 ≤ e`, `e ≠ 0` quand la forme de `e` le montre (carrés, sommes de positifs, exponentielles…) | utiliser des hypothèses compliquées |\n| `omega` | arithmétique linéaire **exacte** sur `ℕ` et `ℤ`, avec `/` et `%` par des constantes | les produits de variables ; les réels |\n| `decide` | propositions décidables sur des valeurs **concrètes** : `Nat.Prime 7` si l'instance le permet, `2 ∣ 10` | les variables libres ; les grands calculs (lent) |\n| `gcongr` | « même forme des deux côtés » : `a ≤ b → a + c ≤ b + c`, laisse les comparaisons des morceaux | |\n\nExemple :\n\n```lean\ntheorem am_gm_deux (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by\n  nlinarith [sq_nonneg (a - b)]\n```\n\nIci $a^2 + b^2 - 2ab = (a-b)^2 \\ge 0$ : le fait donné à `nlinarith` suffit, la combinaison est linéaire en ce fait.\n\n## Chercher\n\n| Tactique | Effet |\n|---|---|\n| `exact?` | cherche dans Mathlib un lemme qui ferme le but et propose `exact …` |\n| `apply?` | propose des lemmes applicables |\n| `aesop` | recherche automatique de preuve (règles et `simp`) |\n| `tauto` | logique propositionnelle |\n\nMadalean **refuse `exact?` et `apply?` dans une preuve finale** : ce sont des outils de recherche, à remplacer par le\nlemme qu'ils trouvent. Ils restent utiles dans un carnet ou un bloc Lean d'une note.\n\n## Lire une erreur\n\n| Message de Lean | Sens habituel |\n|---|---|\n| `unknown identifier 'foo'` / `unknown constant` | le nom n'existe pas dans cette version de Mathlib (renommé, ou inventé par le modèle) |\n| `type mismatch` | le terme n'a pas le type attendu : souvent une conversion `ℕ`/`ℝ` manquante |\n| `unsolved goals` | la preuve s'arrête alors qu'il reste des buts (affichés) |\n| `linarith failed` | les hypothèses données ne suffisent pas linéairement : ajoutez des faits |\n| `motive is not type correct` | `rw` ne peut pas réécrire à cet endroit ; essayez `simp only` ou `conv` |\n| `maximum recursion depth` / `deterministic timeout` | une tactique cherche trop longtemps : rendez la preuve plus explicite |\n| `declaration uses 'sorry'` | la preuve contient un trou : elle n'est pas acceptée |\n",text:`Premières tactiques Une preuve en mode tactique (:= by …) est une suite d'instructions qui transforment le but (ce qui reste à prouver, affiché après ⊢) jusqu'à ce qu'il n'en reste plus. Les exemples supposent import Mathlib. Le comportement exact d'une tactique dépend de la version de Mathlib ; ce qui suit vaut pour les deux espaces de Madalean, sauf mention. Structurer Tactique Effet Exemple de but intro x introduit une variable ou une hypothèse : pour ∀ x, P x ou P → Q ⊢ ∀ n : ℕ, n + 0 = n → intro n exact e ferme le but avec un terme exactement du bon type exact ha quand ha : P et ⊢ P apply f réduit le but aux hypothèses de f ⊢ 0 < a b → apply mulpos laisse 0 < a et 0 < b refine ⟨?, ?⟩ comme exact, avec des trous ? qui deviennent des buts constructor découpe P ∧ Q (deux buts) ou P ↔ Q (les deux sens) use 3 fournit le témoin d'un ∃ ⊢ ∃ n : ℕ, n n = 9 → use 3 obtain ⟨x, hx⟩ := h déballe h : ∃ x, P x (ou h : P ∧ Q) rcases h with h1 h2 cas d'une disjonction h : P ∨ Q left, right choisit un côté d'un ∨ à prouver have h : P := by … prouve un résultat intermédiaire et l'ajoute aux hypothèses show P réécrit le but sous une forme égale par définition (lisibilité) specialize h 2 applique une hypothèse universelle à une valeur exfalso remplace le but par False bycontra h raisonnement par l'absurde : ajoute la négation du but pushneg pousse les négations vers l'intérieur : ¬ ∀ x, P x devient ∃ x, ¬ P x contradiction ferme le but si les hypothèses se contredisent directement h : P et h' : ¬ P Récurrence et cas induction n with zero => … succ n ih => … produit le cas de base et l'hérédité ; ih est l'hypothèse de récurrence. rcases/cases traitent les cas d'un type inductif ou d'une disjonction ; intervalcases n énumère les valeurs d'un entier borné par les hypothèses. (Dans l'espace « Lean actuel », écrivez ∑ i ∈ Finset.range n.) Réécrire et simplifier Tactique Effet Échoue quand rw [h] remplace le membre gauche de h : a = b par le membre droit dans le but ; rw [← h] dans l'autre sens ; rw [h] at h' dans une hypothèse le motif n'apparaît pas tel quel dans le but simp simplifie avec les lemmes marqués @[simp] de Mathlib ; ferme le but s'il devient trivial il n'y a rien à simplifier simp only [a, b] simplifie avec ces lemmes seulement : plus prévisible et plus rapide simp at h simplifie une hypothèse normnum calcule sur des nombres explicites : 2 ^ 10 = 1024, (7 : ℝ) / 2 > 3, Nat.Prime 97 le but contient des variables qu'il ne sait pas éliminer fieldsimp chasse les dénominateurs dans un corps (demande souvent h : x ≠ 0) unfold f déplie une définition ext x égalité de fonctions ou d'ensembles : se ramène à tout x Arithmétique et inégalités Tactique Domaine Ne fait pas ring égalités dans un anneau commutatif : (a + b) ^ 2 = a ^ 2 + 2 a b + b ^ 2 les inégalités ; les égalités qui demandent une hypothèse linarith combinaisons linéaires d'hypothèses et d'inégalités, sur un corps ordonné (ℚ, ℝ) ; marche aussi souvent sur ℕ et ℤ les produits de variables nlinarith comme linarith, en ajoutant des produits d'hypothèses ; on l'aide en donnant des faits : nlinarith [sqnonneg (a - b)] garantie : c'est une heuristique positivity buts 0 < e, 0 ≤ e, e ≠ 0 quand la forme de e le montre (carrés, sommes de positifs, exponentielles…) utiliser des hypothèses compliquées omega arithmétique linéaire exacte sur ℕ et ℤ, avec / et % par des constantes les produits de variables ; les réels decide propositions décidables sur des valeurs concrètes : Nat.Prime 7 si l'instance le permet, 2 ∣ 10 les variables libres ; les grands calculs (lent) gcongr « même forme des deux côtés » : a ≤ b → a + c ≤ b + c, laisse les comparaisons des morceaux Exemple : Ici $a^2 + b^2 - 2ab = (a-b)^2 \\ge 0$ : le fait donné à nlinarith suffit, la combinaison est linéaire en ce fait. Chercher Tactique Effet exact? cherche dans Mathlib un lemme qui ferme le but et propose exact … apply? propose des lemmes applicables aesop recherche automatique de preuve (règles et simp) tauto logique propositionnelle Madalean refuse exact? et apply? dans une preuve finale : ce sont des outils de recherche, à remplacer par le lemme qu'ils trouvent. Ils restent utiles dans un carnet ou un bloc Lean d'une note. Lire une erreur Message de Lean Sens habituel unknown identifier 'foo' / unknown constant le nom n'existe pas dans cette version de Mathlib (renommé, ou inventé par le modèle) type mismatch le terme n'a pas le type attendu : souvent une conversion ℕ/ℝ manquante unsolved goals la preuve s'arrête alors qu'il reste des buts (affichés) linarith failed les hypothèses données ne suffisent pas linéairement : ajoutez des faits motive is not type correct rw ne peut pas réécrire à cet endroit ; essayez simp only ou conv maximum recursion depth / deterministic timeout une tactique cherche trop longtemps : rendez la preuve plus explicite declaration uses 'sorry' la preuve contient un trou : elle n'est pas acceptée`},{id:`shortcuts`,lang:`fr`,title:`Raccourcis clavier`,order:430,section:`reference`,audience:`all`,summary:`Les raccourcis clavier de l'interface et de l'éditeur Lean.`,source:`fr/shortcuts.md`,site_path:`fr/shortcuts.html`,headings:[{level:1,text:`Raccourcis clavier`,id:`raccourcis-clavier`},{level:2,text:`Partout`,id:`partout`},{level:2,text:`Palette, menus et onglets`,id:`palette-menus-et-onglets`},{level:2,text:`Envoyer, exécuter, aller à la ligne`,id:`envoyer-executer-aller-a-la-ligne`},{level:2,text:`Éditeurs (énoncé, Lean, fil du dossier)`,id:`editeurs-enonce-lean-fil-du-dossier`},{level:2,text:`Application de bureau`,id:`application-de-bureau`}],images:[],verify:[],body:"# Raccourcis clavier\n\nSur macOS, `Ctrl` se lit `⌘`. Les raccourcis d'une seule touche (`/`, `n`) ne s'appliquent pas pendant la saisie\ndans un champ de texte.\n\n## Partout\n\n| Raccourci | Action |\n|---|---|\n| `Ctrl+K` ou `/` | ouvrir la palette : chercher un dossier, une commande, une page d'aide |\n| `n` | nouveau dossier (mode *Recherche* seulement) |\n| `Échap` | fermer le menu, la palette ou le volet ouvert ; un clic ailleurs le ferme aussi |\n| `Ctrl+Maj+1` | afficher ou masquer la barre du projet (Dossiers · Sources · Notes…) |\n| `Tab`, `Maj+Tab` | passer d'une commande à l'autre ; un lien « Aller au contenu » apparaît en premier |\n\n## Palette, menus et onglets\n\n| Raccourci | Action |\n|---|---|\n| `↑` `↓` | choisir dans la palette ou un menu |\n| `Entrée` | lancer l'élément choisi |\n| `Début`, `Fin` | premier, dernier élément d'un menu |\n| `←` `→`, `Début`, `Fin` | passer entre les étapes Énoncé, Traduction Lean, Preuve d'un dossier |\n\n## Envoyer, exécuter, aller à la ligne\n\nDans tout champ qui envoie quelque chose (nouvel énoncé, demande de suivi, question sur une source, explication,\nindices, consigne de recherche, correction de la traduction, demande dans Calcul, assistant du carnet), **`Entrée`\nenvoie** et **`Maj+Entrée` va à la ligne**. Une petite ligne sous le champ le rappelle.\n\n| Champ | `Entrée` | `Maj+Entrée` |\n|---|---|---|\n| champs d'envoi (ci-dessus) | envoyer | aller à la ligne |\n| cellule de code de Calcul | exécuter la cellule | aller à la ligne (en gardant l'indentation) ; `Tab` / `Maj+Tab` indente |\n| preuve Lean modifiée à la main, correction d'un exercice | vérifier avec Lean | aller à la ligne |\n| article, corps d'une note, cellule de texte, profil | aller à la ligne | aller à la ligne |\n\nDans l'article et les notes, `Entrée` reste un retour à la ligne : on y écrit de longs textes. Sur un téléphone ou une\ntablette sans clavier, `Entrée` va à la ligne partout et le bouton du champ envoie. `Ctrl+Entrée` envoie aussi.\n\n## Éditeurs (énoncé, Lean, fil du dossier)\n\n| Raccourci | Action |\n|---|---|\n| `\\le` puis `Espace` ou `Tab` | insérer un symbole : `\\forall` → `∀`, `\\R` → `ℝ`, `\\le` → `≤`, `\\to` → `→`, `\\mid` → `∣` (liste complète dans l'écran « Glossaire ») |\n| `Ctrl+Z`, `Ctrl+Maj+Z` | annuler, rétablir |\n| `Tab`, `Maj+Tab` | indenter, désindenter (dans l'éditeur Lean) |\n\nDans l'énoncé en langage courant, les abréviations ne sont pas développées entre `$…$`, pour garder le LaTeX.\n\n## Application de bureau\n\n| Raccourci | Action |\n|---|---|\n| `Ctrl+Maj+K` | changer de serveur |\n",text:`Raccourcis clavier Sur macOS, Ctrl se lit ⌘. Les raccourcis d'une seule touche (/, n) ne s'appliquent pas pendant la saisie dans un champ de texte. Partout Raccourci Action Ctrl+K ou / ouvrir la palette : chercher un dossier, une commande, une page d'aide n nouveau dossier (mode Recherche seulement) Échap fermer le menu, la palette ou le volet ouvert ; un clic ailleurs le ferme aussi Ctrl+Maj+1 afficher ou masquer la barre du projet (Dossiers · Sources · Notes…) Tab, Maj+Tab passer d'une commande à l'autre ; un lien « Aller au contenu » apparaît en premier Palette, menus et onglets Raccourci Action ↑ ↓ choisir dans la palette ou un menu Entrée lancer l'élément choisi Début, Fin premier, dernier élément d'un menu ← →, Début, Fin passer entre les étapes Énoncé, Traduction Lean, Preuve d'un dossier Envoyer, exécuter, aller à la ligne Dans tout champ qui envoie quelque chose (nouvel énoncé, demande de suivi, question sur une source, explication, indices, consigne de recherche, correction de la traduction, demande dans Calcul, assistant du carnet), Entrée envoie et Maj+Entrée va à la ligne. Une petite ligne sous le champ le rappelle. Champ Entrée Maj+Entrée champs d'envoi (ci-dessus) envoyer aller à la ligne cellule de code de Calcul exécuter la cellule aller à la ligne (en gardant l'indentation) ; Tab / Maj+Tab indente preuve Lean modifiée à la main, correction d'un exercice vérifier avec Lean aller à la ligne article, corps d'une note, cellule de texte, profil aller à la ligne aller à la ligne Dans l'article et les notes, Entrée reste un retour à la ligne : on y écrit de longs textes. Sur un téléphone ou une tablette sans clavier, Entrée va à la ligne partout et le bouton du champ envoie. Ctrl+Entrée envoie aussi. Éditeurs (énoncé, Lean, fil du dossier) Raccourci Action \\le puis Espace ou Tab insérer un symbole : \\forall → ∀, \\R → ℝ, \\le → ≤, \\to → →, \\mid → ∣ (liste complète dans l'écran « Glossaire ») Ctrl+Z, Ctrl+Maj+Z annuler, rétablir Tab, Maj+Tab indenter, désindenter (dans l'éditeur Lean) Dans l'énoncé en langage courant, les abréviations ne sont pas développées entre $…$, pour garder le LaTeX. Application de bureau Raccourci Action Ctrl+Maj+K changer de serveur`},{id:`measures`,lang:`fr`,title:`Mesures : ce que Madalean prouve, en combien de temps, à quel coût`,order:440,section:`reference`,audience:`researcher`,summary:`Le banc d'essai intégré — miniF2F, PutnamBench et un jeu de contrôle — compte seulement les preuves qu'un Lean neuf et strict accepte, avec le temps et le coût par preuve.`,source:`fr/measures.md`,site_path:`fr/measures.html`,headings:[{level:1,text:`Mesures`,id:`mesures`},{level:2,text:`Ce qui compte comme « prouvé »`,id:`ce-qui-compte-comme-prouve`},{level:2,text:`Les jeux de problèmes`,id:`les-jeux-de-problemes`},{level:2,text:`Les stratégies`,id:`les-strategies`},{level:2,text:`Le coût`,id:`le-cout`},{level:2,text:`Lancer une mesure`,id:`lancer-une-mesure`},{level:2,text:`Ce que ces chiffres ne disent pas`,id:`ce-que-ces-chiffres-ne-disent-pas`}],images:[],verify:[],body:`# Mesures

Madalean se mesure lui-même. La commande \`madalean bench\` fait passer des énoncés formels par **la même chaîne que
l'application** (recherche dans Mathlib, tournoi de modèles gratuits, chef d'orchestre…), sans interface, et écrit
pour chaque problème : prouvé ou non, nombre d'essais, temps, jetons, coût, modèle qui a trouvé, temps de Lean.

Les résultats publiés sont sur la page « Mesures » du site (lien en bas de chaque page du site). Ils sont refaits à
chaque version.

## Ce qui compte comme « prouvé »

Une seule chose : la preuve trouvée est recompilée **à part**, par un Lean neuf, avec le verdict strict de
l'application — pas de \`sorry\`, pas d'axiome ajouté, seulement les axiomes standards — et elle doit démontrer
**l'énoncé donné**, pas un autre. Le mot du modèle, ou une vérification intermédiaire, ne compte jamais.

Un énoncé que le Lean de l'espace de travail n'accepte pas (le jeu a été écrit pour une autre version de Mathlib) est
compté **à part** : ce n'est pas un échec de la preuve.

## Les jeux de problèmes

| Jeu | Contenu | Licence |
|---|---|---|
| Jeu de contrôle | 20 énoncés écrits pour Madalean, de la logique à la topologie : vérifie que toute la chaîne marche | Apache-2.0 |
| miniF2F | 488 énoncés de niveau lycée et olympiades (244 « valid », 244 « test ») | MIT |
| PutnamBench | 672 énoncés du concours Putnam (1962–2025) | Apache-2.0 |

miniF2F et PutnamBench ne sont pas copiés dans Madalean : \`madalean bench fetch\` les télécharge depuis leur dépôt
public, à une version figée, dans un dossier de cache ; l'empreinte du contenu est contrôlée à chaque lecture.
PutnamBench demande de ne pas publier de preuves : seuls les comptes sont publiés.

## Les stratégies

| Stratégie | Ce qui tourne |
|---|---|
| \`mathlib\` | la recherche dans Mathlib seule, sans aucun modèle |
| \`tournament\` | le réglage par défaut de l'application : Mathlib d'abord, puis le tournoi de modèles gratuits |
| \`conductor\` | le tournoi dirigé par le chef d'orchestre |
| \`single\` | un seul modèle, que vous nommez |
| \`goedel-local\` | Goedel-Prover sur la carte graphique de la machine |

## Le coût

Par défaut, **aucun modèle payant ne peut être appelé** : le banc d'essai ne donne au moteur que les clés des
fournisseurs gratuits. Les modèles payants ne servent que si vous donnez un budget (\`--paid-budget\`, en dollars) ; ce
budget est un plafond ferme pour tout le passage. Le coût affiché est celui des appels payants au prix public ; les
modèles gratuits et Mathlib coûtent 0 $.

## Lancer une mesure

\`\`\`
madalean bench sets
madalean bench fetch minif2f
madalean bench check minif2f --split valid --workspace lean-prover49
madalean bench run minif2f --split valid --sample 50 --seed 1 --strategy tournament --time-budget 30
\`\`\`

Un passage interrompu reprend où il s'était arrêté : relancez la même commande. Le banc d'essai travaille dans son
propre dossier : il ne touche ni vos projets, ni vos réglages, ni le serveur en marche, et ne charge pas de modèle
sur la carte graphique sauf avec \`goedel-local\`.

## Ce que ces chiffres ne disent pas

- Un échantillon de 50 problèmes donne une estimation à une dizaine de points près.
- Les limites sont courtes (quelques minutes et quelques essais par problème) : c'est l'atelier tel qu'on s'en sert,
  pas le maximum atteignable avec des milliers d'essais.
- Les modèles en ligne changent et leurs réponses ne sont pas reproductibles à l'identique : l'ordre des problèmes
  et l'échantillon le sont, les réponses des modèles non.
- Les énoncés sont donnés en Lean : la traduction depuis le français ou l'anglais n'est pas mesurée ici.
`,text:`Mesures Madalean se mesure lui-même. La commande madalean bench fait passer des énoncés formels par la même chaîne que l'application (recherche dans Mathlib, tournoi de modèles gratuits, chef d'orchestre…), sans interface, et écrit pour chaque problème : prouvé ou non, nombre d'essais, temps, jetons, coût, modèle qui a trouvé, temps de Lean. Les résultats publiés sont sur la page « Mesures » du site (lien en bas de chaque page du site). Ils sont refaits à chaque version. Ce qui compte comme « prouvé » Une seule chose : la preuve trouvée est recompilée à part, par un Lean neuf, avec le verdict strict de l'application — pas de sorry, pas d'axiome ajouté, seulement les axiomes standards — et elle doit démontrer l'énoncé donné, pas un autre. Le mot du modèle, ou une vérification intermédiaire, ne compte jamais. Un énoncé que le Lean de l'espace de travail n'accepte pas (le jeu a été écrit pour une autre version de Mathlib) est compté à part : ce n'est pas un échec de la preuve. Les jeux de problèmes Jeu Contenu Licence Jeu de contrôle 20 énoncés écrits pour Madalean, de la logique à la topologie : vérifie que toute la chaîne marche Apache-2.0 miniF2F 488 énoncés de niveau lycée et olympiades (244 « valid », 244 « test ») MIT PutnamBench 672 énoncés du concours Putnam (1962–2025) Apache-2.0 miniF2F et PutnamBench ne sont pas copiés dans Madalean : madalean bench fetch les télécharge depuis leur dépôt public, à une version figée, dans un dossier de cache ; l'empreinte du contenu est contrôlée à chaque lecture. PutnamBench demande de ne pas publier de preuves : seuls les comptes sont publiés. Les stratégies Stratégie Ce qui tourne mathlib la recherche dans Mathlib seule, sans aucun modèle tournament le réglage par défaut de l'application : Mathlib d'abord, puis le tournoi de modèles gratuits conductor le tournoi dirigé par le chef d'orchestre single un seul modèle, que vous nommez goedel-local Goedel-Prover sur la carte graphique de la machine Le coût Par défaut, aucun modèle payant ne peut être appelé : le banc d'essai ne donne au moteur que les clés des fournisseurs gratuits. Les modèles payants ne servent que si vous donnez un budget (--paid-budget, en dollars) ; ce budget est un plafond ferme pour tout le passage. Le coût affiché est celui des appels payants au prix public ; les modèles gratuits et Mathlib coûtent 0 $. Lancer une mesure Un passage interrompu reprend où il s'était arrêté : relancez la même commande. Le banc d'essai travaille dans son propre dossier : il ne touche ni vos projets, ni vos réglages, ni le serveur en marche, et ne charge pas de modèle sur la carte graphique sauf avec goedel-local. Ce que ces chiffres ne disent pas - Un échantillon de 50 problèmes donne une estimation à une dizaine de points près. - Les limites sont courtes (quelques minutes et quelques essais par problème) : c'est l'atelier tel qu'on s'en sert, pas le maximum atteignable avec des milliers d'essais. - Les modèles en ligne changent et leurs réponses ne sont pas reproductibles à l'identique : l'ordre des problèmes et l'échantillon le sont, les réponses des modèles non. - Les énoncés sont donnés en Lean : la traduction depuis le français ou l'anglais n'est pas mesurée ici.`},{id:`index`,lang:`en`,title:`Madalean manual`,order:0,section:`start`,audience:`all`,summary:`What Madalean does, what it does not do, and the map of this manual.`,source:`en/index.md`,site_path:`en/index.html`,headings:[{level:1,text:`Madalean manual`,id:`madalean-manual`},{level:2,text:`What Madalean does not do`,id:`what-madalean-does-not-do`},{level:2,text:`Map of the manual`,id:`map-of-the-manual`},{level:2,text:`Conventions of this manual`,id:`conventions-of-this-manual`}],images:[{src:`img/home.png`,exists:!0}],verify:[],body:`# Madalean manual

Madalean is a proving assistant for **Lean 4** and **Mathlib**. You write a statement in plain language (LaTeX
formulas between dollar signs are accepted); AI models translate it into Lean, search for a proof and explain it;
**Lean decides**. Nothing is ever presented as proved unless Lean accepted it under the strict verdict: no error, no
\`sorry\`, no axiom other than Lean's three standard axioms (\`propext\`, \`Classical.choice\`, \`Quot.sound\`).

A single computer, the **host computer**, does all the work: Lean, local models, storage. Every screen (this
computer, another PC, a tablet, a phone) shows the **same web interface** and stays synchronised. Devices reach the
host only through your private Tailscale network.

![Madalean home screen](img/home.png)

## What Madalean does not do

- It does not guarantee that the Lean translation says what you meant. Lean checks the proof **of the Lean
  statement**, not of your sentence. Always read the translation: see [Reading a Lean statement](reading-lean.md).
- It does not find every proof. “No proof found” does not mean the statement is false.
- It sends nothing over the Internet in **Local** mode. In the other modes, what is sent and to whom is described in
  [Models and keys](models-keys.md).

## Map of the manual

- **Getting started**: [Installing Madalean](install.md) · [What Madalean installs](components.md) ·
  [First configuration](first-config.md) · [First run](first-run.md) ·
  [Link a phone, a tablet, a PC](pairing.md) · [Tailscale](tailscale.md)
- **Working**: [From statement to proof](workflow.md) · [Reading a Lean statement](reading-lean.md) ·
  [Follow-up requests and versions](follow-ups.md) · [Projects and parallel dossiers](projects.md) ·
  [Proof plans and lemmas](proof-plans.md)
- **Research**: [Conjecture workshop](conjectures.md) · [Sources and grounded questions](sources.md) ·
  [Bibliography, article, blueprint](articles.md) · [Notes](notes.md) · [Jupyter and Sage](jupyter.md) ·
  [Publishing a project](publish.md)
- **Settings and security**: [Models and keys](models-keys.md) · [Updates](updates.md) ·
  [Security](security.md)
- **Reference**: [Troubleshooting](troubleshooting.md) · [Lean glossary](glossary.md) ·
  [First tactics](tactics.md) · [Keyboard shortcuts](shortcuts.md) · [Measurements](measures.md)

## Conventions of this manual

- Names in quotation marks (“Send”, “Settings › Devices”) are those of the interface's buttons and menus.
- \`lean\` code blocks are Lean 4 with Mathlib. They follow the Mathlib version of the “Prover” workspace (Lean 4.9)
  unless stated otherwise; a few notations have changed since, and these are pointed out.
- Pages marked *learner* are for people discovering Lean; *researcher* for people using it for a research project.
  Most concern everyone.
`,text:`Madalean manual Madalean is a proving assistant for Lean 4 and Mathlib. You write a statement in plain language (LaTeX formulas between dollar signs are accepted); AI models translate it into Lean, search for a proof and explain it; Lean decides. Nothing is ever presented as proved unless Lean accepted it under the strict verdict: no error, no sorry, no axiom other than Lean's three standard axioms (propext, Classical.choice, Quot.sound). A single computer, the host computer, does all the work: Lean, local models, storage. Every screen (this computer, another PC, a tablet, a phone) shows the same web interface and stays synchronised. Devices reach the host only through your private Tailscale network. Madalean home screen What Madalean does not do - It does not guarantee that the Lean translation says what you meant. Lean checks the proof of the Lean statement, not of your sentence. Always read the translation: see Reading a Lean statement. - It does not find every proof. “No proof found” does not mean the statement is false. - It sends nothing over the Internet in Local mode. In the other modes, what is sent and to whom is described in Models and keys. Map of the manual - Getting started: Installing Madalean · What Madalean installs · First configuration · First run · Link a phone, a tablet, a PC · Tailscale - Working: From statement to proof · Reading a Lean statement · Follow-up requests and versions · Projects and parallel dossiers · Proof plans and lemmas - Research: Conjecture workshop · Sources and grounded questions · Bibliography, article, blueprint · Notes · Jupyter and Sage · Publishing a project - Settings and security: Models and keys · Updates · Security - Reference: Troubleshooting · Lean glossary · First tactics · Keyboard shortcuts · Measurements Conventions of this manual - Names in quotation marks (“Send”, “Settings › Devices”) are those of the interface's buttons and menus. - lean code blocks are Lean 4 with Mathlib. They follow the Mathlib version of the “Prover” workspace (Lean 4.9) unless stated otherwise; a few notations have changed since, and these are pointed out. - Pages marked learner are for people discovering Lean; researcher for people using it for a research project. Most concern everyone.`},{id:`install`,lang:`en`,title:`Installing Madalean`,order:10,section:`start`,audience:`all`,summary:`What the computer needs, the three ways to install (graphical installer, terminal assistant, unattended install), what install.sh does, its options, updating and uninstalling.`,source:`en/install.md`,site_path:`en/install.html`,headings:[{level:1,text:`Installing Madalean`,id:`installing-madalean`},{level:2,text:`Before you start`,id:`before-you-start`},{level:2,text:`Three ways to install`,id:`three-ways-to-install`},{level:3,text:`With the graphical installer (recommended)`,id:`with-the-graphical-installer-recommended`},{level:3,text:`From source, with the terminal assistant`,id:`from-source-with-the-terminal-assistant`},{level:3,text:`Without questions (unattended install)`,id:`without-questions-unattended-install`},{level:2,text:`What install.sh does, step by step`,id:`what-installsh-does-step-by-step`},{level:2,text:`What is already on your computer`,id:`what-is-already-on-your-computer`},{level:2,text:`install.sh options`,id:`installsh-options`},{level:2,text:`Where your choices are recorded`,id:`where-your-choices-are-recorded`},{level:2,text:`Where things are`,id:`where-things-are`},{level:2,text:`Starting and stopping`,id:`starting-and-stopping`},{level:2,text:`Installing without a network`,id:`installing-without-a-network`},{level:2,text:`Updating`,id:`updating`},{level:2,text:`Uninstalling`,id:`uninstalling`}],images:[],verify:[],body:`# Installing Madalean

Madalean is installed on **one computer only**, the **host computer**: it runs the server, Lean and the local models,
and it keeps your data. Your other devices (another PC, a tablet, a phone) install only a light app, or nothing at
all: a browser is enough. See [Link a device](pairing.md).

This page covers the installation itself. Two pages complete it:

- [What Madalean installs, component by component](components.md): what each piece is for (Lean, SageMath, LaTeX,
  local models…), its size, and whether it is better to reuse what is already on your computer;
- [First configuration](first-config.md): the keys of online providers, where the models work and the automatic
  behaviours, to set once the installation is done.

## Before you start

| | Minimum | Recommended |
|---|---|---|
| System | 64-bit Linux (x86_64), any recent distribution | — |
| Memory (RAM) | 8 GB | 16 GB or more |
| Graphics card | none | NVIDIA with at least 8 GB of graphics memory, to run the local prover |
| Disk | ≈ 6 GB free without local models or SageMath | an SSD, with the space listed below |

Disk space, depending on what you install:

| Item | Space |
|---|---|
| Madalean and its basic components (Python, JupyterLab, LaTeX, fonts, Lean, model engine) | ≈ 6 GB |
| The three local models (in \`~/models\`) | ≈ 15 GB more, i.e. ≈ 25 GB in all with the basics and some margin |
| SageMath (the “Calcul” screen) | ≈ 5 GB more |
| Each Lean/Mathlib workspace built on the computer | ≈ 5 GB |

**Without an NVIDIA card**, everything works: online models (free, or with a key) do not depend on your graphics
card, and they are what Madalean uses by default. Only the local models would be too slow on the processor; the
installation then does not suggest them (see [Local models](components.md#local-models)).

**With an NVIDIA card**, only the **NVIDIA driver** must be installed, by you, with your distribution's tools.
Madalean never touches drivers and does not need the “CUDA Toolkit”. If the driver is too old, it installs the
processor version of the model engine.

You also need an Internet connection during the installation (except for an [offline install](#installing-without-a-network)),
and the basic commands \`bash\`, \`curl\`, \`tar\` and \`sha256sum\`, present on every common distribution.

## Three ways to install

| Way | For whom | Questions asked |
|---|---|---|
| [Graphical installer](#with-the-graphical-installer-recommended) (recommended) | everyone | in a page of your web browser, with a recommended plan |
| [From source, terminal assistant](#from-source-with-the-terminal-assistant) | whoever prefers the terminal or wants to follow the code | in the terminal, with the same recommended plan |
| [Unattended install](#without-questions-unattended-install) | repeated installs, scripts, remote machines | none: the defaults |

All three lead to the same installation, done by the same program (\`install.sh\`). None asks for your password:
nothing is installed outside your home folder.

### With the graphical installer (recommended)

1. **Download** the file \`Madalean-installer.run\`: the link
   <https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run> always leads to the
   latest version. The site's
   [download page](site:install) also gives this link.
2. **Make it executable.** A file downloaded by a browser cannot be started as is: this is a Linux protection.
   Either:
   - in the file manager: right-click the file › “Properties” › “Permissions” tab › tick “Allow executing file as
     program” (the wording varies with the desktop: “Executable”, “Is executable”…);
   - or in a terminal, in the file's folder:

     \`\`\`bash
     chmod +x Madalean-installer.run
     \`\`\`
3. **Start it**: double-click the file, or in the terminal:

   \`\`\`bash
   ./Madalean-installer.run
   \`\`\`

What happens next:

- The file **first checks its own integrity** (SHA-256 fingerprint) before unpacking anything. A file damaged during
  the download is refused with a clear message: download it again.
- It then opens an **installation assistant in your web browser**. This page is served by the installer itself, on
  your computer only (address \`127.0.0.1\`, protected by a one-time key): no other computer can reach it.
- The assistant takes you through six screens:
  1. **Welcome**: what will be installed and where.
  2. **Machine check**: system, memory, graphics card, free space, and the tools already present (Lean, SageMath,
     TeX Live, Tailscale, Ollama, bubblewrap…).
  3. **Recommended plan**: for each item (local models, SageMath, LaTeX, Lean workspaces…), the choice advised for
     your computer and the reason; you can change each choice.
  4. **Installation**: live progress, step by step.
  5. **First configuration**: what remains to set in Madalean (online model key, working mode, automatic
     behaviours, devices) and an « Open Madalean » button (\`http://127.0.0.1:11500\`), where the first-run
     assistant takes over (see [First configuration](first-config.md)).
  6. **Done**: Madalean's address; « Close the assistant » stops the small local page (it also stops by itself
     after 30 minutes without activity, never during an installation).
- On an error, the installation screen shows the last lines, « Show details » the whole log, and « Try again »
  resumes where the installation stopped.
- **Without a graphical session** (for example on a computer you reach through \`ssh\`), the installer switches by
  itself to the terminal assistant described below.


### From source, with the terminal assistant

If you prefer the terminal, or want to install the development version:

\`\`\`bash
git clone https://github.com/raantss18/madalean.git ~/madalean
cd ~/madalean
./install.sh
\`\`\`

When started in a terminal, \`install.sh\`:

1. examines the computer (system, memory, graphics card, free space, tools already installed);
2. shows a **summary table** of what it found;
3. suggests a **recommended plan** (the same as the graphical installer's);
4. lets you **accept** it as is or **change each item**, then installs.

To only see this plan without installing anything: \`./install.sh --dry-run\`.

### Without questions (unattended install)

\`\`\`bash
./install.sh --yes
\`\`\`

\`--yes\` (or \`-y\`) installs with the default choices, without asking anything. This is also what happens when
\`install.sh\` is not started in a terminal (from another script, for example). You can add the options of the
[table below](#installsh-options), or reuse a saved plan with \`--plan FILE\`.

## What install.sh does, step by step

The script shows nine steps, numbered \`1/9\` to \`9/9\`. It is **safe to run again**: if it is interrupted (network
failure, computer switched off), start it again; it resumes where it stopped, without redoing what is already done.
Every downloaded file is checked against its **SHA-256 fingerprint** (a kind of digital signature of the content):
an altered file is refused.

| Step | What is done |
|---|---|
| 1. Checks | Linux x86_64? basic tools present? free disk space |
| 2. Madalean | Madalean's code and web interface are copied into \`~/.local/share/madalean/versions/<version>\`; a \`current\` link points to the version in service |
| 3. Environment | the small package manager **micromamba** is downloaded, then it installs the main environment, fixed in advance: Python 3.13, JupyterLab, the LaTeX engine tectonic, poppler (PDF reading), git… Every package is checked against its SHA-256 fingerprint |
| 4. Verified components | fonts (DejaVu Sans Mono, Noto Sans Math), TeX bundle (to typeset PDFs without a network), **elan** (Lean's version manager), **llama.cpp** (engine of the local models, for your NVIDIA card or for the processor), **madalean-net** (the embedded Tailscale node, which lets your devices reach the host) |
| 5. Lean workspaces | Lean workspaces already built on the computer are reused (through hard links: no extra space); otherwise, with \`--build-workspace\`, the “Current Lean” workspace is built |
| 6. Local models | the models chosen in the plan are downloaded into \`~/models\`; those already there are reused, never moved |
| 7. Service | the systemd user service \`madalean\` is installed and started: Madalean runs in the background as soon as your session opens |
| 8. Menu | the **“Madalean Server”** app is added to the applications menu (the Madalean icon with a small server badge): Madalean’s window on this computer, with the server’s status, Start / Stop / Restart buttons and the logs. Without the system library webkit2gtk-4.1, the entry opens a Chromium window (or Chrome, Brave, Edge, Vivaldi), else your browser; the final summary says which |
| 9. Check | a health check of each component, then a connection test to the server |

At the end, the script shows the time taken, the space used and the address to open: \`http://127.0.0.1:11500\`. The
full log is in \`~/.local/share/madalean/install.log\`.

## What is already on your computer

Madalean **never uses \`sudo\`** and **never runs your distribution's package manager** (\`pacman\`, \`apt\`, \`dnf\`,
\`zypper\`…). It changes no program of the system. For what it finds already installed:

| Already present | What Madalean does |
|---|---|
| Built Lean workspaces, Lean versions in \`~/.elan\` | reused **read-only** for the import; \`~/.elan\` is never modified |
| Models in \`~/models\` | reused (checked by fingerprint), never moved |
| The system's SageMath | reused if it is compatible and you choose it; otherwise Madalean installs its own copy on demand |
| TeX Live | used as a fallback, or first if you choose it |
| The system's Python | never modified; the server uses its own Python |
| Tailscale, Ollama | left in place; no conflict |

Details, and what is best in each case: [What Madalean installs](components.md).

When something can only come from your distribution — this is the case of **bubblewrap**, which isolates
compilations and computations in a “sandbox” —, the script **prints the exact command** for you to run, for example
\`sudo pacman -S bubblewrap\` on Arch Linux or \`sudo apt install bubblewrap\` on Debian and Ubuntu. The commands for
each distribution are in [What Madalean installs › bubblewrap](components.md#bubblewrap-the-sandbox).

## install.sh options

\`./install.sh --help\` lists them all.

| Option | Effect |
|---|---|
| \`--yes\`, \`-y\` | no questions: the defaults |
| \`--assistant\` | forces the terminal assistant (even when it would not be offered) |
| \`--plan FILE\` | installs according to a plan saved by the assistant or by the graphical installer |
| \`--dry-run\` | examines the computer and shows the plan, installs nothing |
| \`--models all\\|prover\\|none\` | local models: all three, the prover only, or none (no question: all three; the assistant advises from the graphics card) |
| \`--sage later\\|now\\|system\` | SageMath: on first use of “Calcul” (default), right away, or the system's one |
| \`--tex own\\|system\` | LaTeX: Madalean's (default) or the system's TeX Live first |
| \`--cpu\` \\| \`--gpu\` | model engine for the processor, or for the NVIDIA card (default: the card if the driver is suitable) |
| \`--no-models\` | downloads no local model (files already in \`~/models\` are still used) |
| \`--no-workspaces\` | installs no Lean workspace |
| \`--build-workspace\` | builds the “Current Lean” workspace if none is found (≈ 5 GB, network needed) |
| \`--build-net\` | builds the Tailscale node \`madalean-net\` from source (it must give exactly the expected fingerprint) |
| \`--offline FOLDER\` | installs without a network, from an export made with \`./export_offline.sh\` |
| \`--prefix FOLDER\` | installation folder (default \`~/.local/share/madalean\`) |
| \`--config-dir FOLDER\` | settings and data folder (default \`~/.config/madalean\`) |
| \`--cache-dir FOLDER\` | cache folder (default \`~/.cache/madalean\`) |
| \`--no-systemd\` | does not install the systemd service (you then start Madalean yourself) |
| \`--no-desktop\` | adds no entry to the applications menu |
| \`--port N\`, \`--remote-port N\` | server ports: local interface (default 11500) and access of linked devices (default 11501) |


## Where your choices are recorded

The choices made at installation (local models, SageMath, LaTeX…) are written to \`~/.config/madalean/setup.json\`.
Madalean reads this file at first start and applies the settings that follow from it, for example \`sage_source\`
(which SageMath to use) and \`tex_engine\` (which LaTeX to use); you can change
them at any time (the application also reads them through \`GET /api/setup\`). See [First configuration › Choices made at installation](first-config.md#choices-made-at-installation).

At the first start in the browser on the host, the [“First steps”](first-config.md#the-first-steps-assistant)
assistant shows these choices again (recommended choice and reason for this machine) and lets you change them.

## Where things are

| What | Where |
|---|---|
| Madalean and all its components | \`~/.local/share/madalean/\` |
| Installation log | \`~/.local/share/madalean/install.log\` |
| Settings, installation choices, projects, dossiers, linked devices, keys (if no keyring) | \`~/.config/madalean/\` |
| Search index, caches | \`~/.cache/madalean/\` |
| Local models | \`~/models/\` |
| Jupyter notebooks | \`~/Documents/Madalean/notebooks/\` |
| systemd service | \`~/.config/systemd/user/madalean.service\` |

At first start, if you had Lean AI Station 1.x, the server **copies** (never moves) your settings, dossiers and
library from \`~/.config/lean-ai-station/\`.

## Starting and stopping

The service starts with your session. Open the interface on the host: **“Madalean Server”** in the applications
menu, or \`http://127.0.0.1:11500\` in a browser.

“Madalean Server” is the host computer’s app: it shows Madalean in its own window (no pairing code: it is this
computer) and, in its **Server** menu (or its icon next to the clock), the server’s status, **Start**, **Stop**,
**Restart**, **Open the logs** and **Open in the browser**. When the server stops, the window shows the server panel;
when it comes back, the window returns to Madalean by itself. If the service is not installed, the panel says so and
gives the command to reinstall it. The “Madalean” app (AppImage, no badge) is for the **other** computers: see
[Link a device](pairing.md).

In a terminal, if needed:

\`\`\`bash
systemctl --user status madalean      # status
systemctl --user restart madalean     # restart
journalctl --user -u madalean -e      # log
\`\`\`

Next: [First configuration](first-config.md), then [First run](first-run.md) for a first statement.

## Installing without a network

For a computer without Internet access: on a connected computer where Madalean is installed, \`./export_offline.sh\`
prepares a folder with everything needed (packages, components, Lean workspaces, models). Copy this folder to the
other computer (USB stick, disk), then:

\`\`\`bash
./install.sh --offline /path/to/the-export
\`\`\`

SHA-256 fingerprints are checked as for an online installation.

## Updating

Madalean updates **from the application**, in “Settings › Updates”: each new version is **signed**, checked,
installed next to the old one, then put into service; the previous version is kept to roll back. There is no need
to run \`install.sh\` again. Details: [Updates](updates.md).

## Uninstalling

From the source folder (or \`~/.local/share/madalean/current\`):

\`\`\`bash
./uninstall.sh
\`\`\`

The script **first lists** exactly what will be removed, with the size of each item, then **asks for
confirmation**. It first stops the service and all its processes.

| Removed | Kept |
|---|---|
| \`~/.local/share/madalean\` (environment, components, Lean workspaces installed by Madalean, TeX bundle, Tailscale node state, Madalean versions) | \`~/.config/madalean\`: your settings, projects, dossiers, linked devices and keys |
| \`~/.cache/madalean\` | \`~/models\`: your models |
| the systemd service and the menu entry | \`~/Documents/Madalean\`: your notebooks |
| | never touched: \`~/.elan\`, system packages, the system's Tailscale |

Options:

| Option | Effect |
|---|---|
| \`--purge\` | also offers, with one question each, to remove \`~/.config/madalean\` and \`~/models\` |
| \`--yes\` | does not ask the general confirmation (the \`--purge\` questions are still asked) |
| \`--prefix\`, \`--config-dir\`, \`--cache-dir\` | give them if you changed them at installation |

Keys stored in the system keyring stay in the keyring: remove them first in “Settings › Providers” (“Remove the
key”) if you want them erased.
`,text:`Installing Madalean Madalean is installed on one computer only, the host computer: it runs the server, Lean and the local models, and it keeps your data. Your other devices (another PC, a tablet, a phone) install only a light app, or nothing at all: a browser is enough. See Link a device. This page covers the installation itself. Two pages complete it: - What Madalean installs, component by component: what each piece is for (Lean, SageMath, LaTeX, local models…), its size, and whether it is better to reuse what is already on your computer; - First configuration: the keys of online providers, where the models work and the automatic behaviours, to set once the installation is done. Before you start Minimum Recommended System 64-bit Linux (x8664), any recent distribution — Memory (RAM) 8 GB 16 GB or more Graphics card none NVIDIA with at least 8 GB of graphics memory, to run the local prover Disk ≈ 6 GB free without local models or SageMath an SSD, with the space listed below Disk space, depending on what you install: Item Space Madalean and its basic components (Python, JupyterLab, LaTeX, fonts, Lean, model engine) ≈ 6 GB The three local models (in ~/models) ≈ 15 GB more, i.e. ≈ 25 GB in all with the basics and some margin SageMath (the “Calcul” screen) ≈ 5 GB more Each Lean/Mathlib workspace built on the computer ≈ 5 GB Without an NVIDIA card, everything works: online models (free, or with a key) do not depend on your graphics card, and they are what Madalean uses by default. Only the local models would be too slow on the processor; the installation then does not suggest them (see Local models). With an NVIDIA card, only the NVIDIA driver must be installed, by you, with your distribution's tools. Madalean never touches drivers and does not need the “CUDA Toolkit”. If the driver is too old, it installs the processor version of the model engine. You also need an Internet connection during the installation (except for an offline install), and the basic commands bash, curl, tar and sha256sum, present on every common distribution. Three ways to install Way For whom Questions asked Graphical installer (recommended) everyone in a page of your web browser, with a recommended plan From source, terminal assistant whoever prefers the terminal or wants to follow the code in the terminal, with the same recommended plan Unattended install repeated installs, scripts, remote machines none: the defaults All three lead to the same installation, done by the same program (install.sh). None asks for your password: nothing is installed outside your home folder. With the graphical installer (recommended) 1. Download the file Madalean-installer.run: the link <https://github.com/raantss18/madalean/releases/latest/download/Madalean-installer.run> always leads to the latest version. The site's download page also gives this link. 2. Make it executable. A file downloaded by a browser cannot be started as is: this is a Linux protection. Either: - in the file manager: right-click the file › “Properties” › “Permissions” tab › tick “Allow executing file as program” (the wording varies with the desktop: “Executable”, “Is executable”…); - or in a terminal, in the file's folder: 3. Start it: double-click the file, or in the terminal: What happens next: - The file first checks its own integrity (SHA-256 fingerprint) before unpacking anything. A file damaged during the download is refused with a clear message: download it again. - It then opens an installation assistant in your web browser. This page is served by the installer itself, on your computer only (address 127.0.0.1, protected by a one-time key): no other computer can reach it. - The assistant takes you through six screens: 1. Welcome: what will be installed and where. 2. Machine check: system, memory, graphics card, free space, and the tools already present (Lean, SageMath, TeX Live, Tailscale, Ollama, bubblewrap…). 3. Recommended plan: for each item (local models, SageMath, LaTeX, Lean workspaces…), the choice advised for your computer and the reason; you can change each choice. 4. Installation: live progress, step by step. 5. First configuration: what remains to set in Madalean (online model key, working mode, automatic behaviours, devices) and an « Open Madalean » button (http://127.0.0.1:11500), where the first-run assistant takes over (see First configuration). 6. Done: Madalean's address; « Close the assistant » stops the small local page (it also stops by itself after 30 minutes without activity, never during an installation). - On an error, the installation screen shows the last lines, « Show details » the whole log, and « Try again » resumes where the installation stopped. - Without a graphical session (for example on a computer you reach through ssh), the installer switches by itself to the terminal assistant described below. From source, with the terminal assistant If you prefer the terminal, or want to install the development version: When started in a terminal, install.sh: 1. examines the computer (system, memory, graphics card, free space, tools already installed); 2. shows a summary table of what it found; 3. suggests a recommended plan (the same as the graphical installer's); 4. lets you accept it as is or change each item, then installs. To only see this plan without installing anything: ./install.sh --dry-run. Without questions (unattended install) --yes (or -y) installs with the default choices, without asking anything. This is also what happens when install.sh is not started in a terminal (from another script, for example). You can add the options of the table below, or reuse a saved plan with --plan FILE. What install.sh does, step by step The script shows nine steps, numbered 1/9 to 9/9. It is safe to run again: if it is interrupted (network failure, computer switched off), start it again; it resumes where it stopped, without redoing what is already done. Every downloaded file is checked against its SHA-256 fingerprint (a kind of digital signature of the content): an altered file is refused. Step What is done 1. Checks Linux x8664? basic tools present? free disk space 2. Madalean Madalean's code and web interface are copied into ~/.local/share/madalean/versions/<version>; a current link points to the version in service 3. Environment the small package manager micromamba is downloaded, then it installs the main environment, fixed in advance: Python 3.13, JupyterLab, the LaTeX engine tectonic, poppler (PDF reading), git… Every package is checked against its SHA-256 fingerprint 4. Verified components fonts (DejaVu Sans Mono, Noto Sans Math), TeX bundle (to typeset PDFs without a network), elan (Lean's version manager), llama.cpp (engine of the local models, for your NVIDIA card or for the processor), madalean-net (the embedded Tailscale node, which lets your devices reach the host) 5. Lean workspaces Lean workspaces already built on the computer are reused (through hard links: no extra space); otherwise, with --build-workspace, the “Current Lean” workspace is built 6. Local models the models chosen in the plan are downloaded into ~/models; those already there are reused, never moved 7. Service the systemd user service madalean is installed and started: Madalean runs in the background as soon as your session opens 8. Menu the “Madalean Server” app is added to the applications menu (the Madalean icon with a small server badge): Madalean’s window on this computer, with the server’s status, Start / Stop / Restart buttons and the logs. Without the system library webkit2gtk-4.1, the entry opens a Chromium window (or Chrome, Brave, Edge, Vivaldi), else your browser; the final summary says which 9. Check a health check of each component, then a connection test to the server At the end, the script shows the time taken, the space used and the address to open: http://127.0.0.1:11500. The full log is in ~/.local/share/madalean/install.log. What is already on your computer Madalean never uses sudo and never runs your distribution's package manager (pacman, apt, dnf, zypper…). It changes no program of the system. For what it finds already installed: Already present What Madalean does Built Lean workspaces, Lean versions in ~/.elan reused read-only for the import; ~/.elan is never modified Models in ~/models reused (checked by fingerprint), never moved The system's SageMath reused if it is compatible and you choose it; otherwise Madalean installs its own copy on demand TeX Live used as a fallback, or first if you choose it The system's Python never modified; the server uses its own Python Tailscale, Ollama left in place; no conflict Details, and what is best in each case: What Madalean installs. When something can only come from your distribution — this is the case of bubblewrap, which isolates compilations and computations in a “sandbox” —, the script prints the exact command for you to run, for example sudo pacman -S bubblewrap on Arch Linux or sudo apt install bubblewrap on Debian and Ubuntu. The commands for each distribution are in What Madalean installs › bubblewrap. install.sh options ./install.sh --help lists them all. Option Effect --yes, -y no questions: the defaults --assistant forces the terminal assistant (even when it would not be offered) --plan FILE installs according to a plan saved by the assistant or by the graphical installer --dry-run examines the computer and shows the plan, installs nothing --models all prover none local models: all three, the prover only, or none (no question: all three; the assistant advises from the graphics card) --sage later now system SageMath: on first use of “Calcul” (default), right away, or the system's one --tex own system LaTeX: Madalean's (default) or the system's TeX Live first --cpu --gpu model engine for the processor, or for the NVIDIA card (default: the card if the driver is suitable) --no-models downloads no local model (files already in ~/models are still used) --no-workspaces installs no Lean workspace --build-workspace builds the “Current Lean” workspace if none is found (≈ 5 GB, network needed) --build-net builds the Tailscale node madalean-net from source (it must give exactly the expected fingerprint) --offline FOLDER installs without a network, from an export made with ./exportoffline.sh --prefix FOLDER installation folder (default ~/.local/share/madalean) --config-dir FOLDER settings and data folder (default ~/.config/madalean) --cache-dir FOLDER cache folder (default ~/.cache/madalean) --no-systemd does not install the systemd service (you then start Madalean yourself) --no-desktop adds no entry to the applications menu --port N, --remote-port N server ports: local interface (default 11500) and access of linked devices (default 11501) Where your choices are recorded The choices made at installation (local models, SageMath, LaTeX…) are written to ~/.config/madalean/setup.json. Madalean reads this file at first start and applies the settings that follow from it, for example sagesource (which SageMath to use) and texengine (which LaTeX to use); you can change them at any time (the application also reads them through GET /api/setup). See First configuration › Choices made at installation. At the first start in the browser on the host, the “First steps” assistant shows these choices again (recommended choice and reason for this machine) and lets you change them. Where things are What Where Madalean and all its components ~/.local/share/madalean/ Installation log ~/.local/share/madalean/install.log Settings, installation choices, projects, dossiers, linked devices, keys (if no keyring) ~/.config/madalean/ Search index, caches ~/.cache/madalean/ Local models ~/models/ Jupyter notebooks ~/Documents/Madalean/notebooks/ systemd service ~/.config/systemd/user/madalean.service At first start, if you had Lean AI Station 1.x, the server copies (never moves) your settings, dossiers and library from ~/.config/lean-ai-station/. Starting and stopping The service starts with your session. Open the interface on the host: “Madalean Server” in the applications menu, or http://127.0.0.1:11500 in a browser. “Madalean Server” is the host computer’s app: it shows Madalean in its own window (no pairing code: it is this computer) and, in its Server menu (or its icon next to the clock), the server’s status, Start, Stop, Restart, Open the logs and Open in the browser. When the server stops, the window shows the server panel; when it comes back, the window returns to Madalean by itself. If the service is not installed, the panel says so and gives the command to reinstall it. The “Madalean” app (AppImage, no badge) is for the other computers: see Link a device. In a terminal, if needed: Next: First configuration, then First run for a first statement. Installing without a network For a computer without Internet access: on a connected computer where Madalean is installed, ./exportoffline.sh prepares a folder with everything needed (packages, components, Lean workspaces, models). Copy this folder to the other computer (USB stick, disk), then: SHA-256 fingerprints are checked as for an online installation. Updating Madalean updates from the application, in “Settings › Updates”: each new version is signed, checked, installed next to the old one, then put into service; the previous version is kept to roll back. There is no need to run install.sh again. Details: Updates. Uninstalling From the source folder (or ~/.local/share/madalean/current): The script first lists exactly what will be removed, with the size of each item, then asks for confirmation. It first stops the service and all its processes. Removed Kept ~/.local/share/madalean (environment, components, Lean workspaces installed by Madalean, TeX bundle, Tailscale node state, Madalean versions) ~/.config/madalean: your settings, projects, dossiers, linked devices and keys ~/.cache/madalean ~/models: your models the systemd service and the menu entry ~/Documents/Madalean: your notebooks never touched: ~/.elan, system packages, the system's Tailscale Options: Option Effect --purge also offers, with one question each, to remove ~/.config/madalean and ~/models --yes does not ask the general confirmation (the --purge questions are still asked) --prefix, --config-dir, --cache-dir give them if you changed them at installation Keys stored in the system keyring stay in the keyring: remove them first in “Settings › Providers” (“Remove the key”) if you want them erased.`},{id:`components`,lang:`en`,title:`What Madalean installs, component by component`,order:12,section:`start`,audience:`all`,summary:`Lean, SageMath, JupyterLab, local models, LaTeX, Python, Tailscale, Ollama, bubblewrap — what each is for, whether it is required, its size, where it lives, whether to reuse what is already installed, and how to repair or remove it.`,source:`en/components.md`,site_path:`en/components.html`,headings:[{level:1,text:`What Madalean installs, component by component`,id:`what-madalean-installs-component-by-component`},{level:2,text:`Overview`,id:`overview`},{level:2,text:`Repair, install later, remove`,id:`repair-install-later-remove`},{level:2,text:`Lean, elan and the Mathlib workspaces`,id:`lean-elan-and-the-mathlib-workspaces`},{level:2,text:`SageMath`,id:`sagemath`},{level:2,text:`JupyterLab`,id:`jupyterlab`},{level:2,text:`Local models`,id:`local-models`},{level:2,text:`LaTeX`,id:`latex`},{level:2,text:`Python`,id:`python`},{level:2,text:`Tailscale`,id:`tailscale`},{level:2,text:`Ollama`,id:`ollama`},{level:2,text:`bubblewrap, the sandbox`,id:`bubblewrap-the-sandbox`}],images:[],verify:[],body:`# What Madalean installs, component by component

Madalean relies on several programs: Lean to check proofs, SageMath to compute, LaTeX to typeset PDFs, AI models…
For each of them this page says **what it is for**, whether it is **required**, **how much space** it takes,
**where it lives**, and whether it is better to **reuse** a version already installed on your computer or to let
Madalean install **its own copy**.

One principle holds for all of them: Madalean installs its components in **its own folder**,
\`~/.local/share/madalean\` (called “Madalean's folder” below). It never modifies the programs of your system and never
runs \`sudo\` or your distribution's package manager. When it reuses a program that is already installed, it does so
**read-only**.

## Overview

| Component | Used for | Required | Space | Where |
|---|---|---|---|---|
| [Lean, elan, Mathlib workspaces](#lean-elan-and-the-mathlib-workspaces) | checking every proof | yes | ≈ 5 GB per built workspace | Madalean's folder |
| [SageMath](#sagemath) | the “Calcul” screen, experiments | no | ≈ 5 GB (Madalean's copy) | Madalean's folder, or the system's |
| [JupyterLab](#jupyterlab) | notebooks | yes (included) | part of the main environment | Madalean's folder |
| [Local models](#local-models) | working without Internet | no | ≈ 5 GB per model | \`~/models\` |
| [LaTeX](#latex) | PDF export | yes (included) | ≈ 50 MB for the TeX bundle | Madalean's folder, or the system's TeX Live |
| [Python](#python) | running Madalean | yes (included) | part of the main environment | Madalean's folder |
| [Tailscale](#tailscale) | reaching the host from your devices | yes (included) | ≈ 25 MB | Madalean's folder |
| [Ollama](#ollama) | — (optional, already yours) | no | — | the system's |
| [bubblewrap](#bubblewrap-the-sandbox) | isolating compilations and computations | recommended | < 1 MB | system package |

The main environment (Python, JupyterLab, tectonic, poppler, git…) takes ≈ 1.3 GB once installed.

## Repair, install later, remove

**In the application.** “Settings › System”, “Health” part, checks each component (Lean workspaces, local model
server, models, LaTeX, fonts, Jupyter, SageMath, sandbox, disk). A line with a problem has a “Repair” button when a
repair exists; “Check again” runs the check again. Repairs are started from the host computer. “Settings ›
Updates”, “Tracked components” part, shows the installed version of Lean, Mathlib, SageMath and LaTeX, and the
“System components” part the programs you install yourself (such as bubblewrap), with the exact command and the
“Open a terminal with the command” button.

The “Tools” step of the [“First steps”](first-config.md#the-first-steps-assistant) assistant (logo menu › “First
steps”) lists the same components, each with its state (installed, installed on first use, missing, new version
ready) and an “Install”, “Install now” or “Update” button that shows the stage and the percentage while installing.

**In a terminal**, on the host, the same tool \`install.sh\` uses:

\`\`\`bash
cd ~/.local/share/madalean/current
~/.local/share/madalean/env/bin/python -m madalean.deps health           # state of each component
~/.local/share/madalean/env/bin/python -m madalean.deps install sage     # install or repair a component
~/.local/share/madalean/env/bin/python -m madalean.deps list             # known components, versions
\`\`\`

Component names are \`micromamba\`, \`env\` (the main environment), \`sage\`, \`fonts\`, \`tex-bundle\`, \`elan\`, \`llama.cpp\`
and \`madalean-net\`. \`rollback <component>\` goes back to a component's previous version. Running \`./install.sh\` again
also repairs whatever is missing, without redoing what is fine.

**Removing** a required component makes no sense; everything goes away with [uninstalling](install.md#uninstalling).
Optional components are removed as described in their part.

## Lean, elan and the Mathlib workspaces

**What it is for.** Lean is the proof checker: it decides, and nothing is declared proved without its approval.
Mathlib is the large library of mathematics written in Lean. A **workspace** (or Lean workspace) is a version of Lean
together with an already compiled Mathlib, ready to use. **elan** is the small program that installs and selects
Lean versions.

**Required**: yes.

**The workspaces.**

| Workspace | Content | Role |
|---|---|---|
| “Current Lean” (\`lean-current\`) | a recent Lean (v4.34.1 when this page was written) and the matching Mathlib | the default workspace, kept up to date |
| “Prover” (\`lean-prover49\`) | Lean 4.9 and the Mathlib of that time | the one the Goedel models were trained on; never updated |

**Space**: ≈ 5 GB per built workspace; elan itself is ≈ 5 MB.

**Where**: \`~/.local/share/madalean/workspaces/\` and \`~/.local/share/madalean/elan/\`.

**Reuse or not.** If Lean workspaces are already built on the computer (for example those of Lean AI Station 1.x),
\`install.sh\` **reuses them through hard links**: files are not copied, no extra space. Lean versions already in your
\`~/.elan\` are read for this import, **never modified**. This is the recommended solution when possible. Otherwise,
\`./install.sh --build-workspace\` builds the “Current Lean” workspace (≈ 5 GB, network needed, it takes a good while).
The “Prover” workspace is not built by the script: it is reused if it exists.

**Install later, repair**: “Settings › Lean workspaces” gives the state of each workspace; run
\`./install.sh --build-workspace\` again if none is installed. New versions of Lean and Mathlib are installed from
“Settings › Updates” (see [Updates](updates.md)).

## SageMath

**What it is for.** SageMath is free software for mathematical computation (algebra, number theory,
combinatorics, plots…). Madalean uses it in the “Calcul” screen, for the experiments of the conjecture workshop and
for the examples and figures of an article. See [Calcul](calcul.md).

**Required**: no. Without SageMath, Python notebooks work, and so does the rest of Madalean.

**Two possibilities.**

| | Madalean's copy | Your system's SageMath |
|---|---|---|
| Version | SageMath 10.10 | yours, **10.0 or newer** |
| Space | ≈ 1.4 GB to download, ≈ 5 GB on disk | none extra |
| Updates | by Madalean (“Tracked components”) | by your distribution |
| Condition | none | the Jupyter kernel \`sagemath\` must be installed (for example in \`/usr/share/jupyter/kernels/sagemath\`) |

**What is recommended.** If your system already has a compatible SageMath (version ≥ 10.0 **and** its Jupyter
kernel \`sagemath\`), reuse it: you save 5 GB and your distribution keeps it up to date. Otherwise, let Madalean
install its own copy. In both cases, the computation runs in **the same sandbox**: no network, no access to your home
folder (see [bubblewrap](#bubblewrap-the-sandbox)).

**The \`sage_source\` setting** fixes this choice:

| Value | Effect |
|---|---|
| \`auto\` (default) | Madalean's copy when it is installed, else the system's |
| \`own\` | always Madalean's copy |
| \`system\` | always the system's |

It is written at installation (\`--sage\`, or the choice made in the graphical installer) and can then be changed in
the application, in the “Tools” step of the “First steps” assistant (logo menu, or “Settings”, link “First steps”),
which shows the recommended choice with its reason and the copy in use right now. “The system's” is only offered
there when a compatible SageMath is present.

**Install later.** By default (\`--sage later\`), Madalean's copy is installed **on first use**: in a SageMath notebook
of the “Calcul” screen, “Install SageMath” button, on the host computer; the screen shows the step and the
percentage. To install it right away: \`./install.sh --sage now\`, or \`python -m madalean.deps install sage\` (see
[above](#repair-install-later-remove)).

**Removing Madalean's copy**: stop Madalean (\`systemctl --user stop madalean\`), delete
\`~/.local/share/madalean/envs/sage\` and the \`~/.local/share/madalean/envs/sage-…\` folders, then start it again.
The application has no button for this. Afterwards SageMath shows again as “installed on first use”, and with
\`sage_source\` on \`auto\` the system's SageMath is used when there is one.

## JupyterLab

**What it is for.** JupyterLab is the notebook environment: cells of code and their results. Madalean uses it for
the notebooks of the “Calcul” screen and for the “Notebook” screen (see [Jupyter and Sage](jupyter.md)).

**Required**: yes, it is part of Madalean's main environment; there is nothing to choose.

**Where**: in the main environment, \`~/.local/share/madalean/env/\`. The notebooks themselves are stored in
\`~/Documents/Madalean/notebooks/\`.

**Access from your other devices**: off by default. The \`remote_jupyter\` setting (“Settings › Notebook and access” ›
“Open the notebook to linked devices”, on the host only) opens it to linked devices. A notebook runs code on the
host: only turn it on if you trust your devices.

**Repair**: “Jupyter” line of “Health”, “Repair” button.

## Local models

**What they are for.** AI models that run **on the host computer**, without sending anything to the Internet. They
are used in *Local* mode (nothing leaves the computer) and, in *Automatic* mode, when the Internet is missing. See
[Models and keys](models-keys.md).

**Required**: no. Without a local model, Madalean uses online models (free, or with your keys).

**The engine, llama.cpp.** This is the program that runs the models. \`install.sh\` chooses the version suited to your
computer from the NVIDIA driver: a version for the graphics card (CUDA) if the driver is suitable, otherwise a
processor version (\`--cpu\` / \`--gpu\` force the choice). It is installed in Madalean's folder (≈ 25 MB for the
processor, ≈ 650 MB with the CUDA libraries), even if you take no model.

**The three models** (GGUF files, Q4_K_M quantization), in \`~/models\`:

| File | Role | Size |
|---|---|---|
| \`Goedel-Prover-V2-8B.Q4_K_M.gguf\` | the **prover**: writes Lean proofs | ≈ 5 GB |
| \`Goedel-Formalizer-V2-8B.Q4_K_M.gguf\` | the **translator**: puts statements into Lean | ≈ 5 GB |
| \`Qwen3-8B-Q4_K_M.gguf\` | the **explainer**: explanations and written proofs | ≈ 5 GB |

**When it is worth it.** A local model is only useful if it runs on a large enough graphics card. The recommended
plan follows this rule:

| Your computer | Advice |
|---|---|
| NVIDIA card with 10 GB of graphics memory or more, and 16 GB of RAM or more | all three models (\`--models all\`) |
| NVIDIA card with 8 to 10 GB of graphics memory | the prover only (\`--models prover\`) |
| less than 8 GB, or no NVIDIA card | **no local model advised** (\`--models none\`) |

Without a suitable card, a local model runs on the processor: a single answer can take many minutes, whereas online
models are both faster and better. As an order of magnitude, the prover is set up for a context of 24,000 tokens,
which takes about 7 GB of graphics memory.

**Reuse or not.** Files already in \`~/models\` (with their \`.sha256\` fingerprint) are reused and never moved.

**Adding a model later**: run \`./install.sh --models all\` again (only missing files are downloaded), or download a
specific model from the source folder:

\`\`\`bash
./scripts/download_model.sh Q4_K_M formalizer explainer   # prover, translator, explainer
\`\`\`

(any subset; \`Q4_K_M\` stands for the prover). Each file is checked against its fingerprint.

**Freeing the graphics card.** The local model is stopped after 10 minutes without work, to give the graphics memory
back to other programs (setting \`local_idle_unload_minutes\`, 0 = never; see
[First configuration](first-config.md#automatic-and-manual-behaviours)).

**Removing a model**: delete its file (and the \`.sha256\` next to it) in \`~/models\`. Madalean stops offering it;
uninstalling, by contrast, keeps \`~/models\`.

## LaTeX

**What it is for.** LaTeX typesets PDF documents: export of a dossier, a written proof, an article.

**Required**: yes, and included. Without LaTeX, Madalean opens an HTML version to print from the browser.

**Two possibilities.**

| | Madalean's LaTeX (recommended) | Your system's TeX Live |
|---|---|---|
| Program | **tectonic**, in the main environment | \`xelatex\` or \`lualatex\`, with \`latexmk\` |
| LaTeX packages | a fixed TeX bundle (version v33, ≈ 50 MB), downloaded once at installation | all those of your installation |
| Network | none after installation | none |
| Sandbox | yes | yes |

**What is recommended.** Madalean's LaTeX: it gives **the same result on every computer** (the TeX bundle is fixed
and verified), works **offline** and runs in the sandbox. An existing TeX Live is used anyway **as a fallback** if
tectonic fails. Choose to use it **first** if you need LaTeX packages missing from Madalean's TeX bundle; it then
requires TeX Live 2022 or newer, with \`fontspec\`.

**The \`tex_engine\` setting**:

| Value | Effect |
|---|---|
| \`auto\` (default) | tectonic first, the system's TeX Live as a fallback |
| \`tectonic\` | tectonic only |
| \`system\` | the system's TeX Live first |

It is written at installation (\`--tex own\` or \`--tex system\`, or the choice made in the graphical installer), and
changed in the “Tools” step of the “First steps” assistant. With \`system\` the export tries the system's XeLaTeX,
then LuaLaTeX, and tectonic last; with \`tectonic\`, tectonic only (this choice is refused while Madalean's tectonic is
not installed).

**Repair**: “LaTeX (PDF export)” line of “Health”, “Repair” button, or \`python -m madalean.deps install tex-bundle\`.
The fonts used in PDFs (DejaVu Sans Mono, Noto Sans Math) are installed with Madalean and checked in the same place.

## Python

Madalean has **its own Python** (3.13), in its main environment (\`~/.local/share/madalean/env/\`). Your system's
Python is **never modified**, and the server does not use it. Only the launcher of the experiment kernels may find
it on your system, if there is one, to start a Python kernel in the sandbox. Nothing to choose, nothing to install.

## Tailscale

**What it is for.** Tailscale creates an encrypted private network between your devices (your “tailnet”). Madalean
uses it so that your phone, your tablet or another PC can reach the host computer, without opening anything to the
Internet.

**Included**: Madalean ships **its own Tailscale node**, \`madalean-net\` (≈ 25 MB, in Madalean's folder). It shows up
as “madalean” in your tailnet. It needs neither \`sudo\` nor a system service.

**A Tailscale already installed** on the host can stay: no conflict, both coexist.

**Setting up**: the node must be approved once in your Tailscale account, then each device is linked. See
[Link a device](pairing.md) and [Tailscale](tailscale.md).

## Ollama

Ollama is another program that runs models locally. Madalean **does not install it** and does not need it. If it is
already installed and running on the host, its models show up among the available local models and can be chosen;
the two programs coexist without conflict.

**Sharing the graphics card with Ollama** (“Settings › Models”, “Local models” part; on by default, useful only when
Ollama runs). Both programs do not fit together on an 8 GB card. When Madalean's local model does not fit, Madalean
asks Ollama to unload its models (Ollama's own request: nothing is stopped, Ollama reloads them by itself on its next
request, in about 3 seconds), loads its own, then gives the card back after \`local_idle_unload_minutes\` without work.
**Never while Ollama is answering another application**: Madalean waits for it to finish (30 s at most, adjustable),
then, depending on the setting, loads its model with the free memory (partly on the processor, slower) or moves on to
the next model (online). The status panel (top-right button) and “Settings › System › Health” say in plain words who
holds the card.

## bubblewrap, the sandbox

**What it is for.** bubblewrap is a small Linux tool that locks a program in a **sandbox**: no network, no access to
your home folder, with Lean and Mathlib read-only. Madalean uses it for every Lean compilation, every LaTeX
compilation and every computation (SageMath, Python). This is an important protection, since the code compiled or
run may come from an AI model. See [Security](security.md).

**Required**: no, but **strongly recommended**. Without bubblewrap, compilations and computations run without this
isolation; “Settings › System” shows whether the sandbox is active.

**Installing**: it is a package of your distribution, which Madalean cannot install for you (that would need \`sudo\`).
Run the command for your system yourself:

| Distribution | Command |
|---|---|
| Arch Linux, Manjaro | \`sudo pacman -S bubblewrap\` |
| Debian, Ubuntu, Linux Mint | \`sudo apt install bubblewrap\` |
| Fedora | \`sudo dnf install bubblewrap\` |
| openSUSE | \`sudo zypper install bubblewrap\` |

Then “Check again” in “Settings › System”: the sandbox line should turn fine.
`,text:`What Madalean installs, component by component Madalean relies on several programs: Lean to check proofs, SageMath to compute, LaTeX to typeset PDFs, AI models… For each of them this page says what it is for, whether it is required, how much space it takes, where it lives, and whether it is better to reuse a version already installed on your computer or to let Madalean install its own copy. One principle holds for all of them: Madalean installs its components in its own folder, ~/.local/share/madalean (called “Madalean's folder” below). It never modifies the programs of your system and never runs sudo or your distribution's package manager. When it reuses a program that is already installed, it does so read-only. Overview Component Used for Required Space Where Lean, elan, Mathlib workspaces checking every proof yes ≈ 5 GB per built workspace Madalean's folder SageMath the “Calcul” screen, experiments no ≈ 5 GB (Madalean's copy) Madalean's folder, or the system's JupyterLab notebooks yes (included) part of the main environment Madalean's folder Local models working without Internet no ≈ 5 GB per model ~/models LaTeX PDF export yes (included) ≈ 50 MB for the TeX bundle Madalean's folder, or the system's TeX Live Python running Madalean yes (included) part of the main environment Madalean's folder Tailscale reaching the host from your devices yes (included) ≈ 25 MB Madalean's folder Ollama — (optional, already yours) no — the system's bubblewrap isolating compilations and computations recommended < 1 MB system package The main environment (Python, JupyterLab, tectonic, poppler, git…) takes ≈ 1.3 GB once installed. Repair, install later, remove In the application. “Settings › System”, “Health” part, checks each component (Lean workspaces, local model server, models, LaTeX, fonts, Jupyter, SageMath, sandbox, disk). A line with a problem has a “Repair” button when a repair exists; “Check again” runs the check again. Repairs are started from the host computer. “Settings › Updates”, “Tracked components” part, shows the installed version of Lean, Mathlib, SageMath and LaTeX, and the “System components” part the programs you install yourself (such as bubblewrap), with the exact command and the “Open a terminal with the command” button. The “Tools” step of the “First steps” assistant (logo menu › “First steps”) lists the same components, each with its state (installed, installed on first use, missing, new version ready) and an “Install”, “Install now” or “Update” button that shows the stage and the percentage while installing. In a terminal, on the host, the same tool install.sh uses: Component names are micromamba, env (the main environment), sage, fonts, tex-bundle, elan, llama.cpp and madalean-net. rollback <component> goes back to a component's previous version. Running ./install.sh again also repairs whatever is missing, without redoing what is fine. Removing a required component makes no sense; everything goes away with uninstalling. Optional components are removed as described in their part. Lean, elan and the Mathlib workspaces What it is for. Lean is the proof checker: it decides, and nothing is declared proved without its approval. Mathlib is the large library of mathematics written in Lean. A workspace (or Lean workspace) is a version of Lean together with an already compiled Mathlib, ready to use. elan is the small program that installs and selects Lean versions. Required: yes. The workspaces. Workspace Content Role “Current Lean” (lean-current) a recent Lean (v4.34.1 when this page was written) and the matching Mathlib the default workspace, kept up to date “Prover” (lean-prover49) Lean 4.9 and the Mathlib of that time the one the Goedel models were trained on; never updated Space: ≈ 5 GB per built workspace; elan itself is ≈ 5 MB. Where: ~/.local/share/madalean/workspaces/ and ~/.local/share/madalean/elan/. Reuse or not. If Lean workspaces are already built on the computer (for example those of Lean AI Station 1.x), install.sh reuses them through hard links: files are not copied, no extra space. Lean versions already in your ~/.elan are read for this import, never modified. This is the recommended solution when possible. Otherwise, ./install.sh --build-workspace builds the “Current Lean” workspace (≈ 5 GB, network needed, it takes a good while). The “Prover” workspace is not built by the script: it is reused if it exists. Install later, repair: “Settings › Lean workspaces” gives the state of each workspace; run ./install.sh --build-workspace again if none is installed. New versions of Lean and Mathlib are installed from “Settings › Updates” (see Updates). SageMath What it is for. SageMath is free software for mathematical computation (algebra, number theory, combinatorics, plots…). Madalean uses it in the “Calcul” screen, for the experiments of the conjecture workshop and for the examples and figures of an article. See Calcul. Required: no. Without SageMath, Python notebooks work, and so does the rest of Madalean. Two possibilities. Madalean's copy Your system's SageMath Version SageMath 10.10 yours, 10.0 or newer Space ≈ 1.4 GB to download, ≈ 5 GB on disk none extra Updates by Madalean (“Tracked components”) by your distribution Condition none the Jupyter kernel sagemath must be installed (for example in /usr/share/jupyter/kernels/sagemath) What is recommended. If your system already has a compatible SageMath (version ≥ 10.0 and its Jupyter kernel sagemath), reuse it: you save 5 GB and your distribution keeps it up to date. Otherwise, let Madalean install its own copy. In both cases, the computation runs in the same sandbox: no network, no access to your home folder (see bubblewrap). The sagesource setting fixes this choice: Value Effect auto (default) Madalean's copy when it is installed, else the system's own always Madalean's copy system always the system's It is written at installation (--sage, or the choice made in the graphical installer) and can then be changed in the application, in the “Tools” step of the “First steps” assistant (logo menu, or “Settings”, link “First steps”), which shows the recommended choice with its reason and the copy in use right now. “The system's” is only offered there when a compatible SageMath is present. Install later. By default (--sage later), Madalean's copy is installed on first use: in a SageMath notebook of the “Calcul” screen, “Install SageMath” button, on the host computer; the screen shows the step and the percentage. To install it right away: ./install.sh --sage now, or python -m madalean.deps install sage (see above). Removing Madalean's copy: stop Madalean (systemctl --user stop madalean), delete ~/.local/share/madalean/envs/sage and the ~/.local/share/madalean/envs/sage-… folders, then start it again. The application has no button for this. Afterwards SageMath shows again as “installed on first use”, and with sagesource on auto the system's SageMath is used when there is one. JupyterLab What it is for. JupyterLab is the notebook environment: cells of code and their results. Madalean uses it for the notebooks of the “Calcul” screen and for the “Notebook” screen (see Jupyter and Sage). Required: yes, it is part of Madalean's main environment; there is nothing to choose. Where: in the main environment, ~/.local/share/madalean/env/. The notebooks themselves are stored in ~/Documents/Madalean/notebooks/. Access from your other devices: off by default. The remotejupyter setting (“Settings › Notebook and access” › “Open the notebook to linked devices”, on the host only) opens it to linked devices. A notebook runs code on the host: only turn it on if you trust your devices. Repair: “Jupyter” line of “Health”, “Repair” button. Local models What they are for. AI models that run on the host computer, without sending anything to the Internet. They are used in Local mode (nothing leaves the computer) and, in Automatic mode, when the Internet is missing. See Models and keys. Required: no. Without a local model, Madalean uses online models (free, or with your keys). The engine, llama.cpp. This is the program that runs the models. install.sh chooses the version suited to your computer from the NVIDIA driver: a version for the graphics card (CUDA) if the driver is suitable, otherwise a processor version (--cpu / --gpu force the choice). It is installed in Madalean's folder (≈ 25 MB for the processor, ≈ 650 MB with the CUDA libraries), even if you take no model. The three models (GGUF files, Q4KM quantization), in ~/models: File Role Size Goedel-Prover-V2-8B.Q4KM.gguf the prover: writes Lean proofs ≈ 5 GB Goedel-Formalizer-V2-8B.Q4KM.gguf the translator: puts statements into Lean ≈ 5 GB Qwen3-8B-Q4KM.gguf the explainer: explanations and written proofs ≈ 5 GB When it is worth it. A local model is only useful if it runs on a large enough graphics card. The recommended plan follows this rule: Your computer Advice NVIDIA card with 10 GB of graphics memory or more, and 16 GB of RAM or more all three models (--models all) NVIDIA card with 8 to 10 GB of graphics memory the prover only (--models prover) less than 8 GB, or no NVIDIA card no local model advised (--models none) Without a suitable card, a local model runs on the processor: a single answer can take many minutes, whereas online models are both faster and better. As an order of magnitude, the prover is set up for a context of 24,000 tokens, which takes about 7 GB of graphics memory. Reuse or not. Files already in ~/models (with their .sha256 fingerprint) are reused and never moved. Adding a model later: run ./install.sh --models all again (only missing files are downloaded), or download a specific model from the source folder: (any subset; Q4KM stands for the prover). Each file is checked against its fingerprint. Freeing the graphics card. The local model is stopped after 10 minutes without work, to give the graphics memory back to other programs (setting localidleunloadminutes, 0 = never; see First configuration). Removing a model: delete its file (and the .sha256 next to it) in ~/models. Madalean stops offering it; uninstalling, by contrast, keeps ~/models. LaTeX What it is for. LaTeX typesets PDF documents: export of a dossier, a written proof, an article. Required: yes, and included. Without LaTeX, Madalean opens an HTML version to print from the browser. Two possibilities. Madalean's LaTeX (recommended) Your system's TeX Live Program tectonic, in the main environment xelatex or lualatex, with latexmk LaTeX packages a fixed TeX bundle (version v33, ≈ 50 MB), downloaded once at installation all those of your installation Network none after installation none Sandbox yes yes What is recommended. Madalean's LaTeX: it gives the same result on every computer (the TeX bundle is fixed and verified), works offline and runs in the sandbox. An existing TeX Live is used anyway as a fallback if tectonic fails. Choose to use it first if you need LaTeX packages missing from Madalean's TeX bundle; it then requires TeX Live 2022 or newer, with fontspec. The texengine setting: Value Effect auto (default) tectonic first, the system's TeX Live as a fallback tectonic tectonic only system the system's TeX Live first It is written at installation (--tex own or --tex system, or the choice made in the graphical installer), and changed in the “Tools” step of the “First steps” assistant. With system the export tries the system's XeLaTeX, then LuaLaTeX, and tectonic last; with tectonic, tectonic only (this choice is refused while Madalean's tectonic is not installed). Repair: “LaTeX (PDF export)” line of “Health”, “Repair” button, or python -m madalean.deps install tex-bundle. The fonts used in PDFs (DejaVu Sans Mono, Noto Sans Math) are installed with Madalean and checked in the same place. Python Madalean has its own Python (3.13), in its main environment (~/.local/share/madalean/env/). Your system's Python is never modified, and the server does not use it. Only the launcher of the experiment kernels may find it on your system, if there is one, to start a Python kernel in the sandbox. Nothing to choose, nothing to install. Tailscale What it is for. Tailscale creates an encrypted private network between your devices (your “tailnet”). Madalean uses it so that your phone, your tablet or another PC can reach the host computer, without opening anything to the Internet. Included: Madalean ships its own Tailscale node, madalean-net (≈ 25 MB, in Madalean's folder). It shows up as “madalean” in your tailnet. It needs neither sudo nor a system service. A Tailscale already installed on the host can stay: no conflict, both coexist. Setting up: the node must be approved once in your Tailscale account, then each device is linked. See Link a device and Tailscale. Ollama Ollama is another program that runs models locally. Madalean does not install it and does not need it. If it is already installed and running on the host, its models show up among the available local models and can be chosen; the two programs coexist without conflict. Sharing the graphics card with Ollama (“Settings › Models”, “Local models” part; on by default, useful only when Ollama runs). Both programs do not fit together on an 8 GB card. When Madalean's local model does not fit, Madalean asks Ollama to unload its models (Ollama's own request: nothing is stopped, Ollama reloads them by itself on its next request, in about 3 seconds), loads its own, then gives the card back after localidleunloadminutes without work. Never while Ollama is answering another application: Madalean waits for it to finish (30 s at most, adjustable), then, depending on the setting, loads its model with the free memory (partly on the processor, slower) or moves on to the next model (online). The status panel (top-right button) and “Settings › System › Health” say in plain words who holds the card. bubblewrap, the sandbox What it is for. bubblewrap is a small Linux tool that locks a program in a sandbox: no network, no access to your home folder, with Lean and Mathlib read-only. Madalean uses it for every Lean compilation, every LaTeX compilation and every computation (SageMath, Python). This is an important protection, since the code compiled or run may come from an AI model. See Security. Required: no, but strongly recommended. Without bubblewrap, compilations and computations run without this isolation; “Settings › System” shows whether the sandbox is active. Installing: it is a package of your distribution, which Madalean cannot install for you (that would need sudo). Run the command for your system yourself: Distribution Command Arch Linux, Manjaro sudo pacman -S bubblewrap Debian, Ubuntu, Linux Mint sudo apt install bubblewrap Fedora sudo dnf install bubblewrap openSUSE sudo zypper install bubblewrap Then “Check again” in “Settings › System”: the sandbox line should turn fine.`},{id:`first-config`,lang:`en`,title:`First configuration`,order:15,section:`start`,audience:`all`,summary:`After installing — the keys of online providers (where to get them, what is free, what it costs), Claude as conductor and paid reinforcement, the Local / Automatic / Online modes, Learn or Research, and each automatic behaviour with its default setting.`,source:`en/first-config.md`,site_path:`en/first-config.html`,headings:[{level:1,text:`First configuration`,id:`first-configuration`},{level:2,text:`The “First steps” assistant`,id:`the-first-steps-assistant`},{level:2,text:`Keys of online providers`,id:`keys-of-online-providers`},{level:3,text:`Adding a key`,id:`adding-a-key`},{level:3,text:`Where keys are kept`,id:`where-keys-are-kept`},{level:3,text:`Where to start`,id:`where-to-start`},{level:3,text:`The providers, one by one`,id:`the-providers-one-by-one`},{level:3,text:`Hugging Face token: Goedel-Prover 32B online`,id:`hugging-face-token-goedel-prover-32b-online`},{level:3,text:`Claude: conductor and paid reinforcement`,id:`claude-conductor-and-paid-reinforcement`},{level:2,text:`Where the models work`,id:`where-the-models-work`},{level:2,text:`Learn or Research`,id:`learn-or-research`},{level:2,text:`Automatic and manual behaviours`,id:`automatic-and-manual-behaviours`},{level:2,text:`Choices made at installation`,id:`choices-made-at-installation`},{level:2,text:`Checklist`,id:`checklist`}],images:[{src:`img/wizard-tools.png`,exists:!0},{src:`img/settings-keys.png`,exists:!0},{src:`img/settings-models.png`,exists:!0}],verify:[],body:`# First configuration

Once Madalean is installed (see [Installing Madalean](install.md)), it **works right away, without any key**: free
online providers that need no account and, if you installed them, the local models are enough to get started. This
page reviews what is worth setting next, in the order you will meet it:

1. the **keys** of online providers, which give access to stronger models;
2. **where the models work**: *Local*, *Automatic* or *Online*;
3. **Learn** or **Research**, and your profile;
4. the **automatic behaviours**, which you can make manual.

Everything is in “Settings” (the gear icon at the top right). A [checklist](#checklist) sums it all up at the end of
the page.

## The “First steps” assistant

When you open Madalean for the first time **on the host computer**, the “First steps” assistant opens full screen and
guides you through these same choices, in the order of this page. Your linked devices (phone, tablet, other PC)
never see it: it only opens where Madalean is installed.

![First steps: the tools](img/wizard-tools.png)

| Step | What you do there | More |
|---|---|---|
| Welcome | see what lies ahead, the machine's resources, choose the language | — |
| Tools | see the installed and missing components, **install or repair** them (with progress); choose which SageMath (\`sage_source\`) and which LaTeX (\`tex_engine\`) to use, with the recommended choice and its reason; the command to type yourself for bubblewrap | [Components](components.md) |
| Local model | none, the prover model or all three, depending on your graphics card (recommended choice and download size); “Download” fetches the missing files, verified | [Local models](components.md#local-models) |
| Free keys | one card per provider (Groq, Gemini, Tavily first): what it is good for, what is free, where to create the key; paste it, “Save”, “Test” | [Keys](#keys-of-online-providers) |
| Hugging Face | the token for Goedel-Prover 32B online, and the \`hf_goedel\` switch | [below](#hugging-face-token-goedel-prover-32b-online) |
| Claude | the Anthropic key, the caps per request, per proof and per month, the paid reinforcement | [below](#claude-conductor-and-paid-reinforcement) |
| Modes | *Local*, *Automatic* or *Online* (recommended choice for the machine); Learn or Research | [below](#where-the-models-work) |
| Automatic or manual | experiments without approval, conductor, stages in parallel, warm Lean, pause after the translation, updates | [below](#automatic-and-manual-behaviours) |
| Devices | link a phone or another PC (the same screen as “Settings › Devices”) | [Link a device](pairing.md) |
| Summary | the [checklist](#checklist), checked again, and your choices; “Finish” | — |

- Every step has a “Help” link to the manual page that explains it.
- Every step can be **skipped** (“Skip this step”); every choice is **saved at once**, except keys, which are saved
  (and tested) only by their “Save” button.
- “**Later**” closes the assistant. It no longer opens by itself, but a “First steps” card stays on the home screen
  until you finish it (“Resume”, or “Don't show again”). The assistant resumes **where you stopped**: from that card,
  from the menu (the logo), “First steps” entry, or from “Settings”, link “First steps: the setup assistant”.
- After an update from version 2.0.0 the assistant does not open by itself (your work is already there): the home
  card offers it.
- The four-step tour of the home screen ([First run](first-run.md)) is separate: it shows how to prove a first
  statement.

## Keys of online providers

An **API key** (or “token”) is a password specific to an online service: it lets Madalean use that service's models
on your behalf. It takes two minutes to create on the provider's site.

### Adding a key

“Settings › Providers” sorts online services by use (Lean proofs, writing, code, Internet search…), with, for each,
what is free and where your data goes. On a provider's card:

1. “Create a key” opens the provider's key page; create an account if needed, then create a key and copy it (it is
   often shown only once);
2. paste it on the card: Madalean **tests it at once** and says how many models it gives, or why it is refused;
3. “Remove the key” deletes it in one click.

![Settings › Providers](img/settings-keys.png)

### Where keys are kept

- In the **system keyring** (your desktop's password vault: GNOME Keyring, KWallet…), when the \`secret-tool\` tool is
  available;
- otherwise in the file \`~/.config/madalean/keys.json\`, readable by you only (permissions \`0600\`).

A key is **never shown** again, never written to the log, and **never passed to your linked devices**: the server
only says whether a key is set. It is sent only to **its** provider; Madalean refuses to attach it to any other
address.

### Where to start

For a good free start, without a bank card for the first two: **Groq** (fast models), **Google Gemini** (the strongest
free models) and **Tavily** (Internet search). Then add, as needed, a **Hugging Face** token for the best open Lean
prover, and an **Anthropic** key if you accept paying for Claude per use, within caps you set.

### The providers, one by one

Free tiers change often; each card of “Settings › Providers” shows the date they were checked. The information below
is that of this version of Madalean.

**Lean proofs**

| Provider | What it is for | Free? | Where to create the key |
|---|---|---|---|
| Hugging Face (Goedel-Prover-V2-32B) | the best open Lean prover, served online; it opens every proof | no: paid per token with Hugging Face credits (free account: no included credit; PRO account: $2 per month) | <https://huggingface.co/settings/tokens> |
| Mistral (Leanstral) | Mistral's Lean proof agent, put first in the tournament **if** your Mistral key offers it | announced free, but retired by Mistral on 2026-09-30; Madalean detects it by itself if it comes back | same key as Mistral, below |

**Writing, explanations, reasoning**

| Provider | What it is for | Free? | Where to create the key |
|---|---|---|---|
| Google Gemini | the strongest free models for writing (LaTeX, explanations) and reasoning | yes, with per-project limits; the free tier may be used by Google to improve its products: nothing confidential | <https://aistudio.google.com/apikey> |
| Mistral AI | very good in French; Codestral for code | billing must be activated to create a key; an existing key keeps working | <https://console.mistral.ai/api-keys> |
| Anthropic (Claude) | the strongest at Lean and writing; conductor and paid reinforcement (see [below](#claude-conductor-and-paid-reinforcement)) | no: paid per use | <https://console.anthropic.com/settings/keys> |

**Code (Sage, Python) and small tasks**

| Provider | What it is for | Free? | Where to create the key |
|---|---|---|---|
| Groq | very fast: Sage/Python code, small tasks, routing | yes, without a card (30 requests per minute, 1,000 per day per model) | <https://console.groq.com/keys> |
| Cerebras | very fast: code, computation, reasoning | trial: a one-time $5 credit, after adding a card | <https://cloud.cerebras.ai> |
| SambaNova Cloud | free backup model (code, maths) | yes, without a card (20 requests per day per model) | <https://cloud.sambanova.ai/apis> |

**General backup models, and paid models on request**

| Provider | What it is for | Free? | Where to create the key |
|---|---|---|---|
| OpenRouter | “:free” models | yes (50 requests per day; some free models require allowing training on your data) | <https://openrouter.ai/settings/keys> |
| NVIDIA NIM | trial catalogue, as a backup | limited free trial, for testing only; no confidential work | <https://build.nvidia.com> |
| OpenAI | GPT, only when you choose it | no: paid | <https://platform.openai.com/api-keys> |
| DeepSeek | good at maths and code, cheap, only when you choose it (servers in China) | no: paid | <https://platform.deepseek.com/api_keys> |

**Internet search** (for literature research, never in *Local* mode; only the query is sent)

| Provider | Free? | Where to create the key |
|---|---|---|
| Tavily | 1,000 searches per month, no card | <https://app.tavily.com> |
| Exa | $10 of free credits every month | <https://dashboard.exa.ai/api-keys> |
| Brave Search | $5 of free credits per month; a card is required | <https://api-dashboard.search.brave.com> |

**Without a key**, always available: the free models LLM7, OVHcloud, Kilo and Pollinations (what you send them may
be kept: for confidential work, use *Local* mode), Wikipedia for Internet search, arXiv, zbMATH, Crossref, OpenAlex
and Semantic Scholar for bibliography, LeanSearch and Loogle to search Mathlib.

**GitHub** has a card too: its token is used **only** to “Publish” (push a project's site to your GitHub
repository), never for models. See [Publishing a project](publish.md).

A paid model is never used behind your back: only if you chose it for a task, or as reinforcement within your caps
(Claude, Goedel 32B online). What each model receives, and the prices: [Models and keys](models-keys.md).

### Hugging Face token: Goedel-Prover 32B online

With a Hugging Face token, **Goedel-Prover-V2-32B** opens every proof: the same method as the local prover, with a
model four times larger, without using your graphics card.

1. Create an account on Hugging Face and add credits (calls are paid per token).
2. On the Hugging Face card, “Create a key” opens the token page, ready to create a token with the “Make calls to
   Inference Providers” permission; the token starts with \`hf_\`.
3. Paste it: Madalean checks it without charging anything and says whether Goedel 32B is available.

Setting \`hf_goedel\` (on by default): “Settings › Models › Advanced settings”, box “Goedel-Prover 32B online (Hugging
Face) opens every proof when the token is saved”. Its spending counts towards the monthly cap described below. One
attempt costs at most ≈ $0.11 (Madalean's conservative estimate).

### Claude: conductor and paid reinforcement

With an Anthropic key, Claude can play two roles, set in “Settings › Models”, “Claude as paid reinforcement” part:

| Role | Setting | Default | What it does |
|---|---|---|---|
| **Conductor** | \`conductor\`: “Let Claude direct each request” | on | Claude reads each request, picks the best model for each step, fixes what Lean rejects and checks at the end that statement, proof and explanation agree. Without an Anthropic key, the best free model takes this role. Lean remains the only judge of proofs |
| | \`conductor_cap_usd\`: “Cap per request” | $1 | once reached, Madalean asks whether to continue with Claude, for $0.50 more |
| **Paid reinforcement** | \`claude_reinforce\`: “Call on Claude when the free models fail” | on | Claude enters a proof's tournament **last**, only if the free models have all failed |
| | \`claude_cap_proof_usd\`: “Cap per proof” | $1 | beyond it, the call is not made and the proof says so |
| | \`claude_cap_month_usd\`: “Cap per month” | $20 | for **all** paid calls of the calendar month (Claude and Goedel 32B on Hugging Face) |
| | \`claude_model\`: “Claude model” | Automatic | the best Claude model for proving, or the one you impose |

Before each call, Madalean estimates its cost at the public price and does not make it if it would exceed a cap;
after the call, the real cost is recorded. The month's total and the latest calls are shown under the caps.
Anthropic's invoice is authoritative. Without an Anthropic key, none of these settings costs anything.

## Where the models work

“Settings › Models”, “Where the models work” part (setting \`mode\`). The indicator at the top of the screen shows at
all times the current mode and who receives your work.

![Settings › Models](img/settings-models.png)

| Mode | What happens | For whom |
|---|---|---|
| *Local* | nothing leaves the computer: only the models installed on the host work; any connection to the Internet is refused before it is opened | confidential work, computer without Internet; assumes [local models](components.md#local-models) and a good graphics card |
| *Automatic* (default) | online models; local models **only** without Internet, or if no online model can work | the best choice for almost everyone: fast, and the graphics card stays free |
| *Online* | online models only; without a network, the work fails with a clear message | computer without a local model |

A given dossier can have another mode than the general one (“Options for this dossier”, on the home screen). Just
below, “Proof search method” chooses between *Automatic* (an agent with the best online model if the mode allows it,
otherwise Goedel), *Agent* and *Goedel (local)*. Details of what is sent and to whom: [Models and keys](models-keys.md).

## Learn or Research

The button at the top right switches between two ways of working; the choice is kept **on each device** and can be
changed at any time:

- **Learn** (default): guided — hints before the proof, glossary on hover, line-by-line explanations, a tutor who
  has you explain in your own words. For whoever is discovering Lean, student or teacher.
- **Research**: dense, keyboard-oriented, nothing pedagogical in the way. For whoever uses Lean in a research
  project.

**Your profile** (“Settings › Profile”, setting \`profile\`) tells Madalean whom it is addressing: intended audience,
level, preferred notations. It is read before every translation and every explanation. See also
[First run](first-run.md).

## Automatic and manual behaviours

By default, Madalean chains the steps of a proof by itself, but **never runs code written by a model without your
approval**, and opens nothing to your other devices unless you decide so on the host. Here is each behaviour, its
setting, its default value and where to change it. Settings marked **host** can only be changed from the host
computer (they open the computer to other devices).

A few settings have no switch in the interface: they are changed in the file \`~/.config/madalean/settings.json\`,
with Madalean stopped (\`systemctl --user stop madalean\`, edit, then \`systemctl --user start madalean\`).

**Proof chain** — “Settings › Models › Advanced settings”

| Setting | Default | Label in the application, and effect |
|---|---|---|
| \`pause_after_translation\` | off | “Pause after the translation (to review it)”: when on, Madalean stops after the translation into Lean and waits for you to approve it; otherwise the chain is fully automatic |
| \`statement_check\` | on | “Check every statement before proving it (faithfulness, counterexamples)” |
| \`mathlib_first\` | on | “Look for the theorem in Mathlib first” |
| \`tournament_enabled\` | on | “Model tournament for proofs”: the best models first, then a race between others; with \`tournament_contestants\` (3 models per race), \`tournament_max_rounds\` (3 races), \`tournament_max_minutes\` (at most 40 min per proof), \`tournament_attempts_per_model\` (4 attempts of the best model) |
| \`lean_warm\` | on | “Keep Lean ready in advance during a proof”: attempts are checked in a fraction of a second, at the cost of about 3.4 GB of RAM per Lean workspace in use |
| \`lean_warm_idle_minutes\` | 10 | “Stop Lean ready in advance after (min without an attempt)” |
| \`parallel_stages\` | on | *no switch*: once Lean accepts the statement, guided reading, statement check, Mathlib search and proof search move forward together; off (or in *Local* mode), one step after the other |

**Claude** — “Settings › Models”, “Claude as paid reinforcement” part: \`conductor\`, \`conductor_cap_usd\`,
\`claude_reinforce\`, \`claude_cap_proof_usd\`, \`claude_cap_month_usd\`, \`claude_model\`, described
[above](#claude-conductor-and-paid-reinforcement).

**Code and computation** — “Settings › Notebook and access”

| Setting | Default | Label in the application, and effect |
|---|---|---|
| \`experiments_auto\` | off (host) | “Run experiments without approval”: by default, code written by a model (Sage, Python) **waits for your approval** before running; turning it on is not advised |
| \`experiments_remote\` | off (host) | “Allow experiments from linked devices” (the code still runs on the host, in the sandbox) |
| \`agent_exec\` | off (host) | “Let the agent run code”: the agent can then start computations in the project folder |
| \`remote_jupyter\` | off (host) | “Open the notebook to linked devices” |
| \`lan_listener\` | off (host) | “Access from the local network (without Tailscale)”: for a home network without Tailscale; devices must still be linked |

**Computer resources** — no switch (\`settings.json\` file)

| Setting | Default | Effect |
|---|---|---|
| \`local_idle_unload_minutes\` | 10 | the local model stops after this time without work, to give the graphics memory back (0 = never) |
| \`gpu_share_ollama\` | yes (host) | share the graphics card with Ollama: have its models unloaded when memory is short, never while it is answering |
| \`gpu_share_busy_wait_s\` | 30 (host) | longest wait when Ollama is answering another application |
| \`gpu_share_busy_fallback\` | \`cpu\` (host) | then: \`cpu\` (free memory, partly on the processor) or \`online\` (next model, online) |
| \`calcul_idle_minutes\` | 30 | the kernel of a “Calcul” notebook stops after this time without activity (0 = never) |
| \`browser_session_idle_minutes\` | 120 (host) | a session opened in a browser from another device closes after this idle time |

**Network and updates**

| Setting | Default | Where, and effect |
|---|---|---|
| \`check_updates\` | on | “Settings › Updates” › “Check for updates every week” (never in *Local* mode) |
| \`updates_auto\` | on (host) | “Settings › Updates” › “Install automatically when nothing is running”: unticked, you are told before each installation. See [Updates](updates.md) |
| \`web_search\` | on | “Settings › Providers” › “Internet search for literature research” (never in *Local* mode; only the query is sent) |
| \`offline\` | — | old setting of Lean AI Station 1.x, replaced by *Local* mode; it is only used when importing version 1 settings |

## Choices made at installation

The installer (graphical or terminal) writes your choices to \`~/.config/madalean/setup.json\`; Madalean applies them
at first start. Two of them become settings:

| Setting | Values | Default | Effect |
|---|---|---|---|
| \`sage_source\` | \`auto\`, \`own\`, \`system\` | \`auto\` | which SageMath to use: \`auto\` = Madalean's copy when installed, else the system's; \`system\` = the system's only; \`own\` = Madalean's copy only (see [SageMath](components.md#sagemath)) |
| \`tex_engine\` | \`auto\`, \`tectonic\`, \`system\` | \`auto\` | which LaTeX to use: tectonic first, the system's TeX Live as a fallback (see [LaTeX](components.md#latex)) |

The local models chosen at installation are simply the files present in \`~/models\`.

In the app, \`sage_source\` and \`tex_engine\` are shown and changed in the “Tools” step of the “First steps” assistant
(logo menu, or “Settings”, link “First steps”). Madalean checks the choice before saving it: “The system's” needs a
compatible SageMath (10.0 or later, with its “sagemath” Jupyter kernel) or a TeX Live (XeLaTeX or LuaLaTeX), “tectonic
only” needs Madalean's tectonic; otherwise the choice is refused with the reason. The step also says which copy is in
use right now.

## Checklist

| To do | Where | Essential? |
|---|---|---|
| Go through the “First steps” assistant (or resume it) | opens at the first start; logo menu › “First steps” | recommended |
| Open Madalean and check that everything is fine | “Settings › System”, “Health” part | yes |
| Install bubblewrap if the sandbox is reported inactive | terminal, see [bubblewrap](components.md#bubblewrap-the-sandbox) | strongly recommended |
| Add one or two free keys (Groq, Gemini) | “Settings › Providers” | recommended |
| Add an Internet search key (Tavily) | “Settings › Providers” | for literature research |
| Hugging Face token, Anthropic key, and their caps | “Settings › Providers”, then “Settings › Models” | optional, paid |
| Choose where the models work | “Settings › Models” | the default *Automatic* almost always suits |
| Choose Learn or Research, fill in the profile | button at the top right; “Settings › Profile” | recommended |
| Decide on the automatic behaviours | “Settings › Models › Advanced settings”, “Settings › Notebook and access” | the defaults are cautious |
| Link a phone or another PC | “Settings › Devices”, see [Link a device](pairing.md) | if you need it |
| Make a first try | the home screen, see [First run](first-run.md) | — |
`,text:`First configuration Once Madalean is installed (see Installing Madalean), it works right away, without any key: free online providers that need no account and, if you installed them, the local models are enough to get started. This page reviews what is worth setting next, in the order you will meet it: 1. the keys of online providers, which give access to stronger models; 2. where the models work: Local, Automatic or Online; 3. Learn or Research, and your profile; 4. the automatic behaviours, which you can make manual. Everything is in “Settings” (the gear icon at the top right). A checklist sums it all up at the end of the page. The “First steps” assistant When you open Madalean for the first time on the host computer, the “First steps” assistant opens full screen and guides you through these same choices, in the order of this page. Your linked devices (phone, tablet, other PC) never see it: it only opens where Madalean is installed. First steps: the tools Step What you do there More Welcome see what lies ahead, the machine's resources, choose the language — Tools see the installed and missing components, install or repair them (with progress); choose which SageMath (sagesource) and which LaTeX (texengine) to use, with the recommended choice and its reason; the command to type yourself for bubblewrap Components Local model none, the prover model or all three, depending on your graphics card (recommended choice and download size); “Download” fetches the missing files, verified Local models Free keys one card per provider (Groq, Gemini, Tavily first): what it is good for, what is free, where to create the key; paste it, “Save”, “Test” Keys Hugging Face the token for Goedel-Prover 32B online, and the hfgoedel switch below Claude the Anthropic key, the caps per request, per proof and per month, the paid reinforcement below Modes Local, Automatic or Online (recommended choice for the machine); Learn or Research below Automatic or manual experiments without approval, conductor, stages in parallel, warm Lean, pause after the translation, updates below Devices link a phone or another PC (the same screen as “Settings › Devices”) Link a device Summary the checklist, checked again, and your choices; “Finish” — - Every step has a “Help” link to the manual page that explains it. - Every step can be skipped (“Skip this step”); every choice is saved at once, except keys, which are saved (and tested) only by their “Save” button. - “Later” closes the assistant. It no longer opens by itself, but a “First steps” card stays on the home screen until you finish it (“Resume”, or “Don't show again”). The assistant resumes where you stopped: from that card, from the menu (the logo), “First steps” entry, or from “Settings”, link “First steps: the setup assistant”. - After an update from version 2.0.0 the assistant does not open by itself (your work is already there): the home card offers it. - The four-step tour of the home screen (First run) is separate: it shows how to prove a first statement. Keys of online providers An API key (or “token”) is a password specific to an online service: it lets Madalean use that service's models on your behalf. It takes two minutes to create on the provider's site. Adding a key “Settings › Providers” sorts online services by use (Lean proofs, writing, code, Internet search…), with, for each, what is free and where your data goes. On a provider's card: 1. “Create a key” opens the provider's key page; create an account if needed, then create a key and copy it (it is often shown only once); 2. paste it on the card: Madalean tests it at once and says how many models it gives, or why it is refused; 3. “Remove the key” deletes it in one click. Settings › Providers Where keys are kept - In the system keyring (your desktop's password vault: GNOME Keyring, KWallet…), when the secret-tool tool is available; - otherwise in the file ~/.config/madalean/keys.json, readable by you only (permissions 0600). A key is never shown again, never written to the log, and never passed to your linked devices: the server only says whether a key is set. It is sent only to its provider; Madalean refuses to attach it to any other address. Where to start For a good free start, without a bank card for the first two: Groq (fast models), Google Gemini (the strongest free models) and Tavily (Internet search). Then add, as needed, a Hugging Face token for the best open Lean prover, and an Anthropic key if you accept paying for Claude per use, within caps you set. The providers, one by one Free tiers change often; each card of “Settings › Providers” shows the date they were checked. The information below is that of this version of Madalean. Lean proofs Provider What it is for Free? Where to create the key Hugging Face (Goedel-Prover-V2-32B) the best open Lean prover, served online; it opens every proof no: paid per token with Hugging Face credits (free account: no included credit; PRO account: $2 per month) <https://huggingface.co/settings/tokens> Mistral (Leanstral) Mistral's Lean proof agent, put first in the tournament if your Mistral key offers it announced free, but retired by Mistral on 2026-09-30; Madalean detects it by itself if it comes back same key as Mistral, below Writing, explanations, reasoning Provider What it is for Free? Where to create the key Google Gemini the strongest free models for writing (LaTeX, explanations) and reasoning yes, with per-project limits; the free tier may be used by Google to improve its products: nothing confidential <https://aistudio.google.com/apikey> Mistral AI very good in French; Codestral for code billing must be activated to create a key; an existing key keeps working <https://console.mistral.ai/api-keys> Anthropic (Claude) the strongest at Lean and writing; conductor and paid reinforcement (see below) no: paid per use <https://console.anthropic.com/settings/keys> Code (Sage, Python) and small tasks Provider What it is for Free? Where to create the key Groq very fast: Sage/Python code, small tasks, routing yes, without a card (30 requests per minute, 1,000 per day per model) <https://console.groq.com/keys> Cerebras very fast: code, computation, reasoning trial: a one-time $5 credit, after adding a card <https://cloud.cerebras.ai> SambaNova Cloud free backup model (code, maths) yes, without a card (20 requests per day per model) <https://cloud.sambanova.ai/apis> General backup models, and paid models on request Provider What it is for Free? Where to create the key OpenRouter “:free” models yes (50 requests per day; some free models require allowing training on your data) <https://openrouter.ai/settings/keys> NVIDIA NIM trial catalogue, as a backup limited free trial, for testing only; no confidential work <https://build.nvidia.com> OpenAI GPT, only when you choose it no: paid <https://platform.openai.com/api-keys> DeepSeek good at maths and code, cheap, only when you choose it (servers in China) no: paid <https://platform.deepseek.com/apikeys> Internet search (for literature research, never in Local mode; only the query is sent) Provider Free? Where to create the key Tavily 1,000 searches per month, no card <https://app.tavily.com> Exa $10 of free credits every month <https://dashboard.exa.ai/api-keys> Brave Search $5 of free credits per month; a card is required <https://api-dashboard.search.brave.com> Without a key, always available: the free models LLM7, OVHcloud, Kilo and Pollinations (what you send them may be kept: for confidential work, use Local mode), Wikipedia for Internet search, arXiv, zbMATH, Crossref, OpenAlex and Semantic Scholar for bibliography, LeanSearch and Loogle to search Mathlib. GitHub has a card too: its token is used only to “Publish” (push a project's site to your GitHub repository), never for models. See Publishing a project. A paid model is never used behind your back: only if you chose it for a task, or as reinforcement within your caps (Claude, Goedel 32B online). What each model receives, and the prices: Models and keys. Hugging Face token: Goedel-Prover 32B online With a Hugging Face token, Goedel-Prover-V2-32B opens every proof: the same method as the local prover, with a model four times larger, without using your graphics card. 1. Create an account on Hugging Face and add credits (calls are paid per token). 2. On the Hugging Face card, “Create a key” opens the token page, ready to create a token with the “Make calls to Inference Providers” permission; the token starts with hf. 3. Paste it: Madalean checks it without charging anything and says whether Goedel 32B is available. Setting hfgoedel (on by default): “Settings › Models › Advanced settings”, box “Goedel-Prover 32B online (Hugging Face) opens every proof when the token is saved”. Its spending counts towards the monthly cap described below. One attempt costs at most ≈ $0.11 (Madalean's conservative estimate). Claude: conductor and paid reinforcement With an Anthropic key, Claude can play two roles, set in “Settings › Models”, “Claude as paid reinforcement” part: Role Setting Default What it does Conductor conductor: “Let Claude direct each request” on Claude reads each request, picks the best model for each step, fixes what Lean rejects and checks at the end that statement, proof and explanation agree. Without an Anthropic key, the best free model takes this role. Lean remains the only judge of proofs conductorcapusd: “Cap per request” $1 once reached, Madalean asks whether to continue with Claude, for $0.50 more Paid reinforcement claudereinforce: “Call on Claude when the free models fail” on Claude enters a proof's tournament last, only if the free models have all failed claudecapproofusd: “Cap per proof” $1 beyond it, the call is not made and the proof says so claudecapmonthusd: “Cap per month” $20 for all paid calls of the calendar month (Claude and Goedel 32B on Hugging Face) claudemodel: “Claude model” Automatic the best Claude model for proving, or the one you impose Before each call, Madalean estimates its cost at the public price and does not make it if it would exceed a cap; after the call, the real cost is recorded. The month's total and the latest calls are shown under the caps. Anthropic's invoice is authoritative. Without an Anthropic key, none of these settings costs anything. Where the models work “Settings › Models”, “Where the models work” part (setting mode). The indicator at the top of the screen shows at all times the current mode and who receives your work. Settings › Models Mode What happens For whom Local nothing leaves the computer: only the models installed on the host work; any connection to the Internet is refused before it is opened confidential work, computer without Internet; assumes local models and a good graphics card Automatic (default) online models; local models only without Internet, or if no online model can work the best choice for almost everyone: fast, and the graphics card stays free Online online models only; without a network, the work fails with a clear message computer without a local model A given dossier can have another mode than the general one (“Options for this dossier”, on the home screen). Just below, “Proof search method” chooses between Automatic (an agent with the best online model if the mode allows it, otherwise Goedel), Agent and Goedel (local). Details of what is sent and to whom: Models and keys. Learn or Research The button at the top right switches between two ways of working; the choice is kept on each device and can be changed at any time: - Learn (default): guided — hints before the proof, glossary on hover, line-by-line explanations, a tutor who has you explain in your own words. For whoever is discovering Lean, student or teacher. - Research: dense, keyboard-oriented, nothing pedagogical in the way. For whoever uses Lean in a research project. Your profile (“Settings › Profile”, setting profile) tells Madalean whom it is addressing: intended audience, level, preferred notations. It is read before every translation and every explanation. See also First run. Automatic and manual behaviours By default, Madalean chains the steps of a proof by itself, but never runs code written by a model without your approval, and opens nothing to your other devices unless you decide so on the host. Here is each behaviour, its setting, its default value and where to change it. Settings marked host can only be changed from the host computer (they open the computer to other devices). A few settings have no switch in the interface: they are changed in the file ~/.config/madalean/settings.json, with Madalean stopped (systemctl --user stop madalean, edit, then systemctl --user start madalean). Proof chain — “Settings › Models › Advanced settings” Setting Default Label in the application, and effect pauseaftertranslation off “Pause after the translation (to review it)”: when on, Madalean stops after the translation into Lean and waits for you to approve it; otherwise the chain is fully automatic statementcheck on “Check every statement before proving it (faithfulness, counterexamples)” mathlibfirst on “Look for the theorem in Mathlib first” tournamentenabled on “Model tournament for proofs”: the best models first, then a race between others; with tournamentcontestants (3 models per race), tournamentmaxrounds (3 races), tournamentmaxminutes (at most 40 min per proof), tournamentattemptspermodel (4 attempts of the best model) leanwarm on “Keep Lean ready in advance during a proof”: attempts are checked in a fraction of a second, at the cost of about 3.4 GB of RAM per Lean workspace in use leanwarmidleminutes 10 “Stop Lean ready in advance after (min without an attempt)” parallelstages on no switch: once Lean accepts the statement, guided reading, statement check, Mathlib search and proof search move forward together; off (or in Local mode), one step after the other Claude — “Settings › Models”, “Claude as paid reinforcement” part: conductor, conductorcapusd, claudereinforce, claudecapproofusd, claudecapmonthusd, claudemodel, described above. Code and computation — “Settings › Notebook and access” Setting Default Label in the application, and effect experimentsauto off (host) “Run experiments without approval”: by default, code written by a model (Sage, Python) waits for your approval before running; turning it on is not advised experimentsremote off (host) “Allow experiments from linked devices” (the code still runs on the host, in the sandbox) agentexec off (host) “Let the agent run code”: the agent can then start computations in the project folder remotejupyter off (host) “Open the notebook to linked devices” lanlistener off (host) “Access from the local network (without Tailscale)”: for a home network without Tailscale; devices must still be linked Computer resources — no switch (settings.json file) Setting Default Effect localidleunloadminutes 10 the local model stops after this time without work, to give the graphics memory back (0 = never) gpushareollama yes (host) share the graphics card with Ollama: have its models unloaded when memory is short, never while it is answering gpusharebusywaits 30 (host) longest wait when Ollama is answering another application gpusharebusyfallback cpu (host) then: cpu (free memory, partly on the processor) or online (next model, online) calculidleminutes 30 the kernel of a “Calcul” notebook stops after this time without activity (0 = never) browsersessionidleminutes 120 (host) a session opened in a browser from another device closes after this idle time Network and updates Setting Default Where, and effect checkupdates on “Settings › Updates” › “Check for updates every week” (never in Local mode) updatesauto on (host) “Settings › Updates” › “Install automatically when nothing is running”: unticked, you are told before each installation. See Updates websearch on “Settings › Providers” › “Internet search for literature research” (never in Local mode; only the query is sent) offline — old setting of Lean AI Station 1.x, replaced by Local mode; it is only used when importing version 1 settings Choices made at installation The installer (graphical or terminal) writes your choices to ~/.config/madalean/setup.json; Madalean applies them at first start. Two of them become settings: Setting Values Default Effect sagesource auto, own, system auto which SageMath to use: auto = Madalean's copy when installed, else the system's; system = the system's only; own = Madalean's copy only (see SageMath) texengine auto, tectonic, system auto which LaTeX to use: tectonic first, the system's TeX Live as a fallback (see LaTeX) The local models chosen at installation are simply the files present in ~/models. In the app, sagesource and texengine are shown and changed in the “Tools” step of the “First steps” assistant (logo menu, or “Settings”, link “First steps”). Madalean checks the choice before saving it: “The system's” needs a compatible SageMath (10.0 or later, with its “sagemath” Jupyter kernel) or a TeX Live (XeLaTeX or LuaLaTeX), “tectonic only” needs Madalean's tectonic; otherwise the choice is refused with the reason. The step also says which copy is in use right now. Checklist To do Where Essential? Go through the “First steps” assistant (or resume it) opens at the first start; logo menu › “First steps” recommended Open Madalean and check that everything is fine “Settings › System”, “Health” part yes Install bubblewrap if the sandbox is reported inactive terminal, see bubblewrap strongly recommended Add one or two free keys (Groq, Gemini) “Settings › Providers” recommended Add an Internet search key (Tavily) “Settings › Providers” for literature research Hugging Face token, Anthropic key, and their caps “Settings › Providers”, then “Settings › Models” optional, paid Choose where the models work “Settings › Models” the default Automatic almost always suits Choose Learn or Research, fill in the profile button at the top right; “Settings › Profile” recommended Decide on the automatic behaviours “Settings › Models › Advanced settings”, “Settings › Notebook and access” the defaults are cautious Link a phone or another PC “Settings › Devices”, see Link a device if you need it Make a first try the home screen, see First run —`},{id:`first-run`,lang:`en`,title:`First run`,order:20,section:`start`,audience:`all`,summary:`Guided tour, choice of mode, first statement, demo mode.`,source:`en/first-run.md`,site_path:`en/first-run.html`,headings:[{level:1,text:`First run`,id:`first-run`},{level:2,text:`Three choices to make`,id:`three-choices-to-make`},{level:2,text:`A first statement`,id:`a-first-statement`},{level:2,text:`Trying without models or Lean: demo mode`,id:`trying-without-models-or-lean-demo-mode`}],images:[],verify:[],body:`# First run

On the host computer, the very first opening starts with the “First steps” assistant (tools, local model, keys,
modes…; see [First configuration](first-config.md#the-first-steps-assistant)). Then, on the first opening of the
home screen (in *Learn* mode, the default), a short four-step tour presents the ideas of the interface: write
a statement, check the translation, Lean checks every proof, you stay in control. “Skip the tour” closes it.

The state of the installation (Lean workspaces, models, TeX, fonts, sandbox, disk) is shown in “Settings › System”,
under “Health”: each problem is reported there, with a “Repair” button when a repair exists (to be started from the
host computer).

## Three choices to make

These choices, the providers' keys and each automatic behaviour are detailed in
[First configuration](first-config.md).


1. **Where the models work** (“Settings › Models”):
   - *Local*: nothing leaves the host computer; only the models installed here work.
   - *Automatic* (default): the best available model, online first, local models when the network is missing.
   - *Online*: online models only.

   What each mode sends, and to whom: [Models and keys](models-keys.md).
2. **Learn or Research** (button at the top right): *Learn* offers hints before the proof, a glossary on hover and
   line-by-line explanations; *Research* is dense, keyboard-first, with nothing pedagogical in the way. You can
   switch at any time.
3. **Your profile** (“Settings › Profile”): intended audience, level, preferred notations. It is read before every
   translation and every explanation.

## A first statement

On the home screen, write for example:

> Show that the sum of two even integers is even.

then “Translate and prove”. The stages follow one another by themselves: understanding, translation into Lean, proof search,
explanation. What comes next is described in [From statement to proof](workflow.md).

## Trying without models or Lean: demo mode

\`\`\`bash
~/madalean/bin/madalean serve --demo --port 11600 --remote-port 11601
\`\`\`

then open \`http://127.0.0.1:11600\`. The models and Lean are **simulated**: a banner says so, and nothing there is
really checked. Demo mode is for discovering the interface; its data is kept apart from yours
(\`~/.config/madalean-demo\`).
`,text:`First run On the host computer, the very first opening starts with the “First steps” assistant (tools, local model, keys, modes…; see First configuration). Then, on the first opening of the home screen (in Learn mode, the default), a short four-step tour presents the ideas of the interface: write a statement, check the translation, Lean checks every proof, you stay in control. “Skip the tour” closes it. The state of the installation (Lean workspaces, models, TeX, fonts, sandbox, disk) is shown in “Settings › System”, under “Health”: each problem is reported there, with a “Repair” button when a repair exists (to be started from the host computer). Three choices to make These choices, the providers' keys and each automatic behaviour are detailed in First configuration. 1. Where the models work (“Settings › Models”): - Local: nothing leaves the host computer; only the models installed here work. - Automatic (default): the best available model, online first, local models when the network is missing. - Online: online models only. What each mode sends, and to whom: Models and keys. 2. Learn or Research (button at the top right): Learn offers hints before the proof, a glossary on hover and line-by-line explanations; Research is dense, keyboard-first, with nothing pedagogical in the way. You can switch at any time. 3. Your profile (“Settings › Profile”): intended audience, level, preferred notations. It is read before every translation and every explanation. A first statement On the home screen, write for example: > Show that the sum of two even integers is even. then “Translate and prove”. The stages follow one another by themselves: understanding, translation into Lean, proof search, explanation. What comes next is described in From statement to proof. Trying without models or Lean: demo mode then open http://127.0.0.1:11600. The models and Lean are simulated: a banner says so, and nothing there is really checked. Demo mode is for discovering the interface; its data is kept apart from yours (~/.config/madalean-demo).`},{id:`pairing`,lang:`en`,title:`Link a phone, a tablet or another PC`,order:30,section:`start`,audience:`all`,summary:`Step by step, linking a device to the host computer with a 6-digit code, and unlinking it.`,source:`en/pairing.md`,site_path:`en/pairing.html`,headings:[{level:1,text:`Link a phone, a tablet or another PC`,id:`link-a-phone-a-tablet-or-another-pc`},{level:2,text:`Step 1 — Put the host on your Tailscale network (once)`,id:`step-1-put-the-host-on-your-tailscale-network-once`},{level:2,text:`Step 2 — Show a code on the host`,id:`step-2-show-a-code-on-the-host`},{level:2,text:`Step 3 — On the device`,id:`step-3-on-the-device`},{level:3,text:`Android phone or tablet`,id:`android-phone-or-tablet`},{level:3,text:`iPhone, iPad, or any device with a browser`,id:`iphone-ipad-or-any-device-with-a-browser`},{level:3,text:`Another Linux computer`,id:`another-linux-computer`},{level:2,text:`What happens when linking`,id:`what-happens-when-linking`},{level:2,text:`Unlinking a device`,id:`unlinking-a-device`},{level:2,text:`If it does not work`,id:`if-it-does-not-work`}],images:[{src:`img/devices-add.png`,exists:!0},{src:`img/pair-phone.png`,exists:!0}],verify:[],body:`# Link a phone, a tablet or another PC

A linked device shows the same interface as the host computer and stays synchronised with it: what you start on the
phone appears on the PC, and vice versa. All computation stays on the host.

Three things are needed:

1. the host computer switched on, Madalean running;
2. the host and the device on **your Tailscale network** (see [Tailscale](tailscale.md));
3. a **6-digit code** shown by the host.

On the host computer itself, no code is needed.

**App or browser?**

- The **Madalean apps** (Android, Linux desktop) are linked **once**: afterwards they reconnect by themselves, even
  after the host restarts.
- From a **browser** (iPhone, iPad, another PC without the app), a **code is needed at every connection**: access
  lasts for the session, closes after **2 h without activity** (adjustable on the host), after **12 h** at most, and
  when the host restarts.

## Step 1 — Put the host on your Tailscale network (once)

Madalean brings **its own Tailscale node**: on your tailnet, the host appears as a separate machine named
\`madalean\`, at the address \`https://madalean.tailXXXX.ts.net\` (normal HTTPS port, no port number to type). Nothing
needs installing on the host for this: neither the system's Tailscale nor \`tailscale serve\`.

The first time, this node must be **approved** in your Tailscale account (Madalean never approves anything itself):
open the Tailscale login link it provides, sign in and accept the \`madalean\` machine. For now, this link is read on
the host, in a terminal:

\`\`\`bash
curl -s http://127.0.0.1:11500/api/net
\`\`\`

(\`auth_url\` line). Once the node is approved, the same command shows \`"state": "running"\` and the host's full name
(\`dns_name\`). The tailnet must have HTTPS certificates enabled: see [Tailscale › Enable HTTPS](tailscale.md#enable-https).

If you prefer to go through the Tailscale already installed on the host, see
[Tailscale › Alternative](tailscale.md#alternative-the-systems-tailscale).

## Step 2 — Show a code on the host

On the host computer: “Settings › Devices”, “Add a device” part, “Show a code” button. A 6-digit code appears, valid
for **5 minutes**, usable **once**, with a QR code.

![Settings › Devices: code and QR code](img/devices-add.png)

The field “Address of this computer as seen from other devices” fills in by itself when Madalean's Tailscale node is
running (for example \`madalean.tail1234.ts.net\`). It is used to build the QR code. The QR code also carries fallback
addresses, which the Android app tries if the name does not answer: the host's Tailscale IP address and, if access
from the local network is turned on, its local network address (port 11502 by default, see
[Tailscale › Without Tailscale](tailscale.md#without-tailscale)).

## Step 3 — On the device

### Android phone or tablet

1. Install the **Tailscale** app (Play Store) and sign in with **the same account** as on the host.
2. Install the **Madalean** app from the [install page](site:install) (APK file; Android asks you to allow
   installation from your browser, once).
3. Open Madalean, tap “Scan the QR code” and point at the QR code shown on the host: the address and the code fill
   in by themselves. The app asks for camera access, only to read this QR code. Otherwise, “Or enter the address and
   code” lets you type them by hand.
4. Give the device a name (“Marie's Pixel”) and tap “Pair and open”.

![Linking screen on a phone](img/pair-phone.png)

### iPhone, iPad, or any device with a browser

There is no iOS app. Install Tailscale (App Store), then open the host's address in the browser, for example
\`https://madalean.tail1234.ts.net\`. The “Link this device” page asks for the code and a device name, then “Link”.
Scanning the host's QR code with the camera opens this page directly, with the code filled in.
**A code is needed at every connection from a browser**: at the next visit (or after 2 h without activity), show a
new code on the host.

### Another Linux computer

Install Tailscale, then either a browser (as above) or the **Madalean** desktop app (AppImage,
[install page](site:install)), which keeps the token in the system keyring and reconnects by itself.

## What happens when linking

- **App**: the device sends the code; the host gives it a secret **token** (256 bits), kept in the system keyring,
  that identifies it from then on. The host keeps only a fingerprint of this token, never the token itself.
- **Browser**: the host opens a **temporary session** (a session cookie, erased when the browser closes, that no page
  can read); it is never turned into a permanent token and the host keeps it in memory only.

Five wrong codes in a row lock linking for 10 minutes. Details: [Security](security.md).

## Unlinking a device

- From the host: “Settings › Devices”, the “Unlink” button next to the device. The page shows two lists:
  “Applications (automatic connection)” and “Browsers (temporary session)”. Access is cut **immediately**:
  a page that is already open loses its live connection at once, stops any answer still being written for it, and
  goes back to the linking screen. The same happens when a browser session ends (inactivity, 12 h limit) and when
  the device unlinks itself.
- From the device itself: “Settings › Devices › Unlink this device”. In the Android app, “Forget” also removes a
  saved server from the connection screen.

Unlinking a lost phone is the first thing to do; your Tailscale account also lets you remove the device from the
private network.

## If it does not work

| Message | What to do |
|---|---|
| “Wrong code” | Type again the 6 digits shown on the host. |
| “This code has expired” | “New code” on the host (valid for 5 minutes). |
| “Too many tries: linking is locked for N min” | Wait, then ask for a new code. |
| The address does not answer | Is Tailscale connected on both devices? See [Troubleshooting](troubleshooting.md#the-device-cannot-reach-the-host). |
`,text:`Link a phone, a tablet or another PC A linked device shows the same interface as the host computer and stays synchronised with it: what you start on the phone appears on the PC, and vice versa. All computation stays on the host. Three things are needed: 1. the host computer switched on, Madalean running; 2. the host and the device on your Tailscale network (see Tailscale); 3. a 6-digit code shown by the host. On the host computer itself, no code is needed. App or browser? - The Madalean apps (Android, Linux desktop) are linked once: afterwards they reconnect by themselves, even after the host restarts. - From a browser (iPhone, iPad, another PC without the app), a code is needed at every connection: access lasts for the session, closes after 2 h without activity (adjustable on the host), after 12 h at most, and when the host restarts. Step 1 — Put the host on your Tailscale network (once) Madalean brings its own Tailscale node: on your tailnet, the host appears as a separate machine named madalean, at the address https://madalean.tailXXXX.ts.net (normal HTTPS port, no port number to type). Nothing needs installing on the host for this: neither the system's Tailscale nor tailscale serve. The first time, this node must be approved in your Tailscale account (Madalean never approves anything itself): open the Tailscale login link it provides, sign in and accept the madalean machine. For now, this link is read on the host, in a terminal: (authurl line). Once the node is approved, the same command shows "state": "running" and the host's full name (dnsname). The tailnet must have HTTPS certificates enabled: see Tailscale › Enable HTTPS. If you prefer to go through the Tailscale already installed on the host, see Tailscale › Alternative. Step 2 — Show a code on the host On the host computer: “Settings › Devices”, “Add a device” part, “Show a code” button. A 6-digit code appears, valid for 5 minutes, usable once, with a QR code. Settings › Devices: code and QR code The field “Address of this computer as seen from other devices” fills in by itself when Madalean's Tailscale node is running (for example madalean.tail1234.ts.net). It is used to build the QR code. The QR code also carries fallback addresses, which the Android app tries if the name does not answer: the host's Tailscale IP address and, if access from the local network is turned on, its local network address (port 11502 by default, see Tailscale › Without Tailscale). Step 3 — On the device Android phone or tablet 1. Install the Tailscale app (Play Store) and sign in with the same account as on the host. 2. Install the Madalean app from the install page (APK file; Android asks you to allow installation from your browser, once). 3. Open Madalean, tap “Scan the QR code” and point at the QR code shown on the host: the address and the code fill in by themselves. The app asks for camera access, only to read this QR code. Otherwise, “Or enter the address and code” lets you type them by hand. 4. Give the device a name (“Marie's Pixel”) and tap “Pair and open”. Linking screen on a phone iPhone, iPad, or any device with a browser There is no iOS app. Install Tailscale (App Store), then open the host's address in the browser, for example https://madalean.tail1234.ts.net. The “Link this device” page asks for the code and a device name, then “Link”. Scanning the host's QR code with the camera opens this page directly, with the code filled in. A code is needed at every connection from a browser: at the next visit (or after 2 h without activity), show a new code on the host. Another Linux computer Install Tailscale, then either a browser (as above) or the Madalean desktop app (AppImage, install page), which keeps the token in the system keyring and reconnects by itself. What happens when linking - App: the device sends the code; the host gives it a secret token (256 bits), kept in the system keyring, that identifies it from then on. The host keeps only a fingerprint of this token, never the token itself. - Browser: the host opens a temporary session (a session cookie, erased when the browser closes, that no page can read); it is never turned into a permanent token and the host keeps it in memory only. Five wrong codes in a row lock linking for 10 minutes. Details: Security. Unlinking a device - From the host: “Settings › Devices”, the “Unlink” button next to the device. The page shows two lists: “Applications (automatic connection)” and “Browsers (temporary session)”. Access is cut immediately: a page that is already open loses its live connection at once, stops any answer still being written for it, and goes back to the linking screen. The same happens when a browser session ends (inactivity, 12 h limit) and when the device unlinks itself. - From the device itself: “Settings › Devices › Unlink this device”. In the Android app, “Forget” also removes a saved server from the connection screen. Unlinking a lost phone is the first thing to do; your Tailscale account also lets you remove the device from the private network. If it does not work Message What to do “Wrong code” Type again the 6 digits shown on the host. “This code has expired” “New code” on the host (valid for 5 minutes). “Too many tries: linking is locked for N min” Wait, then ask for a new code. The address does not answer Is Tailscale connected on both devices? See Troubleshooting.`},{id:`tailscale`,lang:`en`,title:`Tailscale, the private network of your devices`,order:40,section:`start`,audience:`all`,summary:`What Tailscale is, why Madalean uses it, how to install it, and what it does not do.`,source:`en/tailscale.md`,site_path:`en/tailscale.html`,headings:[{level:1,text:`Tailscale, the private network of your devices`,id:`tailscale-the-private-network-of-your-devices`},{level:2,text:`What it is`,id:`what-it-is`},{level:2,text:`What Madalean does, and does not do, with Tailscale`,id:`what-madalean-does-and-does-not-do-with-tailscale`},{level:2,text:`Installing Tailscale`,id:`installing-tailscale`},{level:2,text:`Enable HTTPS`,id:`enable-https`},{level:2,text:`Alternative: the system's Tailscale`,id:`alternative-the-systems-tailscale`},{level:2,text:`Without Tailscale`,id:`without-tailscale`}],images:[],verify:[],body:`# Tailscale, the private network of your devices

## What it is

[Tailscale](https://tailscale.com/) connects **your** devices to each other through encrypted links (WireGuard
protocol), wherever they are: same Wi-Fi, 4G, another city. Together they form a private network, the *tailnet*.
Each device gets a stable name there, for example \`nitro.tail1234.ts.net\`. Only the devices signed in to **your**
Tailscale account belong to this network.

Madalean uses it for one thing only: letting your devices reach the host computer. It uses no Madalean server on the
Internet (there is none), and the Madalean website plays no part in synchronisation.

## What Madalean does, and does not do, with Tailscale

- Madalean installs and runs **its own Tailscale node**. On your tailnet, the host appears as a separate machine,
  \`madalean\`, reachable over HTTPS at \`https://madalean.<tailnet>.ts.net\` (normal HTTPS port, no port number). This
  node stops with Madalean and sends no logs to Tailscale.
- The host needs neither the system's Tailscale nor \`tailscale serve\`. If there is one, Madalean does not touch it:
  both coexist.
- Madalean **never enables Funnel**, the Tailscale feature that would open access to the whole Internet.
- Being on the tailnet is **not enough**: each device must also be linked with a code ([Link a device](pairing.md)).

## Installing Tailscale

**On the host computer**, nothing to install: Madalean's node is installed by \`./install.sh\`. The first time, it must
be approved in your Tailscale account (see [Link a device › Step 1](pairing.md)).

**On a phone, a tablet or another computer**: the Tailscale app (App Store, Play Store, or Tailscale's site for a
computer), signed in to **the same account**.

The Tailscale account is created with an identity provider (Google, Microsoft, GitHub, Apple…). The plans and their
limits are described on Tailscale's site; personal use with a few devices usually fits in the free plan, but check
it on that site.

## Enable HTTPS

Devices reach the host over HTTPS, with a certificate that Tailscale issues for the name \`madalean.<tailnet>.ts.net\`.
Once, in Tailscale's admin console, turn on **MagicDNS** and **HTTPS certificates** (the exact menus are described in
Tailscale's help). The first HTTPS connection may take a few seconds, while the certificate is issued.

## Alternative: the system's Tailscale

If you prefer to use the Tailscale already installed on the host (the \`tailscaled\` service, signed in to your
account), the script \`scripts/tailscale_setup.sh\` publishes Madalean through it, on port 10500:
\`https://pc-name.<tailnet>.ts.net:10500\`. It adds **a single** \`tailscale serve\` rule, touches no other rule of the
machine and never enables Funnel. It needs \`sudo tailscale set --operator=$USER\` once to work without \`sudo\`.
\`--status\` shows the state, \`--print\` shows the commands without changing anything, \`--remove\` removes the rule. In
that case, type this address (without \`https://\`) in the “Address of this computer as seen from other devices”
field of “Settings › Devices”.

## Without Tailscale

“Settings › Notebook and access › Access from the local network (without Tailscale)” also makes Madalean listen on
the local network (“Local network port”, 11502 by default; off by default). Devices must still be linked with a code,
but traffic then goes over plain HTTP, **not encrypted**: keep this for a trusted network. This setting can only be
changed from the host and takes effect at the next start of Madalean.
`,text:`Tailscale, the private network of your devices What it is Tailscale connects your devices to each other through encrypted links (WireGuard protocol), wherever they are: same Wi-Fi, 4G, another city. Together they form a private network, the tailnet. Each device gets a stable name there, for example nitro.tail1234.ts.net. Only the devices signed in to your Tailscale account belong to this network. Madalean uses it for one thing only: letting your devices reach the host computer. It uses no Madalean server on the Internet (there is none), and the Madalean website plays no part in synchronisation. What Madalean does, and does not do, with Tailscale - Madalean installs and runs its own Tailscale node. On your tailnet, the host appears as a separate machine, madalean, reachable over HTTPS at https://madalean.<tailnet>.ts.net (normal HTTPS port, no port number). This node stops with Madalean and sends no logs to Tailscale. - The host needs neither the system's Tailscale nor tailscale serve. If there is one, Madalean does not touch it: both coexist. - Madalean never enables Funnel, the Tailscale feature that would open access to the whole Internet. - Being on the tailnet is not enough: each device must also be linked with a code (Link a device). Installing Tailscale On the host computer, nothing to install: Madalean's node is installed by ./install.sh. The first time, it must be approved in your Tailscale account (see Link a device › Step 1). On a phone, a tablet or another computer: the Tailscale app (App Store, Play Store, or Tailscale's site for a computer), signed in to the same account. The Tailscale account is created with an identity provider (Google, Microsoft, GitHub, Apple…). The plans and their limits are described on Tailscale's site; personal use with a few devices usually fits in the free plan, but check it on that site. Enable HTTPS Devices reach the host over HTTPS, with a certificate that Tailscale issues for the name madalean.<tailnet>.ts.net. Once, in Tailscale's admin console, turn on MagicDNS and HTTPS certificates (the exact menus are described in Tailscale's help). The first HTTPS connection may take a few seconds, while the certificate is issued. Alternative: the system's Tailscale If you prefer to use the Tailscale already installed on the host (the tailscaled service, signed in to your account), the script scripts/tailscalesetup.sh publishes Madalean through it, on port 10500: https://pc-name.<tailnet>.ts.net:10500. It adds a single tailscale serve rule, touches no other rule of the machine and never enables Funnel. It needs sudo tailscale set --operator=$USER once to work without sudo. --status shows the state, --print shows the commands without changing anything, --remove removes the rule. In that case, type this address (without https://) in the “Address of this computer as seen from other devices” field of “Settings › Devices”. Without Tailscale “Settings › Notebook and access › Access from the local network (without Tailscale)” also makes Madalean listen on the local network (“Local network port”, 11502 by default; off by default). Devices must still be linked with a code, but traffic then goes over plain HTTP, not encrypted: keep this for a trusted network. This setting can only be changed from the host and takes effect at the next start of Madalean.`},{id:`workflow`,lang:`en`,title:`From statement to proof`,order:100,section:`use`,audience:`all`,summary:`A dossier as one thread — understand, translate, prove, verify — then the explanation and export.`,source:`en/workflow.md`,site_path:`en/workflow.html`,headings:[{level:1,text:`From statement to proof`,id:`from-statement-to-proof`},{level:3,text:`Your two approvals`,id:`your-two-approvals`},{level:3,text:`“Misunderstood”`,id:`misunderstood`},{level:2,text:`1. Writing the statement`,id:`1-writing-the-statement`},{level:2,text:`2. The translation into Lean`,id:`2-the-translation-into-lean`},{level:2,text:`3. The proof`,id:`3-the-proof`},{level:2,text:`4. The explanation`,id:`4-the-explanation`},{level:2,text:`5. Export`,id:`5-export`},{level:2,text:`What next`,id:`what-next`}],images:[{src:`img/lean-statement.png`,exists:!0},{src:`img/hint-ladder.png`,exists:!0}],verify:[],body:`# From statement to proof

Each problem lives in a **dossier**. At the top of the screen four steps say where you are:
**Understand › Translate › Prove › Verify**, each “not started”, “in progress”, “waits for you”, “done” or “failed”.
Just below, a single **“Right now”** line says what Madalean is doing, the attempt number, the model, for how long and
what runs beside; “Stop” is always there. When it is your turn it says so and takes you there; after a failure it leads
to what was tried, the last cause and what you can do.

At the centre, the **thread** tells everything in order: your requests, then each phase, its attempts (folded), the
models' live output, the sub-dossiers where they were created. Filters show only your requests, the results, the checks
or the attempts. The field at the bottom says what your request is **about**.

Beside it, the **pane** holds the references: Statement, Lean, Proof, Sub-lemmas (tree, plan and graph), Literature,
Computations, Versions. “Separate” puts a part in its own window or in a column, “Put back” returns it. The pane can be
resized and hidden; on a phone, the “References” button opens it over the thread.

### Your two approvals

Before any proof, Madalean shows what it **understood** (restated text, objects, hypotheses, claim, what is known with
quotes), then the **Lean statement** with its plain-language reading. For each: “Approve”, “Correct” or “Reject”.
“Lean understands the code” means neither “faithful” nor “proved”. An open problem is announced as such; the known
results around it become sub-dossiers that a single card can approve. The status “according to a model, to be checked”
has no reference.

### “Misunderstood”

On the meaning, the statement, the proof or a message, “Misunderstood” reports a wrong reading: a reason, a few words,
and the step is redone with your remark.

## 1. Writing the statement

Write in your own words, in French or English. LaTeX formulas between dollar signs are read: \`$a^2+b^2 \\ge 2ab$\`.
A preview shows how the statement will be understood. You can also:

- **import a \`.tex\` file**: Madalean extracts its theorem-like environments and you choose which one to prove;
- **paste a Lean statement directly**: the translation stage is then skipped.

A precise statement translates better: name the sets ($n \\in \\mathbb{N}$, $x \\in \\mathbb{R}$), the hypotheses and
the conclusion.

## 2. The translation into Lean

A first model restates your request as a precise mathematical statement (“incomplete basis theorem” becomes “every
linearly independent family of a finite-dimensional vector space extends to a basis”). A second translates it into
Lean; **Lean checks that the statement is well formed** before going further. The note “Lean understands the code”
only means that the statement makes sense to Lean, not that it is true, nor that it says what you meant.

![Lean statement next to the original text](img/lean-statement.png)

**Read this translation.** It is the one place where an error goes unnoticed: Lean will prove exactly the Lean
statement. The usual pitfalls (integer division, truncated subtraction on $\\mathbb{N}$, division by zero) are in
[Reading a Lean statement](reading-lean.md). In *Learn* mode, the “Understand” panel explains the statement line by
line, and each Lean word on hover.

To correct it: “Edit by hand” (you edit the code, Lean checks it again), or “Fix the statement…” (you describe the
correction, the model rewrites).

## 3. The proof

Madalean searches for a proof with the method chosen in “Settings › Models”:

| Method | How it works |
|---|---|
| *goedel* | the local Goedel-Prover model writes a proof; if Lean rejects it, it reads the error and corrects, several times |
| *agent* | a model that can use tools compiles its own attempts with Lean and looks up lemmas in Mathlib |
| *auto* (default) | agent with the best allowed online model, otherwise goedel; goedel also as a fallback when the agent fails |

Whatever the method, the final proof is **checked again by the server** with the strict verdict. The badge “Proof
checked by Lean” gives the Lean version, the Mathlib revision, the duration, the number of attempts, the model that
wrote it and the axioms used.

During the search the models' text arrives live at the end of the thread, with each compiled attempt. “Stop” cuts everything, at any
time (model request and Lean compilation).

In *Learn* mode the proof is not shown at once: a hint ladder (nudge, strategy, key lemma, next step, full proof)
lets you search first. The last level is always the proof checked by Lean, never a model's text.

![Hint ladder in Learn mode](img/hint-ladder.png)

## 4. The explanation

Once the proof is accepted, a model explains it in plain language and writes a **natural-language proof** (the one
that goes into the PDF). These texts are editable drafts: you can correct them by hand, and a manual edit is never
overwritten without your consent.

## 5. Export

“Export” offers:

| Format | Content |
|---|---|
| PDF | title, natural-language statement, Lean statement and its gloss, written proof, Lean proof, verification stamp (Lean version, Mathlib revision, date, axioms, model), tactic-by-tactic explanation in an appendix |
| LaTeX (\`.tex\`) | the same document, to compile with XeLaTeX (for example on Overleaf) |
| Lean (\`.lean\`) | the file that compiles |
| Markdown (\`.md\`) | text and \`$…$\` formulas |
| Everything (\`.zip\`) | all of the above, with \`refs.bib\` if the dossier cites sources |

An unproved dossier is exported marked “Not proved” and without a stamp. If no TeX engine is installed on the host,
Madalean opens an HTML version: use the browser's “Print › Save as PDF”.

## What next

- Refine: [Follow-up requests and versions](follow-ups.md).
- Several related results: [Projects and parallel dossiers](projects.md).
- A result too big for a single proof: [Proof plans and lemmas](proof-plans.md).
- Each proved result goes into the **Library** and serves as a lemma for later proofs in the same Lean workspace.
`,text:`From statement to proof Each problem lives in a dossier. At the top of the screen four steps say where you are: Understand › Translate › Prove › Verify, each “not started”, “in progress”, “waits for you”, “done” or “failed”. Just below, a single “Right now” line says what Madalean is doing, the attempt number, the model, for how long and what runs beside; “Stop” is always there. When it is your turn it says so and takes you there; after a failure it leads to what was tried, the last cause and what you can do. At the centre, the thread tells everything in order: your requests, then each phase, its attempts (folded), the models' live output, the sub-dossiers where they were created. Filters show only your requests, the results, the checks or the attempts. The field at the bottom says what your request is about. Beside it, the pane holds the references: Statement, Lean, Proof, Sub-lemmas (tree, plan and graph), Literature, Computations, Versions. “Separate” puts a part in its own window or in a column, “Put back” returns it. The pane can be resized and hidden; on a phone, the “References” button opens it over the thread. Your two approvals Before any proof, Madalean shows what it understood (restated text, objects, hypotheses, claim, what is known with quotes), then the Lean statement with its plain-language reading. For each: “Approve”, “Correct” or “Reject”. “Lean understands the code” means neither “faithful” nor “proved”. An open problem is announced as such; the known results around it become sub-dossiers that a single card can approve. The status “according to a model, to be checked” has no reference. “Misunderstood” On the meaning, the statement, the proof or a message, “Misunderstood” reports a wrong reading: a reason, a few words, and the step is redone with your remark. 1. Writing the statement Write in your own words, in French or English. LaTeX formulas between dollar signs are read: $a^2+b^2 \\ge 2ab$. A preview shows how the statement will be understood. You can also: - import a .tex file: Madalean extracts its theorem-like environments and you choose which one to prove; - paste a Lean statement directly: the translation stage is then skipped. A precise statement translates better: name the sets ($n \\in \\mathbb{N}$, $x \\in \\mathbb{R}$), the hypotheses and the conclusion. 2. The translation into Lean A first model restates your request as a precise mathematical statement (“incomplete basis theorem” becomes “every linearly independent family of a finite-dimensional vector space extends to a basis”). A second translates it into Lean; Lean checks that the statement is well formed before going further. The note “Lean understands the code” only means that the statement makes sense to Lean, not that it is true, nor that it says what you meant. Lean statement next to the original text Read this translation. It is the one place where an error goes unnoticed: Lean will prove exactly the Lean statement. The usual pitfalls (integer division, truncated subtraction on $\\mathbb{N}$, division by zero) are in Reading a Lean statement. In Learn mode, the “Understand” panel explains the statement line by line, and each Lean word on hover. To correct it: “Edit by hand” (you edit the code, Lean checks it again), or “Fix the statement…” (you describe the correction, the model rewrites). 3. The proof Madalean searches for a proof with the method chosen in “Settings › Models”: Method How it works goedel the local Goedel-Prover model writes a proof; if Lean rejects it, it reads the error and corrects, several times agent a model that can use tools compiles its own attempts with Lean and looks up lemmas in Mathlib auto (default) agent with the best allowed online model, otherwise goedel; goedel also as a fallback when the agent fails Whatever the method, the final proof is checked again by the server with the strict verdict. The badge “Proof checked by Lean” gives the Lean version, the Mathlib revision, the duration, the number of attempts, the model that wrote it and the axioms used. During the search the models' text arrives live at the end of the thread, with each compiled attempt. “Stop” cuts everything, at any time (model request and Lean compilation). In Learn mode the proof is not shown at once: a hint ladder (nudge, strategy, key lemma, next step, full proof) lets you search first. The last level is always the proof checked by Lean, never a model's text. Hint ladder in Learn mode 4. The explanation Once the proof is accepted, a model explains it in plain language and writes a natural-language proof (the one that goes into the PDF). These texts are editable drafts: you can correct them by hand, and a manual edit is never overwritten without your consent. 5. Export “Export” offers: Format Content PDF title, natural-language statement, Lean statement and its gloss, written proof, Lean proof, verification stamp (Lean version, Mathlib revision, date, axioms, model), tactic-by-tactic explanation in an appendix LaTeX (.tex) the same document, to compile with XeLaTeX (for example on Overleaf) Lean (.lean) the file that compiles Markdown (.md) text and $…$ formulas Everything (.zip) all of the above, with refs.bib if the dossier cites sources An unproved dossier is exported marked “Not proved” and without a stamp. If no TeX engine is installed on the host, Madalean opens an HTML version: use the browser's “Print › Save as PDF”. What next - Refine: Follow-up requests and versions. - Several related results: Projects and parallel dossiers. - A result too big for a single proof: Proof plans and lemmas. - Each proved result goes into the Library and serves as a lemma for later proofs in the same Lean workspace.`},{id:`reading-lean`,lang:`en`,title:`Reading a Lean statement`,order:110,section:`use`,audience:`learner`,summary:`Decoding a Lean statement piece by piece, and spotting translations that change the meaning.`,source:`en/reading-lean.md`,site_path:`en/reading-lean.html`,headings:[{level:1,text:`Reading a Lean statement`,id:`reading-a-lean-statement`},{level:2,text:`Anatomy of a statement`,id:`anatomy-of-a-statement`},{level:2,text:`The header`,id:`the-header`},{level:2,text:`Types: which numbers are we talking about?`,id:`types-which-numbers-are-we-talking-about`},{level:2,text:`Pitfalls that change the meaning`,id:`pitfalls-that-change-the-meaning`},{level:2,text:`A reading method`,id:`a-reading-method`}],images:[],verify:[],body:"# Reading a Lean statement\n\nLean proves **exactly** the Lean statement, not the sentence you had in mind. This page teaches you to read a\nstatement well enough to judge a translation, without knowing how to write proofs.\n\n## Anatomy of a statement\n\n```lean\ntheorem somme_pairs (a b : ℕ) (ha : Even a) (hb : Even b) : Even (a + b) := by\n  sorry\n```\n\n| Piece | Reading |\n|---|---|\n| `theorem somme_pairs` | a theorem, and its name (chosen by Madalean, unique) |\n| `(a b : ℕ)` | “let $a$ and $b$ be natural numbers” |\n| `(ha : Even a)` | hypothesis named `ha`: “$a$ is even” |\n| `(hb : Even b)` | hypothesis `hb`: “$b$ is even” |\n| `: Even (a + b)` | after the last `:` outside parentheses comes the **conclusion**: “$a+b$ is even” |\n| `:= by sorry` | “the proof follows, in tactic mode”; `sorry` = proof still to be written |\n\nEverything in parentheses before the last `:` is **assumed**; what comes after is **to be proved**. A statement with\n`sorry` is a statement without a proof: Lean accepts it as a statement, never as a proved theorem.\n\nThe same thing can be written with quantifiers in the conclusion; it is equivalent:\n\n```lean\ntheorem somme_pairs' : ∀ a b : ℕ, Even a → Even b → Even (a + b) := by\n  sorry\n```\n\n`→` reads “implies”; `∀ a b : ℕ,` “for all natural numbers $a$, $b$”.\n\n## The header\n\nStatements of the “Prover” workspace start with a fixed header:\n\n```lean\nimport Mathlib\nimport Aesop\nset_option maxHeartbeats 400000\nopen BigOperators Real Nat Topology Rat\n```\n\n`import Mathlib` loads the mathematical library; `set_option maxHeartbeats` raises the allowed computation time;\n`open …` lets you write `π` or `√` without a prefix. This header does not change the meaning of the statement, but\n`open Nat Real` makes some names ambiguous (`sqrt` exists in both): look at the types.\n\n## Types: which numbers are we talking about?\n\n| Lean | Mathematics | Watch out |\n|---|---|---|\n| `ℕ` | $\\mathbb{N} = \\{0, 1, 2, \\dots\\}$ | contains 0; truncated subtraction and division (see below) |\n| `ℤ` | $\\mathbb{Z}$ | `/` is Euclidean division: the remainder `%` is always $\\ge 0$, `-7 / 2 = -4` |\n| `ℚ`, `ℝ`, `ℂ` | $\\mathbb{Q}$, $\\mathbb{R}$, $\\mathbb{C}$ | division by zero is defined and equals 0 |\n| `Finset ℕ` | finite set of integers | `Finset.range n` $= \\{0, \\dots, n-1\\}$ |\n| `Set ℝ` | subset of $\\mathbb{R}$ | |\n| `ℕ → ℝ` | real sequence | `u n` is the term $u_n$ |\n\nWhen one statement mixes several types, Lean inserts **coercions**: `(n : ℝ)` or `↑n` denotes the integer $n$ seen\nas a real number. A statement like `(n : ℝ) / 2` does not mean the same as `n / 2` on `ℕ`.\n\n## Pitfalls that change the meaning\n\nThese translations are accepted by Lean, but do not say what one thinks.\n\n1. **Subtraction on ℕ**: `2 - 5 = 0` in `ℕ`. A statement about $a - b$ where $a < b$ is possible must be written in\n   `ℤ` or `ℝ`.\n2. **Division on ℕ and ℤ**: `7 / 2 = 3`. “$n/2$” in mathematics is often a rational number.\n3. **Division by zero**: in `ℝ`, `x / 0 = 0` by convention. A statement `x / y * y = x` is false for `y = 0`, and a\n   translation that forgets the hypothesis `y ≠ 0` may become false… or trivial.\n4. **Total functions**: `Real.sqrt (-1) = 0`, `Real.log 0 = 0`. A forgotten hypothesis ($x > 0$) causes no error.\n5. **Contradictory hypotheses**: if the hypotheses cannot all hold, *any* conclusion can be proved. A very short\n   proof of a hard statement is a warning sign.\n6. **Indices**: `Finset.range n` starts at 0. $\\sum_{k=1}^{n} k$ is translated `∑ k in Finset.Icc 1 n, k`; with\n   `Finset.range n` the sum runs from 0 to $n-1$.\n7. **Quantifiers**: order matters. `∀ ε > 0, ∃ N, …` is not `∃ N, ∀ ε > 0, …`.\n8. **“There exists a unique”** is written `∃! x, P x`; `∃ x, P x` does not assert uniqueness.\n\nNotation: in recent versions of Mathlib the sum is written `∑ k ∈ Finset.Icc 1 n, k`; the “Prover” workspace (Lean\n4.9) still uses `∑ k in …`.\n\n## A reading method\n\n1. Read the conclusion alone: is it really what you want to prove?\n2. List the hypotheses: is one missing? Is there one too many (a superfluous hypothesis makes the statement weaker)?\n3. Check the type of each variable.\n4. Look for a division, a subtraction, a root, a logarithm: are they in the right type, with the right hypotheses?\n5. Try to falsify the statement on a small example. If the Lean statement is true and yours false (or the reverse),\n   the translation is wrong.\n\nThe “Understand” panel (*Learn* mode) gives a line-by-line gloss written by a model: it helps reading, but it can be\nwrong too; the code is authoritative. The vocabulary is in the [Glossary](glossary.md).\n",text:`Reading a Lean statement Lean proves exactly the Lean statement, not the sentence you had in mind. This page teaches you to read a statement well enough to judge a translation, without knowing how to write proofs. Anatomy of a statement Piece Reading theorem sommepairs a theorem, and its name (chosen by Madalean, unique) (a b : ℕ) “let $a$ and $b$ be natural numbers” (ha : Even a) hypothesis named ha: “$a$ is even” (hb : Even b) hypothesis hb: “$b$ is even” : Even (a + b) after the last : outside parentheses comes the conclusion: “$a+b$ is even” := by sorry “the proof follows, in tactic mode”; sorry = proof still to be written Everything in parentheses before the last : is assumed; what comes after is to be proved. A statement with sorry is a statement without a proof: Lean accepts it as a statement, never as a proved theorem. The same thing can be written with quantifiers in the conclusion; it is equivalent: → reads “implies”; ∀ a b : ℕ, “for all natural numbers $a$, $b$”. The header Statements of the “Prover” workspace start with a fixed header: import Mathlib loads the mathematical library; setoption maxHeartbeats raises the allowed computation time; open … lets you write π or √ without a prefix. This header does not change the meaning of the statement, but open Nat Real makes some names ambiguous (sqrt exists in both): look at the types. Types: which numbers are we talking about? Lean Mathematics Watch out ℕ $\\mathbb{N} = \\{0, 1, 2, \\dots\\}$ contains 0; truncated subtraction and division (see below) ℤ $\\mathbb{Z}$ / is Euclidean division: the remainder % is always $\\ge 0$, -7 / 2 = -4 ℚ, ℝ, ℂ $\\mathbb{Q}$, $\\mathbb{R}$, $\\mathbb{C}$ division by zero is defined and equals 0 Finset ℕ finite set of integers Finset.range n $= \\{0, \\dots, n-1\\}$ Set ℝ subset of $\\mathbb{R}$ ℕ → ℝ real sequence u n is the term $un$ When one statement mixes several types, Lean inserts coercions: (n : ℝ) or ↑n denotes the integer $n$ seen as a real number. A statement like (n : ℝ) / 2 does not mean the same as n / 2 on ℕ. Pitfalls that change the meaning These translations are accepted by Lean, but do not say what one thinks. 1. Subtraction on ℕ: 2 - 5 = 0 in ℕ. A statement about $a - b$ where $a < b$ is possible must be written in ℤ or ℝ. 2. Division on ℕ and ℤ: 7 / 2 = 3. “$n/2$” in mathematics is often a rational number. 3. Division by zero: in ℝ, x / 0 = 0 by convention. A statement x / y y = x is false for y = 0, and a translation that forgets the hypothesis y ≠ 0 may become false… or trivial. 4. Total functions: Real.sqrt (-1) = 0, Real.log 0 = 0. A forgotten hypothesis ($x > 0$) causes no error. 5. Contradictory hypotheses: if the hypotheses cannot all hold, any conclusion can be proved. A very short proof of a hard statement is a warning sign. 6. Indices: Finset.range n starts at 0. $\\sum{k=1}^{n} k$ is translated ∑ k in Finset.Icc 1 n, k; with Finset.range n the sum runs from 0 to $n-1$. 7. Quantifiers: order matters. ∀ ε > 0, ∃ N, … is not ∃ N, ∀ ε > 0, …. 8. “There exists a unique” is written ∃! x, P x; ∃ x, P x does not assert uniqueness. Notation: in recent versions of Mathlib the sum is written ∑ k ∈ Finset.Icc 1 n, k; the “Prover” workspace (Lean 4.9) still uses ∑ k in …. A reading method 1. Read the conclusion alone: is it really what you want to prove? 2. List the hypotheses: is one missing? Is there one too many (a superfluous hypothesis makes the statement weaker)? 3. Check the type of each variable. 4. Look for a division, a subtraction, a root, a logarithm: are they in the right type, with the right hypotheses? 5. Try to falsify the statement on a small example. If the Lean statement is true and yours false (or the reverse), the translation is wrong. The “Understand” panel (Learn mode) gives a line-by-line gloss written by a model: it helps reading, but it can be wrong too; the code is authoritative. The vocabulary is in the Glossary.`},{id:`validation`,lang:`en`,title:`Approve the meaning and the statement`,order:115,section:`use`,audience:`all`,summary:`Madalean shows what it understood, then the Lean statement, and waits for your approval before any proof.`,source:`en/validation.md`,site_path:`en/validation.html`,headings:[{level:1,text:`Approve the meaning and the statement`,id:`approve-the-meaning-and-the-statement`},{level:2,text:`Open or false problem`,id:`open-or-false-problem`},{level:2,text:`"Misunderstood"`,id:`misunderstood`},{level:2,text:`Proving without approval`,id:`proving-without-approval`}],images:[],verify:[],body:`# Approve the meaning and the statement

Before any proof search, Madalean asks for two approvals.

1. **The meaning**: the statement rewritten, its objects, its hypotheses, what is claimed, and the known status. A status
   supported by a passage found in the literature is quoted word for word; otherwise it says "according to a model, to
   be checked".
2. **The Lean statement**: one or two translations by different models, each read back by a model that does not see your
   problem. Missing objects or numbers are pointed out.

You can accept, correct in your own words, or write the Lean statement yourself. Approvals keep waiting even if Madalean
restarts.

## Open or false problem

Madalean says so first. Your statement stays the target of the dossier. Related known results are opened as
sub-dossiers, up to their own approval; one card can approve several of them.

A fix that changes your statement is marked as such. When fixes go round in circles, Madalean stops suggesting them and
explains why.

## "Misunderstood"

Report a step that was misunderstood and say why. The work that depends on it stops, the step is redone with your remark,
and the remark helps with similar problems. You can delete it in the lessons (Settings).

## Proving without approval

"Prove anyway" accepts the statement as it is. The setting "Approve before proving" can be turned off.
`,text:`Approve the meaning and the statement Before any proof search, Madalean asks for two approvals. 1. The meaning: the statement rewritten, its objects, its hypotheses, what is claimed, and the known status. A status supported by a passage found in the literature is quoted word for word; otherwise it says "according to a model, to be checked". 2. The Lean statement: one or two translations by different models, each read back by a model that does not see your problem. Missing objects or numbers are pointed out. You can accept, correct in your own words, or write the Lean statement yourself. Approvals keep waiting even if Madalean restarts. Open or false problem Madalean says so first. Your statement stays the target of the dossier. Related known results are opened as sub-dossiers, up to their own approval; one card can approve several of them. A fix that changes your statement is marked as such. When fixes go round in circles, Madalean stops suggesting them and explains why. "Misunderstood" Report a step that was misunderstood and say why. The work that depends on it stops, the step is redone with your remark, and the remark helps with similar problems. You can delete it in the lessons (Settings). Proving without approval "Prove anyway" accepts the statement as it is. The setting "Approve before proving" can be turned off.`},{id:`follow-ups`,lang:`en`,title:`Follow-up requests and versions`,order:120,section:`use`,audience:`all`,summary:`Continuing the discussion on a dossier, choosing which stage to redo, going back to an earlier version.`,source:`en/follow-ups.md`,site_path:`en/follow-ups.html`,headings:[{level:1,text:`Follow-up requests and versions`,id:`follow-up-requests-and-versions`},{level:2,text:`Which stage is redone?`,id:`which-stage-is-redone`},{level:2,text:`Versions`,id:`versions`},{level:2,text:`What the assistant remembers`,id:`what-the-assistant-remembers`}],images:[],verify:[],body:`# Follow-up requests and versions

A dossier is never frozen. In the dossier thread, the field “A clarification, a correction?” accepts a request in
plain language:

- “add the hypothesis $n > 0$”
- “and the converse?”
- “a shorter proof”
- “explain step 2”
- “without using \`nlinarith\`”

\`Ctrl+Enter\` sends.

## Which stage is redone?

The menu next to “Send” chooses what must change:

| Choice | Effect |
|---|---|
| *Automatic* | a model reads the request and chooses the stage; failing that, keywords decide |
| *Statement* | new Lean statement (following the request) → new proof → new explanation |
| *Proof* | new proof of the same statement → new explanation |
| *Explanation* | new explanation only |

If the request changes the statement, the old proof no longer applies: Madalean searches for a new one. The buttons
below the proof (“Simpler proof”, “Another method”, “Explain in more detail”, “Split into lemmas”) are ready-made
requests.

## Versions

Each statement, each proof, each explanation produces a **new version**; nothing is erased. Each version shows its
source (a model, with its name, or you), the request that produced it and, for a proof, its Lean verdict.

“Go back to this one” makes a version current without deleting the others. Going back to a proof also brings back
the statement it proves. A proof counts as the dossier's proof only if it proves the **current** statement.

## What the assistant remembers

- **Your profile** (“Settings › Profile”): read before every translation and every explanation.
- **The dossier thread**: each correction builds on the previous versions.
- **The library**: each proved result is offered as a lemma to later proofs in the same Lean workspace.
- Lemma names already rejected by Lean in this dossier are no longer proposed.
`,text:`Follow-up requests and versions A dossier is never frozen. In the dossier thread, the field “A clarification, a correction?” accepts a request in plain language: - “add the hypothesis $n > 0$” - “and the converse?” - “a shorter proof” - “explain step 2” - “without using nlinarith” Ctrl+Enter sends. Which stage is redone? The menu next to “Send” chooses what must change: Choice Effect Automatic a model reads the request and chooses the stage; failing that, keywords decide Statement new Lean statement (following the request) → new proof → new explanation Proof new proof of the same statement → new explanation Explanation new explanation only If the request changes the statement, the old proof no longer applies: Madalean searches for a new one. The buttons below the proof (“Simpler proof”, “Another method”, “Explain in more detail”, “Split into lemmas”) are ready-made requests. Versions Each statement, each proof, each explanation produces a new version; nothing is erased. Each version shows its source (a model, with its name, or you), the request that produced it and, for a proof, its Lean verdict. “Go back to this one” makes a version current without deleting the others. Going back to a proof also brings back the statement it proves. A proof counts as the dossier's proof only if it proves the current statement. What the assistant remembers - Your profile (“Settings › Profile”): read before every translation and every explanation. - The dossier thread: each correction builds on the previous versions. - The library: each proved result is offered as a lemma to later proofs in the same Lean workspace. - Lemma names already rejected by Lean in this dossier are no longer proposed.`},{id:`projects`,lang:`en`,title:`Projects and parallel dossiers`,order:130,section:`use`,audience:`all`,summary:`Grouping dossiers into projects, running several jobs at once, understanding the queue.`,source:`en/projects.md`,site_path:`en/projects.html`,headings:[{level:1,text:`Projects and parallel dossiers`,id:`projects-and-parallel-dossiers`},{level:2,text:`Finding your way`,id:`finding-your-way`},{level:2,text:`Projects`,id:`projects`},{level:2,text:`Several dossiers at once`,id:`several-dossiers-at-once`},{level:2,text:`On every device`,id:`on-every-device`},{level:2,text:`Lean workspaces`,id:`lean-workspaces`}],images:[{src:`img/navigation.png`,exists:!0},{src:`img/activity.png`,exists:!0}],verify:[],body:`# Projects and parallel dossiers

## Finding your way

Everything is in the same place on a computer, a tablet or a phone:

- **The Madal∃an logo**, top left, opens the menu: “Home” first, then Activity, Library, Glossary, Notebook, Help,
  Settings, the *Learn* / *Research* choice and the project bar. A second click on the logo, menu open, goes home.
- **The project name** (and, in a dossier, the dossier's) next to the logo is the one place to change project or
  dossier: projects on the left (“New project…”, “Project overview”), the chosen project's dossiers on the right,
  with their state. Names are written in full.
- **The project bar**, under the top bar: Dossiers · Sources · Notes · Graph · Blueprint · Article · Conjectures ·
  Calcul · Publish. \`Ctrl+Shift+1\` hides or shows it.
- **The status button**, top right (cloud: online; chip: local): the mode, the model receiving your work, the host's
  resources (processor, memory, graphics card), tokens and cost (this request, today, this month), running jobs.
  These measurements are only taken while the panel is open.

A menu or a panel closes with a click elsewhere or \`Esc\`. **Everything saves itself**: a dossier's title and
statement, notes, the article, Calcul cells, experiment code, the plan, the project description, settings. A small
“Saved” confirms it; “Not saved — retrying” signals a network problem (Madalean retries, your text stays on screen).

![The logo menu](img/navigation.png)

## Projects

A **project** groups dossiers: a course chapter, a paper in preparation, a set of exercises. The project name at the
top left (“All projects”) chooses one; the “Dossiers” page then shows its dossiers. A project has its Lean workspace,
its bibliography, its sources, its notes, its article outline; its title and description are edited on its page
(“Project overview”).

Deleting a project moves it to the trash: “Undo” restores it. Its dossiers are not deleted.

## Several dossiers at once

You can start as many dossiers as you like; they progress in parallel, limited by the host's resources:

| Resource | Slots | Used by |
|---|---|---|
| graphics card | 1 | one local model at a time (Madalean switches models according to the stage) |
| online | 3 | calls to online models |
| Lean | 2 | compilations |

A job only waits for the resource of its current stage; your jobs go before automatic retries. The “Activity” screen
shows what is running, what is waiting and why (“waiting: graphics card”).

![Activity: jobs in parallel](img/activity.png)

A dossier has only one active job at a time; a new request on a busy dossier is refused with a clear message. Any job
stops on request.

## On every device

All linked devices see the same projects, the same dossiers and the same jobs live. Start a proof from the phone,
follow it on the PC. After a network cut, the device resynchronises by itself.

## Lean workspaces

Each project uses a Lean **workspace** (“Settings › Lean workspaces”):

- *Prover*: Lean 4.9 and the Mathlib the Goedel models were trained on. Pinned: it is never updated, so that the
  local models remain effective.
- *Current Lean*: latest Mathlib, updated automatically (see [Updates](updates.md)).

A library result can be reused only in the workspace where it was proved.
`,text:`Projects and parallel dossiers Finding your way Everything is in the same place on a computer, a tablet or a phone: - The Madal∃an logo, top left, opens the menu: “Home” first, then Activity, Library, Glossary, Notebook, Help, Settings, the Learn / Research choice and the project bar. A second click on the logo, menu open, goes home. - The project name (and, in a dossier, the dossier's) next to the logo is the one place to change project or dossier: projects on the left (“New project…”, “Project overview”), the chosen project's dossiers on the right, with their state. Names are written in full. - The project bar, under the top bar: Dossiers · Sources · Notes · Graph · Blueprint · Article · Conjectures · Calcul · Publish. Ctrl+Shift+1 hides or shows it. - The status button, top right (cloud: online; chip: local): the mode, the model receiving your work, the host's resources (processor, memory, graphics card), tokens and cost (this request, today, this month), running jobs. These measurements are only taken while the panel is open. A menu or a panel closes with a click elsewhere or Esc. Everything saves itself: a dossier's title and statement, notes, the article, Calcul cells, experiment code, the plan, the project description, settings. A small “Saved” confirms it; “Not saved — retrying” signals a network problem (Madalean retries, your text stays on screen). The logo menu Projects A project groups dossiers: a course chapter, a paper in preparation, a set of exercises. The project name at the top left (“All projects”) chooses one; the “Dossiers” page then shows its dossiers. A project has its Lean workspace, its bibliography, its sources, its notes, its article outline; its title and description are edited on its page (“Project overview”). Deleting a project moves it to the trash: “Undo” restores it. Its dossiers are not deleted. Several dossiers at once You can start as many dossiers as you like; they progress in parallel, limited by the host's resources: Resource Slots Used by graphics card 1 one local model at a time (Madalean switches models according to the stage) online 3 calls to online models Lean 2 compilations A job only waits for the resource of its current stage; your jobs go before automatic retries. The “Activity” screen shows what is running, what is waiting and why (“waiting: graphics card”). Activity: jobs in parallel A dossier has only one active job at a time; a new request on a busy dossier is refused with a clear message. Any job stops on request. On every device All linked devices see the same projects, the same dossiers and the same jobs live. Start a proof from the phone, follow it on the PC. After a network cut, the device resynchronises by itself. Lean workspaces Each project uses a Lean workspace (“Settings › Lean workspaces”): - Prover: Lean 4.9 and the Mathlib the Goedel models were trained on. Pinned: it is never updated, so that the local models remain effective. - Current Lean: latest Mathlib, updated automatically (see Updates). A library result can be reused only in the workspace where it was proved.`},{id:`proof-plans`,lang:`en`,title:`Proof plans and lemmas`,order:140,section:`use`,audience:`researcher`,summary:`Splitting a result into lemmas proved in parallel, admitting temporarily, and what “proved modulo” means.`,source:`en/proof-plans.md`,site_path:`en/proof-plans.html`,headings:[{level:1,text:`Proof plans and lemmas`,id:`proof-plans-and-lemmas`},{level:2,text:`Split into lemmas (quick)`,id:`split-into-lemmas-quick`},{level:2,text:`Proof plan as a mind map (the main way)`,id:`proof-plan-as-a-mind-map-the-main-way`},{level:2,text:`Admitting temporarily`,id:`admitting-temporarily`},{level:2,text:`Good practice`,id:`good-practice`}],images:[],verify:[],body:`# Proof plans and lemmas

A statement too big for a proof in one piece gets split. Madalean offers two tools.

## Split into lemmas (quick)

“Split into lemmas” on a dossier: a model proposes up to four lemmas in Lean (or you write them, one per paragraph).
Each lemma becomes a **sub-dossier** started at once, in parallel. When all are finished and at least one is proved,
the parent dossier is restarted automatically with the proved lemmas at its disposal.

## Proof plan as a mind map (the main way)

« Plan » tab of a dossier (also from the thread and after a failed proof). One path:

1. **« Split this theorem »** (a hint for the AI is optional). The model proposes 2 to 6 lemmas, preferably
   independent, each with its statement in words, its Lean statement and why it helps, plus the **combination**: the
   Lean proof of the theorem from the lemmas. It keeps up to two **other tracks** (different strategies), dashed on
   the map.
2. Before showing you the plan, **Lean checks** that every statement compiles and that the theorem follows from the
   lemmas; otherwise the plan is asked again once with Lean's errors. An unchecked combination is marked « to check ».
   A lemma closed by a simple tactic (\`simp\`, \`omega\`, \`exact?\`…) is **obvious**: proved at once, never split again.
   A lemma that restates the theorem itself is **refused** (loop guard).
3. Read, edit if needed (any node can be edited by hand, each change is a version), then **« Approve the plan »** and
   **« Prove the plan »**: each lemma becomes a sub-dossier proved automatically (Mathlib first, then the model
   tournament); when all lemmas of a node are proved, the combination is compiled with the real proofs, strict
   verdict.
4. Madalean only comes back to you when a lemma **fails**, and offers in order: **another track**, **split it** one
   level deeper, or **leave a hole** (\`sorry\`).

At the top, a « where are we » line says what is left to do. Every node has a written status (to approve, in
progress, proved, failed, abandoned track, hole) and a path from the theorem. Limits: 3 levels of splitting
(adjustable), 6 lemmas per track, 2 other tracks, 30 nodes per plan, and a total time (Settings › Models ›
advanced). On a phone the collapsible list is the main view, the map is one tap away.

## Admitting temporarily

A node whose Lean statement is accepted can be marked “admitted for now”. The parent's proof can then rely on it:
Lean compiles the parent with the admitted lemma written as \`sorry\`.

The result is **proved modulo** the admitted lemmas. It is **not** a checked proof:

- it is not recorded as the dossier's proof, which stays “not proved”;
- the listed axioms contain \`sorryAx\`, Lean's trace of a \`sorry\`;
- the plan shows “proved modulo N admitted lemmas” with their names.

When each admitted lemma later gets a real proof, Madalean replaces the \`sorry\`s with the real lemmas and checks the
parent again with the strict verdict. Only then is the dossier proved.

## Good practice

- State the lemmas in Lean as early as possible: a node without an accepted Lean statement can be neither proved nor
  admitted.
- Prefer **general**, short lemmas; they enter the library and are reused.
- A lemma rejected several times is often badly stated (missing hypothesis) rather than hard: read it again as in
  [Reading a Lean statement](reading-lean.md).
`,text:`Proof plans and lemmas A statement too big for a proof in one piece gets split. Madalean offers two tools. Split into lemmas (quick) “Split into lemmas” on a dossier: a model proposes up to four lemmas in Lean (or you write them, one per paragraph). Each lemma becomes a sub-dossier started at once, in parallel. When all are finished and at least one is proved, the parent dossier is restarted automatically with the proved lemmas at its disposal. Proof plan as a mind map (the main way) « Plan » tab of a dossier (also from the thread and after a failed proof). One path: 1. « Split this theorem » (a hint for the AI is optional). The model proposes 2 to 6 lemmas, preferably independent, each with its statement in words, its Lean statement and why it helps, plus the combination: the Lean proof of the theorem from the lemmas. It keeps up to two other tracks (different strategies), dashed on the map. 2. Before showing you the plan, Lean checks that every statement compiles and that the theorem follows from the lemmas; otherwise the plan is asked again once with Lean's errors. An unchecked combination is marked « to check ». A lemma closed by a simple tactic (simp, omega, exact?…) is obvious: proved at once, never split again. A lemma that restates the theorem itself is refused (loop guard). 3. Read, edit if needed (any node can be edited by hand, each change is a version), then « Approve the plan » and « Prove the plan »: each lemma becomes a sub-dossier proved automatically (Mathlib first, then the model tournament); when all lemmas of a node are proved, the combination is compiled with the real proofs, strict verdict. 4. Madalean only comes back to you when a lemma fails, and offers in order: another track, split it one level deeper, or leave a hole (sorry). At the top, a « where are we » line says what is left to do. Every node has a written status (to approve, in progress, proved, failed, abandoned track, hole) and a path from the theorem. Limits: 3 levels of splitting (adjustable), 6 lemmas per track, 2 other tracks, 30 nodes per plan, and a total time (Settings › Models › advanced). On a phone the collapsible list is the main view, the map is one tap away. Admitting temporarily A node whose Lean statement is accepted can be marked “admitted for now”. The parent's proof can then rely on it: Lean compiles the parent with the admitted lemma written as sorry. The result is proved modulo the admitted lemmas. It is not a checked proof: - it is not recorded as the dossier's proof, which stays “not proved”; - the listed axioms contain sorryAx, Lean's trace of a sorry; - the plan shows “proved modulo N admitted lemmas” with their names. When each admitted lemma later gets a real proof, Madalean replaces the sorrys with the real lemmas and checks the parent again with the strict verdict. Only then is the dossier proved. Good practice - State the lemmas in Lean as early as possible: a node without an accepted Lean statement can be neither proved nor admitted. - Prefer general, short lemmas; they enter the library and are reused. - A lemma rejected several times is often badly stated (missing hypothesis) rather than hard: read it again as in Reading a Lean statement.`},{id:`proof-graph`,lang:`en`,title:`Problem graph, reasoned search and lessons`,order:145,section:`use`,audience:`researcher`,summary:`Madalean keeps the memory of each problem as a graph of lemmas, searches for a proof with guards, explains the proof with its bibliography and learns from its mistakes.`,source:`en/proof-graph.md`,site_path:`en/proof-graph.html`,headings:[{level:1,text:`Problem graph, reasoned search and lessons`,id:`problem-graph-reasoned-search-and-lessons`},{level:2,text:`Statuses`,id:`statuses`},{level:2,text:`Reasoned search`,id:`reasoned-search`},{level:2,text:`Explain the proof`,id:`explain-the-proof`},{level:2,text:`Sub-dossiers`,id:`sub-dossiers`},{level:2,text:`Adapt a method`,id:`adapt-a-method`},{level:2,text:`What Madalean learned`,id:`what-madalean-learned`}],images:[],verify:[],body:`# Problem graph, reasoned search and lessons

Each dossier has a **problem graph**: the **target** (the theorem or conjecture), the **known results** (Mathlib,
your library, the literature, attachments) and the **lemmas to prove**, with what was tried and why. It extends the
[proof plan](proof-plans.md): « Plan » tab, « Graph » view.

## Statuses

Each node has an icon, a word and a border style (never colour alone):

| Status | Meaning |
| --- | --- |
| verified by Lean | proved by Lean (strict verdict), or in Mathlib, or by a certificate |
| conditional | cited or provided without a Lean proof, or proved using such a result |
| to prove | still open |
| refuted | Lean proved the negation (counterexample) |
| abandoned | the reason is kept; the track is not retried while nothing has changed |

A proof that rests on a result cited but not proved in Lean is **always** “conditional, rests on …”, never
“verified”. It becomes verified when Lean proves that result.

A sub-lemma used by two lemmas exists once: it is listed under the first, the other shows “also used by …”. Two
statements that differ only by a hypothesis stay distinct; two statements that differ only by the names of their
variables or hypotheses (\`n\` or \`k\`, \`hn\` or \`h\`) are the same node (Lean confirms it when in doubt). Reordering the
variables gives another node.

**List or drawing.** On a wide screen, “Drawing” shows the graph drawn: the target on top, each lemma below the ones
that use it, a shared sub-lemma drawn once. Drag to move, wheel or + / − to zoom; Tab goes through the nodes in the
list order and Enter opens the detail. On a phone, the list stays the only view.

## Reasoned search

“Reasoned search” tries to prove the target directly, then splits it into lemmas when useful. Before working on a
track, Madalean assesses it (“Why this track?”): already proved elsewhere, already abandoned, close to a failed track,
the same Lean error twice, depth… and, when a model is available, a short opinion of the model, always labelled as
such. Proposed lemmas are first checked by Lean (statements, combination), and Madalean looks for a counterexample: first by computing the statement on small values when it can (integers
0 to 12, simple rationals — its own exact computation, never model-written code), then Lean tries to prove the
negation. A counterexample found is kept only when Lean confirms it: the lemma is then refuted, with the witness.
Otherwise the node's detail says “Tested on n ∈ 0..12: no counterexample”, which counts a little in its viability.

Guards: limits on time, attempts, depth, tokens and spending (never above the conductor's cap), a stop when nothing
progresses, loops refused (a lemma that would use what uses it). At the end, a summary says why the search stopped
and what was tried. “Stop this track” and “Resume” are in each node's detail.

## Explain the proof

“Explain the proof” builds the account **only from what was recorded**: the chosen track and why, the other tracks,
the lemmas and their status, the tactics used and what each does, what failed, and the bibliography (Mathlib
declarations with links, cited works with their verified reference, BibTeX). No model writes this text. “Explain line
by line” shows Lean's goals after each tactic. Exports: project note, LaTeX with \`\\cite\`, BibTeX.

## Sub-dossiers

“Open as a sub-dossier” turns a lemma into a full dossier (its thread, its own graph, Calcul, notes, certificates),
listed under its parent: “Project › Dossier › Lemma”. Its verdict rolls up to the parent (proved → proved;
conditional → conditional). The depth is bounded by “Max depth of the lemma decomposition”. Archiving, moving or
deleting a dossier does the same to its sub-dossiers (“Undo” brings them back together).

## Adapt a method

On a result whose method is known (its Lean proof, or the quoted passage), “Adapt the method” proposes a generalised
statement and the lemmas of the adapted proof. These are **proposals**: their statements are checked by Lean, and only
a Lean proof will validate them.

## What Madalean learned

Settings › “What Madalean learned”: lessons drawn **only from verified proofs**, whatever the model — a Mathlib name
that does not exist and the one that works (applied without a model, then re-checked by Lean), what fixed a Lean
error, dead ends, strategies that work. Each lesson shows its evidence and counters; those that stop helping are
dropped. You can delete some, forget everything, export or import a file.
`,text:`Problem graph, reasoned search and lessons Each dossier has a problem graph: the target (the theorem or conjecture), the known results (Mathlib, your library, the literature, attachments) and the lemmas to prove, with what was tried and why. It extends the proof plan: « Plan » tab, « Graph » view. Statuses Each node has an icon, a word and a border style (never colour alone): Status Meaning verified by Lean proved by Lean (strict verdict), or in Mathlib, or by a certificate conditional cited or provided without a Lean proof, or proved using such a result to prove still open refuted Lean proved the negation (counterexample) abandoned the reason is kept; the track is not retried while nothing has changed A proof that rests on a result cited but not proved in Lean is always “conditional, rests on …”, never “verified”. It becomes verified when Lean proves that result. A sub-lemma used by two lemmas exists once: it is listed under the first, the other shows “also used by …”. Two statements that differ only by a hypothesis stay distinct; two statements that differ only by the names of their variables or hypotheses (n or k, hn or h) are the same node (Lean confirms it when in doubt). Reordering the variables gives another node. List or drawing. On a wide screen, “Drawing” shows the graph drawn: the target on top, each lemma below the ones that use it, a shared sub-lemma drawn once. Drag to move, wheel or + / − to zoom; Tab goes through the nodes in the list order and Enter opens the detail. On a phone, the list stays the only view. Reasoned search “Reasoned search” tries to prove the target directly, then splits it into lemmas when useful. Before working on a track, Madalean assesses it (“Why this track?”): already proved elsewhere, already abandoned, close to a failed track, the same Lean error twice, depth… and, when a model is available, a short opinion of the model, always labelled as such. Proposed lemmas are first checked by Lean (statements, combination), and Madalean looks for a counterexample: first by computing the statement on small values when it can (integers 0 to 12, simple rationals — its own exact computation, never model-written code), then Lean tries to prove the negation. A counterexample found is kept only when Lean confirms it: the lemma is then refuted, with the witness. Otherwise the node's detail says “Tested on n ∈ 0..12: no counterexample”, which counts a little in its viability. Guards: limits on time, attempts, depth, tokens and spending (never above the conductor's cap), a stop when nothing progresses, loops refused (a lemma that would use what uses it). At the end, a summary says why the search stopped and what was tried. “Stop this track” and “Resume” are in each node's detail. Explain the proof “Explain the proof” builds the account only from what was recorded: the chosen track and why, the other tracks, the lemmas and their status, the tactics used and what each does, what failed, and the bibliography (Mathlib declarations with links, cited works with their verified reference, BibTeX). No model writes this text. “Explain line by line” shows Lean's goals after each tactic. Exports: project note, LaTeX with \\cite, BibTeX. Sub-dossiers “Open as a sub-dossier” turns a lemma into a full dossier (its thread, its own graph, Calcul, notes, certificates), listed under its parent: “Project › Dossier › Lemma”. Its verdict rolls up to the parent (proved → proved; conditional → conditional). The depth is bounded by “Max depth of the lemma decomposition”. Archiving, moving or deleting a dossier does the same to its sub-dossiers (“Undo” brings them back together). Adapt a method On a result whose method is known (its Lean proof, or the quoted passage), “Adapt the method” proposes a generalised statement and the lemmas of the adapted proof. These are proposals: their statements are checked by Lean, and only a Lean proof will validate them. What Madalean learned Settings › “What Madalean learned”: lessons drawn only from verified proofs, whatever the model — a Mathlib name that does not exist and the one that works (applied without a model, then re-checked by Lean), what fixed a Lean error, dead ends, strategies that work. Each lesson shows its evidence and counters; those that stop helping are dropped. You can delete some, forget everything, export or import a file.`},{id:`library`,lang:`en`,title:`Library of results`,order:150,section:`use`,audience:`all`,summary:`Your proven results, organised by domain, project or tag, with their status, who proved them, what they use, and export.`,source:`en/library.md`,site_path:`en/library.html`,headings:[{level:1,text:`Library of results`,id:`library-of-results`}],images:[],verify:[],body:`# Library of results

Every proof accepted by Lean goes into the **Library**; these results are then offered as lemmas to your next proofs
(same Lean and Mathlib version).

- **Group by** domain (classified automatically from the statement, editable), project or tag.
- **Cards** or **Table**: the choice is remembered on this device.
- **Status**: *Verified* (Lean accepted the proof, strict verdict) or *Conditional* (proof obtained by admitting
  lemmas of a proof plan: nothing is verified until they are proved).
- For each result: the statement in words and in Lean, the model (or you) that proved it, the axioms, what it
  **uses** and what **uses it**.
- **Export**: everything as Markdown or JSON; a single result as \`.lean\` (with the results it depends on).

Domain and tags are shared between your devices. Removing a result can be undone.
`,text:`Library of results Every proof accepted by Lean goes into the Library; these results are then offered as lemmas to your next proofs (same Lean and Mathlib version). - Group by domain (classified automatically from the statement, editable), project or tag. - Cards or Table: the choice is remembered on this device. - Status: Verified (Lean accepted the proof, strict verdict) or Conditional (proof obtained by admitting lemmas of a proof plan: nothing is verified until they are proved). - For each result: the statement in words and in Lean, the model (or you) that proved it, the axioms, what it uses and what uses it. - Export: everything as Markdown or JSON; a single result as .lean (with the results it depends on). Domain and tags are shared between your devices. Removing a result can be undone.`},{id:`conjectures`,lang:`en`,title:`Conjecture workshop`,order:200,section:`research`,audience:`researcher`,summary:`Proposing conjectures, testing them (Lean on small cases, Sage, counter-examples) before believing them, and promoting them by a proof.`,source:`en/conjectures.md`,site_path:`en/conjectures.html`,headings:[{level:1,text:`Conjecture workshop`,id:`conjecture-workshop`},{level:2,text:`Where conjectures come from`,id:`where-conjectures-come-from`},{level:2,text:`Explore: the conjecture engine`,id:`explore-the-conjecture-engine`},{level:2,text:`States of a conjecture`,id:`states-of-a-conjecture`},{level:2,text:`Testing before believing`,id:`testing-before-believing`},{level:2,text:`The evidence log`,id:`the-evidence-log`},{level:2,text:`Promoting`,id:`promoting`},{level:2,text:`Explore: the conjecture engine`,id:`explore-the-conjecture-engine-1`}],images:[],verify:[],body:`# Conjecture workshop

A conjecture is a dossier of a particular kind, with an **evidence log**: everything that was tried to test it. A
conjecture becomes a theorem only through a Lean proof.

## Where conjectures come from

Everything happens in the project's “Conjectures” screen.

- “Write a conjecture”: you write it in plain language; “Translate to Lean” then proposes a Lean statement, or you
  write one yourself (“Check and save the statement”).
- “Propose”: from the project's notes, proved results and sources, a model proposes a few with their motivation;
  “Keep this conjecture” keeps the ones you want. Proposals that are already known (duplicate, already a dossier,
  already in the library, already in Mathlib) are set aside and listed separately with the reason.

## Explore: the conjecture engine

The “Explore” button of the “Conjectures” screen opens a guided process to **find what to prove**. You ask a
question in words or with a formula (“the sum of the first n odd numbers”, “n^2 + n + 41”, a list of terms,
“connected graphs on n vertices”), then the steps follow one another before your eyes; each can be stopped, and
everything is recorded.

1. **Explore.** Madalean computes a table of data with Sage, in the project's notebook “Explorations (conjectures)”
   (the same protected space as Calcul). When the request is recognised, the code is written without a model,
   always the same for the same request. Otherwise a model writes it: **this code is shown to you and runs only
   after you approve this exact code**, as in [Calcul](calcul.md); an edit cancels the approval. Terms given by hand
   need no computation.
2. **Recognise.** The data are compared with the OEIS (the encyclopedia of integer sequences) and go through
   pattern finders that run on your computer, without the network: polynomial or rational formula, recurrence,
   generating function, multiplicativity, periodicity, congruences, order of growth, inequalities and relations
   between quantities. A formula is fitted on part of the terms and then **validated on terms kept aside**; a
   pattern that fails is discarded, and the journal says on which term. In Local mode the OEIS is not queried:
   nothing leaves the computer. The LMFDB database is not queried (it cannot be searched by a list of terms).
3. **State.** Each pattern kept becomes a precise conjecture, in words and formulas, with a Lean statement when
   possible (Lean must accept it) and an honest label: “checked up to n = 59 (60 cases), not proved”, “heuristic”,
   “agrees on 14 terms”. Never “true”.
4. **Attack.** “Look for a counter-example” takes the computation further and by sampling. A counter-example is
   kept only after a recomputation in a fresh kernel and, when there is a Lean statement, the check by Lean: the
   conjecture is then kept as “refuted”, with its counter-example. If it resists, “Attempt the proof” sends it into
   the usual pipeline (a dossier), or “Keep as an open conjecture” files it in the project.
5. **Journal.** Everything that was tried — patterns kept, patterns discarded and why, look-ups, hunts — stays in
   the exploration's journal, which you can export to a note or to the article. A conjecture already in the project
   is flagged as a duplicate.

Example of the demo mode: “n^2 + n + 41 up to 30” gives “always prime”, checked up to n = 30; the hunt finds
n = 40, and the conjecture is kept, refuted.

## States of a conjecture

| State | Meaning |
|---|---|
| proposed | stated, nothing tested |
| tested on cases | particular cases held (Lean or experiments) |
| Lean statement accepted | a Lean statement is accepted by Lean |
| proved | the dossier's current proof passes the strict verdict |
| refuted | a counter-example was **checked again** independently |

## Testing before believing

**Small cases in Lean** (“Test small cases with Lean”). Madalean writes one \`example\` per case (by default $n = 0, \\dots, 9$ for the first integer
variable) and tries to close it by computation (\`norm_num\`, \`decide\`, \`simp\`, \`omega\`). Option: a bounded statement
\`∀ n < K, …\` closed by \`decide\`. These tests prove nothing beyond the cases tested.

**Sage or Python experiments.** The model writes (or you write) a two-part program: a predicate \`holds(...)\` and a
search that calls \`report(...)\`. **The code is shown to you and runs only after you approve this exact code** (“I read this code:
approve and run”); any edit cancels the approval. Experiments only run from the host computer. Runs are confined (see [Security](security.md#code-run-on-the-host)) and limited in time
and memory.

**Counter-example.** An announced counter-example is not taken on trust: the predicate alone is re-evaluated at the
witness in a fresh kernel and, if the conjecture has a Lean statement, Lean must accept the negation of the statement
at the witness. Only then does the conjecture become “refuted”.

**Literature.** “Search the literature” queries the bibliographic databases (see [Sources](sources.md)) to find out
whether the statement is known.

## The evidence log

On screen it is called “Evidence log”. Each test, experiment, check or search adds a dated entry (with the code run, the output, the model and the device).
The log is **append-only** and its entries are chained by SHA-256 fingerprints: an entry modified afterwards shows
(“log intact” / “log altered!”).

## Promoting

When the conjecture is proved, “Promote to theorem” changes its kind; the history is kept.

Example from demo mode: “$n^2 + n + 41$ is prime for every $n$” holds for $n = 0, \\dots, 9$ in Lean, then an
experiment finds $n = 40$ ($40^2 + 40 + 41 = 41^2$), checked again: refuted.

## Explore: the conjecture engine

The « Explore » button of the « Conjectures » screen opens a guided process to **find what to prove**. Ask a question
in words or as a formula (“the sum of the first n odd numbers”, “n^2 + n + 41”, a list of terms, “connected graphs on
n vertices”); the steps then run in front of you, each can be stopped, and everything is logged.

1. **Explore.** Madalean computes a data table with Sage in the project's « Explorations (conjectures) » notebook
   (the same sandbox as Calcul). When the request is recognised, the code is written without a model, always the
   same for the same request. Otherwise a model writes it: **that code is shown to you and runs only after you approve
   that exact code**, as in [Calcul](calcul.md); editing it cancels the approval. Terms typed by hand need no
   computation.
2. **Recognise.** The data is compared with the OEIS (the encyclopedia of integer sequences) and run through pattern
   finders on your own computer, with no network: polynomial or rational formula, recurrence, generating function,
   multiplicativity, periodicity, congruences, growth, inequalities and relations between quantities. A formula is
   fitted on part of the terms and then **validated on held-out terms**; a pattern that fails is discarded, and the
   log says on which term. In Local mode the OEIS is not queried: nothing leaves the computer. The LMFDB is not
   queried (it cannot be searched by a list of terms).
3. **State.** Each surviving pattern becomes a precise conjecture, in words and formulas, with a Lean statement when
   possible (it must be accepted by Lean) and an honest label: “checked up to n = 59 (60 cases), not proved”,
   “heuristic”, “matches 14 terms”. Never “true”.
4. **Attack.** « Look for a counterexample » computes further and by random sampling. A counterexample counts only
   after a recomputation in a fresh kernel and, when there is a Lean statement, Lean's check: the conjecture is then
   kept as « refuted », with its counterexample. If it survives, « Try the proof » sends it to the usual pipeline (a
   dossier), or « Keep as an open conjecture » files it in the project.
5. **Log.** Everything tried — kept and discarded patterns, with the reason — stays in the conjecture's history, and
   can be exported to a note or the article.
`,text:`Conjecture workshop A conjecture is a dossier of a particular kind, with an evidence log: everything that was tried to test it. A conjecture becomes a theorem only through a Lean proof. Where conjectures come from Everything happens in the project's “Conjectures” screen. - “Write a conjecture”: you write it in plain language; “Translate to Lean” then proposes a Lean statement, or you write one yourself (“Check and save the statement”). - “Propose”: from the project's notes, proved results and sources, a model proposes a few with their motivation; “Keep this conjecture” keeps the ones you want. Proposals that are already known (duplicate, already a dossier, already in the library, already in Mathlib) are set aside and listed separately with the reason. Explore: the conjecture engine The “Explore” button of the “Conjectures” screen opens a guided process to find what to prove. You ask a question in words or with a formula (“the sum of the first n odd numbers”, “n^2 + n + 41”, a list of terms, “connected graphs on n vertices”), then the steps follow one another before your eyes; each can be stopped, and everything is recorded. 1. Explore. Madalean computes a table of data with Sage, in the project's notebook “Explorations (conjectures)” (the same protected space as Calcul). When the request is recognised, the code is written without a model, always the same for the same request. Otherwise a model writes it: this code is shown to you and runs only after you approve this exact code, as in Calcul; an edit cancels the approval. Terms given by hand need no computation. 2. Recognise. The data are compared with the OEIS (the encyclopedia of integer sequences) and go through pattern finders that run on your computer, without the network: polynomial or rational formula, recurrence, generating function, multiplicativity, periodicity, congruences, order of growth, inequalities and relations between quantities. A formula is fitted on part of the terms and then validated on terms kept aside; a pattern that fails is discarded, and the journal says on which term. In Local mode the OEIS is not queried: nothing leaves the computer. The LMFDB database is not queried (it cannot be searched by a list of terms). 3. State. Each pattern kept becomes a precise conjecture, in words and formulas, with a Lean statement when possible (Lean must accept it) and an honest label: “checked up to n = 59 (60 cases), not proved”, “heuristic”, “agrees on 14 terms”. Never “true”. 4. Attack. “Look for a counter-example” takes the computation further and by sampling. A counter-example is kept only after a recomputation in a fresh kernel and, when there is a Lean statement, the check by Lean: the conjecture is then kept as “refuted”, with its counter-example. If it resists, “Attempt the proof” sends it into the usual pipeline (a dossier), or “Keep as an open conjecture” files it in the project. 5. Journal. Everything that was tried — patterns kept, patterns discarded and why, look-ups, hunts — stays in the exploration's journal, which you can export to a note or to the article. A conjecture already in the project is flagged as a duplicate. Example of the demo mode: “n^2 + n + 41 up to 30” gives “always prime”, checked up to n = 30; the hunt finds n = 40, and the conjecture is kept, refuted. States of a conjecture State Meaning proposed stated, nothing tested tested on cases particular cases held (Lean or experiments) Lean statement accepted a Lean statement is accepted by Lean proved the dossier's current proof passes the strict verdict refuted a counter-example was checked again independently Testing before believing Small cases in Lean (“Test small cases with Lean”). Madalean writes one example per case (by default $n = 0, \\dots, 9$ for the first integer variable) and tries to close it by computation (normnum, decide, simp, omega). Option: a bounded statement ∀ n < K, … closed by decide. These tests prove nothing beyond the cases tested. Sage or Python experiments. The model writes (or you write) a two-part program: a predicate holds(...) and a search that calls report(...). The code is shown to you and runs only after you approve this exact code (“I read this code: approve and run”); any edit cancels the approval. Experiments only run from the host computer. Runs are confined (see Security) and limited in time and memory. Counter-example. An announced counter-example is not taken on trust: the predicate alone is re-evaluated at the witness in a fresh kernel and, if the conjecture has a Lean statement, Lean must accept the negation of the statement at the witness. Only then does the conjecture become “refuted”. Literature. “Search the literature” queries the bibliographic databases (see Sources) to find out whether the statement is known. The evidence log On screen it is called “Evidence log”. Each test, experiment, check or search adds a dated entry (with the code run, the output, the model and the device). The log is append-only and its entries are chained by SHA-256 fingerprints: an entry modified afterwards shows (“log intact” / “log altered!”). Promoting When the conjecture is proved, “Promote to theorem” changes its kind; the history is kept. Example from demo mode: “$n^2 + n + 41$ is prime for every $n$” holds for $n = 0, \\dots, 9$ in Lean, then an experiment finds $n = 40$ ($40^2 + 40 + 41 = 41^2$), checked again: refuted. Explore: the conjecture engine The « Explore » button of the « Conjectures » screen opens a guided process to find what to prove. Ask a question in words or as a formula (“the sum of the first n odd numbers”, “n^2 + n + 41”, a list of terms, “connected graphs on n vertices”); the steps then run in front of you, each can be stopped, and everything is logged. 1. Explore. Madalean computes a data table with Sage in the project's « Explorations (conjectures) » notebook (the same sandbox as Calcul). When the request is recognised, the code is written without a model, always the same for the same request. Otherwise a model writes it: that code is shown to you and runs only after you approve that exact code, as in Calcul; editing it cancels the approval. Terms typed by hand need no computation. 2. Recognise. The data is compared with the OEIS (the encyclopedia of integer sequences) and run through pattern finders on your own computer, with no network: polynomial or rational formula, recurrence, generating function, multiplicativity, periodicity, congruences, growth, inequalities and relations between quantities. A formula is fitted on part of the terms and then validated on held-out terms; a pattern that fails is discarded, and the log says on which term. In Local mode the OEIS is not queried: nothing leaves the computer. The LMFDB is not queried (it cannot be searched by a list of terms). 3. State. Each surviving pattern becomes a precise conjecture, in words and formulas, with a Lean statement when possible (it must be accepted by Lean) and an honest label: “checked up to n = 59 (60 cases), not proved”, “heuristic”, “matches 14 terms”. Never “true”. 4. Attack. « Look for a counterexample » computes further and by random sampling. A counterexample counts only after a recomputation in a fresh kernel and, when there is a Lean statement, Lean's check: the conjecture is then kept as « refuted », with its counterexample. If it survives, « Try the proof » sends it to the usual pipeline (a dossier), or « Keep as an open conjecture » files it in the project. 5. Log. Everything tried — kept and discarded patterns, with the reason — stays in the conjecture's history, and can be exported to a note or the article.`},{id:`calcul`,lang:`en`,title:`Compute (Sage and Python)`,order:205,section:`research`,audience:`researcher`,summary:`Sage or Python notebooks in an offline sandbox, a model that writes code on request, and one click to turn a result into a conjecture, a note, a Lean dossier or an article block.`,source:`en/calcul.md`,site_path:`en/calcul.html`,headings:[{level:1,text:`Compute (Sage and Python)`,id:`compute-sage-and-python`},{level:2,text:`Who can run what`,id:`who-can-run-what`},{level:2,text:`Asking the model`,id:`asking-the-model`},{level:2,text:`Outputs`,id:`outputs`},{level:2,text:`Using a result`,id:`using-a-result`},{level:2,text:`SageMath not installed yet`,id:`sagemath-not-installed-yet`}],images:[],verify:[],body:`# Compute (Sage and Python)

The **Compute** screen (project menu) holds the project's **notebooks** (“New notebook”, SageMath or Python). A
notebook is a list of cells sharing one kernel: variables persist from one cell to the next. The file is an ordinary
Jupyter notebook: “Open in JupyterLab” opens it as is, “Download (.ipynb)” gives a copy. Code runs on the host
computer in the **same sandbox** as the conjecture workshop's experiments: no network access, no access to your keys
or personal files, limited time and output.

## Who can run what

- **Your cells** (the ones you type) run with **Run** (or Ctrl+Enter, Shift+Enter to move to the next one). “Run
  all” runs the whole notebook again.
- **Code written by the model** is marked “To review”: it runs only after **Approve and run**. The approval is for
  that exact code: if it changes, read it and approve it again.
- From a linked phone or tablet you can read and write cells; running them is allowed only when the host ticked
  “Allow experiments from linked devices” (“Settings › Notebook and access”, host-only setting).

## Asking the model

The **+** button under the last cell adds a cell (an empty one also appears after the last cell runs). Type Sage
code, or describe the computation in words (“the roots of x^5+x^3+x+1 in F_16”): the cell recognises what you typed
and shows it as “Code / Request” — one click fixes a wrong guess. Shift+Enter runs the code or sends the request.
The cell type (Code, Request, Text, Figure) is the small menu at the top of the cell.

For a request, the model writes the code in a few seconds; it appears while being written, checked against the
installed Sage version before it is shown. “Rewrite”, right under the request, starts again at any time; “Approve
and run” is right under the code. When the code uses names defined above, the cell says so. If the run fails, the
model corrects it automatically (at most three times): each correction is a version of the cell (“Go back to the
previous version”) and still needs your approval, unless the host chose to run model code without approval.

On an error, “Explain the error” says in plain words what is wrong and proposes a fix you apply in one click (to
approve). In “⋯”, “Explain line by line” comments each line. Requests that worked become **learned recipes**: a
similar request is written at once (notebook “⋯” › “Learned recipes” to see or delete them). A computation proves nothing in
general: it checks cases.

## Outputs

Text, formulas (rendered as in LaTeX) and plots. An output that is “Out of date” (code or a cell above changed since)
is flagged. Each cell keeps the versions of its code (“History”).

## Using a result

In the “More actions” of a cell that has an output:

| Action | Effect |
|---|---|
| Create a conjecture | creates a project conjecture; the code and its output are attached as motivation |
| Add to a note | copies the code and its output into a new note |
| Create a Lean dossier | opens a dossier with the statement to prove, prefilled from the result (correct it if needed) |
| Insert in the article | the result goes into the article; the code goes to the “Computations” section at the end |

A PNG plot from Compute can also be inserted as an article figure (“Insert › Figure… › From Calcul” in the article
editor).

## SageMath not installed yet

Python notebooks work right away. SageMath is installed on demand (about 1.5 GB to download, nearly 5 GB on disk):
**Install Sage** button in a Sage notebook, on the host computer. The screen shows the current step and the
percentage.
`,text:`Compute (Sage and Python) The Compute screen (project menu) holds the project's notebooks (“New notebook”, SageMath or Python). A notebook is a list of cells sharing one kernel: variables persist from one cell to the next. The file is an ordinary Jupyter notebook: “Open in JupyterLab” opens it as is, “Download (.ipynb)” gives a copy. Code runs on the host computer in the same sandbox as the conjecture workshop's experiments: no network access, no access to your keys or personal files, limited time and output. Who can run what - Your cells (the ones you type) run with Run (or Ctrl+Enter, Shift+Enter to move to the next one). “Run all” runs the whole notebook again. - Code written by the model is marked “To review”: it runs only after Approve and run. The approval is for that exact code: if it changes, read it and approve it again. - From a linked phone or tablet you can read and write cells; running them is allowed only when the host ticked “Allow experiments from linked devices” (“Settings › Notebook and access”, host-only setting). Asking the model The + button under the last cell adds a cell (an empty one also appears after the last cell runs). Type Sage code, or describe the computation in words (“the roots of x^5+x^3+x+1 in F16”): the cell recognises what you typed and shows it as “Code / Request” — one click fixes a wrong guess. Shift+Enter runs the code or sends the request. The cell type (Code, Request, Text, Figure) is the small menu at the top of the cell. For a request, the model writes the code in a few seconds; it appears while being written, checked against the installed Sage version before it is shown. “Rewrite”, right under the request, starts again at any time; “Approve and run” is right under the code. When the code uses names defined above, the cell says so. If the run fails, the model corrects it automatically (at most three times): each correction is a version of the cell (“Go back to the previous version”) and still needs your approval, unless the host chose to run model code without approval. On an error, “Explain the error” says in plain words what is wrong and proposes a fix you apply in one click (to approve). In “⋯”, “Explain line by line” comments each line. Requests that worked become learned recipes: a similar request is written at once (notebook “⋯” › “Learned recipes” to see or delete them). A computation proves nothing in general: it checks cases. Outputs Text, formulas (rendered as in LaTeX) and plots. An output that is “Out of date” (code or a cell above changed since) is flagged. Each cell keeps the versions of its code (“History”). Using a result In the “More actions” of a cell that has an output: Action Effect Create a conjecture creates a project conjecture; the code and its output are attached as motivation Add to a note copies the code and its output into a new note Create a Lean dossier opens a dossier with the statement to prove, prefilled from the result (correct it if needed) Insert in the article the result goes into the article; the code goes to the “Computations” section at the end A PNG plot from Compute can also be inserted as an article figure (“Insert › Figure… › From Calcul” in the article editor). SageMath not installed yet Python notebooks work right away. SageMath is installed on demand (about 1.5 GB to download, nearly 5 GB on disk): Install Sage button in a Sage notebook, on the host computer. The screen shows the current step and the percentage.`},{id:`news`,lang:`en`,title:`News`,order:205,section:`research`,audience:`all`,summary:`Follow what is new in mathematics — papers by field, open problems, Lean and Mathlib, AI for maths — and send it to a project.`,source:`en/news.md`,site_path:`en/news.html`,headings:[{level:1,text:`News`,id:`news`},{level:2,text:`What you find there`,id:`what-you-find-there`},{level:2,text:`Sorting and searching`,id:`sorting-and-searching`},{level:2,text:`Sending to a project`,id:`sending-to-a-project`},{level:2,text:`French summary`,id:`french-summary`},{level:2,text:`Updates`,id:`updates`},{level:2,text:`Settings › News`,id:`settings-news`},{level:2,text:`What leaves your computer`,id:`what-leaves-your-computer`},{level:2,text:`Check it yourself`,id:`check-it-yourself`}],images:[],verify:[],body:`# News

The **News** screen (logo menu) gathers what is new in mathematics. Madalean fetches it for you, from time to time,
from public addresses; everything is kept on the host computer and can be read without the Internet.

## What you find there

| Section | Sources |
|---|---|
| New papers | arXiv, every mathematics category and logic in computer science |
| Open problems | the Erdős problems (status changes), MathOverflow questions tagged “open-problems”, the Polymath blog |
| Lean and Mathlib | Lean releases, the latest additions to Mathlib, the Lean community blog, the Xena blog |
| AI for mathematics | arXiv papers about automated proving, formalisation and mathematical reasoning |
| Announcements, prizes and outreach | the AMS, Quanta Magazine, Images des mathématiques, Terence Tao's blog |
| Your feeds | the RSS or Atom addresses you add yourself |

Each item shows its source, date, authors, abstract and a link to the original page, which opens in the browser.
Madalean keeps only the title, an excerpt and the link: the full text is read on the original site.

## Sorting and searching

- **Search**: a word, an author; accents do not matter.
- **Field**: algebra, number theory, geometry, topology, analysis, partial differential equations, probability,
  statistics, combinatorics, logic, category theory, numerical analysis, optimisation, mathematical physics, history
  and education. The field comes from the category given by the source, otherwise from the words of the title and
  the abstract.
- **Unread**, **Saved**, **Open problems**.
- **My fields**: only the fields ticked in Settings › News.
- **For my projects**: the items that share rare words with your projects (titles, statements of the dossiers,
  titles of the notes and of the sources). The words in common are shown. This sorting happens on your computer:
  nothing of your projects is sent.

Opening an item marks it as read. “Save” keeps it without a time limit.

## Sending to a project

In an open item, four buttons send it to the project chosen in the top bar:

- **Add to the project's Sources** (arXiv papers): the paper enters the project's library, as if you had given its
  identifier in the Sources screen.
- **Create a conjecture**: the title and the abstract become the statement of a conjecture, with the original link.
- **Create a dossier from this problem**: a dossier is created with this text as its statement. Nothing is started:
  read and correct the statement first.
- **Send to a note**: a note with the quotation, the authors, the link and the date.

## French summary

“Summarise in French” asks a free online model for a summary of two or three sentences. The original text always
stays below it: the summary is a reading aid, not a source. The button only appears for sources whose licence allows
it (arXiv, MathOverflow, Mathlib, your own feeds); for a blog, a magazine or a learned society, Madalean keeps to
the title, the excerpt and the link. The setting “Summarise automatically” does it for a few
new items of your fields at each update.

A text that comes from the Internet may contain sentences written to mislead a program. Madalean treats it as a text
to read, never as an instruction; when it spots such sentences, it says so and does not send that text to a model.

## Updates

Every 6 hours by default, while the host computer is on and connected to the Internet. “Update” does it at once. A
source that does not answer is tried again later, less and less often.

In **Local mode**, Madalean fetches nothing: you read what is already stored.

The number of unread items appears on Home (“What's new”) and in the menu. No message ever pops up by itself.

## Settings › News

- the fields followed;
- each source, to turn on or off, with its licence and terms;
- your own RSS or Atom feeds (an \`https\` address of a public site);
- the frequency, how long items are kept, automatic summaries, whether the unread number is shown.

## What leaves your computer

Only anonymous reads of the addresses listed in Settings › News: no account, no key, no name, no e-mail address. If
you ask for a summary, the item's title and public abstract are sent to the online model, and nothing else. See also
[Security and privacy](security.md).

## Check it yourself

1. Logo menu › News: the list fills after “Update” (outside Local mode).
2. Tick “Open problems”: only MathOverflow questions and open Erdős problems remain.
3. Switch to Local mode, then “Update”: the button is inactive and the list stays readable.
`,text:`News The News screen (logo menu) gathers what is new in mathematics. Madalean fetches it for you, from time to time, from public addresses; everything is kept on the host computer and can be read without the Internet. What you find there Section Sources New papers arXiv, every mathematics category and logic in computer science Open problems the Erdős problems (status changes), MathOverflow questions tagged “open-problems”, the Polymath blog Lean and Mathlib Lean releases, the latest additions to Mathlib, the Lean community blog, the Xena blog AI for mathematics arXiv papers about automated proving, formalisation and mathematical reasoning Announcements, prizes and outreach the AMS, Quanta Magazine, Images des mathématiques, Terence Tao's blog Your feeds the RSS or Atom addresses you add yourself Each item shows its source, date, authors, abstract and a link to the original page, which opens in the browser. Madalean keeps only the title, an excerpt and the link: the full text is read on the original site. Sorting and searching - Search: a word, an author; accents do not matter. - Field: algebra, number theory, geometry, topology, analysis, partial differential equations, probability, statistics, combinatorics, logic, category theory, numerical analysis, optimisation, mathematical physics, history and education. The field comes from the category given by the source, otherwise from the words of the title and the abstract. - Unread, Saved, Open problems. - My fields: only the fields ticked in Settings › News. - For my projects: the items that share rare words with your projects (titles, statements of the dossiers, titles of the notes and of the sources). The words in common are shown. This sorting happens on your computer: nothing of your projects is sent. Opening an item marks it as read. “Save” keeps it without a time limit. Sending to a project In an open item, four buttons send it to the project chosen in the top bar: - Add to the project's Sources (arXiv papers): the paper enters the project's library, as if you had given its identifier in the Sources screen. - Create a conjecture: the title and the abstract become the statement of a conjecture, with the original link. - Create a dossier from this problem: a dossier is created with this text as its statement. Nothing is started: read and correct the statement first. - Send to a note: a note with the quotation, the authors, the link and the date. French summary “Summarise in French” asks a free online model for a summary of two or three sentences. The original text always stays below it: the summary is a reading aid, not a source. The button only appears for sources whose licence allows it (arXiv, MathOverflow, Mathlib, your own feeds); for a blog, a magazine or a learned society, Madalean keeps to the title, the excerpt and the link. The setting “Summarise automatically” does it for a few new items of your fields at each update. A text that comes from the Internet may contain sentences written to mislead a program. Madalean treats it as a text to read, never as an instruction; when it spots such sentences, it says so and does not send that text to a model. Updates Every 6 hours by default, while the host computer is on and connected to the Internet. “Update” does it at once. A source that does not answer is tried again later, less and less often. In Local mode, Madalean fetches nothing: you read what is already stored. The number of unread items appears on Home (“What's new”) and in the menu. No message ever pops up by itself. Settings › News - the fields followed; - each source, to turn on or off, with its licence and terms; - your own RSS or Atom feeds (an https address of a public site); - the frequency, how long items are kept, automatic summaries, whether the unread number is shown. What leaves your computer Only anonymous reads of the addresses listed in Settings › News: no account, no key, no name, no e-mail address. If you ask for a summary, the item's title and public abstract are sent to the online model, and nothing else. See also Security and privacy. Check it yourself 1. Logo menu › News: the list fills after “Update” (outside Local mode). 2. Tick “Open problems”: only MathOverflow questions and open Erdős problems remain. 3. Switch to Local mode, then “Update”: the button is inactive and the list stays readable.`},{id:`certificates`,lang:`en`,title:`Certificates: Sage computes, Lean checks`,order:207,section:`research`,audience:`researcher`,summary:`For statements that fit, Sage finds a witness and Lean only checks it — no model, no cost, in a few seconds.`,source:`en/certificates.md`,site_path:`en/certificates.html`,headings:[{level:1,text:`Certificates: Sage computes, Lean checks`,id:`certificates-sage-computes-lean-checks`},{level:2,text:`What is covered`,id:`what-is-covered`},{level:2,text:`Where to find them`,id:`where-to-find-them`},{level:2,text:`Limits`,id:`limits`}],images:[],verify:[],body:`# Certificates: Sage computes, Lean checks

A **certificate** is a witness that is easy to check: a factor, an inverse, a sum of squares, a counterexample…
Sage finds it (which can be hard), then Lean **checks** it (which is easy and safe). A wrong witness is rejected by
Lean: a certificate can never turn a mistake into a proof.

## What is covered

| Kind | Example statement | What Lean checks |
|---|---|---|
| Primality | “1,000,003 is prime” | a Pratt certificate |
| Composite | “2³² + 1 is not prime” | a factor |
| Arithmetic | gcd, lcm, divisibility, congruences, factorials | the computation |
| Modular power | “3^1000000 mod 7 = …” | the step-by-step computation |
| Identity | a polynomial equality | \`ring\` |
| Ideal | “f is in the ideal generated by g and h” | the cofactors (Gröbner basis) |
| Linear arithmetic | a system of inequalities with no solution | the Farkas combination |
| Sum of squares | “x² + y² ≥ 2xy” | the sum-of-squares decomposition |
| Existence | “∃ x, 17x ≡ 1 (mod 3120)” | the witness (x = 2753) |
| Counterexample | “n² + n + 41 is prime for every n” | the counterexample (n = 40) |
| Numeric bound | “√2 < 1.415”, bounds on π, e, log 2 | the bounds |
| Finite cases | “for every n ≤ 20, …” | the enumeration |

Lean checks everything in its kernel, without compiled code (\`native_decide\` is never used).

## Where to find them

1. **In a proof** — the « certificate » strategy runs on its own next to the Mathlib search when the statement has a
   recognised shape. The dossier's thread shows “witness computed by Sage, checked by Lean” with the witness. It is
   set in **Settings › Models › Certificates** (on by default).
2. **For the proving models** — they can ask Sage for a witness during their search. They send a statement, never
   code.
3. **In Calcul** — on a cell with a result (factorisation, primality, gcd, modular power, inverse, binomial…), menu
   ⋯ › **Certify with Lean**: Madalean creates a dossier with the statement and its proof.

## Limits

Not yet: graphs as witnesses, integrals and general interval arithmetic, sums of squares beyond 4 variables or
degree 8, abstract structures (arbitrary rings, ∑ sums, complex numbers). Without SageMath installed, only
arithmetic, modular powers, identities, finite cases and small primes work.
`,text:`Certificates: Sage computes, Lean checks A certificate is a witness that is easy to check: a factor, an inverse, a sum of squares, a counterexample… Sage finds it (which can be hard), then Lean checks it (which is easy and safe). A wrong witness is rejected by Lean: a certificate can never turn a mistake into a proof. What is covered Kind Example statement What Lean checks Primality “1,000,003 is prime” a Pratt certificate Composite “2³² + 1 is not prime” a factor Arithmetic gcd, lcm, divisibility, congruences, factorials the computation Modular power “3^1000000 mod 7 = …” the step-by-step computation Identity a polynomial equality ring Ideal “f is in the ideal generated by g and h” the cofactors (Gröbner basis) Linear arithmetic a system of inequalities with no solution the Farkas combination Sum of squares “x² + y² ≥ 2xy” the sum-of-squares decomposition Existence “∃ x, 17x ≡ 1 (mod 3120)” the witness (x = 2753) Counterexample “n² + n + 41 is prime for every n” the counterexample (n = 40) Numeric bound “√2 < 1.415”, bounds on π, e, log 2 the bounds Finite cases “for every n ≤ 20, …” the enumeration Lean checks everything in its kernel, without compiled code (nativedecide is never used). Where to find them 1. In a proof — the « certificate » strategy runs on its own next to the Mathlib search when the statement has a recognised shape. The dossier's thread shows “witness computed by Sage, checked by Lean” with the witness. It is set in Settings › Models › Certificates (on by default). 2. For the proving models — they can ask Sage for a witness during their search. They send a statement, never code. 3. In Calcul — on a cell with a result (factorisation, primality, gcd, modular power, inverse, binomial…), menu ⋯ › Certify with Lean: Madalean creates a dossier with the statement and its proof. Limits Not yet: graphs as witnesses, integrals and general interval arithmetic, sums of squares beyond 4 variables or degree 8, abstract structures (arbitrary rings, ∑ sums, complex numbers). Without SageMath installed, only arithmetic, modular powers, identities, finite cases and small primes work.`},{id:`literature`,lang:`en`,title:`Literature first: published results and attachments`,order:208,section:`research`,audience:`researcher`,summary:`During the proof, Madalean looks for published results related to the statement, quotes them word for word and states them in Lean; a result cited but not proved in Lean never makes a proof « verified ».`,source:`en/literature.md`,site_path:`en/literature.html`,headings:[{level:1,text:`Literature first: published results and attachments`,id:`literature-first-published-results-and-attachments`},{level:2,text:`What you see`,id:`what-you-see`},{level:2,text:`Conditional proof`,id:`conditional-proof`},{level:2,text:`Attachments`,id:`attachments`},{level:2,text:`Settings and privacy`,id:`settings-and-privacy`}],images:[],verify:[],body:`# Literature first: published results and attachments

When the proof of a statement starts, Madalean searches the scholarly databases, in parallel, for related published
results: **zbMATH Open** (reviewed literature, with its reviews), **OpenAlex**, **arXiv**, and your **Sources**. The
search never delays the proof.

## What you see

In the **Proof** step, the **Literature** panel:

- every **reference** comes from a scholarly database (never from a model); a badge says whether it is **published in
  a journal (peer reviewed)** or a **preprint (not reviewed)**;
- the **statement quoted word for word**, with its place (“abstract, sentence 2”, “zbMATH review”, “Theorem 2.1,
  p. 5”);
- its **Lean statement** when a model could translate it (read it again) and its status: **In Mathlib**, **Proved in
  Lean**, **To prove (conditional)** or **No Lean statement**;
- the buttons **Add to Sources**, **Add to the article’s bibliography**, **Prove this lemma**, and the BibTeX record.

When nothing reliable is found, it says so: Madalean never invents a reference or a quotation.

## Conditional proof

When a cited result lets Lean conclude but is not proved in Lean, Madalean says so: **“Conditional proof — not
verified”**, with the reference it rests on. It enters neither the dossier’s proofs nor the library, and the export
spells it out. Click **Prove this lemma**: once Lean accepts the proof of the cited result, the proof is checked again
strictly and becomes **verified**.

## Attachments

The paperclip of the dossier’s thread (and the **Literature** panel) attaches an **image**, a **PDF**, a **LaTeX** or
**BibTeX** file, or a **web address**. The attachment becomes a Source of the project and is **read only once**:
Madalean keeps a digest (the reference, the statements quoted word for word, their Lean statement). Attaching the same
file in another dossier of the project does not read it again. An image is read by a model that can read images
(otherwise it stays “not read”); its transcription is marked as such and the original stays in Sources. **Read again**
reads it again when you ask.

In the thread you can write, for example, “from attachment 2, lemma 3.1, conclude”: Madalean quotes that lemma as
written in the attachment.

In **Calcul**, a “Request” cell has a paperclip too: the file joins the project's Sources (read once, as above) and
the cell shows its attachments. A request such as “according to attachment 1, lemma 1, check p = 7” sends the exact
quote to the model (never the whole document); the code written still needs your approval before it runs.

## Settings and privacy

**Settings › Models › Advanced options**: “Search the literature” (on by default) and its depth (quick ≈ 45 s,
thorough ≈ 2 min 30). In **local mode**, no search is sent over the network: only your Sources and Mathlib are used.
What leaves the computer: the search words drawn from the statement and the identifiers (DOI, arXiv) to check; never
your Lean file, your notes, a key or your name.
`,text:`Literature first: published results and attachments When the proof of a statement starts, Madalean searches the scholarly databases, in parallel, for related published results: zbMATH Open (reviewed literature, with its reviews), OpenAlex, arXiv, and your Sources. The search never delays the proof. What you see In the Proof step, the Literature panel: - every reference comes from a scholarly database (never from a model); a badge says whether it is published in a journal (peer reviewed) or a preprint (not reviewed); - the statement quoted word for word, with its place (“abstract, sentence 2”, “zbMATH review”, “Theorem 2.1, p. 5”); - its Lean statement when a model could translate it (read it again) and its status: In Mathlib, Proved in Lean, To prove (conditional) or No Lean statement; - the buttons Add to Sources, Add to the article’s bibliography, Prove this lemma, and the BibTeX record. When nothing reliable is found, it says so: Madalean never invents a reference or a quotation. Conditional proof When a cited result lets Lean conclude but is not proved in Lean, Madalean says so: “Conditional proof — not verified”, with the reference it rests on. It enters neither the dossier’s proofs nor the library, and the export spells it out. Click Prove this lemma: once Lean accepts the proof of the cited result, the proof is checked again strictly and becomes verified. Attachments The paperclip of the dossier’s thread (and the Literature panel) attaches an image, a PDF, a LaTeX or BibTeX file, or a web address. The attachment becomes a Source of the project and is read only once: Madalean keeps a digest (the reference, the statements quoted word for word, their Lean statement). Attaching the same file in another dossier of the project does not read it again. An image is read by a model that can read images (otherwise it stays “not read”); its transcription is marked as such and the original stays in Sources. Read again reads it again when you ask. In the thread you can write, for example, “from attachment 2, lemma 3.1, conclude”: Madalean quotes that lemma as written in the attachment. In Calcul, a “Request” cell has a paperclip too: the file joins the project's Sources (read once, as above) and the cell shows its attachments. A request such as “according to attachment 1, lemma 1, check p = 7” sends the exact quote to the model (never the whole document); the code written still needs your approval before it runs. Settings and privacy Settings › Models › Advanced options: “Search the literature” (on by default) and its depth (quick ≈ 45 s, thorough ≈ 2 min 30). In local mode, no search is sent over the network: only your Sources and Mathlib are used. What leaves the computer: the search words drawn from the statement and the identifiers (DOI, arXiv) to check; never your Lean file, your notes, a key or your name.`},{id:`sources`,lang:`en`,title:`Sources, literature search and grounded questions`,order:210,section:`research`,audience:`researcher`,summary:`The sources library (papers, books), searching the databases, the annotated reader, and answers that cite your sources.`,source:`en/sources.md`,site_path:`en/sources.html`,headings:[{level:1,text:`Sources, literature search and grounded questions`,id:`sources-literature-search-and-grounded-questions`},{level:2,text:`The sources library`,id:`the-sources-library`},{level:2,text:`Literature search`,id:`literature-search`},{level:2,text:`Reading and annotating`,id:`reading-and-annotating`},{level:2,text:`Questions grounded in your sources`,id:`questions-grounded-in-your-sources`},{level:2,text:`What goes over the Internet`,id:`what-goes-over-the-internet`}],images:[],verify:[],body:`# Sources, literature search and grounded questions

## The sources library

The project's “Sources” screen has three tabs: “Library”, “Literature search” and “Ask a question”. Papers, books,
lecture notes are arranged there on **shelves**: one per project, a general shelf, and the *Mathlib* shelf
(read-only, taken from Mathlib's bibliography). To add a source, “Add” offers three ways: “Identifier”, “File”,
“Paste”.

| By | What Madalean does |
|---|---|
| “Identifier”: DOI, arXiv identifier, ISBN, \`Zbl …\`, OpenAlex identifier | fetches verified metadata; for arXiv, also the TeX sources and the PDF; for a DOI, the PDF only if it is open access |
| “Identifier”: web address | metadata of the page only |
| “File”: PDF, TeX source (\`.tex\`, \`.tar.gz\`, \`.zip\`) | looks for an identifier in the first pages; otherwise guessed metadata, marked **unverified** |
| “File” or “Paste”: BibTeX, RIS, CSL-JSON, Zotero export (RDF, or \`.zip\` with the attached files) | imports the references and the files attached in the archive |

Duplicates (same DOI, same arXiv id, same title) are flagged. Each source has tags, a reading status, annotations,
and its BibTeX key. The “BibTeX” button exports the shelf.

Metadata guessed from a file stays marked “metadata to check” until you confirm it (“They are right” in the
reader).

## Literature search

The “Literature search” tab queries arXiv, zbMATH Open, Crossref, OpenAlex and Semantic Scholar and merges the
results. **Only your query is sent.** A service that does not answer is marked “unavailable”, without blocking the
others. “Add” puts a result in your sources.

In *Local* mode these searches are refused: they need the network.

## Reading and annotating

The reader shows the PDF next to the extracted text. “Highlight” a passage, add a “Margin note”: annotations are
anchored to the page and position, and can be found by search.

The full text of each source is indexed **locally**, split into passages with their page and section. For a PDF
without a text layer (scan), character recognition exists, but formulas read this way are not reliable.

## Questions grounded in your sources

Ask a question (“Ask a question” tab, or “Questions about this text” in the reader): the answer cites precise
**passages**.

- Each citation leads to the passage (click: the page opens at the right place).
- The citation is checked by code: the cited passage must contain the quoted text. A sentence without a valid
  citation is shown struck through or greyed.
- If no relevant passage is found, the answer says so, **without calling a model**.
- An optional “general knowledge” part (“Add general knowledge (marked)”) is kept separate and marked as such,
  without citations.

What the check guarantees: the cited passage exists and contains the quotation. What it does not guarantee: that the
passage *justifies* the sentence. Read the passage for the important points.

Other requests: “Summarise” (what the paper proves, its definitions, its dependencies) and “Compare” several
sources (“Compare with…” in the reader).

## What goes over the Internet

Search queries, identifiers (DOI, arXiv…) and the download of open-access files. Questions about your sources go
through the chosen model, with the retained passages: in *Local* mode, only through a local model. See
[Models and keys](models-keys.md#what-is-sent-and-to-whom).
`,text:`Sources, literature search and grounded questions The sources library The project's “Sources” screen has three tabs: “Library”, “Literature search” and “Ask a question”. Papers, books, lecture notes are arranged there on shelves: one per project, a general shelf, and the Mathlib shelf (read-only, taken from Mathlib's bibliography). To add a source, “Add” offers three ways: “Identifier”, “File”, “Paste”. By What Madalean does “Identifier”: DOI, arXiv identifier, ISBN, Zbl …, OpenAlex identifier fetches verified metadata; for arXiv, also the TeX sources and the PDF; for a DOI, the PDF only if it is open access “Identifier”: web address metadata of the page only “File”: PDF, TeX source (.tex, .tar.gz, .zip) looks for an identifier in the first pages; otherwise guessed metadata, marked unverified “File” or “Paste”: BibTeX, RIS, CSL-JSON, Zotero export (RDF, or .zip with the attached files) imports the references and the files attached in the archive Duplicates (same DOI, same arXiv id, same title) are flagged. Each source has tags, a reading status, annotations, and its BibTeX key. The “BibTeX” button exports the shelf. Metadata guessed from a file stays marked “metadata to check” until you confirm it (“They are right” in the reader). Literature search The “Literature search” tab queries arXiv, zbMATH Open, Crossref, OpenAlex and Semantic Scholar and merges the results. Only your query is sent. A service that does not answer is marked “unavailable”, without blocking the others. “Add” puts a result in your sources. In Local mode these searches are refused: they need the network. Reading and annotating The reader shows the PDF next to the extracted text. “Highlight” a passage, add a “Margin note”: annotations are anchored to the page and position, and can be found by search. The full text of each source is indexed locally, split into passages with their page and section. For a PDF without a text layer (scan), character recognition exists, but formulas read this way are not reliable. Questions grounded in your sources Ask a question (“Ask a question” tab, or “Questions about this text” in the reader): the answer cites precise passages. - Each citation leads to the passage (click: the page opens at the right place). - The citation is checked by code: the cited passage must contain the quoted text. A sentence without a valid citation is shown struck through or greyed. - If no relevant passage is found, the answer says so, without calling a model. - An optional “general knowledge” part (“Add general knowledge (marked)”) is kept separate and marked as such, without citations. What the check guarantees: the cited passage exists and contains the quotation. What it does not guarantee: that the passage justifies the sentence. Read the passage for the important points. Other requests: “Summarise” (what the paper proves, its definitions, its dependencies) and “Compare” several sources (“Compare with…” in the reader). What goes over the Internet Search queries, identifiers (DOI, arXiv…) and the download of open-access files. Questions about your sources go through the chosen model, with the retained passages: in Local mode, only through a local model. See Models and keys.`},{id:`articles`,lang:`en`,title:`Bibliography, article and blueprint`,order:220,section:`research`,audience:`researcher`,summary:`Citing in proofs, writing an article from a project, turning a paper into a blueprint of Lean dossiers, and what is reliable.`,source:`en/articles.md`,site_path:`en/articles.html`,headings:[{level:1,text:`Bibliography, article and blueprint`,id:`bibliography-article-and-blueprint`},{level:2,text:`What is reliable, and what is not`,id:`what-is-reliable-and-what-is-not`},{level:2,text:`Citing`,id:`citing`},{level:2,text:`Writing the article`,id:`writing-the-article`},{level:2,text:`From a paper to a blueprint`,id:`from-a-paper-to-a-blueprint`},{level:2,text:`From the blueprint to a formal plan`,id:`from-the-blueprint-to-a-formal-plan`},{level:2,text:`Publishing`,id:`publishing`}],images:[],verify:[],body:`# Bibliography, article and blueprint

## What is reliable, and what is not

| Feature | Reliability | How |
|---|---|---|
| Bibliography in proofs and exports | High | One BibTeX file per project. Add by DOI, arXiv, zbMATH, pasted BibTeX, or from Mathlib's bibliography. A model may only cite existing keys: an invented reference is removed by code, never printed. |
| Lean → article | High for the structure, model-dependent for the prose | Project → LaTeX article (amsart): abstract, sections, each dossier as theorem + written proof, optional Lean appendix, bibliography, verification table. An unproved statement is typeset as a conjecture or claim, marked — never as a theorem. |
| Paper → structured statements | High from LaTeX sources (arXiv), medium from a PDF | arXiv sources first; a PDF through its text layer, and a model that reads PDFs when a key allows it; formulas from a scanned PDF are not reliable without review. Result: a **blueprint**, one dossier per definition, lemma or theorem, with the original text, its place in the paper and its dependencies. |
| Paper → Lean statements | Medium (textbook, graduate level), low (research level with objects absent from Mathlib) | Each node goes through understanding → translation with lemma retrieval; missing definitions are detected and become nodes “to define”. Always reviewed by you: the paper's text is shown next to the Lean statement. |
| Paper → Lean proofs | Low to medium | The paper's proof is given to the prover as a hint. Elementary lemmas are often proved, deep results rarely. The graph shows honestly what is proved, only stated, or blocked. |

**No result is presented as verified unless Lean accepted its proof and the proofs of all its dependencies.**

## Citing

In any text (statement, written proof, explanation, note, article section), a citation uses the BibTeX key:
\`[@hardy-wright]\`, \`[@hardy-wright, Thm 2.1]\`, \`[see @a, p. 3; @b]\`. Autocompletion offers the project's keys. Exports
print only the cited references: PDF with biblatex and biber if installed, otherwise BibTeX; the \`.zip\` contains
\`refs.bib\`.

## Writing the article

The project's “Article” screen is a visual LaTeX editor: the text you see *is* the LaTeX source (rendered
formulas, theorem boxes, citations, figures), and “LaTeX source” shows the same text raw. On first opening,
Madalean prepares the article from the project: an introduction and one block per dossier. The outline is on the
left, the “PDF preview” on the right on a wide screen; “Compile” produces the PDF. The assistant (“Rewrite”,
“Shorten”, “Make more formal”…) only makes suggestions, which you accept or reject in the text.

When compiling, Madalean adds the bibliography (only the cited references), the **Lean verification table** (for
each result: Lean name, verified or not, Lean and Mathlib versions, axioms) and, if you ask for it in “Advanced
options”, an appendix with the Lean code. A theorem linked to a dossier whose proof is not verified by Lean is
printed as a claim, never as a theorem.

Under “More actions”: “Versions” (an automatic version at most every 2 minutes of writing, plus your own),
“Download the PDF”, and “Overleaf…” to send the project to Overleaf (or download the project as a \`.zip\`) and take
it back.

## From a paper to a blueprint

1. Add the paper to your sources (preferably by its arXiv identifier: the LaTeX sources give a much better result
   than the PDF).
2. In the source's reader, “Extract the blueprint”: definitions, lemmas, theorems, with their number (“Lemma 2.3”), text, proof, and the
   dependencies found in the proofs (\`\\ref\`, “by Lemma 2.3”).
3. Dependencies written in prose (“by the previous lemma”) often escape extraction: an optional model pass
   proposes links marked **“proposed (to confirm)”**, which you confirm (“Confirm”) or set aside
   (“Discard”).
4. “Create the dossiers”: each node becomes a dossier linked to the source and to its location in the paper.
5. The “Blueprint” screen colours each result by its state: no dossier, stated in words, Lean statement accepted,
   defined, proved (dependencies not verified), verified (proved and all its dependencies verified), blocked (uses
   a definition without an accepted Lean statement), failed. “Open the dossier” opens the dossier.

Honest measurement (three short arXiv papers, checked by hand): statements found 12 of 12 from the TeX and from the
PDF; proofs 10 of 11 from the TeX, 8 of 11 from the PDF; dependencies written in prose: 2 of 7 without a model pass.
These figures come from a small sample.

## From the blueprint to a formal plan

The “Formal plan” tab of the “Blueprint” screen turns the paper into a plan of Lean work, progressively:

1. Tick the theorems you want (the main result, for instance). The button shows how many statements their
   **dependency closure** holds: everything they use according to the paper's explicit references (\`\\ref\`,
   “Proof of Theorem 3”, “by Lemma 2.3” in a PDF), and the links proposed by a model only once you confirmed them.
   An unknown dependency stays unknown: nothing is invented.
2. “Formalise the selection and its dependencies”: dependencies first, each statement **quoted verbatim** from the
   paper (with the definitions it uses) goes to the formalizer; Lean checks the statement; then Madalean looks
   whether Mathlib (or your library) already proves it. A run stops after the chosen number of statements
   (“Statements per run”) or when you press “Stop”; start it again to **resume** where it stopped.
3. When the whole closure is processed, Madalean opens a dossier for the main theorem and, in its problem graph, one
   node per result it uses: those in Mathlib are verified, the others are **conditional** (the paper claims them,
   Lean has not proved them) and each one to prove becomes a **sub-dossier**. Nothing is started: you launch the
   provers from the dossiers.

Each result shows one state: *proved (Lean)*, *in Mathlib*, *to prove*, *statement formalised*, *not formalised*;
“Conditional: rests on …” lists what is not proved yet. The counter gives the proved or in-Mathlib results of the
plan. Clicking a result shows its text from the paper (verbatim, with its place: number, section, line or page)
beside the Lean statement — a model's translation accepted by Lean, to be re-read. “Export (LaTeX)” writes a
blueprint in the style of \`leanblueprint\` (\`\\lean\`, \`\\leanok\`, \`\\mathlibok\`, \`\\uses\`), “Export (HTML)” a summary
page. Definitions are not formalised yet.

## Publishing

A project can be published as a static site that anyone can verify: see [Publishing a project](publish.md).
`,text:`Bibliography, article and blueprint What is reliable, and what is not Feature Reliability How Bibliography in proofs and exports High One BibTeX file per project. Add by DOI, arXiv, zbMATH, pasted BibTeX, or from Mathlib's bibliography. A model may only cite existing keys: an invented reference is removed by code, never printed. Lean → article High for the structure, model-dependent for the prose Project → LaTeX article (amsart): abstract, sections, each dossier as theorem + written proof, optional Lean appendix, bibliography, verification table. An unproved statement is typeset as a conjecture or claim, marked — never as a theorem. Paper → structured statements High from LaTeX sources (arXiv), medium from a PDF arXiv sources first; a PDF through its text layer, and a model that reads PDFs when a key allows it; formulas from a scanned PDF are not reliable without review. Result: a blueprint, one dossier per definition, lemma or theorem, with the original text, its place in the paper and its dependencies. Paper → Lean statements Medium (textbook, graduate level), low (research level with objects absent from Mathlib) Each node goes through understanding → translation with lemma retrieval; missing definitions are detected and become nodes “to define”. Always reviewed by you: the paper's text is shown next to the Lean statement. Paper → Lean proofs Low to medium The paper's proof is given to the prover as a hint. Elementary lemmas are often proved, deep results rarely. The graph shows honestly what is proved, only stated, or blocked. No result is presented as verified unless Lean accepted its proof and the proofs of all its dependencies. Citing In any text (statement, written proof, explanation, note, article section), a citation uses the BibTeX key: [@hardy-wright], [@hardy-wright, Thm 2.1], [see @a, p. 3; @b]. Autocompletion offers the project's keys. Exports print only the cited references: PDF with biblatex and biber if installed, otherwise BibTeX; the .zip contains refs.bib. Writing the article The project's “Article” screen is a visual LaTeX editor: the text you see is the LaTeX source (rendered formulas, theorem boxes, citations, figures), and “LaTeX source” shows the same text raw. On first opening, Madalean prepares the article from the project: an introduction and one block per dossier. The outline is on the left, the “PDF preview” on the right on a wide screen; “Compile” produces the PDF. The assistant (“Rewrite”, “Shorten”, “Make more formal”…) only makes suggestions, which you accept or reject in the text. When compiling, Madalean adds the bibliography (only the cited references), the Lean verification table (for each result: Lean name, verified or not, Lean and Mathlib versions, axioms) and, if you ask for it in “Advanced options”, an appendix with the Lean code. A theorem linked to a dossier whose proof is not verified by Lean is printed as a claim, never as a theorem. Under “More actions”: “Versions” (an automatic version at most every 2 minutes of writing, plus your own), “Download the PDF”, and “Overleaf…” to send the project to Overleaf (or download the project as a .zip) and take it back. From a paper to a blueprint 1. Add the paper to your sources (preferably by its arXiv identifier: the LaTeX sources give a much better result than the PDF). 2. In the source's reader, “Extract the blueprint”: definitions, lemmas, theorems, with their number (“Lemma 2.3”), text, proof, and the dependencies found in the proofs (\\ref, “by Lemma 2.3”). 3. Dependencies written in prose (“by the previous lemma”) often escape extraction: an optional model pass proposes links marked “proposed (to confirm)”, which you confirm (“Confirm”) or set aside (“Discard”). 4. “Create the dossiers”: each node becomes a dossier linked to the source and to its location in the paper. 5. The “Blueprint” screen colours each result by its state: no dossier, stated in words, Lean statement accepted, defined, proved (dependencies not verified), verified (proved and all its dependencies verified), blocked (uses a definition without an accepted Lean statement), failed. “Open the dossier” opens the dossier. Honest measurement (three short arXiv papers, checked by hand): statements found 12 of 12 from the TeX and from the PDF; proofs 10 of 11 from the TeX, 8 of 11 from the PDF; dependencies written in prose: 2 of 7 without a model pass. These figures come from a small sample. From the blueprint to a formal plan The “Formal plan” tab of the “Blueprint” screen turns the paper into a plan of Lean work, progressively: 1. Tick the theorems you want (the main result, for instance). The button shows how many statements their dependency closure holds: everything they use according to the paper's explicit references (\\ref, “Proof of Theorem 3”, “by Lemma 2.3” in a PDF), and the links proposed by a model only once you confirmed them. An unknown dependency stays unknown: nothing is invented. 2. “Formalise the selection and its dependencies”: dependencies first, each statement quoted verbatim from the paper (with the definitions it uses) goes to the formalizer; Lean checks the statement; then Madalean looks whether Mathlib (or your library) already proves it. A run stops after the chosen number of statements (“Statements per run”) or when you press “Stop”; start it again to resume where it stopped. 3. When the whole closure is processed, Madalean opens a dossier for the main theorem and, in its problem graph, one node per result it uses: those in Mathlib are verified, the others are conditional (the paper claims them, Lean has not proved them) and each one to prove becomes a sub-dossier. Nothing is started: you launch the provers from the dossiers. Each result shows one state: proved (Lean), in Mathlib, to prove, statement formalised, not formalised; “Conditional: rests on …” lists what is not proved yet. The counter gives the proved or in-Mathlib results of the plan. Clicking a result shows its text from the paper (verbatim, with its place: number, section, line or page) beside the Lean statement — a model's translation accepted by Lean, to be re-read. “Export (LaTeX)” writes a blueprint in the style of leanblueprint (\\lean, \\leanok, \\mathlibok, \\uses), “Export (HTML)” a summary page. Definitions are not formalised yet. Publishing A project can be published as a static site that anyone can verify: see Publishing a project.`},{id:`notes`,lang:`en`,title:`Notes`,order:230,section:`research`,audience:`all`,summary:`Linked notes in Markdown, LaTeX and Lean; links, backlinks, graph, versions and editing on several devices.`,source:`en/notes.md`,site_path:`en/notes.html`,headings:[{level:1,text:`Notes`,id:`notes`},{level:2,text:`Links`,id:`links`},{level:2,text:`Lean in notes`,id:`lean-in-notes`},{level:2,text:`Research log`,id:`research-log`},{level:2,text:`Versions and several devices`,id:`versions-and-several-devices`},{level:2,text:`Export`,id:`export`}],images:[],verify:[],body:`# Notes

Notes belong to Madalean (this is not an Obsidian vault) and are filed by project. They are written in Markdown,
with \`$…$\` and \`$$…$$\` formulas and Lean code blocks.

## Links

| Syntax | Target |
|---|---|
| \`[[Title]]\`, \`[[Title\\|displayed text]]\` | a note of the same project (title, case-insensitive) |
| \`[[dossier:Title]]\` or \`[[dossier:ID]]\` | a dossier (theorem, conjecture, lemma…) |
| \`[[@key]]\`, \`[[@key#p12]]\` | a source, optionally at a page |
| \`[[passage:ID]]\` | a specific passage of a source |
| \`[[lib:Name]]\` | a library result (Lean name) |

Each note shows its **backlinks** (the notes pointing to it). The project's **graph** (“Graph” button)
connects notes, dossiers and sources; it can be filtered by tag. Tags are written \`#tag\` in the text.

Renaming a note updates the \`[[Old title]]\` links in the project's other notes.

## Lean in notes

Below the editor, the “Lean blocks” part lists every \`lean\` block of the note. “Check all with Lean” compiles them
all in the project's workspace (“Check with Lean” on one block checks only that one); each block shows “Lean
accepts” or “Lean rejects”, with the errors at the right line. “Make it a dossier” opens a dossier with the block's
statement and adds a link to it below the block.

## Research log

“Today’s note” creates (or opens) the “research log” note dated today, with the list of dossiers worked on that
day.

## Versions and several devices

Every save creates a revision; all are kept. Two revisions can be compared and an old one restored (which creates a
new revision: nothing is lost). A deleted note goes to the trash.

If the same note is edited on two devices, changes to different lines are merged automatically. If both devices
changed the same lines, Madalean shows both versions of each conflicting passage and you choose.

## Export

The “.md” button of the editor downloads the note as Markdown.
`,text:`Notes Notes belong to Madalean (this is not an Obsidian vault) and are filed by project. They are written in Markdown, with $…$ and $$…$$ formulas and Lean code blocks. Links Syntax Target [[Title]], [[Title displayed text]] a note of the same project (title, case-insensitive) [[dossier:Title]] or [[dossier:ID]] a dossier (theorem, conjecture, lemma…) [[@key]], [[@key#p12]] a source, optionally at a page [[passage:ID]] a specific passage of a source [[lib:Name]] a library result (Lean name) Each note shows its backlinks (the notes pointing to it). The project's graph (“Graph” button) connects notes, dossiers and sources; it can be filtered by tag. Tags are written #tag in the text. Renaming a note updates the [[Old title]] links in the project's other notes. Lean in notes Below the editor, the “Lean blocks” part lists every lean block of the note. “Check all with Lean” compiles them all in the project's workspace (“Check with Lean” on one block checks only that one); each block shows “Lean accepts” or “Lean rejects”, with the errors at the right line. “Make it a dossier” opens a dossier with the block's statement and adds a link to it below the block. Research log “Today’s note” creates (or opens) the “research log” note dated today, with the list of dossiers worked on that day. Versions and several devices Every save creates a revision; all are kept. Two revisions can be compared and an old one restored (which creates a new revision: nothing is lost). A deleted note goes to the trash. If the same note is edited on two devices, changes to different lines are merged automatically. If both devices changed the same lines, Madalean shows both versions of each conflicting passage and you choose. Export The “.md” button of the editor downloads the note as Markdown.`},{id:`jupyter`,lang:`en`,title:`Jupyter and Sage`,order:240,section:`research`,audience:`researcher`,summary:`Built-in JupyterLab with the Python and SageMath kernels, the assistant next to the notebook, and who can access it.`,source:`en/jupyter.md`,site_path:`en/jupyter.html`,headings:[{level:1,text:`Jupyter and Sage`,id:`jupyter-and-sage`},{level:2,text:`Kernels`,id:`kernels`},{level:2,text:`The assistant next to the notebook`,id:`the-assistant-next-to-the-notebook`},{level:2,text:`Who can access it`,id:`who-can-access-it`}],images:[],verify:[],body:`# Jupyter and Sage

The “Notebook” screen opens **JupyterLab**, started on demand by the host computer, behind the same connection as
the rest of Madalean. Notebooks are stored in \`~/Documents/Madalean/notebooks/\`.

## Kernels

| Kernel | Available if |
|---|---|
| Python 3 | always (with JupyterLab) |
| SageMath | Madalean's copy is installed, or the system's SageMath is compatible |
| Lean 4 | not provided: no Lean 4 kernel is reliable enough today. Use dossiers or the \`lean\` blocks of [notes](notes.md). |

Madalean installs its own copy of SageMath on demand, or reuses your system's if it is compatible: see
[What Madalean installs › SageMath](components.md#sagemath).

## The assistant next to the notebook

The assistant panel reads the open notebook (cells and outputs) and can **append a cell** at the end, which you run
yourself. It answers with the model of the current mode; in *Local* mode, only a local model.

## Who can access it

A Jupyter kernel runs arbitrary code on the host computer. Therefore:

- on the host, the notebook is always available;
- from a linked device, it is reachable only if the host allowed it (“Settings › Notebook and access”), a setting
  that can be changed **only from the host**;
- Jupyter's internal token never leaves the server.

The experiments of the [conjecture workshop](conjectures.md) use separate, confined kernels, and run only after your
approval.
`,text:`Jupyter and Sage The “Notebook” screen opens JupyterLab, started on demand by the host computer, behind the same connection as the rest of Madalean. Notebooks are stored in ~/Documents/Madalean/notebooks/. Kernels Kernel Available if Python 3 always (with JupyterLab) SageMath Madalean's copy is installed, or the system's SageMath is compatible Lean 4 not provided: no Lean 4 kernel is reliable enough today. Use dossiers or the lean blocks of notes. Madalean installs its own copy of SageMath on demand, or reuses your system's if it is compatible: see What Madalean installs › SageMath. The assistant next to the notebook The assistant panel reads the open notebook (cells and outputs) and can append a cell at the end, which you run yourself. It answers with the model of the current mode; in Local mode, only a local model. Who can access it A Jupyter kernel runs arbitrary code on the host computer. Therefore: - on the host, the notebook is always available; - from a linked device, it is reachable only if the host allowed it (“Settings › Notebook and access”), a setting that can be changed only from the host; - Jupyter's internal token never leaves the server. The experiments of the conjecture workshop use separate, confined kernels, and run only after your approval.`},{id:`publish`,lang:`en`,title:`Publishing a project`,order:250,section:`research`,audience:`researcher`,summary:`Publish a verified project as a static site on a GitHub repository of your choice, independently re-verified by lake build.`,source:`en/publish.md`,site_path:`en/publish.html`,headings:[{level:1,text:`Publishing a project`,id:`publishing-a-project`},{level:2,text:`What leaves, and only with your consent`,id:`what-leaves-and-only-with-your-consent`},{level:2,text:`What the site shows`,id:`what-the-site-shows`}],images:[],verify:[],body:`# Publishing a project

The “Publish” screen (project menu) turns a project into a **static site** that anyone can read and re-verify:

- the article (HTML, and the PDF if you attach it);
- the **dependency graph**, with the state of each result;
- one page per result: natural-language statement, coloured Lean code, written proof, verification information
  (Lean version, Mathlib revision, axioms);
- the verification table and the bibliography;
- the complete **Lean (Lake) project** to download, and, if you ask for it, your computations (Calcul).

A published result takes along everything it depends on: a result is never shown without what it relies on.

The site is sent to a GitHub repository **that you choose**, with a GitHub action that runs \`lake build\` again on the
published Lean project. The verification badge shown by the site comes from that action, independent of your
computer: a reader does not have to take Madalean's word for it.

## What leaves, and only with your consent

1. **“What you publish”**: tick the results, the notes (none by default), “Attach the paper’s PDF”, “Include the
   computations (Calcul)”, and choose the site licence.
2. **“Prepare the exact list”**: nothing is sent at this step. The screen lists **exactly** what will leave the
   computer (“What will leave this computer”): each file, its type, its origin and its size, what is excluded, and
   what is never published (your keys, your private notes, the PDFs of other authors' papers, your settings).
3. **“Local preview”** builds the site on the computer; “Open the preview” shows it before anything is published.
4. **“Send to GitHub”**: give the repository (\`account/name\`), tick if needed “Create the repository if it does not
   exist” (and “Private repository”), then “Publish” and confirm with “Yes, publish”. A GitHub key (token) is needed,
   saved in the key settings (the screen links to them); otherwise, the login of the \`gh\` tool, if it is installed on
   the host, is used. Madalean then turns on the repository's GitHub Pages site; if it cannot, it gives the link to
   turn it on by hand.

Publishing is started from the host computer. If the list changes between its preparation and the sending, Madalean
asks you to prepare it again. A new publication adds a commit to the repository; nothing is sent if nothing changed.

## What the site shows

Each state has a colour, a border style and a written label (never colour alone):

| Mark | Label on the site |
|---|---|
| ✓ | verified by Lean (proof accepted by Lean, and all its dependencies verified) |
| (✓) | proved, dependencies not verified |
| ≔ | definition accepted by Lean |
| ◇ | Lean statement accepted, no proof |
| … | natural-language statement only |
| ✕ | blocked: uses a definition not formalised |

An unverified theorem is never presented as a theorem: it is titled “Claim”, with a warning. The site uses no
tracker, no external font or script.
`,text:`Publishing a project The “Publish” screen (project menu) turns a project into a static site that anyone can read and re-verify: - the article (HTML, and the PDF if you attach it); - the dependency graph, with the state of each result; - one page per result: natural-language statement, coloured Lean code, written proof, verification information (Lean version, Mathlib revision, axioms); - the verification table and the bibliography; - the complete Lean (Lake) project to download, and, if you ask for it, your computations (Calcul). A published result takes along everything it depends on: a result is never shown without what it relies on. The site is sent to a GitHub repository that you choose, with a GitHub action that runs lake build again on the published Lean project. The verification badge shown by the site comes from that action, independent of your computer: a reader does not have to take Madalean's word for it. What leaves, and only with your consent 1. “What you publish”: tick the results, the notes (none by default), “Attach the paper’s PDF”, “Include the computations (Calcul)”, and choose the site licence. 2. “Prepare the exact list”: nothing is sent at this step. The screen lists exactly what will leave the computer (“What will leave this computer”): each file, its type, its origin and its size, what is excluded, and what is never published (your keys, your private notes, the PDFs of other authors' papers, your settings). 3. “Local preview” builds the site on the computer; “Open the preview” shows it before anything is published. 4. “Send to GitHub”: give the repository (account/name), tick if needed “Create the repository if it does not exist” (and “Private repository”), then “Publish” and confirm with “Yes, publish”. A GitHub key (token) is needed, saved in the key settings (the screen links to them); otherwise, the login of the gh tool, if it is installed on the host, is used. Madalean then turns on the repository's GitHub Pages site; if it cannot, it gives the link to turn it on by hand. Publishing is started from the host computer. If the list changes between its preparation and the sending, Madalean asks you to prepare it again. A new publication adds a commit to the repository; nothing is sent if nothing changed. What the site shows Each state has a colour, a border style and a written label (never colour alone): Mark Label on the site ✓ verified by Lean (proof accepted by Lean, and all its dependencies verified) (✓) proved, dependencies not verified ≔ definition accepted by Lean ◇ Lean statement accepted, no proof … natural-language statement only ✕ blocked: uses a definition not formalised An unverified theorem is never presented as a theorem: it is titled “Claim”, with a warning. The site uses no tracker, no external font or script.`},{id:`mathlib-contrib`,lang:`en`,title:`Contributing to Mathlib`,order:255,section:`research`,audience:`researcher`,summary:`From a verified result to a proposed addition to Mathlib — checked with current Mathlib, named, checked against the style rules, reviewed by you; nothing is sent without two clicks from you.`,source:`en/mathlib-contrib.md`,site_path:`en/mathlib-contrib.html`,headings:[{level:1,text:`Contributing to Mathlib`,id:`contributing-to-mathlib`},{level:2,text:`Where the button is`,id:`where-the-button-is`},{level:2,text:`The steps`,id:`the-steps`},{level:2,text:`The checklist`,id:`the-checklist`},{level:2,text:`Sending`,id:`sending`}],images:[],verify:[],body:`# Contributing to Mathlib

Mathlib is Lean's large library of mathematics. When one of your results
is missing from it, Madalean prepares what is needed to propose it: the file, the name, the checklist, the text of
the request. **You review everything**; nothing leaves without you.

## Where the button is

- in the **Library**: open a verified result, then “Prepare for Mathlib”;
- in a **dossier**: below the verified proof, “Prepare for Mathlib”.

Give your name (it goes at the top of the file, as Mathlib requires), then “Start the preparation”.

## The steps

1. **Check with current Mathlib.** Mathlib only accepts up-to-date code. When the proof was found with the prover's
   Lean (Lean 4.9), Madalean first replaces the names that changed since (those Lean reports as deprecated, those
   learned from your proofs, a small checked table) and has Lean 4.36 check it again. When that is not enough,
   “Restart the proof in current Lean” opens a new dossier, with the old proof as a hint.
2. **Look for it in Mathlib.** When a Mathlib lemma gives the result directly, Madalean says so, with its name, and
   stops: no duplicate contribution.
3. **Propose a name.** Mathlib names a theorem after its statement, read from left to right: \`a + b ≤ c\` gives
   \`add_le\`, \`0 ≤ x\` gives \`x_nonneg\`, a hypothesis adds \`_of_…\`. Madalean explains every word of the name and
   checks that it is free.
4. **Reduce the imports.** Instead of all of Mathlib, only the files needed — then Lean checks again.
5. **Check the final file** and run Mathlib's **style checks** (\`#lint\` and its automatic checks).

## The checklist

Each rule is marked *good*, *to review*, *blocking* or *not checked*: copyright header, file overview, an
explanatory sentence for each theorem, lines of at most 100 characters, no \`sorry\`, no raised time limit, \`simp\`
only at the end of a proof, ≤ rather than ≥, variables deduced from the hypotheses in braces, no deprecated name,
a free name, reduced imports. The explanatory sentence is written automatically from the statement: reread it.

## Sending

- **Copy** or **Download the file**: always possible, nothing leaves the computer.
- **Create a branch on my fork…**: only with a GitHub key saved in Settings → Keys, and from the host computer.
  Madalean first shows **exactly** what will be sent (each request, the content of the file); nothing leaves before
  “Confirm”.
- **Open the PR…**: a second, separate confirmation. The request is opened as a **draft**: you review it on GitHub
  before proposing it to the reviewers.

Mathlib's guides (contributing, naming, style, documentation) are linked at the bottom of the panel. Mathlib's
reviewers often ask for a shorter proof or a more general statement: that is normal.
`,text:`Contributing to Mathlib Mathlib is Lean's large library of mathematics. When one of your results is missing from it, Madalean prepares what is needed to propose it: the file, the name, the checklist, the text of the request. You review everything; nothing leaves without you. Where the button is - in the Library: open a verified result, then “Prepare for Mathlib”; - in a dossier: below the verified proof, “Prepare for Mathlib”. Give your name (it goes at the top of the file, as Mathlib requires), then “Start the preparation”. The steps 1. Check with current Mathlib. Mathlib only accepts up-to-date code. When the proof was found with the prover's Lean (Lean 4.9), Madalean first replaces the names that changed since (those Lean reports as deprecated, those learned from your proofs, a small checked table) and has Lean 4.36 check it again. When that is not enough, “Restart the proof in current Lean” opens a new dossier, with the old proof as a hint. 2. Look for it in Mathlib. When a Mathlib lemma gives the result directly, Madalean says so, with its name, and stops: no duplicate contribution. 3. Propose a name. Mathlib names a theorem after its statement, read from left to right: a + b ≤ c gives addle, 0 ≤ x gives xnonneg, a hypothesis adds of…. Madalean explains every word of the name and checks that it is free. 4. Reduce the imports. Instead of all of Mathlib, only the files needed — then Lean checks again. 5. Check the final file and run Mathlib's style checks (#lint and its automatic checks). The checklist Each rule is marked good, to review, blocking or not checked: copyright header, file overview, an explanatory sentence for each theorem, lines of at most 100 characters, no sorry, no raised time limit, simp only at the end of a proof, ≤ rather than ≥, variables deduced from the hypotheses in braces, no deprecated name, a free name, reduced imports. The explanatory sentence is written automatically from the statement: reread it. Sending - Copy or Download the file: always possible, nothing leaves the computer. - Create a branch on my fork…: only with a GitHub key saved in Settings → Keys, and from the host computer. Madalean first shows exactly what will be sent (each request, the content of the file); nothing leaves before “Confirm”. - Open the PR…: a second, separate confirmation. The request is opened as a draft: you review it on GitHub before proposing it to the reviewers. Mathlib's guides (contributing, naming, style, documentation) are linked at the bottom of the panel. Mathlib's reviewers often ask for a shorter proof or a more general statement: that is normal.`},{id:`memory`,lang:`en`,title:`Memory — export, import, back up`,order:146,section:`settings`,audience:`researcher`,summary:`Everything Madalean learned (library, lessons, recipes, graphs, digests) in one file, re-checked by Lean on import; automatic backups; a dataset of verified pairs.`,source:`en/memory.md`,site_path:`en/memory.html`,headings:[{level:1,text:`Memory — export, import, back up`,id:`memory-export-import-back-up`},{level:2,text:`Export`,id:`export`},{level:2,text:`Import`,id:`import`},{level:2,text:`Automatic backups`,id:`automatic-backups`},{level:2,text:`Training dataset`,id:`training-dataset`}],images:[],verify:[],body:`# Memory — export, import, back up

Madalean learns without training a model: the **library** of proved results, the **lessons** drawn from its
mistakes, the computation **recipes**, the **graphs** of your problems, the **digests** of attachments. Settings ›
“Memory” puts all of it in one \`.madalean-memory\` file, to keep or to move to another computer.

## Export

Tick the parts to include and, if you like, only some projects, then “Export the memory”.

- **Digests of protected sources** (©, or unknown licence) are left out by default: their licence may forbid
  redistribution. The file says what is missing. Tick “Include digests of copyrighted (©) sources” for a strictly
  personal copy.
- The **original files** of attachments (PDF, images…) are included only when you tick it.
- The file carries the fingerprint (SHA-256) of each part and the Lean and Mathlib versions of your workspaces.

## Import

On the host computer only. Choose a file: Madalean first shows a **preview** — what would be added, checked,
skipped, and why — without writing anything. “Import” applies it.

Nothing is taken on trust:

- every **proof** is re-checked here by Lean, in a workspace with **the same Lean and Mathlib versions**. Accepted,
  it enters the library. Otherwise it stays in “Imported, not verified” with the reason (no workspace with the same
  versions, Lean rejects the proof, a result it uses is missing…) and is not used. After installing the right
  workspace, “Re-check”;
- computation **recipes** are re-read by Sage or Python (never run); code that reaches the system is refused; an
  imported recipe never replaces yours;
- **lessons** keep their evidence but start again from zero: they count only once they helped here;
- **graphs** from elsewhere stay read-only **references** (the preview says how many of their lemmas are already in
  your graphs); your graphs are never changed;
- **digests** join the project with the same id when it exists (as “provided results”: never proofs), otherwise they
  are references;
- duplicates (same statement up to renaming, same lesson, same code) are skipped;
- text that addresses a model (“ignore the instructions…”) is refused; a modified file (different fingerprint) is
  refused as a whole.

## Automatic backups

Tick “Back up automatically”, choose the frequency (day, week, month), how many copies to keep and the folder
(default \`~/.config/madalean/backups\`). Copies stay on this computer; only Madalean's oldest copies are deleted,
never your other files. “Back up now” writes one at once. To restore: “Import” a copy.

## Training dataset

“Export the dataset” writes a JSONL file of the pairs **Lean verified** (statement → proof, error → fix), with the
licence and provenance of each row. It prepares a possible later fine-tune of a local model (off, not provided):
Madalean trains no model.

See also: [Problem graph and lessons](proof-graph.md) · [Library](library.md) · [Security](security.md).
`,text:`Memory — export, import, back up Madalean learns without training a model: the library of proved results, the lessons drawn from its mistakes, the computation recipes, the graphs of your problems, the digests of attachments. Settings › “Memory” puts all of it in one .madalean-memory file, to keep or to move to another computer. Export Tick the parts to include and, if you like, only some projects, then “Export the memory”. - Digests of protected sources (©, or unknown licence) are left out by default: their licence may forbid redistribution. The file says what is missing. Tick “Include digests of copyrighted (©) sources” for a strictly personal copy. - The original files of attachments (PDF, images…) are included only when you tick it. - The file carries the fingerprint (SHA-256) of each part and the Lean and Mathlib versions of your workspaces. Import On the host computer only. Choose a file: Madalean first shows a preview — what would be added, checked, skipped, and why — without writing anything. “Import” applies it. Nothing is taken on trust: - every proof is re-checked here by Lean, in a workspace with the same Lean and Mathlib versions. Accepted, it enters the library. Otherwise it stays in “Imported, not verified” with the reason (no workspace with the same versions, Lean rejects the proof, a result it uses is missing…) and is not used. After installing the right workspace, “Re-check”; - computation recipes are re-read by Sage or Python (never run); code that reaches the system is refused; an imported recipe never replaces yours; - lessons keep their evidence but start again from zero: they count only once they helped here; - graphs from elsewhere stay read-only references (the preview says how many of their lemmas are already in your graphs); your graphs are never changed; - digests join the project with the same id when it exists (as “provided results”: never proofs), otherwise they are references; - duplicates (same statement up to renaming, same lesson, same code) are skipped; - text that addresses a model (“ignore the instructions…”) is refused; a modified file (different fingerprint) is refused as a whole. Automatic backups Tick “Back up automatically”, choose the frequency (day, week, month), how many copies to keep and the folder (default ~/.config/madalean/backups). Copies stay on this computer; only Madalean's oldest copies are deleted, never your other files. “Back up now” writes one at once. To restore: “Import” a copy. Training dataset “Export the dataset” writes a JSONL file of the pairs Lean verified (statement → proof, error → fix), with the licence and provenance of each row. It prepares a possible later fine-tune of a local model (off, not provided): Madalean trains no model. See also: Problem graph and lessons · Library · Security.`},{id:`models-keys`,lang:`en`,title:`Models and keys`,order:300,section:`settings`,audience:`all`,summary:`The Local / Automatic / Online modes, what is sent and to whom, how to get an Anthropic or Gemini key, and what it costs.`,source:`en/models-keys.md`,site_path:`en/models-keys.html`,headings:[{level:1,text:`Models and keys`,id:`models-and-keys`},{level:2,text:`The three modes`,id:`the-three-modes`},{level:2,text:`What is sent, and to whom`,id:`what-is-sent-and-to-whom`},{level:2,text:`Adding a key`,id:`adding-a-key`},{level:3,text:`Anthropic key (Claude)`,id:`anthropic-key-claude`},{level:3,text:`Google Gemini key`,id:`google-gemini-key`},{level:3,text:`Hugging Face token (Goedel-Prover 32B online)`,id:`hugging-face-token-goedel-prover-32b-online`},{level:2,text:`What it costs`,id:`what-it-costs`},{level:2,text:`Claude as paid reinforcement, with caps`,id:`claude-as-paid-reinforcement-with-caps`},{level:2,text:`Choosing a model per role`,id:`choosing-a-model-per-role`}],images:[{src:`img/settings-keys.png`,exists:!0}],verify:[],body:`# Models and keys

Madalean works **without any key**: local models installed on the host and free online providers that need no
account. A key adds a provider's models, often stronger ones. The list of providers, with what is free and where to
create each key, is in [First configuration](first-config.md#keys-of-online-providers); the local models are
described in [What Madalean installs](components.md#local-models).

## The three modes

| Mode | Who works | Network |
|---|---|---|
| *Local* | only the host computer's models (Goedel-Prover, Goedel-Formalizer, Qwen3, and Ollama if it is running) | nothing leaves the host; any non-local connection is refused before it is opened |
| *Automatic* (default) | the online models (with a Hugging Face token, Goedel-Prover 32B opens every proof) | the local models **only** without Internet, or when no online model can work (all down, paused or refused); otherwise the local model is not loaded and the graphics card stays free |
| *Online* | online models only | without network, the work fails with a clear message |

Madalean tells “no Internet” (a quick, cached probe) from “a provider is down” (the Internet answers but not that
provider): without Internet it moves at once to the local models; a provider that is down is only skipped for a
minute. In *Automatic* mode, a proof that the online models searched without finding it is **not** re-run on the
local model (the online Goedel 32B is stronger than the local 8B).

For a given dossier, “Options for this dossier” (on the home screen) lets you choose another mode than the general
one. The status button at the top right of the screen
(its panel “Who receives what”) tells at every moment which model receives your work, with the tokens and cost spent. Every text produced by a model shows
its name.

## What is sent, and to whom

| Stage | What the model receives |
|---|---|
| Understanding | your statement in plain language |
| Translation into Lean | your statement and its reformulation |
| Proof | the Lean statement, Lean's error messages, Mathlib lemmas retrieved for the statement |
| Explanation, written proof | the statement and the Lean proof |
| Questions about sources | your question and the selected passages of your sources |
| Compute (“Ask” cell) | your request and the names already defined in the notebook (not the full outputs) |

What is **never** sent to a model: your API keys, your device tokens, your other dossiers, your files. A key is sent
only to **its** provider: Madalean refuses to attach a key to an address that is not that provider's.

The free providers without an account shipped with Madalean (LLM7.io, OVHcloud AI Endpoints, Kilo Code,
Pollinations) apply their own terms; assume that what you send them may be retained. For confidential work, use
*Local* mode.

## Adding a key

“Settings › Providers” lists the online services by use, with what is free and where your data goes. On a
provider's card, “Create a key” opens its key page; paste the key, Madalean **tests it at once** (“It works: N models available”, or the reason
for the refusal). The key is kept in the host computer's keyring (otherwise in a file readable only by you) and is
never shown again. “Remove the key” deletes it in one click.

![Settings › Providers](img/settings-keys.png)

### Anthropic key (Claude)

1. On the Anthropic card, “Create a key” opens the key page of Anthropic's console; create an account if needed.
2. Claude is pay-as-you-go: follow Anthropic's instructions to add a payment method or credits.
3. Create a key and copy it (it starts with \`sk-ant-\`). It is usually shown only once.
4. Paste it on the Anthropic card.

Advice: if Anthropic's console allows it, set a spend limit there too; Madalean has its own caps anyway (see
below).

### Google Gemini key

1. On the Google Gemini card, “Create a key” opens the key page of Google AI Studio (with a Google account).
2. Create a key and copy it.
3. Paste it on the Google Gemini card.

Gemini's free tier has quotas; when they are reached, Madalean moves on to the next model. The data-use terms differ
between offers and may change: read Google's before sending unpublished work with a free key.

### Hugging Face token (Goedel-Prover 32B online)

With a Hugging Face token, **Goedel-Prover-V2-32B** (served online by a Hugging Face partner provider) opens every
proof: the same loop as the local Goedel — same prompts, ≤ 2 corrections per line of attack, same sampling —,
with the 32B model instead of the 8B, without using the graphics card. If it fails, the free models take over (the
tournament). Goedel-Formalizer is used the same way as soon as a provider serves it online.

1. Create an account on the Hugging Face website (\`huggingface.co\`). Calls are paid with Hugging Face credits (the terms of the offer
   are on Hugging Face's site).
2. On the Hugging Face card, “Create a key” opens Hugging Face's token page, ready to create a token with the “Make
   calls to Inference Providers” permission; create the token (it starts with \`hf_\`).
3. Paste it: Madalean checks the token (nothing billed) and says whether Goedel 32B is available online.

The token is only sent to \`router.huggingface.co\` (inference) and \`huggingface.co\` (the token check). The list of
Goedel models served online is read from Hugging Face's public API, **without** the token. It can be turned off in
“Settings › Models › Advanced settings” (“Goedel-Prover 32B online (Hugging Face) opens every proof when the token is
saved”).

## What it costs

Paid providers bill by the number of *tokens* (≈ ¾ of a word) sent and received. Anthropic's public prices that this
version of Madalean uses for its estimates, per million tokens (input / output); the prices in force are those on
Anthropic's site:

| Model | Input | Output |
|---|---|---|
| Claude Opus 5.5 | $4 | $20 |
| Claude Sonnet 5.5 | $2 | $10 |
| Claude Haiku 5.5 | $0.10 | $0.50 |

The cost of a proof depends on the statement and the number of attempts; it is bounded by the per-proof cap (see
below), and each paid call is shown with its cost under the caps. The limits (agent steps and duration, attempts,
duration of a proof) are set in “Settings › Models › Advanced settings”. A paid model is used only if you chose it
for a task, or as reinforcement (Claude, below).

**Goedel-Prover 32B online (Hugging Face).** The provider publishes no per-token price for this model: Madalean
uses a **conservative estimate** of $1.00 (input) / $3.20 (output) per million tokens, replaced by the published
price as soon as Hugging Face gives one. One Goedel attempt (up to 32,768 output tokens) costs at most ≈ $0.11; the 4
attempts of a proof's first round at most ≈ $0.45. The real cost is shown in the billing area of your Hugging Face
account.

## Claude as paid reinforcement, with caps

With an Anthropic key, Claude can join a proof's tournament **last**, only when all the free models failed
(“Settings › Models”, “Claude as paid reinforcement” part, “Call on Claude when the free models fail” box, ticked
by default). Two caps, editable there:

- “Cap per proof” ($1.00 by default);
- “Cap per month”, per calendar month ($20 by default), for every paid call — Claude, including a role where you chose it, and
  Goedel online on Hugging Face (same caps, same ledger).

Before each call, Madalean estimates the cost at list prices (request size and allowed answer length) and shortens
the allowed answer if needed; if even a short answer would pass a cap, the call **is not made** and the proof says so.
After the call, the real cost is computed from the usage Anthropic returns (input, output, cache read and cache write
tokens) and written to a small private ledger on the host. The month's total (“Spent in …”) and the latest calls are
shown under the caps. This total is computed at list prices: Anthropic's invoice is what counts.

## Choosing a model per role

“Settings › Models”, “Model per task” part, shows, for each task (understand the statement, translate to Lean,
prove, explain, assistant…), the ranking of the available models and the reason for the ranking (“Why?”). “Automatic” lets the router choose; you can impose a model. A
model in error (quota, refused key, overload) is paused and the next one takes over.
`,text:`Models and keys Madalean works without any key: local models installed on the host and free online providers that need no account. A key adds a provider's models, often stronger ones. The list of providers, with what is free and where to create each key, is in First configuration; the local models are described in What Madalean installs. The three modes Mode Who works Network Local only the host computer's models (Goedel-Prover, Goedel-Formalizer, Qwen3, and Ollama if it is running) nothing leaves the host; any non-local connection is refused before it is opened Automatic (default) the online models (with a Hugging Face token, Goedel-Prover 32B opens every proof) the local models only without Internet, or when no online model can work (all down, paused or refused); otherwise the local model is not loaded and the graphics card stays free Online online models only without network, the work fails with a clear message Madalean tells “no Internet” (a quick, cached probe) from “a provider is down” (the Internet answers but not that provider): without Internet it moves at once to the local models; a provider that is down is only skipped for a minute. In Automatic mode, a proof that the online models searched without finding it is not re-run on the local model (the online Goedel 32B is stronger than the local 8B). For a given dossier, “Options for this dossier” (on the home screen) lets you choose another mode than the general one. The status button at the top right of the screen (its panel “Who receives what”) tells at every moment which model receives your work, with the tokens and cost spent. Every text produced by a model shows its name. What is sent, and to whom Stage What the model receives Understanding your statement in plain language Translation into Lean your statement and its reformulation Proof the Lean statement, Lean's error messages, Mathlib lemmas retrieved for the statement Explanation, written proof the statement and the Lean proof Questions about sources your question and the selected passages of your sources Compute (“Ask” cell) your request and the names already defined in the notebook (not the full outputs) What is never sent to a model: your API keys, your device tokens, your other dossiers, your files. A key is sent only to its provider: Madalean refuses to attach a key to an address that is not that provider's. The free providers without an account shipped with Madalean (LLM7.io, OVHcloud AI Endpoints, Kilo Code, Pollinations) apply their own terms; assume that what you send them may be retained. For confidential work, use Local mode. Adding a key “Settings › Providers” lists the online services by use, with what is free and where your data goes. On a provider's card, “Create a key” opens its key page; paste the key, Madalean tests it at once (“It works: N models available”, or the reason for the refusal). The key is kept in the host computer's keyring (otherwise in a file readable only by you) and is never shown again. “Remove the key” deletes it in one click. Settings › Providers Anthropic key (Claude) 1. On the Anthropic card, “Create a key” opens the key page of Anthropic's console; create an account if needed. 2. Claude is pay-as-you-go: follow Anthropic's instructions to add a payment method or credits. 3. Create a key and copy it (it starts with sk-ant-). It is usually shown only once. 4. Paste it on the Anthropic card. Advice: if Anthropic's console allows it, set a spend limit there too; Madalean has its own caps anyway (see below). Google Gemini key 1. On the Google Gemini card, “Create a key” opens the key page of Google AI Studio (with a Google account). 2. Create a key and copy it. 3. Paste it on the Google Gemini card. Gemini's free tier has quotas; when they are reached, Madalean moves on to the next model. The data-use terms differ between offers and may change: read Google's before sending unpublished work with a free key. Hugging Face token (Goedel-Prover 32B online) With a Hugging Face token, Goedel-Prover-V2-32B (served online by a Hugging Face partner provider) opens every proof: the same loop as the local Goedel — same prompts, ≤ 2 corrections per line of attack, same sampling —, with the 32B model instead of the 8B, without using the graphics card. If it fails, the free models take over (the tournament). Goedel-Formalizer is used the same way as soon as a provider serves it online. 1. Create an account on the Hugging Face website (huggingface.co). Calls are paid with Hugging Face credits (the terms of the offer are on Hugging Face's site). 2. On the Hugging Face card, “Create a key” opens Hugging Face's token page, ready to create a token with the “Make calls to Inference Providers” permission; create the token (it starts with hf). 3. Paste it: Madalean checks the token (nothing billed) and says whether Goedel 32B is available online. The token is only sent to router.huggingface.co (inference) and huggingface.co (the token check). The list of Goedel models served online is read from Hugging Face's public API, without the token. It can be turned off in “Settings › Models › Advanced settings” (“Goedel-Prover 32B online (Hugging Face) opens every proof when the token is saved”). What it costs Paid providers bill by the number of tokens (≈ ¾ of a word) sent and received. Anthropic's public prices that this version of Madalean uses for its estimates, per million tokens (input / output); the prices in force are those on Anthropic's site: Model Input Output Claude Opus 5.5 $4 $20 Claude Sonnet 5.5 $2 $10 Claude Haiku 5.5 $0.10 $0.50 The cost of a proof depends on the statement and the number of attempts; it is bounded by the per-proof cap (see below), and each paid call is shown with its cost under the caps. The limits (agent steps and duration, attempts, duration of a proof) are set in “Settings › Models › Advanced settings”. A paid model is used only if you chose it for a task, or as reinforcement (Claude, below). Goedel-Prover 32B online (Hugging Face). The provider publishes no per-token price for this model: Madalean uses a conservative estimate of $1.00 (input) / $3.20 (output) per million tokens, replaced by the published price as soon as Hugging Face gives one. One Goedel attempt (up to 32,768 output tokens) costs at most ≈ $0.11; the 4 attempts of a proof's first round at most ≈ $0.45. The real cost is shown in the billing area of your Hugging Face account. Claude as paid reinforcement, with caps With an Anthropic key, Claude can join a proof's tournament last, only when all the free models failed (“Settings › Models”, “Claude as paid reinforcement” part, “Call on Claude when the free models fail” box, ticked by default). Two caps, editable there: - “Cap per proof” ($1.00 by default); - “Cap per month”, per calendar month ($20 by default), for every paid call — Claude, including a role where you chose it, and Goedel online on Hugging Face (same caps, same ledger). Before each call, Madalean estimates the cost at list prices (request size and allowed answer length) and shortens the allowed answer if needed; if even a short answer would pass a cap, the call is not made and the proof says so. After the call, the real cost is computed from the usage Anthropic returns (input, output, cache read and cache write tokens) and written to a small private ledger on the host. The month's total (“Spent in …”) and the latest calls are shown under the caps. This total is computed at list prices: Anthropic's invoice is what counts. Choosing a model per role “Settings › Models”, “Model per task” part, shows, for each task (understand the statement, translate to Lean, prove, explain, assistant…), the ranking of the available models and the reason for the ranking (“Why?”). “Automatic” lets the router choose; you can impose a model. A model in error (quota, refused key, overload) is paused and the next one takes over.`},{id:`updates`,lang:`en`,title:`Updates`,order:310,section:`settings`,audience:`all`,summary:`What updates on its own, what needs a click, how an update is verified, and how to roll back.`,source:`en/updates.md`,site_path:`en/updates.html`,headings:[{level:1,text:`Updates`,id:`updates`},{level:2,text:`What is updated, and how`,id:`what-is-updated-and-how`},{level:2,text:`Why a Madalean update is safe`,id:`why-a-madalean-update-is-safe`},{level:2,text:`After a Lean or Mathlib update`,id:`after-a-lean-or-mathlib-update`},{level:2,text:`Rolling back`,id:`rolling-back`}],images:[],verify:[],body:`# Updates

Everything updates from within Madalean, without a terminal, by a single rule: **install alongside, verify, switch,
then delete the old version**. A failure changes nothing and you are told.

## What is updated, and how

Everything is set in “Settings › Updates”.

| Component | Default behaviour |
|---|---|
| Madalean (server and interface), “Madalean itself” part | checked every week (except in *Local* mode), downloaded, verified, installed at a quiet moment (no running work), then restarted; “Install” and “Restart now” do it at once. The previous version is kept for rolling back |
| Desktop application (AppImage) | replaces itself after verification; the new version opens at the next start (or at once with “Restart”) |
| Android application | the app's “Automatic updates” setting: it checks at most twice a day, downloads and verifies the signature; installing always asks for your confirmation (Android rule) |
| Lean, Mathlib, Lean packages of the “Current Lean” workspace, SageMath, LaTeX (“Tracked components” part) | automatic: installed alongside, verified (test theorem and re-check of the proved dossiers), switched |
| Goedel models, catalogue of online models | automatic, checksums verified |
| “Prover” workspace (Lean 4.9) | **never**: pinned, it is the models' training environment |
| llama.cpp | notification only; its pinned version changes with Madalean's versions |
| Programs installed on the system outside Madalean (“System components” part) | notification only, with the exact command and an “Open a terminal with the command” button; you type your password. Madalean never runs \`sudo\`, \`pacman\`, \`apt\` or \`dnf\` itself. |

Untick “Install automatically when nothing is running” to be told before each installation instead of the automatic
behaviour. “Check every week (nothing installs without your click)” sets the automatic check; “Check for updates”
runs it at once.

## Why a Madalean update is safe

Every published version comes with a list of checksums (\`SHA256SUMS\`) **signed** with an Ed25519 key kept outside
GitHub. The public key is built into Madalean. A version whose signature does not match is refused, **even if the
GitHub account were compromised**. The update channel (\`updates/stable.json\`, on the site) is signed the same way.

To verify a download yourself: see the [install page](site:install#verify).

## After a Lean or Mathlib update

The proved dossiers of the affected workspace are re-checked automatically (“Re-checking proofs” part, “Re-check
now” button). A dossier
whose proof no longer passes (a renamed lemma, a changed tactic) is flagged; its old verdict is never shown alone.

## Rolling back

For Madalean: “Settings › Updates”, “Madalean itself” part, “Go back to …” button (with the number of the previous
version). For Lean and Mathlib, the old version is replaced only after a successful verification; if it fails,
nothing changes.
`,text:`Updates Everything updates from within Madalean, without a terminal, by a single rule: install alongside, verify, switch, then delete the old version. A failure changes nothing and you are told. What is updated, and how Everything is set in “Settings › Updates”. Component Default behaviour Madalean (server and interface), “Madalean itself” part checked every week (except in Local mode), downloaded, verified, installed at a quiet moment (no running work), then restarted; “Install” and “Restart now” do it at once. The previous version is kept for rolling back Desktop application (AppImage) replaces itself after verification; the new version opens at the next start (or at once with “Restart”) Android application the app's “Automatic updates” setting: it checks at most twice a day, downloads and verifies the signature; installing always asks for your confirmation (Android rule) Lean, Mathlib, Lean packages of the “Current Lean” workspace, SageMath, LaTeX (“Tracked components” part) automatic: installed alongside, verified (test theorem and re-check of the proved dossiers), switched Goedel models, catalogue of online models automatic, checksums verified “Prover” workspace (Lean 4.9) never: pinned, it is the models' training environment llama.cpp notification only; its pinned version changes with Madalean's versions Programs installed on the system outside Madalean (“System components” part) notification only, with the exact command and an “Open a terminal with the command” button; you type your password. Madalean never runs sudo, pacman, apt or dnf itself. Untick “Install automatically when nothing is running” to be told before each installation instead of the automatic behaviour. “Check every week (nothing installs without your click)” sets the automatic check; “Check for updates” runs it at once. Why a Madalean update is safe Every published version comes with a list of checksums (SHA256SUMS) signed with an Ed25519 key kept outside GitHub. The public key is built into Madalean. A version whose signature does not match is refused, even if the GitHub account were compromised. The update channel (updates/stable.json, on the site) is signed the same way. To verify a download yourself: see the install page. After a Lean or Mathlib update The proved dossiers of the affected workspace are re-checked automatically (“Re-checking proofs” part, “Re-check now” button). A dossier whose proof no longer passes (a renamed lemma, a changed tactic) is flagged; its old verdict is never shown alone. Rolling back For Madalean: “Settings › Updates”, “Madalean itself” part, “Go back to …” button (with the number of the previous version). For Lean and Mathlib, the old version is replaced only after a successful verification; if it fails, nothing changes.`},{id:`security`,lang:`en`,title:`Security, explained simply`,order:320,section:`settings`,audience:`all`,summary:`Who can access Madalean, how devices are linked and unlinked, where the keys are, and what Madalean never does.`,source:`en/security.md`,site_path:`en/security.html`,headings:[{level:1,text:`Security, explained simply`,id:`security-explained-simply`},{level:2,text:`Who can talk to Madalean`,id:`who-can-talk-to-madalean`},{level:2,text:`Devices and codes`,id:`devices-and-codes`},{level:2,text:`What a linked device cannot do`,id:`what-a-linked-device-cannot-do`},{level:2,text:`Your API keys`,id:`your-api-keys`},{level:2,text:`Code run on the host`,id:`code-run-on-the-host`},{level:2,text:`Documents from outside`,id:`documents-from-outside`},{level:2,text:`What Madalean never does`,id:`what-madalean-never-does`}],images:[],verify:[],body:`# Security, explained simply

## Who can talk to Madalean

Madalean listens at two doors, both closed to the outside of the host computer:

1. **The local door** (\`127.0.0.1:11500\`), used by the browser or desktop application **of the host**. It accepts
   only requests coming from the host itself.
2. **The device door** (\`127.0.0.1:11501\`), published on your private Tailscale network. Every request must present
   the **token** of a linked device, except the pairing page itself.

A third door, on the local network (port 11502), exists only if you open it from the host (see
[Tailscale › Without Tailscale](tailscale.md#without-tailscale)); it also requires a linked device's token, but its
traffic is not encrypted.

There is no Madalean account, no Madalean server on the Internet, no telemetry.

## Devices and codes

- Linking a device needs a **6-digit code** shown on the host: valid 5 minutes, usable once. Five wrong codes lock
  pairing for 10 minutes; rapid attempts are throttled.
- The device then receives a 256-bit **token**. The host keeps only a fingerprint of it (SHA-256): even someone who
  read the host's files could not recover the token.
- On the phone, the token is in Android's protected storage; on a PC, in the system keyring; in a browser, in a
  cookie inaccessible to the page's scripts.
- **Unlinking** a device (“Settings › Devices”) cuts its access immediately.

A lost or stolen device: unlink it from the host, and remove it from your Tailscale network.

## What a linked device cannot do

Some settings would open the machine; they can be changed **only from the host** (padlock in the interface):

- listening on the local network;
- opening Jupyter (which runs code) to linked devices;
- allowing experiments to run from a linked device, or without prior approval.

## Your API keys

Kept in the host's keyring (otherwise in a file readable only by you). Never sent back to the interface (it only
knows whether a key is saved), never written to a log, never sent to a provider other than their own.

## Code run on the host

- **Lean** compiles the proofs written by the models. Forbidden constructs (\`sorry\`, new axioms, search commands)
  are refused before compiling.
- **Lean can also run code** while it reads a file: \`#eval\`, \`initialize\`, \`run_cmd\`, tactics, macros, notations or
  elaborators defined in the file (\`elab\`, \`macro\`, \`syntax\`, \`notation\`…), attributes that register code, \`unsafe\`,
  \`implemented_by\`, \`IO\`, \`native_decide\`. Since Lean code may come from a model, from the text of a paper or from a
  paired device, Madalean **refuses to compile** any file containing one of these constructs (“Refused before
  compiling: …”). \`import\`s are limited to Mathlib, Aesop, Batteries, Std, Qq, ProofWidgets and Plausible. The check
  works on words, outside comments and strings: it can wrongly refuse a legitimate file (a variable named \`prefix\`,
  for instance); the refusal message gives the kind of construct at fault.
- This filter is only a first barrier. **Every Lean compilation runs in a sandbox** (bubblewrap): no network, no
  access to your home folder, Lean and Mathlib read-only. LaTeX compilations too. “Settings › System” shows whether
  the sandbox is active; without bubblewrap (or if the system does not allow it), they run without this isolation.
- **Experiments of the conjecture workshop**: the code is shown to you, and runs only after your approval of **this
  exact code**. It runs with time, memory and file-size limits, without your keys or secret variables; in the
  sandbox, **without network**, with a read-only file system in which your configuration folder, \`~/.ssh\`, your
  keyrings and the Tailscale state are hidden. The Compute notebooks run in the same sandbox.
- **Jupyter** (JupyterLab opened on its own) runs what you type into it, like any Jupyter installation: its kernels
  are not in the sandbox.
- A model's text never becomes a system command.

## Documents from outside

PDFs, TeX sources, BibTeX files and website responses can be booby-trapped. Madalean never compiles a paper's TeX
(it only reads it), compiles its own TeX exports without any shell access, limits the size and content of archives,
and treats the text of sources as **data**: a passage saying “ignore your instructions” has no effect on the tools,
because answers grounded in your sources have access to no tool.

## What Madalean never does

- Open a port on the Internet (no Tailscale Funnel, no port forwarding).
- Run \`sudo\`, or install a system package for you.
- Send your data to a service you did not choose, or anything at all in *Local* mode.
- Show a proof as verified without Lean's strict verdict.
- Publish anything before you have approved, item by item, what leaves.
- Install an update whose signature is not valid.

Madalean 2.0 went through an independent security review before its first release (its authors did not do the
review); its findings and the accepted risks are in \`docs/SECURITY.md\` in the repository.
`,text:`Security, explained simply Who can talk to Madalean Madalean listens at two doors, both closed to the outside of the host computer: 1. The local door (127.0.0.1:11500), used by the browser or desktop application of the host. It accepts only requests coming from the host itself. 2. The device door (127.0.0.1:11501), published on your private Tailscale network. Every request must present the token of a linked device, except the pairing page itself. A third door, on the local network (port 11502), exists only if you open it from the host (see Tailscale › Without Tailscale); it also requires a linked device's token, but its traffic is not encrypted. There is no Madalean account, no Madalean server on the Internet, no telemetry. Devices and codes - Linking a device needs a 6-digit code shown on the host: valid 5 minutes, usable once. Five wrong codes lock pairing for 10 minutes; rapid attempts are throttled. - The device then receives a 256-bit token. The host keeps only a fingerprint of it (SHA-256): even someone who read the host's files could not recover the token. - On the phone, the token is in Android's protected storage; on a PC, in the system keyring; in a browser, in a cookie inaccessible to the page's scripts. - Unlinking a device (“Settings › Devices”) cuts its access immediately. A lost or stolen device: unlink it from the host, and remove it from your Tailscale network. What a linked device cannot do Some settings would open the machine; they can be changed only from the host (padlock in the interface): - listening on the local network; - opening Jupyter (which runs code) to linked devices; - allowing experiments to run from a linked device, or without prior approval. Your API keys Kept in the host's keyring (otherwise in a file readable only by you). Never sent back to the interface (it only knows whether a key is saved), never written to a log, never sent to a provider other than their own. Code run on the host - Lean compiles the proofs written by the models. Forbidden constructs (sorry, new axioms, search commands) are refused before compiling. - Lean can also run code while it reads a file: #eval, initialize, runcmd, tactics, macros, notations or elaborators defined in the file (elab, macro, syntax, notation…), attributes that register code, unsafe, implementedby, IO, nativedecide. Since Lean code may come from a model, from the text of a paper or from a paired device, Madalean refuses to compile any file containing one of these constructs (“Refused before compiling: …”). imports are limited to Mathlib, Aesop, Batteries, Std, Qq, ProofWidgets and Plausible. The check works on words, outside comments and strings: it can wrongly refuse a legitimate file (a variable named prefix, for instance); the refusal message gives the kind of construct at fault. - This filter is only a first barrier. Every Lean compilation runs in a sandbox (bubblewrap): no network, no access to your home folder, Lean and Mathlib read-only. LaTeX compilations too. “Settings › System” shows whether the sandbox is active; without bubblewrap (or if the system does not allow it), they run without this isolation. - Experiments of the conjecture workshop: the code is shown to you, and runs only after your approval of this exact code. It runs with time, memory and file-size limits, without your keys or secret variables; in the sandbox, without network, with a read-only file system in which your configuration folder, ~/.ssh, your keyrings and the Tailscale state are hidden. The Compute notebooks run in the same sandbox. - Jupyter (JupyterLab opened on its own) runs what you type into it, like any Jupyter installation: its kernels are not in the sandbox. - A model's text never becomes a system command. Documents from outside PDFs, TeX sources, BibTeX files and website responses can be booby-trapped. Madalean never compiles a paper's TeX (it only reads it), compiles its own TeX exports without any shell access, limits the size and content of archives, and treats the text of sources as data: a passage saying “ignore your instructions” has no effect on the tools, because answers grounded in your sources have access to no tool. What Madalean never does - Open a port on the Internet (no Tailscale Funnel, no port forwarding). - Run sudo, or install a system package for you. - Send your data to a service you did not choose, or anything at all in Local mode. - Show a proof as verified without Lean's strict verdict. - Publish anything before you have approved, item by item, what leaves. - Install an update whose signature is not valid. Madalean 2.0 went through an independent security review before its first release (its authors did not do the review); its findings and the accepted risks are in docs/SECURITY.md in the repository.`},{id:`mcp`,lang:`en`,title:`MCP tools: connecting Madalean with other assistants`,order:325,section:`settings`,audience:`all`,summary:`Let another assistant on this computer use Madalean's tools, and give Madalean's models tools of other programs — off until you switch it on.`,source:`en/mcp.md`,site_path:`en/mcp.html`,headings:[{level:1,text:`MCP tools: connecting Madalean with other assistants`,id:`mcp-tools-connecting-madalean-with-other-assistants`},{level:2,text:`Madalean as an MCP server`,id:`madalean-as-an-mcp-server`},{level:2,text:`External MCP servers`,id:`external-mcp-servers`},{level:3,text:`Example: an MCP server for Lean`,id:`example-an-mcp-server-for-lean`},{level:2,text:`The call log`,id:`the-call-log`}],images:[],verify:[],body:`# MCP tools: connecting Madalean with other assistants

**MCP** (*Model Context Protocol*) is a common way for AI assistants to use the tools of other programs. Madalean
speaks it both ways. Everything is set in **Settings › Tools (MCP)**, on the host computer only, and everything is
**off** at first.

## Madalean as an MCP server

Another assistant on this computer (Claude Code, Claude Desktop…) can then:

- **search Mathlib** for the exact names of the installed version;
- **check with Lean** a statement, or a proof of it — with Madalean's strict verdict (no \`sorry\`, no added axiom);
  the proof cannot change the statement;
- **certify** a computational statement (Sage computes a witness, Lean checks it);
- **explain** a Lean error, or code line by line;
- **search your library** and see **the state of your dossiers**.

These tools **store nothing**: no dossier is created, nothing is added to the library.

To connect it:

1. switch on **“Allow the applications of this computer”**;
2. copy the command shown (Claude Code) or the JSON block (Claude Desktop and other clients);
3. restart the client. Madalean must be running.

Two more switches:

- **“Also through a local address (HTTP)”**: for clients that connect to an \`http://127.0.0.1:…\` address. It is open
  to this computer only;
- **“Allow Sage computations”**: the client describes a computation in words (“factor x⁴ − 1 over F₅”); Madalean
  runs only **its own verified code**, in the isolated kernel. Code sent by the client is never run.

Paired devices (phone, another computer) **never** have access to it.

## External MCP servers

The other way round, you can give Madalean's models tools of other programs, for instance an MCP server for the Lean
language. Add it by its **command** (Madalean starts it) or its **address**, then:

1. **Test**: Madalean starts it, reads the list of its tools and stops it;
2. **switch it on**;
3. **tick** the tools the models may call during a proof. Nothing is ticked at first.

What Madalean does to protect you:

- the answers of these tools are read as **data**, never as orders; a text that tries to give orders to the model is
  flagged and set aside;
- a tool whose description gives orders to the model is **refused** (it cannot be ticked);
- the program receives **no API key** and no password; every call is limited in time and size;
- only **Lean** decides that a proof is right: an external tool can never make a proof pass.

A server started by a command runs with **your rights**: add only programs you trust.

### Example: an MCP server for Lean

The \`lean-lsp-mcp\` project (install it yourself, without administrator rights, for instance with \`uv\`) gives access
to Lean's language server. Command to add: \`uvx lean-lsp-mcp\`. It reads the files of a Lean project: start it from
the project or set the project in its own configuration (see its documentation).

## The call log

Every call, in either direction, is written down: when, which tool, done or not, how long it took. The log is at the
bottom of the page, and in \`logs/mcp-activity.jsonl\` of the configuration folder.
`,text:`MCP tools: connecting Madalean with other assistants MCP (Model Context Protocol) is a common way for AI assistants to use the tools of other programs. Madalean speaks it both ways. Everything is set in Settings › Tools (MCP), on the host computer only, and everything is off at first. Madalean as an MCP server Another assistant on this computer (Claude Code, Claude Desktop…) can then: - search Mathlib for the exact names of the installed version; - check with Lean a statement, or a proof of it — with Madalean's strict verdict (no sorry, no added axiom); the proof cannot change the statement; - certify a computational statement (Sage computes a witness, Lean checks it); - explain a Lean error, or code line by line; - search your library and see the state of your dossiers. These tools store nothing: no dossier is created, nothing is added to the library. To connect it: 1. switch on “Allow the applications of this computer”; 2. copy the command shown (Claude Code) or the JSON block (Claude Desktop and other clients); 3. restart the client. Madalean must be running. Two more switches: - “Also through a local address (HTTP)”: for clients that connect to an http://127.0.0.1:… address. It is open to this computer only; - “Allow Sage computations”: the client describes a computation in words (“factor x⁴ − 1 over F₅”); Madalean runs only its own verified code, in the isolated kernel. Code sent by the client is never run. Paired devices (phone, another computer) never have access to it. External MCP servers The other way round, you can give Madalean's models tools of other programs, for instance an MCP server for the Lean language. Add it by its command (Madalean starts it) or its address, then: 1. Test: Madalean starts it, reads the list of its tools and stops it; 2. switch it on; 3. tick the tools the models may call during a proof. Nothing is ticked at first. What Madalean does to protect you: - the answers of these tools are read as data, never as orders; a text that tries to give orders to the model is flagged and set aside; - a tool whose description gives orders to the model is refused (it cannot be ticked); - the program receives no API key and no password; every call is limited in time and size; - only Lean decides that a proof is right: an external tool can never make a proof pass. A server started by a command runs with your rights: add only programs you trust. Example: an MCP server for Lean The lean-lsp-mcp project (install it yourself, without administrator rights, for instance with uv) gives access to Lean's language server. Command to add: uvx lean-lsp-mcp. It reads the files of a Lean project: start it from the project or set the project in its own configuration (see its documentation). The call log Every call, in either direction, is written down: when, which tool, done or not, how long it took. The log is at the bottom of the page, and in logs/mcp-activity.jsonl of the configuration folder.`},{id:`troubleshooting`,lang:`en`,title:`Troubleshooting`,order:400,section:`help`,audience:`all`,summary:`Error messages in plain language, their cause and what to do.`,source:`en/troubleshooting.md`,site_path:`en/troubleshooting.html`,headings:[{level:1,text:`Troubleshooting`,id:`troubleshooting`},{level:2,text:`Installation`,id:`installation`},{level:3,text:`The .run installer does not start`,id:`the-run-installer-does-not-start`},{level:3,text:`No browser opens`,id:`no-browser-opens`},{level:3,text:`The disk is full`,id:`the-disk-is-full`},{level:3,text:`“micromamba failed”`,id:`micromamba-failed`},{level:3,text:`“Wrong SHA-256 fingerprint: …”`,id:`wrong-sha-256-fingerprint`},{level:3,text:`No NVIDIA card, or driver too old`,id:`no-nvidia-card-or-driver-too-old`},{level:3,text:`The system's SageMath is not used`,id:`the-systems-sagemath-is-not-used`},{level:3,text:`LaTeX export fails`,id:`latex-export-fails`},{level:3,text:`The service does not start`,id:`the-service-does-not-start`},{level:3,text:`The sandbox is reported inactive`,id:`the-sandbox-is-reported-inactive`},{level:2,text:`Connection and devices`,id:`connection-and-devices`},{level:3,text:`The device cannot reach the host`,id:`the-device-cannot-reach-the-host`},{level:3,text:`“This device is not (or no longer) linked to Madalean”`,id:`this-device-is-not-or-no-longer-linked-to-madalean`},{level:3,text:`The HTTPS certificate is refused, or the first connection is very slow`,id:`the-https-certificate-is-refused-or-the-first-connection-is-very-slow`},{level:3,text:`“Host computer only”`,id:`host-computer-only`},{level:2,text:`Models`,id:`models`},{level:3,text:`“No model available”`,id:`no-model-available`},{level:3,text:`“The provider refuses the key”`,id:`the-provider-refuses-the-key`},{level:3,text:`The local model is slow, or “not enough GPU memory”`,id:`the-local-model-is-slow-or-not-enough-gpu-memory`},{level:3,text:`“Paused: quota reached” on a free provider`,id:`paused-quota-reached-on-a-free-provider`},{level:2,text:`Lean`,id:`lean`},{level:3,text:`“Lean rejects the statement”`,id:`lean-rejects-the-statement`},{level:3,text:`“Refused before compiling: …”`,id:`refused-before-compiling`},{level:3,text:`“No proof found”`,id:`no-proof-found`},{level:3,text:`“Proof rejected: contains sorry” or “non-standard axiom”`,id:`proof-rejected-contains-sorry-or-non-standard-axiom`},{level:3,text:`“Compilation timeout”`,id:`compilation-timeout`},{level:3,text:`“Lean workspace not found” or “workspace not ready”`,id:`lean-workspace-not-found-or-workspace-not-ready`},{level:3,text:`“This dossier already has work in progress”`,id:`this-dossier-already-has-work-in-progress`},{level:2,text:`Export`,id:`export`},{level:3,text:`“No LaTeX on the host computer: the HTML version opens”`,id:`no-latex-on-the-host-computer-the-html-version-opens`},{level:3,text:`Symbols are missing in the PDF`,id:`symbols-are-missing-in-the-pdf`},{level:2,text:`Jupyter`,id:`jupyter`},{level:3,text:`“Jupyter is not available”`,id:`jupyter-is-not-available`},{level:3,text:`“Jupyter is reachable only from the host”`,id:`jupyter-is-reachable-only-from-the-host`},{level:2,text:`When nothing works`,id:`when-nothing-works`}],images:[],verify:[],body:`# Troubleshooting

“Settings › System”, “Health” part, shows the state of each component (Lean workspaces, models, TeX, fonts, Jupyter,
sandbox, disk) with a “Repair” button when one exists. Start there.

## Installation

The full installation log is in \`~/.local/share/madalean/install.log\`. \`install.sh\` is safe to run again: it resumes
where it stopped. See [Installing Madalean](install.md).

### The .run installer does not start

- **Nothing happens on double-click, or “Permission denied”**: the file is not executable. Right-click › “Properties”
  › “Permissions” › “Allow executing file as program”, or in a terminal \`chmod +x Madalean-installer.run\`, then
  start it again.
- **Double-clicking opens the file in a text editor**: start it from a terminal, \`./Madalean-installer.run\`
  (with the right version number).
- **“Damaged or modified file (wrong SHA-256)”**: the file was damaged during the download, or it is
  incomplete. Delete it and **download it again** from the releases page; never bypass this check.


### No browser opens

Without a graphical session, the installer switches by itself to the terminal assistant. If there is a desktop but no
browser opens, the installer prints the address of its page in the terminal (\`http://127.0.0.1:…\`, with its
one-time key): copy it into a browser on the **same** computer. You can also force the terminal assistant from
source: \`./install.sh --assistant\` (or \`./Madalean-installer.run --terminal\`).

### The disk is full

Step 1 shows the free space. Plan for ≈ 6 GB without local models or SageMath, ≈ 25 GB with the local models, 5 GB
more for SageMath (see [Installing Madalean](install.md#before-you-start)). Free some space, or reduce the plan:
\`--models none\` (or \`--models prover\`), \`--sage later\`. Then run \`install.sh\` again: what is already installed is not
redone. Ongoing downloads are kept in \`~/.local/share/madalean/downloads/\` and resumed.

### “micromamba failed”

Installing the main environment (step 3) failed, most often because of a network interruption or a full disk. The
last lines of the log are shown; details are in \`~/.local/share/madalean/install.log\`. Check the connection and the
free space, then run \`install.sh\` again.

### “Wrong SHA-256 fingerprint: …”

A downloaded file does not match the expected fingerprint: it was truncated or altered on the way. The faulty file
is deleted; run \`install.sh\` again, which downloads it again. If the error repeats, a proxy or filter on your network
may be modifying downloads.

### No NVIDIA card, or driver too old

This is not an error: Madalean then installs the processor version of the model engine and advises no local model.
Online models work normally. If you do have an NVIDIA card, check that the driver is installed (\`nvidia-smi\` must
answer), then run \`./install.sh --gpu\` again. See [Local models](components.md#local-models).

### The system's SageMath is not used

To be reused, your system's SageMath must be version 10.0 or newer **and** provide its Jupyter kernel \`sagemath\`
(for example \`/usr/share/jupyter/kernels/sagemath\`). Otherwise Madalean uses its own copy (≈ 5 GB). Install the
Jupyter kernel with your distribution, or let Madalean install its copy. See [SageMath](components.md#sagemath).

### LaTeX export fails

“Settings › System”, “Health” part, “LaTeX (PDF export)” line: “Repair” reinstalls the TeX bundle. If you use the
system's TeX Live first (\`tex_engine = system\`), it must be version 2022 or newer, with \`fontspec\`. See also
[Export](#export) below and [LaTeX](components.md#latex).

### The service does not start

At the end of the installation, “The server does not answer yet” means the service did not start in time. Look at
its log:

\`\`\`bash
systemctl --user status madalean
journalctl --user -u madalean -e
\`\`\`

The log gives the cause (port 11500 already taken by another program, missing component…). If \`systemctl --user\` is
not available (some containers or sessions without systemd), start Madalean by hand:
\`~/.local/share/madalean/current/bin/madalean serve\`.

### The sandbox is reported inactive

bubblewrap is not installed: it is a package of your distribution, to install yourself (for example
\`sudo apt install bubblewrap\`). See [bubblewrap](components.md#bubblewrap-the-sandbox).

## Connection and devices

### The device cannot reach the host

1. Is the host computer on, and not asleep?
2. Is Tailscale **connected** on the device, with the same account as the host? (Tailscale app: switch on.)
3. Is the server running? On the host: \`systemctl --user status madalean\`.
4. Is Madalean's Tailscale node approved and running? On the host: \`curl -s http://127.0.0.1:11500/api/net\` must
   show \`"state": "running"\` (otherwise, see [Link a device › Step 1](pairing.md)). If you use the system's Tailscale
   instead: \`scripts/tailscale_setup.sh --status\`.
5. Is the address typed in full, \`madalean.tailXXXX.ts.net\` (or \`pc-name.tailXXXX.ts.net:10500\` with the system's
   Tailscale)?

### “This device is not (or no longer) linked to Madalean”

The device was unlinked, or its data was erased. Ask for a new code on the host and link it again.

### The HTTPS certificate is refused, or the first connection is very slow

HTTPS is not enabled on your tailnet: see [Tailscale › Enable HTTPS](tailscale.md#enable-https). The very first
connection may take a few seconds while the certificate is issued.

### “Host computer only”

This setting opens the machine to other devices; it can only be changed on the host. See [Security](security.md).

## Models

### “No model available”

- *Local* mode: no local model is installed or loadable. “Settings › System” says which one is missing;
  \`./install.sh\` downloads the models.
- *Online* mode: no network, or all providers are paused (quotas). Switch to *Automatic* to use the local models as a
  fallback.

### “The provider refuses the key”

The key was badly copied (extra space), revoked, or the account has no credit left. Create it again on the
provider's site and paste it again (“Settings › Providers”): Madalean tests it at once. After a key refusal, Madalean
pauses the provider for 12 h (“Paused for now (key refused (check it))”). For Hugging Face, a new token that passes
the test lifts the pause at once; for the other providers, the pause runs its course, then the new key is used
normally.

### The local model is slow, or “not enough GPU memory”

Another program is using the graphics card (game, another AI). “Settings › System” shows the memory used per
application. Without an NVIDIA card, local models run on the processor: expect minutes per answer.

### “Paused: quota reached” on a free provider

Normal: Madalean moves on to the next model and retries the provider later (after the time given by the provider, or
the next day for a daily quota).

## Lean

### “Lean rejects the statement”

The translation is not valid Lean for this workspace (unknown name, notation from another Mathlib version). Lean's
message is shown below the statement. “Fix the statement…” reruns the translation with the error; or “Edit by
hand”.

### “Refused before compiling: …”

The code contains a construct that could run code on the host (\`#eval\`, \`macro\`, \`elab\`, \`unsafe\`,
\`native_decide\`…) or an \`import\` outside Mathlib and its dependencies: Madalean refuses to compile it (see
[Security](security.md#code-run-on-the-host)). The message gives the kind of construct found, for example
meta-programming, system access (IO, unsafe) or the import of a module that is not allowed. Remove it. If the word at
fault is just a variable name (\`prefix\`, \`syntax\`, \`IO\`…), rename the variable.

### “No proof found”

The attempts are exhausted. This does not prove the statement false. Try: re-reading the statement (missing
hypothesis?), “Another method”, a stronger model (a key), “Split into lemmas”, or a hint in a follow-up request
(“use induction on $n$”).

### “Proof rejected: contains sorry” or “non-standard axiom”

The strict verdict rejects an incomplete proof or one that adds an axiom. Only \`propext\`, \`Classical.choice\` and
\`Quot.sound\` are allowed.

### “Compilation timeout”

Compilation exceeded the maximum time (“Settings › Models”, 10 to 1800 s). A tactic such as \`simp\` or \`nlinarith\`
can search for a long time; a more explicit proof compiles faster.

### “Lean workspace not found” or “workspace not ready”

The workspace is not installed or its build is not finished. “Settings › Lean workspaces” gives its state; rerun
\`./install.sh\` if needed.

### “This dossier already has work in progress”

A dossier has only one active job. Wait for it to finish, or “Stop”.

## Export

### “No LaTeX on the host computer: the HTML version opens”

Madalean's LaTeX engine (installed by \`./install.sh\`) is missing or could not typeset the document, and no system
LaTeX replaced it. The HTML prints to PDF from the browser. For the real PDF: “Settings › System”, “Health” part,
LaTeX line, “Repair” button (or rerun \`./install.sh\`).

### Symbols are missing in the PDF

The DejaVu Sans Mono and Noto Sans Math fonts are installed with Madalean; “Settings › System” checks that they are
present. Rerun \`./install.sh\` if one is missing.

## Jupyter

### “Jupyter is not available”

JupyterLab (installed with Madalean) is missing or did not start. “Settings › System” gives the cause, with a
“Repair” button.

### “Jupyter is reachable only from the host”

The host has not opened Jupyter to linked devices (“Settings › Notebook and access”, on the host).

## When nothing works

\`\`\`bash
systemctl --user restart madalean
journalctl --user -u madalean -e
\`\`\`

The log contains no key and no token: you can attach it to a problem report.
`,text:`Troubleshooting “Settings › System”, “Health” part, shows the state of each component (Lean workspaces, models, TeX, fonts, Jupyter, sandbox, disk) with a “Repair” button when one exists. Start there. Installation The full installation log is in ~/.local/share/madalean/install.log. install.sh is safe to run again: it resumes where it stopped. See Installing Madalean. The .run installer does not start - Nothing happens on double-click, or “Permission denied”: the file is not executable. Right-click › “Properties” › “Permissions” › “Allow executing file as program”, or in a terminal chmod +x Madalean-installer.run, then start it again. - Double-clicking opens the file in a text editor: start it from a terminal, ./Madalean-installer.run (with the right version number). - “Damaged or modified file (wrong SHA-256)”: the file was damaged during the download, or it is incomplete. Delete it and download it again from the releases page; never bypass this check. No browser opens Without a graphical session, the installer switches by itself to the terminal assistant. If there is a desktop but no browser opens, the installer prints the address of its page in the terminal (http://127.0.0.1:…, with its one-time key): copy it into a browser on the same computer. You can also force the terminal assistant from source: ./install.sh --assistant (or ./Madalean-installer.run --terminal). The disk is full Step 1 shows the free space. Plan for ≈ 6 GB without local models or SageMath, ≈ 25 GB with the local models, 5 GB more for SageMath (see Installing Madalean). Free some space, or reduce the plan: --models none (or --models prover), --sage later. Then run install.sh again: what is already installed is not redone. Ongoing downloads are kept in ~/.local/share/madalean/downloads/ and resumed. “micromamba failed” Installing the main environment (step 3) failed, most often because of a network interruption or a full disk. The last lines of the log are shown; details are in ~/.local/share/madalean/install.log. Check the connection and the free space, then run install.sh again. “Wrong SHA-256 fingerprint: …” A downloaded file does not match the expected fingerprint: it was truncated or altered on the way. The faulty file is deleted; run install.sh again, which downloads it again. If the error repeats, a proxy or filter on your network may be modifying downloads. No NVIDIA card, or driver too old This is not an error: Madalean then installs the processor version of the model engine and advises no local model. Online models work normally. If you do have an NVIDIA card, check that the driver is installed (nvidia-smi must answer), then run ./install.sh --gpu again. See Local models. The system's SageMath is not used To be reused, your system's SageMath must be version 10.0 or newer and provide its Jupyter kernel sagemath (for example /usr/share/jupyter/kernels/sagemath). Otherwise Madalean uses its own copy (≈ 5 GB). Install the Jupyter kernel with your distribution, or let Madalean install its copy. See SageMath. LaTeX export fails “Settings › System”, “Health” part, “LaTeX (PDF export)” line: “Repair” reinstalls the TeX bundle. If you use the system's TeX Live first (texengine = system), it must be version 2022 or newer, with fontspec. See also Export below and LaTeX. The service does not start At the end of the installation, “The server does not answer yet” means the service did not start in time. Look at its log: The log gives the cause (port 11500 already taken by another program, missing component…). If systemctl --user is not available (some containers or sessions without systemd), start Madalean by hand: ~/.local/share/madalean/current/bin/madalean serve. The sandbox is reported inactive bubblewrap is not installed: it is a package of your distribution, to install yourself (for example sudo apt install bubblewrap). See bubblewrap. Connection and devices The device cannot reach the host 1. Is the host computer on, and not asleep? 2. Is Tailscale connected on the device, with the same account as the host? (Tailscale app: switch on.) 3. Is the server running? On the host: systemctl --user status madalean. 4. Is Madalean's Tailscale node approved and running? On the host: curl -s http://127.0.0.1:11500/api/net must show "state": "running" (otherwise, see Link a device › Step 1). If you use the system's Tailscale instead: scripts/tailscalesetup.sh --status. 5. Is the address typed in full, madalean.tailXXXX.ts.net (or pc-name.tailXXXX.ts.net:10500 with the system's Tailscale)? “This device is not (or no longer) linked to Madalean” The device was unlinked, or its data was erased. Ask for a new code on the host and link it again. The HTTPS certificate is refused, or the first connection is very slow HTTPS is not enabled on your tailnet: see Tailscale › Enable HTTPS. The very first connection may take a few seconds while the certificate is issued. “Host computer only” This setting opens the machine to other devices; it can only be changed on the host. See Security. Models “No model available” - Local mode: no local model is installed or loadable. “Settings › System” says which one is missing; ./install.sh downloads the models. - Online mode: no network, or all providers are paused (quotas). Switch to Automatic to use the local models as a fallback. “The provider refuses the key” The key was badly copied (extra space), revoked, or the account has no credit left. Create it again on the provider's site and paste it again (“Settings › Providers”): Madalean tests it at once. After a key refusal, Madalean pauses the provider for 12 h (“Paused for now (key refused (check it))”). For Hugging Face, a new token that passes the test lifts the pause at once; for the other providers, the pause runs its course, then the new key is used normally. The local model is slow, or “not enough GPU memory” Another program is using the graphics card (game, another AI). “Settings › System” shows the memory used per application. Without an NVIDIA card, local models run on the processor: expect minutes per answer. “Paused: quota reached” on a free provider Normal: Madalean moves on to the next model and retries the provider later (after the time given by the provider, or the next day for a daily quota). Lean “Lean rejects the statement” The translation is not valid Lean for this workspace (unknown name, notation from another Mathlib version). Lean's message is shown below the statement. “Fix the statement…” reruns the translation with the error; or “Edit by hand”. “Refused before compiling: …” The code contains a construct that could run code on the host (#eval, macro, elab, unsafe, nativedecide…) or an import outside Mathlib and its dependencies: Madalean refuses to compile it (see Security). The message gives the kind of construct found, for example meta-programming, system access (IO, unsafe) or the import of a module that is not allowed. Remove it. If the word at fault is just a variable name (prefix, syntax, IO…), rename the variable. “No proof found” The attempts are exhausted. This does not prove the statement false. Try: re-reading the statement (missing hypothesis?), “Another method”, a stronger model (a key), “Split into lemmas”, or a hint in a follow-up request (“use induction on $n$”). “Proof rejected: contains sorry” or “non-standard axiom” The strict verdict rejects an incomplete proof or one that adds an axiom. Only propext, Classical.choice and Quot.sound are allowed. “Compilation timeout” Compilation exceeded the maximum time (“Settings › Models”, 10 to 1800 s). A tactic such as simp or nlinarith can search for a long time; a more explicit proof compiles faster. “Lean workspace not found” or “workspace not ready” The workspace is not installed or its build is not finished. “Settings › Lean workspaces” gives its state; rerun ./install.sh if needed. “This dossier already has work in progress” A dossier has only one active job. Wait for it to finish, or “Stop”. Export “No LaTeX on the host computer: the HTML version opens” Madalean's LaTeX engine (installed by ./install.sh) is missing or could not typeset the document, and no system LaTeX replaced it. The HTML prints to PDF from the browser. For the real PDF: “Settings › System”, “Health” part, LaTeX line, “Repair” button (or rerun ./install.sh). Symbols are missing in the PDF The DejaVu Sans Mono and Noto Sans Math fonts are installed with Madalean; “Settings › System” checks that they are present. Rerun ./install.sh if one is missing. Jupyter “Jupyter is not available” JupyterLab (installed with Madalean) is missing or did not start. “Settings › System” gives the cause, with a “Repair” button. “Jupyter is reachable only from the host” The host has not opened Jupyter to linked devices (“Settings › Notebook and access”, on the host). When nothing works The log contains no key and no token: you can attach it to a problem report.`},{id:`glossary`,lang:`en`,title:`Lean glossary`,order:410,section:`reference`,audience:`learner`,summary:`The Lean and Mathlib vocabulary needed to read statements and proofs.`,source:`en/glossary.md`,site_path:`en/glossary.html`,headings:[{level:1,text:`Lean glossary`,id:`lean-glossary`},{level:2,text:`Logic and notation`,id:`logic-and-notation`},{level:2,text:`Declarations`,id:`declarations`},{level:2,text:`Arguments`,id:`arguments`},{level:2,text:`Types and universes`,id:`types-and-universes`},{level:2,text:`Proofs`,id:`proofs`},{level:2,text:`Ecosystem`,id:`ecosystem`}],images:[],verify:[],body:"# Lean glossary\n\nTerms are grouped by theme. For tactics, see [First tactics](tactics.md).\n\nIn the app, the **Glossary** screen covers these terms and many more (about 250, by category and by level beginner /\nintermediate / advanced), each with its meaning, Lean form, a tiny example, related entries, the matching Mathlib\ndeclarations and your dossiers that use it. It also powers the hover help on statements in Learn mode.\n\n## Logic and notation\n\n| Lean | Reads | Remark |\n|---|---|---|\n| `∀ x, P x` | for all $x$, $P(x)$ | `∀ x > 0, …` abbreviates `∀ x, x > 0 → …` |\n| `∃ x, P x` | there exists $x$ such that $P(x)$ | `∃! x, P x`: there exists a unique $x$ |\n| `P → Q` | $P$ implies $Q$ | also the type of functions from `P` to `Q` |\n| `P ↔ Q` | $P$ if and only if $Q$ | |\n| `P ∧ Q`, `P ∨ Q` | and, or | |\n| `¬ P` | not $P$ | defined as `P → False` |\n| `a ≠ b` | $a \\neq b$ | abbreviates `¬ (a = b)` |\n| `True`, `False` | true, false | propositions |\n| `a ∣ b` | $a$ divides $b$ | special vertical bar, typed `\\mid`; it is not the keyboard bar `\\|` |\n| `a % b` | remainder of the division | |\n| `x⁻¹` | inverse | `0⁻¹ = 0` in a field |\n| `↑n`, `(n : ℝ)` | $n$ seen in another type | conversion (*coercion*) |\n| `fun x => e` | $x \\mapsto e$ | also written `λ x => e` or `fun x ↦ e` |\n| `f x` | $f(x)$ | application is written without parentheses |\n| `∑ i in s, f i` | $\\sum_{i \\in s} f(i)$ | `∑ i ∈ s, f i` in recent versions |\n| `∏ i in s, f i` | $\\prod_{i \\in s} f(i)$ | same |\n| `Finset.range n` | $\\{0, \\dots, n-1\\}$ | |\n| `Finset.Icc a b` | $\\{a, \\dots, b\\}$ | also `Ico`, `Ioc`, `Ioo` |\n| `\\|x\\|` | absolute value | |\n| `⌊x⌋`, `⌈x⌉` | floor, ceiling | `Int.floor`, `Int.ceil` |\n\n## Declarations\n\n| Term | Meaning |\n|---|---|\n| `theorem`, `lemma` | a statement with its proof (Madalean normalises `lemma` to `theorem`) |\n| `example` | an unnamed theorem |\n| `def` | a definition |\n| `abbrev` | a definition that Lean unfolds readily |\n| `structure`, `class`, `instance` | types with fields; type classes (“ℝ is a field”) and their instances |\n| `axiom` | a statement admitted without proof; forbidden in a proof accepted by Madalean |\n| `sorry` | “proof to be completed”: Lean accepts it provisionally, but reports a gap |\n| `variable` | declares variables shared by several statements |\n| `namespace X … end X` | prefixes names: `X.foo` |\n| `open X` | lets you write `foo` instead of `X.foo` |\n| `import` | loads a library (`import Mathlib`) |\n| `#check e` | shows the type of `e` |\n| `#eval e` | computes `e` |\n\n## Arguments\n\n| Syntax | Meaning |\n|---|---|\n| `(x : α)` | explicit argument, to be given |\n| `{x : α}` | implicit argument, inferred by Lean |\n| `[inst : Field α]` | instance argument, found by Lean (“α is a field”) |\n| `(h : P)` | a hypothesis named `h`; a proof of `P` |\n\n## Types and universes\n\n| Term | Meaning |\n|---|---|\n| `Prop` | the type of propositions; a proof of `P : Prop` is a term of type `P` |\n| `Type` | the type of “ordinary” types (`ℕ : Type`) |\n| `ℕ`, `ℤ`, `ℚ`, `ℝ`, `ℂ` | natural numbers (with 0), integers, rationals, reals, complex numbers |\n| `Fin n` | $\\{0, \\dots, n-1\\}$ as a type |\n| `Set α`, `Finset α` | subsets of `α`; finite (computable) subsets |\n| `α × β` | Cartesian product; `p.1`, `p.2` the components |\n| `List α` | lists |\n| `Polynomial R` (`R[X]`) | polynomials with coefficients in `R` |\n| `Matrix m n R` | matrices |\n\n## Proofs\n\n| Term | Meaning |\n|---|---|\n| goal | what remains to be proved, shown as `⊢ P` |\n| hypothesis | what is assumed, above the `⊢` |\n| tactic | an instruction that transforms the goal (`intro`, `simp`…) |\n| `by` | switches to tactic mode |\n| term mode | a proof written as a term: `fun h => h.1` |\n| `h.1`, `h.2` | the two parts of a hypothesis `h : P ∧ Q` |\n| `⟨a, b⟩` | builds a pair, a conjunction, or a witness with its proof |\n| `·` | starts handling one of the goals |\n| `<;>` | applies the next tactic to all the goals produced |\n| `rfl` | “by definition”: both sides are equal after computation |\n\n## Ecosystem\n\n| Term | Meaning |\n|---|---|\n| Lean 4 | the language and proof checker |\n| Mathlib | the community's mathematical library (≈ 290,000 declarations in a recent version) |\n| kernel | the small part of Lean that actually checks proofs |\n| standard axioms | `propext`, `Classical.choice`, `Quot.sound`: accepted by Mathlib and by Madalean |\n| Lake | the build tool of Lean projects (`lake build`) |\n| elan | the Lean version manager |\n| toolchain | a precise Lean version, fixed by a project's `lean-toolchain` file |\n| workspace | in Madalean, a Lake project with a Lean and Mathlib version |\n| blueprint | the graph of a formalisation project's statements and their dependencies |\n",text:`Lean glossary Terms are grouped by theme. For tactics, see First tactics. In the app, the Glossary screen covers these terms and many more (about 250, by category and by level beginner / intermediate / advanced), each with its meaning, Lean form, a tiny example, related entries, the matching Mathlib declarations and your dossiers that use it. It also powers the hover help on statements in Learn mode. Logic and notation Lean Reads Remark ∀ x, P x for all $x$, $P(x)$ ∀ x > 0, … abbreviates ∀ x, x > 0 → … ∃ x, P x there exists $x$ such that $P(x)$ ∃! x, P x: there exists a unique $x$ P → Q $P$ implies $Q$ also the type of functions from P to Q P ↔ Q $P$ if and only if $Q$ P ∧ Q, P ∨ Q and, or ¬ P not $P$ defined as P → False a ≠ b $a \\neq b$ abbreviates ¬ (a = b) True, False true, false propositions a ∣ b $a$ divides $b$ special vertical bar, typed \\mid; it is not the keyboard bar a % b remainder of the division x⁻¹ inverse 0⁻¹ = 0 in a field ↑n, (n : ℝ) $n$ seen in another type conversion (coercion) fun x => e $x \\mapsto e$ also written λ x => e or fun x ↦ e f x $f(x)$ application is written without parentheses ∑ i in s, f i $\\sum{i \\in s} f(i)$ ∑ i ∈ s, f i in recent versions ∏ i in s, f i $\\prod{i \\in s} f(i)$ same Finset.range n $\\{0, \\dots, n-1\\}$ Finset.Icc a b $\\{a, \\dots, b\\}$ also Ico, Ioc, Ioo x absolute value ⌊x⌋, ⌈x⌉ floor, ceiling Int.floor, Int.ceil Declarations Term Meaning theorem, lemma a statement with its proof (Madalean normalises lemma to theorem) example an unnamed theorem def a definition abbrev a definition that Lean unfolds readily structure, class, instance types with fields; type classes (“ℝ is a field”) and their instances axiom a statement admitted without proof; forbidden in a proof accepted by Madalean sorry “proof to be completed”: Lean accepts it provisionally, but reports a gap variable declares variables shared by several statements namespace X … end X prefixes names: X.foo open X lets you write foo instead of X.foo import loads a library (import Mathlib) #check e shows the type of e #eval e computes e Arguments Syntax Meaning (x : α) explicit argument, to be given {x : α} implicit argument, inferred by Lean [inst : Field α] instance argument, found by Lean (“α is a field”) (h : P) a hypothesis named h; a proof of P Types and universes Term Meaning Prop the type of propositions; a proof of P : Prop is a term of type P Type the type of “ordinary” types (ℕ : Type) ℕ, ℤ, ℚ, ℝ, ℂ natural numbers (with 0), integers, rationals, reals, complex numbers Fin n $\\{0, \\dots, n-1\\}$ as a type Set α, Finset α subsets of α; finite (computable) subsets α × β Cartesian product; p.1, p.2 the components List α lists Polynomial R (R[X]) polynomials with coefficients in R Matrix m n R matrices Proofs Term Meaning goal what remains to be proved, shown as ⊢ P hypothesis what is assumed, above the ⊢ tactic an instruction that transforms the goal (intro, simp…) by switches to tactic mode term mode a proof written as a term: fun h => h.1 h.1, h.2 the two parts of a hypothesis h : P ∧ Q ⟨a, b⟩ builds a pair, a conjunction, or a witness with its proof · starts handling one of the goals <;> applies the next tactic to all the goals produced rfl “by definition”: both sides are equal after computation Ecosystem Term Meaning Lean 4 the language and proof checker Mathlib the community's mathematical library (≈ 290,000 declarations in a recent version) kernel the small part of Lean that actually checks proofs standard axioms propext, Classical.choice, Quot.sound: accepted by Mathlib and by Madalean Lake the build tool of Lean projects (lake build) elan the Lean version manager toolchain a precise Lean version, fixed by a project's lean-toolchain file workspace in Madalean, a Lake project with a Lean and Mathlib version blueprint the graph of a formalisation project's statements and their dependencies`},{id:`tactics`,lang:`en`,title:`First tactics`,order:420,section:`reference`,audience:`learner`,summary:`What the most common Lean 4 and Mathlib tactics do, with an example each, and when they fail.`,source:`en/tactics.md`,site_path:`en/tactics.html`,headings:[{level:1,text:`First tactics`,id:`first-tactics`},{level:2,text:`Structuring`,id:`structuring`},{level:2,text:`Induction and cases`,id:`induction-and-cases`},{level:2,text:`Rewriting and simplifying`,id:`rewriting-and-simplifying`},{level:2,text:`Arithmetic and inequalities`,id:`arithmetic-and-inequalities`},{level:2,text:`Searching`,id:`searching`},{level:2,text:`Reading an error`,id:`reading-an-error`}],images:[],verify:[],body:"# First tactics\n\nA proof in tactic mode (`:= by …`) is a sequence of instructions that transform the **goal** (what remains to be\nproved, shown after `⊢`) until nothing is left. The examples assume `import Mathlib`. The exact behaviour of a tactic\ndepends on the Mathlib version; what follows holds for both Madalean workspaces unless stated.\n\n## Structuring\n\n| Tactic | Effect | Example goal |\n|---|---|---|\n| `intro x` | introduces a variable or hypothesis: for `∀ x, P x` or `P → Q` | `⊢ ∀ n : ℕ, n + 0 = n` → `intro n` |\n| `exact e` | closes the goal with a term of exactly the right type | `exact ha` when `ha : P` and `⊢ P` |\n| `apply f` | reduces the goal to the hypotheses of `f` | `⊢ 0 < a * b` → `apply mul_pos` leaves `0 < a` and `0 < b` |\n| `refine ⟨?_, ?_⟩` | like `exact`, with holes `?_` that become goals | |\n| `constructor` | splits `P ∧ Q` (two goals) or `P ↔ Q` (both directions) | |\n| `use 3` | provides the witness of an `∃` | `⊢ ∃ n : ℕ, n * n = 9` → `use 3` |\n| `obtain ⟨x, hx⟩ := h` | unpacks `h : ∃ x, P x` (or `h : P ∧ Q`) | |\n| `rcases h with h1 \\| h2` | cases of a disjunction `h : P ∨ Q` | |\n| `left`, `right` | chooses one side of an `∨` to prove | |\n| `have h : P := by …` | proves an intermediate result and adds it to the hypotheses | |\n| `show P` | restates the goal in a definitionally equal form (readability) | |\n| `specialize h 2` | applies a universal hypothesis to a value | |\n| `exfalso` | replaces the goal by `False` | |\n| `by_contra h` | proof by contradiction: adds the negation of the goal | |\n| `push_neg` | pushes negations inwards: `¬ ∀ x, P x` becomes `∃ x, ¬ P x` | |\n| `contradiction` | closes the goal if the hypotheses contradict each other directly | `h : P` and `h' : ¬ P` |\n\n## Induction and cases\n\n```lean\ntheorem sum_odds (n : ℕ) : ∑ i in Finset.range n, (2 * i + 1) = n ^ 2 := by\n  induction n with\n  | zero => simp\n  | succ n ih =>\n    rw [Finset.sum_range_succ, ih]\n    ring\n```\n\n`induction n with | zero => … | succ n ih => …` produces the base case and the inductive step; `ih` is the induction\nhypothesis. `rcases`/`cases` handle the cases of an inductive type or of a disjunction; `interval_cases n` enumerates\nthe values of an integer bounded by the hypotheses. (In the “Current Lean” workspace, write\n`∑ i ∈ Finset.range n`.)\n\n## Rewriting and simplifying\n\n| Tactic | Effect | Fails when |\n|---|---|---|\n| `rw [h]` | replaces the left-hand side of `h : a = b` by the right-hand side in the goal; `rw [← h]` the other way; `rw [h] at h'` in a hypothesis | the pattern does not occur literally in the goal |\n| `simp` | simplifies with Mathlib's lemmas tagged `@[simp]`; closes the goal if it becomes trivial | there is nothing to simplify |\n| `simp only [a, b]` | simplifies with these lemmas only: more predictable and faster | |\n| `simp at h` | simplifies a hypothesis | |\n| `norm_num` | computes with explicit numbers: `2 ^ 10 = 1024`, `(7 : ℝ) / 2 > 3`, `Nat.Prime 97` | the goal contains variables it cannot eliminate |\n| `field_simp` | clears denominators in a field (often needs `h : x ≠ 0`) | |\n| `unfold f` | unfolds a definition | |\n| `ext x` | equality of functions or sets: reduces to every `x` | |\n\n## Arithmetic and inequalities\n\n| Tactic | Domain | Does not do |\n|---|---|---|\n| `ring` | equalities in a commutative ring: `(a + b) ^ 2 = a ^ 2 + 2 * a * b + b ^ 2` | inequalities; equalities that need a hypothesis |\n| `linarith` | **linear** combinations of hypotheses and inequalities, over an ordered field (`ℚ`, `ℝ`); often works on `ℕ` and `ℤ` too | products of variables |\n| `nlinarith` | like `linarith`, adding products of hypotheses; help it by giving facts: `nlinarith [sq_nonneg (a - b)]` | guarantees: it is a heuristic |\n| `positivity` | goals `0 < e`, `0 ≤ e`, `e ≠ 0` when the shape of `e` shows it (squares, sums of positives, exponentials…) | use complicated hypotheses |\n| `omega` | **exact** linear arithmetic over `ℕ` and `ℤ`, with `/` and `%` by constants | products of variables; the reals |\n| `decide` | decidable propositions on **concrete** values: `Nat.Prime 7` if the instance allows it, `2 ∣ 10` | free variables; large computations (slow) |\n| `gcongr` | “same shape on both sides”: `a ≤ b → a + c ≤ b + c`, leaves the comparisons of the pieces | |\n\nExample:\n\n```lean\ntheorem two_mul_le_sq_add_sq (a b : ℝ) : 2 * a * b ≤ a ^ 2 + b ^ 2 := by\n  nlinarith [sq_nonneg (a - b)]\n```\n\nHere $a^2 + b^2 - 2ab = (a-b)^2 \\ge 0$: the fact given to `nlinarith` suffices, the combination is linear in that\nfact.\n\n## Searching\n\n| Tactic | Effect |\n|---|---|\n| `exact?` | searches Mathlib for a lemma that closes the goal and suggests `exact …` |\n| `apply?` | suggests applicable lemmas |\n| `aesop` | automatic proof search (rules and `simp`) |\n| `tauto` | propositional logic |\n\nMadalean **rejects `exact?` and `apply?` in a final proof**: they are search tools, to be replaced by the lemma they\nfind. They remain useful in a notebook or in a Lean block of a note.\n\n## Reading an error\n\n| Lean's message | Usual meaning |\n|---|---|\n| `unknown identifier 'foo'` / `unknown constant` | the name does not exist in this Mathlib version (renamed, or invented by the model) |\n| `type mismatch` | the term does not have the expected type: often a missing `ℕ`/`ℝ` conversion |\n| `unsolved goals` | the proof stops while goals remain (shown) |\n| `linarith failed` | the given hypotheses are not enough linearly: add facts |\n| `motive is not type correct` | `rw` cannot rewrite at this place; try `simp only` or `conv` |\n| `maximum recursion depth` / `deterministic timeout` | a tactic searches too long: make the proof more explicit |\n| `declaration uses 'sorry'` | the proof contains a gap: it is not accepted |\n",text:`First tactics A proof in tactic mode (:= by …) is a sequence of instructions that transform the goal (what remains to be proved, shown after ⊢) until nothing is left. The examples assume import Mathlib. The exact behaviour of a tactic depends on the Mathlib version; what follows holds for both Madalean workspaces unless stated. Structuring Tactic Effect Example goal intro x introduces a variable or hypothesis: for ∀ x, P x or P → Q ⊢ ∀ n : ℕ, n + 0 = n → intro n exact e closes the goal with a term of exactly the right type exact ha when ha : P and ⊢ P apply f reduces the goal to the hypotheses of f ⊢ 0 < a b → apply mulpos leaves 0 < a and 0 < b refine ⟨?, ?⟩ like exact, with holes ? that become goals constructor splits P ∧ Q (two goals) or P ↔ Q (both directions) use 3 provides the witness of an ∃ ⊢ ∃ n : ℕ, n n = 9 → use 3 obtain ⟨x, hx⟩ := h unpacks h : ∃ x, P x (or h : P ∧ Q) rcases h with h1 h2 cases of a disjunction h : P ∨ Q left, right chooses one side of an ∨ to prove have h : P := by … proves an intermediate result and adds it to the hypotheses show P restates the goal in a definitionally equal form (readability) specialize h 2 applies a universal hypothesis to a value exfalso replaces the goal by False bycontra h proof by contradiction: adds the negation of the goal pushneg pushes negations inwards: ¬ ∀ x, P x becomes ∃ x, ¬ P x contradiction closes the goal if the hypotheses contradict each other directly h : P and h' : ¬ P Induction and cases induction n with zero => … succ n ih => … produces the base case and the inductive step; ih is the induction hypothesis. rcases/cases handle the cases of an inductive type or of a disjunction; intervalcases n enumerates the values of an integer bounded by the hypotheses. (In the “Current Lean” workspace, write ∑ i ∈ Finset.range n.) Rewriting and simplifying Tactic Effect Fails when rw [h] replaces the left-hand side of h : a = b by the right-hand side in the goal; rw [← h] the other way; rw [h] at h' in a hypothesis the pattern does not occur literally in the goal simp simplifies with Mathlib's lemmas tagged @[simp]; closes the goal if it becomes trivial there is nothing to simplify simp only [a, b] simplifies with these lemmas only: more predictable and faster simp at h simplifies a hypothesis normnum computes with explicit numbers: 2 ^ 10 = 1024, (7 : ℝ) / 2 > 3, Nat.Prime 97 the goal contains variables it cannot eliminate fieldsimp clears denominators in a field (often needs h : x ≠ 0) unfold f unfolds a definition ext x equality of functions or sets: reduces to every x Arithmetic and inequalities Tactic Domain Does not do ring equalities in a commutative ring: (a + b) ^ 2 = a ^ 2 + 2 a b + b ^ 2 inequalities; equalities that need a hypothesis linarith linear combinations of hypotheses and inequalities, over an ordered field (ℚ, ℝ); often works on ℕ and ℤ too products of variables nlinarith like linarith, adding products of hypotheses; help it by giving facts: nlinarith [sqnonneg (a - b)] guarantees: it is a heuristic positivity goals 0 < e, 0 ≤ e, e ≠ 0 when the shape of e shows it (squares, sums of positives, exponentials…) use complicated hypotheses omega exact linear arithmetic over ℕ and ℤ, with / and % by constants products of variables; the reals decide decidable propositions on concrete values: Nat.Prime 7 if the instance allows it, 2 ∣ 10 free variables; large computations (slow) gcongr “same shape on both sides”: a ≤ b → a + c ≤ b + c, leaves the comparisons of the pieces Example: Here $a^2 + b^2 - 2ab = (a-b)^2 \\ge 0$: the fact given to nlinarith suffices, the combination is linear in that fact. Searching Tactic Effect exact? searches Mathlib for a lemma that closes the goal and suggests exact … apply? suggests applicable lemmas aesop automatic proof search (rules and simp) tauto propositional logic Madalean rejects exact? and apply? in a final proof: they are search tools, to be replaced by the lemma they find. They remain useful in a notebook or in a Lean block of a note. Reading an error Lean's message Usual meaning unknown identifier 'foo' / unknown constant the name does not exist in this Mathlib version (renamed, or invented by the model) type mismatch the term does not have the expected type: often a missing ℕ/ℝ conversion unsolved goals the proof stops while goals remain (shown) linarith failed the given hypotheses are not enough linearly: add facts motive is not type correct rw cannot rewrite at this place; try simp only or conv maximum recursion depth / deterministic timeout a tactic searches too long: make the proof more explicit declaration uses 'sorry' the proof contains a gap: it is not accepted`},{id:`shortcuts`,lang:`en`,title:`Keyboard shortcuts`,order:430,section:`reference`,audience:`all`,summary:`Keyboard shortcuts of the interface and of the Lean editor.`,source:`en/shortcuts.md`,site_path:`en/shortcuts.html`,headings:[{level:1,text:`Keyboard shortcuts`,id:`keyboard-shortcuts`},{level:2,text:`Everywhere`,id:`everywhere`},{level:2,text:`Palette, menus and tabs`,id:`palette-menus-and-tabs`},{level:2,text:`Send, run, new line`,id:`send-run-new-line`},{level:2,text:`Editors (statement, Lean, dossier thread)`,id:`editors-statement-lean-dossier-thread`},{level:2,text:`Desktop application`,id:`desktop-application`}],images:[],verify:[],body:"# Keyboard shortcuts\n\nOn macOS, read `Ctrl` as `⌘`. Single-key shortcuts (`/`, `n`) do not apply while you type in a text field.\n\n## Everywhere\n\n| Shortcut | Action |\n|---|---|\n| `Ctrl+K` or `/` | open the palette: find a dossier, a command, a help page |\n| `n` | new dossier (*Research* mode only) |\n| `Esc` | close the open menu, palette or panel; a click elsewhere closes it too |\n| `Ctrl+Shift+1` | show or hide the project bar (Dossiers · Sources · Notes…) |\n| `Tab`, `Shift+Tab` | move between controls; a “Skip to content” link comes first |\n\n## Palette, menus and tabs\n\n| Shortcut | Action |\n|---|---|\n| `↑` `↓` | choose in the palette or a menu |\n| `Enter` | run the chosen item |\n| `Home`, `End` | first, last item of a menu |\n| `←` `→`, `Home`, `End` | move between the Statement, Lean translation and Proof steps of a dossier |\n\n## Send, run, new line\n\nIn every field that sends something (new statement, follow-up request, question on a source, explanation, hints,\nresearch instruction, translation correction, Calcul request, notebook assistant), **`Enter` sends** and\n**`Shift+Enter` starts a new line**. A small line under the field reminds you.\n\n| Field | `Enter` | `Shift+Enter` |\n|---|---|---|\n| sending fields (above) | send | new line |\n| Calcul code cell | run the cell | new line (keeping the indentation); `Tab` / `Shift+Tab` indents |\n| Lean proof edited by hand, exercise fix | check with Lean | new line |\n| article, note body, text cell, profile | new line | new line |\n\nIn the article and in notes, `Enter` stays a new line: long texts are written there. On a phone or a tablet without\na keyboard, `Enter` is a new line everywhere and the field's button sends. `Ctrl+Enter` sends too.\n\n## Editors (statement, Lean, dossier thread)\n\n| Shortcut | Action |\n|---|---|\n| `\\le` then `Space` or `Tab` | insert a symbol: `\\forall` → `∀`, `\\R` → `ℝ`, `\\le` → `≤`, `\\to` → `→`, `\\mid` → `∣` (full list in the “Glossary” screen) |\n| `Ctrl+Z`, `Ctrl+Shift+Z` | undo, redo |\n| `Tab`, `Shift+Tab` | indent, unindent (in the Lean editor) |\n\nIn a natural-language statement, abbreviations are not expanded between `$…$`, to keep the LaTeX.\n\n## Desktop application\n\n| Shortcut | Action |\n|---|---|\n| `Ctrl+Shift+K` | change server |\n",text:`Keyboard shortcuts On macOS, read Ctrl as ⌘. Single-key shortcuts (/, n) do not apply while you type in a text field. Everywhere Shortcut Action Ctrl+K or / open the palette: find a dossier, a command, a help page n new dossier (Research mode only) Esc close the open menu, palette or panel; a click elsewhere closes it too Ctrl+Shift+1 show or hide the project bar (Dossiers · Sources · Notes…) Tab, Shift+Tab move between controls; a “Skip to content” link comes first Palette, menus and tabs Shortcut Action ↑ ↓ choose in the palette or a menu Enter run the chosen item Home, End first, last item of a menu ← →, Home, End move between the Statement, Lean translation and Proof steps of a dossier Send, run, new line In every field that sends something (new statement, follow-up request, question on a source, explanation, hints, research instruction, translation correction, Calcul request, notebook assistant), Enter sends and Shift+Enter starts a new line. A small line under the field reminds you. Field Enter Shift+Enter sending fields (above) send new line Calcul code cell run the cell new line (keeping the indentation); Tab / Shift+Tab indents Lean proof edited by hand, exercise fix check with Lean new line article, note body, text cell, profile new line new line In the article and in notes, Enter stays a new line: long texts are written there. On a phone or a tablet without a keyboard, Enter is a new line everywhere and the field's button sends. Ctrl+Enter sends too. Editors (statement, Lean, dossier thread) Shortcut Action \\le then Space or Tab insert a symbol: \\forall → ∀, \\R → ℝ, \\le → ≤, \\to → →, \\mid → ∣ (full list in the “Glossary” screen) Ctrl+Z, Ctrl+Shift+Z undo, redo Tab, Shift+Tab indent, unindent (in the Lean editor) In a natural-language statement, abbreviations are not expanded between $…$, to keep the LaTeX. Desktop application Shortcut Action Ctrl+Shift+K change server`},{id:`measures`,lang:`en`,title:`Measurements: what Madalean proves, how fast, at what cost`,order:440,section:`reference`,audience:`researcher`,summary:`The built-in benchmark — miniF2F, PutnamBench and a smoke set — counts only the proofs a fresh strict Lean accepts, with the time and the cost per proof.`,source:`en/measures.md`,site_path:`en/measures.html`,headings:[{level:1,text:`Measurements`,id:`measurements`},{level:2,text:`What counts as “proved”`,id:`what-counts-as-proved`},{level:2,text:`The problem sets`,id:`the-problem-sets`},{level:2,text:`The strategies`,id:`the-strategies`},{level:2,text:`Cost`,id:`cost`},{level:2,text:`Running a measurement`,id:`running-a-measurement`},{level:2,text:`What these figures do not say`,id:`what-these-figures-do-not-say`}],images:[],verify:[],body:`# Measurements

Madalean measures itself. The \`madalean bench\` command feeds formal statements through **the same pipeline as the
application** (Mathlib search, tournament of free models, conductor…), without the interface, and writes for each
problem: proved or not, number of attempts, time, tokens, cost, the model that found the proof, Lean time.

Published results are on the “Measurements” page of the site (link at the bottom of every page of the site). They
are redone for each version.

## What counts as “proved”

One thing only: the proof found is compiled again **on its own**, by a fresh Lean, with the application's strict
verdict — no \`sorry\`, no added axiom, the standard axioms only — and it must prove **the statement that was given**,
not another one. The model's word, or an intermediate check, never counts.

A statement that the workspace's Lean does not accept (the set was written for another Mathlib version) is counted
**apart**: it is not a failed proof.

## The problem sets

| Set | Content | Licence |
|---|---|---|
| Smoke set | 20 statements written for Madalean, from logic to topology: checks that the whole pipeline works | Apache-2.0 |
| miniF2F | 488 high-school and olympiad statements (244 “valid”, 244 “test”) | MIT |
| PutnamBench | 672 statements from the Putnam competition (1962–2025) | Apache-2.0 |

miniF2F and PutnamBench are not copied into Madalean: \`madalean bench fetch\` downloads them from their public
repository, at a pinned version, into a cache folder; the content hash is checked at each read. PutnamBench asks
that proofs not be published: only counts are published.

## The strategies

| Strategy | What runs |
|---|---|
| \`mathlib\` | the Mathlib search alone, with no model at all |
| \`tournament\` | the application's default: Mathlib first, then the tournament of free models |
| \`conductor\` | the tournament directed by the conductor |
| \`single\` | a single model that you name |
| \`goedel-local\` | Goedel-Prover on the machine's graphics card |

## Cost

By default, **no paid model can be called**: the benchmark gives the engine the keys of free providers only. Paid
models are used only if you give a budget (\`--paid-budget\`, in dollars); that budget is a hard cap for the whole
run. The cost shown is that of paid calls at list price; free models and Mathlib cost $0.

## Running a measurement

\`\`\`
madalean bench sets
madalean bench fetch minif2f
madalean bench check minif2f --split valid --workspace lean-prover49
madalean bench run minif2f --split valid --sample 50 --seed 1 --strategy tournament --time-budget 30
\`\`\`

An interrupted run resumes where it stopped: run the same command again. The benchmark works in its own folder: it
touches neither your projects, nor your settings, nor the running server, and loads no model on the graphics card
except with \`goedel-local\`.

## What these figures do not say

- A sample of 50 problems gives an estimate within about ten points.
- Limits are short (a few minutes and a few attempts per problem): this is the workshop as it is used, not the
  maximum reachable with thousands of attempts.
- Online models change and their answers cannot be reproduced exactly: the order of the problems and the sample
  are reproducible, the models' answers are not.
- Statements are given in Lean: the translation from French or English is not measured here.
`,text:`Measurements Madalean measures itself. The madalean bench command feeds formal statements through the same pipeline as the application (Mathlib search, tournament of free models, conductor…), without the interface, and writes for each problem: proved or not, number of attempts, time, tokens, cost, the model that found the proof, Lean time. Published results are on the “Measurements” page of the site (link at the bottom of every page of the site). They are redone for each version. What counts as “proved” One thing only: the proof found is compiled again on its own, by a fresh Lean, with the application's strict verdict — no sorry, no added axiom, the standard axioms only — and it must prove the statement that was given, not another one. The model's word, or an intermediate check, never counts. A statement that the workspace's Lean does not accept (the set was written for another Mathlib version) is counted apart: it is not a failed proof. The problem sets Set Content Licence Smoke set 20 statements written for Madalean, from logic to topology: checks that the whole pipeline works Apache-2.0 miniF2F 488 high-school and olympiad statements (244 “valid”, 244 “test”) MIT PutnamBench 672 statements from the Putnam competition (1962–2025) Apache-2.0 miniF2F and PutnamBench are not copied into Madalean: madalean bench fetch downloads them from their public repository, at a pinned version, into a cache folder; the content hash is checked at each read. PutnamBench asks that proofs not be published: only counts are published. The strategies Strategy What runs mathlib the Mathlib search alone, with no model at all tournament the application's default: Mathlib first, then the tournament of free models conductor the tournament directed by the conductor single a single model that you name goedel-local Goedel-Prover on the machine's graphics card Cost By default, no paid model can be called: the benchmark gives the engine the keys of free providers only. Paid models are used only if you give a budget (--paid-budget, in dollars); that budget is a hard cap for the whole run. The cost shown is that of paid calls at list price; free models and Mathlib cost $0. Running a measurement An interrupted run resumes where it stopped: run the same command again. The benchmark works in its own folder: it touches neither your projects, nor your settings, nor the running server, and loads no model on the graphics card except with goedel-local. What these figures do not say - A sample of 50 problems gives an estimate within about ten points. - Limits are short (a few minutes and a few attempts per problem): this is the workshop as it is used, not the maximum reachable with thousands of attempts. - Online models change and their answers cannot be reproduced exactly: the order of the problems and the sample are reproducible, the models' answers are not. - Statements are given in Lean: the translation from French or English is not measured here.`}],s={schema:e,source:t,site_url:n,languages:r,sections:i,site_links:a,pages:o};export{s as default,r as languages,o as pages,e as schema,i as sections,a as site_links,n as site_url,t as source};