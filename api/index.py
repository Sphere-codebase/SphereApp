"""Vercel serverless entrypoint for FastAPI."""

from __future__ import annotations

import logging
import os
import platform


def _load_app():
    try:
        from app.main import app as fastapi_app
    except Exception:
        logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))
        logging.getLogger(__name__).exception(
            "vercel entrypoint failed to import app python=%s cwd=%s",
            platform.python_version(),
            os.getcwd(),
        )
        raise
    return fastapi_app


app = _load_app()

__all__ = ["app"]
