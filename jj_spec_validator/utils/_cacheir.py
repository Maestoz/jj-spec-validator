from hashlib import md5
from os import makedirs, path, remove
from pickle import dump
from pickle import load as pickle_load
from time import time
from typing import Dict, List, Tuple

from httpx import ConnectTimeout, Response, get
from schemax_openapi import SchemaData, collect_schema_data
from yaml import FullLoader, load

__all__ = ('load_cache', )


CACHE_DIR = 'cache_parsed_specs'
CACHE_TTL = 3600  # in second


def _build_entity_dict(entities: List[SchemaData]) -> Dict[Tuple[str, str], SchemaData]:
    entity_dict = {}
    for entity in entities:
        entity_key = (entity.http_method.upper(), entity.path)
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
    try:
        response = get(spec_link)
    except ConnectTimeout:
        raise ConnectTimeout("Timeout occurred while trying to connect to the specified link.")
    response.raise_for_status()
    return response


def _save_cache(spec_link: str, raw_schema) -> None:
    filename = _get_cache_filename(spec_link)
    makedirs(CACHE_DIR, exist_ok=True)
    with open(filename, 'wb') as f:
        dump(raw_schema, f)


def load_cache(spec_link: str) -> Dict[Tuple[str, str], SchemaData]:
    filename = _get_cache_filename(spec_link)

    if _validate_cache_file(filename):
        with open(filename, 'rb') as f:
            raw_schema = pickle_load(f)
    else:
        raw_spec = _download_spec(spec_link)
        data = raw_spec.text
        raw_schema = load(data, FullLoader)
        _save_cache(spec_link, raw_schema)

    parsed_data = collect_schema_data(raw_schema)
    prepared_dict = _build_entity_dict(parsed_data)

    return prepared_dict
