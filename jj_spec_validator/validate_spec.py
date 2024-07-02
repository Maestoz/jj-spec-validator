from functools import wraps
from json import loads
from typing import Callable, Dict, Optional, Tuple, TypeVar, Literal
from schemax_openapi import SchemaData
from d42 import validate_or_fail

from .utils import normalize_path, load_cache

_T = TypeVar('_T')


class Validator:
    @staticmethod
    def _check_entity_match(entity_dict: Dict[Tuple[str, str], SchemaData],
                            http_method: str,
                            path: str) -> Optional[SchemaData]:
        normalized_path = normalize_path(path)
        entity_key = (http_method.lower(), normalized_path)
        return entity_dict.get(entity_key)

    @staticmethod
    def validate(mocked: _T,
                 prepared_dict: Dict[Tuple[str, str], SchemaData],
                 is_strict: bool,
                 validate_level: Literal["error", "warning"],
                 func_name: str) -> None:
        is_strict = False
        matcher = mocked.handler.matcher.sub_matchers  # type: ignore
        method = matcher[0].sub_matcher.expected
        path = normalize_path(matcher[1].sub_matcher.path)

        parsed_request = Validator._check_entity_match(prepared_dict, http_method=method, path=path)

        if parsed_request:
            if parsed_request.response_schema_d42:
                decoded_mocked_body = loads(mocked.handler.response.get_body().decode())  # type: ignore

                if is_strict:
                    assert validate_or_fail(parsed_request.response_schema_d42, decoded_mocked_body)
                else:
                    try:
                        parsed_request.response_schema_d42 % decoded_mocked_body
                    except Exception as e:
                        if e.__class__.__name__ == 'SubstitutionError':
                            if validate_level == "error":
                                raise ValueError(f"ValidationError: There are some mismatches in {func_name}:\n{str(e)}")
                            elif validate_level == "warning":
                                print(f"⚠️ There are some mismatches in {func_name} ⚠️:\n{str(e)}")
                        else:
                            raise
            else:
                raise AssertionError(f"API method '{method} {path}' in the spec_link"
                                     f" lacks a response structure for the validation of {func_name}")
        else:
            raise AssertionError(f"API method '{method} {path}' was not found in the spec_link "
                                 f"for the validation of {func_name}")


def _prepare_data(spec_link: str) -> Dict[Tuple[str, str], SchemaData]:
    return load_cache(spec_link)


def validate_spec(*,
                  spec_link: str,
                  is_strict: bool = False,
                  validate_level: Literal["error", "warning"] = "error") -> (
        Callable)[[Callable[..., _T]], Callable[..., _T]]:
    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        func_name = func.__name__

        @wraps(func)
        def wrapper(*args: object, **kwargs: object) -> _T:

            prepared_dict = _prepare_data(spec_link)
            mocked = func(*args, **kwargs)

            Validator.validate(mocked, prepared_dict, is_strict, validate_level, func_name)
            
            return mocked
        return wrapper
    return decorator
