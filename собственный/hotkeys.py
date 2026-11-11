from pynput import keyboard


class HotkeyListener:
    def __init__(self, callback):
        self.callback = callback
        self.listener = None

    def on_press(self, key):
        try:
            if key.char and key.char.lower() == "m":
                self.callback()
        except AttributeError:
            pass

    def start(self):
        self.listener = keyboard.Listener(
            on_press=self.on_press
        )

        self.listener.start()

    def stop(self):
        if self.listener:
            self.listener.stop()