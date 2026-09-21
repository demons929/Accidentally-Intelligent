"""Start the HarryPort FastAPI backend.

Usage:
    python run_server.py                     # http://127.0.0.1:8000
    python run_server.py --port 8001         # custom port
    python run_server.py --reload            # auto-reload on code changes (dev)
"""

from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve the HarryPort dashboard and API.")
    parser.add_argument(
        "--host",
        default=os.environ.get("HOST", "0.0.0.0"),
        help="Bind address (default: 0.0.0.0, or $HOST if set)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", "8000")),
        help="Bind port (default: 8000, or $PORT if set — used by Render/HF Spaces)",
    )
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload for development")
    args = parser.parse_args()

    uvicorn.run("backend.main:app", host=args.host, port=args.port, reload=args.reload)


if __name__ == "__main__":
    main()
