from .app import create_app

app = create_app()


@app.get("/", tags=["root"])
async def root() -> dict[str, str]:
    return {"status": "ok"}

