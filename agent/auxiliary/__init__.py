"""Auxiliary client package (F-C3).

Holds the provider router used by side tasks (context compression,
title generation, vision, session search, web extraction, analyst
council, etc.). Historically a single ~1,930-line module at
``agent/auxiliary_client.py``; F-C3 splits it into smaller siblings
under this package. Step 1 lands the package with everything in
``base.py`` and leaves the legacy import path intact via a shim.

All public symbols are re-exported here. Existing callers that do
``from agent.auxiliary_client import <name>`` keep working through
the ``agent/auxiliary_client.py`` shim, which re-exports this
package.
"""

from __future__ import annotations

from agent.auxiliary.base import *  # noqa: F401,F403
