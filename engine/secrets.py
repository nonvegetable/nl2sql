"""Secret storage behind a small platform-credential abstraction."""

from __future__ import annotations

from typing import Protocol


class SecretStore(Protocol):
    def set(self, key: str, value: str) -> None: ...
    def get(self, key: str) -> str | None: ...
    def delete(self, key: str) -> None: ...


class KeyringSecretStore:
    """Use the OS credential backend selected by the keyring package."""

    def __init__(self, service: str = "nl2sql") -> None:
        self.service = service

    def set(self, key: str, value: str) -> None:
        import keyring
        keyring.set_password(self.service, key, value)

    def get(self, key: str) -> str | None:
        import keyring
        return keyring.get_password(self.service, key)

    def delete(self, key: str) -> None:
        import keyring
        try:
            keyring.delete_password(self.service, key)
        except keyring.errors.PasswordDeleteError:
            pass


class MemorySecretStore:
    """Deterministic secret store for tests and embedded callers."""

    def __init__(self) -> None:
        self._values: dict[str, str] = {}

    def set(self, key: str, value: str) -> None:
        self._values[key] = value

    def get(self, key: str) -> str | None:
        return self._values.get(key)

    def delete(self, key: str) -> None:
        self._values.pop(key, None)
