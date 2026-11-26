"""Runs Community Manager inside an Android app.

The same Flask app as the Windows version runs on a local server inside the
app, and a full-screen web view shows it. Saving files (backups, Excel
exports) and choosing a backup to restore use Android's own file screens.
"""
import asyncio
import os
import socket
import threading

import toga
from toga.style import Pack

PREFERRED_PORT = 5055


def free_port(preferred=PREFERRED_PORT):
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("No free port")


class CommunityApp(toga.App):
    def startup(self):
        start_path, demo = self._launch_options()
        data_dir = self.paths.data / "demo" if demo else self.paths.data
        data_dir.mkdir(parents=True, exist_ok=True)
        os.environ["COMMUNITY_DATA_DIR"] = str(data_dir)

        from community_manager import create_app, db
        from waitress import create_server

        from .native import AndroidFiles

        flask_app = create_app({"NATIVE": AndroidFiles(self), "DEMO": demo})
        if demo:
            from community_manager.demo import load
            conn = db.connect(flask_app.config["DATABASE"])
            try:
                load(conn)
            finally:
                conn.close()
        port = free_port()
        self.server = create_server(flask_app, host="127.0.0.1", port=port, threads=4)
        threading.Thread(target=self.server.run, daemon=True).start()

        self.webview = toga.WebView(url=f"http://127.0.0.1:{port}{start_path}", style=Pack(flex=1))
        self.main_window = toga.MainWindow(title=self.formal_name)
        self.main_window.content = self.webview
        self.main_window.show()
        self._handle_back_button()

    def _launch_options(self):
        """Optional extras on the launch intent, used for automated testing:
        `path` opens a given page and `demo` uses the sample data."""
        try:
            intent = self._impl.native.getIntent()
            path = intent.getStringExtra("path") or "/"
            return (path if path.startswith("/") else "/"), intent.getBooleanExtra("demo", False)
        except Exception:
            return "/", False

    def _handle_back_button(self):
        """Make the phone's Back button go back a page instead of closing the app."""
        try:
            from .native import install_back_handler
            install_back_handler(self, self.webview._impl.native)
        except Exception as exc:  # pragma: no cover - only on Android
            print(f"Back button handler not installed: {exc}")

    def run_on_ui(self, coro):
        """Run a coroutine on the app's main thread from a web-server thread."""
        return asyncio.run_coroutine_threadsafe(coro, self.loop).result()


def main():
    return CommunityApp("Community Manager", "org.ambesh.community_app")
