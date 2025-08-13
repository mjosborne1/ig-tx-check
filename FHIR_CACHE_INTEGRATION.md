# FHIR Package Cache Integration

## Overview

The ig-tx-check tool has been updated to use the local FHIR package cache instead of downloading packages via npm from Simplifier. This provides several benefits:

- **Faster execution**: No need to download packages that are already cached
- **Offline capability**: Works without internet connection if packages are already cached
- **Consistency**: Uses the same packages that other FHIR tools (like the IG Publisher) use
- **Efficiency**: Reduces network usage and dependency on external services

## Configuration

Add the FHIR package cache location to your `config/config.json`:

```json
{
    "init": [...],
    "fhir-package-cache": "/Users/osb074/.fhir/packages",
    "valueset-binding-options": {...},
    "packages": [...]
}
```

## Package Resolution

The tool will look for packages in the cache using the following logic:

1. **Exact match**: `{name}#{version}` (e.g., `hl7.fhir.au.ereq#dev`)
2. **Version aliases**: For versions like `dev`, `current`, or `cibuild`, it looks for exact matches
3. **Fallback**: If the exact version isn't found, it uses the most recently modified package with the same name
4. **Error handling**: Clear error messages if packages are not found

## Usage

The existing scripts work the same way:

```bash
python3 main.py
```

Or for individual components:

```python
from getter import get_fhir_packages

paths = get_fhir_packages('clean', '/path/to/data', 'config/config.json')
```

## Backward Compatibility

The old `get_npm_packages()` function is still available and now calls `get_fhir_packages()` internally, so existing code continues to work without changes.

## Testing

Run the test script to verify FHIR cache integration:

```bash
python3 test_fhir_cache.py
```
