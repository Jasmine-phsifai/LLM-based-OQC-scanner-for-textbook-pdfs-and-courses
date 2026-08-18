"""Delete the HKCU registry trees that isolated QSettings tests leave behind."""

from __future__ import annotations

import sys

_TEST_ORG_PREFIX = "OCRLLMTests-"
_SOFTWARE_KEY = r"Software"


def delete_test_qsettings_tree(org: str) -> None:
    """Remove one isolated test organization key, values and empty subkeys alike.

    QSettings.clear() only removes values; on Windows the organization key itself
    survives and accumulates across runs.
    """
    if not org.startswith(_TEST_ORG_PREFIX):
        raise ValueError("refusing to delete a registry tree outside the test prefix")
    if sys.platform != "win32":
        return

    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _SOFTWARE_KEY, 0, winreg.KEY_ALL_ACCESS) as software:
            _delete_key_tree(winreg, software, org)
    except FileNotFoundError:
        return


def delete_orphaned_test_qsettings_trees() -> int:
    """Remove every leftover test organization key and return how many were deleted."""
    if sys.platform != "win32":
        return 0

    import winreg

    deleted = 0
    with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _SOFTWARE_KEY, 0, winreg.KEY_ALL_ACCESS) as software:
        orphans = []
        index = 0
        while True:
            try:
                name = winreg.EnumKey(software, index)
            except OSError:
                break
            if name.startswith(_TEST_ORG_PREFIX):
                orphans.append(name)
            index += 1
        for name in orphans:
            _delete_key_tree(winreg, software, name)
            deleted += 1
    return deleted


def _delete_key_tree(winreg, parent, name: str) -> None:
    try:
        with winreg.OpenKey(parent, name, 0, winreg.KEY_ALL_ACCESS) as child:
            while True:
                try:
                    subkey = winreg.EnumKey(child, 0)
                except OSError:
                    break
                _delete_key_tree(winreg, child, subkey)
    except FileNotFoundError:
        return
    winreg.DeleteKey(parent, name)


if __name__ == "__main__":
    print(f"deleted {delete_orphaned_test_qsettings_trees()} orphaned test registry keys")
