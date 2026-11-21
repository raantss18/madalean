# Madalean thin clients (shells) — desktop AppImage and Android APK

Owner: session S-C. Sources in `shells/`, build/setup scripts in `scripts/`.

## Required server endpoints (contract for S-A, and for S-D where noted)

The shells never put the long-lived device token in a URL. They talk to the server natively (Rust / Dart HTTP
client, `Authorization: Bearer`), then hand the web view a **one-time ticket** that the server swaps for an
`HttpOnly` cookie. Everything below is on the API prefix `/api`; "remote" = listener `127.0.0.1:11501` published as
`https://<host>.<tailnet>.ts.net:10500`, "local" = trusted listener `127.0.0.1:11500`.

1. **`GET /api/hello`** (no auth, both listeners) → `200 {name:"madalean", version, paired, local, host_name}`,
   `Cache-Control: no-store`.
   - `local`: true on the local listener.
   - `paired`: true on the local listener; on the remote listener true **iff the request carries a valid device
     credential** (`Authorization: Bearer <token>` or the session cookie). The shells call it with their Bearer
     token at start-up and on resume: `paired:false` with a stored token means "revoked" → back to pairing.
2. **`POST /api/pair`** `{code:"123456", device_name}` (no auth) →
   - `200 {token, device_id}` — token = 256-bit random, URL-safe base64; only its SHA-256 is stored server-side.
   - `401 {error:"bad_code"}` (wrong or expired code), `429 {error:"locked", retry_after:<seconds>}` with a
     `Retry-After` header (5 wrong tries → 10 min), `400 {error:"bad_request"}`.
   - The code is single use. `Cache-Control: no-store`.
3. **`POST /api/session/ticket`** with `Authorization: Bearer <token>` (no cookie, no body) →
   `200 {ticket, expires_in:60}` or `401 {error:"unauthorized"}`. Ticket = ≥128-bit random, **single use**, valid
   60 s, bound to the device. Bearer-only, so it cannot be triggered cross-site (no CSRF surface).
4. **`GET /api/session?ticket=<t>&next=<path>`** (no other auth) →
   - valid ticket: consume it, `303 See Other` to `next` (only a relative path starting with `/` and not `//` or
     containing `\`; otherwise `/`), with
     `Set-Cookie: madalean_session=<new random 256-bit session secret bound to the device>; HttpOnly; Secure;
     SameSite=Strict; Path=/; Max-Age=31536000`, `Cache-Control: no-store`, `Referrer-Policy: no-referrer`.
     The cookie is **not** the device token: revoking the device revokes all its sessions.
   - invalid / expired / reused ticket: `303` to `/pair?reason=ticket` (same headers, no cookie).
   - The server must **not log the query string** of this route (access log off or `ticket=` redacted).
   - The ticket travels over TLS (tailnet HTTPS) or loopback only; after the redirect it is dead, so its presence
     in the web view's back/forward list or in a log is harmless.
5. **Unauthenticated requests on the remote listener**: `/api/*` → `401 {error:"unauthorized"}`; WebSocket
   upgrade → 401 (or close code `4401`); **HTML navigations (GET with `Accept: text/html`) → `303 /pair?reason=auth`**.
   `/pair` is the browser pairing page (for plain browsers). The shells intercept any top-level navigation to
   `<server>/pair…`, re-check `hello` with their Bearer token and either open a new session (token still valid,
   cookie only expired) or show their own pairing screen (token revoked).
6. **S-D (web UI)**: when an API call returns 401 or the WebSocket closes with 4401, do
   `location.assign('/pair?reason=auth')` (never show a dead UI). Use `<a download>` / `Content-Disposition:
   attachment` for exports (PDF, .tex, .lean, .zip) — real URLs work best; blob/data URLs also work in the
   desktop shell but **only real HTTP URLs are guaranteed on Android** (the shell re-downloads them with the
   Bearer token). Upload with a plain `<input type="file" accept=".tex,.lean">`. Open external links with
   `target="_blank"` (the shells send any off-origin URL to the system browser).
7. **Optional shell bridge (S-D may use it)**: in the shells, `window.madaleanShell` exists:
   `{kind: "desktop"|"android", version, changeServer(), openExternal(url)}`. When present, the web UI may show a
   "Changer de serveur / Change server" item in its settings that calls `madaleanShell.changeServer()`.
8. **Optional `POST /api/devices/self/forget`** (Bearer) → `204`: revokes the calling device (used by "Forget this
   server" in the shells; if missing they just delete the token locally).
9. **Pair link** shown by the host UI (as text + QR code): `madalean://pair?host=<host>[:<port>]&code=<6 digits>`,
   e.g. `madalean://pair?host=antsa-nitroanv1541.tail804764.ts.net:10500&code=123456`. Scheme is always `https`
   (port 10500 when omitted), except loopback hosts (`127.0.0.1`, `localhost`) which use `http`. Scanning the QR
   with the phone's camera opens the Android app directly (deep link), so the app needs no camera permission.

`shells/dev/mock_server.py` implements exactly this contract (plus test helpers) and is the reference for S-A.
