#!/usr/bin/env python3
"""Compatibility entry point for the DCT n8n deployment.

The email-action deployment script is now the authoritative source because
the main workflow and the isolated action/retraction workflow must be
deployed together. Use ``deploy_dct_email_actions.py`` directly for the
available phases.
"""
from __future__ import annotations

import sys

from deploy_dct_email_actions import main


if __name__ == "__main__":
    if "--phase" not in sys.argv:
        sys.argv.extend(["--phase", "main"])
    raise SystemExit(main())
