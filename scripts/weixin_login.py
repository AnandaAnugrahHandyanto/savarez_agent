#!/usr/bin/env python3
"""Compatibility wrapper for the Hermes WeChat QR login flow."""

import asyncio
import sys

try:
    from hermes_cli.wechat_login import run_wechat_login
except ImportError:
    print("Error: Hermes WeChat login module not available.")
    sys.exit(1)


def main() -> None:
    try:
        asyncio.run(run_wechat_login())
    except KeyboardInterrupt:
        print("\nLogin cancelled.")
        sys.exit(1)
    except Exception as e:
        print(f"\nWeChat login failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
