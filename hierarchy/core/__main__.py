"""Allow running the package as ``python -m core``."""

import sys

from hierarchy.core.cli import main

sys.exit(main())
