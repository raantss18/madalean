"""English catalogue: French source text -> English. Checked by tests/test_i18n.py (every key used in the code exists)."""
EN: dict[str, str] = {
    # ---------------------------------------------------------------- navigation, window, status bar
    "🏠  Accueil": "🏠  Home",
    "∀  Lean": "∀  Lean",
    "📚  Bibliothèque": "📚  Library",
    "📦  Modèles": "📦  Models",
    "🖥  Serveur": "🖥  Server",
    "⚙  Système": "⚙  System",
    "❓  Aide": "❓  Help",
    "Lean AI Station": "Lean AI Station",
    "Lean pour les débutants : à quoi ça sert, comment faire (F1)": "Lean for beginners: what it is for, how to use it (F1)",
    "Changer la langue de l'interface et des réponses de l'IA": "Change the language of the interface and of the AI's answers",
    "État du modèle d'IA (cliquez sur « Serveur » pour les détails)": "AI model status (click “Server” for details)",
    "Mode hors-ligne : modifiable dans « Système »": "Offline mode: change it in “System”",
    "🟢 {model}  ·  {n} couches GPU": "🟢 {model}  ·  {n} GPU layers",
    "🟡 Chargement du modèle…": "🟡 Loading the model…",
    "🟠 Arrêt du modèle…": "🟠 Stopping the model…",
    "⚪ Modèle non chargé (chargement automatique au besoin)": "⚪ Model not loaded (loaded automatically when needed)",
    "GPU {u:.1f}/{t:.1f} Go · {temp} °C · {util} %": "GPU {u:.1f}/{t:.1f} GB · {temp} °C · {util} %",
    "GPU : —": "GPU: —",
    "🔒 Hors-ligne": "🔒 Offline",
    "🌐 En ligne": "🌐 Online",
    "Lean AI Station est déjà ouvert : fenêtre existante mise au premier plan.":
        "Lean AI Station is already open: the existing window was brought to the front.",
    "settings.json illisible : réglages par défaut rétablis (copie conservée).":
        "settings.json unreadable: default settings restored (a copy was kept).",
    "Aide — Lean pour les débutants": "Help — Lean for beginners",
    "Fermer": "Close",

    # ---------------------------------------------------------------- widgets
    "Fermer ce message": "Close this message",
    "Afficher les détails": "Show details",
    "Masquer les détails": "Hide details",
    "Annuler": "Undo",
    "Arrêter cette opération (Échap)": "Stop this operation (Esc)",

    # ---------------------------------------------------------------- errors.py
    "Le moteur d'IA s'est arrêté": "The AI engine stopped",
    "Le serveur du modèle s'est fermé de façon inattendue. Cliquez sur « Redémarrer le modèle » pour le relancer ; votre travail n'est pas perdu.":
        "The model server closed unexpectedly. Click “Restart the model” to start it again; your work is not lost.",
    "Redémarrer le modèle": "Restart the model",
    "Le modèle n'est pas chargé": "The model is not loaded",
    "Il faut un modèle chargé pour générer une preuve. Cliquez sur « Charger le modèle » puis relancez.":
        "A loaded model is needed to generate a proof. Click “Load the model”, then try again.",
    "Charger le modèle": "Load the model",
    "Mémoire de la carte graphique insuffisante": "Not enough graphics memory",
    "Le modèle ne tient pas sur la carte graphique, même après réduction automatique. Fermez les jeux ou logiciels qui utilisent la carte, ou choisissez un modèle plus petit (Q4_K_M) dans « Modèles ».":
        "The model does not fit on the graphics card, even after automatic reduction. Close games or programs using the card, or choose a smaller model (Q4_K_M) in “Models”.",
    "Réessayer": "Try again",
    "Choisir un modèle": "Choose a model",
    "Fichier de modèle illisible": "Unreadable model file",
    "Le fichier du modèle est absent, incomplet ou abîmé. Choisissez un autre modèle dans « Modèles » ou retéléchargez-le.":
        "The model file is missing, incomplete or damaged. Choose another model in “Models” or download it again.",
    "Moteur d'IA introuvable": "AI engine not found",
    "Le programme llama-server est introuvable. Ouvrez « Système » et cliquez sur « Recompiler ».":
        "The llama-server program cannot be found. Open “System” and click “Rebuild”.",
    "Ouvrir Système": "Open System",
    "Port réseau occupé": "Network port in use",
    "Aucun port local libre n'a été trouvé pour le serveur. Changez le port dans « Serveur ».":
        "No free local port was found for the server. Change the port in “Server”.",
    "Ouvrir Serveur": "Open Server",
    "Le modèle met trop de temps à se charger": "The model takes too long to load",
    "Le chargement a dépassé 5 minutes. Réessayez ; si cela se reproduit, choisissez un modèle plus petit.":
        "Loading took more than 5 minutes. Try again; if it happens again, choose a smaller model.",
    "L'espace de travail Lean n'est pas prêt": "The Lean workspace is not ready",
    "Lean ne trouve pas Mathlib dans l'espace choisi. Choisissez un autre espace en haut de l'onglet Lean, ou ouvrez « Système » pour le réparer.":
        "Lean cannot find Mathlib in the chosen workspace. Choose another workspace (⚙ Options in the Lean tab), or open “System” to repair it.",
    "La génération a échoué": "Generation failed",
    "Le modèle a renvoyé une erreur. Réessayez ; si cela continue, redémarrez le modèle.":
        "The model returned an error. Try again; if it keeps happening, restart the model.",
    "Carte graphique non détectée": "Graphics card not detected",
    "La carte NVIDIA n'est pas disponible : le modèle fonctionnera sur le processeur, beaucoup plus lentement. Redémarrer l'ordinateur règle souvent ce problème.":
        "The NVIDIA card is not available: the model will run on the processor, much more slowly. Restarting the computer often fixes this.",
    "Disque presque plein": "Disk almost full",
    "Il reste peu d'espace disque. Libérez de la place avant de télécharger ou d'importer un modèle.":
        "Little disk space is left. Free some space before downloading or importing a model.",
    "Session restaurée": "Session restored",
    "L'application s'était fermée brutalement. Votre texte et vos réglages ont été restaurés.":
        "The application had closed abruptly. Your text and settings have been restored.",
    "Mode hors-ligne actif": "Offline mode is on",
    "Le téléchargement est désactivé en mode hors-ligne. Désactivez-le dans « Système » si vous avez Internet.":
        "Downloading is disabled in offline mode. Turn it off in “System” if you have Internet.",
    "Le traducteur français → Lean n'est pas installé": "The natural language → Lean translator is not installed",
    "Pour écrire votre problème en français, il faut le modèle « Goedel-Formalizer » (≈ 5 Go). Avec Internet : ouvrez « Modèles » → téléchargez « mradermacher/Goedel-Formalizer-V2-8B-GGUF ». Sinon, écrivez directement l'énoncé en Lean dans l'onglet « Énoncé Lean ».":
        "To write your problem in plain language you need the “Goedel-Formalizer” model (≈ 5 GB). With Internet: open “Models” → download “mradermacher/Goedel-Formalizer-V2-8B-GGUF”. Otherwise, write the statement directly in Lean in the “Lean statement” tab.",
    "Le modèle d'explication n'est pas installé": "The explanation model is not installed",
    "Pour expliquer une preuve en français, il faut le modèle « Qwen3-8B » (≈ 5 Go). Avec Internet : ouvrez « Modèles » → téléchargez « Qwen/Qwen3-8B-GGUF » (fichier Qwen3-8B-Q4_K_M.gguf).":
        "To explain a proof in plain language you need the “Qwen3-8B” model (≈ 5 GB). With Internet: open “Models” → download “Qwen/Qwen3-8B-GGUF” (file Qwen3-8B-Q4_K_M.gguf).",
    "Énoncé incomplet": "Incomplete statement",
    "Ouvrir Modèles": "Open Models",

    # ---------------------------------------------------------------- examples
    "Et logique": "Logical and",
    "Initiation": "Beginner",
    "Si P et Q sont vraies, alors « P et Q » est vraie.": "If P and Q are true, then “P and Q” is true.",
    "Somme de deux nombres pairs": "Sum of two even numbers",
    "Collège": "Middle school",
    "La somme de deux entiers pairs est paire.": "The sum of two even integers is even.",
    "Identité remarquable": "Square of a sum",
    "(a + b)² = a² + 2ab + b² pour tous réels a, b.": "(a + b)² = a² + 2ab + b² for all real numbers a, b.",
    "Inégalité 2ab ≤ a² + b²": "Inequality 2ab ≤ a² + b²",
    "Lycée": "High school",
    "Conséquence de (a − b)² ≥ 0.": "A consequence of (a − b)² ≥ 0.",
    "Équation de cercle": "Circle equation",
    "Si x² + y² = 2x − 4y − 5, alors x + y = −1 (exemple officiel de Goedel-Prover).":
        "If x² + y² = 2x − 4y − 5, then x + y = −1 (official Goedel-Prover example).",
    "Inégalité triangulaire": "Triangle inequality",
    "Licence": "University",
    "|a + b| ≤ |a| + |b| pour tous réels a, b.": "|a + b| ≤ |a| + |b| for all real numbers a, b.",
    "Produit de trois entiers consécutifs": "Product of three consecutive integers",
    "n(n + 1)(n + 2) est divisible par 6.": "n(n + 1)(n + 2) is divisible by 6.",
    "Volume d'un cône (miniF2F)": "Volume of a cone (miniF2F)",
    "Olympiade": "Olympiad",
    "mathd_algebra_478 : B = 30, h = 6,5 et V = Bh/3 donnent V = 65.": "mathd_algebra_478: B = 30, h = 6.5 and V = Bh/3 give V = 65.",

    # ---------------------------------------------------------------- leancheck / services / workspaces / gguf
    "« sorry » (preuve laissée en suspens)": "“sorry” (unfinished proof)",
    "« admit » (preuve laissée en suspens)": "“admit” (unfinished proof)",
    "déclaration d'un nouvel axiome": "declaration of a new axiom",
    "« apply? / exact? » (recherche non finalisée)": "“apply? / exact?” (unfinished search)",
    "« #exit »": "“#exit”",
    "code non vérifié (unsafe / extern)": "unchecked code (unsafe / extern)",
    "méta-programmation": "meta-programming",
    "désactivation du noyau": "kernel check disabled",
    "L'éditeur est vide : écrivez un énoncé ou choisissez un exemple.": "The editor is empty: write a statement or choose an example.",
    "Aucun « theorem », « lemma » ou « example » trouvé dans l'éditeur.": "No “theorem”, “lemma” or “example” found in the editor.",
    "L'énoncé doit se terminer par « := by sorry ».": "The statement must end with “:= by sorry”.",
    "Impossible de trouver le nom du théorème.": "Cannot find the theorem's name.",
    "Énoncé mal formé (il faut « theorem … := by sorry »).": "Malformed statement (expected “theorem … := by sorry”).",
    "La réponse du modèle ne contient pas de « theorem … := by ».": "The model's answer contains no “theorem … := by”.",
    "Lean a trouvé 1 erreur.": "Lean found 1 error.",
    "Lean a trouvé {n} erreurs.": "Lean found {n} errors.",
    "Lean s'est arrêté anormalement.": "Lean stopped abnormally.",
    "Refusé : la preuve contient « sorry ».": "Rejected: the proof contains “sorry”.",
    "Refusé : {why}.": "Rejected: {why}.",
    "Refusé : impossible de contrôler les axiomes utilisés.": "Rejected: the axioms used could not be checked.",
    "Refusé : axiomes non standard ({ax}).": "Rejected: non-standard axioms ({ax}).",
    "Preuve acceptée par Lean ✔": "Proof accepted by Lean ✔",
    "Lean accepte le fichier ✔": "Lean accepts the file ✔",
    "Aucune carte graphique NVIDIA utilisable : le modèle tourne sur le processeur (beaucoup plus lent).":
        "No usable NVIDIA graphics card: the model runs on the processor (much slower).",
    "Mémoire graphique limitée : contexte réduit à {c} tokens pour que tout tienne sur la carte.":
        "Limited graphics memory: context reduced to {c} tokens so that everything fits on the card.",
    "Le modèle est trop gros pour la carte graphique : {l}/{n} couches sur la carte, le reste sur le processeur (plus lent). Un modèle plus petit (Q4_K_M) serait plus rapide.":
        "The model is too big for the graphics card: {l}/{n} layers on the card, the rest on the processor (slower). A smaller model (Q4_K_M) would be faster.",
    "Le port {port} est déjà utilisé : le serveur utilise le port {p}.": "Port {port} is already in use: the server uses port {p}.",
    "Aucun port libre à partir de {port}": "No free port from {port}",
    "Le serveur ne répond pas après 5 minutes.": "The server is not responding after 5 minutes.",
    "Mémoire graphique insuffisante : nouvel essai avec un contexte de {n} tokens.":
        "Not enough graphics memory: trying again with a context of {n} tokens.",
    "Mémoire graphique insuffisante : nouvel essai avec {n} couches sur la carte.":
        "Not enough graphics memory: trying again with {n} layers on the card.",
    "Aucune donnée reçue depuis {s} s.": "No data received for {s} s.",
    "Lean n'a pas pu démarrer.": "Lean could not start.",
    "Vérification annulée.": "Check cancelled.",
    "Lean a dépassé le délai ({s} s).": "Lean exceeded the time limit ({s} s).",
    "Mathlib introuvable ou non compilé dans cet espace.": "Mathlib not found or not built in this workspace.",
    "Recherche de preuve arrêtée.": "Proof search stopped.",
    "Aucune preuve trouvée après {n} essais.": "No proof found after {n} attempts.",
    "La génération a échoué.": "Generation failed.",
    "Pas de réponse des modèles en {s} s : adaptation d'un résultat de Mathlib abandonnée.":
        "No answer from the models in {s} s: adapting a Mathlib result abandoned.",
    "Réponse trop longue, coupée avant le code Lean.": "Answer too long, cut off before the Lean code.",
    "Le modèle n'a pas produit de code Lean.": "The model produced no Lean code.",
    "L'IA tournait en rond : essai interrompu, nouvel essai.": "The AI was going round in circles: attempt stopped, new attempt.",
    "Preuve trouvée et vérifiée par Lean (essai {i}).": "Proof found and checked by Lean (attempt {i}).",
    "Traduction arrêtée.": "Translation stopped.",
    "La traduction ne compile pas encore : corrigez-la dans l'éditeur ou reformulez le problème.":
        "The translation does not compile yet: fix it in the editor or rephrase the problem.",
    "La traduction a échoué.": "Translation failed.",
    "L'IA tournait en rond : nouvel essai.": "The AI was going round in circles: new attempt.",
    "Pas d'énoncé Lean dans la réponse : nouvel essai.": "No Lean statement in the answer: new attempt.",
    "Énoncé valide en Lean (à relire)": "Valid Lean statement (to review)",
    "Énoncé traduit : Lean le comprend. Relisez-le avant de prouver.": "Statement translated: Lean understands it. Review it before proving.",
    "L'IA n'a rien écrit : réessayez.": "The AI wrote nothing: try again.",
    "Explication prête.": "Explanation ready.",
    "Explication prête (réponse interrompue : l'IA tournait en rond).": "Explanation ready (answer cut: the AI was going round in circles).",
    "Explication arrêtée.": "Explanation stopped.",
    "nvidia-smi n'a rien renvoyé": "nvidia-smi returned nothing",
    "Le dossier de l'espace de travail est introuvable (pas encore installé ?).": "The workspace folder cannot be found (not installed yet?).",
    "La version de Lean « {tc} » n'est pas installée.": "Lean version “{tc}” is not installed.",
    "Mathlib n'est pas compilé dans cet espace.": "Mathlib is not built in this workspace.",
    "Prouveur (Lean 4.9, Mathlib de Goedel)": "Prover (Lean 4.9, Goedel's Mathlib)",
    "Version exacte utilisée pour entraîner Goedel-Prover-V2 : meilleurs résultats du modèle.":
        "The exact version Goedel-Prover-V2 was trained with: best results from the model.",
    "Lean actuel (Mathlib récent)": "Current Lean (recent Mathlib)",
    "Lean et Mathlib récents, pour le travail quotidien et les cours.": "Recent Lean and Mathlib, for everyday work and teaching.",
    "fichier tronqué": "truncated file",
    "chaîne invalide": "invalid string",
    "ce n'est pas un fichier GGUF": "this is not a GGUF file",
    "version GGUF {v} non prise en charge": "GGUF version {v} not supported",
    "en-tête corrompu": "corrupted header",
    "type inconnu {t}": "unknown type {t}",
    "Tout le document": "Whole document",
    "Théorème": "Theorem",
    "Lemme": "Lemma",
    "Proposition": "Proposition",
    "Corollaire": "Corollary",
    "Exercice": "Exercise",
    "Problème": "Problem",
    "Question": "Question",
    "Affirmation": "Claim",
    "Conjecture": "Conjecture",
    "Énoncé": "Statement",

    # ---------------------------------------------------------------- statuses
    "génération": "writing",
    "compilation": "checking",
    "accepté": "accepted",
    "refusé": "rejected",
    "erreur": "error",
    "annulé": "cancelled",

    # ---------------------------------------------------------------- context / pipeline
    "Impossible d'enregistrer les réglages": "Cannot save the settings",
    "Le disque est peut-être plein ou protégé en écriture.": "The disk may be full or write-protected.",
    "Aucun modèle installé": "No model installed",
    "Aucun fichier de modèle (.gguf) n'a été trouvé. Ouvrez « Modèles » pour en importer un.":
        "No model file (.gguf) was found. Open “Models” to import one.",
    "Réglage automatique": "Automatic adjustment",
    "{n:.1f} Go libres": "{n:.1f} GB free",
    "Une opération est en cours : arrêtez-la d'abord (Échap).": "An operation is running: stop it first (Esc).",
    "Énoncé Lean fourni.": "Lean statement provided.",
    "Énoncé écrit à la main": "Hand-written statement",
    "Énoncé modifié à la main.": "Statement edited by hand.",
    "énoncé": "statement",
    "preuve": "proof",
    "explication": "explanation",
    "Retour à la version {n} de la {what}.": "Back to version {n} of the {what}.",
    "Arrêté à votre demande.": "Stopped at your request.",
    "Étape impossible : le modèle nécessaire n'est pas installé (voir « Modèles »).":
        "Step impossible: the required model is not installed (see “Models”).",
    "Résultats de votre bibliothèque proposés à l'IA : {names}.": "Results from your library offered to the AI: {names}.",
    "Le modèle n'a pas pu être chargé (voir le message en haut).": "The model could not be loaded (see the message at the top).",
    "Interrompu : le moteur d'IA ou Lean ne répond plus. Voir le message en haut, puis renvoyez votre demande.":
        "Interrupted: the AI engine or Lean stopped responding. See the message at the top, then send your request again.",
    "Pas d'énoncé produit. Reformulez le problème (plus précis, avec les hypothèses) ou écrivez l'énoncé Lean vous-même dans l'onglet « Énoncé Lean ».":
        "No statement produced. Rephrase the problem (more precisely, with the hypotheses) or write the Lean statement yourself in the “Lean statement” tab.",
    "L'IA a traduit le problème en Lean et Lean accepte l'énoncé. Relisez-le : la preuve portera exactement sur ce texte.":
        "The AI translated the problem into Lean and Lean accepts the statement. Review it: the proof will be about exactly this text.",
    "Pause : relisez l'énoncé, puis cliquez sur « Prouver cet énoncé ».": "Paused: review the statement, then click “Prove this statement”.",
    "Lean refuse la traduction. Corrigez l'énoncé dans l'onglet « Énoncé Lean », ou demandez une correction ci-dessous.":
        "Lean rejects the translation. Fix the statement in the “Lean statement” tab, or ask for a correction below.",
    "Aucune preuve trouvée après {n} essais. Essayez : « autre méthode », un énoncé plus simple, ou plus d'essais (⚙ Options).":
        "No proof found after {n} attempts. Try: “another method”, a simpler statement, or more attempts (⚙ Options).",
    "Aucune preuve trouvée après {n} essais. Cause probable : {cause}.": "No proof found after {n} attempts. Likely cause: {cause}.",
    "Preuve directe non cherchée : {cause}.": "Direct proof not attempted: {cause}.",
    "le problème est ouvert, d'après l'étude du sens : une preuve directe n'est pas à attendre":
        "the problem is open, according to the study of its meaning: a direct proof is not to be expected",
    "l'affirmation est dite fausse dans l'étude du sens": "the claim is said to be false in the study of its meaning",
    "la traduction Lean est mise en doute": "the Lean translation is doubtful",
    "les fournisseurs de modèles n'ont pas répondu : ce n'est pas un échec mathématique":
        "the model providers did not answer: this is not a mathematical failure",
    "le budget de recherche est épuisé": "the search budget is used up",
    "plusieurs noms cherchés n'existent pas dans ce Mathlib : une théorie manque peut-être":
        "several names that were tried do not exist in this Mathlib: a theory may be missing",
    "indéterminée": "undetermined",
    "conjonction": "conjunction",
    "équivalence": "equivalence",
    "disjonction de cas": "case analysis",
    "Découpage sans modèle ({pattern}) : {n} morceaux, {k} prouvés directement par Lean.":
        "Split without a model ({pattern}): {n} parts, {k} proved directly by Lean.",
    "Découpage en lemmes : {n} vérifiés par Lean, {m} encore ouverts.": "Split into lemmas: {n} verified by Lean, {m} still open.",
    "Lemmes intermédiaires vérifiés par Lean, gardés pour les essais suivants : {n}.":
        "Intermediate lemmas verified by Lean, kept for the next attempts: {n}.",
    "Recherche dans Mathlib.": "Search in Mathlib.",
    "Certificat par le calcul.": "Certificate by computation.",
    "Découpage sans modèle ({pattern}) : {k} morceaux sur {n} prouvés.": "Split without a model ({pattern}): {k} of {n} parts proved.",
    "Recherche par lemmes : {n} vérifiés, {m} ouverts.": "Search through lemmas: {n} verified, {m} open.",
    "Essais directs : {models} ({n} essais).": "Direct attempts: {models} ({n} attempts).",
    "Aucun essai direct : problème ouvert ou dit faux, sans budget demandé.":
        "No direct attempt: the problem is open or said to be false, and no budget was requested.",
    "Arrêt : plus aucun progrès.": "Stopped: no more progress.",
    "Essayé, dans l'ordre": "Tried, in order",
    "Établi (vérifié par Lean)": "Established (verified by Lean)",
    "Rien de plus que l'énoncé.": "Nothing beyond the statement.",
    "Où cela bloque": "Where it is stuck",
    "Aucun but précis n'a été relevé.": "No precise goal was recorded.",
    "Cause probable": "Likely cause",
    "Preuve trouvée et vérifiée par Lean (essai {i}, {s:.0f} s).": "Proof found and checked by Lean (attempt {i}, {s:.0f} s).",
    "Ajouté à votre bibliothèque sous le nom « {name} » : réutilisable dans vos prochaines preuves.":
        "Added to your library as “{name}”: reusable in your next proofs.",
    "Explication rédigée par l'IA (la preuve Lean fait foi).": "Explanation written by the AI (the Lean proof is what counts).",

    # ---------------------------------------------------------------- home
    "Vous décrivez un problème de mathématiques ; l'IA l'écrit dans le langage <b>Lean</b> puis cherche une preuve ; <b>Lean</b>, un logiciel de vérification, contrôle chaque ligne. Une preuve n'est jamais affichée comme « réussie » sans son feu vert.<br>Rien n'est envoyé sur Internet : l'IA est un fichier installé chez vous, exécuté par la carte graphique de l'ordinateur (à défaut, par son processeur).":
        "You describe a mathematics problem; the AI writes it in the <b>Lean</b> language and searches for a proof; <b>Lean</b>, a proof-checking program, verifies every line. A proof is never shown as “successful” without its approval.<br>Nothing is sent over the Internet: the AI is a file installed on your computer, run by its graphics card (or, failing that, by its processor).",
    "Quel problème voulez-vous prouver ?": "Which problem do you want to prove?",
    "Écrivez-le comme vous le diriez à un collègue, en français ou en anglais.\nExemple : « Montrer que la somme de deux entiers pairs est paire. »\nFormules LaTeX acceptées : $a^2 + b^2 \\ge 2ab$.":
        "Write it as you would say it to a colleague, in English or French.\nExample: “Show that the sum of two even integers is even.”\nLaTeX formulas are welcome: $a^2 + b^2 \\ge 2ab$.",
    "✨  Prouver un théorème": "✨  Prove a theorem",
    "L'IA traduit votre problème en Lean, cherche une preuve vérifiée par Lean, puis l'explique":
        "The AI translates your problem into Lean, searches for a proof checked by Lean, then explains it",
    "📄 Importer un fichier .tex…": "📄 Import a .tex file…",
    "Prendre un théorème, un lemme ou un exercice dans un document LaTeX (vous pouvez aussi glisser le .tex sur la fenêtre)":
        "Take a theorem, lemma or exercise from a LaTeX document (you can also drop the .tex file on the window)",
    "Je sais écrire du Lean": "I can write Lean",
    "Ouvrir directement l'éditeur Lean (Ctrl+2)": "Open the Lean editor directly (Ctrl+2)",
    "Vous décrivez": "You describe",
    "Avec vos mots, ou en important un .tex. Vous pouvez aussi écrire directement du Lean.":
        "In your own words, or by importing a .tex file. You can also write Lean directly.",
    "L'IA traduit en Lean": "The AI translates into Lean",
    "Elle écrit l'énoncé officiel. Il reste affiché : vous pouvez le relire et demander une correction à tout moment.":
        "It writes the formal statement. The statement stays visible: you can review it and ask for a correction at any time.",
    "L'IA prouve, Lean vérifie": "The AI proves, Lean checks",
    "Si Lean refuse une preuve, l'IA corrige et réessaie. Ensuite : explication en langage courant, export LaTeX.":
        "If Lean rejects a proof, the AI fixes it and tries again. Then: plain-language explanation, LaTeX export.",
    "Ou essayez un exercice : un clic lance la recherche de preuve": "Or try an exercise: one click starts the proof search",
    "Niveau indicatif de l'exercice": "Indicative level of the exercise",
    "▶  Prouver": "▶  Prove",
    "Lance la recherche de preuve pour « {t} »": "Starts the proof search for “{t}”",
    "Prouver : {t}": "Prove: {t}",
    "✍️ Écrivez d'abord votre problème dans la zone ci-dessus (ou importez un .tex).": "✍️ First write your problem in the box above (or import a .tex file).",
    "Importer un fichier LaTeX": "Import a LaTeX file",
    "Fichiers LaTeX (*.tex);;Tous (*)": "LaTeX files (*.tex);;All (*)",
    "🟢 Modèle prêt": "🟢 Model ready",
    "⚪ Le modèle se chargera automatiquement au premier clic": "⚪ The model will load automatically on the first click",
    "⚠️ Aucun modèle installé (voir « Modèles »)": "⚠️ No model installed (see “Models”)",
    "⚠️ Traducteur français → Lean absent : vous pouvez écrire l'énoncé en Lean (voir « Aide »)":
        "⚠️ Natural language → Lean translator missing: you can write the statement in Lean (see “Help”)",
    "Espace Lean : {ws}": "Lean workspace: {ws}",
    "Espace : {ws}": "Workspace: {ws}",
    "⚠️ Aucun espace Lean prêt (voir « Système »)": "⚠️ No Lean workspace ready (see “System”)",

    # ---------------------------------------------------------------- lean page
    "Auto (l'outil choisit)": "Auto (the tool decides)",
    "Corriger l'énoncé": "Fix the statement",
    "Changer la preuve": "Change the proof",
    "Changer l'explication": "Change the explanation",
    "Dossier :": "Dossier:",
    "Chaque preuve est un dossier : son fil de discussion et toutes ses versions sont conservés. Choisissez-en un pour le rouvrir.":
        "Each proof is a dossier: its conversation thread and all its versions are kept. Choose one to reopen it.",
    "＋ Nouveau": "＋ New",
    "Commencer un nouveau problème (Ctrl+N)": "Start a new problem (Ctrl+N)",
    "Renommer ce dossier": "Rename this dossier",
    "Supprimer ce dossier (annulable)": "Delete this dossier (can be undone)",
    "⚙ Options": "⚙ Options",
    "Version de Lean, nombre d'essais, pause après la traduction": "Lean version, number of attempts, pause after translation",
    "⏹ Arrêter": "⏹ Stop",
    "Arrêter l'opération en cours (Échap)": "Stop the current operation (Esc)",
    "Espace Lean :": "Lean workspace:",
    "Version de Lean et de Mathlib utilisée pour vérifier.\n« Prouveur (Lean 4.9) » donne les meilleurs résultats avec Goedel-Prover.":
        "Lean and Mathlib version used for checking.\n“Prover (Lean 4.9)” gives the best results with Goedel-Prover.",
    "Essais :": "Attempts:",
    "Nombre maximal d'essais : après chaque échec, les erreurs de Lean sont renvoyées à l'IA pour qu'elle corrige sa preuve.":
        "Maximum number of attempts: after each failure, Lean's errors are sent back to the AI so it can fix its proof.",
    "Pause pour relire l'énoncé": "Pause to review the statement",
    "Désactivé : traduction, preuve et explication s'enchaînent sans arrêt.\nActivé : l'outil s'arrête après la traduction pour que vous relisiez l'énoncé.":
        "Off: translation, proof and explanation run one after the other without stopping.\nOn: the tool stops after the translation so that you can review the statement.",
    "Corriger l'énoncé…": "Fix the statement…",
    "Décrivez ce qui ne va pas dans l'énoncé : l'IA le retraduit puis refait la preuve":
        "Describe what is wrong with the statement: the AI translates it again and redoes the proof",
    "Preuve plus simple": "Simpler proof",
    "Demander une preuve plus courte et plus lisible": "Ask for a shorter, more readable proof",
    "Autre méthode": "Another method",
    "Demander une preuve par une autre méthode": "Ask for a proof using another method",
    "Expliquer plus en détail": "Explain in more detail",
    "Demander une explication plus détaillée": "Ask for a more detailed explanation",
    "Exemples ▾": "Examples ▾",
    "Lancer un exercice d'exemple": "Run an example exercise",
    "Fichier Lean à vérifier (exemple)": "Lean file to check (example)",
    "Exemple à vérifier": "Example to check",
    "📄 Importer un .tex…": "📄 Import a .tex…",
    "Ouvrir un .lean…": "Open a .lean…",
    "Ouvrir un fichier .lean et le faire vérifier par Lean (Ctrl+O)": "Open a .lean file and have Lean check it (Ctrl+O)",
    "Que doit modifier votre demande ? « Auto » : l'outil devine (énoncé, preuve ou explication) d'après vos mots.":
        "What should your request change? “Auto”: the tool works it out (statement, proof or explanation) from your words.",
    "Envoyer": "Send",
    "Envoyer (Ctrl+Entrée)": "Send (Ctrl+Enter)",
    "L'énoncé Lean apparaîtra ici après la traduction. Vous pouvez aussi l'écrire vous-même :\n\ntheorem exemple (a b : ℝ) : a + b = b + a := by sorry\n\nAstuce : tapez \\R puis espace pour obtenir ℝ, \\le pour ≤, \\to pour →.":
        "The Lean statement will appear here after the translation. You can also write it yourself:\n\ntheorem example1 (a b : ℝ) : a + b = b + a := by sorry\n\nTip: type \\R then space to get ℝ, \\le for ≤, \\to for →.",
    "✔ Vérifier": "✔ Check",
    "Faire vérifier ce texte par Lean (F5)": "Have Lean check this text (F5)",
    "✨ Prouver cet énoncé": "✨ Prove this statement",
    "L'IA cherche une preuve de cet énoncé, puis l'explique (Ctrl+Maj+Entrée)": "The AI searches for a proof of this statement, then explains it (Ctrl+Shift+Enter)",
    "Enregistrer…": "Save…",
    "Enregistrer ce texte dans un fichier .lean (Ctrl+S)": "Save this text to a .lean file (Ctrl+S)",
    "Astuce : \\R → ℝ, \\N → ℕ, \\le → ≤, \\to → →, \\forall → ∀ (tapez puis Espace).": "Tip: \\R → ℝ, \\N → ℕ, \\le → ≤, \\to → →, \\forall → ∀ (type, then Space).",
    "Énoncé Lean": "Lean statement",
    "Aucune preuve pour l'instant.": "No proof yet.",
    "📋 Copier": "📋 Copy",
    "Copier la preuve dans le presse-papiers": "Copy the proof to the clipboard",
    "💾 Enregistrer…": "💾 Save…",
    "Enregistrer la preuve dans un fichier .lean": "Save the proof to a .lean file",
    "📄 LaTeX ▾": "📄 LaTeX ▾",
    "Exporter énoncé, preuve et explication en LaTeX (compatible Overleaf)": "Export statement, proof and explanation as LaTeX (Overleaf-compatible)",
    "Enregistrer un fichier .tex…": "Save a .tex file…",
    "Copier le code LaTeX": "Copy the LaTeX code",
    "Ouvrir Overleaf (navigateur)": "Open Overleaf (browser)",
    "Ouvrir la preuve dans votre Lean4Web local (navigateur).\nAttention : Lean4Web utilise une autre version de Lean.":
        "Open the proof in your local Lean4Web (browser).\nNote: Lean4Web uses another Lean version.",
    "Preuve": "Proof",
    "L'explication en langage courant apparaîtra ici après la preuve.": "The plain-language explanation will appear here after the proof.",
    "💬 Expliquer": "💬 Explain",
    "Une IA explique la preuve en langage courant (≈ 20 s)": "An AI explains the proof in plain language (≈ 20 s)",
    "Copier l'explication": "Copy the explanation",
    "Copier le texte de l'explication": "Copy the text of the explanation",
    "Explication": "Explanation",
    "Chaque essai de l'IA. Cliquez pour voir sa réflexion et le code testé.": "Each attempt by the AI. Click to see its reasoning and the code checked.",
    "La réflexion de l'IA (souvent en anglais) s'affiche ici en direct.": "The AI's reasoning is shown here live.",
    "Essais": "Attempts",
    "Les messages de Lean (erreurs, avertissements) apparaîtront ici.": "Lean's messages (errors, warnings) will appear here.",
    "Messages Lean": "Lean messages",
    "Aucun espace sélectionné.": "No workspace selected.",
    "  — indisponible": "  — unavailable",
    "(nouveau problème)": "(new problem)",
    "Écrivez votre problème avec vos mots (français ou anglais, LaTeX accepté).\nExemple : « Montrer que la somme de deux entiers pairs est paire. »":
        "Write your problem in your own words (English or French, LaTeX welcome).\nExample: “Show that the sum of two even integers is even.”",
    "Une précision, une correction ? Par exemple : « ajoute l'hypothèse n > 0 », « preuve plus courte », « explique l'étape 2 ».":
        "A detail, a correction? For example: “add the hypothesis n > 0”, “shorter proof”, “explain step 2”.",
    "✨ Prouver": "✨ Prove",
    "Nouveau problème": "New problem",
    "Décrivez-le en bas, puis cliquez sur « Prouver » : l'IA le traduit en Lean, cherche une preuve, et l'explique.":
        "Describe it below, then click “Prove”: the AI translates it into Lean, searches for a proof, and explains it.",
    "écrit par vous": "written by you",
    "traduit par l'IA": "translated by the AI",
    "Lean l'accepte": "Lean accepts it",
    "Lean le refuse": "Lean rejects it",
    "Version {n} sur {t} · {src} · {ok}. Relisez-le : la preuve porte exactement sur ce texte.":
        "Version {n} of {t} · {src} · {ok}. Review it: the proof is about exactly this text.",
    "Pas encore d'énoncé.": "No statement yet.",
    " ⚠️ Cette preuve correspond à une ancienne version de l'énoncé.": " ⚠️ This proof belongs to an older version of the statement.",
    "Preuve {n} sur {t}, vérifiée par Lean (sans « sorry », axiomes standard).": "Proof {n} of {t}, checked by Lean (no “sorry”, standard axioms).",
    "✅ Prouvé et expliqué": "✅ Proved and explained",
    "Demandez une précision ci-dessous, ou exportez (onglet « Preuve »).": "Ask for a detail below, or export (“Proof” tab).",
    "✅ Prouvé": "✅ Proved",
    "Lean a vérifié la preuve. Cliquez sur « 💬 Expliquer » pour une explication.": "Lean checked the proof. Click “💬 Explain” for an explanation.",
    "⚠️ À vous de jouer": "⚠️ Your turn",
    "Énoncé prêt": "Statement ready",
    "Relisez-le dans l'onglet « Énoncé Lean », puis cliquez sur « Prouver cet énoncé ».": "Review it in the “Lean statement” tab, then click “Prove this statement”.",
    "Dossier vide": "Empty dossier",
    "Décrivez votre problème en bas.": "Describe your problem below.",
    "Comment ça marche": "How it works",
    "Écrivez votre problème en bas, avec vos mots.": "Write your problem below, in your own words.",
    "L’IA le traduit en Lean, cherche une preuve que Lean vérifie, puis l’explique.": "The AI translates it into Lean, searches for a proof that Lean checks, then explains it.",
    "Vous pouvez ensuite demander des corrections ou des précisions : tout reste dans ce dossier.":
        "You can then ask for corrections or details: everything stays in this dossier.",
    "Idées :": "Ideas:",
    "Vous": "You",
    "{n} lignes de Lean": "{n} lines of Lean",
    "Voir": "View",
    "version actuelle": "current version",
    "Revenir à cette version": "Go back to this version",
    "Renommer le dossier": "Rename the dossier",
    "Nouveau titre :": "New title:",
    "Dossier supprimé.": "Dossier deleted.",
    "L'énoncé est faux : ": "The statement is wrong: ",
    "Une recherche est déjà en cours : arrêtez-la d'abord (Échap).": "A search is already running: stop it first (Esc).",
    "Exemple : ": "Example: ",
    "Il n'y a pas encore de preuve à expliquer": "There is no proof to explain yet",
    "Lancez d'abord une preuve (« Prouver »).": "Run a proof first (“Prove”).",
    "① Traduction en Lean…": "① Translating into Lean…",
    "L'IA écrit l'énoncé en Lean, puis Lean contrôle qu'il est valide.": "The AI writes the statement in Lean, then Lean checks that it is valid.",
    "② Recherche de preuve…": "② Searching for a proof…",
    "L'IA écrit une preuve ; si Lean la refuse, elle corrige et réessaie.": "The AI writes a proof; if Lean rejects it, it fixes it and tries again.",
    "③ Explication…": "③ Explaining…",
    "L'IA explique la preuve en langage courant.": "The AI explains the proof in plain language.",
    "du traducteur": "the translator",
    "du prouveur": "the prover",
    "de l'explicateur": "the explainer",
    "Chargement {name} en mémoire graphique… (environ 5 à 30 s)": "Loading {name} into graphics memory… (about 5 to 30 s)",
    "traduit votre problème": "is translating your problem",
    "écrit une preuve": "is writing a proof",
    "réécrit la preuve selon votre demande": "is rewriting the proof as you asked",
    "écrit une correction": "is writing a correction",
    "Essai {i}/{n} : l'IA {what}…": "Attempt {i}/{n}: the AI {what}…",
    "{n} tokens, {s:.0f} tok/s": "{n} tokens, {s:.0f} tok/s",
    "Lean {s:.0f} s": "Lean {s:.0f} s",
    "1re tentative": "first try",
    "traduction": "translation",
    "selon votre demande": "as you asked",
    "correction": "correction",
    "Essai {i} ({kind}) — {s}": "Attempt {i} ({kind}) — {s}",
    "l'énoncé": "the statement",
    "la preuve": "the proof",
    "Essai {i}/{n} : Lean vérifie {what}…": "Attempt {i}/{n}: Lean is checking {what}…",
    "L'éditeur est vide": "The editor is empty",
    "Écrivez du code Lean, ou ouvrez un fichier .lean.": "Write Lean code, or open a .lean file.",
    "Lean vérifie le texte… (quelques secondes ; jusqu'à 1 minute la première fois)": "Lean is checking the text… (a few seconds; up to 1 minute the first time)",
    "Vérification en cours…": "Checking…",
    "Vérification annulée": "Check cancelled",
    "Lean n'a pas pu vérifier": "Lean could not check",
    "❌ Erreur": "❌ Error",
    "⚠️ Avertissement": "⚠️ Warning",
    "ℹ️ Info": "ℹ️ Info",
    "{sev} — ligne {l}, colonne {c} :": "{sev} — line {l}, column {c}:",
    "{sev}, ligne {l} : {t}": "{sev}, line {l}: {t}",
    "Aucun message : tout est correct.": "No messages: everything is correct.",
    "Vérifié en {s:.1f} s.": "Checked in {s:.1f} s.",
    "⚠️ Accepté, mais incomplet": "⚠️ Accepted, but incomplete",
    "Le texte contient « sorry » : une preuve manque. Cliquez sur « Prouver cet énoncé » pour que l'IA la cherche.":
        "The text contains “sorry”: a proof is missing. Click “Prove this statement” to have the AI search for it.",
    "Augmentez le délai dans « Système » ou simplifiez le fichier.": "Increase the time limit in “System” or simplify the file.",
    "Les lignes en rouge contiennent des erreurs. Double-cliquez sur un message (onglet « Essais ») pour aller à la ligne.":
        "Lines in red contain errors. Double-click a message (“Attempts” tab) to go to the line.",
    "Ouvrir un fichier Lean": "Open a Lean file",
    "Fichiers Lean (*.lean);;Tous (*)": "Lean files (*.lean);;All (*)",
    "Impossible d'ouvrir le fichier": "Cannot open the file",
    "Le fichier n'est pas lisible (droits ou encodage). Choisissez un autre fichier.": "The file is not readable (permissions or encoding). Choose another file.",
    "Fichier ouvert : {name}": "File opened: {name}",
    "Enregistrer": "Save",
    "Enregistrement impossible": "Cannot save",
    "Choisissez un autre dossier.": "Choose another folder.",
    "Enregistré : {name}": "Saved: {name}",
    "Fichiers Lean (*.lean)": "Lean files (*.lean)",
    "Preuve copiée dans le presse-papiers.": "Proof copied to the clipboard.",
    "Aucune explication à copier.": "No explanation to copy.",
    "Explication copiée.": "Explanation copied.",
    "Lean4Web ne répond pas sur cet ordinateur.": "Lean4Web is not responding on this computer.",
    "Le fichier n'est pas lisible (droits).": "The file is not readable (permissions).",
    "Aucun énoncé trouvé": "No statement found",
    "Ce fichier .tex ne contient ni théorème, ni lemme, ni exercice, ni texte exploitable.":
        "This .tex file contains no theorem, lemma, exercise or usable text.",
    "Choisir l'énoncé": "Choose the statement",
    "Ce fichier contient plusieurs énoncés.\nLequel voulez-vous prouver ?": "This file contains several statements.\nWhich one do you want to prove?",
    "Importé : {t}. Cliquez sur « Prouver ».": "Imported: {t}. Click “Prove”.",
    "Il n'y a pas encore de preuve à exporter.": "There is no proof to export yet.",
    "Fichiers LaTeX (*.tex)": "LaTeX files (*.tex)",
    "Dans Overleaf : « Nouveau projet → Téléverser », compilateur XeLaTeX.": "In Overleaf: “New project → Upload”, XeLaTeX compiler.",
    "Code LaTeX copié : collez-le dans un fichier .tex d'Overleaf (compilateur XeLaTeX).": "LaTeX code copied: paste it into an Overleaf .tex file (XeLaTeX compiler).",

    'Auto': 'Auto',
    'Modifier :': 'Change:',
    '📂 Importer ▾': '📂 Import ▾',
    'Prendre un énoncé dans un fichier LaTeX, ou faire vérifier un fichier .lean (vous pouvez aussi glisser le fichier sur la fenêtre)': 'Take a statement from a LaTeX file, or have a .lean file checked (you can also drop the file on the window)',
    "Un théorème d'un fichier .tex…": 'A theorem from a .tex file…',
    'Un fichier .lean à vérifier… (Ctrl+O)': 'A .lean file to check… (Ctrl+O)',
    # ---------------------------------------------------------------- library page
    "Bibliothèque de résultats": "Library of results",
    "Rechercher (titre, nom, symbole…)": "Search (title, name, symbol…)",
    "Tout exporter en .lean…": "Export everything as .lean…",
    "Un seul fichier Lean avec tous vos résultats prouvés": "A single Lean file with all your proven results",
    "Chaque théorème prouvé est rangé ici automatiquement. Quand un nouveau problème lui ressemble, il est proposé à l'IA comme lemme (avec sa preuve), pour la même version de Lean.":
        "Every proven theorem is stored here automatically. When a new problem looks similar, it is offered to the AI as a lemma (with its proof), for the same Lean version.",
    "Titre": "Title",
    "Nom Lean": "Lean name",
    "Espace Lean": "Lean workspace",
    "Date": "Date",
    "Sélectionnez un résultat pour voir son énoncé et sa preuve.": "Select a result to see its statement and proof.",
    "Copier l'énoncé et la preuve": "Copy the statement and the proof",
    "Ouvrir le dossier d'origine": "Open the original dossier",
    "Rouvrir la discussion qui a produit ce résultat": "Reopen the conversation that produced this result",
    "Retirer de la bibliothèque": "Remove from the library",
    "Il ne sera plus proposé (annulable)": "It will no longer be offered (can be undone)",
    "La bibliothèque est vide : elle se remplit à chaque preuve réussie.": "The library is empty: it fills up with every successful proof.",
    "Copié.": "Copied.",
    "« {t} » retiré de la bibliothèque.": "“{t}” removed from the library.",
    "La bibliothèque est vide.": "The library is empty.",
    "Exporter la bibliothèque": "Export the library",

    # ---------------------------------------------------------------- models page
    "Modèles installés": "Installed models",
    "Importer un fichier .gguf…": "Import a .gguf file…",
    "Copier un modèle GGUF dans le dossier des modèles": "Copy a GGUF model into the models folder",
    "Ouvrir le dossier": "Open the folder",
    "Relire le dossier des modèles": "Re-read the models folder",
    "Dossier : {d}": "Folder: {d}",
    "Précision du modèle compressé : Q4_K_M = bon compromis vitesse/qualité ; Q5/Q6/Q8 = plus précis mais plus lourd.":
        "Precision of the compressed model: Q4_K_M = good speed/quality balance; Q5/Q6/Q8 = more precise but heavier.",
    "Le modèle tient-il entièrement dans la mémoire de la carte graphique (VRAM) ? Sinon il sera plus lent.":
        "Does the model fit entirely in the graphics card's memory (VRAM)? Otherwise it will be slower.",
    "Aucun modèle trouvé. Cliquez sur « Importer un fichier .gguf… » ou téléchargez-en un ci-dessous.":
        "No model found. Click “Import a .gguf file…” or download one below.",
    "▶ Charger": "▶ Load",
    "Charger ce modèle sur la carte graphique (double-clic)": "Load this model on the graphics card (double-click)",
    "⏏ Décharger": "⏏ Unload",
    "Libérer la mémoire de la carte graphique": "Free the graphics card's memory",
    "Mettre le fichier à la corbeille (annulable)": "Move the file to the trash (can be undone)",
    "Télécharger depuis Hugging Face (nécessite Internet)": "Download from Hugging Face (needs Internet)",
    "Nom du dépôt Hugging Face contenant des fichiers .gguf": "Name of the Hugging Face repository containing .gguf files",
    "Lister les fichiers": "List the files",
    "Afficher les fichiers .gguf du dépôt": "Show the repository's .gguf files",
    "Télécharger": "Download",
    "Télécharger le fichier sélectionné dans le dossier des modèles": "Download the selected file into the models folder",
    "Inconnue": "Unknown",
    "✔ Tient entièrement": "✔ Fits entirely",
    "◐ Partiellement (plus lent)": "◐ Partly (slower)",
    "✖ Trop gros (très lent)": "✖ Too big (very slow)",
    "⚠️ Illisible : {err}": "⚠️ Unreadable: {err}",
    "traduction texte → Lean": "text → Lean translation",
    "explication en langage courant": "plain-language explanation",
    "preuves": "proofs",
    "🟢 Chargé": "🟢 Loaded",
    "🟡 Chargement…": "🟡 Loading…",
    "Chargement de {name}…": "Loading {name}…",
    "Suppression impossible": "Cannot delete",
    "Le fichier n'a pas pu être mis à la corbeille.": "The file could not be moved to the trash.",
    "Restauration impossible": "Cannot restore",
    "Restaurez le fichier depuis la corbeille.": "Restore the file from the trash.",
    "{name} mis à la corbeille.": "{name} moved to the trash.",
    "Importer un modèle": "Import a model",
    "Modèles GGUF (*.gguf)": "GGUF models (*.gguf)",
    "Ce modèle est déjà installé.": "This model is already installed.",
    "Copie de {name}…": "Copying {name}…",
    "Modèle importé : {name}": "Model imported: {name}",
    "Import impossible": "Cannot import",
    "La copie a échoué (disque plein ?).": "The copy failed (disk full?).",
    "🔒 Mode hors-ligne actif : téléchargement désactivé (modifiable dans « Système »).": "🔒 Offline mode on: downloading disabled (change it in “System”).",
    "Le fichier sera vérifié puis ajouté à la liste.": "The file will be checked, then added to the list.",
    "Recherche des fichiers…": "Looking for files…",
    "Aucun fichier trouvé": "No file found",
    "Vérifiez le nom du dépôt et la connexion Internet.": "Check the repository name and the Internet connection.",
    "Choisissez d'abord un fichier dans la liste.": "First choose a file in the list.",
    "Téléchargement de {name}…": "Downloading {name}…",
    "Téléchargement : {a} / {b}": "Downloading: {a} / {b}",
    "Téléchargement interrompu": "Download interrupted",
    "Vérifiez la connexion puis réessayez.": "Check the connection, then try again.",
    "Téléchargé : {name}": "Downloaded: {name}",

    # ---------------------------------------------------------------- server page
    "⚪ Arrêté": "⚪ Stopped",
    "🟡 Démarrage…": "🟡 Starting…",
    "🟢 En marche": "🟢 Running",
    "🟠 Arrêt…": "🟠 Stopping…",
    "▶ Démarrer": "▶ Start",
    "Démarrer le serveur avec le modèle choisi": "Start the server with the chosen model",
    "↻ Redémarrer": "↻ Restart",
    "Redémarrer avec les réglages ci-dessous": "Restart with the settings below",
    "Arrêter le serveur et libérer la carte graphique": "Stop the server and free the graphics card",
    "Adresse compatible OpenAI, utilisable par d'autres logiciels de cet ordinateur.": "OpenAI-compatible address, usable by other programs on this computer.",
    "Copier l'adresse": "Copy the address",
    "Copier l'URL de l'API": "Copy the API URL",
    "Adresse copiée.": "Address copied.",
    "Réglages avancés (les valeurs recommandées conviennent dans la plupart des cas)": "Advanced settings (the recommended values suit most cases)",
    "Port local du serveur (127.0.0.1 uniquement, jamais exposé au réseau).": "Local server port (127.0.0.1 only, never exposed to the network).",
    "Mémoire de travail du modèle. Plus grand = preuves longues possibles, mais plus de mémoire graphique.":
        "The model's working memory. Larger = longer proofs possible, but more graphics memory.",
    "Nombre de couches du modèle sur la carte graphique (99 = toutes ; 0 = processeur seul).": "Number of model layers on the graphics card (99 = all; 0 = processor only).",
    "Taille de lot pour lire la question (plus grand = lecture plus rapide).": "Batch size for reading the prompt (larger = faster reading).",
    "Taille de micro-lot physique sur la carte graphique.": "Physical micro-batch size on the graphics card.",
    "f16 (précis, plus de mémoire)": "f16 (precise, more memory)",
    "q8_0 (recommandé)": "q8_0 (recommended)",
    "q4_0 (économe)": "q4_0 (economical)",
    "Format du cache de contexte (KV). q8_0 divise la mémoire par deux sans perte notable.": "Context cache (KV) format. q8_0 halves the memory with no noticeable loss.",
    "Activée": "On",
    "Flash Attention : plus rapide et plus économe en mémoire sur les cartes RTX.": "Flash Attention: faster and more memory-efficient on RTX cards.",
    "Nombre de cœurs du processeur utilisés.": "Number of processor cores used.",
    "Port": "Port",
    "Contexte": "Context",
    "Couches sur la carte graphique": "Layers on the graphics card",
    "Lot (batch)": "Batch",
    "Micro-lot (ubatch)": "Micro-batch (ubatch)",
    "Cache KV": "KV cache",
    "Flash Attention": "Flash Attention",
    "Threads processeur": "Processor threads",
    "Valeurs recommandées": "Recommended values",
    "Revenir aux réglages mesurés comme les meilleurs (BENCH.md)": "Go back to the settings measured as best (BENCH.md)",
    "Journal du serveur (en direct)": "Server log (live)",
    "Le journal apparaîtra ici quand le serveur démarrera.": "The log will appear here when the server starts.",
    "Réglages recommandés rétablis (redémarrez le serveur pour les appliquer).": "Recommended settings restored (restart the server to apply them).",
    "Modèle : {m} — couches sur la carte graphique : {n} — contexte : {c} tokens — chargé en {s:.1f} s":
        "Model: {m} — layers on the graphics card: {n} — context: {c} tokens — loaded in {s:.1f} s",
    "Modèle qui sera chargé : {name}": "Model that will be loaded: {name}",
    "Aucun modèle installé.": "No model installed.",
    "API : {url}/v1": "API: {url}/v1",
    "API : (serveur arrêté)": "API: (server stopped)",
    "Aucun modèle installé : ouvrez l'onglet « Modèles » pour en ajouter un.": "No model installed: open the “Models” tab to add one.",

    # ---------------------------------------------------------------- system page
    "Carte graphique": "Graphics card",
    "Détection…": "Detecting…",
    "Mémoire graphique (VRAM) utilisée": "Graphics memory (VRAM) used",
    "Mémoire graphique (VRAM)": "Graphics memory (VRAM)",
    "Disque et mémoire": "Disk and memory",
    "Disque (dossier personnel)": "Disk (home folder)",
    "Mémoire vive (RAM)": "Main memory (RAM)",
    "Confidentialité et options": "Privacy and options",
    "Mode hors-ligne (aucune connexion Internet depuis l'application)": "Offline mode (no Internet connection from the application)",
    "Activé : l'application ne contacte que cet ordinateur. Seul le téléchargement de modèles a besoin d'Internet.":
        "On: the application only talks to this computer. Only model downloads need the Internet.",
    "Aucune télémétrie : rien n'est jamais envoyé.": "No telemetry: nothing is ever sent.",
    "Délai max. de vérification Lean (s) :": "Maximum Lean check time (s):",
    "Au-delà, Lean est arrêté et l'essai est compté comme un échec.": "Beyond it, Lean is stopped and the attempt counts as a failure.",
    "Adresse de votre Overleaf (optionnel) :": "Your Overleaf address (optional):",
    "Utilisée par « LaTeX ▾ → Ouvrir Overleaf » après une preuve réussie.": "Used by “LaTeX ▾ → Open Overleaf” after a successful proof.",
    "Relancer l'assistant de démarrage": "Run the setup assistant again",
    "Refaire la configuration guidée": "Redo the guided setup",
    "Langue de l'interface et des réponses :": "Language of the interface and answers:",
    "Votre profil (mémoire de l'assistant)": "Your profile (the assistant's memory)",
    "Lu avant chaque traduction et chaque explication : qui vous êtes, votre public, vos notations. Le prouveur, lui, n'en tient pas compte (son format est fixé pour rester fiable).":
        "Read before every translation and explanation: who you are, your audience, your notations. The prover ignores it (its format is fixed to stay reliable).",
    "Exemple : « Je suis enseignant en lycée. Mes élèves de terminale débutent : explications simples, sans jargon. ℕ commence à 0. Les suites sont indexées par n ≥ 0. »":
        "Example: “I teach high school. My final-year students are beginners: simple explanations, no jargon. ℕ starts at 0. Sequences are indexed by n ≥ 0.”",
    "État de l'installation": "Installation status",
    "Tout revérifier": "Check everything again",
    "Relancer toutes les vérifications": "Run all checks again",
    "Température : {t} °C — Utilisation : {u} %": "Temperature: {t} °C — Load: {u} %",
    "Libre : {n:.0f} Go": "Free: {n:.0f} GB",
    "  ⚠️ presque plein": "  ⚠️ almost full",
    "⚠️ Carte NVIDIA non disponible : le modèle utilisera le processeur (lent).": "⚠️ NVIDIA card unavailable: the model will use the processor (slow).",
    "Moteur d'IA (llama-server)": "AI engine (llama-server)",
    "Programme introuvable.": "Program not found.",
    "Carte graphique NVIDIA": "NVIDIA graphics card",
    "Non détectée : fonctionnement sur processeur (lent). Redémarrez l'ordinateur si cela persiste.":
        "Not detected: running on the processor (slow). Restart the computer if this persists.",
    "Modèle d'IA installé (prouveur)": "AI model installed (prover)",
    "{n} modèle(s) prêt(s)": "{n} model(s) ready",
    ", {n} illisible(s)": ", {n} unreadable",
    "Aucun modèle utilisable.": "No usable model.",
    "Traducteur français → Lean (Goedel-Formalizer)": "Natural language → Lean translator (Goedel-Formalizer)",
    "Absent : sans lui, écrivez l'énoncé directement en Lean. Avec Internet : « Modèles » → mradermacher/Goedel-Formalizer-V2-8B-GGUF.":
        "Missing: without it, write the statement directly in Lean. With Internet: “Models” → mradermacher/Goedel-Formalizer-V2-8B-GGUF.",
    "Modèle d'explication en français (Qwen3-8B)": "Plain-language explanation model (Qwen3-8B)",
    "Absent : le bouton « Expliquer » est indisponible. Avec Internet : « Modèles » → Qwen/Qwen3-8B-GGUF.":
        "Missing: the “Explain” button is unavailable. With Internet: “Models” → Qwen/Qwen3-8B-GGUF.",
    "Prêt": "Ready",
    "Installer / réparer": "Install / repair",
    "Projets Lean existants détectés": "Existing Lean projects detected",
    " (utilisés en lecture seule)": " (used read-only)",
    "Processus fantômes": "Leftover processes",
    "Un ancien serveur semble encore actif.": "An old server seems to be still running.",
    "Espace disque": "Disk space",
    "{n:.0f} Go libres": "{n:.0f} GB free",
    "Processus nettoyés.": "Processes cleaned up.",
    "Compilation du moteur d'IA (≈ 15 min)…": "Building the AI engine (≈ 15 min)…",
    "Connexion Internet nécessaire": "Internet connection needed",
    "L'installation de cet espace télécharge Mathlib une seule fois. Désactivez le mode hors-ligne ci-dessus puis recliquez sur « Installer / réparer ».":
        "Installing this workspace downloads Mathlib once. Turn off offline mode above, then click “Install / repair” again.",
    "Installation / compilation de « {ws} » (peut être long)…": "Installing / building “{ws}” (can take a while)…",
    "Réparation terminée.": "Repair finished.",
    "La réparation n'a pas abouti": "The repair did not succeed",
    "Vérifiez la connexion Internet (si nécessaire) puis réessayez. Le journal est affiché sous les vérifications.":
        "Check the Internet connection (if needed), then try again. The log is shown below the checks.",

    # ---------------------------------------------------------------- wizard
    "Bienvenue !": "Welcome!",
    "Préparons Lean AI Station.": "Let's set up Lean AI Station.",
    "Détection de votre ordinateur": "Detecting your computer",
    "Vérification automatique en cours…": "Automatic check in progress…",
    "Choix automatiques": "Automatic choices",
    "Voici ce que nous vous conseillons.": "Here is what we recommend.",
    "Auto-test": "Self-test",
    "Nous vérifions que tout fonctionne vraiment.": "We check that everything really works.",
    "Tout est prêt 🎉": "All set 🎉",
    "Passer l'assistant": "Skip the assistant",
    "Configurer plus tard (tout reste modifiable)": "Set up later (everything can be changed)",
    "← Retour": "← Back",
    "Commencer →": "Start →",
    "Suivant →": "Next →",
    "Ouvrir l'accueil": "Open the home screen",
    "Cet assistant vérifie votre ordinateur et prépare tout automatiquement. Comptez environ une minute. Rien à installer ni à configurer à la main.":
        "This assistant checks your computer and prepares everything automatically. It takes about a minute. Nothing to install or configure by hand.",
    "• Trois IA spécialisées traduisent votre problème en Lean, écrivent la preuve et l'expliquent.\n• Lean vérifie chaque preuve : seules les preuves correctes sont acceptées.\n• Rien n'est envoyé sur Internet : l'IA est un fichier installé chez vous, exécuté par la carte graphique (à défaut, le processeur).":
        "• Three specialised AI models translate your problem into Lean, write the proof and explain it.\n• Lean checks every proof: only correct proofs are accepted.\n• Nothing is sent over the Internet: the AI is a file installed on your computer, run by the graphics card (or, failing that, the processor).",
    "Moteur d'IA": "AI engine",
    "Modèle d'IA": "AI model",
    "Lean et Mathlib": "Lean and Mathlib",
    "Le modèle conseillé est présélectionné.": "The recommended model is preselected.",
    "La version de Lean conseillée pour Goedel-Prover est présélectionnée.": "The Lean version recommended for Goedel-Prover is preselected.",
    "Modèle d'IA :": "AI model:",
    "Ces choix sont déjà les bons dans la plupart des cas : cliquez simplement sur « Suivant ».": "These choices are right in most cases: just click “Next”.",
    "Chargement du modèle sur la carte graphique": "Loading the model on the graphics card",
    "Test de génération": "Generation test",
    "Test de vérification Lean": "Lean check test",
    "{name} — {n:.1f} Go de mémoire graphique": "{name} — {n:.1f} GB of graphics memory",
    "Non détectée : le modèle fonctionnera sur le processeur (beaucoup plus lent).": "Not detected: the model will run on the processor (much slower).",
    "llama.cpp (CUDA)": "llama.cpp (CUDA)",
    "Introuvable : ouvrez « Système » → « Recompiler ».": "Not found: open “System” → “Rebuild”.",
    "{n} modèle(s) ; conseillé : {name}": "{n} model(s); recommended: {name}",
    "Aucun modèle : importez-en un dans « Modèles ».": "No model: import one in “Models”.",
    "{n} espace(s) prêt(s)": "{n} workspace(s) ready",
    "Aucun espace Lean prêt : ouvrez « Système » pour l'installer.": "No Lean workspace ready: open “System” to install it.",
    "  — conseillé": "  — recommended",
    "Environ 10 à 30 secondes…": "About 10 to 30 seconds…",
    "Chargé en {s:.1f} s — couches sur la carte graphique : {n}": "Loaded in {s:.1f} s — layers on the graphics card: {n}",
    "Pas de réponse du modèle.": "No answer from the model.",
    "Réponse en {s:.1f} s ({t:.0f} tokens/s)": "Answer in {s:.1f} s ({t:.0f} tokens/s)",
    "Aucun espace Lean prêt (voir « Système »).": "No Lean workspace ready (see “System”).",
    "Première vérification : jusqu'à 1 minute (chargement de Mathlib en mémoire)…": "First check: up to 1 minute (loading Mathlib into memory)…",
    "Lean a vérifié une preuve en {s:.1f} s": "Lean checked a proof in {s:.1f} s",
    "Tout fonctionne. Sur l'écran d'accueil, cliquez sur « ▶ Prouver » sous un exercice pour voir l'IA trouver une preuve vérifiée par Lean.\n\nRaccourcis : Ctrl+1 à Ctrl+6 pour changer d'onglet, Ctrl+Entrée pour envoyer une demande, F5 pour vérifier, Échap pour arrêter.":
        "Everything works. On the home screen, click “▶ Prove” under an exercise to watch the AI find a proof checked by Lean.\n\nShortcuts: Ctrl+1 to Ctrl+6 to switch tabs, Ctrl+Enter to send a request, F5 to check, Esc to stop.",
    "L'installation est utilisable mais certains tests ont échoué. L'onglet « Système » indique quoi réparer, avec un bouton pour chaque problème.":
        "The installation is usable but some tests failed. The “System” tab shows what to repair, with a button for each problem.",
    "Chaque mise à jour est installée à côté de l'ancienne, vérifiée, puis l'ancienne version est supprimée automatiquement (une version de Lean encore utilisée par un de vos projets est gardée). Le prouveur Lean 4.9 reste fixe : c'est la version d'entraînement du modèle.":
        'Each update is installed next to the old version and verified; then the old version is deleted automatically (a Lean version still used by one of your projects is kept). The Lean 4.9 prover workspace stays fixed: it is the version the model was trained on.',
    'Contacte GitHub (Mathlib) et Hugging Face (modèles)':
        'Contacts GitHub (Mathlib) and Hugging Face (models)',
    'Dernière vérification : {when}.':
        'Last check: {when}.',
    'Dernière vérification : {when}. Problème : {err}':
        'Last check: {when}. Problem: {err}',
    'Dernière vérification : {when}. Tout est à jour.':
        'Last check: {when}. Everything is up to date.',
    'Installer':
        'Install',
    "La mise à jour a échoué à l'étape « {step} ». L'ancienne version est conservée.":
        'The update failed at step “{step}”. The old version is kept.',
    'Lean + Mathlib {new} (installé : {cur}). Environ 8 Go, 10 à 60 minutes.':
        'Lean + Mathlib {new} (installed: {cur}). About 8 GB, 10 to 60 minutes.',
    'Lean AI Station : mise à jour disponible':
        'Lean AI Station: update available',
    'Lean actuel : Mathlib {v}':
        'Current Lean: Mathlib {v}',
    "Mise à jour annulée. L'ancienne version est conservée.":
        'Update cancelled. The old version is kept.',
    'Mise à jour disponible':
        'Update available',
    'Mise à jour installée':
        'Update installed',
    'Mise à jour non installée':
        'Update not installed',
    'Mises à jour de Lean et des modèles Goedel':
        'Updates of Lean and the Goedel models',
    "Pas assez d'espace disque. L'ancienne version est conservée.":
        'Not enough disk space. The old version is kept.',
    'Pas de nouvelle mise à jour installable.':
        'No new installable update.',
    'Tout est à jour.':
        'Everything is up to date.',
    "Télécharger, vérifier, puis remplacer l'ancienne version":
        'Download, verify, then replace the old version',
    'Voir les mises à jour':
        'See the updates',
    "Vérification impossible (pas d'Internet ?).":
        'Could not check (no Internet?).',
    'Vérifier chaque semaine au démarrage (contacte uniquement GitHub et Hugging Face, même en mode hors-ligne)':
        'Check every week at start-up (contacts only GitHub and Hugging Face, even in offline mode)',
    'Vérifier maintenant':
        'Check now',
    'jamais':
        'never',
    "{names}. L'ancienne version sera supprimée automatiquement une fois la nouvelle vérifiée.":
        '{names}. The old version will be deleted automatically once the new one is verified.',
    '{name} : fichier republié par son auteur (correctifs), {gb} Go.':
        '{name}: file re-published by its author (fixes), {gb} GB.',
    '{name} : nouvelle version du {role} ({cur} → {new}), {gb} Go.':
        '{name}: new version of the {role} ({cur} → {new}), {gb} GB.',
    '{name} est installé et vérifié. Supprimé : {removed}.':
        '{name} is installed and verified. Deleted: {removed}.',
    "{name} est publié, mais pas encore au format utilisable ici (GGUF). L'outil revérifiera la semaine prochaine.":
        '{name} is published, but not yet in the format used here (GGUF). The tool will check again next week.',
    '{role} : V{v}':
        '{role}: V{v}',
    'Installation de la nouvelle version de Lean…':
        'Installing the new Lean version…',
    'Téléchargement de Mathlib…':
        'Downloading Mathlib…',
    'Téléchargement des fichiers compilés de Mathlib (plusieurs Go)…':
        "Downloading Mathlib's compiled files (several GB)…",
    'Finalisation de Mathlib…':
        'Finishing Mathlib…',
    'Vérification avec un théorème test…':
        'Checking with a test theorem…',
    'Téléchargement du modèle…':
        'Downloading the model…',
    'Test du nouveau modèle (chargement et réponse)…':
        'Testing the new model (loading and answering)…',
    'Bascule vers la nouvelle version…':
        'Switching to the new version…',
    "Suppression de l'ancienne version…":
        'Deleting the old version…',
    'Préparation…':
        'Preparing…',
    'prouveur':
        'prover',
    'traducteur':
        'translator',
    "Je ne reconnais pas d'énoncé mathématique dans votre demande. Écrivez le résultat à prouver avec ses hypothèses, par exemple : « toute famille libre d'un espace vectoriel de dimension finie se complète en une base ».":
        'I do not recognise a mathematical statement in your request. Write the result to prove with its hypotheses, for example: “every linearly independent family of a finite-dimensional vector space extends to a basis”.',
    "L'IA reformule votre demande en un énoncé mathématique précis, avec toutes ses hypothèses.":
        'The AI rewrites your request as a precise mathematical statement, with all its hypotheses.',
    "Problème compris ainsi (c'est ce texte que l'IA traduit en Lean) :":
        'Problem understood as follows (this is the text the AI translates into Lean):',
    '⓪ Compréhension du problème…':
        '⓪ Understanding the problem…',
    "L'IA décide s'il faut un nouvel énoncé, une autre preuve ou une autre explication.":
        'The AI decides whether you want a new statement, another proof or another explanation.',
    'Lecture de votre demande…':
        'Reading your request…',
    "Nouvel énoncé compris ainsi (c'est ce texte que l'IA traduit en Lean) :":
        'New statement understood as follows (this is the text the AI translates into Lean):',
    # ---- Madalean 2.0 server
    "Appairage bloqué pendant {m} minutes après trop d'erreurs.": 'Pairing locked for {m} minutes after too many errors.',
    "Aucun code actif : affichez-en un sur l'ordinateur hôte.": 'No active code: display one on the host computer.',
    "Aucun modèle disponible pour découper l'énoncé ({err}).": 'No model available to split the statement ({err}).',
    'Aucun modèle local « {role} » installé.': 'No local « {role} » model installed.',
    "Ce code a expiré : demandez-en un nouveau sur l'ordinateur hôte.": 'This code has expired: ask for a new one on the host computer.',
    'Champs refusés : {fields}.': 'Refused fields: {fields}.',
    'Code incorrect.': 'Wrong code.',
    'Disque presque plein : {n} Go libres.': 'Disk almost full: {n} GB free.',
    'Erreur interne : {err}': 'Internal error: {err}',
    'Espace de travail Lean prêt : {ws}.': 'Lean workspace ready: {ws}.',
    'Espace disque suffisant.': 'Enough disk space.',
    "Jupyter n'est accessible que depuis l'ordinateur hôte (réglage).": 'Jupyter is only reachable from the host computer (setting).',
    'JupyterLab absent : les carnets ne sont pas disponibles.': 'JupyterLab missing: notebooks are not available.',
    'JupyterLab présent.': 'JupyterLab installed.',
    "L'agent n'a pas trouvé de preuve ({steps} étapes).": 'The agent found no proof ({steps} steps).',
    "L'espace de travail Lean n'est pas prêt : {ws}.": 'The Lean workspace is not ready: {ws}.',
    'LaTeX (latexmk + XeLaTeX) présent : export PDF possible.': 'LaTeX (latexmk + XeLaTeX) installed: PDF export available.',
    "LaTeX absent : l'export PDF devient une page HTML à imprimer.": 'LaTeX missing: the PDF export becomes an HTML page to print.',
    "Le modèle n'a proposé aucun lemme utilisable.": 'The model proposed no usable lemma.',
    'Lean refuse cette traduction : nouvel essai.': 'Lean refuses this translation: new attempt.',
    'Lean refuse cette traduction.': 'Lean refuses this translation.',
    "Lecture guidée de l'énoncé Lean, rédigée par l'IA :": 'Guided reading of the Lean statement, written by the AI:',
    'Lemmes prouvés : {n}/{m}. Nouvel essai de la preuve avec ces lemmes.': 'Lemmas proved: {n}/{m}. New proof attempt using these lemmas.',
    'Mise à jour disponible : {names}.': 'Update available: {names}.',
    'Modèle local « {role} » : {name}.': 'Local « {role} » model: {name}.',
    'Moteur de modèles : {kind}.': 'Model engine: {kind}.',
    'Moteur de modèles absent : réponses simulées (installation incomplète).': 'Model engine missing: simulated answers (incomplete installation).',
    'Moteur local llama-server présent.': 'Local llama-server engine installed.',
    'Nouvel essai.': 'New attempt.',
    "Pas d'énoncé à prouver : écrivez ou traduisez d'abord l'énoncé.": 'No statement to prove: write or translate the statement first.',
    'Pas de preuve à expliquer.': 'No proof to explain.',
    'Police {f} : présente.': 'Font {f}: installed.',
    'Police {f} absente (export PDF moins lisible).': 'Font {f} missing (PDF export less readable).',
    "Preuve rédigée en langage naturel par l'IA (la preuve Lean fait foi).": 'Proof written in natural language by the AI (the Lean proof is authoritative).',
    "Trop d'essais : attendez une minute.": 'Too many attempts: wait a minute.',
    'ligne {line} : {text}': 'line {line}: {text}',
    'llama-server introuvable : relancez install.sh.': 'llama-server not found: run install.sh again.',
    '{why}': '{why}',
    'Énoncé découpé en {n} lemmes, prouvés en parallèle ; la preuve sera relancée avec eux.': 'Statement split into {n} lemmas, proved in parallel; the proof will be retried with them.',
    "Étape impossible : l'espace de travail Lean n'est pas prêt ({why}).": 'Step impossible: the Lean workspace is not ready ({why}).',
}

# ---- research layer: sources, bibliography, grounded answers, blueprint, article (session S-E)
EN.update({
    "Étagère commune": "Shared shelf",
    "Références de Mathlib": "Mathlib references",
    "Introuvable.": "Not found.",
    "Mode local : aucune requête n'est envoyée sur le réseau (changez de mode pour chercher en ligne).":
        "Local mode: no request is sent over the network (change the mode to search online).",
    "Adresse refusée par la sécurité (seuls les services savants publics en https sont contactés).":
        "Address refused for security reasons (only public scholarly services over https are contacted).",
    "Une opération est déjà en cours sur cet élément.": "An operation is already running on this item.",
    "Étagère en lecture seule (références de Mathlib).": "Read-only shelf (Mathlib references).",
    "Ce bloc a été modifié à la main : confirmez pour le régénérer (votre version reste dans l'historique).":
        "This block was edited by hand: confirm to regenerate it (your version stays in the history).",
    "Fichier trop volumineux.": "File too large.",
    "Type de fichier non pris en charge.": "File type not supported.",
    "Archive refusée (chemins dangereux, liens ou taille excessive).":
        "Archive refused (dangerous paths, links or excessive size).",
    "Identifiant non reconnu (DOI, arXiv, ISBN, zbMATH, OpenAlex ou adresse web).":
        "Identifier not recognised (DOI, arXiv, ISBN, zbMATH, OpenAlex or web address).",
    "Aucune notice trouvée pour cet identifiant.": "No record found for this identifier.",
    "Le service n'a pas répondu ({why}). Réessayez plus tard.": "The service did not answer ({why}). Try again later.",
    "Créé depuis {paper} ({where}).": "Created from {paper} ({where}).",
    "Références inventées par l'IA retirées : {keys}.": "References invented by the AI removed: {keys}.",
    "Le contenu à publier a changé : relisez la nouvelle liste avant de confirmer.":
        "What would be published has changed: review the new list before confirming.",
    "Préparez d'abord la publication (liste de ce qui sera publié).":
        "Prepare the publication first (list of what will be published).",
    "Construisez d'abord l'aperçu local.": "Build the local preview first.",
    "Aucun accès GitHub : ajoutez un jeton (fournisseur « github ») ou connectez gh.":
        "No GitHub access: add a token (provider « github ») or log in with gh.",
    "GitHub a refusé l'envoi (historique différent) : rien n'a été écrasé.":
        "GitHub refused the push (diverging history): nothing was overwritten.",
    "Aucun résultat à publier dans ce projet.": "No result to publish in this project.",
    # ---- publish: precise GitHub errors (session S-Q)
    "GitHub refuse le jeton : il est expiré, révoqué ou mal copié. Créez-en un nouveau et collez-le dans Réglages → "
    "Clés.": "GitHub refuses the token: it is expired, revoked or mis-pasted. Create a new one and paste it in "
             "Settings → Keys.",
    "Le jeton GitHub (classique) n'a pas le droit « {scope} ». Sur {settings}, modifiez le jeton, cochez « {scope} » "
    "(et « workflow »), enregistrez, puis réessayez.":
        "The GitHub token (classic) lacks the « {scope} » scope. On {settings}, edit the token, tick « {scope} » "
        "(and « workflow »), save, then try again.",
    "Le jeton GitHub (à accès précis) n'a pas la permission {permission}. Sur {settings}, modifiez le jeton "
    "(Repository permissions), enregistrez, puis réessayez.":
        "The GitHub token (fine-grained) lacks the permission {permission}. On {settings}, edit the token "
        "(Repository permissions), save, then try again.",
    "L'organisation {org} impose la connexion SSO (SAML) : autorisez ce jeton pour elle sur GitHub ({url}), puis "
    "réessayez.": "The organisation {org} enforces SSO (SAML): authorise this token for it on GitHub ({url}), then "
                  "try again.",
    "L'organisation {org} exige la double authentification (2FA) : activez-la sur votre compte GitHub, puis "
    "réessayez.": "The organisation {org} requires two-factor authentication (2FA): enable it on your GitHub "
                  "account, then try again.",
    "GitHub limite le nombre de requêtes : réessayez dans quelques minutes.":
        "GitHub is rate-limiting requests: try again in a few minutes.",
    "Le dépôt {repo} existe, mais ce jeton n'y a pas accès : ajoutez-le dans « Repository access » du jeton "
    "({settings}).": "The repository {repo} exists but this token cannot access it: add it under « Repository "
                     "access » of the token ({settings}).",
    "Organisation {org} introuvable, ou vous n'en êtes pas membre.":
        "Organisation {org} not found, or you are not a member.",
    "GitHub refuse l'opération : {message}": "GitHub refuses the operation: {message}",
    "GitHub a répondu une erreur ({status}) : {message}": "GitHub answered an error ({status}): {message}",
    "Impossible de joindre GitHub : vérifiez la connexion Internet.":
        "Cannot reach GitHub: check the Internet connection.",
    "Dépôt {repo} introuvable : cochez « Créer le dépôt », ou vérifiez le nom (un jeton à accès précis ne voit que "
    "les dépôts qu'on lui a donnés).": "Repository {repo} not found: tick « Create the repository », or check the "
                                      "name (a fine-grained token only sees the repositories it was given).",
    "Impossible de récupérer le dépôt (git clone).": "Cannot fetch the repository (git clone).",
    "GitHub a refusé l'envoi (git push).": "GitHub refused the push (git push).",
    "Échec de la préparation de l'envoi (git commit).": "Preparing the push failed (git commit).",
    "Nom de dépôt invalide : écrivez compte/nom.": "Invalid repository name: write account/name.",
    # ---- « consigne de recherche » and suggestions (session S-Q)
    "(Calcul : cellule {id}, pas encore exécutée)": "(Calcul: cell {id}, not run yet)",
    "(Figure : carnet Calcul, cellule {id})": "(Figure: Calcul notebook, cell {id})",
    "Ajoute le résultat à l'article avec son statut Lean (énoncé et preuve vérifiés par le pipeline normal).":
        "Adds the result to the article with its Lean status (statement and proof checked by the normal pipeline).",
    "Arrêt : limite atteinte ({why}).": "Stopped: limit reached ({why}).",
    "Calcul Sage proposé ; le résultat affiché est celui du carnet Calcul.":
        "Proposed Sage computation; the result shown is the one of the Calcul notebook.",
    "Conjecture (généralisation de {what})": "Conjecture (generalisation of {what})",
    "Consigne : {text}": "Instruction: {text}",
    "Contexte (réponse sourcée) : {text}": "Context (sourced answer): {text}",
    "Exemple ({what})": "Example ({what})",
    "Figure ({what})": "Figure ({what})",
    "Fin : {n} suggestion(s) à relire dans Article → Suggestions.":
        "End: {n} suggestion(s) to review in Article → Suggestions.",
    "Généralisation de {what}": "Generalisation of {what}",
    "Journal de recherche — {date} ({id})": "Research journal — {date} ({id})",
    "Résumé": "Abstract",
    "Test de la conjecture « {t} »": "Test of the conjecture « {t} »",
    "Théorème (généralisation de {what}, vérifiée par Lean)": "Theorem (generalisation of {what}, verified by Lean)",
    "{what} : pas encore vérifié par Lean (dossier « {title} »).": "{what}: not verified by Lean yet (dossier « {title} »).",
    "{what} : preuve vérifiée par Lean (dossier « {title} »).": "{what}: proof verified by Lean (dossier « {title} »).",
    "Écrivez une consigne (par exemple : « vérifie le théorème 2 avec Lean »).":
        "Write an instruction (for example: « check theorem 2 with Lean »).",
    "Consigne non comprise : demandez une vérification Lean, des exemples, des figures, une amélioration de la "
    "rédaction ou une généralisation.": "Instruction not understood: ask for a Lean check, examples, figures, better "
                                       "wording or a generalisation.",
    "Une consigne est déjà en cours dans ce projet : arrêtez-la ou attendez la fin.":
        "An instruction is already running in this project: stop it or wait for the end.",
    "Le texte visé a changé depuis la suggestion : elle n'a pas été appliquée.":
        "The targeted text changed since the suggestion: it was not applied.",
    "Cette suggestion a déjà été traitée.": "This suggestion was already handled.",
    "Cette consigne est terminée : lancez-en une nouvelle.": "This instruction is finished: start a new one.",
    "Déjà dans l'article.": "Already in the article.",
    "Reprise de la consigne.": "Instruction resumed.",
    "Modèle trop lent : appel abandonné ({role}).": "Model too slow: call abandoned ({role}).",
})

# ---- research workshop: notes, conjectures, proof plans, learning, update checkers (session S-G)
EN.update({
    'Ajouter {name} à {ws}': 'Add {name} to {ws}',
    "Après la mise à jour ({reason}), Lean n'accepte plus cette preuve : à revérifier.": 'After the update ({reason}), Lean no longer accepts this proof: needs re-checking.',
    'Aucun modèle disponible ({err}).': 'No model available ({err}).',
    "Cet espace de travail n'est pas géré par Madalean (lecture seule).": 'This workspace is not managed by Madalean (read-only).',
    "Cette expérience exécute du code sur l'ordinateur hôte : relisez-la et approuvez-la d'abord.": 'This experiment runs code on the host computer: read it and approve it first.',
    'Cette note ne contient aucun bloc ```lean.': 'This note has no ```lean block.',
    'Conjecture proposée.': 'Conjecture proposed.',
    'Conjecture réfutée : contre-exemple {w} vérifié indépendamment.': 'Conjecture refuted: counter-example {w} verified independently.',
    'Contre-exemple {w} : {verdict}.': 'Counter-example {w}: {verdict}.',
    "Copie de l'espace de travail, compilation et vérification avant la bascule.": 'Copy of the workspace, build and verification before switching.',
    'Corrigez-la : Lean vérifiera votre correction.': 'Fix it: Lean will check your correction.',
    'Dossiers travaillés :': 'Dossiers worked on:',
    'Dépendance de Mathlib : elle change avec Mathlib (mise à jour « Lean + Mathlib »), jamais seule.': 'Dependency of Mathlib: it changes with Mathlib (the « Lean + Mathlib » update), never alone.',
    'Dépendance indirecte : mise à jour par le paquet qui la requiert.': 'Indirect dependency: updated by the package that requires it.',
    'Expérience ({lang}) : {verdict}.': 'Experiment ({lang}): {verdict}.',
    'Expérience refusée : {why}.': 'Experiment refused: {why}.',
    'Idées, questions :': 'Ideas, questions:',
    "Installation manuelle pour l'instant : suivez les étapes indiquées.": 'Manual installation for now: follow the steps shown.',
    'Installé hors gestionnaire de paquets : voir le site du projet.': 'Installed outside the package manager: see the project website.',
    'Installé hors gestionnaire de paquets. Commande exacte (à lancer vous-même) : {cmd}': 'Installed outside the package manager. Exact command (run it yourself): {cmd}',
    'Journal de recherche — {date}': 'Research log — {date}',
    'Lean : {k} cas sur {n} vérifiés.': 'Lean: {k} of {n} cases verified.',
    "Les expériences exécutent du code sur l'ordinateur hôte : autorisées seulement depuis l'hôte (réglage).": 'Experiments run code on the host computer: allowed only from the host (setting).',
    'Les lemmes admis sont maintenant prouvés : la preuve est vérifiée par Lean (verdict strict).': 'The admitted lemmas are now proved: the proof is verified by Lean (strict verdict).',
    'Lisez la preuve : chaque étape est-elle juste ?': 'Read the proof: is every step right?',
    'Mise à jour : {n} preuve(s) à revérifier (voir la liste).': 'Update: {n} proof(s) to re-check (see the list).',
    'Mise à jour disponible dans les dépôts de votre distribution. Commande exacte (à lancer vous-même) : {cmd}': "Update available in your distribution's repositories. Exact command (run it yourself): {cmd}",
    "Notification seulement : une nouvelle version de Lean arrive avec la mise à jour de Mathlib. Un toolchain n'est jamais supprimé tant qu'un projet l'utilise.": 'Notification only: a new Lean version comes with the Mathlib update. A toolchain is never removed while a project uses it.',
    'Nouvelle version publiée en amont ({up}), pas encore dans les dépôts de votre distribution ({repo}) : attendre la mise à jour du paquet {pkg}.': "New upstream release ({up}), not yet in your distribution's repositories ({repo}): wait for the {pkg} package update.",
    'Objectif du jour :': "Today's goal:",
    "Paquet système : Madalean ne l'installe jamais lui-même.": 'System package: Madalean never installs it itself.',
    'Promue en théorème (preuve Lean).': 'Promoted to theorem (Lean proof).',
    "Prouvé modulo {n} lemme(s) admis ({names}) : ce n'est PAS une preuve vérifiée.": 'Proved modulo {n} admitted lemma(s) ({names}): this is NOT a verified proof.',
    'Quelle étape est fausse ? Expliquez pourquoi.': 'Which step is wrong? Explain why.',
    'Recherche bibliographique : {n} résultat(s).': 'Literature search: {n} result(s).',
    'Reconstruit : {names}': 'Rebuilds: {names}',
    'Redémarre le serveur ; vos données (~/.config/madalean) sont conservées.': 'Restarts the server; your data (~/.config/madalean) is kept.',
    'Une vérification est déjà en cours pour cette note.': 'A check is already running for this note.',
    "« {name} » est inconnu de l'index des déclarations de cet espace de travail : aucune explication n'est inventée.": '« {name} » is unknown to the declaration index of this workspace: no explanation is made up.',
    'Énoncé Lean accepté par Lean.': 'Lean statement accepted by Lean.',
    'Énoncé Lean de la conjecture.': 'Lean statement of the conjecture.',
    'Énoncé Lean refusé par Lean (ou non vérifié).': 'Lean statement refused by Lean (or not checked).',
    'Épinglé : la version de llama.cpp est celle validée avec les modèles (BENCH.md). Notification seulement.': 'Pinned: this llama.cpp version is the one validated with the models (BENCH.md). Notification only.',
    'Épinglé volontairement : Goedel-Prover-V2 a été entraîné sur exactement cette version de Lean et de Mathlib ; la changer dégraderait le prouveur.': 'Pinned on purpose: Goedel-Prover-V2 was trained on exactly this Lean and Mathlib version; changing it would degrade the prover.',
    'Aucun terminal trouvé : copiez la commande et lancez-la vous-même.': 'No terminal found: copy the command and run it yourself.',
    'Madalean {v} est installé et vérifié ; redémarrage au prochain moment calme.': 'Madalean {v} is installed and verified; restart at the next quiet moment.',
    "Mise à jour de Madalean refusée ({why}) : rien n'a changé.": 'Madalean update refused ({why}): nothing changed.',
    'Refusé avant compilation : {why}.': 'Refused before compiling: {why}.',
    # messages carried by exceptions (keys passed as variables)
    'Le code doit contenir « # PREDICATE » (avec def holds) puis « # SEARCH ».': 'The code must contain « # PREDICATE » (with def holds) then « # SEARCH ».',
    "Le modèle n'a pas produit de code d'expérience utilisable.": 'The model produced no usable experiment code.',
    "Le code a changé depuis que vous l'avez lu : relisez-le.": 'The code changed since you read it: read it again.',
    'Seule une preuve acceptée par Lean permet la promotion.': 'Only a proof accepted by Lean allows the promotion.',
    "Le plan contient des modifications manuelles : confirmez pour créer une nouvelle version proposée par l'IA (l'ancienne reste disponible).": 'The plan has manual edits: confirm to create a new AI-proposed version (the old one stays available).',
    "Le modèle n'a proposé aucun plan utilisable.": 'The model proposed no usable plan.',
    'Ce nœud a déjà son dossier : modifiez l\'énoncé dans le dossier.': 'This node already has its dossier: edit the statement in the dossier.',
    "Acceptez d'abord au moins un nœud du plan.": 'Accept at least one node of the plan first.',
    'Un lemme admis doit avoir un énoncé Lean accepté.': 'An admitted lemma needs an accepted Lean statement.',
    'Aucun lemme admis sous ce nœud.': 'No admitted lemma under this node.',
    "Preuve sans « by » : pas d'exercice possible.": 'Proof without « by »: no exercise possible.',
    'Le mode Apprendre demande une preuve vérifiée par Lean.': 'Learn mode needs a proof verified by Lean.',
    "Écrivez d'abord ce que vous avez essayé, même partiel.": 'First write what you tried, even partial.',
    "Avant le premier indice : écrivez ce que vous avez essayé (et votre confiance de 0 à 100).": 'Before the first hint: write what you tried (and your confidence from 0 to 100).',
    "Les indices se débloquent dans l'ordre.": 'Hints unlock in order.',
    "Dites d'abord ce que l'indice précédent vous a appris.": 'First say what the previous hint told you.',
    'Expliquez la preuve en quelques phrases.': 'Explain the proof in a few sentences.',
    "La preuve d'origine ne compile plus dans cet espace : à revérifier.": 'The original proof no longer compiles in this workspace: needs re-checking.',
    "Chaque étape de cette preuve se règle automatiquement : pas d'exercice utile.": 'Every step of this proof is solved automatically: no useful exercise.',
    "Dites d'abord où est l'erreur et pourquoi.": 'First say where the error is and why.',
    "Aucune variante plausible de cette preuve n'a été trouvée.": 'No plausible variant of this proof was found.',
})

# ---- Madalean 2.0 server (S-A): manual versions
EN.update({
    "Preuve modifiée à la main : Lean l'accepte.": 'Proof edited by hand: Lean accepts it.',
    'Preuve modifiée à la main : pas vérifiée par Lean ({why}).': 'Proof edited by hand: not verified by Lean ({why}).',
    'vérification non demandée': 'check not requested',
    'Explication modifiée à la main.': 'Explanation edited by hand.',
    'Preuve en langage naturel modifiée à la main.': 'Natural-language proof edited by hand.',
    "Lecture de l'énoncé modifiée à la main.": 'Reading of the statement edited by hand.',
})

# ---- Madalean 2.0 self-contained install (S-I): components of the prefix, embedded Tailscale node
EN.update({
    'LaTeX (tectonic de Madalean, hors ligne) présent : export PDF possible.':
        "LaTeX (Madalean's own tectonic, offline) present: PDF export available.",
    'Bac à sable actif (bubblewrap) : Lean, LaTeX et les expériences tournent sans réseau ni accès à vos fichiers.':
        'Sandbox active (bubblewrap): Lean, LaTeX and experiments run without network or access to your files.',
    'Bac à sable indisponible (bubblewrap absent ou espaces de noms utilisateur désactivés) : Lean, LaTeX et les expériences tournent sans isolation.':
        'Sandbox unavailable (bubblewrap missing or user namespaces disabled): Lean, LaTeX and experiments run without isolation.',
    'LaTeX du système (latexmk + XeLaTeX) utilisé : export PDF possible.':
        "System LaTeX (latexmk + XeLaTeX) used: PDF export available.",
    "Nouvelle version fournie par la mise à jour de Madalean : vérifiée (SHA-256) puis installée à côté de "
    "l'ancienne, qui reste disponible.":
        'New version delivered by the Madalean update: verified (SHA-256), then installed next to the old one, '
        'which stays available.',
    "Version plus récente publiée en amont. Madalean n'installe que des versions épinglées avec leur empreinte : "
    "elle arrivera avec une prochaine version de Madalean.":
        'A newer version was published upstream. Madalean only installs pinned versions with their checksum: it '
        'will come with a future Madalean release.',
    'Composant {name} {version} : installé ({path}).': 'Component {name} {version}: installed ({path}).',
    'Composant {name} : installé à la première utilisation.': 'Component {name}: installed on first use.',
    'Composant {name} : la version {pinned} est prête à être installée.':
        'Component {name}: version {pinned} is ready to be installed.',
    'Composant {name} absent ou incomplet : réparez-le.': 'Component {name} missing or incomplete: repair it.',
    # conductor (S-AI, D41)
    'Dirigé par {name} : plan en {n} étapes.': 'Directed by {name}: plan in {n} steps.',
    '{name} a corrigé l\'erreur Lean : {what}': '{name} fixed the Lean error: {what}',
    'Plafond atteint : continuer avec Claude (+{step} $) ?': 'Cap reached: continue with Claude (+{step} $)?',
    'Plafond de la demande relevé à {cap} $.': 'Request cap raised to {cap} $.',
    'Suite sans Claude : la chaîne gratuite habituelle continue.':
        'Continuing without Claude: the usual free chain goes on.',
    'Plafond mensuel atteint : suite sans Claude.': 'Monthly cap reached: continuing without Claude.',
    'Claude indisponible : {name} dirige à sa place.': 'Claude unavailable: {name} directs instead.',
    'Vérification finale ({name}) : énoncé, preuve et explication concordent.':
        'Final check ({name}): statement, proof and explanation agree.',
    'Vérification finale ({name}) : à revoir — {issues}': 'Final check ({name}): to review — {issues}',
    'Preuve vérifiée par Lean': 'Proof verified by Lean',
    # proof tournament (S-J)
    'Tournoi, round {k} : {models}.': 'Tournament, round {k}: {models}.',
    'Essai arrêté : la course est terminée.': 'Attempt stopped: the race is over.',
    'Modèle indisponible : {why}': 'Model unavailable: {why}',
    'Modèle payant dans le tournoi : {name} (coût estimé : au plus {cost} $ par essai).':
        'Paid model in the tournament: {name} (estimated cost: at most {cost} $ per attempt).',
    'Renfort payant : {name} entre au tournoi car les modèles gratuits ont échoué (plafonds : {cap_p} $ pour cette '
    'preuve, {cap_m} $ par mois).':
        'Paid reinforcement: {name} joins the tournament because the free models failed (caps: {cap_p} $ for this '
        'proof, {cap_m} $ per month).',
    'Tournoi : {name} a trouvé la preuve au round {k}. Classement des modèles mis à jour.':
        'Tournament: {name} found the proof in round {k}. Model leaderboard updated.',
    'Tournoi terminé sans preuve : {n} modèles essayés en {m} min.':
        'Tournament over without a proof: {n} models tried in {m} min.',
})

EN.update({
    # statement check and Mathlib-first search (S-K)
    "(mineur)": "(minor)",
    "Aucun résultat de Mathlib ne s'applique directement.": "No Mathlib result applies directly.",
    "Ce théorème est dans Mathlib sous le nom « {name} » : la preuve l'utilise directement.":
        "This theorem is in Mathlib under the name “{name}”: the proof uses it directly.",
    "Correction proposée : {fix}": "Suggested correction: {fix}",
    "Lean prouve l'énoncé directement ({tactic}) : il est vrai.": "Lean proves the statement directly ({tactic}): it is true.",
    "Lecture du modèle : {text}": "Model's reading: {text}",
    "Preuve Lean de la négation (vérifiée) :": "Lean proof of the negation (checked):",
    "Preuve non lancée : l'énoncé a été signalé ({verdict}). Corrigez-le ou cliquez sur « Prouver quand même ».":
        "Proof not started: the statement was flagged ({verdict}). Correct it or click “Prove anyway”.",
    "Preuve non lancée : l'énoncé est douteux.": "Proof not started: the statement is doubtful.",
    "Preuve non lancée : l'énoncé est faux.": "Proof not started: the statement is false.",
    "faux": "false",
    "douteux": "doubtful",
    "Recherche dans Mathlib : {n} résultats candidats.": "Mathlib search: {n} candidate results.",
    "Trouvé dans Mathlib : {name}.": "Found in Mathlib: {name}.",
    "Rien de directement applicable dans Mathlib ({n} candidats essayés).":
        "Nothing directly applicable in Mathlib ({n} candidates tried).",
    "Résultat connu de Mathlib donné au traducteur comme référence : {names}.":
        "Known Mathlib result given to the translator as a reference: {names}.",
    "Vérification de l'énoncé : fidèle à votre demande.": "Statement check: faithful to your request.",
    "Vérification de l'énoncé : douteux. La preuve n'est pas lancée : corrigez l'énoncé ou cliquez sur « Prouver "
    "quand même ».": "Statement check: doubtful. The proof is not started: correct the statement or click “Prove anyway”.",
    "Vérification de l'énoncé : FAUX, Lean prouve le contraire. La preuve n'est pas lancée : corrigez l'énoncé ou "
    "cliquez sur « Prouver quand même ».":
        "Statement check: FALSE, Lean proves the opposite. The proof is not started: correct the statement or click "
        "“Prove anyway”.",
    "Vérification de l'énoncé : rien n'a pu être vérifié (modèle ou Lean indisponible).":
        "Statement check: nothing could be checked (model or Lean unavailable).",
    "Mauvais objet": "Wrong object",
    "Hypothèse manquante": "Missing hypothesis",
    "Hypothèse en trop": "Extra hypothesis",
    "Mauvais quantificateur": "Wrong quantifier",
    "Mauvais sens": "Wrong direction",
    "Énoncé faux": "False statement",
    "Remarque": "Remark",
})

# ---- proof plans as a mind map (S-L)
EN.update({
    'Lemme évident : fermé par une tactique simple, vérifié par Lean.':
        'Obvious lemma: closed by a simple tactic, checked by Lean.',
    'Plan de preuve : les lemmes sont prouvés, la combinaison est vérifiée par Lean (verdict strict).':
        'Proof plan: the lemmas are proved, the combination is checked by Lean (strict verdict).',
    'Conditionnel — {n} trou(s) : la combinaison est vérifiée par Lean avec des lemmes admis (sorry). Ce n\'est PAS une preuve vérifiée.':
        'Conditional — {n} hole(s): the combination is checked by Lean with admitted lemmas (sorry). This is NOT a verified proof.',
    'Il faut d\'abord un énoncé Lean accepté.': 'An accepted Lean statement is needed first.',
    'Ce lemme n\'a pas d\'énoncé Lean : écrivez-le d\'abord.': 'This lemma has no Lean statement: write it first.',
    'Ce lemme appartient à une piste non choisie.': 'This lemma belongs to a track that is not chosen.',
    'Ce lemme est évident (fermé par une tactique simple) : il ne se découpe pas.':
        'This lemma is obvious (closed by a simple tactic): it is not split.',
    'Profondeur maximale atteinte ({n} niveaux) : prouvez ce lemme, changez de piste ou laissez un trou.':
        'Maximum depth reached ({n} levels): prove this lemma, switch track or leave a hole.',
    'Le plan a atteint {n} nœuds : simplifiez-le avant de découper encore.':
        'The plan has reached {n} nodes: simplify it before splitting further.',
    'Une analyse est déjà en cours pour ce plan.': 'An analysis is already running for this plan.',
    'Chaque piste proposée redisait le théorème lui-même : refusée (garde-fou contre les boucles).':
        'Every proposed track restated the theorem itself: refused (loop guard).',
    'Au plus {n} lemmes par piste.': 'At most {n} lemmas per track.',
    'Lean a refusé chaque découpage proposé (énoncés de lemmes invalides) : réessayez, donnez une piste ou changez de modèle.':
        'Lean rejected every proposed split (invalid lemma statements): try again, give a hint or change model.',
    'Aucune autre piste pour ce nœud : redécoupez-le ou laissez un trou.':
        'No other track for this node: split it again or leave a hole.',
    'Découpez d\'abord le théorème en lemmes.': 'Split the theorem into lemmas first.',
    'Ce lemme fait partie d\'un plan : redécoupez-le depuis le plan du théorème.':
        'This lemma belongs to a plan: split it from the theorem\'s plan.',
    # S-N: GPU lending with Ollama, idle unload
    # S-AS (D51): « Partage de la carte graphique avec Ollama »
    'Carte graphique : {who} ; {free} Mo libres. Ollama n\'est pas lancé : rien à partager.':
        'GPU: {who}; {free} MB free. Ollama is not running: nothing to share.',
    'Carte graphique : {who} ; {free} Mo libres. Partage avec Ollama désactivé : si la place manque, le modèle local '
    'tourne en partie sur le processeur.':
        'GPU: {who}; {free} MB free. Sharing with Ollama is off: when memory is short, the local model runs partly '
        'on the processor.',
    'Carte graphique : {who} ; {free} Mo libres. Partage avec Ollama activé : si la place manque, Madalean fait '
    'décharger les modèles d\'Ollama (rechargés à la demande), jamais pendant qu\'il répond à une autre application, '
    'et rend la carte après {min} min sans utilisation.':
        'GPU: {who}; {free} MB free. Sharing with Ollama is on: when memory is short, Madalean asks Ollama to unload '
        'its models (reloaded on demand), never while it is answering another application, and gives the GPU back '
        'after {min} min without use.',
    'Le moteur des modèles locaux est la version « processeur » alors que la carte graphique {gpu} fonctionne : '
    'réparez-le pour installer la version CUDA (ici 5 à 7 fois plus rapide).':
        'The local model engine is the « processor » build although the {gpu} GPU works: repair it to install the '
        'CUDA build (5 to 7 times faster here).',
    'Partage de la carte graphique avec Ollama désactivé : le modèle utilise la mémoire graphique libre (en partie '
    'sur le processeur, plus lent).':
        'GPU sharing with Ollama is off: the model uses the free GPU memory (partly on the processor, slower).',
    'Ollama répond toujours à une autre application : Madalean ne l\'interrompt pas et confie la tâche au modèle '
    'suivant (en ligne).':
        'Ollama is still answering another application: Madalean does not interrupt it and hands the task to the '
        'next model (online).',
    'Ollama répond toujours à une autre application : Madalean ne l\'interrompt pas et charge son modèle avec la '
    'mémoire graphique libre (en partie sur le processeur, plus lent).':
        'Ollama is still answering another application: Madalean does not interrupt it and loads its model with the '
        'free GPU memory (partly on the processor, slower).',
    'Ollama répond à une autre application : Madalean attend qu\'il ait fini (au plus {s} s) avant de lui emprunter '
    'la carte graphique.':
        'Ollama is answering another application: Madalean waits for it to finish (at most {s} s) before borrowing '
        'the GPU.',
    'Carte graphique prêtée par Ollama : {models} déchargé(s) (Ollama les rechargera à la demande).':
        'GPU lent by Ollama: {models} unloaded (Ollama reloads them on demand).',
    'Modèle local arrêté après {m} min sans utilisation : la carte graphique est rendue aux autres applications.':
        'Local model stopped after {m} min without use: the GPU is given back to the other applications.',
    # session S-M: Calcul, library catalogue
    'Calcul du {d}': 'Computation of {d}',
    "Ce code a été écrit par l'assistant : relisez-le et approuvez-le d'abord.":
        'This code was written by the assistant: read it and approve it first.',
    "Exécutez d'abord la cellule.": 'Run the cell first.',
    "Image PNG attendue.": "A PNG image was expected.",
    "Noyau indisponible ({err}).": "Kernel unavailable ({err}).",
    "Rien à exécuter.": "Nothing to run.",
    "Le modèle n'a pas proposé de code ; reformulez la demande.": 'The model proposed no code; rephrase the request.',
    'Résultat de calcul': 'Computation result',
    'conditionnel (lemmes admis : {a})': 'conditional (admitted lemmas: {a})',
    'vérifié par Lean': 'verified by Lean',
    'Bibliothèque de résultats': 'Library of results',
})

# ---- article editor: LaTeX project, compilation diagnostics (session S-R, docs/ARTICLE.md)
EN.update({
    'Le paquet {name} est déjà chargé par {by}.': 'Package {name} is already loaded by {by}.',
    "Le moteur TeX de Madalean (tectonic) n'est pas installé : réparez « TeX » dans Système.": 'Madalean’s TeX engine (tectonic) is not installed: repair “TeX” in System.',
    "Référence \\ref{{{name}}} vers une étiquette qui n'existe pas.": 'Reference \\ref{{{name}}} points to a label that does not exist.',
    'Citation {name} absente de la bibliothèque du projet.': 'Citation {name} is not in the project’s library.',
    '{n} ligne(s) dépassent légèrement la marge.': '{n} line(s) slightly overflow the margin.',
    "Le paquet {name} a besoin d'exécuter des programmes : refusé. {instead}": 'Package {name} needs to run programs: refused. {instead}',
    '{n} fichier(s) du TeX de Madalean ne sont pas encore téléchargés ({files}) : téléchargez-les une fois, ensuite tout marche hors ligne.': '{n} file(s) of Madalean’s TeX are not downloaded yet ({files}): download them once, then everything works offline.',
    'La compilation a dépassé {s} s.': 'Compilation took more than {s} s.',
    'Le fichier {file} est dans le TeX de Madalean mais pas encore téléchargé : téléchargez-le une fois (ensuite tout marche hors ligne).': 'File {file} is in Madalean’s TeX but not downloaded yet: download it once (then everything works offline).',
    "Le fichier {file} n'existe pas dans le TeX de Madalean. Retirez ce paquet ou remplacez-le.": 'File {file} does not exist in Madalean’s TeX. Remove this package or replace it.',
    "Une police utilisée par la mise en page n'est pas encore téléchargée : téléchargez-la une fois.": 'A font used by the layout is not downloaded yet: download it once.',
    'Construction refusée pour la sécurité ({what}) : Madalean ne compile pas ce qui lit ou écrit des fichiers hors du projet, lance des commandes ou reconstruit des noms de commandes.': 'Construct refused for security ({what}): Madalean does not compile what reads or writes files outside the project, runs commands or rebuilds command names.',
    "« {name} » n'est ni dans le TeX de Madalean ni téléchargeable : il ne peut pas être utilisé ici. Retirez-le ou choisissez une autre classe.": '“{name}” is neither in Madalean’s TeX nor downloadable: it cannot be used here. Remove it or choose another class.',
    '{why} demande le paquet {name}.': '{why} needs package {name}.',
    'Le paquet {name} est chargé deux fois.': 'Package {name} is loaded twice.',
    'cleveref doit être chargé après hyperref.': 'cleveref must be loaded after hyperref.',
    "La commande \\{cmd} vient du paquet {pkg}, qui n'est pas chargé.": 'Command \\{cmd} comes from package {pkg}, which is not loaded.',
    'Commande inconnue \\{cmd}. Vouliez-vous écrire \\{close} ?': 'Unknown command \\{cmd}. Did you mean \\{close}?',
    'Commande inconnue \\{cmd} : définissez-la dans les macros (Options avancées) ou corrigez-la.': 'Unknown command \\{cmd}: define it in the macros (Advanced options) or correct it.',
    "L'environnement {env} vient du paquet {pkg}, qui n'est pas chargé.": 'Environment {env} comes from package {pkg}, which is not loaded.',
    "L'environnement {env} n'est pas défini : ajoutez-le aux environnements de théorèmes (Options avancées) ou corrigez son nom.": 'Environment {env} is not defined: add it to the theorem environments (Advanced options) or correct its name.',
    'Une formule est hors des $…$ (ou un _ ou ^ est dans le texte). Entourez-la de $…$ ou écrivez \\_.': 'A formula is outside $…$ (or a _ or ^ is in the text). Put it inside $…$ or write \\_.',
    'Accolades { } mal appariées près de cette ligne.': 'Unbalanced braces { } near this line.',
    "Un \\begin{…} n'est pas fermé par le bon \\end{…}.": 'A \\begin{…} is not closed by the matching \\end{…}.',
    'Du texte se trouve avant \\begin{document} (dans le préambule).': 'There is text before \\begin{document} (in the preamble).',
    'Erreur LaTeX : {raw}': 'LaTeX error: {raw}',
    'Ce fichier a changé ailleurs (autre appareil, suggestion acceptée ou import).': 'This file changed elsewhere (another device, an accepted suggestion or an import).',
    'Chemin de fichier refusé.': 'File path refused.',
    'Fichier trop volumineux.': 'File too large.',
    'Modèle inconnu.': 'Unknown template.',
    'Construction LaTeX refusée pour la sécurité ({found}).': 'LaTeX construct refused for security ({found}).',
    "Le texte visé par la suggestion n'existe plus.": 'The text the suggestion targets no longer exists.',
    "Le texte visé par la suggestion a changé : elle ne peut plus s'appliquer.": 'The text the suggestion targets changed: it can no longer apply.',
    'Cette suggestion a déjà été traitée.': 'This suggestion was already handled.',
    "Format d'image refusé (PNG, JPEG ou PDF).": 'Image format refused (PNG, JPEG or PDF).',
    'Archive illisible ou trop grande.': 'Unreadable or too large archive.',
    "L'archive ne contient pas de main.tex à sa racine.": 'The archive has no main.tex at its root.',
    "Fichier qui n'est pas en UTF-8 : {file}.": 'File not in UTF-8: {file}.',
    "Mode local : rien n'est téléchargé (changez de mode pour télécharger les fichiers TeX).": 'Local mode: nothing is downloaded (change the mode to download the TeX files).',
    'Une opération est déjà en cours sur cet élément.': 'An operation is already running on this item.',
    'Introuvable.': 'Not found.',
    'Le projet LaTeX existe déjà.': 'The LaTeX project already exists.',
    'Champs refusés : {fields}.': 'Refused fields: {fields}.',
})

EN.update({
    'Énoncé vide de sens (`True`, `x = x`) : nouvel essai.': 'Statement says nothing (`True`, `x = x`): new attempt.',
})

# ---------------------------------------------------------------- Hugging Face, Goedel online, local fallback (S-T)
EN.update({
    "Aucun modèle en ligne n'a pu travailler (mode « en ligne » : pas de modèle local).":
        "No online model could work (« online » mode: no local model).",
    "Aucun modèle en ligne n'a pu travailler : repli sur le modèle local.":
        "No online model could work: falling back to the local model.",
    'Goedel en ligne indisponible ({why}).': 'Goedel online unavailable ({why}).',
    'Goedel-Prover en ligne : {name}, la boucle de Goedel servie par Hugging Face (payant, plafonds : {cap_p} $ pour '
    'cette preuve, {cap_m} $ par mois).':
        'Goedel-Prover online: {name}, Goedel’s own loop served through Hugging Face (paid, caps: {cap_p} $ for this '
        'proof, {cap_m} $ per month).',
    "Pas d'accès à Internet : la preuve est cherchée avec le modèle local.":
        "No Internet access: the proof is searched with the local model.",
    # leancheck.EXEC_RISKS labels (shown in « Refusé avant compilation : … »)
    "commande exécutée à la compilation (#eval…)": "command run at compile time (#eval…)",
    "code exécuté au chargement (initialize)": "code run at load time (initialize)",
    "méta-programmation (élaborateur, macro, syntaxe)": "meta-programming (elaborator, macro, syntax)",
    "attribut qui enregistre du code exécutable": "attribute that registers executable code",
    "accès au système (IO, unsafe)": "system access (IO, unsafe)",
    "code natif (native_decide)": "native code (native_decide)",
    "import d'un module non autorisé": "import of a module that is not allowed",
})

# S-AC: health self-test of the sandboxed tools (update_checkers/selftest.py)
EN.update({
    "L'auto-test est déjà en cours : patientez une minute.": "The self-test is already running: wait a minute.",
    "Auto-test {part} : en cours…": "Self-test {part}: running…",
    "Auto-test {part} : pas encore lancé (il se lance après chaque mise à jour).":
        "Self-test {part}: not run yet (it runs after every update).",
    "Auto-test {part} : non installé, rien à tester.": "Self-test {part}: not installed, nothing to test.",
    "Auto-test {part} : {n} essais réussis dans le bac à sable ({s} s, le {when}).":
        "Self-test {part}: {n} checks passed in the sandbox ({s} s, on {when}).",
    "Auto-test {part} : {n} essai(s) en échec : {names}. « Réparer » réinitialise les caches des outils et relance "
    "le test.": "Self-test {part}: {n} check(s) failed: {names}. “Repair” resets the tools' caches and runs the test "
                "again.",
    "Auto-test {part} : l'outil n'a pas démarré ({error}). « Réparer » réinitialise les caches des outils et relance "
    "le test.": "Self-test {part}: the tool did not start ({error}). “Repair” resets the tools' caches and runs the "
                "test again.",
    "Auto-test après mise à jour : {names} ne fonctionne plus correctement. Voir Réglages › Système › État de santé.":
        "Self-test after an update: {names} no longer works correctly. See Settings › System › Health.",
})

# S-AB: Calcul notebook (fast transcription, replaced requests, cells running)
EN.update({
    "Des cellules sont en cours d'exécution : attendez la fin ou interrompez-les.":
        "Cells are running: wait for them to finish or interrupt them.",
    "Une demande plus récente a remplacé celle-ci.": "A newer request replaced this one.",
    # S-AJ (D42): « Expliquer les étapes du calcul »
    "Exécutez d'abord la cellule : il faut un résultat à expliquer.":
        "Run the cell first: there must be a result to explain.",
})
# S-AF (D38): stages in parallel, nothing redone twice
EN.update({
    "Essai arrêté : la preuve a été trouvée autrement.": "Attempt stopped: the proof was found another way.",
    "Énoncé déjà vérifié avec cette version de Mathlib : le résultat est repris sans refaire la vérification.":
        "Statement already checked with this Mathlib version: the result is reused without checking again.",
    "Déjà cherché dans Mathlib pour cet énoncé : rien de directement applicable, la recherche de preuve commence tout "
    "de suite.": "Already searched in Mathlib for this statement: nothing directly applicable, the proof search starts "
                 "at once.",
    "Déjà trouvé dans Mathlib pour cet énoncé ({name}) : preuve vérifiée à nouveau par Lean.":
        "Already found in Mathlib for this statement ({name}): proof checked again by Lean.",
    "{text}": "{text}",                 # S-AG: a message already written in the interface's language (intent.py)
})

# ---- warm Lean (S-AE, D37)
EN.update({
    "Lean prêt d'avance : désactivé ; chaque essai relance Lean et recharge Mathlib.":
        "Lean ready in advance: off; every attempt starts Lean and loads Mathlib again.",
    "Lean prêt d'avance mis de côté pour {ws} : un de ses résultats différait de la vérification complète. Les essais "
    "sont vérifiés par un Lean relancé à chaque fois.":
        "Lean ready in advance set aside for {ws}: one of its results differed from the full check. Attempts are "
        "checked by a Lean started each time.",
    "Lean prêt d'avance pour {ws} : chaque essai est vérifié en une fraction de seconde ({gb} Go de mémoire, arrêté "
    "après {min} min sans essai). Une preuve trouvée est toujours revérifiée par un Lean neuf.":
        "Lean ready in advance for {ws}: each attempt is checked in a fraction of a second ({gb} GB of memory, stopped "
        "after {min} min without an attempt). A proof that is found is always checked again by a new Lean.",
    "Lean prêt d'avance : chargement de Mathlib pour {ws}…": "Lean ready in advance: loading Mathlib for {ws}…",
    "Lean prêt d'avance n'a pas pu démarrer ({why}) : les essais sont vérifiés par un Lean relancé à chaque fois.":
        "Lean ready in advance could not start ({why}): attempts are checked by a Lean started each time.",
    "Lean prêt d'avance : au repos ; il démarre avec la prochaine preuve et s'arrête après {min} min sans essai.":
        "Lean ready in advance: at rest; it starts with the next proof and stops after {min} min without an attempt.",
})

# ---- a proof kept aside before a « douteux » / « faux » verdict (S-AN, D46)
EN.update({
    "Une preuve a été trouvée pendant la vérification de l'énoncé. Elle est mise de côté, sans être enregistrée comme "
    "vérifiée : « Prouver quand même » la revérifie avec Lean au lieu de relancer la recherche ; corriger l'énoncé "
    "l'abandonne.":
        "A proof was found while the statement was being checked. It is kept aside, not recorded as verified: “Prove "
        "anyway” checks it again with Lean instead of searching again; correcting the statement discards it.",
    "La preuve mise de côté n'est pas acceptée par Lean : nouvelle recherche.":
        "Lean does not accept the proof kept aside: searching again.",
    "Preuve mise de côté revérifiée par Lean et enregistrée ({s:.0f} s).":
        "Proof kept aside checked again by Lean and recorded ({s:.0f} s).",
})

# ---- Calcul ready in advance (S-AO, D47)
EN.update({
    "Calcul prêt d'avance : désactivé ; le noyau d'un document démarre à sa première exécution.":
        "Calcul ready in advance: off; a document's kernel starts at its first run.",
    "Calcul prêt d'avance n'a pas pu préparer un noyau ({why}) : il démarrera à la première exécution.":
        "Calcul ready in advance could not prepare a kernel ({why}): it will start at the first run.",
    "Calcul prêt d'avance : préparation de {n} noyau(x) en arrière-plan…":
        "Calcul ready in advance: preparing {n} kernel(s) in the background…",
    "Calcul prêt d'avance : {n} noyau(x) prêt(s) ; dernière préparation en {s} s. Arrêt après {min} min sans activité.":
        "Calcul ready in advance: {n} kernel(s) ready; last preparation took {s} s. Stopped after {min} min without "
        "activity.",
    "Calcul prêt d'avance : noyau non préparé, mémoire disponible insuffisante ({why}).":
        "Calcul ready in advance: kernel not prepared, not enough memory available ({why}).",
    "Calcul prêt d'avance : au repos ; le noyau d'un document démarre dès son ouverture et s'arrête après {min} min "
    "sans activité.":
        "Calcul ready in advance: at rest; a document's kernel starts as soon as it is opened and stops after {min} "
        "min without activity.",
})

# ---- dossier history compaction (S-AO, D47)
EN.update({
    "Historique compacté : {events} événements plus anciens ({jobs} travaux) résumés ; le détail est conservé à part.":
        "History compacted: {events} older events ({jobs} jobs) summarised; the details are kept aside.",
})
# ---- certificates: Sage computes, Lean checks (S-AT, D52)
EN.update({
    "Primalité": "Primality",
    "Nombre composé": "Composite number",
    "Calcul sur des nombres": "Arithmetic on numbers",
    "Puissance modulaire": "Modular power",
    "Identité polynomiale": "Polynomial identity",
    "Conséquence d'équations polynomiales": "Consequence of polynomial equations",
    "Inégalités linéaires": "Linear inequalities",
    "Inégalité polynomiale (somme de carrés)": "Polynomial inequality (sum of squares)",
    "Existence (témoin)": "Existence (witness)",
    "Contre-exemple": "Counterexample",
    "Inégalité numérique": "Numerical inequality",
    "Vérification exhaustive": "Exhaustive check",
    " plus la constante {c}": " plus the constant {c}",
    ", pour la puissance {k} du but": ", for the power {k} of the goal",
    "Aucun témoin trouvé par Sage ({title}).": "Sage found no witness ({title}).",
    "Calcul direct sur des nombres.": "Direct computation on numbers.",
    "Ce résultat n'a pas de certificat pris en charge.": "No supported certificate for this result.",
    "Certificat": "Certificate",
    "Certificat : Lean vérifie le témoin…": "Certificate: Lean is checking the witness…",
    "Certificat : calcul d'un témoin par Sage…": "Certificate: Sage is computing a witness…",
    "Certificat : {what}": "Certificate: {what}",
    "Certificat impossible : SageMath n'est pas disponible ({title}).":
        "No certificate: SageMath is not available ({title}).",
    "Certificat refusé par Lean ({title}) : le témoin calculé ne passe pas la vérification.":
        "Certificate refused by Lean ({title}): the computed witness does not pass the check.",
    "Certificat vérifié par Lean ({title}).": "Certificate checked by Lean ({title}).",
    "Certificat ({title}) : témoin calculé par Sage, vérifié par Lean.":
        "Certificate ({title}): witness computed by Sage, checked by Lean.",
    "Certificat ({title}) : vérifié par Lean par un calcul direct.":
        "Certificate ({title}): checked by Lean by a direct computation.",
    "Combinaison des hypothèses trouvée (base de Gröbner){pw} :": "Combination of the hypotheses found (Gröbner basis){pw}:",
    "Combinaison linéaire des hypothèses qui donne le résultat (certificat de Farkas) :":
        "Linear combination of the hypotheses that gives the result (Farkas certificate):",
    "Contre-exemple : {w}.": "Counterexample: {w}.",
    "Diviseur trouvé : {n} = {d} × {q}.": "Divisor found: {n} = {d} × {q}.",
    "Encadrements calculés par Sage, vérifiés par Lean :": "Bounds computed by Sage, checked by Lean:",
    "Identité polynomiale : les deux membres ont le même développement.":
        "Polynomial identity: both sides expand to the same polynomial.",
    "Indisponible dans la démonstration.": "Not available in the demo.",
    "L'espace de travail Lean n'est pas prêt.": "The Lean workspace is not ready.",
    "Le calcul indique que l'énoncé est faux ({title} : {why}).":
        "The computation says the statement is false ({title}: {why}).",
    "Pas de certificat pour cet énoncé.": "No certificate for this statement.",
    "Petit nombre : Lean essaie lui-même tous les diviseurs possibles.":
        "Small number: Lean tries every possible divisor itself.",
    "Puissance modulaire par carrés successifs ({k} étapes) : reste {r}.":
        "Modular power by repeated squaring ({k} steps): remainder {r}.",
    "Témoin : {w}.": "Witness: {w}.",
    "Témoin de primalité (Pratt) : a = {a} est d'ordre p − 1 modulo p, avec p − 1 = {fact}.":
        "Primality witness (Pratt): a = {a} has order p − 1 modulo p, with p − 1 = {fact}.",
    "Vérification exhaustive : {n} cas.": "Exhaustive check: {n} cases.",
    "aucune hypothèse nécessaire": "no hypothesis needed",
    "{c} × ({f})²": "{c} × ({f})²",
    "{c} × {h}": "{c} × {h}",
    "{h} multipliée par {c}": "{h} multiplied by {c}",
    "{h} × {c} × ({f})²": "{h} × {c} × ({f})²",
    "{lo} < {x} < {hi}": "{lo} < {x} < {hi}",
    "{n} nombres premiers intermédiaires certifiés de la même façon.":
        "{n} intermediate primes certified in the same way.",
    "Écriture comme somme de carrés{c} :": "Written as a sum of squares{c}:",
})

# ---------------------------------------------------------------- literature first (S-AX, D56)
EN.update({
    "Aucun résultat cité n'a d'énoncé Lean à utiliser.": "No cited result has a Lean statement to use.",
    "Ce résultat est déjà prouvé (Mathlib ou bibliothèque).": "This result is already proved (Mathlib or library).",
    "Ce résultat n'a pas d'énoncé Lean qui compile : rien à prouver.":
        "This result has no Lean statement that compiles: nothing to prove.",
    "Le dossier a déjà une preuve vérifiée.": "The dossier already has a verified proof.",
    "Lemme cité confié aux prouveurs : {title}.": "Cited lemma handed to the provers: {title}.",
    "Les résultats cités sont maintenant prouvés en Lean : la preuve est vérifiée (verdict strict).":
        "The cited results are now proved in Lean: the proof is verified (strict verdict).",
    "Littérature : mode local, aucune recherche en ligne.": "Literature: local mode, no online search.",
    "Littérature : rien de fiable trouvé pour cet énoncé (aucune référence avec un énoncé cité).":
        "Literature: nothing reliable found for this statement (no reference with a quoted statement).",
    "Littérature : {n} référence(s) avec un énoncé cité mot pour mot ({peer} publiée(s) dans une revue, "
    "{pre} prépublication(s)).":
        "Literature: {n} reference(s) with a statement quoted word for word ({peer} published in a journal, "
        "{pre} preprint(s)).",
    "Mode local : aucune recherche n'est envoyée sur le réseau (changez de mode pour chercher dans la littérature).":
        "Local mode: no search is sent over the network (change the mode to search the literature).",
    "Pas d'énoncé : écrivez ou traduisez d'abord l'énoncé.": "No statement: write or translate the statement first.",
    "Preuve conditionnelle : repose sur {refs} (résultat cité, non prouvé en Lean). Ce n'est PAS une preuve "
    "vérifiée.":
        "Conditional proof: relies on {refs} (cited result, not proved in Lean). This is NOT a verified proof.",
    "Référence ajoutée à la bibliographie : {ref}.": "Reference added to the bibliography: {ref}.",
    "Une recherche dans la littérature est déjà en cours pour ce dossier.":
        "A literature search is already running for this dossier.",
    "dans Mathlib : {name}": "in Mathlib: {name}",
    "prouvé en Lean": "proved in Lean",
    "énoncé Lean à prouver (preuve conditionnelle)": "Lean statement to prove (conditional proof)",
    "revue": "journal",
    "actes de conférence": "conference proceedings",
    "livre": "book",
    "prépublication": "preprint",
    "thèse": "thesis",
    "type inconnu": "unknown type",
    "Pièce jointe {n} : {name}.": "Attachment {n}: {name}.",
    "À prouver : {target}. Résultats fournis (pièces jointes, Sources du projet) : {n}.":
        "To prove: {target}. Results provided (attachments, project Sources): {n}.",
    "non formalisé": "not formalized",
    "dans Mathlib": "in Mathlib",
})

# ---------------------------------------------------------------- understanding and translation (S-BG, D65)
EN.update({
    "(sans source)":
        "(no source)",
    "Cet énoncé a déjà été refusé pour ce problème.":
        "This statement was already refused for this problem.",
    "Cette correction change l'énoncé demandé.":
        "This fix changes the statement you asked for.",
    "Deux traductions indépendantes : Lean n'a pas montré qu'elles disent la même chose. Comparez-les avant de choisir.":
        "Two independent translations: Lean did not show that they say the same thing. Compare them before choosing.",
    "En attente de votre validation.":
        "Waiting for your approval.",
    "L'existence énoncée est vraie par construction : elle ne dit rien du problème.":
        "The existence stated is true by construction: it says nothing about the problem.",
    "L'énoncé porte sur un type vide (« Fin 0 »…) : il est vrai ou faux pour une raison sans rapport avec le problème.":
        "The statement is about an empty type (“Fin 0”…): it is true or false for a reason unrelated to the problem.",
    "La conclusion est vraie par construction (« True », « x = x »).":
        "The conclusion is true by construction (“True”, “x = x”).",
    "La conclusion est « False » : l'énoncé ne dit rien du problème (une négation s'écrit « ¬ … » ou « ≠ »).":
        "The conclusion is “False”: the statement says nothing about the problem (a negation is written “¬ …” or “≠”).",
    "La conclusion ne dépend d'aucun objet ni d'aucun nombre du problème.":
        "The conclusion depends on no object and no number of the problem.",
    "La relecture de l'énoncé (sans voir le problème) ne mentionne pas : {names}.":
        "Read back without seeing the problem, the statement does not mention: {names}.",
    "Lean prouve l'énoncé d'un coup ({tactic}) alors que le problème est ouvert ou faux : ce n'est pas le même énoncé.":
        "Lean proves the statement at once ({tactic}) although the problem is open or false: it is not the same statement.",
    "Définition vide : {names}. L'énoncé ne dit rien du vrai objet.":
        "Empty definition: {names}. The statement says nothing of the real object.",
    "Lean prouve l'énoncé d'un coup ({tactic}) : ce résultat n'est pas si facile, l'énoncé ne le dit pas.":
        "Lean proves the statement at once ({tactic}): this result is not that easy, the statement does not say it.",
    "Lean prouve l'énoncé d'un coup ({tactic}).":
        "Lean proves the statement at once ({tactic}).",
    "Lean prouve le contraire de cet énoncé.":
        "Lean proves the opposite of this statement.",
    "Les corrections proposées tournent en rond (déjà vues pour ce dossier) : Madalean n'en propose plus. L'énoncé demandé reste la cible ; choisissez vous-même l'énoncé, ou traitez un résultat connu dans un sous-dossier.":
        "The suggested fixes go round in circles (already seen for this dossier): Madalean suggests no more of them. The statement you asked for stays the target; choose the statement yourself, or work on a known result in a sub-dossier.",
    "Les hypothèses se contredisent (Lean en déduit « False ») : l'énoncé est vrai à vide.":
        "The hypotheses contradict each other (Lean derives “False”): the statement is vacuously true.",
    "Mal compris : {why}":
        "Misunderstood: {why}",
    "Nombres ajoutés dans la conclusion, absents du problème : {names}.":
        "Numbers added in the conclusion, absent from the problem: {names}.",
    "Nombres du problème absents de l'énoncé Lean : {names}.":
        "Numbers of the problem absent from the Lean statement: {names}.",
    "Objets du problème absents de l'énoncé Lean : {names}.":
        "Objects of the problem absent from the Lean statement: {names}.",
    "Résultat connu, ouvert depuis « {title} ».":
        "Known result, opened from “{title}”.",
    "Traduction refusée : elle ne dit pas ce que dit le problème.":
        "Translation refused: it does not say what the problem says.",
    "L'IA a traduit le problème en Lean, mais la traduction est refusée.":
        "The AI translated the problem into Lean, but the translation is refused.",
    "Vérifiez que le problème est bien compris avant la traduction en Lean.":
        "Check that the problem is well understood before the translation into Lean.",
    "Vérifiez l'énoncé Lean avant la recherche de preuve.":
        "Check the Lean statement before the proof search.",
    "D'après ce qui a été trouvé, ce problème est ouvert : personne n'en connaît de preuve.":
        "According to what was found, this problem is open: nobody knows a proof of it.",
    "D'après ce qui a été trouvé, l'énoncé est faux tel quel.":
        "According to what was found, the statement is false as it is.",
    "Le statut de ce problème n'est pas clair.":
        "The status of this problem is not clear.",
    "Problème ouvert, d'après un modèle, à vérifier.":
        "Open problem according to a model, to be checked.",
    "Énoncé faux, d'après un modèle, à vérifier.":
        "False statement according to a model, to be checked.",
    "Statut incertain, d'après un modèle, à vérifier.":
        "Uncertain status according to a model, to be checked.",
    "ce n'est pas le bon objet":
        "it is not the right object",
    "c'est trop général":
        "it is too general",
    "il manque une hypothèse":
        "a hypothesis is missing",
    "ce n'est pas ce qui est affirmé":
        "it is not what is claimed",
    "une demande a été ignorée":
        "a request was ignored",
    "autre raison":
        "another reason",
    "Cette validation n'est plus d'actualité : relisez la version affichée.":
        "This approval is out of date: read the version shown now.",
    "Cet énoncé ne dit rien du problème : il ne peut pas être validé tel quel.":
        "This statement says nothing about the problem: it cannot be approved as it is.",
    "L'IA a traduit le problème en Lean. Lean comprend le code (cela ne dit pas qu'il est fidèle). Relisez-le : la preuve portera exactement sur ce texte.":
        "The AI translated the problem into Lean. Lean understands the code (this does not mean it is faithful). Read it: the proof will be about exactly this text.",
    "Sens validé.": "Meaning approved.", "Énoncé Lean validé.": "Lean statement approved.",
    "Sens corrigé : il est relu.": "Meaning corrected: it is read again.",
    "Énoncé Lean corrigé : il est refait.": "Lean statement corrected: it is redone.",
    "Sens refusé : il est relu.": "Meaning rejected: it is read again.",
    "Énoncé Lean refusé : il est refait.": "Lean statement rejected: it is redone.",
    "Cette traduction n'existe pas.":
        "This translation does not exist.",
    "Validez d'abord l'énoncé Lean de ce dossier (bouton « Prouver »).":
        "Approve the Lean statement of this dossier first (“Prove” button).",
    "Cet élément n'existe pas.":
        "This item does not exist.",
})
