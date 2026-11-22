"""Starts Community Manager and opens it in the web browser.

This is what the Windows shortcut runs. Close the black window to stop the app.
"""
import os
import socket
import sys
import threading
import time
import webbrowser

from community_manager import __version__, config, create_app

PREFERRED_PORT = 5055


def pick_port(preferred):
    for port in (preferred, 0):
        with socket.socket() as s:
            try:
                s.bind(("127.0.0.1", port))
                return s.getsockname()[1]
            except OSError:
                continue
    raise RuntimeError("No free port")


def already_running(port):
    with socket.socket() as s:
        s.settimeout(0.3)
        return s.connect_ex(("127.0.0.1", port)) == 0


def main():
    port = int(os.environ.get("COMMUNITY_PORT", PREFERRED_PORT))
    url = f"http://127.0.0.1:{port}/"
    if already_running(port):
        # A second click on the shortcut just opens the browser again.
        webbrowser.open(url)
        return
    port = pick_port(port)
    url = f"http://127.0.0.1:{port}/"
    demo = "--demo" in sys.argv
    if demo:
        # Separate folder so sample data never mixes with real records.
        os.environ["COMMUNITY_DATA_DIR"] = str(config.data_dir() / "demo")
    app = create_app({"DEMO": demo})
    if demo:
        from community_manager import db as database
        from community_manager.demo import load
        conn = database.connect(app.config["DATABASE"])
        try:
            load(conn)
        finally:
            conn.close()

    if sys.platform == "win32":
        os.system(f"title {config.APP_NAME}")
    print("=" * 60)
    print(f"  {config.APP_NAME} v{__version__} is running{' (DEMO DATA)' if demo else ''}")
    print(f"  Open in your browser: {url}")
    print(f"  Data folder: {config.data_dir()}")
    print()
    print("  Keep this window open while you use the app")
    print("  (you can minimise it). Close it to stop the app.")
    print("=" * 60)
    if "--no-browser" not in sys.argv:
        threading.Thread(target=lambda: (time.sleep(1.2), webbrowser.open(url)), daemon=True).start()

    try:
        from waitress import serve
        serve(app, host="127.0.0.1", port=port, threads=4)
    except ImportError:
        app.run(host="127.0.0.1", port=port)


if __name__ == "__main__":
    main()
