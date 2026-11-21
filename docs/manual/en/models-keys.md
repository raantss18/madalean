---
id: models-keys
title: Models and keys
order: 300
section: settings
audience: all
summary: The Local / Automatic / Online modes, what is sent and to whom, how to get an Anthropic or Gemini key, and what it costs.
---

# Models and keys

Madalean works **without any key**: local models installed on the host and free online providers that need no
account. A key adds a provider's models, often stronger ones.

## The three modes

| Mode | Who works | Network |
|---|---|---|
| *Local* | only the host computer's models (Goedel-Prover, Goedel-Formalizer, Qwen3, and Ollama if it is running) | nothing leaves the host; any non-local connection is refused before it is opened |
| *Automatic* (default) | the online models (with a Hugging Face token, Goedel-Prover 32B opens every proof) | the local models **only** without Internet, or when no online model can work (all down, paused or refused); otherwise the local model is not loaded and the graphics card stays free |
| *Online* | online models only | without network, the work fails with a clear message |

A project can be switched to “local only” whatever the general mode. The indicator at the top of the screen
(“Who receives what”) tells at every moment which model receives your work. Every text produced by a model shows
its name.

## What is sent, and to whom

| Stage | What the model receives |
|---|---|
| Understanding | your statement in plain language |
| Translation into Lean | your statement and its reformulation |
| Proof | the Lean statement, Lean's error messages, Mathlib lemmas retrieved for the statement |
| Explanation, written proof | the statement and the Lean proof |
| Questions about sources | your question and the selected passages of your sources |
| Notebook assistant | the open notebook (cells and outputs) |

What is **never** sent to a model: your API keys, your device tokens, your other dossiers, your files. A key is sent
only to **its** provider: Madalean refuses to attach a key to an address that is not that provider's.

Free providers without an account (LLM7, OVHcloud, Kilo, Pollinations…) apply their own terms; assume that what you
send them may be retained. For confidential work, use *Local* mode.
<!-- verify after integration: list of keyless providers in the shipped catalogue -->

## Adding a key

“Settings › Keys”: paste the key, Madalean **tests it at once** (“It works: N models available”, or the reason
for the refusal). The key is kept in the host computer's keyring (otherwise in a file readable only by you) and is
never shown again. “Remove the key” deletes it in one click.

![Settings › Keys](../img/settings-keys.png)

### Anthropic key (Claude)

1. Open Anthropic's console: <https://platform.claude.com/> and create an account.
2. Add a payment method and buy credits (prepaid, pay-as-you-go billing).
3. “API keys › Create key”, copy the key (it starts with `sk-ant-`). It is shown only once.
4. Paste it in “Settings › Keys › Anthropic”.

Advice: set a monthly **spend limit** in the console.
<!-- verify after integration: console URL and menu names at release time -->

### Google Gemini key

1. Open Google AI Studio: <https://aistudio.google.com/apikey> with a Google account.
2. “Create API key”, copy the key.
3. Paste it in “Settings › Keys › Gemini”.

Gemini's free tier has quotas; when they are reached, Madalean moves on to the next model. On the free tier, Google
may use the content sent to improve its products: read its terms before sending unpublished work.
<!-- verify after integration: Gemini free-tier data-use terms at release time -->

### Hugging Face token (Goedel-Prover 32B online)

With a Hugging Face token, **Goedel-Prover-V2-32B** (served by a Hugging Face provider, today Featherless AI) opens
every proof: the same loop as the local Goedel — same prompts, ≤ 2 corrections per line of attack, same sampling —,
with the 32B model instead of the 8B, without using the graphics card. If it fails, the free models take over (the
tournament). Goedel-Formalizer is used the same way as soon as a provider serves it online (none today).

1. Create an account on <https://huggingface.co>. Free accounts must **buy credits**; a PRO account gets $2 of credits
   a month. Hugging Face bills the provider's price, with no markup.
2. “Settings › Keys › Hugging Face › Get a key” opens <https://huggingface.co/settings/tokens> with the “Make calls to
   Inference Providers” permission preselected; create the token (it starts with `hf_`).
3. Paste it: Madalean checks the token (nothing billed) and says whether Goedel 32B is available online.

The token is only sent to `router.huggingface.co` (inference) and `huggingface.co` (the token check). The list of
Goedel models served online is read from Hugging Face's public API, **without** the token. Without Internet, or when
no online model can work, the local models take over; a proof the online models searched without success is **not**
re-run on the local model. It can be turned off in “Settings › Models › Advanced”.

## What it costs

Paid providers bill by the number of *tokens* (≈ ¾ of a word) sent and received. Orders of magnitude, Anthropic's
public prices in November 2026, per million tokens (input / output):

| Model | Input | Output |
|---|---|---|
| Claude Opus 5.5 | $4 | $20 |
| Claude Sonnet 5.5 | $2 | $10 |
| Claude Haiku 5.5 | $0.10 | $0.50 |

A proof search in agent mode with Claude Opus typically costs from a few cents to 50 cents; a hard statement, with
many attempts, more. The limits (number of steps, duration, tokens) are set in “Settings › Models”. By default, a
paid model is used only if you chose it for a role, or if you enabled “paid first”.
<!-- verify after integration: prices and the per-proof estimate (BRAIN.md: ≈ $0.05–0.50) with a real key -->

**Goedel-Prover 32B online (Hugging Face).** The provider publishes no per-token price for this model: Madalean
uses a **conservative estimate** of $1.00 (input) / $3.20 (output) per million tokens, replaced by the published
price as soon as Hugging Face gives one. One Goedel attempt (up to 32,768 output tokens) costs at most ≈ $0.11; the 4
attempts of a proof's first round at most ≈ $0.45. The real cost is on <https://huggingface.co/settings/billing>.

## Claude as paid reinforcement, with caps

With an Anthropic key, Claude can join a proof's tournament **last**, only when all the free models failed
(“Settings › Models › Claude as paid reinforcement”, on by default when the key exists). Two caps, editable there:

- **per proof** ($1.00 by default);
- **per calendar month** ($20 by default), for every paid call — Claude, including a role where you chose it, and
  Goedel online on Hugging Face (same caps, same ledger).

Before each call, Madalean estimates the cost at list prices (request size and allowed answer length) and shortens
the allowed answer if needed; if even a short answer would pass a cap, the call **is not made** and the proof says so.
After the call, the real cost is computed from the usage Anthropic returns (input, output, cache read and cache write
tokens) and written to a small private ledger on the host. The month's total is shown under the caps.
<!-- verify after integration: a real Claude reinforcement round within the 1 $ cap, and the ledger total against the Anthropic console -->

## Choosing a model per role

“Settings › Models” shows, for each role (understand, translate, prove, explain, assistant), the ranking of the
available models and the reason for the ranking. “Automatic” lets the router choose; you can impose a model. A
model in error (quota, refused key, overload) is paused and the next one takes over.
