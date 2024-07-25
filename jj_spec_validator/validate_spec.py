from functools import wraps
from json import loads, JSONDecodeError
from typing import Callable, Dict, Union, List, Literal, Optional, Tuple, TypeVar, Any
import asyncio

from d42 import validate_or_fail
from schemax_openapi import SchemaData
from jj import RelayResponse
from jj.matchers import ResolvableMatcher
from jj.matchers import MethodMatcher as JJMethodMatcher
from jj.matchers import PathMatcher as JJPathMatcher
from jj.matchers.attribute_matchers import RouteMatcher as JJRouteMatcher
from jj.matchers import AnyMatcher as JJAnyMatcher
from jj.matchers import AllMatcher as JJAllMatcher
from jj.matchers import EqualMatcher as JJEqualMatcher
from .utils import load_cache, normalize_path
from revolt.errors import SubstitutionError
from aiohttp.web_urldispatcher import DynamicResource
from dataclasses import dataclass


from valera import ValidationException

_T = TypeVar('_T')


class BaseMatcher:
    def match(self, spec_unit: tuple[str, str]) -> bool:
        raise NotImplementedError()


class MethodMatcher(BaseMatcher):
    def __init__(self, mocked_method: Any) -> None:
        self._mocked_method = mocked_method

    def match(self, spec_unit: tuple[str, str]) -> bool:
        print(f"{self._mocked_method} == {spec_unit[0]}", bool(self._mocked_method == spec_unit[0]))
        return bool(self._mocked_method == spec_unit[0])


class _Resource(DynamicResource):
    def match(self, path: str) -> Union[Dict[str, str], None]:
        return self._match(path)


class RouteMatcher(BaseMatcher):
    def __init__(self, mocked_path: str) -> None:
        self._mocked_path = mocked_path
        self._resource = _Resource(mocked_path)

    def match(self, spec_unit: tuple[str, str]) -> bool:
        self._resource_spec = _Resource(spec_unit[1])
        mock = normalize_path(self._mocked_path)
        spec = normalize_path(spec_unit[1])
        print(f"{mock} == {spec}", (mock == spec) or (self._resource_spec.match(self._mocked_path) is not None))
        return (mock == spec) or (self._resource_spec.match(self._mocked_path) is not None)


class AnyMatcher(BaseMatcher):
    def __init__(self, matchers: list[BaseMatcher]) -> None:
        assert len(matchers) > 0
        self._matchers = matchers

    def match(self, spec_unit: tuple[str, str]) -> bool:
        for matcher in self._matchers:
            if matcher.match(spec_unit):
                return True
        return False


class AllMatcher(BaseMatcher):
    def __init__(self, matchers: list[BaseMatcher]) -> None:
        assert len(matchers) > 0
        self._matchers = matchers

    def match(self, spec_unit: tuple[str, str]) -> bool:
        for matcher in self._matchers:
            if not matcher.match(spec_unit):
                return False
        return True


class Validator:
    @staticmethod
    def _check_entity_match(entity_dict: Dict[Tuple[str, str], SchemaData],
                            http_method: str,
                            path: str) -> Optional[SchemaData]:
        normalized_path = normalize_path(path)
        entity_key = (http_method.lower(), normalized_path)
        return entity_dict.get(entity_key)

    @staticmethod
    def create_openapi_matcher(matcher: ResolvableMatcher, prefix: str | None = None) -> BaseMatcher:
        if isinstance(matcher, JJMethodMatcher):
            submatcher = matcher.sub_matcher
            if isinstance(submatcher, JJEqualMatcher):
                spec_matcher = MethodMatcher(mocked_method=submatcher.expected)
                return spec_matcher
        if isinstance(matcher, JJPathMatcher):
            submatcher = matcher.sub_matcher
            if isinstance(submatcher, JJRouteMatcher):
                mocked_path = normalize_path(submatcher.path, prefix=prefix)
                spec_matcher = RouteMatcher(mocked_path=mocked_path)
                return spec_matcher
        if isinstance(matcher, JJAllMatcher):
            submatchers = matcher.sub_matchers
            spec_matcher = AllMatcher(matchers=[Validator.create_openapi_matcher(submatcher, prefix=prefix) for submatcher in submatchers])
            return spec_matcher
        if isinstance(matcher, JJAnyMatcher):
            submatchers = matcher.sub_matchers
            spec_matcher = AnyMatcher(matchers=[Validator.create_openapi_matcher(submatcher, prefix=prefix) for submatcher in submatchers])
            return spec_matcher

    @staticmethod
    def _handle_non_strict_validation_error(parsed_request: Optional[SchemaData],
                                            decoded_mocked_body: Any,
                                            validate_level: Literal["error", "warning", "skip"],
                                            func_name: str) -> None:

        try:
            parsed_request.response_schema_d42 % decoded_mocked_body
        except SubstitutionError as e:
            if validate_level == "error":
                raise ValidationException(f"There are some mismatches in {func_name}:\n{str(e)}")
            elif validate_level == "warning":
                print(f"⚠️ There are some mismatches in {func_name} ⚠️:\n{str(e)}")
            elif validate_level == "skip":
                pass


    @staticmethod
    def validate(mocked: _T,
                 prepared_dict_from_spec: Dict[Tuple[str, str], SchemaData],
                 is_strict: bool,
                 validate_level: Literal["error", "warning", "skip"],
                 func_name: str,
                 prefix: str | None) -> None:
        mock_matcher = mocked.handler.matcher

        # debug_method = MethodMatcher(mocked_method='get')
        # debug_match_method = debug_method.match(spec_unit=('get', '3.0/'))
        #
        # debug_path = RouteMatcher(mocked_path='/2.0/{id}/{another_id}/bob/alice')
        # debug_match_path = debug_path.match(spec_unit=('get', '/2.0/{id_segment}/{id_submodule}/bob/alice'))  # now True, and True exp
        #
        # debug_path_2 = RouteMatcher(mocked_path='/2.0/2352352352/bob/alice')
        # debug_match_path_2 = debug_path_2.match(spec_unit=('get', '/2.0/{id_segment}/bob/alice'))  # now False, but True exp
        #
        # debug_path_3 = RouteMatcher(mocked_path='/2.0/413412341/2352352352/bob/alice')
        # debug_match_path_3 = debug_path_3.match(spec_unit=('get', '/2.0/{id_segment}/{id_submodule}/bob/alice'))  # now False, but True exp
        #
        # debug_all_matcher = AllMatcher(matchers=[debug_method, debug_path])
        # debug_match_all_matcher = debug_all_matcher.match(spec_unit=('post', '/2.0/{id_segment}/{id_submodule}/bob/alice'))
        #
        # debug_any_matcher = AnyMatcher(matchers=[debug_method, debug_path])
        # debug_match_any_matcher = debug_any_matcher.match(spec_unit=('post', '/2.0/{id_segment}/{id_submodule}/bob/alice/a'))
        print("\n  \n")
        spec_matcher = Validator.create_openapi_matcher(matcher=mock_matcher, prefix=prefix)
        print("\n  \n")

        matched_spec_units = [(http_method, path) for http_method, path in prepared_dict_from_spec.keys() if spec_matcher.match((http_method, path))]

        assert len(matched_spec_units) == 1, "matched more than one spec unit or nothing matched"

        spec_unit = prepared_dict_from_spec.get(matched_spec_units[0])

        if spec_unit:
            if spec_unit.response_schema_d42:
                try:
                    # check for JSON in response of mock
                    decoded_mocked_body = loads(mocked.handler.response.get_body().decode())  # type: ignore
                except JSONDecodeError:
                    raise AssertionError(f"JSON expected in Response body of the {func_name}")

                if is_strict:
                    try:
                        validate_or_fail(spec_unit.response_schema_d42, decoded_mocked_body)
                    except ValidationException as e:
                        raise ValidationException(f"There are some mismatches in {func_name}:{str(e)}")

                    Validator._handle_non_strict_validation_error(spec_unit, decoded_mocked_body, validate_level,
                                                                  func_name)
                else:
                    Validator._handle_non_strict_validation_error(spec_unit, decoded_mocked_body, validate_level,
                                                                  func_name)

            else:
                raise AssertionError(f"API method '{prepared_dict_from_spec}' in the spec_link"
                                     f" lacks a response structure for the validation of {func_name}")
        else:
            raise AssertionError(f"API method '{prepared_dict_from_spec}' was not found in the spec_link "
                                 f"for the validation of {func_name}")


def _prepare_data(spec_link: str, prefix: str | None = None) -> Dict[Tuple[str, str], SchemaData]:
    return load_cache(spec_link, prefix=prefix)


def validate_spec(*,
                  spec_link: str | None,
                  is_strict: bool = False,
                  validate_level: Literal["error", "warning", "skip"] = "error",
                  prefix: str | None = None) -> Callable[[Callable[..., _T]], Callable[..., _T]]:
    """
       Validates the jj mock function with given specification lint.

       Args:
           spec_link (str | None): The link to the specification. `None` for disable validation.
           is_strict (bool): WIP, only "False" is working now.
           validate_level (Literal["error", "warning", "skip"]): The validation level. Can be 'error', 'warning', or 'skip'. Default is 'error'.
           prefix (str | None): Prefix is used to cut paths prefix in mock function.
       """
    def decorator(func: Callable[..., _T]) -> Callable[..., _T]:
        func_name = func.__name__

        # non_sctrict_path_matcher = PathMatcher(path='/__reviews__/2.0/reviews/{review_id}/comments')
        # sctrict_path_matcher = PathMatcher(path='/__reviews__/2.0/reviews/123123/comments')
        # test_request_path = '/__reviews__/2.0/reviews/123123/comments'

        @wraps(func)
        async def async_wrapper(*args: object, **kwargs: object) -> _T:
            if spec_link:
                mocked = await func(*args, **kwargs)
                if isinstance(mocked.handler.response, RelayResponse):
                    print("RelayResponse type is not supported")
                    return mocked
                prepared_dict_from_spec = _prepare_data(spec_link, prefix=prefix)
                Validator.validate(mocked, prepared_dict_from_spec, is_strict, validate_level, func_name, prefix)
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
                prepared_dict_from_spec = _prepare_data(spec_link, prefix=prefix)

                Validator.validate(mocked, prepared_dict_from_spec, is_strict, validate_level, func_name, prefix)
            else:
                mocked = func(*args, **kwargs)
            return mocked

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    return decorator
