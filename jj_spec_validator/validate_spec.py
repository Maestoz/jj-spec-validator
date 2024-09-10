import asyncio
from functools import wraps
from json import JSONDecodeError, loads
from typing import (Any, Callable, Dict, Literal, Tuple, TypeVar)

from d42 import validate_or_fail
from jj import RelayResponse
from pathlib import Path


from revolt.errors import SubstitutionError
from schemax_openapi import SchemaData
from valera import ValidationException

from ._config import Config
from .utils import load_cache, create_openapi_matcher

_T = TypeVar('_T')


class Validator:
    path_for_tmp = Path(str(Config.TEMP_DIRECTORY))

    @staticmethod
    def _gen_tmp_filename(func_name: str) -> Path:
        file_path = Validator.path_for_tmp / f"_jj-validator_tmp_{func_name}.txt"
        return file_path

    @staticmethod
    def _validation_failure(func_name: str,
                            e: Exception,
                            validate_level: Literal["error", "warning", "skip"],
                            output_mode: str | None,
                            ) -> None:
        if validate_level == "error":
            raise ValidationException(f"There are some mismatches in {func_name}:\n{str(e)}")
        elif validate_level == "warning":
            if output_mode == "std":
                print(f"⚠️ There are some mismatches in {func_name} :\n{str(e)}\n")
            elif output_mode == "file":
                Validator.path_for_tmp.mkdir(exist_ok=True)
                with Validator._gen_tmp_filename(func_name).open("a") as f:
                    f.write(f"{str(e)}\n")
        elif validate_level == "skip":
            pass

    @staticmethod
    def _handle_non_strict_validation(parsed_request: SchemaData,
                                      decoded_mocked_body: Any,
                                      validate_level: Literal["error", "warning", "skip"],
                                      func_name: str,
                                      output_mode: str | None,
                                      ) -> None:

        try:
            parsed_request.response_schema_d42 % decoded_mocked_body
        except SubstitutionError as e:
            Validator._validation_failure(func_name, e, validate_level, output_mode)

    @staticmethod
    def _handle_strict_validation(parsed_request: SchemaData,
                                  decoded_mocked_body: Any,
                                  validate_level: Literal["error", "warning", "skip"],
                                  func_name: str,
                                  output_mode: str | None,
                                  ) -> None:
        try:
            validate_or_fail(parsed_request.response_schema_d42, decoded_mocked_body)
        except ValidationException as e:
            Validator._validation_failure(func_name, e, validate_level, output_mode)

    @staticmethod
    def prepare_data(spec_link: str) -> Dict[Tuple[str, str], SchemaData]:
        return load_cache(spec_link)

    @staticmethod
    def validate(mocked: _T,
                 prepared_dict_from_spec: Dict[Tuple[str, str], SchemaData],
                 is_strict: bool,
                 validate_level: Literal["error", "warning", "skip"],
                 func_name: str,
                 prefix: str | None,
                 output_mode: str | None,
                 ) -> None:
        mock_matcher = mocked.handler.matcher
        spec_matcher = create_openapi_matcher(matcher=mock_matcher, prefix=prefix)

        if not spec_matcher:
            raise AssertionError(f"There is no valid matcher in {func_name}")
        matched_spec_units = [(http_method, path) for http_method, path in prepared_dict_from_spec.keys() if spec_matcher.match((http_method, path))]

        if len(matched_spec_units) > 1:
            raise AssertionError(f"There is more than 1 matches")

        if len(matched_spec_units) == 0:
            raise AssertionError(f"There is no match for {func_name} :(")

        spec_unit = prepared_dict_from_spec.get(matched_spec_units[0])

        if spec_unit:
            if spec_unit.response_schema_d42:
                try:
                    # check for JSON in response of mock
                    decoded_mocked_body = loads(mocked.handler.response.get_body().decode())  # type: ignore
                except JSONDecodeError:
                    raise AssertionError(f"JSON expected in Response body of the {func_name}")

                if is_strict:
                    Validator._handle_strict_validation(spec_unit, decoded_mocked_body, validate_level, func_name, output_mode)
                else:
                    Validator._handle_non_strict_validation(spec_unit, decoded_mocked_body, validate_level, func_name, output_mode)

            else:
                raise AssertionError(f"API method '{prepared_dict_from_spec}' in the spec_link"
                                     f" lacks a response structure for the validation of {func_name}")
        else:
            raise AssertionError(f"API method '{prepared_dict_from_spec}' was not found in the spec_link "
                                 f"for the validation of {func_name}")


def validate_spec(*,
                  spec_link: str | None,
                  is_strict: bool = False,
                  validate_level: Literal["error", "warning", "skip"] = "warning",
                  prefix: str | None = None,
                  output_mode: Literal["std", "file"] = "std",
                  ) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """
    Validates the jj mock function with given specification lint.

    Args:
       spec_link: The link to the specification. `None` for disable validation.
       is_strict: Defines the comparison policy. Default is 'False'.
       validate_level: The validation level. Can be 'error', 'warning', or 'skip'. Default is 'warning'.
       prefix: Prefix is used to cut paths prefix in mock function.
       output_mode: Defines warning messages output. 'std' is default. 'file' for creating file with result per func call.
    """
    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        func_name = func.__name__

        @wraps(func)
        async def async_wrapper(*args: object, **kwargs: object) -> _T:
            if spec_link:
                mocked = await func(*args, **kwargs)
                if isinstance(mocked.handler.response, RelayResponse):
                    print("RelayResponse type is not supported")
                    return mocked
                prepared_dict_from_spec = Validator.prepare_data(spec_link)
                Validator.validate(mocked, prepared_dict_from_spec, is_strict, validate_level, func_name, prefix, output_mode)
            else:
                mocked = await func(*args, **kwargs)
            return mocked

        @wraps(func)
        def sync_wrapper(*args: object, **kwargs: object) -> _T:
            if spec_link:
                mocked = func(*args, **kwargs)
                if isinstance(mocked.handler.response, RelayResponse):
                    print("RelayResponse type is not supported")
                    return mocked
                prepared_dict_from_spec = Validator.prepare_data(spec_link)
                Validator.validate(mocked, prepared_dict_from_spec, is_strict, validate_level, func_name, prefix, output_mode)
            else:
                mocked = func(*args, **kwargs)
            return mocked

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
