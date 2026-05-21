# Improvement Suggestions

_Analysis as of current code. Previously fixed: typos, `write_config` creates missing file and
directory, `random.sample` → `secrets.token_hex(8)`, `get_caller_identity` documented,
variable shadowing (`profiles` → `profiles_to_assume`), wildcard import, error message uses
`profile['name']`, `not x in y` → `x not in y`. All-or-nothing error strategy is intentional._

---

## Critical Bugs

### 1. Non-MFA path is broken
When `mfa_serial` is absent from a profile, the code silently assigns the sentinel string
`'no-mfa'` and then passes it as the AWS `SerialNumber` to `get_session_token`. AWS will
reject the call. Either raise a `ConfigurationException` immediately to give the user a clear
message, or implement a separate code path that skips `get_session_token` and calls
`assume_role` directly using the base-profile session.

### 2. `RoleSessionName` can exceed the 64-character AWS limit
```python
RoleSessionName=session_name + secrets.token_hex(8)
```
`session_name` is the IAM username (up to 64 characters). `secrets.token_hex(8)` adds 16
more characters, so the combined value can reach 80 characters. AWS enforces a hard 64-character
limit on `RoleSessionName` and will reject the call for any user whose username is longer than
48 characters. Truncate `session_name` before concatenation, e.g.:
```python
RoleSessionName=session_name[:48] + secrets.token_hex(8)
```

---

## Code Quality

### 3. String concatenation mixed with f-string in the entry point
`aws-get-creds.py` line 8:
```python
print(f"Error while fetching the credentials:\n\t" + err.__str__())
```
Mixing an f-string with `+` concatenation is inconsistent. Use a single f-string:
```python
print(f"Error while fetching the credentials:\n\t{err}")
```

### 4. `os.path.dirname` returns an empty string for a bare filename
`write_config` calls `os.makedirs(os.path.dirname(path), ...)`. If `path` were ever a bare
filename with no directory component, `os.path.dirname` returns `''` and `os.makedirs('')`
raises `FileNotFoundError`. For the current hardcoded path this is harmless, but it makes
`write_config` fragile if the path is ever passed in externally. Guard with:
```python
parent = os.path.dirname(path)
if parent:
    os.makedirs(parent, exist_ok=True)
```

---

## Documentation

### 5. README incorrectly tells the user to create `~/.aws/credentials` manually
The README currently says:
> Make sure that `~/.aws/credentials` file exists in your home directory

This is outdated — `write_config` now creates the file automatically. The instruction should
be removed or replaced with a note that the file will be created if absent.

---

## Configuration / UX

### 6. MFA token duration hardcoded at the minimum (900 s)
`DurationSeconds=900` in `get_session_token` is the absolute AWS minimum. With many profiles
to process, the token may expire mid-run. Make the duration configurable via an optional INI
key (e.g. `mfa_duration`) with a sensible default such as `3600`.

### 7. Role session duration hardcoded
`DurationSeconds=3600` in `assume_role` is not configurable. Expose it as an optional
per-profile INI key (e.g. `duration`) so users can adjust it within the limits set by the
role's trust policy.

### 8. Config paths are not overridable
The config and credentials paths are hardcoded class attributes with no way to override them
without modifying the source. Accepting them as constructor arguments (or reading from
environment variables such as `AWS_GET_CREDS_CONFIG`) would also make the class properly
testable without touching the real `~/.aws/` directory.

### 9. No support for roles without MFA
Roles that do not require MFA are a common use case. The code acknowledges this
("not supported yet") but provides no path forward. Directly related to bug #1.

---

## Testing

### 10. No tests
There are no automated tests. `parse_configuration`, `assume_role`, and `write_config` are
all unit-testable with mocked boto3 clients. A `pytest` suite using `moto` (AWS mock library)
would catch regressions and validate edge cases without needing real AWS credentials.
