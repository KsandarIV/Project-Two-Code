"""The system keystore (KAN-107): where the app keeps the key of the encrypted database.

`flet-secure-storage` (Android Keystore, Windows Credential Manager) is in the builds made by `flet build`. Started
from Python (`flet run`, the web) it is missing, or its Flutter side is: then nothing is kept, and the app asks the
main password at every start. Every call gives up after a few seconds rather than hang the start.
"""

import asyncio
import hashlib
import logging
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger("zibaldone.ui")
TIMEOUT = 5.0


def key_name(folder: Path) -> str:
    """One entry per data folder, without writing its path in the keystore."""
    return "zibaldone.database_key." + hashlib.sha256(str(Path(folder).resolve()).encode("utf-8")).hexdigest()[:16]


def _service(ctx: Any) -> Optional[Any]:
    page = getattr(ctx, "page", None)
    if page is None:
        return None
    service = ctx.memory.get("secure_storage")
    if service is None:
        try:
            import flet_secure_storage as fss
        except ImportError:
            return None
        service = ctx.memory["secure_storage"] = fss.SecureStorage()
        page.services.append(service)
    return service


async def read(ctx: Any) -> Optional[str]:
    service = _service(ctx)
    if service is None:
        return None
    try:
        return await asyncio.wait_for(service.get(key_name(ctx.folder)), TIMEOUT)
    except Exception:  # no keystore here, or it refused
        logger.info("keystore read failed", exc_info=True)
        return None


async def write(ctx: Any, text: str) -> bool:
    service = _service(ctx)
    if service is None:
        return False
    try:
        await asyncio.wait_for(service.set(key_name(ctx.folder), text), TIMEOUT)
    except Exception:
        logger.info("keystore write failed", exc_info=True)
        return False
    return True
