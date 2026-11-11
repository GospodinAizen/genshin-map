"""Global hotkeys are forwarded to Qt through a thread-safe signal."""
from PySide6.QtCore import QObject, Signal
from pynput import keyboard


class HotkeyBridge(QObject):
    toggle_overlay = Signal()


class HotkeyListener:
    def __init__(self, callback) -> None:
        self.bridge = HotkeyBridge()
        self.bridge.toggle_overlay.connect(callback)
        self.listener = None

    def on_press(self, key) -> None:
        try:
            if key.char and key.char.lower() == "m":
                self.bridge.toggle_overlay.emit()
        except AttributeError:
            pass

    def start(self) -> None:
        if self.listener is None:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener.join(timeout=2)
            self.listener = None
