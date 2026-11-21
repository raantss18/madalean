//! Pure logic of the desktop shell (no Tauri, no network): addresses, pair links, saved servers,
//! mapping of server answers. Mirrors `shells/android/lib/src/address.dart`. Unit-tested below.

use serde::{Deserialize, Serialize};
use std::path::{Path, PathBuf};
use url::Url;

/// Default HTTPS port of the remote listener published by `tailscale serve`.
/// Madalean's embedded Tailscale node (tsnet) serves HTTPS on the standard port: https://madalean.<tailnet>.ts.net
pub const DEFAULT_REMOTE_PORT: u16 = 443;
/// Port of the former `tailscale serve --https=10500` design: saved `*.ts.net:10500` servers are migrated to 443.
pub const LEGACY_REMOTE_PORT: u16 = 10500;
/// Trusted local listener of the server on the host itself.
pub const DEFAULT_LOCAL_URL: &str = "http://127.0.0.1:11500";
/// Hosts reached over plain HTTP (the host machine itself). Everything else must be HTTPS.
pub const LOOPBACK_HOSTS: [&str; 3] = ["127.0.0.1", "localhost", "[::1]"];

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum AddrError {
    Empty,
    Invalid,
    CleartextForbidden,
    NeedFullName,
}

fn host_str(u: &Url) -> String {
    match u.host() {
        Some(url::Host::Ipv6(a)) => format!("[{a}]"),
        Some(h) => h.to_string().to_lowercase(),
        None => String::new(),
    }
}

pub fn is_loopback_host(host: &str) -> bool {
    LOOPBACK_HOSTS.contains(&host.to_lowercase().as_str())
}

/// Normalise what the user typed ("pc.tailnet.ts.net", "host:port", "https://host:port/x") into an
/// origin URL `scheme://host:port/`. HTTPS only, except `http://` to a loopback host with an explicit port.
pub fn normalise_address(input: &str) -> Result<Url, AddrError> {
    let text = input.trim();
    if text.is_empty() {
        return Err(AddrError::Empty);
    }
    if text.chars().any(char::is_whitespace) {
        return Err(AddrError::Invalid);
    }
    let with_scheme = if text.contains("://") {
        text.to_string()
    } else {
        let host_part = text.split('/').next().unwrap_or("");
        let bare = if host_part.starts_with('[') {
            host_part.split(']').next().map(|h| format!("{h}]")).unwrap_or_default()
        } else {
            host_part.split(':').next().unwrap_or("").to_string()
        };
        if is_loopback_host(&bare) {
            format!("http://{text}")
        } else {
            format!("https://{text}")
        }
    };
    let u = Url::parse(&with_scheme).map_err(|_| AddrError::Invalid)?;
    let host = host_str(&u);
    if host.is_empty() || !u.username().is_empty() || u.password().is_some() {
        return Err(AddrError::Invalid);
    }
    match u.scheme() {
        "http" => {
            if !is_loopback_host(&host) {
                return Err(AddrError::CleartextForbidden);
            }
            // Url drops the default port 80; loopback addresses must name their listener port.
            let port = u.port().ok_or(AddrError::Invalid)?;
            Url::parse(&format!("http://{host}:{port}/")).map_err(|_| AddrError::Invalid)
        }
        "https" => {
            // A MagicDNS short name resolves, but the Let's Encrypt certificate is issued for the
            // full name (host.tailnet.ts.net): require a dotted name or an IP literal.
            if !host.contains('.') && !host.contains(':') {
                return Err(AddrError::NeedFullName);
            }
            let port = u.port_or_known_default().unwrap_or(DEFAULT_REMOTE_PORT);
            Url::parse(&format!("https://{host}:{port}/")).map_err(|_| AddrError::Invalid)
        }
        _ => Err(AddrError::Invalid),
    }
}

/// Canonical text form of an origin: `https://host` for the default 443, `scheme://host:port` otherwise.
pub fn origin_key(origin: &Url) -> String {
    let port = origin.port_or_known_default().unwrap_or(0);
    if origin.scheme() == "https" && port == 443 {
        format!("https://{}", host_str(origin))
    } else {
        format!("{}://{}:{}", origin.scheme(), host_str(origin), port)
    }
}

/// Saved origin of the former design (`https://<x>.ts.net:10500`) → its new canonical form (`https://<x>.ts.net`).
pub fn migrate_legacy_origin(origin: &str) -> Option<String> {
    let u = Url::parse(origin).ok()?;
    let host = host_str(&u);
    (u.scheme() == "https" && u.port() == Some(LEGACY_REMOTE_PORT) && host.ends_with(".ts.net")).then(|| format!("https://{host}"))
}

/// Display form: drops the default remote port.
pub fn display_address(origin: &Url) -> String {
    let port = origin.port_or_known_default().unwrap_or(0);
    if origin.scheme() == "https" && port == DEFAULT_REMOTE_PORT {
        host_str(origin)
    } else {
        format!("{}:{}", host_str(origin), port)
    }
}

pub fn same_origin(a: &Url, b: &Url) -> bool {
    a.scheme() == b.scheme() && host_str(a) == host_str(b) && a.port_or_known_default() == b.port_or_known_default()
}

/// True for a top-level navigation to the server's pairing page (`/pair`, `/pair?…`): the session
/// is gone (contract item 5), the shell takes over.
pub fn is_pair_page(url: &Url, origin: &Url) -> bool {
    same_origin(url, origin) && (url.path() == "/pair" || url.path() == "/pair/")
}

/// URL that swaps a one-time ticket for the HttpOnly session cookie (contract item 4).
pub fn session_url(origin: &Url, ticket: &str, next: &str) -> Url {
    let mut u = origin.join("/api/session").expect("static path");
    u.query_pairs_mut().append_pair("ticket", ticket).append_pair("next", next);
    u
}

pub fn is_valid_code(code: &str) -> bool {
    code.len() == 6 && code.bytes().all(|b| b.is_ascii_digit())
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct PairLink {
    pub host: String,
    pub code: Option<String>,
}

/// Parse a pairing link, also when embedded in pasted text: `madalean://pair?host=…&code=…`, or the https form shown
/// by the host as a QR code, `https://<host>/pair?code=…` (the host is then the link's own host[:port]).
pub fn parse_pair_link(text: &str) -> Option<PairLink> {
    let lower = text.to_lowercase();
    if let Some(start) = lower.find("madalean://pair") {
        let rest = &text[start..];
        let end = rest.find(char::is_whitespace).unwrap_or(rest.len());
        let u = Url::parse(&rest[..end]).ok()?;
        if u.host_str().map(str::to_lowercase).as_deref() != Some("pair") {
            return None;
        }
        let mut host = String::new();
        let mut code = None;
        for (k, v) in u.query_pairs() {
            match k.as_ref() {
                "host" => host = v.trim().to_string(),
                "code" if is_valid_code(v.trim()) => code = Some(v.trim().to_string()),
                _ => {}
            }
        }
        if host.is_empty() || host.contains('/') || host.contains('@') || host.chars().any(char::is_whitespace) {
            return None;
        }
        return Some(PairLink { host, code });
    }
    let start = lower.find("https://")?;
    let rest = &text[start..];
    let end = rest.find(char::is_whitespace).unwrap_or(rest.len());
    let u = Url::parse(&rest[..end]).ok()?;
    if u.path() != "/pair" || !u.username().is_empty() {
        return None;
    }
    let code = u.query_pairs().find(|(k, _)| k == "code").map(|(_, v)| v.trim().to_string()).filter(|c| is_valid_code(c))?;
    let host = match u.port() {
        Some(p) => format!("{}:{p}", host_str(&u)),
        None => host_str(&u),
    };
    Some(PairLink { host, code: Some(code) })
}

/// Origin of a pair-link host: https (port 10500 by default) except loopback hosts (http).
pub fn pair_link_origin(link: &PairLink) -> Result<Url, AddrError> {
    normalise_address(&link.host)
}

/// Answer of `GET /api/hello`.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Hello {
    pub name: String,
    #[serde(default)]
    pub version: String,
    #[serde(default)]
    pub paired: bool,
    #[serde(default)]
    pub local: bool,
    #[serde(default)]
    pub host_name: String,
}

/// Failures the connect screen knows how to explain (codes shared with the UI's message table).
#[derive(Debug, Clone, PartialEq, Eq, Serialize)]
#[serde(tag = "code", rename_all = "snake_case")]
pub enum ShellError {
    Address { reason: AddrError },
    Unreachable { detail: String },
    Tls { detail: String },
    NotMadalean,
    BadCode,
    Locked { retry_after: Option<u64> },
    Revoked,
    NeedPairing,
    Server { status: u16 },
    Storage { detail: String },
    Internal { detail: String },
}

/// Map the answer of `POST /api/pair` (contract item 2).
pub fn map_pair_response(status: u16, body: &str, retry_after_header: Option<&str>) -> Result<(String, Option<String>), ShellError> {
    let json: serde_json::Value = serde_json::from_str(body).unwrap_or(serde_json::Value::Null);
    match status {
        200 => {
            let token = json.get("token").and_then(|t| t.as_str()).unwrap_or("");
            // 256-bit token, URL-safe base64 (43 chars); refuse anything absurd.
            if token.len() < 32 || token.len() > 512 || !token.bytes().all(|b| b.is_ascii_graphic()) {
                return Err(ShellError::NotMadalean);
            }
            let dev = json
                .get("device_id")
                .or_else(|| json.get("device").and_then(|d| d.get("id")))
                .and_then(|d| d.as_str())
                .map(str::to_string);
            Ok((token.to_string(), dev))
        }
        // 401 bad_code (contract) or 403 wrong / expired / no_code (current server, docs/API.md).
        401 | 403 => Err(ShellError::BadCode),
        429 => {
            let ra = json
                .get("retry_after")
                .and_then(|v| v.as_u64())
                .or_else(|| retry_after_header.and_then(|h| h.trim().parse().ok()))
                .or_else(|| (json.get("error").and_then(|e| e.as_str()) == Some("rate_limited")).then_some(60));
            Err(ShellError::Locked { retry_after: ra })
        }
        404 => Err(ShellError::NotMadalean),
        s => Err(ShellError::Server { status: s }),
    }
}

/// One server known to this shell. No secret here: the token lives in the keyring / token file.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct SavedServer {
    pub origin: String,
    #[serde(default)]
    pub host_name: String,
    #[serde(default)]
    pub device_name: String,
    /// Unix seconds.
    #[serde(default)]
    pub last_used: u64,
}

#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct Settings {
    #[serde(default)]
    pub servers: Vec<SavedServer>,
    /// "fr" (default) or "en".
    #[serde(default)]
    pub lang: Option<String>,
    /// « Mises à jour automatiques » (default on).
    #[serde(default)]
    pub auto_update: Option<bool>,
    /// Unix seconds of the last successful channel check.
    #[serde(default)]
    pub last_update_check: u64,
}

impl Settings {
    pub fn load(path: &Path) -> Settings {
        std::fs::read_to_string(path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }

    pub fn save(&self, path: &Path) -> std::io::Result<()> {
        write_private_atomic(path, serde_json::to_string_pretty(self).unwrap_or_default().as_bytes())
    }

    /// Insert or refresh a server and keep the list most-recent first.
    pub fn upsert(&mut self, s: SavedServer) {
        self.servers.retain(|x| x.origin != s.origin);
        self.servers.push(s);
        self.servers.sort_by_key(|s| std::cmp::Reverse(s.last_used));
    }

    pub fn remove(&mut self, origin: &str) -> bool {
        let n = self.servers.len();
        self.servers.retain(|x| x.origin != origin);
        n != self.servers.len()
    }

    pub fn last(&self) -> Option<&SavedServer> {
        self.servers.first()
    }
}

/// Write a file readable only by the user (0600, parent 0700), atomically (tmp + rename).
pub fn write_private_atomic(path: &Path, data: &[u8]) -> std::io::Result<()> {
    use std::io::Write;
    #[cfg(unix)]
    use std::os::unix::fs::{OpenOptionsExt, PermissionsExt};
    let dir = path.parent().map(Path::to_path_buf).unwrap_or_else(|| PathBuf::from("."));
    std::fs::create_dir_all(&dir)?;
    #[cfg(unix)]
    std::fs::set_permissions(&dir, std::fs::Permissions::from_mode(0o700))?;
    let tmp = dir.join(format!(
        ".{}.tmp{}",
        path.file_name().and_then(|n| n.to_str()).unwrap_or("file"),
        std::process::id()
    ));
    let mut opts = std::fs::OpenOptions::new();
    opts.write(true).create(true).truncate(true);
    #[cfg(unix)]
    opts.mode(0o600);
    let mut f = opts.open(&tmp)?;
    f.write_all(data)?;
    f.sync_all()?;
    drop(f);
    std::fs::rename(&tmp, path)
}

/// Device name proposed on the pairing form: "<hostname> (Linux)".
pub fn default_device_name(hostname: &str) -> String {
    let h: String = hostname.chars().filter(|c| !c.is_control()).take(40).collect();
    if h.trim().is_empty() {
        "Linux".into()
    } else {
        format!("{} (Linux)", h.trim())
    }
}

/// Safe file name for a download: no path separators, no leading dots, no control characters.
pub fn sanitize_file_name(name: &str) -> String {
    let cleaned: String = name
        .chars()
        .map(|c| if c == '/' || c == '\\' || c.is_control() { '_' } else { c })
        .collect();
    let cleaned = cleaned.trim().trim_start_matches('.').to_string();
    let cleaned: String = cleaned.chars().take(180).collect();
    if cleaned.is_empty() { "download".into() } else { cleaned }
}

pub fn now_secs() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.as_secs())
        .unwrap_or(0)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn address_defaults_to_https_443() {
        let u = normalise_address("madalean.tail804764.ts.net").unwrap();
        assert_eq!(origin_key(&u), "https://madalean.tail804764.ts.net");
        assert_eq!(display_address(&u), "madalean.tail804764.ts.net");
        assert_eq!(u.as_str(), "https://madalean.tail804764.ts.net/");
        let u = normalise_address("https://madalean.tail804764.ts.net:443/pair?code=123456").unwrap();
        assert_eq!(origin_key(&u), "https://madalean.tail804764.ts.net");
        let u = normalise_address("  HTTPS://Pc.Tail.ts.net:8443/some/path?x=1 ").unwrap();
        assert_eq!(origin_key(&u), "https://pc.tail.ts.net:8443");
        assert_eq!(display_address(&u), "pc.tail.ts.net:8443");
        // explicit ports are kept
        let u = normalise_address("pc.tail.ts.net:10500").unwrap();
        assert_eq!(origin_key(&u), "https://pc.tail.ts.net:10500");
        assert_eq!(display_address(&u), "pc.tail.ts.net:10500");
    }

    #[test]
    fn address_cleartext_only_loopback_with_port() {
        assert_eq!(origin_key(&normalise_address("127.0.0.1:11501").unwrap()), "http://127.0.0.1:11501");
        assert_eq!(origin_key(&normalise_address("http://localhost:11500/").unwrap()), "http://localhost:11500");
        assert_eq!(origin_key(&normalise_address("[::1]:11501").unwrap()), "http://[::1]:11501");
        assert_eq!(normalise_address("http://pc.tail.ts.net:10500"), Err(AddrError::CleartextForbidden));
        assert_eq!(normalise_address("http://192.168.1.4:11501"), Err(AddrError::CleartextForbidden));
        assert_eq!(normalise_address("http://127.0.0.1"), Err(AddrError::Invalid));
    }

    #[test]
    fn address_rejections() {
        assert_eq!(normalise_address("  "), Err(AddrError::Empty));
        assert_eq!(normalise_address("pc tail"), Err(AddrError::Invalid));
        assert_eq!(normalise_address("antsa-pc"), Err(AddrError::NeedFullName));
        assert_eq!(normalise_address("https://user:pw@pc.tail.ts.net"), Err(AddrError::Invalid));
        assert_eq!(normalise_address("ftp://pc.tail.ts.net"), Err(AddrError::Invalid));
        assert_eq!(normalise_address("javascript:alert(1)"), Err(AddrError::Invalid));
    }

    #[test]
    fn pair_links() {
        let l = parse_pair_link("madalean://pair?host=pc.tail.ts.net:10500&code=123456").unwrap();
        assert_eq!(l, PairLink { host: "pc.tail.ts.net:10500".into(), code: Some("123456".into()) });
        assert_eq!(origin_key(&pair_link_origin(&l).unwrap()), "https://pc.tail.ts.net:10500");
        let l = parse_pair_link("madalean://pair?host=madalean.tail.ts.net&code=123456").unwrap();
        assert_eq!(origin_key(&pair_link_origin(&l).unwrap()), "https://madalean.tail.ts.net");
        let l = parse_pair_link("Scan: MADALEAN://pair?host=pc.tail.ts.net&code=12a456 thanks").unwrap();
        assert_eq!(l.code, None);
        assert_eq!(origin_key(&pair_link_origin(&l).unwrap()), "https://pc.tail.ts.net");
        let l = parse_pair_link("madalean://pair?host=127.0.0.1:11601&code=000001").unwrap();
        assert_eq!(origin_key(&pair_link_origin(&l).unwrap()), "http://127.0.0.1:11601");
        assert!(parse_pair_link("madalean://pair?code=123456").is_none());
        assert!(parse_pair_link("madalean://pair?host=evil.com/x&code=123456").is_none());
        assert!(parse_pair_link("madalean://pair?host=a@b.c").is_none());
        assert!(parse_pair_link("madalean://other?host=pc.tail.ts.net").is_none());
        assert!(parse_pair_link("https://pc.tail.ts.net").is_none());
        // https form of the host's QR code
        let l = parse_pair_link("https://madalean.tail804764.ts.net/pair?code=654321").unwrap();
        assert_eq!(l, PairLink { host: "madalean.tail804764.ts.net".into(), code: Some("654321".into()) });
        assert_eq!(origin_key(&pair_link_origin(&l).unwrap()), "https://madalean.tail804764.ts.net");
        assert!(parse_pair_link("https://madalean.tail.ts.net/pair?code=12").is_none());
        assert!(parse_pair_link("https://madalean.tail.ts.net/other?code=123456").is_none());
    }

    #[test]
    fn legacy_10500_migration() {
        assert_eq!(migrate_legacy_origin("https://antsa-pc.tail804764.ts.net:10500").as_deref(), Some("https://antsa-pc.tail804764.ts.net"));
        assert_eq!(migrate_legacy_origin("https://pc.example.org:10500"), None);
        assert_eq!(migrate_legacy_origin("https://pc.tail.ts.net"), None);
        assert_eq!(migrate_legacy_origin("http://127.0.0.1:10500"), None);
    }

    #[test]
    fn codes() {
        assert!(is_valid_code("012345"));
        assert!(!is_valid_code("12345"));
        assert!(!is_valid_code("1234567"));
        assert!(!is_valid_code("١٢٣٤٥٦")); // non-ASCII digits
    }

    #[test]
    fn pair_response_mapping() {
        let tok = "A".repeat(43);
        let ok = map_pair_response(200, &format!(r#"{{"token":"{tok}","device_id":"d1"}}"#), None).unwrap();
        assert_eq!(ok, (tok, Some("d1".into())));
        assert_eq!(map_pair_response(200, r#"{"token":"short"}"#, None), Err(ShellError::NotMadalean));
        assert_eq!(map_pair_response(401, r#"{"error":"bad_code"}"#, None), Err(ShellError::BadCode));
        assert_eq!(
            map_pair_response(429, r#"{"error":"locked","retry_after":600}"#, None),
            Err(ShellError::Locked { retry_after: Some(600) })
        );
        assert_eq!(map_pair_response(429, "", Some("42")), Err(ShellError::Locked { retry_after: Some(42) }));
        assert_eq!(map_pair_response(500, "", None), Err(ShellError::Server { status: 500 }));
        // Shapes of the current server (docs/API.md): 403 wrong/expired, 429 rate_limited, device object.
        assert_eq!(map_pair_response(403, r#"{"error":"expired","message":"…"}"#, None), Err(ShellError::BadCode));
        assert_eq!(
            map_pair_response(429, r#"{"error":"rate_limited"}"#, None),
            Err(ShellError::Locked { retry_after: Some(60) })
        );
        let tok = "B".repeat(43);
        let ok = map_pair_response(200, &format!(r#"{{"token":"{tok}","device":{{"id":"dv9","name":"x"}}}}"#), None).unwrap();
        assert_eq!(ok.1.as_deref(), Some("dv9"));
        assert_eq!(map_pair_response(404, "", None), Err(ShellError::NotMadalean));
    }

    #[test]
    fn origins_and_session_url() {
        let o = normalise_address("pc.tail.ts.net").unwrap();
        assert!(is_pair_page(&Url::parse("https://pc.tail.ts.net/pair?reason=auth").unwrap(), &o));
        assert!(is_pair_page(&Url::parse("https://pc.tail.ts.net:443/pair").unwrap(), &o));
        assert!(!is_pair_page(&Url::parse("https://pc.tail.ts.net/pairing").unwrap(), &o));
        assert!(!is_pair_page(&Url::parse("https://other.ts.net/pair").unwrap(), &o));
        assert!(!same_origin(&Url::parse("https://pc.tail.ts.net:10500/").unwrap(), &o));
        let s = session_url(&o, "t+k/=", "/");
        assert_eq!(s.as_str(), "https://pc.tail.ts.net/api/session?ticket=t%2Bk%2F%3D&next=%2F");
    }

    #[test]
    fn settings_roundtrip_private_file() {
        let dir = tempfile::tempdir().unwrap();
        let p = dir.path().join("sub").join("settings.json");
        let mut s = Settings::default();
        s.upsert(SavedServer { origin: "https://a.ts.net:10500".into(), host_name: "a".into(), device_name: "d".into(), last_used: 10 });
        s.upsert(SavedServer { origin: "https://b.ts.net:10500".into(), host_name: "b".into(), device_name: "d".into(), last_used: 20 });
        s.upsert(SavedServer { origin: "https://a.ts.net:10500".into(), host_name: "a2".into(), device_name: "d".into(), last_used: 30 });
        assert_eq!(s.servers.len(), 2);
        assert_eq!(s.last().unwrap().host_name, "a2");
        s.save(&p).unwrap();
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&p).unwrap().permissions().mode() & 0o777, 0o600);
            assert_eq!(std::fs::metadata(p.parent().unwrap()).unwrap().permissions().mode() & 0o777, 0o700);
        }
        let back = Settings::load(&p);
        assert_eq!(back, s);
        let mut back = back;
        assert!(back.remove("https://b.ts.net:10500"));
        assert!(!back.remove("https://b.ts.net:10500"));
        assert_eq!(Settings::load(&dir.path().join("missing.json")), Settings::default());
    }

    #[test]
    fn file_names() {
        assert_eq!(sanitize_file_name("theoreme.pdf"), "theoreme.pdf");
        assert_eq!(sanitize_file_name("../../etc/passwd"), "_.._etc_passwd");
        assert_eq!(sanitize_file_name(".hidden"), "hidden");
        assert_eq!(sanitize_file_name(""), "download");
    }

    #[test]
    fn device_names() {
        assert_eq!(default_device_name("antsa-pc"), "antsa-pc (Linux)");
        assert_eq!(default_device_name(" "), "Linux");
    }
}
