# Online providers — what Madalean uses, what is free, where data goes (session S-U)

Every fact below was read on the provider's **own** page on **2026-11-22** (URLs given). Free tiers change often: the
app shows « vérifié le 22 novembre 2026 » on each card (Réglages → Fournisseurs); re-check before each release and
update `madalean/brain/hub.py` (cards) and this file together.

## 1. Summary

| Provider | Use in Madalean | Free tier (verified 2026-11-22) | Key | Integrated |
|---|---|---|---|---|
| **Leanstral** (Mistral) | Lean 4 proof agent: tournament round 0 when listed by the Mistral key | Announced as a free API endpoint `leanstral-1-5` (July 2026) — but Mistral's model card lists `labs-leanstral-1-5` **deprecated 2026-09-29, retired 2026-09-30**, no successor | Mistral | auto (detected when `/v1/models` lists any `*leanstral*`) |
| Goedel-Prover-V2-32B (Hugging Face → featherless-ai) | Lean prover, round 0 (S-T) | Pay per token; free HF accounts: no credit; PRO: 2 USD/month | HF token | yes (S-T) |
| Featherless AI (direct) | hosts open Lean provers | none; API plan from 50 USD/month | — | no (HF route instead) |
| Harmonic Aristotle | — | prepaid credits, prices unpublished; **API verifies only Rust / C / Verilog today** | — | no |
| Google Gemini | writing / LaTeX, reasoning, code | free models (per-project limits in AI Studio); data used to improve products | Gemini | yes |
| Mistral | French writing, Codestral / Small for code | API keys now require billing activation; existing keys keep working | Mistral | yes |
| Groq | fast code (Sage/Python), routing | free without card (Developer plan: 30 RPM, 1 000 RPD per model) | Groq | yes |
| Cerebras | fast code / reasoning | 5 USD one-time credit after adding a card, 30 days | Cerebras | yes |
| SambaNova | backup gpt-oss-120b | free: 20 RPM, 20 RPD, 200 k tokens/day per model | SambaNova | **yes (new)** |
| NVIDIA NIM | backup free catalogue | rate-limited trial, testing/evaluation only | NVIDIA | **yes (new)** |
| OpenRouter | `:free` models | 20 RPM, 50 RPD (1 000 RPD after 10 USD bought once) | OpenRouter | yes |
| Cloudflare Workers AI | — | 10 000 neurons/day | — | no (URL needs the account id) |
| GitHub Models | — | **retired 2026-07-30** | — | retired |
| **Tavily** | Internet search (research) | 1 000 credits/month, no card (basic = 1 credit) | Tavily | **yes (new)** |
| **Exa** | semantic Internet search | 10 USD credits/month (lite = 4 USD / 1 000) | Exa | **yes (new)** |
| **Brave Search** | Internet search | 5 USD credits/month (5 USD / 1 000 req), card required | Brave | **yes (new)** |
| **Wikipedia** | keyless search fallback | free, permitted (etiquette: one request at a time, descriptive UA) | none | **yes (new)** |
| arXiv, zbMATH, Crossref, OpenAlex, Semantic Scholar, LeanSearch, Loogle | scholarly search, Mathlib search | free, no key | none | yes (earlier sessions) |
| Mathpix | formula OCR | none (19.99 USD setup, 0.002 USD/image) | — | no (documented) |
| pix2text | formula OCR, local | MIT, ONNX, offline | none | no (proposed new local model) |

**Recommended minimal setup** (shown at the top of the hub): **Groq** (fast free models, no card, no retention by
default) + **Google Gemini** (strongest free models; free tier trains on prompts — nothing confidential) + **Tavily**
(1 000 free searches/month). The user already has Mistral, GitHub and possibly Hugging Face keys.

## 2. Lean specialists

### Leanstral (Mistral) — checked 2026-11-22
- Release post (2026-07-02): « available now as a free API endpoint as `leanstral-1-5` », Apache-2.0, 119B total /
  6B active; PutnamBench 587/672 (pass@8, 4M tokens), FATE-H 87, FATE-X 34. https://mistral.ai/news/leanstral-1-5/
- Model card: API id **`labs-leanstral-1-5`**, 256k context, 128k max output, Function Calling on
  `/v1/chat/completions`; header « This model is deprecated and is being phased out », deprecation 2026-09-29.
  https://docs.mistral.ai/models/model-cards/leanstral-1-5
- Models overview: `labs-leanstral-1-5` deprecated 2026-09-29, **retired 2026-09-30, successor: none listed**;
  `labs-leanstral-2603` retired 2026-06-30. https://docs.mistral.ai/getting-started/models/models_overview/
- Weights card: tools via OpenAI-compatible chat completions (vLLM `--tool-call-parser mistral`), example tool
  `lean_run_code {code | file_path}`, lean-lsp-mcp recommended, temperature 1.0, reasoning effort `high`, ≤ 200k
  tokens; no Lean/Mathlib version stated. https://huggingface.co/mistralai/Leanstral-1.5-119B-A6B
- No other host: OpenRouter `/api/v1/models` has no `leanstral`; the HF model has an empty
  `inferenceProviderMapping` (both queried 2026-11-22).

**What Madalean does.** Any Mistral model whose id contains `leanstral` gets the « Leanstral » family quality
(lean ≈ 1.0 with the prover bonus, low chat/code so it never writes prose or Sage), hence leads `brain.pool("prove")`
— round 0 of the tournament, ahead of the free general models; paid Claude stays the final reinforcement. When a
contestant is pinned to a Leanstral key, the prover agent also exposes `lean_run_code {code}` (→ our `lean_check`
with the statement re-assembled) and, online, `lean_leansearch` / `lean_loogle` (→ LeanSearch / Loogle). Every proof
still goes through the server's strict verdict + D28 gate + sandbox (`runner._agent` re-checks the final code). The
workspace is the one of the statement (lean-current preferred when it compiles there; nothing Leanstral-specific).

**Verify with the user's key (integrator, not done here — no call through the live server):**
1. `curl -s https://api.mistral.ai/v1/models -H "Authorization: Bearer $MISTRAL_API_KEY" | python3 -c "import sys,json;print([m['id'] for m in json.load(sys.stdin)['data'] if 'lean' in m['id']])"`
2. If an id is listed: Réglages → Fournisseurs → Mistral → « Retirer » / re-paste is not needed; press « Actualiser »
   in Réglages → Modèles, then « Pourquoi ce modèle ? » for `prove` must show it first.
3. One tiny tool call: `curl https://api.mistral.ai/v1/chat/completions -H "Authorization: Bearer $MISTRAL_API_KEY" -H 'Content-Type: application/json' -d '{"model":"<id>","messages":[{"role":"user","content":"Prove 2+2=4 in Lean 4 with lean_run_code."}],"tools":[{"type":"function","function":{"name":"lean_run_code","parameters":{"type":"object","properties":{"code":{"type":"string"}}}}}]}'` — expect a `tool_calls` entry.
4. If nothing is listed (expected after the 2026-09-30 retirement), the card says so; nothing else to do.

### Harmonic Aristotle — checked 2026-11-22: not integrated
- SDK `aristotlelib` 3.4.0 (2026-11-18) source: base `https://aristotle.harmonic.fun/api/v3`, header `X-API-Key`,
  `POST /project` (multipart `body` JSON + tar `input`), `GET /task/{id}`, `POST /task/{id}/cancel`,
  `GET /project/{id}/result` (tar.gz); statuses QUEUED … COMPLETE / OUT_OF_BUDGET / FAILED / CANCELED.
  https://pypi.org/project/aristotlelib/ — the REST API itself is undocumented (https://aristotle.harmonic.fun/docs/api).
- **It no longer verifies Lean**: README and https://aristotle.harmonic.fun/docs/overview — « Projects with only Lean
  files aren't supported »; FAQ: « Lean support will return in the coming months »
  (https://aristotle.harmonic.fun/docs/faq). A Lean job would spend credits and verify nothing.
- Prices and free credits unpublished; terms §5.2: customer data may train Harmonic models (opt-out for later data)
  (https://www.harmonic.fun/legal/terms/, modified 2026-10-26).
- Decision: shown in the hub as « non intégré » with the reason. When Lean returns, the client is small (create
  project with the `.lean` file, poll `/task/{id}` with a deadline, cancel on job cancel, download the result, re-check
  with our strict verdict in lean-current only, skip lean-prover49 statements that do not compile in lean-current).

### Other online Lean provers — checked 2026-11-22
Only **Featherless AI** serves them (Goedel-Prover-V2 8B/32B, Goedel-Formalizer-V2, Kimina-Prover distills,
BFS-Prover-V2, StepFun-Prover), paid (from 50 USD/month; https://featherless.ai/pricing), reachable through Hugging
Face (S-T's integration). DeepSeek-Prover-V2-671B: OpenRouter endpoints list empty, DeepInfra deprecated
2026-09-29, Fireworks dedicated-only. Nothing on NVIDIA NIM (`integrate.api.nvidia.com/v1/models`), SambaNova,
Chutes, Novita, OpenRouter.

## 3. General model providers (keys) — checked 2026-11-22

| Provider | Base URL (OpenAI-compatible) | Key page | Facts (source) |
|---|---|---|---|
| Gemini | `https://generativelanguage.googleapis.com/v1beta/openai` | https://aistudio.google.com/apikey | free: gemini-4-hydrogen, 3.8/3.6-flash, flash-lite…; paid: Gemini 4 Carbon/Argon/Neon, 3.1 Pro; 2.5 Pro/Flash rerouted 2026-12-01 (https://aistudio.google.com/docs/pricing, /docs/models); limits per project, 429 RESOURCE_EXHAUSTED (/docs/rate-limits); free tier used to improve products, EEA apps for users only on paid services (/docs/terms) |
| Mistral | `https://api.mistral.ai/v1` | https://console.mistral.ai/api-keys | billing required for API keys (https://docs.mistral.ai/admin/billing-usage/usage-limits); training opt-out in Privacy (help article 455207) |
| Groq | `https://api.groq.com/openai/v1` | https://console.groq.com/keys | gpt-oss-120b/20b, qwen3.8-27b: 30 RPM / 1K RPD (Developer); headers `retry-after`, `x-ratelimit-reset-*` (https://console.groq.com/docs/rate-limits); no retention by default (/docs/your-data) |
| Cerebras | `https://api.cerebras.ai/v1` | https://cloud.cerebras.ai | gpt-oss-120b 5 RPM, 1M TPD; qwen-3.8-27b 300 RPM (https://inference-docs.cerebras.ai/support/rate-limits); 5 USD trial after card (https://www.cerebras.ai/pricing) |
| SambaNova | `https://api.sambanova.ai/v1` | https://cloud.sambanova.ai/apis | free 20 RPM / 20 RPD / 200k TPD (https://docs.sambanova.ai/docs/en/models/rate-limits); headers `x-ratelimit-*-requests(-day)` |
| NVIDIA NIM | `https://integrate.api.nvidia.com/v1` | https://build.nvidia.com | chat completions (https://docs.api.nvidia.com/nim/reference/llm-apis); trial terms: evaluation only |
| OpenRouter | `https://openrouter.ai/api/v1` | https://openrouter.ai/settings/keys | `:free` 20 RPM, 50/1000 RPD (https://openrouter.ai/docs/api/reference/limits); free endpoints may need « allow training » (/docs/guides/privacy/provider-logging) |
| Cloudflare | `https://api.cloudflare.com/client/v4/accounts/{account_id}/ai/v1` | dashboard → Workers AI | 10 000 neurons/day (https://developers.cloudflare.com/workers-ai/platform/pricing/); no training (/platform/data-usage/) — not integrated |
| GitHub Models | — | — | retired 2026-07-30 (https://github.blog/changelog/2026-07-30-github-models-is-now-retired/): the GitHub token stays for publishing only |

Rate limits: every provider goes through the existing failure rules (docs/BRAIN.md §3): 429 → pause for
`Retry-After` / `x-ratelimit-reset*`, daily quota → until midnight UTC, 401/403 → provider paused (`key_refused`),
402 → 12 h. Router order: free online models first (quality × reliability), paid only when chosen / `paid_first` /
Claude reinforcement; the spend ledger covers every paid model with a price (Claude; Hugging Face per S-T).
OpenAI and DeepSeek keys are « paid, only when chosen »: their calls are not priced by the ledger (prices not
verified this session) — they are never picked automatically.

## 4. Internet search — checked 2026-11-22

Module `madalean/brain/websearch.py` (`WebSearch`), server plugin `madalean/server/plugins/providers_hub.py`.

| Provider | Request | Auth | Errors handled | Cost counted |
|---|---|---|---|---|
| Tavily | `POST https://api.tavily.com/search {query, max_results, search_depth:"basic", include_answer:false}` | `Authorization: Bearer tvly-…` | 401 key_refused, 432/433 quota, 429 rate_limit | 1 credit / search (https://docs.tavily.com/documentation/api-credits) |
| Exa | `POST https://api.exa.ai/search {query, numResults, type:"lite", contents:{highlights:true}}` | `x-api-key` | 401, 402 quota, 429 | `costDollars.total` (else 0.004 USD) (https://exa.ai/pricing) |
| Brave | `GET https://api.search.brave.com/res/v1/web/search?q=&count=` | `X-Subscription-Token` | 401/403, 429 | 0.005 USD / request (https://brave.com/search/api/) |
| Wikipedia | `GET https://{en,fr}.wikipedia.org/w/api.php?action=query&list=search&srsearch=&format=json&formatversion=2` | none | — | requests |

Brave terms (https://api-dashboard.search.brave.com/terms-of-service): no storing / database of results (transient
use only), no training of models — Madalean only shows and cites them. Tavily may use query data to improve its
service (https://www.tavily.com/privacy). Keyless alternatives rejected: DuckDuckGo Instant Answers (not web
results), keyless Jina search (blocked), public SearXNG (bots refused), Marginalia `public` key (dev only).

Rules: order = keyed providers with a key and free allowance left → keyed ones past it → Wikipedia; a refused key /
quota / network error moves to the next one; **never in local mode** (`mode == "local"` in the settings or the call →
`SearchError("local_mode")` before any connection, plus `Http.check`); `web_search: false` turns it off; a key only
goes to its provider's host (key-host binding fixed at construction); only the query is sent; only `https://` result
URLs are returned; nothing is fetched from result URLs (use `research.fetch.Fetcher.get(url, policy="public")`, the
SSRF-safe client, to read a page); usage per month in `<config>/websearch-usage.json` (0600, no query, no key).

### Interface for the research orchestrator (S-Q)
```python
ws = ctx.websearch                                   # set by the providers_hub plugin
res = await ws.search("Erdős–Straus conjecture", k=6, mode=job.mode, lang="fr")
# → {"query", "provider": "tavily", "results": [{"n", "title", "url", "snippet", "published", "source"}], "tried": [...]}
# raises websearch.SearchError(kind) — kind: local_mode | disabled | no_provider | http
from madalean.brain.websearch import tool_spec, format_results
tools.append(tool_spec(ws, mode=job.mode, lang="fr"))    # `web_search` tool for brain.run_agent (cites [n] + URL)
```
HTTP: `POST /api/search/web {query, k?, lang?, providers?}` → same JSON; 409 `local_mode` / `disabled`, 503
`no_provider`. `POST /api/search/test {provider}` → `{ok, reason, results, latency_s}`. `GET /api/providers` → hub
cards with `key_set`, `disabled`, `state` (models usable now), `usage` (search providers).

## 5. Task routing (LaTeX writing / Sage code)

Roles are fixed (`api.Role`), so the kind of work is a context hint read by the router (`brain/classify.py`):
```python
from madalean.brain import classify
with classify.task("sage"):        # or "code" / "python" → code models (Codestral, Qwen Coder, gpt-oss…)
    c = await brain.complete("explain", msgs)
with classify.task("latex"):       # → strong writing models (Gemini, Mistral Large, Claude when chosen)
    c = await brain.complete("explain", msgs)
```
`prove` / `formalize` are never overridden. The `assistant` role's classifier now also sends Sage / SageMath / PARI /
NumPy / SymPy requests to code models. To wire (owners of the files): the article editor's Sage cell generation
(`server/plugins/article_editor.py`, `complete_once(ctx, "explain", …)` near « wb.calc.add ») and the Calcul
notebook's code generation (S-P) should wrap their call in `classify.task("sage")`; the article rewriting in
`classify.task("latex")`.

## 6. Formula OCR (image / PDF → LaTeX) — evaluated, nothing installed

- **pix2text** (https://github.com/breezedeus/Pix2Text): MIT code, MFR model `breezedeus/pix2text-mfr-1.5` MIT,
  ONNX, offline (https://huggingface.co/breezedeus/pix2text-mfr-1.5). Best free option; already used by the user's
  Fikajiana. It would be a **new local model** (download + onnxruntime): proposed, not installed.
- **Mathpix** (https://mathpix.com/pricing/api): 19.99 USD setup (29 USD test credit), 0.002 USD/image, 0.005
  USD/PDF page; `improve_mathpix=false` keeps images from being stored (https://docs.mathpix.com/concepts/data-retention).
- LaTeX-OCR/pix2tex (MIT, formulas only), Nougat (weights CC-BY-NC), Surya/Marker (weights under a modified
  OpenRAIL-M: free for research/personal/small companies), Texify (archived), UniMERNet (weights licence unstated).
- A free vision model (Gemini free tier) can read formulas, but the free tier may use the image to improve Google's
  products.

## 7. Risks
- Free tiers move monthly (GitHub Models closed, Mistral free API gone, Leanstral retired in 3 months, Gemini model
  names changed): the hub shows the check date; failures degrade to the next provider, never block.
- Gemini / NVIDIA / OpenRouter free endpoints may train on prompts: the cards say so; local mode avoids every one.
- Brave and Tavily terms on storing results: Madalean does not persist search results (only the answer that cites
  them, as the user's own document).
- Leanstral: implemented and tested against a fake Mistral server only; whether the user's key lists it must be
  checked with the steps in §2.
