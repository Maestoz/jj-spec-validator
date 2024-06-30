from re import sub

__all__ = ('normalize_path', )


def normalize_path(path: str) -> str:
    path = sub(r'/__[a-zA-Z0-9_]+__', '', path)
    path = sub(r'{[a-zA-Z0-9_]+}', '{var}', path)
    return path
