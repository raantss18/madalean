//! Device-token storage: OS keyring (Secret Service: GNOME Keyring, KWallet ≥ 5.97/ksecretd, KeePassXC…)
//! with a fallback file `tokens.json` (0600, directory 0700) in the app data dir when no keyring is
//! reachable. `MADALEAN_TOKEN_STORE=file|keyring` forces one backend (tests use `file`).

use crate::core::write_private_atomic;
use std::collections::BTreeMap;
use std::path::PathBuf;

const SERVICE: &str = "madalean";

pub trait TokenStore: Send + Sync {
    fn get(&self, origin: &str) -> Result<Option<String>, String>;
    fn set(&self, origin: &str, token: &str) -> Result<(), String>;
    fn delete(&self, origin: &str) -> Result<(), String>;
    fn backend(&self) -> &'static str;
}

/// Fallback: JSON map origin → token in a private file.
pub struct FileStore {
    pub path: PathBuf,
}

impl FileStore {
    fn read(&self) -> BTreeMap<String, String> {
        std::fs::read_to_string(&self.path)
            .ok()
            .and_then(|s| serde_json::from_str(&s).ok())
            .unwrap_or_default()
    }
    fn write(&self, m: &BTreeMap<String, String>) -> Result<(), String> {
        if m.is_empty() {
            return match std::fs::remove_file(&self.path) {
                Ok(()) => Ok(()),
                Err(e) if e.kind() == std::io::ErrorKind::NotFound => Ok(()),
                Err(e) => Err(e.to_string()),
            };
        }
        write_private_atomic(&self.path, serde_json::to_string(m).unwrap_or_default().as_bytes()).map_err(|e| e.to_string())
    }
}

impl TokenStore for FileStore {
    fn get(&self, origin: &str) -> Result<Option<String>, String> {
        Ok(self.read().get(origin).cloned())
    }
    fn set(&self, origin: &str, token: &str) -> Result<(), String> {
        let mut m = self.read();
        m.insert(origin.to_string(), token.to_string());
        self.write(&m)
    }
    fn delete(&self, origin: &str) -> Result<(), String> {
        let mut m = self.read();
        if m.remove(origin).is_some() {
            self.write(&m)?;
        }
        Ok(())
    }
    fn backend(&self) -> &'static str {
        "file"
    }
}

/// OS keyring through the `keyring` crate (Secret Service D-Bus API on Linux).
pub struct KeyringStore;

impl KeyringStore {
    fn entry(origin: &str) -> Result<keyring::Entry, String> {
        keyring::Entry::new(SERVICE, origin).map_err(|e| e.to_string())
    }
    /// True if a Secret Service answers (does not create anything).
    pub fn available() -> bool {
        match keyring::Entry::new(SERVICE, "madalean-probe") {
            Ok(e) => !matches!(e.get_password(), Err(keyring::Error::PlatformFailure(_)) | Err(keyring::Error::NoStorageAccess(_))),
            Err(_) => false,
        }
    }
}

impl TokenStore for KeyringStore {
    fn get(&self, origin: &str) -> Result<Option<String>, String> {
        match Self::entry(origin)?.get_password() {
            Ok(t) => Ok(Some(t)),
            Err(keyring::Error::NoEntry) => Ok(None),
            Err(e) => Err(e.to_string()),
        }
    }
    fn set(&self, origin: &str, token: &str) -> Result<(), String> {
        Self::entry(origin)?.set_password(token).map_err(|e| e.to_string())
    }
    fn delete(&self, origin: &str) -> Result<(), String> {
        match Self::entry(origin)?.delete_credential() {
            Ok(()) | Err(keyring::Error::NoEntry) => Ok(()),
            Err(e) => Err(e.to_string()),
        }
    }
    fn backend(&self) -> &'static str {
        "keyring"
    }
}

/// Keyring first, file as fallback. Reads look in both (a token saved while the keyring was
/// unavailable stays usable); writes go to the keyring when it works, and then remove any file copy.
pub struct AutoStore {
    pub keyring: Option<KeyringStore>,
    pub file: FileStore,
}

impl AutoStore {
    pub fn new(file_path: PathBuf) -> AutoStore {
        let forced = std::env::var("MADALEAN_TOKEN_STORE").unwrap_or_default();
        let keyring = match forced.as_str() {
            "file" => None,
            "keyring" => Some(KeyringStore),
            _ => KeyringStore::available().then_some(KeyringStore),
        };
        AutoStore { keyring, file: FileStore { path: file_path } }
    }
}

impl TokenStore for AutoStore {
    fn get(&self, origin: &str) -> Result<Option<String>, String> {
        if let Some(k) = &self.keyring {
            if let Ok(Some(t)) = k.get(origin) {
                return Ok(Some(t));
            }
        }
        self.file.get(origin)
    }
    fn set(&self, origin: &str, token: &str) -> Result<(), String> {
        if let Some(k) = &self.keyring {
            if k.set(origin, token).is_ok() {
                let _ = self.file.delete(origin);
                return Ok(());
            }
        }
        self.file.set(origin, token)
    }
    fn delete(&self, origin: &str) -> Result<(), String> {
        let k = self.keyring.as_ref().map(|k| k.delete(origin)).unwrap_or(Ok(()));
        let f = self.file.delete(origin);
        k.and(f)
    }
    fn backend(&self) -> &'static str {
        if self.keyring.is_some() {
            "keyring"
        } else {
            "file"
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn file_store_roundtrip_and_permissions() {
        let dir = tempfile::tempdir().unwrap();
        let s = FileStore { path: dir.path().join("data").join("tokens.json") };
        assert_eq!(s.get("https://a:10500").unwrap(), None);
        s.set("https://a:10500", "tokA").unwrap();
        s.set("https://b:10500", "tokB").unwrap();
        assert_eq!(s.get("https://a:10500").unwrap().as_deref(), Some("tokA"));
        #[cfg(unix)]
        {
            use std::os::unix::fs::PermissionsExt;
            assert_eq!(std::fs::metadata(&s.path).unwrap().permissions().mode() & 0o777, 0o600);
        }
        s.delete("https://a:10500").unwrap();
        assert_eq!(s.get("https://a:10500").unwrap(), None);
        assert_eq!(s.get("https://b:10500").unwrap().as_deref(), Some("tokB"));
        s.delete("https://b:10500").unwrap();
        assert!(!s.path.exists(), "empty store leaves no file behind");
        s.delete("https://nothing:1").unwrap();
    }

    #[test]
    fn auto_store_without_keyring_uses_file() {
        let dir = tempfile::tempdir().unwrap();
        let s = AutoStore { keyring: None, file: FileStore { path: dir.path().join("tokens.json") } };
        assert_eq!(s.backend(), "file");
        s.set("o", "t").unwrap();
        assert_eq!(s.get("o").unwrap().as_deref(), Some("t"));
        s.delete("o").unwrap();
        assert_eq!(s.get("o").unwrap(), None);
    }

    /// Talks to the real Secret Service of the session: run explicitly
    /// (`cargo test -- --ignored keyring`) inside a throw-away D-Bus session with a keyring daemon.
    #[test]
    #[ignore]
    fn keyring_roundtrip() {
        let k = KeyringStore;
        let o = "madalean-test://roundtrip";
        k.set(o, "secret-value").unwrap();
        assert_eq!(k.get(o).unwrap().as_deref(), Some("secret-value"));
        k.delete(o).unwrap();
        assert_eq!(k.get(o).unwrap(), None);
    }
}
