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
2. Control discrepancy handling with `validate_level` key: 
   - `"warning"` (default, logs a warning, continues execution)
   - `"error"` (raises exceptions, stops execution)
   - `"skip"` (skips validation)


3. Control the output mode of warning messages with the `output_mode` key:
   - `"std"` (default, prints warnings to stdout)
   - `"file"` (writes warnings to a file)
   
Note: The `output_mode` parameter is only applicable when `validate_level` is set to `"warning"`

4. `is_strict` key will allow choosing between strict and non-strict comparison. False by default.


5. Use the `prefix` key to specify a prefix that should be removed from the paths in the mock function before matching them against the OpenAPI spec.
```python
from jj_spec_validator import validate_spec


@validate_spec(spec_link="http://example.com/api/users/spec.yml", prefix='/__mocked_api__')  # Goes to validate `/users` instead of `/__mocked_api__/users`
async def your_mocked_function():
    matcher = jj.match("GET", "/__mocked_api__/users")
    ...
```
