#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use tauri_plugin_shell::ShellExt;

fn main() {
    tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .setup(|app| {
            #[cfg(not(debug_assertions))]
            {
                let sidecar = app.shell().sidecar("nl2sql-engine")?;
                let _child = sidecar.args(["--port", "47821"]).spawn()?;
            }
            Ok(())
        })
        .run(tauri::generate_context!())
        .expect("error while running NL2SQL desktop application");
}
