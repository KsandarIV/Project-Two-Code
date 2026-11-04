"""Fingerprint, face or the screen lock of the device before the diary opens (KAN-108).

`flet-local-auth` only answers yes or no: what protects the data is the key in the system keystore (KAN-107);
this is the door in front of it. Where the device has no screen lock, or the app runs without the extension
(`flet run`, the web, Linux), there is no door and the keystore alone opens the diary, as before.
"""

import asyncio
import logging
from typing import Any, Optional

logger = logging.getLogger("zibaldone.ui")
CHECK_TIMEOUT = 5.0
REASON = "Apri il tuo diario"


def _service(ctx: Any) -> Optional[Any]:
    page = getattr(ctx, "page", None)
    if page is None or getattr(page, "web", False):
        return None
    service = ctx.memory.get("local_auth")
    if service is None:
        try:
            import flet_local_auth as fla
        except ImportError:
            return None
        service = ctx.memory["local_auth"] = fla.LocalAuthentication()
        try:
            page.services.append(service)
        except Exception:  # Linux: not supported
            logger.info("local auth not available", exc_info=True)
            ctx.memory["local_auth"] = None
            return None
    return service


async def available(ctx: Any) -> bool:
    """True when the device can ask fingerprint, face or its screen lock."""
    service = _service(ctx)
    if service is None:
        return False
    try:
        return bool(await asyncio.wait_for(service.is_device_supported(), CHECK_TIMEOUT))
    except Exception:
        logger.info("local auth check failed", exc_info=True)
        return False


async def confirm(ctx: Any, reason: str = REASON) -> Optional[bool]:
    """None: nothing to ask on this device. True: the owner confirmed. False: cancelled or refused."""
    if not await available(ctx):
        return None
    try:
        return bool(await _service(ctx).authenticate(reason, persist_across_backgrounding=True))
    except Exception:  # cancelled, too many tries, no fingerprint enrolled …
        logger.info("local auth refused", exc_info=True)
        return False
