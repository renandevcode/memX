"""Project-relative capture exclusions shared by sources, artifacts and events."""

from fnmatch import fnmatchcase
from pathlib import PurePath

DEFAULT_EXCLUDED_PATHS = (".env", ".env.*", "secrets", "secrets/**", "*.pem", "*.key")


def is_excluded(path: str | PurePath, patterns: tuple[str, ...] = DEFAULT_EXCLUDED_PATHS) -> bool:
    candidate = PurePath(path)
    pieces = candidate.parts
    for pattern in patterns:
        clean = pattern.removesuffix("/**")
        if "/" in clean:
            if fnmatchcase(candidate.as_posix(), clean) or candidate.as_posix().startswith(clean + "/"):
                return True
        elif any(fnmatchcase(piece, clean) for piece in pieces):
            return True
    return False
