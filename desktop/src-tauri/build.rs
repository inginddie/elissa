// Commands are declared in an app manifest so the ACL can grant them to the engine's page (a "remote" origin).
const COMMANDS: &[&str] = &[
    "set_mode", "set_pinned", "hide_window", "quit_app", "get_autostart", "set_autostart", "shell_info", "install_update", "open_url",
];

fn main() {
    tauri_build::try_build(
        tauri_build::Attributes::new()
            .app_manifest(tauri_build::AppManifest::new().commands(COMMANDS)),
    )
    .expect("failed to run tauri-build");
}
