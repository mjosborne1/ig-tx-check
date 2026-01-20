### Installation Requirements
- Python3 and the ability to install modules using pip. This will be automatic through the requirements file.
- A file path for the output of the process, on Windows this might be C:\data\ig-tx-check\ 
  on Mac/Linux it will be `/home/user/data/ig-tx-check` or similar where `user` is your account name


### How to install this script 
   * `git clone https://github.com/mjosborne1/ig-tx-check.git`
   * `cd ig-tx-check`
   * `virtualenv .venv`
   * `source ./.venv/bin/activate`
   * `pip install -r requirements.txt`

### How to run the script
   * Update `./config/config.json` to match the name and version of the package to be checked e.g.  
   ```       
        "name" : "hl7.fhir.au.base",             // name of the package on simplifier.net
        "version" : "4.2.2-preview",             // version of the package
        "title" : "AU Base Implementation Guide" // human readable description to aid debugging etc...            
   ```
   * ensure the virtual environment is set
      * Mac/Linux/WSL: `source ./.venv/bin/activate`
      * Windows CMD/Powershell: `.\.venv\Scripts\activate`
   * `python main.py --rootdir /path/to/data/folder`  rootdir defaults to $HOME/data/ig-tx-check
   ```
        ig-tx-check % python main.py -h
        usage: main.py [-h] [-r ROOTDIR]

        options:
        -h, --help            show this help message and exit
        -r ROOTDIR, --rootdir ROOTDIR
                                Root data folder
   ```    

### Output
    * Example code validation HTML: `ExampleCodeSystemChecks.html`
    * Focused ValueSet bindings HTML: `ValueSetBindings-<package-names>.html`
    * Cross-server analysis TSV: `ValueSetBindings-<ig-id>-<server>.tsv`

---

### Features
- Terminology server check: Verifies `CapabilityStatement` instantiates a terminology server and `fhirVersion` is `4.0.1`.
- FHIR package cache integration: Uses your local FHIR package cache instead of npm for faster, offline-friendly runs (see `FHIR_CACHE_INTEGRATION.md`).
- Example instance code validation: Scans IG examples and validates codes via `$validate-code` against `CodeSystem`, generating `ExampleCodeSystemChecks.html`.
- ValueSet bindings report: Builds a focused report of ValueSets referenced in the main IG package (both snapshot and differential views), sorted by ValueSet title.
- Configurable filtering: Control inclusion via `valueset-binding-options` (e.g., `require-must-support`, `minimum-binding-strength`).
- ValueSet titles and counts: Resolves ValueSet titles from local packages or the terminology server and shows expansion counts via `$expand`.
- TSV export: Writes a TSV file to support cross-server comparisons.

### Configuration
Update `./config/config.json` with these keys:

```json
{
   "init": [
      { "endpoint": "https://tx.hl7.org.au/fhir" }
   ],
   "fhir-package-cache": "/Users/<you>/.fhir/packages",
   "packages": [
      {
         "name": "hl7.fhir.au.ereq",
         "version": "dev",
         "title": "AU eRequesting Implementation Guide"
      }
   ],
   "codesystem-excluded": [
      {
      "uri": "http://www.mims.com.au/codes",
      "result": "MANUAL",
      "reason": "Manual validation required: MIMS is a proprietary code system, not published as a FHIR resource as yet"
      },
      {
         "uri": "http://www.whocc.no/atc",
         "result": "MANUAL",
         "reason": "Manual validation required: WHO ATC classification system is not published as a FHIR resource as yet"
      },
      {
         "uri": "http://example.acme.com.au/generic-packages",
         "result": "IGNORED",
         "reason": "Codes from 'example' code systems can not be validated, they are essentially local codes"
      },
      {
         "uri": "http://pbs.gov.au/code/item",
         "result": "MANUAL",
         "reason": "Manual validation required: PBS licensing prevents publishing of this code system as a FHIR resource."
      }
   ],
   "valueset-binding-options": {
      "require-must-support": true,
      "minimum-binding-strength": ["required", "extensible", "preferred"]
   }
}
```

Notes:
- `fhir-package-cache` points to your local FHIR cache; version aliases like `dev`/`current` are supported with sensible fallbacks.
- `packages` can include multiple IGs; the report filename will reflect configured package names.
- `valueset-binding-options` controls filtering; see `FOCUSED_VALUESET_REPORT.md` for behavior and scope.

### Run

```bash
# Activate venv
source ./.venv/bin/activate

# Run with default rootdir ($HOME/data/ig-tx-check)
python main.py

# Or specify a custom root directory for reports and local packages
python main.py --rootdir /path/to/data/ig-tx-check
```

Reports are written to `$rootdir/reports`.