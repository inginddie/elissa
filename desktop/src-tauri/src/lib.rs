//! Elissa's native shell: a transparent, frameless, always-on-top window, tray icon, global shortcut,
//! autostart and updates. The assistant itself (agent, providers, tools, memory, voice) is the Python engine,
//! which this process starts on a free local port with a per-launch token and asks to quit on exit.

use std::io::{Read, Write};
use std::net::{TcpListener, TcpStream};
use std::path::PathBuf;
use std::process::{Child, Command, Stdio};
use std::sync::atomic::{AtomicBool, AtomicI32, Ordering};
use std::sync::Mutex;
use std::time::{Duration, Instant};

use tauri::menu::{CheckMenuItemBuilder, MenuBuilder, MenuItem, MenuItemBuilder};
use tauri::tray::{MouseButton, MouseButtonState, TrayIconBuilder, TrayIconEvent};
use tauri::{
    AppHandle, Emitter, Manager, PhysicalPosition, PhysicalSize, RunEvent, Url, WebviewUrl, WebviewWindow,
    WebviewWindowBuilder, WindowEvent,
};
use tauri::webview::{PermissionKind, PermissionResponse};
use tauri_plugin_autostart::ManagerExt;
use tauri_plugin_global_shortcut::{GlobalShortcutExt, Shortcut, ShortcutState};
use tauri_plugin_updater::{Update, UpdaterExt};

const PREFERRED_PORT: u16 = 8740;
const DEFAULT_HOTKEY: &str = "ctrl+alt+space";

/// The global shortcut currently registered (configurable in Settings).
struct Hotkey(Mutex<Option<Shortcut>>);
const MARGIN: f64 = 16.0;
const ENGINE_START_TIMEOUT: Duration = Duration::from_secs(90);
/// Before an update the engine gets this long to save the conversation; then it is stopped.
const ENGINE_QUIT_TIMEOUT: Duration = Duration::from_secs(90);
const UPDATE_FIRST_CHECK: Duration = Duration::from_secs(20);
const UPDATE_INTERVAL: Duration = Duration::from_secs(6 * 3600);

struct Engine {
    child: Mutex<Option<Child>>,
    port: u16,
    token: String,
}

/// Window position (physical px), scale and visibility, kept up to date from window events so the cursor feed
/// never has to query the window (each query wakes the UI thread).
struct Geometry {
    x: AtomicI32,
    y: AtomicI32,
    scale_milli: AtomicI32,
    visible: AtomicBool,
}

impl Geometry {
    fn set_pos(&self, x: i32, y: i32) {
        self.x.store(x, Ordering::Relaxed);
        self.y.store(y, Ordering::Relaxed);
    }
}

/// An update found by the periodic check, waiting for the user to install it from the tray or Settings.
struct Updates {
    pending: Mutex<Option<Update>>,
    tray_item: Mutex<Option<MenuItem<tauri::Wry>>>,
}

/// Where the window's bottom-right corner lives. Mode changes resize around it (clamped to the screen without
/// moving it); only a move the user makes (dragging) changes it.
struct Layout {
    anchor: Mutex<Option<(i32, i32)>>,
    ignore_moves_until: Mutex<Instant>,
}

/// Logical size of the window in each UI mode. The bottom-right corner stays put when switching.
fn mode_size(mode: &str) -> (f64, f64) {
    match mode {
        "talk" => (360.0, 330.0),
        "panel" => (400.0, 640.0),
        "approval" => (400.0, 520.0),
        _ => (168.0, 188.0), // compact: just the character
    }
}

fn free_port() -> u16 {
    if TcpListener::bind(("127.0.0.1", PREFERRED_PORT)).is_ok() {
        return PREFERRED_PORT;
    }
    TcpListener::bind(("127.0.0.1", 0))
        .and_then(|l| l.local_addr())
        .map(|a| a.port())
        .unwrap_or(PREFERRED_PORT)
}

fn engine_command(app: &AppHandle) -> Command {
    if cfg!(debug_assertions) {
        // Development: run the engine from the repository with uv.
        let root = PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("..").join("..");
        let mut cmd = Command::new("uv");
        cmd.args(["run", "python", "-m", "elissa"]).current_dir(root);
        cmd
    } else {
        let dir = app.path().resource_dir().expect("resource dir").join("engine");
        let exe = if cfg!(windows) { "elissa-engine.exe" } else { "elissa-engine" };
        let mut cmd = Command::new(dir.join(exe));
        cmd.current_dir(dir);
        cmd
    }
}

fn start_engine(app: &AppHandle, port: u16, token: &str) -> std::io::Result<Child> {
    let mut cmd = engine_command(app);
    cmd.env("ELISSA_PORT", port.to_string())
        .env("ELISSA_TOKEN", token)
        .env("ELISSA_PARENT_PID", std::process::id().to_string())
        .stdin(Stdio::null())
        .stdout(Stdio::null())
        .stderr(Stdio::null());
    #[cfg(windows)]
    {
        use std::os::windows::process::CommandExt;
        const CREATE_NO_WINDOW: u32 = 0x0800_0000;
        cmd.creation_flags(CREATE_NO_WINDOW);
    }
    cmd.spawn()
}

/// Waits for the engine to listen, then points the window at it (or tells the splash it failed).
fn connect_when_ready(app: AppHandle) {
    std::thread::spawn(move || {
        let engine = app.state::<Engine>();
        let started = Instant::now();
        let addr = ("127.0.0.1", engine.port);
        loop {
            if TcpStream::connect(addr).is_ok() {
                break;
            }
            let exited = engine
                .child
                .lock()
                .unwrap()
                .as_mut()
                .map_or(true, |c| c.try_wait().ok().flatten().is_some());
            if exited || started.elapsed() > ENGINE_START_TIMEOUT {
                let _ = app.emit("engine-failed", if exited { "exited" } else { "timeout" });
                return;
            }
            std::thread::sleep(Duration::from_millis(150));
        }
        let url = format!("http://127.0.0.1:{}/?t={}", engine.port, engine.token);
        if let Some(w) = app.get_webview_window("main") {
            let _ = w.navigate(Url::parse(&url).expect("engine url"));
        }
    });
}

/// Asks the engine to save the conversation and exit. It would also notice this process is gone, but asking
/// lets it start right away.
fn request_engine_quit(engine: &Engine) {
    if let Ok(mut stream) = TcpStream::connect_timeout(
        &([127, 0, 0, 1], engine.port).into(),
        Duration::from_secs(2),
    ) {
        let request = format!(
            "POST /api/quit HTTP/1.1\r\nHost: 127.0.0.1\r\nCookie: elissa_session={}\r\n\
             Content-Length: 0\r\nConnection: close\r\n\r\n",
            engine.token
        );
        // Wait for the answer: closing right after writing can make the server drop the request.
        if stream.write_all(request.as_bytes()).is_ok() {
            let _ = stream.set_read_timeout(Some(Duration::from_secs(3)));
            let _ = stream.read(&mut [0u8; 512]);
        }
    }
}

/// Quit: the engine finishes saving on its own after this process is gone.
fn release_engine(app: &AppHandle) {
    let engine = app.state::<Engine>();
    request_engine_quit(&engine);
    engine.child.lock().unwrap().take();
}

/// Update: the installer replaces the engine's files, so it has to be gone first.
fn stop_engine_and_wait(app: &AppHandle) {
    let engine = app.state::<Engine>();
    request_engine_quit(&engine);
    let Some(mut child) = engine.child.lock().unwrap().take() else { return };
    let started = Instant::now();
    while started.elapsed() < ENGINE_QUIT_TIMEOUT {
        if child.try_wait().ok().flatten().is_some() {
            return;
        }
        std::thread::sleep(Duration::from_millis(200));
    }
    let _ = child.kill();
    let _ = child.wait();
}

// ----- updates -----

async fn check_for_update(app: &AppHandle) -> Option<String> {
    let update = app.updater().ok()?.check().await.ok()??;
    let version = update.version.clone();
    let updates = app.state::<Updates>();
    if let Some(item) = updates.tray_item.lock().unwrap().as_ref() {
        let _ = item.set_text(format!("Instalar la versión {version}"));
    }
    *updates.pending.lock().unwrap() = Some(update);
    let _ = app.emit("update-available", &version);
    Some(version)
}

async fn install_pending_update(app: AppHandle) -> Result<(), String> {
    let update = app.state::<Updates>().pending.lock().unwrap().take().ok_or("No hay actualizaciones pendientes")?;
    let _ = app.emit("update-installing", &update.version);
    let bytes = update.download(|_, _| {}, || {}).await.map_err(|e| e.to_string())?;
    let handle = app.clone();
    tauri::async_runtime::spawn_blocking(move || stop_engine_and_wait(&handle)).await.map_err(|e| e.to_string())?;
    // On Windows this launches the installer, which closes the app and opens the new version.
    update.install(bytes).map_err(|e| e.to_string())
}

fn start_update_checks(app: AppHandle) {
    if cfg!(debug_assertions) {
        return; // development builds are not released
    }
    tauri::async_runtime::spawn(async move {
        tokio::time::sleep(UPDATE_FIRST_CHECK).await;
        loop {
            check_for_update(&app).await;
            tokio::time::sleep(UPDATE_INTERVAL).await;
        }
    });
}

fn place_bottom_right(w: &WebviewWindow, mode: &str) {
    let Ok(Some(monitor)) = w.current_monitor().or_else(|_| w.primary_monitor()) else { return };
    let area = monitor.work_area();
    let m = (MARGIN * monitor.scale_factor()) as i32;
    *w.state::<Layout>().anchor.lock().unwrap() = Some((
        area.position.x + area.size.width as i32 - m,
        area.position.y + area.size.height as i32 - m,
    ));
    apply_mode(w, mode);
}

fn apply_mode(w: &WebviewWindow, mode: &str) {
    let layout = w.state::<Layout>();
    let (Ok(pos), Ok(size), Ok(scale)) = (w.outer_position(), w.outer_size(), w.scale_factor()) else { return };
    let (ax, ay) = layout
        .anchor
        .lock()
        .unwrap()
        .unwrap_or((pos.x + size.width as i32, pos.y + size.height as i32));
    let (lw, lh) = mode_size(mode);
    let (nw, nh) = ((lw * scale) as i32, (lh * scale) as i32);
    let (mut x, mut y) = (ax - nw, ay - nh);
    if let Ok(Some(monitor)) = w.current_monitor() {
        let a = monitor.work_area();
        x = x.clamp(a.position.x, (a.position.x + a.size.width as i32 - nw).max(a.position.x));
        y = y.clamp(a.position.y, (a.position.y + a.size.height as i32 - nh).max(a.position.y));
    }
    *layout.ignore_moves_until.lock().unwrap() = Instant::now() + Duration::from_millis(500);
    let _ = w.set_size(PhysicalSize::new(nw as u32, nh as u32));
    let _ = w.set_position(PhysicalPosition::new(x, y));
    let geometry = w.state::<Geometry>();
    geometry.set_pos(x, y);
    geometry.scale_milli.store((scale * 1000.0) as i32, Ordering::Relaxed);
}

#[cfg(windows)]
fn global_cursor() -> Option<(i32, i32)> {
    use windows_sys::Win32::Foundation::POINT;
    use windows_sys::Win32::UI::WindowsAndMessaging::GetCursorPos;
    let mut p = POINT { x: 0, y: 0 };
    // SAFETY: GetCursorPos only writes the POINT we pass.
    (unsafe { GetCursorPos(&mut p) } != 0).then_some((p.x, p.y))
}

#[cfg(not(windows))]
fn global_cursor() -> Option<(i32, i32)> {
    None
}

/// Feeds the global cursor position (relative to the window, in CSS pixels) to the page, so Elissa's eyes can
/// follow it across the whole desktop. Only while the window is visible, and only when the cursor moves.
fn start_cursor_feed(app: AppHandle) {
    std::thread::spawn(move || {
        let mut last = (i32::MAX, i32::MAX);
        loop {
            std::thread::sleep(Duration::from_millis(40));
            let geometry = app.state::<Geometry>();
            if !geometry.visible.load(Ordering::Relaxed) {
                std::thread::sleep(Duration::from_millis(500));
                continue;
            }
            let Some(c) = global_cursor() else { continue };
            if c == last {
                continue;
            }
            last = c;
            let scale = geometry.scale_milli.load(Ordering::Relaxed).max(1) as f64 / 1000.0;
            let rel_x = (c.0 - geometry.x.load(Ordering::Relaxed)) as f64 / scale;
            let rel_y = (c.1 - geometry.y.load(Ordering::Relaxed)) as f64 / scale;
            let _ = app.emit_to("main", "cursor", serde_json::json!({ "x": rel_x, "y": rel_y }));
        }
    });
}

fn set_visible(app: &AppHandle, on: bool) {
    app.state::<Geometry>().visible.store(on, Ordering::Relaxed);
}

fn toggle_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        if w.is_visible().unwrap_or(false) {
            let _ = w.hide();
            set_visible(app, false);
        } else {
            let _ = w.show();
            let _ = w.set_focus();
            set_visible(app, true);
        }
    }
}

fn show_window(app: &AppHandle) {
    if let Some(w) = app.get_webview_window("main") {
        let _ = w.show();
        let _ = w.set_focus();
        set_visible(app, true);
    }
}

// ----- commands available to the engine's page -----

/// Resizes the window for a UI mode around its anchor (bottom-right corner), keeping it on screen.
#[tauri::command]
fn set_mode(window: WebviewWindow, mode: String) {
    apply_mode(&window, &mode);
}

#[tauri::command]
fn set_pinned(window: WebviewWindow, on: bool) {
    let _ = window.set_always_on_top(on);
}

#[tauri::command]
fn hide_window(window: WebviewWindow) {
    let _ = window.hide();
    set_visible(window.app_handle(), false);
}

#[tauri::command]
fn show_window_cmd(app: AppHandle) {
    show_window(&app);
}

#[tauri::command]
fn quit_app(app: AppHandle) {
    app.exit(0);
}

#[tauri::command]
fn get_autostart(app: AppHandle) -> bool {
    app.autolaunch().is_enabled().unwrap_or(false)
}

#[tauri::command]
fn set_autostart(app: AppHandle, on: bool) -> Result<bool, String> {
    let launcher = app.autolaunch();
    let result = if on { launcher.enable() } else { launcher.disable() };
    result.map_err(|e| e.to_string())?;
    Ok(launcher.is_enabled().unwrap_or(on))
}

#[tauri::command]
fn shell_info(app: AppHandle) -> serde_json::Value {
    let pending = app.state::<Updates>().pending.lock().unwrap().as_ref().map(|u| u.version.clone());
    serde_json::json!({ "version": app.package_info().version.to_string(), "update": pending })
}

#[tauri::command]
async fn install_update(app: AppHandle) -> Result<(), String> {
    install_pending_update(app).await
}

/// A Windows notification (reminders and timers, so they are seen even when Elissa is hidden).
#[tauri::command]
fn notify(app: AppHandle, title: String, body: String) -> Result<(), String> {
    use tauri_plugin_notification::NotificationExt;
    app.notification().builder().title(title).body(body).show().map_err(|e| e.to_string())
}

/// Changes the global shortcut. The new one is registered before the old one is released, so a combination another
/// app already owns leaves the current shortcut working.
#[tauri::command]
fn set_hotkey(app: AppHandle, combo: String) -> Result<String, String> {
    let new: Shortcut = combo.to_lowercase().parse().map_err(|e| format!("{e}"))?;
    let state = app.state::<Hotkey>();
    let mut current = state.0.lock().unwrap();
    if current.as_ref() == Some(&new) {
        return Ok(combo);
    }
    let shortcuts = app.global_shortcut();
    shortcuts.register(new).map_err(|e| e.to_string())?;
    if let Some(old) = current.take() {
        let _ = shortcuts.unregister(old);
    }
    *current = Some(new);
    Ok(combo)
}

#[tauri::command]
fn open_url(url: String) -> Result<(), String> {
    let parsed = Url::parse(&url).map_err(|e| e.to_string())?;
    if !matches!(parsed.scheme(), "http" | "https") {
        return Err("solo enlaces web".into());
    }
    open_in_browser(parsed.as_str())
}

#[cfg(windows)]
fn open_in_browser(url: &str) -> Result<(), String> {
    // rundll32 hands the URL to the default browser without going through a shell parser.
    Command::new("rundll32")
        .args(["url.dll,FileProtocolHandler", url])
        .spawn()
        .map(|_| ())
        .map_err(|e| e.to_string())
}

#[cfg(target_os = "macos")]
fn open_in_browser(url: &str) -> Result<(), String> {
    Command::new("open").arg(url).spawn().map(|_| ()).map_err(|e| e.to_string())
}

#[cfg(all(unix, not(target_os = "macos")))]
fn open_in_browser(url: &str) -> Result<(), String> {
    Command::new("xdg-open").arg(url).spawn().map(|_| ()).map_err(|e| e.to_string())
}

// ----- app -----

fn build_tray(app: &AppHandle) -> tauri::Result<()> {
    let show = MenuItemBuilder::with_id("toggle", "Mostrar u ocultar").build(app)?;
    let settings = MenuItemBuilder::with_id("settings", "Ajustes").build(app)?;
    let reset = MenuItemBuilder::with_id("reset", "Nueva conversación").build(app)?;
    let autostart_label = if cfg!(windows) {
        "Iniciar con Windows"
    } else if cfg!(target_os = "macos") {
        "Abrir al iniciar sesión"
    } else {
        "Iniciar con la sesión"
    };
    let autostart = CheckMenuItemBuilder::with_id("autostart", autostart_label)
        .checked(app.autolaunch().is_enabled().unwrap_or(false))
        .build(app)?;
    let update = MenuItemBuilder::with_id("update", "Buscar actualizaciones").build(app)?;
    let quit = MenuItemBuilder::with_id("quit", "Salir").build(app)?;
    let menu = MenuBuilder::new(app)
        .items(&[&show, &settings, &reset])
        .separator()
        .items(&[&autostart, &update])
        .separator()
        .item(&quit)
        .build()?;
    *app.state::<Updates>().tray_item.lock().unwrap() = Some(update.clone());
    let autostart_item = autostart.clone();
    TrayIconBuilder::with_id("main")
        .icon(app.default_window_icon().cloned().expect("icon"))
        .tooltip("Elissa")
        .menu(&menu)
        .show_menu_on_left_click(false)
        .on_menu_event(move |app, event| match event.id().as_ref() {
            "toggle" => toggle_window(app),
            "settings" | "reset" => {
                show_window(app);
                let _ = app.emit("shell-action", event.id().as_ref());
            }
            "autostart" => {
                let launcher = app.autolaunch();
                let on = !launcher.is_enabled().unwrap_or(false);
                let _ = if on { launcher.enable() } else { launcher.disable() };
                let _ = autostart_item.set_checked(launcher.is_enabled().unwrap_or(on));
            }
            "update" => {
                let app = app.clone();
                tauri::async_runtime::spawn(async move {
                    let pending = app.state::<Updates>().pending.lock().unwrap().is_some();
                    if pending || check_for_update(&app).await.is_some() {
                        show_window(&app);
                        let _ = app.emit("shell-action", "update");
                    } else {
                        let _ = app.emit("update-none", ());
                    }
                });
            }
            "quit" => app.exit(0),
            _ => {}
        })
        .on_tray_icon_event(|tray, event| {
            if let TrayIconEvent::Click { button: MouseButton::Left, button_state: MouseButtonState::Up, .. } = event {
                toggle_window(tray.app_handle());
            }
        })
        .build(app)?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    if std::env::args().any(|a| a == "--quit") && TcpStream::connect(("127.0.0.1", PREFERRED_PORT)).is_err() {
        return; // nothing running to close (best effort: a running copy on another port still gets the message)
    }
    let port = free_port();
    let token = uuid::Uuid::new_v4().simple().to_string();

    let app = tauri::Builder::default()
        // Must be first: a second launch just brings the window back.
        // `elissa.exe --quit` closes the running instance cleanly (scripts, installer).
        .plugin(tauri_plugin_single_instance::init(|app, argv, _cwd| {
            if argv.iter().any(|a| a == "--quit") {
                app.exit(0);
            } else {
                show_window(app);
            }
        }))
        .plugin(tauri_plugin_autostart::Builder::new().build())
        .plugin(tauri_plugin_updater::Builder::new().build())
        .plugin(tauri_plugin_notification::init())
        .plugin(
            tauri_plugin_global_shortcut::Builder::new()
                .with_shortcuts([DEFAULT_HOTKEY])
                .expect("shortcut")
                // Only Elissa's own shortcut is ever registered, so any press is "talk".
                .with_handler(|app, _shortcut, event| {
                    if event.state == ShortcutState::Pressed {
                        show_window(app);
                        let _ = app.emit("hotkey", ());
                    }
                })
                .build(),
        )
        .manage(Engine { child: Mutex::new(None), port, token: token.clone() })
        .manage(Layout { anchor: Mutex::new(None), ignore_moves_until: Mutex::new(Instant::now()) })
        .manage(Updates { pending: Mutex::new(None), tray_item: Mutex::new(None) })
        .manage(Hotkey(Mutex::new(DEFAULT_HOTKEY.parse().ok())))
        .manage(Geometry {
            x: AtomicI32::new(0),
            y: AtomicI32::new(0),
            scale_milli: AtomicI32::new(1000),
            visible: AtomicBool::new(false),
        })
        .invoke_handler(tauri::generate_handler![
            set_mode,
            set_pinned,
            hide_window,
            show_window_cmd,
            quit_app,
            get_autostart,
            set_autostart,
            shell_info,
            install_update,
            open_url,
            notify,
            set_hotkey
        ])
        .setup(move |app| {
            let handle = app.handle().clone();
            let window = WebviewWindowBuilder::new(app, "main", WebviewUrl::App("index.html".into()))
                .title("Elissa")
                .transparent(true)
                .decorations(false)
                .shadow(false)
                .always_on_top(true)
                .skip_taskbar(true)
                .resizable(false)
                .visible(false)
                .inner_size(168.0, 188.0)
                // Replaces Tauri's default WebView2 flags, so they are repeated here; autoplay lets her answer
                // out loud after the global shortcut, which is not a click inside the page.
                .additional_browser_args(concat!(
                    "--disable-features=msWebOOUI,msPdfOOUI,msSmartScreenProtection ",
                    "--autoplay-policy=no-user-gesture-required"
                ))
                // Only the bundled splash and this launch's engine may load in the window.
                .on_navigation(move |url| {
                    matches!(url.scheme(), "tauri")
                        || url.host_str() == Some("tauri.localhost")
                        || (url.host_str() == Some("127.0.0.1") && url.port() == Some(port))
                })
                // The microphone is granted silently, but only to this launch's engine page.
                .on_permission_request(move |webview, kind| {
                    let ours = webview
                        .url()
                        .map(|u| u.host_str() == Some("127.0.0.1") && u.port() == Some(port))
                        .unwrap_or(false);
                    match kind {
                        PermissionKind::Microphone if ours => PermissionResponse::Allow,
                        _ => PermissionResponse::Deny,
                    }
                })
                .build()?;
            place_bottom_right(&window, "compact");
            let moved = window.clone();
            window.on_window_event(move |event| {
                if let WindowEvent::CloseRequested { api, .. } = event {
                    // Alt+F4 hides the bubble; quitting is in the tray menu.
                    api.prevent_close();
                    let _ = moved.hide();
                    set_visible(moved.app_handle(), false);
                }
                if let WindowEvent::Moved(pos) = event {
                    moved.state::<Geometry>().set_pos(pos.x, pos.y);
                    let layout = moved.state::<Layout>();
                    if Instant::now() < *layout.ignore_moves_until.lock().unwrap() {
                        return; // our own resize, not the user dragging
                    }
                    if let Ok(size) = moved.outer_size() {
                        *layout.anchor.lock().unwrap() =
                            Some((pos.x + size.width as i32, pos.y + size.height as i32));
                    }
                    let _ = moved.emit("window-drag", ());
                }
            });
            window.show()?;
            set_visible(&handle, true);
            build_tray(&handle)?;

            let child = start_engine(&handle, port, &token)?;
            *handle.state::<Engine>().child.lock().unwrap() = Some(child);
            connect_when_ready(handle.clone());
            start_cursor_feed(handle.clone());
            start_update_checks(handle);
            Ok(())
        })
        .build(tauri::generate_context!())
        .expect("error while building Elissa");

    app.run(|app, event| {
        if let RunEvent::Exit = event {
            release_engine(app);
        }
    });
}
