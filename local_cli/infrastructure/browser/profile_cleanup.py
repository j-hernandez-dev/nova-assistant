"""Finite cleanup of the current owned profile, never historical directory scans."""
import shutil
import time


def remove_owned_profile(profile, parent, prefix, *, timeout=2):
    deadline = time.monotonic() + timeout
    while True:
        if not profile.exists() and not profile.is_symlink(): return True
        if (profile.parent != parent or profile.resolve() != profile or profile.is_symlink()
                or not profile.name.startswith(prefix)):
            return False
        try:
            shutil.rmtree(profile)
            return not profile.exists()
        except PermissionError:
            # Windows may release a crashed engine's file handles just after
            # its process is signaled. Retry cleanup only, never browser work.
            if time.monotonic() >= deadline: return False
            time.sleep(0.05)
        except OSError: return False
