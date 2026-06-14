import reflex as rx

def api_transformer(app):
    print("App type:", type(app))
    return app

app = rx.App(api_transformer=api_transformer)
app()
