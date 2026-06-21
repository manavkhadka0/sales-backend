"""
Daraz / Lazada Open Platform (LOP) client.

This module re-exports the official Lazop Python SDK classes
(located in <project_root>/python/lazop/) under the names
IopClient, IopRequest, and IopResponse so the rest of the
`daraz` app can use a stable internal interface regardless of
where the SDK lives on disk.
"""

import os
import sys

# ---------------------------------------------------------------------------
# Make the bundled Lazop SDK importable
# ---------------------------------------------------------------------------
_SDK_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "python",
)
if _SDK_DIR not in sys.path:
    sys.path.insert(0, _SDK_DIR)

# pylint: disable=wrong-import-position
from lazop.base import (  # noqa: E402
    LazopClient as IopClient,
    LazopRequest as IopRequest,
    LazopResponse as IopResponse,
)

__all__ = ["IopClient", "IopRequest", "IopResponse"]
