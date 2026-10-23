"""Start the API with `python -m app`. Binds to GUARDIAN_HOST (default 127.0.0.1)."""
import uvicorn

from app.core.config import settings

if __name__ == "__main__":
    uvicorn.run("app.main:app", host=settings.host, port=settings.port, reload=False)
