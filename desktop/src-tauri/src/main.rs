#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

#[cfg(not(debug_assertions))]
use std::io::{Read, Write};
#[cfg(not(debug_assertions))]
use std::net::{TcpListener, TcpStream};
use std::sync::Mutex;
#[cfg(not(debug_assertions))]
use std::time::Duration;

use tauri::{Manager, RunEvent, State};
#[cfg(not(debug_assertions))]
use tauri_plugin_shell::ShellExt;

struct EngineState {
    port: u16,
    child: Mutex<Option<tauri_plugin_shell::process::CommandChild>>,
}

#[tauri::command]
fn engine_url(state: State<'_, EngineState>) -> String {
    format!("http://127.0.0.1:{}/api/v1", state.port)
}

#[cfg(not(debug_assertions))]
fn wait_for_engine(port: u16) -> Result<(), String> {
    for _ in 0..100 {
        if let Ok(mut stream) = TcpStream::connect(("127.0.0.1", port)) {
            stream.set_read_timeout(Some(Duration::from_millis(250))).map_err(|error| error.to_string())?;
            stream.write_all(b"GET /api/v1/health HTTP/1.0\r\nHost: 127.0.0.1\r\n\r\n").map_err(|error| error.to_string())?;
            let mut response = String::new();
            stream.read_to_string(&mut response).ok();
            if response.contains("200 OK") { return Ok(()); }
        }
        std::thread::sleep(Duration::from_millis(100));
    }
    Err("NL2SQL engine did not become ready".to_string())
}

fn main() {
    let builder = tauri::Builder::default()
        .plugin(tauri_plugin_shell::init())
        .invoke_handler(tauri::generate_handler![engine_url])
        .setup(|app| {
            #[cfg(not(debug_assertions))]
            let port = {
                let listener = TcpListener::bind("127.0.0.1:0").map_err(|error| error.to_string())?;
                let port = listener.local_addr().map_err(|error| error.to_string())?.port();
                drop(listener);
                port
            };
            #[cfg(debug_assertions)]
            let port = 47821;
            let child;
            #[cfg(not(debug_assertions))]
            {
                let sidecar = app.shell().sidecar("nl2sql-engine")?;
                let (_events, process) = sidecar.args(["--host", "127.0.0.1", "--port", &port.to_string()]).spawn()?;
                wait_for_engine(port).map_err(|error| std::io::Error::new(std::io::ErrorKind::TimedOut, error))?;
                child = Some(process);
            }
            #[cfg(debug_assertions)]
            {
                child = None;
            }
            app.manage(EngineState { port, child: Mutex::new(child) });
            Ok(())
        });
    let app = builder
        .build(tauri::generate_context!())
        .expect("error while building NL2SQL desktop application");
    app.run(|app, event| {
            if let RunEvent::ExitRequested { .. } = event {
                if let Some(state) = app.try_state::<EngineState>() {
                    if let Ok(mut child) = state.child.lock() {
                        if let Some(process) = child.take() { let _ = process.kill(); }
                    }
                }
            }
        });
}
