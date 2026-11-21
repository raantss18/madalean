# Madalean thin clients (shells) — desktop AppImage and Android APK

Owner: session S-C. Sources in `shells/`, build/setup scripts in `scripts/`.

## Required server endpoints (contract for S-A, and for S-D where noted)

The shells never put the long-lived device token in a URL. They talk to the server natively (Rust / Dart HTTP
client, `Authorization: Bearer`), then hand the web view a **one-time ticket** that the server swaps for the
`HttpOnly` cookie. Everything below is under `/api`; "remote" = listener `127.0.0.1:11501` published as
`https://<host>.<tailnet>.ts.net:10500`, "local" = trusted listener `127.0.0.1:11500`.

**Status against the current server (`madalean/server/`, docs/API.md, 2026-11-21):** items 1, 2 exist (the shells
accept both the shapes below and the current ones: `403 wrong|expired|no_code`, `429 rate_limited|locked`,
`{token, device:{id…}}`); **items 3, 4 are missing and block the shells on remote devices**; item 5/6 differ (see
notes). On the host itself nothing is needed: the local listener is opened directly.

1. **`GET /api/hello`** (no auth, both listeners) → `200 {name:"madalean", version, paired, local, host_name}`,
   `Cache-Control: no-store`. `paired` = true on the local listener; on the remote listener true **iff the request
   carries a valid device credential** (Bearer or cookie). The shells call it with their Bearer token at start-up
   and on resume: `paired:false` with a stored token means "revoked" → back to pairing. *(Implemented.)*
2. **`POST /api/pair`** `{code:"123456", device_name}` (no auth) → `200 {token, …}`; wrong/expired code `401` or
   `403`; locked / rate-limited `429` (`retry_after` seconds in the body or a `Retry-After` header are used when
   present). The code is single use. *(Implemented.)*
3. **`POST /api/session/ticket`** — **to add.** `Authorization: Bearer <token>` (no cookie, no body) →
   `200 {ticket, expires_in:60}` or `401 {error:"unauthorized"}`. Ticket = ≥128-bit random, **single use**, valid
   60 s, bound to the device, kept in memory only. Bearer-only, so a web page cannot trigger it (no CSRF surface).
   Add it to the public-route exceptions only in the sense that it authenticates by Bearer (never by cookie).
4. **`GET /api/session?ticket=<t>&next=<path>`** — **to add.** No other auth (the ticket is the credential).
   - valid ticket: consume it and answer **`200 text/html`** (not a 303, see below) with
     `Set-Cookie: madalean_token=<credential>; HttpOnly; Secure; SameSite=Strict; Path=/; Max-Age=…`,
     `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, a CSP without scripts, and a body that moves on with
     a same-origin meta refresh:
     `<meta http-equiv="refresh" content="0;url=NEXT">` where NEXT = `next` HTML-escaped, accepted only if it is a
     relative path starting with `/`, not `//`, without `\`; otherwise `/`.
     The cookie value may be the device token (as `POST /api/pair` does today) or, better, a fresh session secret
     bound to the device (revoked with it); the shells do not read it.
   - invalid / expired / reused ticket: `303` to `/?reason=ticket` (or `/pair?reason=ticket`, see 5), no cookie.
   - **Why 200 + meta refresh, not 303:** the shell's navigation comes from its own bundled page (`tauri://…`),
     a cross-site initiator. WebKitGTK keeps that initiator through a 303 chain and **withholds the
     `SameSite=Strict` cookie on the redirected request** — observed in the desktop e2e test (the page after the
     303 arrived without cookie, every time). A navigation started by the server's own page is same-site, so the
     Strict cookie is sent. (`SameSite=Lax` would also work with a 303, but §4 of ARCHITECTURE asks for Strict.)
   - Do **not log the query string** of this route (or redact `ticket=`). The ticket only travels over TLS
     (tailnet HTTPS) or loopback and is dead after one use, so its presence in the web view's history is harmless.
5. **Session lost while the UI is open** (cookie expired, device revoked): today unauthenticated static GETs serve
   the SPA, which shows its own pairing screen. For the shells to take over (re-open a session with their token,
   or show their pairing screen with the right message), **S-D: on a 401 from the API, or a WebSocket close with
   4401, when `window.madaleanShell` exists, call `location.assign('/pair?reason=auth')`** (the shells intercept
   any top-level navigation to `<server>/pair…`; the server needs no `/pair` route for them; in a plain browser
   keep the SPA's pairing screen). The shells additionally re-check `hello` when the window regains focus
   (desktop, > 45 s) or the app resumes (Android, > 30 s).
6. **S-D (web UI)**: exports with real URLs + `Content-Disposition: attachment` (PDF, .tex, .lean, .zip) — they work
   in both shells (Android re-downloads same-origin URLs natively with the Bearer token; `blob:`/`data:` URLs are
   best effort there). Uploads with a plain `<input type="file" accept=".tex,.lean">`. External links with
   `target="_blank"` or plain links: any off-origin URL goes to the system browser.
7. **Optional shell bridge (S-D may use it)**: `window.madaleanShell =
   {kind: "desktop"|"android", version, changeServer(), openExternal(url)}`. When present, show a
   « Changer de serveur / Change server » item in settings calling `madaleanShell.changeServer()`. Look it up when
   needed (not only at load: on old Android WebViews it appears after the page's first scripts). Desktop also has
   the shortcut Ctrl+Shift+K. The bridge gives remote pages **no** other capability (no Tauri IPC at all).
8. **Optional `POST /api/devices/self/forget`** (Bearer) → `204`: revokes the calling device ("Forget this server"
   in the shells). The current `POST /api/logout` does the same and would also do: the shells try
   `/api/devices/self/forget` and otherwise just delete their token locally.
9. **Pair link** shown by the host UI (text + QR code): `madalean://pair?host=<host>[:<port>]&code=<6 digits>`,
   e.g. `madalean://pair?host=antsa-nitroanv1541.tail804764.ts.net:10500&code=123456`. Scheme is always `https`
   (port 10500 when omitted), except loopback hosts (`127.0.0.1`, `localhost`) which use `http`. Scanning the QR
   with the phone's camera app opens the Android app directly (deep link), so the app needs no camera permission;
   on desktop the link opens the AppImage when the launcher is installed (`scripts/install_desktop_entry.sh`).

`shells/dev/mock_server.py` implements exactly this contract (plus test helpers: `/mock/events`,
`/mock/revoke_all`, `/mock/new_code` on its local listener) and is the reference for S-A.

## Architecture

```
            host PC                                          any device on the tailnet
 ┌───────────────────────────────┐                     ┌────────────────────────────────┐
 │ madalean serve                │                     │ shell (AppImage / APK)         │
 │  127.0.0.1:11500  local ◄─────┼── host's own shell  │  1. connect screen (bundled)   │
 │  127.0.0.1:11501  remote      │   (no pairing)      │  2. hello / pair / ticket      │
 │        ▲                      │                     │     native HTTP, Bearer token  │
 │ tailscale serve --https=10500 │◄── HTTPS (LE cert) ─┤  3. web view → /api/session    │
 └───────────────────────────────┘    tailnet only     │     → cookie → server web UI   │
                                                       └────────────────────────────────┘
```

Start-up (both shells): (a) desktop only — `GET http://127.0.0.1:11500/api/hello`; if a Madalean answers with
`local:true` the window opens it directly (host mode). (b) Otherwise the last server with a stored token:
`hello` with Bearer → `paired:false` ⇒ token deleted, pairing screen « appareil révoqué » ; unreachable ⇒ clear
message + Retry + the server list / form ; OK ⇒ `POST /api/session/ticket` → web view loads
`/api/session?ticket=…` → cookie → `/`. (c) No server yet ⇒ form: address (full `*.ts.net` name; port 10500 by
default; a pasted `madalean://pair` link fills address + code), 6-digit code, device name ⇒ `hello` (is it a
Madalean?) ⇒ `POST /api/pair` ⇒ token stored ⇒ (b).

Navigation policy in the web view: same origin as the connected server → allowed; `<server>/pair…` → intercepted
(re-authentication, max 3 per minute, else back to the connect screen); `madalean://pair…` → pairing form
prefilled; `madalean://shell/…` → bridge actions (desktop); any other http(s) → system browser; `target=_blank` /
`window.open` → same rule (same origin stays in the window). Remote pages never get native IPC.

## Desktop shell (`shells/desktop`, Tauri 2 → AppImage)

- `src-tauri/src/core.rs` pure logic (addresses, pair links, saved servers, answer mapping) — unit-tested;
  `store.rs` token storage; `net.rs` native HTTP (reqwest + rustls, native roots, 5 s connect / 12 s timeout, no
  redirects); `lib.rs` window, navigation policy, downloads, single instance, deep links; `bridge.js` injected
  into pages (bridge + download toast + Ctrl+Shift+K); `ui/` the connect screen (vanilla HTML/CSS/JS, FR default +
  EN, light/dark, no external resource, CSP `script-src 'self'`).
- Capabilities: the bundled screen (local origin) may call the 7 app commands; remote origins get nothing
  (`capabilities/default.json`, commands declared in `build.rs`).
- Plugins: single-instance (a second launch, e.g. from a `madalean://` link, is forwarded to the running window),
  window-state (size/position/maximised restored), opener (system browser / open downloaded file).
- Downloads: saved to the XDG download folder (fallback `~/Downloads`), unique names, then a toast
  « Téléchargé : x.pdf [Ouvrir] » in the page. Uploads: WebKitGTK's native GTK file chooser.
- Window title « Madalean — <host_name> ». The host's own shell needs no token and never pairs.
- Test hooks (environment only, inert otherwise): `MADALEAN_LOCAL_URL` (local probe target),
  `MADALEAN_TOKEN_STORE=file|keyring`, `MADALEAN_SHELL_TEST_LOG` (JSON trace, no secrets),
  `MADALEAN_SHELL_TEST_AUTOSUBMIT=1` (submit a form prefilled by a deep link), `MADALEAN_SHELL_TEST_CLICK=id,…`.

**Why Tauri 2 and not Electron / a browser app-mode:** system WebKitGTK, 6.3 MB binary, native keyring access,
fine-grained navigation/download/new-window hooks; the AppImage is large only because it bundles WebKitGTK/GTK
so that it runs on other distributions (see sizes).

### Build (desktop)

```
cargo install tauri-cli --version "^2" --locked      # once (tested: tauri-cli 2.12.6)
scripts/build_appimage.sh                            # → shells/desktop/dist/Madalean-2.0.0-x86_64.AppImage + .sha256
scripts/build_appimage.sh --test                     # Rust unit tests only
shells/desktop/tests/e2e.sh [AppImage|binary]        # scripted end-to-end run (below)
scripts/install_desktop_entry.sh [--replace-old]     # menu entry, icon, madalean:// handler (user level)
```

Pinned (Cargo.lock): Rust 1.100, tauri 2.12.7, tauri-build 2.7.6, wry 0.57.3, webkit2gtk-rs 2.0.2 (system
WebKitGTK 2.54.2, webkit2gtk-4.1), tauri-plugin-single-instance 2.5.5, -window-state 2.5.0, -opener 2.7.3,
keyring 3.6.3, reqwest 0.12.28 (rustls). Build host deps (Arch): `webkit2gtk-4.1 gtk3 libsoup3 librsvg patchelf`
(+ `fuse2` to run AppImages). linuxdeploy is fetched by tauri-cli into `~/.cache/tauri`; the script sets
`NO_STRIP=true` (linuxdeploy's strip cannot read current Arch libraries).

## Android shell (`shells/android`, Flutter)

**Why Flutter + flutter_inappwebview instead of Tauri 2 Android.** The plugin already provides what a web wrapper
needs: file chooser for uploads, download hook, cookie manager, JavaScript handlers (for the `madaleanShell`
bridge), navigation interception, new-window handling and back history; flutter_secure_storage gives
Keystore-backed storage and app_links the deep links. About 150 lines of Kotlin were needed (device name, save to
Downloads, open a saved file). Tauri 2 Android would share the desktop's connect screen, but needs custom Kotlin
for downloads and Keystore storage, a remote-origin capability for the bridge, and a Rust build for four ABIs
through Gradle; its mobile support is younger. Everything was built and exercised on emulators (API 36, API 29).

Flow as above. Specifics:
- Back button: page history first, then a dialog (Change server / Cancel / Quit). Network error on the main page →
  "unreachable" screen with Retry and Change server. After > 30 s in background, `hello` is checked again.
- Downloads: same-origin URLs are fetched again natively with the Bearer token and saved to Downloads (MediaStore
  on Android 10+, the system "save as" picker on 8–9), then « Ouvrir ». `data:` decoded directly; `blob:` best
  effort (read in the page, passed through the bridge).
- Uploads: system file picker (`accept=".tex,.lean"` does not filter on Android: no MIME type for those).
- Deep link `madalean://pair?host=…&code=…` prefills address and code; the user taps « Appairer ».
- Adaptive icon (vector baobab-∀ on #1F2A44, monochrome layer for Android 13 themed icons), splash #1F2A44 + mark.
  Tablets: the responsive web UI, nothing specific in the shell.

### Build and signing (Android)

```
scripts/build_apk.sh --new-key   # ONCE: RSA-4096 release key, 10 000 days, refuses to overwrite
scripts/build_apk.sh             # release APKs per ABI + universal → shells/android/dist/, signature verified,
                                 # refuses debug-signed output, writes SHA256SUMS
scripts/build_apk.sh --debug     # debug APK (cleartext allowed to 10.0.2.2/127.0.0.1/localhost for the mock)
```

Release key: `~/.config/madalean/release-keys/madalean-release.jks` + `keystore.properties` (passwords), both 0600,
outside the repository (`*.jks`, `*.keystore` are git-ignored). Certificate `CN=Madalean, O=Madalean, C=MG`,
SHA-256 `0d43426ba9682f791707ee3233361c369c8ebec3f1209c6e000d7322936fc544`.
**The user must back up both files** (encrypted USB key / password manager): without them no update can be
installed over an existing installation (only uninstall + reinstall, which loses the pairing).

Pinned: Flutter 3.47.9 / Dart 3.13.7, AGP 8.13.2, Kotlin 2.4.0, Gradle 9.3.1, JDK 17, compileSdk/targetSdk 36,
minSdk 26 (Android 8.0); flutter_inappwebview 6.1.5, flutter_secure_storage 11.2.0, app_links 7.2.2, http 1.6.0,
shared_preferences 2.5.6, url_launcher 6.3.3, androidx core-splashscreen 1.0.1 (versions locked in pubspec.lock).

## Network setup on the host (`scripts/tailscale_setup.sh`)

Manages exactly one entry: `tailscale serve --bg --https=10500 http://127.0.0.1:11501`. Idempotent; refuses if
https port 10500 is used by anything else; refuses if Funnel is on for that port; never runs `serve reset` and never
touches other entries (Sampana: 443, 80, 10005–10447). `--status`, `--print` (exact commands, changes nothing),
`--remove` (only its own entry: `tailscale serve --https=10500 off`). Explains the MagicDNS + "Enable HTTPS"
prerequisites when the tailnet has no certificate domain. Not applied on this machine yet (integrator's job once
the server runs); `--status`/`--print` were run, and the refusal path was checked against a real Sampana port
(`MADALEAN_TS_PORT=10005` → refused, nothing changed).

## Security notes — what is stored where

| What | Desktop | Android |
|---|---|---|
| Device token (256 bit) | OS keyring via Secret Service (service `madalean`, account = origin `https://host:10500`); if no keyring answers: `~/.local/share/mg.madalean.desktop/tokens.json` (0600, dir 0700) | flutter_secure_storage (Android Keystore, AES-GCM), key `token:<origin>` |
| Server list, device name, language | `~/.local/share/mg.madalean.desktop/settings.json` (0600) — no secret | shared_preferences — no secret |
| Session cookie | WebKitGTK data dir of the app (`~/.local/share/mg.madalean.desktop/`), HttpOnly | WebView cookie store, HttpOnly |
| Window geometry | window-state plugin file in the app config dir | — |

- The token only travels in `Authorization: Bearer` from native code, over HTTPS (tailnet, Let's Encrypt
  certificate, system roots) or to loopback. Plain `http://` is refused except to `127.0.0.1`/`localhost`/`[::1]`
  (desktop) — release APKs refuse all cleartext (network security config), debug APKs allow 10.0.2.2/loopback.
- The web view only ever receives a one-time 60 s ticket; tokens and tickets are never logged (the test trace
  logs origins and event kinds only); the mock server logs no URLs.
- Remote pages get no native IPC; the bridge only offers "change server" and "open externally" and is injected
  only on http(s) pages. Off-origin navigations leave the app. Android app backup is disabled; permission requests
  from pages (camera, micro…) are denied.
- "Forget" deletes the token (and asks the server to revoke it when the endpoint exists) and clears the web view's
  cookies (desktop: all browsing data of the shell).
- The keyring probe at start may make KWallet / GNOME Keyring ask the user to unlock the wallet (normal keyring
  behaviour); if refused, the file fallback is used.

## Branding (`shells/branding`)

`madalean-icon.svg` (app icon: baobab whose crown is the quantifier ∀, on ink #1F2A44, paper #F2E6CF, laterite
ground line #D9643F), `madalean-mark-mono.svg` (single colour, `currentColor`, for monochrome / adaptive
foregrounds), `madalean-wordmark.svg` / `-dark.svg` (text set in a serif font stack — convert to paths before
print use), `png/` exports (16 → 1024 px). `candidates/` keeps the two other studies (lemur-tail λ, ravinala ⊢);
the baobab-∀ was chosen because it stays legible at 16–48 px and as a one-colour shape.

## Tests

- Desktop: `cargo test` in `shells/desktop/src-tauri` — 12 unit tests (addresses, pair links, answer mapping for
  both server shapes, saved servers + 0600/0700 files, token file store, file-name sanitising); 1 ignored test for
  the real keyring.
- Android: `flutter test` in `shells/android` — 34 tests (addresses, API client incl. both server shapes, controller
  flows: revocation, unreachable, re-auth loop guard, storage).
- End to end, desktop: `shells/desktop/tests/e2e.sh` runs the AppImage against the mock server inside a private
  `kwin_wayland --virtual` session with its own D-Bus bus, a temporary HOME, a rootful Xwayland for screenshots
  (ffmpeg x11grab) and a fake `xdg-open`. Nothing appears on the user's screen; no input is injected (clicks are
  done by a test-only init script). Checks: pairing via deep link → ticket → cookie → page authenticated by cookie
  → WebSocket; PDF download saved; external link → system opener; single instance forwards a deep link; restart
  reconnects with the stored token; wrong code; revocation; unreachable server (EN UI); host mode on the local
  listener; files 0600/0700. Last run: 14/14 PASS.
- End to end, Android: emulator runs (API 36 phone, API 29) against the mock through 10.0.2.2 with the debug APK;
  release APK launch + cleartext refusal. See "not verified".

## NOT verified (honest list)

Desktop:
- Against the real server (its ticket endpoints do not exist yet) and over the real tailnet HTTPS/port 10500
  (rustls + Let's Encrypt chain not exercised; the `Secure` cookie flag was not exercised: the mock serves http).
- The OS keyring path (KWallet/ksecretd or GNOME Keyring): only the file fallback ran in tests (an isolated
  ksecretd needs an interactive wallet-creation prompt). The keyring code path is untested.
- File upload through the GTK file chooser (needs real input); `target=_blank` links (WebKit blocks script-
  initiated popups, so only same-tab external links were exercised); blob:/data: downloads; the « Ouvrir » action of
  the download toast; reconnect on resume after a real suspend (logic exercised only by the start-up checks).
- The AppImage on another distribution / older glibc (built on Arch, glibc of 2026: it will NOT start on older
  distributions — build on the oldest target if needed); on a real Wayland desktop (tests used X11 inside a
  nested compositor); HiDPI; the installed launcher's `StartupWMClass` and the `madalean://` handler in a real
  KDE session (install script was run into a temporary HOME only).
- Light theme rendering (screenshots were taken with the environment preferring dark).

Android:
- No real phone or tablet: only x86_64 emulators (API 36, API 29); arm64/armv7 APKs never installed.
- Not against the real server, not over tailnet HTTPS with the Tailscale app running; cookie `Secure` flag not
  exercised. The final code (403/rate-limit tolerance, logout fallback) was re-run on the API 36 emulator with the
  debug APK and the 200 + meta-refresh session page: paired → ticket → session → page authenticated by cookie →
  WebSocket. The release APKs themselves were only launched (connect screen, cleartext refused) in the earlier run.
- Language: French by default, English when the device language is English (desktop: French unless switched).
- Android 8–9 "save as" download path, blob:/data: downloads, tablet layout, Android 13 themed icon rendering,
  splash on a real device, QR scan with the camera app, Keystore behaviour after a device restore.
