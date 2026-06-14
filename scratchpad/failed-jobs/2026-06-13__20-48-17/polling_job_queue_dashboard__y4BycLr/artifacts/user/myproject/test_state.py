class AppState:
    _worker_started: bool = False

    def test(self):
        if AppState._worker_started:
            return
        AppState._worker_started = True

s1 = AppState()
s2 = AppState()
s1.test()
print(s2._worker_started)
print(AppState._worker_started)
