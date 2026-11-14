from pynput import keyboard


class HotkeyListener:
    """Global shortcuts: M toggles the overlay, F6 toggles its control panel."""
    def __init__(self, overlay_callback, panel_callback=None):
        self.overlay_callback = overlay_callback
        self.panel_callback = panel_callback or (lambda: None)
        self.listener = None

    def on_press(self, key):
        try:
            if key.char and key.char.lower() == "m":
                self.overlay_callback()
        except AttributeError:
            if key == keyboard.Key.f6:
                self.panel_callback()

    def start(self):
        self.listener = keyboard.Listener(on_press=self.on_press)
        self.listener.start()

    def stop(self):
        if self.listener is not None:
            self.listener.stop()
            self.listener.join(timeout=2)
            self.listener = None
