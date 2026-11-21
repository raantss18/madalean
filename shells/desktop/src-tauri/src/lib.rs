//! Madalean desktop shell (Tauri 2). See docs/SHELLS.md.
//!
//! The main window starts on the bundled connect screen (`ui/`), which drives the commands below.
//! Once connected, the same window navigates to the server's web UI: directly on the host's
//! trusted local listener, or through the one-time ticket → HttpOnly cookie exchange elsewhere.
//! Remote pages get no Tauri IPC at all: the small `window.madaleanShell` bridge talks to the shell
//! by navigating to `madalean://shell/…` URLs, which the navigation handler intercepts.

pub mod core;
pub mod net;
pub mod store;

use crate::core::*;
use crate::store::{AutoStore, TokenStore};
use serde::Serialize;
use std::io::Write;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use std::time::{Duration, Instant};
use tauri::webview::{DownloadEvent, NewWindowResponse, PageLoadEvent};
use tauri::{AppHandle, Manager, State, WebviewUrl, WebviewWindow, WebviewWindowBuilder};
use tauri_plugin_opener::OpenerExt;
use url::Url;

const BRIDGE_JS: &str = include_str!("bridge.js");
/// Re-check the server when the window regains focus after this long (resume after sleep…).
const RECHECK_AFTER: Duration = Duration::from_secs(45);

#[derive(Clone)]
struct Current {
    origin: Url,
    local: bool,
}

pub struct Shell {
    settings_path: PathBuf,
    settings: Mutex<Settings>,
    tokens: AutoStore,
    current: Mutex<Option<Current>>,
    last_check: Mutex<Instant>,
    pending_link: Mutex<Option<PairLink>>,
    app_url: Mutex<Option<Url>>,
    local_url: Url,
    reauth_count: Mutex<(Instant, u32)>,
    downloads: Mutex<Vec<PathBuf>>,
    test_log: Option<PathBuf>,
}

type Shared = Arc<Shell>;

impl Shell {
    fn log(&self, kind: &str, extra: serde_json::Value) {
        // Test-only trace (MADALEAN_SHELL_TEST_LOG). Never contains tokens or tickets.
        if let Some(p) = &self.test_log {
            if let Ok(mut f) = std::fs::OpenOptions::new().create(true).append(true).open(p) {
                let _ = writeln!(f, "{}", serde_json::json!({"t": now_secs(), "kind": kind, "extra": extra}));
            }
        }
    }

    fn save_settings(&self) {
        let s = self.settings.lock().unwrap().clone();
        if let Err(e) = s.save(&self.settings_path) {
            eprintln!("madalean: cannot save settings: {e}");
        }
    }
}

fn main_window(app: &AppHandle) -> Option<WebviewWindow> {
    app.get_webview_window("main")
}

/// Back to the bundled connect screen, with a reason shown there (`#screen=…`).
fn show_connect(app: &AppHandle, reason: &str) {
    let shell = app.state::<Shared>();
    *shell.current.lock().unwrap() = None;
    shell.log("connect_screen", serde_json::json!({ "reason": reason }));
    let base = shell.app_url.lock().unwrap().clone();
    if let (Some(w), Some(mut u)) = (main_window(app), base) {
        u.set_fragment(Some(&format!("reason={reason}")));
        let _ = w.navigate(u);
        let _ = w.set_title("Madalean");
    }
}

/// Connect to an origin we know: local listener directly, otherwise Bearer → ticket → cookie.
async fn open_origin(app: &AppHandle, origin: Url) -> Result<(), ShellError> {
    let shell = app.state::<Shared>().inner().clone();
    let key = origin_key(&origin);
    let is_local_url = same_origin(&origin, &shell.local_url);
    let token = if is_local_url {
        None
    } else {
        shell.tokens.get(&key).map_err(|detail| ShellError::Storage { detail })?
    };
    let hello = net::hello(&origin, token.as_deref()).await?;
    let target = if hello.local {
        origin.join("/").expect("root")
    } else {
        let Some(token) = token else {
            return Err(ShellError::NeedPairing);
        };
        if !hello.paired {
            // Token revoked on the host: forget it, the user must pair again.
            let _ = shell.tokens.delete(&key);
            shell.log("revoked", serde_json::json!({ "origin": key }));
            return Err(ShellError::Revoked);
        }
        let t = net::ticket(&origin, &token).await.inspect_err(|e| {
            if *e == ShellError::Revoked {
                let _ = shell.tokens.delete(&key);
            }
        })?;
        session_url(&origin, &t, "/")
    };
    {
        let mut st = shell.settings.lock().unwrap();
        let prev = st.servers.iter().find(|s| s.origin == key).cloned();
        if !hello.local || prev.is_some() {
            st.upsert(SavedServer {
                origin: key.clone(),
                host_name: hello.host_name.clone(),
                device_name: prev.map(|p| p.device_name).unwrap_or_default(),
                last_used: now_secs(),
            });
        }
    }
    shell.save_settings();
    *shell.current.lock().unwrap() = Some(Current { origin: origin.clone(), local: hello.local });
    *shell.last_check.lock().unwrap() = Instant::now();
    shell.log("open", serde_json::json!({ "origin": key, "local": hello.local, "host": hello.host_name }));
    let w = main_window(app).ok_or(ShellError::Internal { detail: "no window".into() })?;
    let title = if hello.host_name.is_empty() { "Madalean".to_string() } else { format!("Madalean — {}", hello.host_name) };
    let _ = w.set_title(&title);
    w.navigate(target).map_err(|e| ShellError::Internal { detail: e.to_string() })
}

// ---------------------------------------------------------------- commands (bundled UI only)

#[derive(Serialize)]
struct InitState {
    version: &'static str,
    lang: String,
    servers: Vec<ServerView>,
    device_name: String,
    pending_link: Option<PairLink>,
    local_url: String,
    token_backend: &'static str,
    autosubmit: bool,
}

#[derive(Serialize)]
struct ServerView {
    origin: String,
    display: String,
    host_name: String,
    has_token: bool,
    last_used: u64,
}

#[tauri::command]
fn init_state(shell: State<'_, Shared>) -> InitState {
    let st = shell.settings.lock().unwrap().clone();
    let servers = st
        .servers
        .iter()
        .map(|s| ServerView {
            origin: s.origin.clone(),
            display: Url::parse(&s.origin).map(|u| display_address(&u)).unwrap_or_else(|_| s.origin.clone()),
            host_name: s.host_name.clone(),
            has_token: same_origin_str(&s.origin, &shell.local_url) || matches!(shell.tokens.get(&s.origin), Ok(Some(_))),
            last_used: s.last_used,
        })
        .collect();
    let device = st.servers.iter().find(|s| !s.device_name.is_empty()).map(|s| s.device_name.clone());
    InitState {
        version: env!("CARGO_PKG_VERSION"),
        lang: st.lang.unwrap_or_else(|| "fr".into()),
        servers,
        device_name: device.unwrap_or_else(|| default_device_name(&gethostname::gethostname().to_string_lossy())),
        pending_link: shell.pending_link.lock().unwrap().take(),
        local_url: shell.local_url.to_string(),
        token_backend: shell.tokens.backend(),
        autosubmit: std::env::var("MADALEAN_SHELL_TEST_AUTOSUBMIT").is_ok_and(|v| v == "1"),
    }
}

fn same_origin_str(a: &str, b: &Url) -> bool {
    Url::parse(a).map(|u| same_origin(&u, b)).unwrap_or(false)
}

/// Is the Madalean server running on this very machine (trusted local listener)?
#[tauri::command]
async fn probe_local(shell: State<'_, Shared>) -> Result<Option<Hello>, ()> {
    let local = shell.local_url.clone();
    Ok(net::hello(&local, None).await.ok().filter(|h| h.local))
}

#[tauri::command]
async fn connect(app: AppHandle, origin: String) -> Result<(), ShellError> {
    let u = normalise_address(&origin).map_err(|reason| ShellError::Address { reason })?;
    let r = open_origin(&app, u).await;
    if let Err(e) = &r {
        app.state::<Shared>().log("connect_error", serde_json::to_value(e).unwrap_or_default());
    }
    r
}

#[tauri::command]
async fn pair(app: AppHandle, address: String, code: String, device_name: String) -> Result<(), ShellError> {
    let shell = app.state::<Shared>().inner().clone();
    let origin = normalise_address(&address).map_err(|reason| ShellError::Address { reason })?;
    let code = code.trim().to_string();
    if !is_valid_code(&code) {
        return Err(ShellError::BadCode);
    }
    let device_name: String = device_name.trim().chars().filter(|c| !c.is_control()).take(64).collect();
    let device_name = if device_name.is_empty() { default_device_name("") } else { device_name };
    // Make sure it is a Madalean server before sending the code.
    let hello = net::hello(&origin, None).await?;
    if hello.local {
        return open_origin(&app, origin).await;
    }
    let result = net::pair(&origin, &code, &device_name).await;
    shell.log("pair", serde_json::json!({ "origin": origin_key(&origin), "ok": result.is_ok() }));
    let (token, _device_id) = result?;
    let key = origin_key(&origin);
    shell.tokens.set(&key, &token).map_err(|detail| ShellError::Storage { detail })?;
    {
        let mut st = shell.settings.lock().unwrap();
        st.upsert(SavedServer { origin: key, host_name: hello.host_name, device_name, last_used: now_secs() });
    }
    shell.save_settings();
    open_origin(&app, origin).await
}

#[tauri::command]
fn parse_link(text: String) -> Option<(PairLink, Option<String>)> {
    let l = parse_pair_link(&text)?;
    let origin = pair_link_origin(&l).ok().map(|o| origin_key(&o));
    Some((l, origin))
}

#[tauri::command]
async fn forget(app: AppHandle, origin: String) -> Result<(), ShellError> {
    let shell = app.state::<Shared>().inner().clone();
    if let Ok(u) = Url::parse(&origin) {
        if let Ok(Some(t)) = shell.tokens.get(&origin) {
            net::forget(&u, &t).await;
        }
    }
    shell.tokens.delete(&origin).map_err(|detail| ShellError::Storage { detail })?;
    shell.settings.lock().unwrap().remove(&origin);
    shell.save_settings();
    if let Some(w) = main_window(&app) {
        // Drop that server's session cookie too (WebKit cannot clear a single origin from here).
        let _ = w.clear_all_browsing_data();
    }
    shell.log("forget", serde_json::json!({ "origin": origin }));
    Ok(())
}

#[tauri::command]
fn set_lang(shell: State<'_, Shared>, lang: String) {
    let lang = if lang == "en" { "en" } else { "fr" };
    shell.settings.lock().unwrap().lang = Some(lang.into());
    shell.save_settings();
}

// ---------------------------------------------------------------- navigation policy

/// `madalean://pair?…` deep link (argv, second instance, or a link inside a page).
fn handle_deep_link(app: &AppHandle, link: &str) {
    let shell = app.state::<Shared>();
    if let Some(l) = parse_pair_link(link) {
        shell.log("deep_link", serde_json::json!({ "host": l.host, "has_code": l.code.is_some() }));
        *shell.pending_link.lock().unwrap() = Some(l);
        show_connect(app, "link");
    }
    if let Some(w) = main_window(app) {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

/// `madalean://shell/<action>` requests from the bridge in remote pages.
fn handle_shell_url(app: &AppHandle, url: &Url) {
    match url.path().trim_start_matches('/') {
        "change-server" => show_connect(app, "manual"),
        "check" => recheck(app.clone(), true),
        "open-download" => {
            let shell = app.state::<Shared>();
            let idx: Option<usize> = url.query_pairs().find(|(k, _)| k == "i").and_then(|(_, v)| v.parse().ok());
            let path = idx.and_then(|i| shell.downloads.lock().unwrap().get(i).cloned());
            if let Some(p) = path {
                let _ = app.opener().open_path(p.to_string_lossy(), None::<&str>);
            }
        }
        _ => {}
    }
}

/// Re-check the current server (resume, network back, `/pair` page reached).
fn recheck(app: AppHandle, force: bool) {
    let shell = app.state::<Shared>().inner().clone();
    let Some(cur) = shell.current.lock().unwrap().clone() else { return };
    {
        let mut last = shell.last_check.lock().unwrap();
        if !force && last.elapsed() < RECHECK_AFTER {
            return;
        }
        *last = Instant::now();
    }
    tauri::async_runtime::spawn(async move {
        let key = origin_key(&cur.origin);
        let token = if cur.local { None } else { shell.tokens.get(&key).ok().flatten() };
        match net::hello(&cur.origin, token.as_deref()).await {
            Err(ShellError::Unreachable { .. }) | Err(ShellError::Tls { .. }) => {
                shell.log("recheck", serde_json::json!({ "result": "unreachable" }));
                show_connect(&app, "unreachable")
            }
            Ok(h) if !h.local && !h.paired => {
                let _ = shell.tokens.delete(&key);
                shell.log("recheck", serde_json::json!({ "result": "revoked" }));
                show_connect(&app, "revoked")
            }
            _ => shell.log("recheck", serde_json::json!({ "result": "ok" })),
        }
    });
}

/// The server sent the web view to `/pair`: the session cookie is missing or dead.
fn reauthenticate(app: AppHandle, origin: Url) {
    let shell = app.state::<Shared>().inner().clone();
    {
        // Never loop: at most 3 automatic re-authentications per minute.
        let mut rc = shell.reauth_count.lock().unwrap();
        if rc.0.elapsed() > Duration::from_secs(60) {
            *rc = (Instant::now(), 0);
        }
        rc.1 += 1;
        if rc.1 > 3 {
            drop(rc);
            show_connect(&app, "session_failed");
            return;
        }
    }
    shell.log("reauth", serde_json::json!({ "origin": origin_key(&origin) }));
    tauri::async_runtime::spawn(async move {
        match open_origin(&app, origin).await {
            Ok(()) => {}
            Err(ShellError::Revoked) => show_connect(&app, "revoked"),
            Err(ShellError::Unreachable { .. }) | Err(ShellError::Tls { .. }) => show_connect(&app, "unreachable"),
            Err(_) => show_connect(&app, "session_failed"),
        }
    });
}

/// Decide a top-level navigation of the main web view. Returns true to let it happen.
fn on_navigate(app: &AppHandle, url: &Url) -> bool {
    let shell = app.state::<Shared>().inner().clone();
    match url.scheme() {
        "madalean" => {
            if url.host_str() == Some("shell") {
                handle_shell_url(app, url);
            } else {
                handle_deep_link(app, url.as_str());
            }
            return false;
        }
        "tauri" | "about" | "blob" | "data" => return true,
        "http" | "https" => {}
        "mailto" => {
            let _ = app.opener().open_url(url.as_str(), None::<&str>);
            return false;
        }
        _ => return false,
    }
    // The bundled UI itself (dev server / custom protocol variants on other platforms).
    if let Some(base) = shell.app_url.lock().unwrap().as_ref() {
        if same_origin(base, url) {
            return true;
        }
    }
    let cur = shell.current.lock().unwrap().clone();
    match cur {
        Some(c) if same_origin(url, &c.origin) => {
            if !c.local && is_pair_page(url, &c.origin) {
                reauthenticate(app.clone(), c.origin.clone());
                return false;
            }
            true
        }
        _ => {
            // Anything else (documentation, Mathlib docs, GitHub…) goes to the system browser.
            shell.log("external", serde_json::json!({ "url": url.origin().ascii_serialization() }));
            let _ = app.opener().open_url(url.as_str(), None::<&str>);
            false
        }
    }
}

fn toast_js(text: &str, action: Option<(&str, String)>) -> String {
    format!(
        "window.__madaleanToast && window.__madaleanToast({}, {}, {});",
        serde_json::to_string(text).unwrap_or_default(),
        serde_json::to_string(&action.as_ref().map(|a| a.0)).unwrap_or_default(),
        serde_json::to_string(&action.map(|a| a.1)).unwrap_or_default()
    )
}

// ---------------------------------------------------------------- app

pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            if let Some(link) = argv.iter().find(|a| a.to_lowercase().starts_with("madalean://")) {
                handle_deep_link(app, link);
            } else if let Some(w) = main_window(app) {
                let _ = w.unminimize();
                let _ = w.show();
                let _ = w.set_focus();
            }
        }))
        .plugin(
            tauri_plugin_window_state::Builder::default()
                .with_state_flags(
                    tauri_plugin_window_state::StateFlags::all() - tauri_plugin_window_state::StateFlags::VISIBLE,
                )
                .build(),
        )
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![init_state, probe_local, connect, pair, parse_link, forget, set_lang])
        .setup(|app| {
            let data_dir = app.path().app_data_dir()?;
            let local_url = std::env::var("MADALEAN_LOCAL_URL")
                .ok()
                .and_then(|u| normalise_address(&u).ok())
                .unwrap_or_else(|| Url::parse(DEFAULT_LOCAL_URL).expect("static url"));
            let settings_path = data_dir.join("settings.json");
            let shell: Shared = Arc::new(Shell {
                settings: Mutex::new(Settings::load(&settings_path)),
                settings_path,
                tokens: AutoStore::new(data_dir.join("tokens.json")),
                current: Mutex::new(None),
                last_check: Mutex::new(Instant::now()),
                pending_link: Mutex::new(
                    std::env::args().skip(1).find(|a| a.to_lowercase().starts_with("madalean://")).and_then(|a| parse_pair_link(&a)),
                ),
                app_url: Mutex::new(None),
                local_url,
                reauth_count: Mutex::new((Instant::now(), 0)),
                downloads: Mutex::new(Vec::new()),
                test_log: std::env::var_os("MADALEAN_SHELL_TEST_LOG").map(PathBuf::from),
            });
            shell.log("start", serde_json::json!({ "token_backend": shell.tokens.backend() }));
            app.manage(shell.clone());

            let h_nav = app.handle().clone();
            let h_new = app.handle().clone();
            let h_dl = app.handle().clone();
            let h_load = app.handle().clone();
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Madalean")
                .inner_size(1280.0, 840.0)
                .min_inner_size(420.0, 520.0)
                .initialization_script(BRIDGE_JS)
                .on_navigation(move |url| on_navigate(&h_nav, url))
                .on_new_window(move |url, _features| {
                    // target=_blank / window.open: same server → this window; anything else → browser.
                    let cur = h_new.state::<Shared>().current.lock().unwrap().clone();
                    match cur {
                        Some(c) if same_origin(&url, &c.origin) => {
                            if let Some(w) = main_window(&h_new) {
                                let _ = w.navigate(url);
                            }
                        }
                        _ => {
                            on_navigate(&h_new, &url);
                        }
                    }
                    NewWindowResponse::Deny
                })
                .on_download(move |webview, event| {
                    let shell = h_dl.state::<Shared>().inner().clone();
                    match event {
                        DownloadEvent::Requested { url, destination } => {
                            // wry proposes ~/Downloads/<suggested name> (made unique); keep it.
                            shell.log("download_requested", serde_json::json!({ "path": destination.to_string_lossy(), "scheme": url.scheme() }));
                            true
                        }
                        DownloadEvent::Finished { path, success, .. } => {
                            shell.log("download_finished", serde_json::json!({ "success": success, "path": path }));
                            let fr = shell.settings.lock().unwrap().lang.as_deref() != Some("en");
                            let js = match (success, path) {
                                (true, Some(p)) => {
                                    let name = p.file_name().map(|n| n.to_string_lossy().to_string()).unwrap_or_default();
                                    let i = {
                                        let mut d = shell.downloads.lock().unwrap();
                                        d.push(p.clone());
                                        d.len() - 1
                                    };
                                    let msg = if fr { format!("Téléchargé : {name}") } else { format!("Downloaded: {name}") };
                                    toast_js(&msg, Some((if fr { "Ouvrir" } else { "Open" }, format!("madalean://shell/open-download?i={i}"))))
                                }
                                _ => toast_js(if fr { "Échec du téléchargement." } else { "Download failed." }, None),
                            };
                            let _ = webview.eval(&js);
                            true
                        }
                        _ => true,
                    }
                })
                .on_page_load(move |w, payload| {
                    if payload.event() != PageLoadEvent::Finished {
                        return;
                    }
                    let shell = h_load.state::<Shared>().inner().clone();
                    let url = payload.url().clone();
                    shell.log("page_loaded", serde_json::json!({ "origin": url.origin().ascii_serialization(), "path": url.path() }));
                    // Test hook (MADALEAN_SHELL_TEST_CLICK=<element id>): click an element of a server page.
                    if let Ok(id) = std::env::var("MADALEAN_SHELL_TEST_CLICK") {
                        if matches!(url.scheme(), "http" | "https") && url.path() == "/" {
                            let id = serde_json::to_string(&id).unwrap_or_default();
                            let _ = w.eval(format!("setTimeout(() => {{ const e = document.getElementById({id}); if (e) e.click(); }}, 1500);"));
                        }
                    }
                })
                .build()?;
            if let Ok(mut u) = window.url() {
                // tauri://localhost/index.html in production: the origin of the bundled connect screen.
                u.set_query(None);
                u.set_fragment(None);
                *shell.app_url.lock().unwrap() = Some(u);
            }
            let h_ev = app.handle().clone();
            window.on_window_event(move |ev| {
                if let tauri::WindowEvent::Focused(true) = ev {
                    recheck(h_ev.clone(), false);
                }
            });
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running Madalean");
}
