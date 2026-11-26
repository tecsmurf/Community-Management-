"""Android pieces: file save/open screens and the Back button.

Uses Android's Storage Access Framework, so no storage permissions are
needed: the person picks where a file goes (Drive, Downloads, ...) and which
backup file to restore.
"""
import asyncio
import os
import shutil

from android.app import Activity
from android.content import Intent
from android.os import Build
from java import dynamic_proxy


class AndroidFiles:
    """The NATIVE object the web app calls for saving and opening files."""

    def __init__(self, app):
        self.app = app

    @property
    def activity(self):
        return self.app._impl.native

    async def _run_intent(self, intent):
        done = asyncio.get_running_loop().create_future()

        def on_complete(code, data):
            if not done.done():
                done.set_result((code, data))

        self.app._impl.start_activity(intent, on_complete=on_complete)
        code, data = await done
        if code != Activity.RESULT_OK or data is None or data.getData() is None:
            return None
        return data.getData()

    def _open_fd(self, uri, mode):
        resolver = self.activity.getContentResolver()
        pfd = resolver.openFileDescriptor(uri, mode)
        return os.fdopen(pfd.detachFd(), "wb" if "w" in mode else "rb")

    # Called from a web-server thread; each waits for the person to finish.
    def save_file(self, path, filename, mime):
        async def run():
            intent = Intent(Intent.ACTION_CREATE_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType(mime)
            intent.putExtra(Intent.EXTRA_TITLE, filename)
            uri = await self._run_intent(intent)
            if uri is None:
                return False
            with open(path, "rb") as src, self._open_fd(uri, "wt") as dst:
                shutil.copyfileobj(src, dst)
            return True

        return self.app.run_on_ui(run())

    def pick_file(self, target):
        async def run():
            intent = Intent(Intent.ACTION_OPEN_DOCUMENT)
            intent.addCategory(Intent.CATEGORY_OPENABLE)
            intent.setType("*/*")
            uri = await self._run_intent(intent)
            if uri is None:
                return False
            with self._open_fd(uri, "r") as src, open(target, "wb") as dst:
                shutil.copyfileobj(src, dst)
            return True

        return self.app.run_on_ui(run())


def install_back_handler(app, webview):
    """Back goes to the previous page; on the first page it leaves the app."""
    activity = app._impl.native

    def go_back():
        if webview.canGoBack():
            webview.goBack()
        else:
            activity.moveTaskToBack(True)

    if Build.VERSION.SDK_INT >= 33:
        from android.window import OnBackInvokedCallback, OnBackInvokedDispatcher

        class BackCallback(dynamic_proxy(OnBackInvokedCallback)):
            def onBackInvoked(self):
                go_back()

        app._back_callback = BackCallback()  # keep a reference
        activity.getOnBackInvokedDispatcher().registerOnBackInvokedCallback(
            OnBackInvokedDispatcher.PRIORITY_DEFAULT, app._back_callback)
    else:
        from android.view import KeyEvent, View

        class BackKey(dynamic_proxy(View.OnKeyListener)):
            def onKey(self, view, code, event):
                if code != KeyEvent.KEYCODE_BACK:
                    return False
                if event.getAction() == KeyEvent.ACTION_UP:
                    go_back()
                return True

        app._back_callback = BackKey()
        webview.setOnKeyListener(app._back_callback)
