fn main() {
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
        ]),
    ))
    .expect("tauri build");
}
