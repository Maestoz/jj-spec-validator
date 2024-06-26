from functools import wraps
from json import loads
from typing import Callable, Dict, Optional, Tuple, TypeVar

from schemax_openapi import SchemaData

from utils._common import _normalize_path
from jj_spec_validator.utils._cacheir import _load_cache

_T = TypeVar('_T')


def _check_entity_match(entity_dict: Dict[Tuple[str, str], SchemaData],
                        http_method: str, path: str) -> Optional[SchemaData]:
    normalized_path = _normalize_path(path)
    entity_key = (http_method.lower(), normalized_path)
    return entity_dict.get(entity_key)


def validate_spec(*, spec_link: str) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        @wraps(func)
        def wrapper(*args: object, **kwargs: object) -> _T:

            prepared_dict = _load_cache(spec_link)

            mocked = func(*args, **kwargs)

            matcher = mocked.handler.matcher.sub_matchers  # type: ignore
            method = matcher[0].sub_matcher.expected
            path = _normalize_path(matcher[1].sub_matcher.path)

            parsed_request = _check_entity_match(prepared_dict, http_method=method, path=path)

            if parsed_request:
                if parsed_request.response_schema_d42:
                    decoded_mocked_body = loads(mocked.handler.response.get_body().decode())  # type: ignore
                    parsed_request.response_schema_d42 % decoded_mocked_body
                else:
                    raise AssertionError(f"API method '{method} {path}' in the {spec_link}"
                                         f" does not have a response structure")
            else:
                raise AssertionError(f"API method '{method} {path}' not found in the {spec_link}.")
            return mocked
        return wrapper
    return decorator
