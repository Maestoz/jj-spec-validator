from re import sub

__all__ = ('normalize_path', )


def normalize_path(path: str, prefix: str | None = None) -> str:
    if prefix:
        path = sub(prefix, '', path)
    path = sub(r'{[a-zA-Z0-9_]+}', '{var}', path)
    return path
