use std::path::PathBuf;
use std::process::Command;

/// Ed25519 public key of the update channel (32 bytes), embedded at build time:
/// `MADALEAN_UPDATE_PUBKEY` (base64), else derived from the private release key kept outside git
/// (`~/.config/madalean/release-keys/ed25519.pem`, or `MADALEAN_RELEASE_KEY`) with openssl.
/// Without either, the updater is compiled disabled (development builds only; build_appimage.sh refuses).
fn update_pubkey() -> String {
    println!("cargo:rerun-if-env-changed=MADALEAN_UPDATE_PUBKEY");
    println!("cargo:rerun-if-env-changed=MADALEAN_RELEASE_KEY");
    if let Ok(k) = std::env::var("MADALEAN_UPDATE_PUBKEY") {
        return k.trim().to_string();
    }
    let key = std::env::var("MADALEAN_RELEASE_KEY").map(PathBuf::from).unwrap_or_else(|_| {
        PathBuf::from(std::env::var("HOME").unwrap_or_default()).join(".config/madalean/release-keys/ed25519.pem")
    });
    if !key.is_file() {
        return String::new();
    }
    println!("cargo:rerun-if-changed={}", key.display());
    let out = Command::new("openssl").args(["pkey", "-pubout", "-outform", "DER", "-in"]).arg(&key).output();
    match out {
        Ok(o) if o.status.success() && o.stdout.len() >= 32 => {
            use std::fmt::Write;
            let raw = &o.stdout[o.stdout.len() - 32..];
            // base64 by hand (no build dependency).
            const T: &[u8; 64] = b"ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
            let mut s = String::new();
            for c in raw.chunks(3) {
                let n = (c[0] as u32) << 16 | (*c.get(1).unwrap_or(&0) as u32) << 8 | *c.get(2).unwrap_or(&0) as u32;
                for i in 0..4 {
                    if i <= c.len() {
                        let _ = write!(s, "{}", T[(n >> (18 - 6 * i) & 63) as usize] as char);
                    } else {
                        s.push('=');
                    }
                }
            }
            s
        }
        _ => String::new(),
    }
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
