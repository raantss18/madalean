"""Providers hub (session S-U): what each online service is good for in Madalean, its free tier or price, where the data
goes, and how to get a key — the data of Réglages → Fournisseurs (`GET /api/providers`) and of docs/PROVIDERS.md.

Every fact was read on the provider's own page on CHECKED (URLs in `sources`, summarised in docs/PROVIDERS.md). Free
tiers change often: the app shows « vérifié le … » and the integrator re-checks them at each release. Text is plain
language, FR + EN; the advanced details go in `details`."""
from __future__ import annotations

CHECKED = "2026-11-22"

GROUPS = [
    ("lean", "Preuves Lean", "Lean proofs"),
    ("writing", "Rédaction & LaTeX", "Writing & LaTeX"),
    ("code", "Code Sage / Python", "Sage / Python code"),
    ("web", "Recherche Internet", "Internet search"),
    ("science", "Recherche scientifique", "Scholarly search"),
    ("general", "Modèles généraux gratuits", "Free general models"),
    ("publish", "Publication", "Publishing"),
]

# The minimal setup shown at the top of the hub (« pour bien démarrer, 3 clés gratuites suffisent »).
STARTER = ["groq", "gemini", "tavily"]


def _c(id_: str, group: str, name: str, *, key: str | None, kind: str, price: str, integrated: str,
       good: tuple[str, str], tier: tuple[str, str], privacy: tuple[str, str], key_url: str = "",
       sources: list[str] | None = None, details: tuple[str, str] = ("", ""), prefix: str = "",
       models: list[str] | None = None) -> dict:
    """kind: llm (model provider) | search (Internet search) | keyless (works without key) | info (not callable) |
    token (a key for something else than models: GitHub publishing).
    price: free | free_tier | credits | paid. integrated: yes | auto (used when the provider lists it) | no | retired."""
    return {"id": id_, "group": group, "name": name, "key": key, "kind": kind, "price": price,
            "integrated": integrated, "good_for": {"fr": good[0], "en": good[1]}, "free_tier": {"fr": tier[0], "en": tier[1]},
            "privacy": {"fr": privacy[0], "en": privacy[1]}, "details": {"fr": details[0], "en": details[1]},
            "key_url": key_url, "sources": sources or [], "checked": CHECKED, "prefix": prefix, "models": models or []}


CARDS: list[dict] = [
    # ------------------------------------------------------------------ Lean proofs
    _c("leanstral", "lean", "Leanstral (Mistral)", key="mistral", kind="llm", price="free_tier", integrated="auto",
       good=("Agent de preuve Lean 4 de Mistral (code ouvert, Apache-2.0). Quand votre clé Mistral le propose, Madalean "
             "le met en tête du tournoi de preuve.",
             "Mistral's Lean 4 proof agent (open weights, Apache-2.0). When your Mistral key offers it, Madalean puts it "
             "first in the proof tournament."),
       tier=("Annoncé gratuit sur l'API Mistral (juillet 2026), mais la documentation Mistral indique « labs-leanstral-1-5 » "
             "retiré le 30/09/2026. Madalean le détecte tout seul s'il revient dans la liste de votre clé.",
             "Announced free on Mistral's API (July 2026), but Mistral's docs list « labs-leanstral-1-5 » as retired on "
             "2026-09-30. Madalean detects it automatically if your key lists it again."),
       privacy=("Envoyé chez Mistral (France/UE). Réglage « Data usage for improving our services » à désactiver dans la "
                "console Mistral (Privacy).",
                "Sent to Mistral (France/EU). Turn off « Data usage for improving our services » in the Mistral console "
                "(Privacy)."),
       key_url="https://console.mistral.ai/api-keys",
       sources=["https://mistral.ai/news/leanstral-1-5/", "https://docs.mistral.ai/models/model-cards/leanstral-1-5",
                "https://docs.mistral.ai/getting-started/models/models_overview/",
                "https://huggingface.co/mistralai/Leanstral-1.5-119B-A6B"],
       details=("119 Md de paramètres (6,5 Md actifs), contexte 256k, appels d'outils OpenAI. Entraîné avec retour du "
                "compilateur Lean et le serveur de langage Lean : Madalean lui donne lean_check, la recherche Mathlib et "
                "l'alias « lean_run_code ». Toute preuve est revérifiée par Lean (verdict strict). Aucun autre hébergeur "
                "public (OpenRouter, Hugging Face) au 22/11/2026.",
                "119B parameters (6.5B active), 256k context, OpenAI tool calls. Trained with Lean compiler feedback and "
                "the Lean language server: Madalean gives it lean_check, Mathlib search and the « lean_run_code » alias. "
                "Every proof is re-checked by Lean (strict verdict). No other public host (OpenRouter, Hugging Face) on "
                "2026-11-22."),
       models=["labs-leanstral-1-5"]),
    _c("huggingface", "lean", "Goedel-Prover-V2-32B (Hugging Face)", key="huggingface", kind="llm", price="credits",
       integrated="yes",
       good=("Le meilleur prouveur Lean ouvert, servi en ligne (featherless-ai) : il ouvre le tournoi quand le jeton est "
             "là, dans vos plafonds de dépense.",
             "The best open Lean prover, served online (featherless-ai): it opens the tournament when the token is set, "
             "within your spending caps."),
       tier=("Payant au jeton, sans marge. Compte gratuit : pas de crédit inclus ; compte PRO : 2 $ de crédits par mois.",
             "Pay per token, no markup. Free account: no included credit; PRO account: 2 USD of credits per month."),
       privacy=("Jeton envoyé uniquement à router.huggingface.co et huggingface.co ; Featherless dit ne jamais stocker les "
                "requêtes.",
                "Token sent only to router.huggingface.co and huggingface.co; Featherless says prompts are never stored."),
       key_url="https://huggingface.co/settings/tokens/new?ownUserPermissions=inference.serverless.write&tokenType=fineGrained",
       sources=["https://huggingface.co/docs/inference-providers/pricing",
                "https://huggingface.co/docs/inference-providers/providers/featherless-ai", "https://featherless.ai/pricing"],
       prefix="^hf_"),
    _c("featherless", "lean", "Featherless AI (direct)", key=None, kind="info", price="paid", integrated="no",
       good=("Héberge les prouveurs Lean ouverts (Goedel-Prover-V2, Kimina-Prover, BFS-Prover-V2, StepFun-Prover).",
             "Hosts the open Lean provers (Goedel-Prover-V2, Kimina-Prover, BFS-Prover-V2, StepFun-Prover)."),
       tier=("Pas de gratuit ; offre API à partir de 50 $/mois (l'offre Chat à 25 $ interdit l'usage par une app). "
             "Madalean passe par Hugging Face (même hébergeur, payé à l'usage).",
             "No free tier; API plan from 50 USD/month (the 25 USD Chat plan forbids app use). Madalean goes through "
             "Hugging Face instead (same host, pay per use)."),
       privacy=("Requêtes « jamais stockées » selon Featherless.", "Prompts « never stored » according to Featherless."),
       sources=["https://featherless.ai/pricing", "https://featherless.ai/models/Goedel-LM/Goedel-Prover-V2-32B"]),
    _c("aristotle", "lean", "Harmonic Aristotle", key=None, kind="info", price="credits", integrated="no",
       good=("Prouveur de Harmonic (IMO 2025). Aujourd'hui son API ne vérifie que Rust, C et Verilog.",
             "Harmonic's prover (IMO 2025). Today its API only verifies Rust, C and Verilog."),
       tier=("Crédits prépayés, prix non publiés. « Lean support will return in the coming months » (FAQ Harmonic). "
             "Non intégré : un fichier Lean y consommerait des crédits sans rien vérifier.",
             "Prepaid credits, prices not published. « Lean support will return in the coming months » (Harmonic FAQ). "
             "Not integrated: a Lean file would spend credits and verify nothing."),
       privacy=("Les données envoyées peuvent servir à entraîner leurs modèles (CGU §5.2, refus possible pour la suite).",
                "Submitted data may be used to train their models (terms §5.2, opt-out applies to later data)."),
       key_url="https://aristotle.harmonic.fun/keys",
       sources=["https://aristotle.harmonic.fun/docs/faq", "https://aristotle.harmonic.fun/docs/overview",
                "https://www.harmonic.fun/legal/terms/", "https://pypi.org/project/aristotlelib/"]),
    # ------------------------------------------------------------------ writing & LaTeX
    _c("gemini", "writing", "Google Gemini", key="gemini", kind="llm", price="free_tier", integrated="yes",
       good=("Le plus fort des modèles gratuits pour rédiger (LaTeX, explications) et raisonner ; aussi pour le code.",
             "The strongest free models for writing (LaTeX, explanations) and reasoning; also for code."),
       tier=("Gratuit (limites par projet, visibles dans AI Studio) : gemini-4-hydrogen, gemini-3.8-flash, Flash-Lite… "
             "Les modèles « Pro » et Gemini 4 Carbon/Argon/Neon sont payants.",
             "Free (per-project limits, shown in AI Studio): gemini-4-hydrogen, gemini-3.8-flash, Flash-Lite… « Pro » "
             "models and Gemini 4 Carbon/Argon/Neon are paid."),
       privacy=("Offre gratuite : Google peut utiliser vos requêtes pour améliorer ses produits (relecture humaine "
                "possible). Ne pas y envoyer de travaux confidentiels. Dans l'UE, les CGU réservent aux offres payantes "
                "les apps proposées à des utilisateurs.",
                "Free tier: Google may use your prompts to improve its products (human review possible). Do not send "
                "confidential work. In the EU, the terms reserve apps offered to users to paid services."),
       key_url="https://aistudio.google.com/apikey",
       sources=["https://aistudio.google.com/docs/pricing", "https://aistudio.google.com/docs/models",
                "https://aistudio.google.com/docs/rate-limits", "https://aistudio.google.com/docs/terms"],
       prefix="^AIza"),
    _c("mistral", "writing", "Mistral AI", key="mistral", kind="llm", price="free_tier", integrated="yes",
       good=("Très bon en français ; Mistral Large/Medium pour rédiger, Codestral/Mistral Small pour le code, Magistral "
             "pour raisonner.",
             "Very good in French; Mistral Large/Medium for writing, Codestral/Mistral Small for code, Magistral for "
             "reasoning."),
       tier=("La page « usage limits » actuelle demande d'activer la facturation pour les clés API ; une clé déjà créée "
             "reste valable (testez-la ici). Mistral Large : 0,5 $ / 1,5 $ par million de jetons.",
             "The current « usage limits » page asks to activate billing for API keys; an existing key keeps working "
             "(test it here). Mistral Large: 0.5 / 1.5 USD per million tokens."),
       privacy=("Hébergé dans l'UE. Désactivez l'entraînement : console → Privacy → « Data usage for improving our "
                "services ».",
                "Hosted in the EU. Turn training off: console → Privacy → « Data usage for improving our services »."),
       key_url="https://console.mistral.ai/api-keys",
       sources=["https://docs.mistral.ai/admin/billing-usage/usage-limits", "https://mistral.ai/pricing",
                "https://help.mistral.ai/en/articles/455207-can-i-opt-out-of-my-input-or-output-data-being-used-for-training"]),
    _c("anthropic", "writing", "Anthropic (Claude)", key="anthropic", kind="llm", price="paid", integrated="yes",
       good=("Renfort payant : le meilleur en Lean et en rédaction, appelé seulement si les gratuits échouent, dans vos "
             "plafonds.",
             "Paid reinforcement: the best at Lean and writing, called only when the free models fail, within your caps."),
       tier=("Payant (Haiku 5.5 : 0,10 $ / 0,50 $ ; Opus 5.5 : 4 $ / 20 $ par million de jetons). Plafonds par preuve et "
             "par mois dans Réglages → Modèles.",
             "Paid (Haiku 5.5: 0.10 / 0.50 USD; Opus 5.5: 4 / 20 USD per million tokens). Caps per proof and per month "
             "in Settings → Models."),
       privacy=("API : pas d'entraînement sur vos données par défaut.", "API: no training on your data by default."),
       key_url="https://console.anthropic.com/settings/keys", prefix="^sk-ant-"),
    # ------------------------------------------------------------------ code
    _c("groq", "code", "Groq", key="groq", kind="llm", price="free_tier", integrated="yes",
       good=("Très rapide : gpt-oss-120b et Qwen 3.8 pour le code Sage/Python, les petites tâches et le routage.",
             "Very fast: gpt-oss-120b and Qwen 3.8 for Sage/Python code, small tasks and routing."),
       tier=("Gratuit sans carte (limites affichées dans la console ; offre Developer : 30 req/min, 1 000 req/jour par "
             "modèle).",
             "Free without a card (limits shown in the console; Developer plan: 30 req/min, 1,000 req/day per model)."),
       privacy=("Pas de conservation par défaut (journaux jusqu'à 30 jours pour la fiabilité ; « Zero Data Retention » "
                "activable).",
                "No retention by default (logs up to 30 days for reliability; « Zero Data Retention » available)."),
       key_url="https://console.groq.com/keys",
       sources=["https://console.groq.com/docs/rate-limits", "https://console.groq.com/docs/models",
                "https://console.groq.com/docs/your-data"], prefix="^gsk_"),
    _c("cerebras", "code", "Cerebras", key="cerebras", kind="llm", price="free_tier", integrated="yes",
       good=("gpt-oss-120b et Qwen 3.8 très rapides : code, calcul, raisonnement.",
             "Very fast gpt-oss-120b and Qwen 3.8: code, computation, reasoning."),
       tier=("Essai : 5 $ offerts une fois après ajout d'une carte, valables 30 jours ; ensuite crédits payants. "
             "gpt-oss-120b : 5 req/min, 1 M jetons/jour.",
             "Trial: a one-time 5 USD credit after adding a card, valid 30 days; then paid credits. gpt-oss-120b: "
             "5 req/min, 1M tokens/day."),
       privacy=("Les CGU n'autorisent pas Cerebras à entraîner sur vos contenus.",
                "The terms do not let Cerebras train on your content."),
       key_url="https://cloud.cerebras.ai",
       sources=["https://inference-docs.cerebras.ai/support/rate-limits", "https://www.cerebras.ai/pricing",
                "https://www.cerebras.ai/terms-of-service"], prefix="^csk-"),
    _c("sambanova", "code", "SambaNova Cloud", key="sambanova", kind="llm", price="free_tier", integrated="yes",
       good=("gpt-oss-120b gratuit en secours (code, maths).", "Free gpt-oss-120b as a backup (code, maths)."),
       tier=("Gratuit sans carte : 20 req/min, 20 req/jour, 200 000 jetons/jour par modèle (gpt-oss-120b, Gemma 4 31B).",
             "Free without a card: 20 req/min, 20 req/day, 200,000 tokens/day per model (gpt-oss-120b, Gemma 4 31B)."),
       privacy=("Politique d'entraînement non précisée sur les pages consultées.",
                "Training policy not stated on the pages checked."),
       key_url="https://cloud.sambanova.ai/apis",
       sources=["https://docs.sambanova.ai/docs/en/models/rate-limits",
                "https://docs.sambanova.ai/docs/en/get-started/api-keys-urls.md"]),
    # ------------------------------------------------------------------ web search
    _c("tavily", "web", "Tavily", key="tavily", kind="search", price="free_tier", integrated="yes",
       good=("Recherche Internet pensée pour les assistants : résultats courts et cités pour l'orchestrateur de "
             "recherche et les réponses sourcées.",
             "Internet search built for assistants: short, cited results for the research orchestrator and grounded "
             "answers."),
       tier=("Gratuit : 1 000 crédits par mois sans carte (1 recherche simple = 1 crédit).",
             "Free: 1,000 credits per month without a card (1 basic search = 1 credit)."),
       privacy=("Seule la requête est envoyée. Tavily peut utiliser une partie des requêtes pour améliorer ses réponses.",
                "Only the query is sent. Tavily may use parts of the queries to improve its answers."),
       key_url="https://app.tavily.com",
       sources=["https://docs.tavily.com/documentation/api-credits",
                "https://docs.tavily.com/documentation/api-reference/endpoint/search", "https://www.tavily.com/privacy"],
       prefix="^tvly-"),
    _c("exa", "web", "Exa", key="exa", kind="search", price="free_tier", integrated="yes",
       good=("Recherche « sémantique » : trouve des articles et pages proches d'une idée.",
             "« Semantic » search: finds articles and pages close to an idea."),
       tier=("10 $ de crédits offerts chaque mois (≈ 2 500 recherches « lite » à 4 $ / 1 000).",
             "10 USD of free credits every month (≈ 2,500 « lite » searches at 4 USD / 1,000)."),
       privacy=("Seule la requête est envoyée. Politique de conservation non vérifiée.",
                "Only the query is sent. Retention policy not verified."),
       key_url="https://dashboard.exa.ai/api-keys", sources=["https://exa.ai/pricing", "https://docs.exa.ai/reference/search"]),
    _c("brave", "web", "Brave Search", key="brave", kind="search", price="credits", integrated="yes",
       good=("Index web indépendant, large.", "Large independent web index."),
       tier=("5 $ de crédits offerts par mois (≈ 1 000 requêtes à 5 $ / 1 000) ; carte bancaire exigée.",
             "5 USD of free credits per month (≈ 1,000 requests at 5 USD / 1,000); a card is required."),
       privacy=("Seule la requête est envoyée. CGU : pas de stockage des résultats ni d'entraînement de modèles — "
                "Madalean les affiche et les cite seulement.",
                "Only the query is sent. Terms: no storing of results nor model training — Madalean only shows and "
                "cites them."),
       key_url="https://api-dashboard.search.brave.com",
       sources=["https://brave.com/search/api/", "https://api-dashboard.search.brave.com/terms-of-service"]),
    _c("wikipedia", "web", "Wikipedia (sans clé)", key=None, kind="keyless", price="free", integrated="yes",
       good=("Secours toujours disponible : articles encyclopédiques (définitions, théorèmes, historique).",
             "Always-available fallback: encyclopedia articles (definitions, theorems, history)."),
       tier=("Gratuit, sans clé, autorisé (une requête à la fois, agent utilisateur descriptif).",
             "Free, no key, permitted (one request at a time, descriptive user agent)."),
       privacy=("Seule la requête est envoyée à wikipedia.org.", "Only the query is sent to wikipedia.org."),
       sources=["https://www.mediawiki.org/wiki/API:Etiquette", "https://www.mediawiki.org/wiki/Wikimedia_APIs/Rate_limits"]),
    # ------------------------------------------------------------------ scholarly search (already integrated, keyless)
    _c("scholarly", "science", "arXiv, zbMATH, Crossref, OpenAlex, Semantic Scholar", key=None, kind="keyless",
       price="free", integrated="yes",
       good=("Bibliographie, recherche d'articles, texte intégral libre (Sources, Recherche documentaire).",
             "Bibliography, paper search, open-access full text (Sources, literature search)."),
       tier=("Gratuit, sans clé (débit poli : 3 s entre deux appels arXiv).",
             "Free, no key (polite rate: 3 s between arXiv calls)."),
       privacy=("Seules les requêtes de recherche sont envoyées.", "Only the search queries are sent.")),
    _c("leansearch", "science", "LeanSearch, Loogle", key=None, kind="keyless", price="free", integrated="yes",
       good=("Trouver un lemme Mathlib par une phrase (LeanSearch) ou par un motif Lean (Loogle) — outil du prouveur.",
             "Find a Mathlib lemma from a sentence (LeanSearch) or a Lean pattern (Loogle) — a prover tool."),
       tier=("Gratuit, sans clé.", "Free, no key."),
       privacy=("Seule la requête courte est envoyée (jamais l'énoncé complet).",
                "Only the short query is sent (never the whole statement).")),
    # ------------------------------------------------------------------ free general models
    _c("keyless", "general", "LLM7, OVHcloud, Kilo, Pollinations (sans clé)", key=None, kind="keyless", price="free",
       integrated="yes",
       good=("Modèles gratuits sans clé : Madalean marche dès l'installation.",
             "Free models without a key: Madalean works right after install."),
       tier=("Gratuit, limites variables (pauses automatiques en cas de saturation).",
             "Free, variable limits (automatic pauses when saturated)."),
       privacy=("Requêtes envoyées à ces services : à éviter pour un travail confidentiel (mode local).",
                "Prompts go to these services: avoid for confidential work (use local mode).")),
    _c("openrouter", "general", "OpenRouter", key="openrouter", kind="llm", price="free_tier", integrated="yes",
       good=("Un accès à des modèles « :free » (Nemotron 3 Ultra, Gemma 4…).",
             "Access to « :free » models (Nemotron 3 Ultra, Gemma 4…)."),
       tier=("Modèles « :free » : 20 req/min et 50 req/jour (1 000/jour après 10 $ de crédits achetés une fois).",
             "« :free » models: 20 req/min and 50 req/day (1,000/day after buying 10 USD of credits once)."),
       privacy=("Certains modèles gratuits ne sont servis que si vous acceptez qu'ils entraînent sur vos données "
                "(réglage « privacy » d'OpenRouter).",
                "Some free models are only served if you allow training on your data (OpenRouter's privacy setting)."),
       key_url="https://openrouter.ai/settings/keys",
       sources=["https://openrouter.ai/docs/api/reference/limits",
                "https://openrouter.ai/docs/guides/privacy/provider-logging"], prefix="^sk-or-"),
    _c("nvidia", "general", "NVIDIA NIM (build.nvidia.com)", key="nvidia", kind="llm", price="free_tier",
       integrated="yes",
       good=("Catalogue d'essai gratuit (Nemotron, DeepSeek, Qwen…), en secours.",
             "Free trial catalogue (Nemotron, DeepSeek, Qwen…), as a backup."),
       tier=("Essai gratuit à débit limité (limites par modèle non publiées). Réservé aux tests et à l'évaluation.",
             "Free rate-limited trial (per-model limits not published). For testing and evaluation only."),
       privacy=("Les CGU d'essai permettraient à NVIDIA d'utiliser requêtes et réponses (texte non consultable "
                "directement) : pas de travail confidentiel.",
                "The trial terms reportedly let NVIDIA use prompts and outputs (text not directly readable): no "
                "confidential work."),
       key_url="https://build.nvidia.com", sources=["https://docs.api.nvidia.com/nim/reference/llm-apis",
                                                    "https://docs.api.nvidia.com/nim/docs/api-quickstart"],
       prefix="^nvapi-"),
    _c("cloudflare", "general", "Cloudflare Workers AI", key=None, kind="info", price="free_tier", integrated="no",
       good=("gpt-oss-120b, Qwen Coder… ; n'entraîne pas sur vos données.",
             "gpt-oss-120b, Qwen Coder…; does not train on your data."),
       tier=("10 000 « neurones » par jour gratuits (≈ 300 000 jetons d'entrée de gpt-oss-120b). Non intégré : l'adresse "
             "exige votre identifiant de compte et un jeton à droits spécifiques.",
             "10,000 « neurons » per day free (≈ 300,000 input tokens of gpt-oss-120b). Not integrated: the URL needs "
             "your account id and a token with specific rights."),
       privacy=("« Cloudflare does not use Customer Content … to train AI models ».",
                "« Cloudflare does not use Customer Content … to train AI models »."),
       sources=["https://developers.cloudflare.com/workers-ai/platform/pricing/",
                "https://developers.cloudflare.com/workers-ai/platform/data-usage/"]),
    _c("github-models", "general", "GitHub Models", key=None, kind="info", price="free", integrated="retired",
       good=("Ancien accès gratuit avec un jeton GitHub.", "Former free access with a GitHub token."),
       tier=("Fermé définitivement le 30/07/2026 : votre jeton GitHub reste réservé à la publication.",
             "Permanently retired on 2026-07-30: your GitHub token stays for publishing only."),
       privacy=("—", "—"),
       sources=["https://github.blog/changelog/2026-07-30-github-models-is-now-retired/"]),
    _c("openai", "general", "OpenAI", key="openai", kind="llm", price="paid", integrated="yes",
       good=("GPT-5 : payant, seulement si vous le choisissez.", "GPT-5: paid, only when you choose it."),
       tier=("Payant.", "Paid."), privacy=("API : pas d'entraînement par défaut.", "API: no training by default."),
       key_url="https://platform.openai.com/api-keys", prefix="^sk-"),
    _c("deepseek", "general", "DeepSeek", key="deepseek", kind="llm", price="paid", integrated="yes",
       good=("Bon en maths et code, peu cher ; seulement si vous le choisissez.",
             "Good at maths and code, cheap; only when you choose it."),
       tier=("Payant.", "Paid."), privacy=("Serveurs en Chine.", "Servers in China."),
       key_url="https://platform.deepseek.com/api_keys", prefix="^sk-"),
]

CARDS.append(_c(
    "github", "publish", "GitHub (publication)", key="github", kind="token", price="free", integrated="yes",
    good=("Seulement pour « Publier » : envoyer le site sur votre dépôt GitHub. Jamais utilisé pour des modèles.",
          "Only for « Publish »: push the site to your GitHub repository. Never used for models."),
    tier=("Gratuit.", "Free."),
    privacy=("Le jeton ne part que vers api.github.com et github.com.", "The token only goes to api.github.com and github.com."),
    key_url="https://github.com/settings/tokens/new?scopes=repo,workflow&description=Madalean",
    prefix="^(ghp_|github_pat_|gho_)"))



def cards() -> list[dict]:
    return [dict(c) for c in CARDS]


def key_providers() -> list[str]:
    """Every provider id a key can be stored for from the hub (model providers and search providers)."""
    return sorted({c["key"] for c in CARDS if c["key"]})
