# ValueSet Binding Report with Dependencies and MustSupport

## Overview

The ValueSet binding report has been enhanced to support:

1. **Dependency Processing**: Automatically checks package dependencies for additional ValueSets
2. **MustSupport Element Filtering**: When `require-must-support` is true, checks both differential and snapshot views for MustSupport elements

## Configuration

### require-must-support Setting

```json
{
  "valueset-binding-options": {
    "require-must-support": true,  // or false
    "minimum-binding-strength": ["required", "extensible", "preferred"]
  }
}
```

#### When `require-must-support: true`
- Processes **differential view** (customizations/constraints in the profile)
- Processes **snapshot view** (complete computed view) for MustSupport elements only
- Reports only ValueSets bound to elements marked as `mustSupport: true`
- Includes dependency packages for comprehensive coverage

#### When `require-must-support: false`  
- Processes **differential view only**
- Reports ValueSets bound to all elements meeting binding strength criteria
- Filters out international HL7 content, keeping Australian-specific content
- Includes dependency packages

## Dependency Processing

The system automatically:

1. **Reads package.json** from each processed package
2. **Extracts dependencies** (e.g., hl7.fhir.au.base, hl7.fhir.au.core, hl7.fhir.uv.ips)
3. **Locates dependency packages** in the FHIR package cache
4. **Processes ValueSet bindings** from dependency StructureDefinitions
5. **Combines results** with main package bindings

### Example Dependencies
For AU eRequesting package:
```json
{
  "dependencies": {
    "hl7.fhir.r4.core": "4.0.1",
    "hl7.terminology.r4": "6.5.0", 
    "hl7.fhir.uv.extensions.r4": "5.2.0",
    "hl7.fhir.au.base": "current",
    "hl7.fhir.au.core": "current",
    "hl7.fhir.uv.ips": "current"
  }
}
```

## Report Content

### Enhanced Information
- **Binding counts**: Shows main package vs dependency bindings
- **MustSupport status**: Indicates filtering criteria used
- **Comprehensive coverage**: Includes all relevant ValueSets from entire dependency tree

### Example Output
```
Criteria: Includes ValueSets bound to MustSupport elements with binding strength: required, extensible, preferred. 
Includes 67 bindings from main package and 388 from dependencies.
```

## Performance Impact

- **require-must-support: true**: More comprehensive, processes both views
- **Dependency processing**: Adds processing time but provides complete picture
- **Caching**: Uses local FHIR package cache for fast dependency access

## Benefits

1. **Complete Coverage**: Finds all relevant ValueSets including inherited ones
2. **Accurate Filtering**: MustSupport elements are properly identified
3. **Dependency Awareness**: No ValueSets missed due to inheritance
4. **Configurable**: Can adjust scope based on requirements

## Testing

Run the test suite to verify functionality:

```bash
python3 test_mustsupport_dependencies.py
```

## Typical Results

- **With MustSupport**: ~442 ValueSets (comprehensive)
- **Without MustSupport**: ~250 ValueSets (Australian content only)
- **Dependencies**: Typically adds 300-400 additional bindings from base profiles
