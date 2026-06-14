import reflex as rx

class AppState(rx.State):
    _worker_started: bool = False

    def test(self):
        AppState._worker_started = True
        return AppState._worker_started

print(AppState._worker_started)
