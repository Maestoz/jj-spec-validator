## Usage

1. Decorate your [mocked](https://pypi.org/project/jj/) function with `@validate_spec()`, passing a link to a YAML OpenAPI spec.
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
2. Control discrepancy handling with `validate_level` key: `"error"` (default, raises error) or `"warning"` (prints warning, continues execution).
```python
@validate_spec(spec_link="http://example.com/spec.yml", validate_level="warning")
```
3. `is_strict` key (in development) will allow choosing between strict and non-strict comparison. Currently, non-strict comparison is used.
