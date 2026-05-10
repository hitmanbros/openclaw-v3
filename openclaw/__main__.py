"""Entry point: python -m openclaw"""

import asyncio
import logging
import os
import sys

from openclaw.main import create_bot, run_bot


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
        datefmt="%H:%M:%S",
    )

    config_path = os.environ.get("OPENCLAW_CONFIG", "config.yaml")
    if not os.path.exists(config_path):
        print(f"Config not found: {config_path}")
        sys.exit(1)

    bot = create_bot(config_path)
    try:
        asyncio.run(run_bot(bot))
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
