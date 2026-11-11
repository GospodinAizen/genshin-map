"""Global hotkeys are forwarded to Qt through thread-safe signals."""
from PySide6.QtCore import QObject, Signal
from pynput import keyboard


class HotkeyBridge(QObject):
    toggle_overlay = Signal()
    toggle_panel = Signal()


class HotkeyListener:
    def __init__(self, overlay_callback, panel_callback) -> None:
        self.bridge = HotkeyBridge()
        self.bridge.toggle_overlay.connect(overlay_callback)
        self.bridge.toggle_panel.connect(panel_callback)
        self.listener = None

    def on_press(self, key) -> None:
        try:
            if key.char and key.char.lower() == "m":
                self.bridge.toggle_overlay.emit()
                return
        except AttributeError:
            pass
        if key == keyboard.Key.f6:
            self.bridge.toggle_panel.emit()

    def start(self) -> None:
        if self.listener is None:
            self.listener = keyboard.Listener(on_press=self.on_press)
            self.listener.start()

    def stop(self) -> None:
        if self.listener is not None:
            self.listener.stop()
            self.listener.join(timeout=2)
            self.listener = None
