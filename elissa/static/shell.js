// Bridge to the native desktop shell (Tauri). In a plain browser (dev) every call is a harmless no-op.
const T = window.__TAURI__;
export const native = !!T;

const invoke = (cmd, args) => (T ? T.core.invoke(cmd, args) : Promise.resolve(null));

export const shell = {
  setMode: (mode) => invoke('set_mode', { mode }).catch(() => {}),
  setPinned: (on) => invoke('set_pinned', { on }).catch(() => {}),
  hide: () => invoke('hide_window').catch(() => {}),
  show: () => invoke('show_window_cmd').catch(() => {}),
  notify: (title, body) => invoke('notify', { title, body }).catch(() => {}),
  quit: () => invoke('quit_app'),
  getAutostart: () => invoke('get_autostart').catch(() => null),
  setAutostart: (on) => invoke('set_autostart', { on }),
  info: () => invoke('shell_info').catch(() => null),
  installUpdate: () => invoke('install_update'),
  openUrl: (url) => (T ? invoke('open_url', { url }) : Promise.resolve(window.open(url, '_blank', 'noopener'))),
  startDragging: () => T?.window.getCurrentWindow().startDragging().catch(() => {}),
  on: (event, fn) => T?.event.listen(event, (e) => fn(e.payload)),
};
