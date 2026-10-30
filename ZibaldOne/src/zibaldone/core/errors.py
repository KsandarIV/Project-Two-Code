"""Errors shared by core and storage.

They live in core so that core never has to import storage (layer rule);
`zibaldone.storage.database` re-exports `StoreError` for the layers above.
"""


class StoreError(Exception):
    """A storage operation was refused (missing item, conflict, …)."""
