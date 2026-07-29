from __future__ import annotations

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

from midi2tracker.instruments.error import BankError
from midi2tracker.instruments.manifest import BankManifest

MANIFEST_NAME: Final = "bank.json"
MANIFEST_EXTENSION: Final = ".json"
CONTAINER_EXTENSION: Final = ".bank"


class BankStore(Protocol):
    """Where a bank's bytes are read from: its manifest, and each entry that manifest names.

    A bank is a manifest and the instruments it points at, and the two ship together either as one
    archive or as a directory. Naming both through one interface is what lets everything above read a
    bank without knowing which of them it was handed.
    """

    def manifest(self) -> BankManifest:
        """The document describing the bank.

        Raises:
            BankError: when it cannot be read, or describes a bank of another shape.
        """

    def read(self, name: str) -> bytes:
        """The bytes stored under ``name``.

        Raises:
            BankError: when the store holds no such entry.
        """


def _file_bytes(path: Path) -> bytes:
    """The bytes of a file a bank names.

    Raises:
        BankError: when it cannot be read.
    """
    try:
        return path.read_bytes()
    except OSError as unreadable:
        raise BankError(f"{path} cannot be read: {unreadable}") from unreadable


@dataclass(frozen=True)
class DirectoryStore:
    """A bank spread over a directory: a manifest file, with every entry named against the directory it sits in.

    ``path`` is the manifest itself, which is what a caller names when the instruments are loose files
    beside it.
    """

    path: Path

    def manifest(self) -> BankManifest:
        """The document describing the bank.

        Raises:
            BankError: when the file cannot be read, or describes a bank of another shape.
        """
        return BankManifest.parse(_file_bytes(self.path), origin=str(self.path))

    def read(self, name: str) -> bytes:
        """The bytes of the file ``name`` names, read against the directory the manifest sits in.

        Raises:
            BankError: when the directory holds no such file.
        """
        return _file_bytes(self.path.parent / name)


@dataclass(frozen=True)
class StatedStore:
    """A bank whose manifest is stated where it is used, with its entries read against ``root``.

    An arrangement naming a track's layers outright holds the document already, so there is nothing to
    read it from; what is left is where the instruments it names sit, which is the directory the
    arrangement itself was read from.
    """

    stated: BankManifest
    root: Path

    def manifest(self) -> BankManifest:
        """The document the caller stated."""
        return self.stated

    def read(self, name: str) -> bytes:
        """The bytes of the file ``name`` names, read against the directory the layers were stated in.

        Raises:
            BankError: when the directory holds no such file.
        """
        return _file_bytes(self.root / name)


@dataclass(frozen=True)
class ContainerStore:
    """A bank shipped as one archive holding its manifest and every instrument the manifest names.

    A producer measures the velocity a layer reads against the very waveforms it stores, so the two are
    one calibrated unit; a bank that travels as a single file keeps them together however it is copied,
    renamed or handed on.
    """

    path: Path

    def manifest(self) -> BankManifest:
        """The document the archive stores under its manifest entry.

        Raises:
            BankError: when the archive or the entry cannot be read, or describes a bank of another shape.
        """
        return BankManifest.parse(self.read(MANIFEST_NAME), origin=f"{self.path}:{MANIFEST_NAME}")

    def read(self, name: str) -> bytes:
        """The bytes the archive stores under ``name``.

        Raises:
            BankError: when the archive cannot be opened, or holds no such entry.
        """
        try:
            with zipfile.ZipFile(self.path) as container:
                return container.read(name)
        except KeyError as absent:
            raise BankError(f"{self.path} holds no entry named {name}") from absent
        except (OSError, zipfile.BadZipFile) as unreadable:
            raise BankError(f"{self.path} does not read as a bank container: {unreadable}") from unreadable


def open_bank(path: Path) -> BankStore:
    """The store a bank at ``path`` is read through, whichever way it was shipped.

    A manifest named outright is read where it sits, with its instruments beside it. Anything else is the
    archive carrying both, which is the form a bank travels in.
    """
    if path.suffix.lower() == MANIFEST_EXTENSION:
        return DirectoryStore(path=path)

    return ContainerStore(path=path)
