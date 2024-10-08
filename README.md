## Usage

1. Decorate your [mocked](https://pypi.org/project/jj/) function with `@validate_spec()`, providing a link to a YAML or JSON OpenAPI spec.
```python
import jj
from jj.mock import mocked
from jj_spec_validator import validate_spec


@validate_spec(spec_link="http://example.com/api/users/spec.yml")
async def your_mocked_function():
    matcher = jj.match("GET", "/users")
    response = jj.Response(status=200, json=[])
    
    mock = await mocked(matcher, response)
```

2. `is_strict` key allows choosing between strict and non-strict comparison. Non-strict comparison allows you to mock only some fields from the spec. `False` (= non-strict) by default.

3. Use the `prefix` key to specify a prefix that should be removed from the paths in the mock function before matching them against the OpenAPI spec.
```python
from jj_spec_validator import validate_spec


@validate_spec(spec_link="http://example.com/api/users/spec.yml", prefix='/__mocked_api__')  # Goes to validate `/users` instead of `/__mocked_api__/users`
async def your_mocked_function():
    matcher = jj.match("GET", "/__mocked_api__/users")
    ...
```

4. `is_raise_error` key allows raising an error when a mismatch occurs. `False` by default.

5. `force_strict` key allows enforcing strict validation against the downloaded spec. This is useful when the spec is occasionally have all dicts relaxed. `False` by default.