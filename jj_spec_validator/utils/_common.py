import re

__all__ = ('normalize_path', 'destroy_prefix', )


def normalize_path(path: str) -> str:
    var_counter = 1

    def replace_var(match) -> str:
        nonlocal var_counter
        replacement = f'{{var{var_counter}}}'
        var_counter += 1
        return replacement

    normalized_path = re.sub(r'{[a-zA-Z0-9_]+}', replace_var, path)

    return normalized_path


def destroy_prefix(path: str, prefix: str) -> str:
    return re.sub(prefix, '', path)
