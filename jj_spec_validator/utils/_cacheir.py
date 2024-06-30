from hashlib import md5
from os import makedirs, path, remove
from time import time
from typing import Dict, List, Tuple

from httpx import Response, get
from schemax_openapi import SchemaData, collect_schema_data
from yaml import FullLoader, load

from ._common import normalize_path

__all__ = ('load_cache', )


CACHE_DIR = 'cache_parsed_specs'
CACHE_TTL = 3600  # in second


def _build_entity_dict(entities: List[SchemaData]) -> Dict[Tuple[str, str], SchemaData]:
    entity_dict = {}
    for entity in entities:
        normalized_path = normalize_path(entity.path)
        entity_key = (entity.http_method.lower(), normalized_path)
        entity_dict[entity_key] = entity
    return entity_dict


def _validate_cache_file(filename: str) -> bool:
    if not path.isfile(filename):
        return False

    file_age = time() - path.getmtime(filename)

    if file_age > CACHE_TTL:
        remove(filename)
        return False

    return True


def _get_cache_filename(url: str) -> str:
    hash_obj = md5(url.encode())
    return path.join(CACHE_DIR, hash_obj.hexdigest() + '.cache' + '.yml')


def _download_spec(spec_link: str) -> Response:
    response = get(spec_link)
    response.raise_for_status()
    return response


def _save_cache(spec_link: str) -> str:
    filename = _get_cache_filename(spec_link)

    raw_spec = _download_spec(spec_link)

    data = raw_spec.text

    makedirs(CACHE_DIR, exist_ok=True)
    with open(filename, 'w') as f:
        f.write(data)
    return data


def load_cache(spec_link: str) -> Dict[Tuple[str, str], SchemaData]:
    filename = _get_cache_filename(spec_link)

    if _validate_cache_file(filename):
        with open(filename, 'r') as f:
            data = f.read()
    else:
        data = _save_cache(spec_link)

    raw_schema = load(data, FullLoader)

    parsed_data = collect_schema_data(raw_schema)
    prepared_dict = _build_entity_dict(parsed_data)

    return prepared_dict
