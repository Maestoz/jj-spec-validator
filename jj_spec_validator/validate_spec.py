import asyncio
from functools import wraps
from json import JSONDecodeError, loads
from typing import Any, Callable, Dict, Tuple, TypeVar

from jj import RelayResponse
from schemax_openapi import SchemaData
from valera import ValidationException, validate_or_fail

from ._config import Config
from .utils import (create_openapi_matcher, get_forced_strict_spec, load_cache,
                    validate_non_strict)

_T = TypeVar('_T')

class Validator:

    def __init__(self,
                 is_raise_error: bool,
                 is_strict: bool,
                 func_name: str,
                 spec_link: str | None = None,
                 force_strict: bool = False,
                 prefix: str | None = None,
                 ):
        self.is_raise_error = is_raise_error
        self.is_strict = is_strict
        self.func_name = func_name
        self.spec_link = spec_link
        self.force_strict = force_strict
        self.prefix = prefix

    def output(self,
               e: Exception
               ) -> None:
        if Config.OUTPUT_FUNCTION is None:
            print(f"⚠️ ⚠️ ⚠️ There are some mismatches in {self.func_name} :\n{str(e)}\n")
        else:
            Config.OUTPUT_FUNCTION(self.func_name, e)

    def _validation_failure(self,
                            exception: Exception,
                            ) -> None:
        self.output(exception)
        if self.is_raise_error:
            raise ValidationException(f"There are some mismatches in {self.func_name}:\n{str(exception)}")

    def prepare_data(self) -> dict[tuple[str, str], SchemaData]:
        if self.spec_link is None:
            raise ValueError("Spec link cannot be None")
        return load_cache(self.spec_link)

    def _prepare_validation(self,
                           mocked,
                           ) -> tuple[SchemaData | None, Any]:
        mock_matcher = mocked.handler.matcher

        try:
            # check for JSON in response of mock
            decoded_mocked_body = loads(mocked.handler.response.get_body().decode())
        except JSONDecodeError:
            raise AssertionError(f"JSON expected in Response body of the {self.func_name}")

        spec_matcher = create_openapi_matcher(matcher=mock_matcher, prefix=self.prefix)

        if not spec_matcher:
            raise AssertionError(f"There is no valid matcher in {self.func_name}")

        prepared_spec = self.prepare_data()
        matched_spec_units = [(http_method, path) for http_method, path in prepared_spec.keys() if
                              spec_matcher.match((http_method, path))]

        if len(matched_spec_units) > 1:
            raise AssertionError(f"There is more than 1 matches")

        elif len(matched_spec_units) == 0:
            raise AssertionError(f"API method '{prepared_spec}' was not found in the spec_link "
                                 f"for the validation of {self.func_name}")

        spec_unit = prepared_spec.get(matched_spec_units[0])

        return spec_unit, decoded_mocked_body

    def validate(self,
                 mocked: _T,
                 ) -> None:

        spec_unit, decoded_mocked_body = self._prepare_validation(mocked=mocked)
        if spec_unit is not None:
            spec_response_schema = spec_unit.response_schema_d42
            if spec_response_schema:
                if self.force_strict:
                    spec_response_schema = get_forced_strict_spec(spec_response_schema)
                else:
                    spec_response_schema = spec_response_schema

                try:
                    if self.is_strict:
                        validate_or_fail(spec_response_schema, decoded_mocked_body)
                    else:
                        validate_non_strict(spec_response_schema, decoded_mocked_body)

                except ValidationException as exception:
                    self._validation_failure(exception)

        else:
            raise AssertionError(f"API method '{spec_unit}' in the spec_link"
                                 f" lacks a response structure for the validation of {self.func_name}")

def validate_spec(*,
                  spec_link: str | None,
                  is_raise_error: bool | None = None,
                  is_strict: bool | None = None,
                  prefix: str | None = None,
                  force_strict: bool = False,
                  ) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """
    Validates the jj mock function with given specification lint.

    Args:
       spec_link: The link to the specification. `None` for disable validation.
       is_raise_error: If True - raises error when validation is failes. False is default.
       is_strict: If True - validate exact structure in given mocked.
       prefix: Prefix is used to cut paths prefix in mock function.
       force_strict: If True - forced remove all Ellipsis from the spec.
    """
    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        func_name = func.__name__

        validator = Validator(
            spec_link=spec_link,
            prefix=prefix,
            func_name=func_name,
            force_strict=force_strict,
            is_raise_error=is_raise_error if is_raise_error is not None else Config.IS_RAISES,
            is_strict=is_strict if is_strict is not None else Config.IS_STRICT
            )

        @wraps(func)
        async def async_wrapper(*args: object, **kwargs: object) -> _T:
            mocked = await func(*args, **kwargs)
            if validator.spec_link:
                if isinstance(mocked.handler.response, RelayResponse):
                    print("RelayResponse type is not supported")
                    return mocked
                validator.validate(mocked)
            else:...
            return mocked

        @wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> _T:
            mocked = func(*args, **kwargs)
            if validator.spec_link:
                if isinstance(mocked.handler.response, RelayResponse):
                    print("RelayResponse type is not supported")
                    return mocked
                validator.validate(mocked)
            else:...
            return mocked

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
