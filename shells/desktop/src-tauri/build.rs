use std::path::PathBuf;

/// Ed25519 public key of the update channel (32 bytes, base64), embedded at build time:
/// `MADALEAN_UPDATE_PUBKEY`, else `PUBLIC_KEY = bytes.fromhex("…")` of madalean/update_checkers/selfupdate.py (the
/// single source of truth; the private key file is never read — it may be encrypted). Without either, the updater is
/// compiled disabled (build_appimage.sh refuses that for releases).
fn update_pubkey() -> String {
    println!("cargo:rerun-if-env-changed=MADALEAN_UPDATE_PUBKEY");
    if let Ok(k) = std::env::var("MADALEAN_UPDATE_PUBKEY") {
        return k.trim().to_string();
    }
    let src = PathBuf::from(std::env::var("CARGO_MANIFEST_DIR").unwrap_or_default())
        .join("../../../madalean/update_checkers/selfupdate.py");
    println!("cargo:rerun-if-changed={}", src.display());
    let Ok(text) = std::fs::read_to_string(&src) else { return String::new() };
    let Some(pos) = text.find("PUBLIC_KEY = bytes.fromhex(\"") else { return String::new() };
    let hex: String = text[pos + 28..].chars().take(64).collect();
    if hex.len() != 64 || !hex.chars().all(|c| c.is_ascii_hexdigit()) {
        return String::new();
    }
    let raw: Vec<u8> = (0..32).map(|i| u8::from_str_radix(&hex[2 * i..2 * i + 2], 16).unwrap_or(0)).collect();
    // base64 by hand (no build dependency).
    const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
    let mut s = String::new();
    for c in raw.chunks(3) {
        let n = (c[0] as u32) << 16 | (*c.get(1).unwrap_or(&0) as u32) << 8 | *c.get(2).unwrap_or(&0) as u32;
        for i in 0..4 {
            if i <= c.len() {
                s.push(T[(n >> (18 - 6 * i) & 63) as usize] as char);
            } else {
                s.push('=');
            }
        }
    }
    s
}

fn main() {
    println!("cargo:rustc-env=MADALEAN_UPDATE_PUBKEY={}", update_pubkey());
    // Declare the app commands so that capabilities/default.json can grant them to the local origin only.
    tauri_build::try_build(tauri_build::Attributes::new().app_manifest(
        tauri_build::AppManifest::new().commands(&[
            "init_state",
            "probe_local",
            "connect",
            "pair",
            "parse_link",
            "forget",
            "set_lang",
            "update_status",
            "set_auto_update",
            "check_updates_now",
            "restart_now",
        ]),
    ))
    .expect("tauri build");
}
