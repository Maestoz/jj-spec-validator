from district42.types import (
    DictSchema,
    ListSchema,
    AnySchema,
)
from district42 import GenericSchema
from district42.utils import is_ellipsis
from niltype import Nil
import copy

__all__ = ('get_forced_strict_spec', )


def get_forced_strict_spec(spec_unit_schema: GenericSchema) -> GenericSchema:

    if not isinstance(spec_unit_schema, DictSchema):
        raise ValueError("Expected DictSchema")

    refined_object = copy.deepcopy(spec_unit_schema)

    _remove_ellipsis(refined_object)

    return refined_object

def _remove_ellipsis(schema: GenericSchema) -> None:

    if isinstance(schema, ListSchema):
        _remove_ellipsis(schema.props.type)

    elif isinstance(schema, AnySchema):
        if schema.props.types is not Nil:
            for elem in schema.props.types:
                _remove_ellipsis(elem)

    elif isinstance(schema, DictSchema):
        if schema.props.keys is not Nil:
            for key, (val, is_optional) in list(schema.props.keys.items()):
                if is_ellipsis(key):
                    del schema.props.keys[key]
                else:
                    _remove_ellipsis(val)





