//! « Madalean Server » — the I/O half of host mode (pure logic in host.rs; DECISIONS D50).
//!
//! A poller (every 2 s, sooner after an action) asks the local listener `/api/hello` and
//! `systemctl --user show <unit>.service`, keeps a snapshot, relabels the window menu and the tray, and moves the window
//! between the server's web UI (running) and the bundled control panel `ui/host.html` (anything else). Actions run
//! `systemctl --user start|stop|restart <unit>.service` — the user manager only, never sudo.

use super::*;
use crate::host::{self, Action, HostArgs, Phase, ServiceInfo};
use std::process::{Command, Stdio};
use std::sync::Condvar;
use tauri::menu::{IsMenuItem, Menu, MenuItem, PredefinedMenuItem, Submenu};
use tauri::tray::{TrayIcon, TrayIconBuilder};
use tauri::Wry;

const POLL_EVERY: Duration = Duration::from_secs(2);
const ACTION_TIMEOUT: Duration = Duration::from_secs(40);
pub const SERVER_ICON_128: &[u8] = include_bytes!("../icons/server-128x128.png");
const SERVER_ICON_32: &[u8] = include_bytes!("../icons/server-32x32.png");

#[derive(Clone, Serialize)]
struct Snapshot {
    phase: Phase,
    version: String,
    host_name: String,
    host_lang: String,
    managed: bool,
    service: Option<ServiceInfo>,
}

pub struct HostCtx {
    pub args: HostArgs,
    snap: Mutex<Snapshot>,
    /// Open the web UI as soon as the server answers (at start, after Start/Restart, after an unexpected stop).
    auto_open: Mutex<bool>,
    /// The user pressed « Arrêter »: do not jump back to the web UI by ourselves.
    user_stopped: Mutex<bool>,
    busy: Mutex<Option<Action>>,
    last_error: Mutex<Option<String>>,
    items: Mutex<Vec<(String, MenuItem<Wry>)>>,
    submenu: Mutex<Option<Submenu<Wry>>>,
    tray: Mutex<Option<TrayIcon>>,
    wake: (Mutex<bool>, Condvar),
}

impl HostCtx {
    pub fn new(args: HostArgs) -> HostCtx {
        HostCtx {
            args,
            snap: Mutex::new(Snapshot {
                phase: Phase::Checking,
                version: String::new(),
                host_name: String::new(),
                host_lang: String::new(),
                managed: false,
                service: None,
            }),
            auto_open: Mutex::new(true),
            user_stopped: Mutex::new(false),
            busy: Mutex::new(None),
            last_error: Mutex::new(None),
            items: Mutex::new(Vec::new()),
            submenu: Mutex::new(None),
            tray: Mutex::new(None),
            wake: (Mutex::new(false), Condvar::new()),
        }
    }

    fn poke(&self) {
        *self.wake.0.lock().unwrap() = true;
        self.wake.1.notify_all();
    }
}

fn ctx(app: &AppHandle) -> Option<Arc<HostCtx>> {
    app.state::<Shared>().host.clone()
}

fn lang(app: &AppHandle) -> &'static str {
    let shell = app.state::<Shared>();
    let chosen = shell.settings.lock().unwrap().lang.clone();
    let host_lang = shell.host.as_ref().map(|h| h.snap.lock().unwrap().host_lang.clone()).unwrap_or_default();
    host::lang_or_default(chosen.as_deref(), &host_lang)
}

// ---------------------------------------------------------------- processes

/// Run a program with a timeout; stdout and stderr are read on their own threads (no pipe dead-lock).
fn run_cmd(prog: &str, args: &[String], timeout: Duration) -> Result<(bool, String, String), String> {
    let mut child = Command::new(prog)
        .args(args)
        .stdin(Stdio::null())
        .stdout(Stdio::piped())
        .stderr(Stdio::piped())
        .env("SYSTEMD_PAGER", "")
        .env("LC_ALL", "C.UTF-8")
        .spawn()
        .map_err(|e| format!("{prog}: {e}"))?;
    let read = |r: Option<Box<dyn std::io::Read + Send>>| {
        std::thread::spawn(move || {
            let mut s = Vec::new();
            if let Some(mut r) = r {
                let _ = std::io::Read::read_to_end(&mut r, &mut s);
            }
            String::from_utf8_lossy(&s).into_owned()
        })
    };
    let out = read(child.stdout.take().map(|r| Box::new(r) as Box<dyn std::io::Read + Send>));
    let err = read(child.stderr.take().map(|r| Box::new(r) as Box<dyn std::io::Read + Send>));
    let t0 = Instant::now();
    let status = loop {
        match child.try_wait() {
            Ok(Some(s)) => break s,
            Ok(None) if t0.elapsed() > timeout => {
                let _ = child.kill();
                let _ = child.wait();
                return Err(format!("{prog}: timeout"));
            }
            Ok(None) => std::thread::sleep(Duration::from_millis(40)),
            Err(e) => return Err(e.to_string()),
        }
    };
    Ok((status.success(), out.join().unwrap_or_default(), err.join().unwrap_or_default()))
}

/// `systemctl --user show`; None when systemctl is missing or the user manager does not answer.
fn service_info(unit: &str) -> Option<ServiceInfo> {
    match run_cmd("systemctl", &host::show_args(unit), Duration::from_secs(8)) {
        Ok((true, out, _)) => Some(host::parse_show(&out)),
        _ => None,
    }
}

// ---------------------------------------------------------------- poller

pub fn start_poller(app: AppHandle) {
    // Test hook (tests/host_e2e.sh): MADALEAN_HOST_TEST_ACTIONS="stop@6,start@14,logs@20,panel@24" runs menu actions
    // at those seconds after start, as if clicked (no input is injected in the test session).
    if let Ok(spec) = std::env::var("MADALEAN_HOST_TEST_ACTIONS") {
        let app2 = app.clone();
        std::thread::spawn(move || {
            let t0 = Instant::now();
            for (id, at) in spec.split(',').filter_map(|p| p.split_once('@')).filter_map(|(a, s)| Some((a.to_string(), s.parse::<u64>().ok()?))) {
                let wait = Duration::from_secs(at).saturating_sub(t0.elapsed());
                std::thread::sleep(wait);
                app2.state::<Shared>().log("host_test_action", serde_json::json!({ "id": id }));
                on_menu(&app2, &id);
            }
        });
    }
    std::thread::spawn(move || loop {
        tick(&app);
        let Some(c) = ctx(&app) else { return };
        let mut woken = c.wake.0.lock().unwrap();
        if !*woken {
            woken = c.wake.1.wait_timeout(woken, POLL_EVERY).unwrap().0;
        }
        *woken = false;
    });
}

fn tick(app: &AppHandle) {
    let Some(c) = ctx(app) else { return };
    let shell = app.state::<Shared>().inner().clone();
    let hello = tauri::async_runtime::block_on(net::hello(&shell.local_url, None)).ok().filter(|h| h.local);
    let svc = service_info(&c.args.unit);
    let phase = host::derive(svc.as_ref(), hello.is_some());
    let next = Snapshot {
        phase,
        version: hello.as_ref().map(|h| h.version.clone()).unwrap_or_default(),
        host_name: hello.as_ref().map(|h| h.host_name.clone()).unwrap_or_default(),
        host_lang: hello.as_ref().map(|h| h.lang.clone()).unwrap_or_else(|| c.snap.lock().unwrap().host_lang.clone()),
        managed: host::managed(svc.as_ref()),
        service: svc,
    };
    let changed = {
        let mut s = c.snap.lock().unwrap();
        let ch = s.phase != next.phase || s.version != next.version || s.host_lang != next.host_lang || s.managed != next.managed;
        if ch {
            shell.log("host_state", serde_json::json!({ "phase": next.phase, "version": next.version, "managed": next.managed }));
        }
        *s = next;
        ch
    };
    if changed {
        refresh_labels(app);
    }
    let showing_ui = shell.current.lock().unwrap().is_some();
    if phase != Phase::Running && showing_ui {
        // The server went away under the web UI: back to the panel, and come back by ourselves unless the user
        // stopped it.
        *c.auto_open.lock().unwrap() = !*c.user_stopped.lock().unwrap();
        show_connect(app, "stopped");
    } else if phase == Phase::Running && !showing_ui {
        let go = std::mem::replace(&mut *c.auto_open.lock().unwrap(), false);
        if go {
            open_ui(app);
        }
    }
}

fn open_ui(app: &AppHandle) {
    let app = app.clone();
    tauri::async_runtime::spawn(async move {
        let local = app.state::<Shared>().local_url.clone();
        if let Err(e) = open_origin(&app, local).await {
            app.state::<Shared>().log("host_open_error", serde_json::to_value(&e).unwrap_or_default());
            show_connect(&app, "unreachable");
        }
    });
}

fn show_panel(app: &AppHandle, reason: &str) {
    if let Some(c) = ctx(app) {
        *c.auto_open.lock().unwrap() = false;
    }
    show_connect(app, reason);
    focus(app);
}

fn focus(app: &AppHandle) {
    if let Some(w) = main_window(app) {
        let _ = w.unminimize();
        let _ = w.show();
        let _ = w.set_focus();
    }
}

fn run_action(app: &AppHandle, action: Action) -> Result<(), ShellError> {
    let c = ctx(app).ok_or(ShellError::Internal { detail: "not in host mode".into() })?;
    {
        let mut busy = c.busy.lock().unwrap();
        if busy.is_some() {
            return Ok(());
        }
        *busy = Some(action);
    }
    *c.last_error.lock().unwrap() = None;
    *c.user_stopped.lock().unwrap() = action == Action::Stop;
    *c.auto_open.lock().unwrap() = action != Action::Stop;
    app.state::<Shared>().log("host_action", serde_json::json!({ "action": action }));
    refresh_labels(app);
    let app = app.clone();
    let c2 = c.clone();
    std::thread::spawn(move || {
        let c = c2;
        let r = run_cmd("systemctl", &host::action_args(action, &c.args.unit), ACTION_TIMEOUT);
        let err = match r {
            Ok((true, _, _)) => None,
            Ok((false, _, e)) => Some(e.trim().chars().rev().take(600).collect::<Vec<_>>().into_iter().rev().collect()),
            Err(e) => Some(e),
        };
        if let Some(e) = &err {
            app.state::<Shared>().log("host_action_error", serde_json::json!({ "action": action, "error": e }));
        }
        *c.last_error.lock().unwrap() = err;
        *c.busy.lock().unwrap() = None;
        refresh_labels(&app);
        c.poke();
    });
    c.poke();
    Ok(())
}

// ---------------------------------------------------------------- menus and tray

fn item(app: &AppHandle, id: &str, lang: &str, enabled: bool) -> tauri::Result<MenuItem<Wry>> {
    let base = id.strip_prefix("tray_").unwrap_or(id);
    MenuItem::with_id(app, id, host::menu_label(base, lang), enabled, None::<&str>)
}

/// The window's menu bar « Serveur ». Returns the menu to pass to the window builder.
pub fn build_menu(app: &AppHandle) -> tauri::Result<Menu<Wry>> {
    let c = ctx(app).expect("host mode");
    let l = lang(app);
    let mut items = Vec::new();
    for id in ["status", "open_ui", "panel", "start", "stop", "restart", "logs", "browser", "quit"] {
        items.push((id.to_string(), item(app, id, l, id != "status")?));
    }
    // Separators after « Panneau du serveur », « Redémarrer » and « Ouvrir dans le navigateur ».
    let seps = [PredefinedMenuItem::separator(app)?, PredefinedMenuItem::separator(app)?, PredefinedMenuItem::separator(app)?];
    let mut entries: Vec<&dyn IsMenuItem<Wry>> = Vec::new();
    for (id, m) in &items {
        entries.push(m);
        match id.as_str() {
            "panel" => entries.push(&seps[0]),
            "restart" => entries.push(&seps[1]),
            "browser" => entries.push(&seps[2]),
            _ => {}
        }
    }
    let sub = Submenu::with_items(app, host::menu_label("menu", l), true, &entries)?;
    drop(entries);
    let menu = Menu::with_items(app, &[&sub])?;
    c.items.lock().unwrap().extend(items);
    *c.submenu.lock().unwrap() = Some(sub);
    Ok(menu)
}

/// Tray icon (status + quick actions), only when an AppIndicator library is installed: libappindicator-sys aborts the
/// program when it cannot load one. KDE shows it natively; GNOME needs the AppIndicator extension.
pub fn build_tray(app: &AppHandle) {
    let Some(c) = ctx(app) else { return };
    if std::env::var("MADALEAN_HOST_NO_TRAY").is_ok_and(|v| v == "1") || !host::appindicator_available(&host::LIB_DIRS) {
        app.state::<Shared>().log("host_tray", serde_json::json!({ "created": false }));
        return;
    }
    let l = lang(app);
    let r = (|| -> tauri::Result<TrayIcon> {
        let mut items = Vec::new();
        for id in ["tray_status", "tray_show", "tray_start", "tray_stop", "tray_restart", "tray_quit"] {
            items.push((id.to_string(), item(app, id, l, id != "tray_status")?));
        }
        let s1 = PredefinedMenuItem::separator(app)?;
        let s2 = PredefinedMenuItem::separator(app)?;
        let r: Vec<&MenuItem<Wry>> = items.iter().map(|(_, m)| m).collect();
        let menu = Menu::with_items(app, &[r[0], r[1], &s1, r[2], r[3], r[4], &s2, r[5]])?;
        let tray = TrayIconBuilder::with_id("madalean-server")
            .icon(tauri::image::Image::from_bytes(SERVER_ICON_32)?)
            .tooltip(host::HOST_TITLE)
            .menu(&menu)
            .show_menu_on_left_click(true)
            .on_menu_event(|app, ev| on_menu(app, ev.id().as_ref()))
            .build(app)?;
        c.items.lock().unwrap().extend(items);
        Ok(tray)
    })();
    match r {
        Ok(t) => {
            *c.tray.lock().unwrap() = Some(t);
            app.state::<Shared>().log("host_tray", serde_json::json!({ "created": true }));
        }
        Err(e) => eprintln!("madalean-server: no tray icon: {e}"),
    }
}

/// Labels and enabled states of every menu item from the current snapshot (also on a language change).
pub fn refresh_labels(app: &AppHandle) {
    let Some(c) = ctx(app) else { return };
    let l = lang(app);
    let s = c.snap.lock().unwrap().clone();
    let busy = c.busy.lock().unwrap().is_some();
    let (can_start, can_stop, can_restart) = host::allowed(s.phase, s.managed, busy);
    let status = host::status_line(s.phase, &s.version, l);
    for (id, m) in c.items.lock().unwrap().iter() {
        let base = id.strip_prefix("tray_").unwrap_or(id);
        let _ = if base == "status" { m.set_text(&status) } else { m.set_text(host::menu_label(base, l)) };
        let enabled = match base {
            "status" => false,
            "open_ui" => s.phase == Phase::Running,
            "start" => can_start,
            "stop" => can_stop,
            "restart" => can_restart,
            _ => true,
        };
        let _ = m.set_enabled(enabled);
    }
    if let Some(sub) = c.submenu.lock().unwrap().as_ref() {
        let _ = sub.set_text(host::menu_label("menu", l));
    }
    let tray = c.tray.lock().unwrap().clone();
    if let Some(t) = tray {
        let _ = t.set_tooltip(Some(&status));
    }
}

pub fn on_menu(app: &AppHandle, id: &str) {
    match id.strip_prefix("tray_").unwrap_or(id) {
        "open_ui" => {
            if let Some(c) = ctx(app) {
                if c.snap.lock().unwrap().phase == Phase::Running {
                    open_ui(app);
                }
            }
        }
        "panel" => show_panel(app, "manual"),
        "logs" => show_panel(app, "logs"),
        "show" => focus(app),
        "browser" => open_browser(app),
        "quit" => app.exit(0),
        other => {
            if let Some(a) = Action::parse(other) {
                let _ = run_action(app, a);
            }
        }
    }
}

fn open_browser(app: &AppHandle) {
    let url = app.state::<Shared>().local_url.to_string();
    let _ = app.opener().open_url(url, None::<&str>);
}

// ---------------------------------------------------------------- commands of the bundled panel (ui/host.html)

#[derive(Serialize)]
pub struct HostView {
    phase: Phase,
    version: String,
    host_name: String,
    managed: bool,
    service: Option<ServiceInfo>,
    busy: Option<Action>,
    error: Option<String>,
    can_start: bool,
    can_stop: bool,
    can_restart: bool,
    url: String,
    unit: String,
    lang: &'static str,
    app_version: &'static str,
    install_sh: Option<String>,
}

fn not_host() -> ShellError {
    ShellError::Internal { detail: "not in host mode".into() }
}

#[tauri::command]
pub fn host_status(app: AppHandle) -> Result<HostView, ShellError> {
    let c = ctx(&app).ok_or_else(not_host)?;
    let s = c.snap.lock().unwrap().clone();
    let busy = *c.busy.lock().unwrap();
    let error = c.last_error.lock().unwrap().clone();
    let (can_start, can_stop, can_restart) = host::allowed(s.phase, s.managed, busy.is_some());
    Ok(HostView {
        phase: s.phase,
        version: s.version,
        host_name: s.host_name,
        managed: s.managed,
        service: s.service,
        busy,
        error,
        can_start,
        can_stop,
        can_restart,
        url: app.state::<Shared>().local_url.to_string(),
        unit: c.args.unit.clone(),
        lang: lang(&app),
        app_version: env!("CARGO_PKG_VERSION"),
        install_sh: std::env::current_exe().ok().and_then(|e| host::find_install_sh(&e)).map(|p| p.display().to_string()),
    })
}

#[tauri::command]
pub fn host_action(app: AppHandle, action: String) -> Result<(), ShellError> {
    let a = Action::parse(&action).ok_or(ShellError::Internal { detail: "unknown action".into() })?;
    run_action(&app, a)
}

#[tauri::command]
pub async fn host_logs(app: AppHandle, lines: u32) -> Result<String, ShellError> {
    let c = ctx(&app).ok_or_else(not_host)?;
    let args = host::journal_args(&c.args.unit, lines);
    let r = tauri::async_runtime::spawn_blocking(move || run_cmd("journalctl", &args, Duration::from_secs(15)))
        .await
        .map_err(|e| ShellError::Internal { detail: e.to_string() })?;
    match r {
        Ok((_, out, err)) if !out.trim().is_empty() || err.trim().is_empty() => Ok(out),
        Ok((_, _, err)) => Ok(err),
        Err(e) => Err(ShellError::Internal { detail: e }),
    }
}

#[tauri::command]
pub fn host_open(app: AppHandle, what: String) -> Result<(), ShellError> {
    ctx(&app).ok_or_else(not_host)?;
    match what.as_str() {
        "ui" => {
            if let Some(c) = ctx(&app) {
                *c.auto_open.lock().unwrap() = true;
                c.poke();
            }
        }
        "browser" => open_browser(&app),
        _ => {}
    }
    Ok(())
}
