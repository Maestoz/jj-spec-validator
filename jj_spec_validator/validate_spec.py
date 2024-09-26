import asyncio
from functools import wraps
from json import JSONDecodeError, loads
from typing import Callable, Dict, Literal, Tuple, TypeVar

from d42 import substitute
from jj import RelayResponse
from revolt.errors import SubstitutionError
from schemax_openapi import SchemaData
from valera import ValidationException

from ._config import Config
from .utils import create_openapi_matcher, load_cache

_T = TypeVar('_T')

class Validator:

    def __init__(self,
                 is_raise_error: bool,
                 func_name: str,
                 spec_link: str | None = None,
                 validate_level: Literal["error", "warning"] = "warning",
                 prefix: str | None = None,
                 ):
        self.func_name = func_name
        self.spec_link = spec_link
        self.is_raise_error = is_raise_error
        self.validate_level = validate_level
        self.prefix = prefix

    def output(self,
               e: Exception):
        if Config.OUTPUT_FUNCTION is None:
            print(f"⚠️ ⚠️ ⚠️ There are some mismatches in {self.func_name} :\n{str(e)}\n")
        else:
            Config.OUTPUT_FUNCTION(self, e)

    def _validation_failure(self,
                            exception: Exception,
                            ) -> None:
        self.output(exception)
        if self.is_raise_error:
            raise ValidationException(f"There are some mismatches in {self.func_name}:\n{str(exception)}")

    def prepare_data(self) -> Dict[Tuple[str, str], SchemaData]:
        return load_cache(self.spec_link, self.func_name)

    def _prepare_validation(self,
                           mocked: _T,
                           ):
        mock_matcher = mocked.handler.matcher

        try:
            # check for JSON in response of mock
            decoded_mocked_body = loads(mocked.handler.response.get_body().decode())  # type: ignore
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

        if len(matched_spec_units) == 0:
            raise AssertionError(f"API method '{prepared_spec}' was not found in the spec_link "
                                 f"for the validation of {self.func_name}")

        spec_unit = prepared_spec.get(matched_spec_units[0])

        return spec_unit, decoded_mocked_body


    def validate(self,
                 mocked: _T,
                 ) -> None:

        spec_unit, decoded_mocked_body = self._prepare_validation(mocked=mocked)

        if spec_unit.response_schema_d42:

            try:
                substitute(spec_unit.response_schema_d42, decoded_mocked_body)
            except SubstitutionError as exception:
                self._validation_failure(exception)

        else:
            raise AssertionError(f"API method '{spec_unit}' in the spec_link"
                                 f" lacks a response structure for the validation of {self.func_name}")


def validate_spec(*,
                  spec_link: str | None,
                  is_raise_error: bool = None,
                  prefix: str | None = None
                  ) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """
    Validates the jj mock function with given specification lint.

    Args:
       spec_link: The link to the specification. `None` for disable validation.
       is_raise_error: If True - raises error when validation is failes. False is default.
       prefix: Prefix is used to cut paths prefix in mock function.
    """
    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        func_name = func.__name__

        validator = Validator(
            spec_link=spec_link,
            prefix=prefix,
            func_name=func_name,
            is_raise_error=is_raise_error if is_raise_error is not None else Config.IS_RAISES
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
