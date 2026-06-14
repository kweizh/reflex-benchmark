import reflex as rx

class AppState(rx.State):
    def on_load(self):
        return AppState.start_polling_worker()
    
    @rx.event(background=True)
    async def start_polling_worker(self):
        pass

print(AppState.on_load(AppState()))
