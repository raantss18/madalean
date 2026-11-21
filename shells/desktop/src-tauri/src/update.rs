//! Signed self-update of the AppImage (docs/SHELLS.md, "Updates").
//!
//! Channel: `stable.json` + `stable.json.sig` (base64 Ed25519 signature of the exact bytes of the JSON, made with the
//! release key kept outside git; public key embedded at build time by build.rs). The manifest is verified BEFORE
//! anything is downloaded; the AppImage is then downloaded next to the running one, checked (size + SHA-256),
//! made executable, the running file is kept as `<name>.previous` (hard link, rollback) and the new one is renamed
//! over it atomically. The new version runs at the next start, or when the shell restarts itself at a quiet moment.
//! Never a downgrade, never an unsigned or mis-signed manifest.

use serde::{Deserialize, Serialize};
use sha2::{Digest, Sha256};
use std::cmp::Ordering;
use std::path::{Path, PathBuf};

pub const DEFAULT_CHANNEL: &str = "https://raantss18.github.io/madalean/updates/stable.json";
pub const CHECK_EVERY_SECS: u64 = 12 * 3600;
/// Refuse absurd files (the AppImage is ~100 MB).
pub const MAX_SIZE: u64 = 600 * 1024 * 1024;

pub fn embedded_pubkey() -> Option<[u8; 32]> {
    use base64::Engine;
    let b = base64::engine::general_purpose::STANDARD.decode(env!("MADALEAN_UPDATE_PUBKEY")).ok()?;
    b.try_into().ok()
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FileEntry {
    pub name: String,
    pub url: String,
    pub sha256: String,
    pub size: u64,
    pub kind: String,
}

#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Manifest {
    #[serde(default)]
    pub channel: String,
    pub version: String,
    #[serde(default)]
    pub published: String,
    #[serde(default)]
    pub notes_url: String,
    #[serde(default)]
    pub min_version: String,
    pub files: Vec<FileEntry>,
}

#[derive(Debug, Clone, Copy, PartialEq, Eq, Serialize)]
#[serde(rename_all = "snake_case")]
pub enum UpdError {
    NoKey,
    Unsigned,
    BadSignature,
    BadChannel,
    BadManifest,
    NoFile,
    Network,
    Size,
    Checksum,
    NotWritable,
}

/// Numeric dotted version compare; a pre-release suffix (`2.0.0-rc1`) sorts before the release.
pub fn cmp_versions(a: &str, b: &str) -> Ordering {
    fn split(v: &str) -> (Vec<u64>, bool) {
        let v = v.trim().trim_start_matches('v');
        let (core, pre) = match v.split_once(['-', '+']) {
            Some((c, _)) => (c, true),
            None => (v, false),
        };
        (core.split('.').map(|p| p.parse().unwrap_or(0)).collect(), pre)
    }
    let (mut x, xp) = split(a);
    let (mut y, yp) = split(b);
    let n = x.len().max(y.len());
    x.resize(n, 0);
    y.resize(n, 0);
    x.cmp(&y).then(match (xp, yp) {
        (true, false) => Ordering::Less,
        (false, true) => Ordering::Greater,
        _ => Ordering::Equal,
    })
}

/// Expected `channel` field = base name of the requested file (`…/stable.json` → `stable`).
pub fn channel_name(url: &str) -> String {
    url.rsplit('/').next().unwrap_or("").trim_end_matches(".json").to_string()
}

/// Verify the signature of the exact manifest bytes, then parse and check it.
pub fn verify_manifest(bytes: &[u8], sig_text: Option<&str>, pubkey: Option<[u8; 32]>, expected_channel: &str) -> Result<Manifest, UpdError> {
    use base64::Engine;
    let key = pubkey.ok_or(UpdError::NoKey)?;
    let sig_text = sig_text.ok_or(UpdError::Unsigned)?;
    let compact: String = sig_text.split_whitespace().collect();
    let sig = base64::engine::general_purpose::STANDARD.decode(compact).map_err(|_| UpdError::BadSignature)?;
    let pk = ed25519_compact::PublicKey::from_slice(&key).map_err(|_| UpdError::NoKey)?;
    let sig = ed25519_compact::Signature::from_slice(&sig).map_err(|_| UpdError::BadSignature)?;
    pk.verify(bytes, &sig).map_err(|_| UpdError::BadSignature)?;
    let m: Manifest = serde_json::from_slice(bytes).map_err(|_| UpdError::BadManifest)?;
    if m.channel != expected_channel {
        return Err(UpdError::BadChannel);
    }
    if m.version.trim().is_empty() {
        return Err(UpdError::BadManifest);
    }
    Ok(m)
}

/// The AppImage of a manifest (x86_64).
pub fn pick_appimage(m: &Manifest) -> Result<FileEntry, UpdError> {
    let f = m
        .files
        .iter()
        .find(|f| f.kind == "appimage" && f.name.to_lowercase().ends_with(".appimage"))
        .cloned()
        .ok_or(UpdError::NoFile)?;
    let hex_ok = f.sha256.len() == 64 && f.sha256.bytes().all(|b| b.is_ascii_hexdigit());
    let name_ok = !f.name.contains('/') && !f.name.contains('\\') && !f.name.starts_with('.');
    if !hex_ok || !name_ok || f.size == 0 || f.size > MAX_SIZE || !(f.url.starts_with("https://") || is_loopback_http(&f.url)) {
        return Err(UpdError::BadManifest);
    }
    Ok(f)
}

/// http:// is accepted only to loopback (local test channels); everything real is https.
pub fn is_loopback_http(url: &str) -> bool {
    url::Url::parse(url)
        .ok()
        .filter(|u| u.scheme() == "http")
        .and_then(|u| u.host_str().map(|h| matches!(h, "127.0.0.1" | "localhost" | "[::1]")))
        .unwrap_or(false)
}

pub fn sha256_file(p: &Path) -> std::io::Result<String> {
    use std::io::Read;
    let mut f = std::fs::File::open(p)?;
    let mut h = Sha256::new();
    let mut buf = vec![0u8; 1 << 16];
    loop {
        let n = f.read(&mut buf)?;
        if n == 0 {
            break;
        }
        h.update(&buf[..n]);
    }
    Ok(hex(&h.finalize()))
}

pub fn hex(b: &[u8]) -> String {
    b.iter().map(|x| format!("{x:02x}")).collect()
}

/// Swap a verified download in place of the running AppImage, keeping the old one as `<target>.previous`.
pub fn swap_in(download: &Path, target: &Path) -> std::io::Result<PathBuf> {
    #[cfg(unix)]
    {
        use std::os::unix::fs::PermissionsExt;
        std::fs::set_permissions(download, std::fs::Permissions::from_mode(0o755))?;
    }
    let mut prev = target.as_os_str().to_owned();
    prev.push(".previous");
    let prev = PathBuf::from(prev);
    let _ = std::fs::remove_file(&prev);
    if std::fs::hard_link(target, &prev).is_err() {
        std::fs::copy(target, &prev)?;
    }
    std::fs::rename(download, target)?;
    Ok(prev)
}

#[cfg(test)]
mod tests {
    use super::*;

    fn keypair() -> ed25519_compact::KeyPair {
        ed25519_compact::KeyPair::from_seed(ed25519_compact::Seed::new([7u8; 32]))
    }
    fn sign(kp: &ed25519_compact::KeyPair, b: &[u8]) -> String {
        use base64::Engine;
        base64::engine::general_purpose::STANDARD.encode(kp.sk.sign(b, None).as_ref()) + "\n"
    }
    fn manifest(channel: &str, version: &str) -> Vec<u8> {
        format!(
            r#"{{"channel":"{channel}","version":"{version}","published":"2026-11-21","notes_url":"","min_version":"","files":[
            {{"name":"Madalean-{version}-x86_64.AppImage","url":"https://github.com/x/y/Madalean.AppImage","sha256":"{}","size":10,"kind":"appimage"}},
            {{"name":"madalean-universal-release.apk","url":"https://github.com/x/y/a.apk","sha256":"{}","size":10,"kind":"apk"}}]}}"#,
            "a".repeat(64),
            "b".repeat(64)
        )
        .into_bytes()
    }

    #[test]
    fn signature_and_channel() {
        let kp = keypair();
        let pk: [u8; 32] = kp.pk.as_ref().try_into().unwrap();
        let m = manifest("stable", "2.0.1");
        let sig = sign(&kp, &m);
        let ok = verify_manifest(&m, Some(&sig), Some(pk), "stable").unwrap();
        assert_eq!(ok.version, "2.0.1");
        assert_eq!(pick_appimage(&ok).unwrap().name, "Madalean-2.0.1-x86_64.AppImage");
        // tampered bytes (one space added)
        let mut t = m.clone();
        t.insert(1, b' ');
        assert_eq!(verify_manifest(&t, Some(&sig), Some(pk), "stable"), Err(UpdError::BadSignature));
        // missing / garbage / other-key signature
        assert_eq!(verify_manifest(&m, None, Some(pk), "stable"), Err(UpdError::Unsigned));
        assert_eq!(verify_manifest(&m, Some("not base64!"), Some(pk), "stable"), Err(UpdError::BadSignature));
        let other = ed25519_compact::KeyPair::from_seed(ed25519_compact::Seed::new([9u8; 32]));
        assert_eq!(verify_manifest(&m, Some(&sign(&other, &m)), Some(pk), "stable"), Err(UpdError::BadSignature));
        // a manifest signed for the test channel is refused on stable
        let tm = manifest("test", "9.9.9");
        assert_eq!(verify_manifest(&tm, Some(&sign(&kp, &tm)), Some(pk), "stable"), Err(UpdError::BadChannel));
        assert_eq!(verify_manifest(&m, Some(&sig), None, "stable"), Err(UpdError::NoKey));
    }

    #[test]
    fn versions() {
        assert_eq!(cmp_versions("2.0.1", "2.0.0"), Ordering::Greater);
        assert_eq!(cmp_versions("2.0.0", "2.0.0"), Ordering::Equal);
        assert_eq!(cmp_versions("v2.0", "2.0.0"), Ordering::Equal);
        assert_eq!(cmp_versions("1.9.9", "2.0.0"), Ordering::Less);
        assert_eq!(cmp_versions("2.0.0-rc1", "2.0.0"), Ordering::Less);
        assert_eq!(cmp_versions("2.10.0", "2.9.0"), Ordering::Greater);
        assert_eq!(channel_name("https://h/madalean/updates/stable.json"), "stable");
        assert_eq!(channel_name("http://127.0.0.1:8/test.json"), "test");
    }

    #[test]
    fn file_checks() {
        let mut m: Manifest = serde_json::from_slice(&manifest("stable", "2.0.1")).unwrap();
        m.files[0].url = "http://evil.example/x.AppImage".into();
        assert_eq!(pick_appimage(&m), Err(UpdError::BadManifest));
        m.files[0].url = "http://127.0.0.1:9/x.AppImage".into();
        assert!(pick_appimage(&m).is_ok());
        m.files[0].name = "../x.AppImage".into();
        assert_eq!(pick_appimage(&m), Err(UpdError::BadManifest));
        m.files.remove(0);
        assert_eq!(pick_appimage(&m), Err(UpdError::NoFile));
    }

    #[test]
    fn swap_keeps_previous() {
        let d = tempfile::tempdir().unwrap();
        let target = d.path().join("Madalean.AppImage");
        std::fs::write(&target, b"old").unwrap();
        let dl = d.path().join(".Madalean.AppImage.download");
        std::fs::write(&dl, b"new").unwrap();
        let prev = swap_in(&dl, &target).unwrap();
        assert_eq!(std::fs::read(&target).unwrap(), b"new");
        assert_eq!(std::fs::read(&prev).unwrap(), b"old");
        assert!(!dl.exists());
        assert_eq!(sha256_file(&target).unwrap(), hex(&Sha256::digest(b"new")));
    }
}
