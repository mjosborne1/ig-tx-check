# Focused ValueSet Binding Report

## Overview

The ValueSet binding report has been updated to focus specifically on ValueSets referenced in the main IG package configured in `config.json`, rather than including all dependencies. This provides a much more targeted and relevant report.

## Changes Made

### 1. **Removed Dependency Processing**
- No longer processes AU Base, AU Core, IPS, and other dependency packages
- Focuses only on the main IG specified in config (e.g., `hl7.fhir.au.ereq`)

### 2. **Enhanced View Processing**
- Processes **both** snapshot and differential views for comprehensive coverage
- **Differential view**: Profile customizations and constraints
- **Snapshot view**: Complete computed view with all elements
- No conditional processing based on `require-must-support` setting

### 3. **Dramatically Reduced Results**
- **Before**: 442+ ValueSets (including dependencies)
- **After**: 68-85 ValueSets (main IG only)
- **Report size**: Reduced from 74KB to 17KB

## Configuration

The same configuration options apply:

```json
{
  "valueset-binding-options": {
    "require-must-support": true,
    "minimum-binding-strength": ["required", "extensible", "preferred"]
  }
}
```

## Results

The report now shows only ValueSets that are:
1. **Actually referenced** in the main IG profiles
2. **Meet binding strength criteria** (required, extensible, preferred)
3. **Comply with MustSupport filtering** (if enabled)
4. **Found in both snapshot and differential views**

## Report Features

- Clean HTML output with responsive styling
- Clickable ValueSet and Profile links
- Alphabetical sorting by ValueSet title
- Clear indication that results are from "main IG package"
- Processing information showing both views were analyzed

## Benefits

1. **Focused Results**: Only ValueSets actually used in the target IG
2. **Faster Processing**: No dependency traversal required
3. **Cleaner Reports**: More manageable and relevant output
4. **Better Performance**: Reduced file sizes and processing time
5. **Targeted Analysis**: Easier to identify ValueSets specific to the IG

## Usage

```bash
python3 main.py
```

The report will be generated as `ValueSetBindings-{package-name}.html` in the reports directory, containing only ValueSets referenced within the specified IG package.
