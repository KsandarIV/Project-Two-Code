"""The system keystore (KAN-107): where the app keeps the key of the encrypted database and, from KAN-108, the
backup private key, so that this device can give a new main password without the old one («dispositivo principale»).

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


DATABASE_KEY = "database_key"
BACKUP_KEY = "backup_key"


def key_name(folder: Path, what: str = DATABASE_KEY) -> str:
    """One entry per data folder and secret, without writing the folder's path in the keystore."""
    return f"zibaldone.{what}." + hashlib.sha256(str(Path(folder).resolve()).encode("utf-8")).hexdigest()[:16]


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


async def read(ctx: Any, what: str = DATABASE_KEY) -> Optional[str]:
    service = _service(ctx)
    if service is None:
        return None
    try:
        return await asyncio.wait_for(service.get(key_name(ctx.folder, what)), TIMEOUT)
    except Exception:  # no keystore here, or it refused
        logger.info("keystore read failed", exc_info=True)
        return None


async def write(ctx: Any, text: str, what: str = DATABASE_KEY) -> bool:
    service = _service(ctx)
    if service is None:
        return False
    try:
        await asyncio.wait_for(service.set(key_name(ctx.folder, what), text), TIMEOUT)
    except Exception:
        logger.info("keystore write failed", exc_info=True)
        return False
    return True
