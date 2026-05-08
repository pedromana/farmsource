from app.main import app

if __name__ == "__main__":
    import os

    import uvicorn

    port = int(os.getenv("PORT", "8010"))
    uvicorn.run("app.main:app", host="127.0.0.1", port=port, reload=True)
