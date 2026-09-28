"""Console entry point for the bundled Python sidecar."""

import argparse
import os

import uvicorn

from engine.api import app


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the NL2SQL local engine.")
    parser.add_argument("--host", default=os.getenv("NL2SQL_ENGINE_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("NL2SQL_ENGINE_PORT", "47821")))
    args = parser.parse_args()
    uvicorn.run(app, host=args.host, port=args.port)


if __name__ == "__main__":
    main()
