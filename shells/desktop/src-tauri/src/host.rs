//! « Madalean Server »: host mode of the desktop shell (DECISIONS D50, docs/SHELLS.md).
//!
//! The same binary, started with `--host` (or installed under the name `madalean-server`), is the host's own desktop
//! application: it shows the local Madalean (trusted listener, no pairing) in its own window, plus a small control
//! panel for the `madalean` systemd **user** service (start / stop / restart, logs, open in the browser).
//! This module is the pure part (arguments, service state, labels), unit-tested; lib.rs does the I/O.

use serde::Serialize;

/// Program name in host mode: GTK program name / X11 WM_CLASS / Wayland app_id, and the installed binary's name.
/// The desktop entry is `madalean-server.desktop` with `StartupWMClass=madalean-server`.
pub const HOST_PRGNAME: &str = "madalean-server";
/// Tauri identifier in host mode: separate single-instance D-Bus name and data directory from the client AppImage
/// (`mg.madalean.desktop`), so both can run on the same machine.
pub const HOST_IDENTIFIER: &str = "mg.madalean.server";
pub const HOST_TITLE: &str = "Madalean Server";

#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
pub struct HostArgs {
    /// systemd user unit name without `.service` (default `madalean`).
    pub unit: String,
    /// Port of the local listener (default 11500).
    pub port: u16,
}

impl Default for HostArgs {
    fn default() -> Self {
        HostArgs { unit: "madalean".into(), port: 11500 }
    }
}

/// Host mode when `--host` is given or the program is called `madalean-server`; `--unit NAME` and `--port N`
/// (written by the installer when they differ from the defaults). Unknown or invalid values keep the defaults.
pub fn parse_args(args: &[String]) -> Option<HostArgs> {
    let argv0 = args.first().map(String::as_str).unwrap_or("");
    let name = argv0.rsplit('/').next().unwrap_or("");
    let mut host = name == HOST_PRGNAME;
    let mut out = HostArgs::default();
    let mut it = args.iter().skip(1);
    while let Some(a) = it.next() {
        let (key, inline) = match a.split_once('=') {
            Some((k, v)) => (k, Some(v.to_string())),
            None => (a.as_str(), None),
        };
        match key {
            "--host" => host = true,
            "--unit" => {
                if let Some(v) = inline.or_else(|| it.next().cloned()) {
                    let v = v.strip_suffix(".service").unwrap_or(&v).to_string();
                    if valid_unit(&v) {
                        out.unit = v;
                    }
                }
            }
            "--port" => {
                if let Some(p) = inline.or_else(|| it.next().cloned()).and_then(|v| v.parse::<u16>().ok()) {
                    if p > 0 {
                        out.port = p;
                    }
                }
            }
            _ => {}
        }
    }
    host.then_some(out)
}

/// Same rule as install.sh / uninstall.sh (`^[A-Za-z0-9_.-]+$`), plus a length limit and no leading dash/dot.
pub fn valid_unit(name: &str) -> bool {
    !name.is_empty()
        && name.len() <= 64
        && !name.starts_with('-')
        && !name.starts_with('.')
        && name.chars().all(|c| c.is_ascii_alphanumeric() || matches!(c, '_' | '.' | '-'))
}

/// `systemctl --user show` properties we read.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize)]
pub struct ServiceInfo {
    pub load: String,
    pub active: String,
    pub sub: String,
    pub enabled: String,
}

pub fn show_args(unit: &str) -> Vec<String> {
    ["--user", "show", &format!("{unit}.service"), "--property=LoadState,ActiveState,SubState,UnitFileState"]
        .iter()
        .map(|s| s.to_string())
        .collect()
}

pub fn parse_show(out: &str) -> ServiceInfo {
    let mut s = ServiceInfo::default();
    for line in out.lines() {
        if let Some((k, v)) = line.split_once('=') {
            let v = v.trim().to_string();
            match k.trim() {
                "LoadState" => s.load = v,
                "ActiveState" => s.active = v,
                "SubState" => s.sub = v,
                "UnitFileState" => s.enabled = v,
                _ => {}
            }
        }
    }
    s
}

/// The only verbs the app runs, always on the user manager (never sudo, never the system manager).
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Action {
    Start,
    Stop,
    Restart,
}

impl Action {
    pub fn parse(s: &str) -> Option<Action> {
        match s {
            "start" => Some(Action::Start),
            "stop" => Some(Action::Stop),
            "restart" => Some(Action::Restart),
            _ => None,
        }
    }
    pub fn verb(self) -> &'static str {
        match self {
            Action::Start => "start",
            Action::Stop => "stop",
            Action::Restart => "restart",
        }
    }
}

pub fn action_args(action: Action, unit: &str) -> Vec<String> {
    vec!["--user".into(), action.verb().into(), format!("{unit}.service")]
}

pub fn journal_args(unit: &str, lines: u32) -> Vec<String> {
    vec![
        "--user".into(),
        "-u".into(),
        format!("{unit}.service"),
        "-n".into(),
        lines.clamp(10, 2000).to_string(),
        "--no-pager".into(),
        "-o".into(),
        "short-iso".into(),
    ]
}

/// What the window shows and the menus say.
#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum Phase {
    /// First check not done yet.
    Checking,
    /// `/api/hello` answers on the local listener.
    Running,
    Starting,
    Stopping,
    Stopped,
    Failed,
    /// No `<unit>.service` for this user (install.sh not run, or `--no-systemd`).
    NotInstalled,
    /// No `systemctl` (or no user manager): only a manually started server can be shown.
    NoSystemd,
}

/// Derive the phase from the service state and whether the server answers.
/// `service` = None when systemctl is missing or the user manager does not answer.
pub fn derive(service: Option<&ServiceInfo>, answers: bool) -> Phase {
    if answers {
        return Phase::Running;
    }
    let Some(s) = service else { return Phase::NoSystemd };
    if s.load == "not-found" || (s.load.is_empty() && s.active.is_empty()) {
        return Phase::NotInstalled;
    }
    match s.active.as_str() {
        // active but not answering yet: the server is loading (Python, listeners) — or hung; the panel says so.
        "active" | "activating" | "reloading" => Phase::Starting,
        "deactivating" => Phase::Stopping,
        "failed" => Phase::Failed,
        _ => Phase::Stopped,
    }
}

/// Is the running server the one of the service (start/stop/restart make sense)? A `madalean serve` started by hand
/// answers while the unit is inactive: the app shows it but does not offer to stop it.
pub fn managed(service: Option<&ServiceInfo>) -> bool {
    service.is_some_and(|s| matches!(s.active.as_str(), "active" | "activating" | "reloading" | "deactivating"))
}

/// Which actions make sense now (menu items and panel buttons).
pub fn allowed(phase: Phase, managed: bool, busy: bool) -> (bool, bool, bool) {
    if busy {
        return (false, false, false);
    }
    match phase {
        Phase::Running => (false, managed, managed),
        Phase::Starting => (false, true, true),
        Phase::Stopping => (false, false, false),
        Phase::Stopped | Phase::Failed => (true, false, true),
        Phase::Checking | Phase::NotInstalled | Phase::NoSystemd => (false, false, false),
    }
}

pub fn lang_or_default(chosen: Option<&str>, host: &str) -> &'static str {
    match chosen.unwrap_or(host) {
        "en" => "en",
        _ => "fr",
    }
}

/// Short state text (menus, tray title). The panel has its own longer texts (ui/host.js).
pub fn phase_label(phase: Phase, lang: &str) -> &'static str {
    let en = lang == "en";
    match phase {
        Phase::Checking => if en { "Checking…" } else { "Vérification…" },
        Phase::Running => if en { "Running" } else { "En marche" },
        Phase::Starting => if en { "Starting…" } else { "Démarrage…" },
        Phase::Stopping => if en { "Stopping…" } else { "Arrêt…" },
        Phase::Stopped => if en { "Stopped" } else { "Arrêté" },
        Phase::Failed => if en { "Stopped after an error" } else { "Arrêté après une erreur" },
        Phase::NotInstalled => if en { "Service not installed" } else { "Service non installé" },
        Phase::NoSystemd => if en { "Not running" } else { "Pas lancé" },
    }
}

/// Menu item ids (window menu and tray menu share them) and their labels.
pub const MENU_IDS: [&str; 10] =
    ["status", "open_ui", "panel", "start", "stop", "restart", "logs", "browser", "show", "quit"];

pub fn menu_label(id: &str, lang: &str) -> String {
    let en = lang == "en";
    let s = match id {
        "menu" => if en { "Server" } else { "Serveur" },
        "open_ui" => if en { "Open Madalean" } else { "Ouvrir Madalean" },
        "panel" => if en { "Server panel" } else { "Panneau du serveur" },
        "start" => if en { "Start" } else { "Démarrer" },
        "stop" => if en { "Stop" } else { "Arrêter" },
        "restart" => if en { "Restart" } else { "Redémarrer" },
        "logs" => if en { "Open the logs" } else { "Ouvrir les journaux" },
        "browser" => if en { "Open in the browser" } else { "Ouvrir dans le navigateur" },
        "show" => if en { "Show the window" } else { "Afficher la fenêtre" },
        "quit" => if en { "Quit" } else { "Quitter" },
        _ => "",
    };
    s.to_string()
}

pub fn status_line(phase: Phase, version: &str, lang: &str) -> String {
    let p = phase_label(phase, lang);
    if phase == Phase::Running && !version.is_empty() {
        format!("{HOST_TITLE} {version} — {p}")
    } else {
        format!("{HOST_TITLE} — {p}")
    }
}

/// `install.sh` of the installation this binary belongs to (`<prefix>/versions/<v>/dist/host-app/madalean-server`
/// → `<prefix>/versions/<v>/install.sh`), for the « service not installed » fix. Looks up to 4 levels up.
pub fn find_install_sh(exe: &std::path::Path) -> Option<std::path::PathBuf> {
    let mut d = exe.parent();
    for _ in 0..4 {
        let dir = d?;
        let p = dir.join("install.sh");
        if p.is_file() {
            return Some(p);
        }
        d = dir.parent();
    }
    None
}

/// Shared-library names the tray needs at run time (loaded with dlopen by libappindicator-sys, which aborts the
/// program when none loads): the tray is only created when one of them exists.
pub const APPINDICATOR_LIBS: [&str; 2] = ["libayatana-appindicator3.so.1", "libappindicator3.so.1"];
pub const LIB_DIRS: [&str; 6] = [
    "/usr/lib",
    "/usr/lib64",
    "/usr/lib/x86_64-linux-gnu",
    "/lib/x86_64-linux-gnu",
    "/usr/local/lib",
    "/lib64",
];

pub fn appindicator_available(dirs: &[&str]) -> bool {
    dirs.iter().any(|d| APPINDICATOR_LIBS.iter().any(|l| std::path::Path::new(d).join(l).exists()))
}

#[cfg(test)]
mod tests {
    use super::*;

    fn a(v: &[&str]) -> Vec<String> {
        v.iter().map(|s| s.to_string()).collect()
    }

    #[test]
    fn host_mode_by_flag_or_program_name() {
        assert_eq!(parse_args(&a(&["/opt/x/madalean"])), None);
        assert_eq!(parse_args(&a(&["/opt/x/madalean", "madalean://pair?host=x"])), None);
        assert_eq!(parse_args(&a(&["/opt/x/madalean", "--host"])), Some(HostArgs::default()));
        assert_eq!(parse_args(&a(&["/p/current/dist/host-app/madalean-server"])), Some(HostArgs::default()));
        assert_eq!(parse_args(&a(&["madalean-server"])), Some(HostArgs::default()));
        assert_eq!(
            parse_args(&a(&["madalean", "--host", "--unit", "madalean-test.service", "--port=11600"])),
            Some(HostArgs { unit: "madalean-test".into(), port: 11600 })
        );
        // invalid values keep the defaults
        assert_eq!(
            parse_args(&a(&["madalean", "--host", "--unit", "a b;rm", "--port", "0"])),
            Some(HostArgs::default())
        );
        assert_eq!(parse_args(&a(&["madalean", "--host", "--unit=-x", "--port=99999"])), Some(HostArgs::default()));
    }

    #[test]
    fn unit_names() {
        for ok in ["madalean", "madalean-test", "m_1.x"] {
            assert!(valid_unit(ok), "{ok}");
        }
        for bad in ["", "-x", ".x", "a/b", "a b", "a;b", "$(x)", &"x".repeat(65)] {
            assert!(!valid_unit(bad), "{bad}");
        }
    }

    #[test]
    fn systemctl_and_journalctl_arguments() {
        assert_eq!(action_args(Action::Restart, "madalean"), a(&["--user", "restart", "madalean.service"]));
        assert_eq!(action_args(Action::Stop, "m2"), a(&["--user", "stop", "m2.service"]));
        assert_eq!(show_args("madalean")[..3], a(&["--user", "show", "madalean.service"])[..]);
        assert_eq!(Action::parse("start"), Some(Action::Start));
        assert_eq!(Action::parse("enable"), None);
        assert_eq!(Action::parse("daemon-reload"), None);
        let j = journal_args("madalean", 5);
        assert_eq!(j[..3], a(&["--user", "-u", "madalean.service"])[..]);
        assert!(j.contains(&"10".to_string()) && j.contains(&"--no-pager".to_string()));
        assert!(journal_args("madalean", 1_000_000).contains(&"2000".to_string()));
    }

    #[test]
    fn parse_systemctl_show() {
        let s = parse_show("LoadState=loaded\nActiveState=active\nSubState=running\nUnitFileState=enabled\n");
        assert_eq!(s, ServiceInfo { load: "loaded".into(), active: "active".into(), sub: "running".into(), enabled: "enabled".into() });
        let s = parse_show("LoadState=not-found\nActiveState=inactive\nSubState=dead\nUnitFileState=\n");
        assert_eq!(s.load, "not-found");
    }

    #[test]
    fn phases() {
        let svc = |load: &str, active: &str| ServiceInfo { load: load.into(), active: active.into(), ..Default::default() };
        assert_eq!(derive(Some(&svc("loaded", "active")), true), Phase::Running);
        assert_eq!(derive(None, true), Phase::Running); // manual `madalean serve`, no systemd
        assert_eq!(derive(Some(&svc("loaded", "active")), false), Phase::Starting);
        assert_eq!(derive(Some(&svc("loaded", "activating")), false), Phase::Starting);
        assert_eq!(derive(Some(&svc("loaded", "deactivating")), false), Phase::Stopping);
        assert_eq!(derive(Some(&svc("loaded", "inactive")), false), Phase::Stopped);
        assert_eq!(derive(Some(&svc("loaded", "failed")), false), Phase::Failed);
        assert_eq!(derive(Some(&svc("not-found", "inactive")), false), Phase::NotInstalled);
        assert_eq!(derive(Some(&ServiceInfo::default()), false), Phase::NotInstalled);
        assert_eq!(derive(None, false), Phase::NoSystemd);
        assert!(managed(Some(&svc("loaded", "active"))));
        assert!(!managed(Some(&svc("loaded", "inactive"))));
        assert!(!managed(None));
    }

    #[test]
    fn allowed_actions() {
        assert_eq!(allowed(Phase::Running, true, false), (false, true, true));
        assert_eq!(allowed(Phase::Running, false, false), (false, false, false)); // started by hand
        assert_eq!(allowed(Phase::Stopped, false, false), (true, false, true));
        assert_eq!(allowed(Phase::Failed, false, false), (true, false, true));
        assert_eq!(allowed(Phase::Stopped, false, true), (false, false, false)); // an action is running
        assert_eq!(allowed(Phase::NotInstalled, false, false), (false, false, false));
    }

    #[test]
    fn labels_both_languages() {
        for id in MENU_IDS.iter().filter(|i| **i != "status") {
            assert!(!menu_label(id, "fr").is_empty() && !menu_label(id, "en").is_empty(), "{id}");
            assert_ne!(menu_label(id, "fr"), menu_label(id, "en"), "{id}");
        }
        assert_eq!(status_line(Phase::Running, "2.0.2", "fr"), "Madalean Server 2.0.2 — En marche");
        assert_eq!(status_line(Phase::Stopped, "", "en"), "Madalean Server — Stopped");
        assert_eq!(lang_or_default(None, "en"), "en");
        assert_eq!(lang_or_default(Some("fr"), "en"), "fr");
        assert_eq!(lang_or_default(None, ""), "fr");
    }

    #[test]
    fn install_sh_next_to_the_binary() {
        let d = tempfile::tempdir().unwrap();
        let v = d.path().join("versions/2.0.2");
        std::fs::create_dir_all(v.join("dist/host-app")).unwrap();
        std::fs::write(v.join("install.sh"), "#!/bin/sh\n").unwrap();
        assert_eq!(find_install_sh(&v.join("dist/host-app/madalean-server")), Some(v.join("install.sh")));
        assert_eq!(find_install_sh(&d.path().join("elsewhere/bin/madalean-server")), None);
    }

    #[test]
    fn tray_library_probe() {
        let d = tempfile::tempdir().unwrap();
        let p = d.path().to_str().unwrap();
        assert!(!appindicator_available(&[p]));
        std::fs::write(d.path().join("libayatana-appindicator3.so.1"), b"").unwrap();
        assert!(appindicator_available(&[p]));
    }
}
