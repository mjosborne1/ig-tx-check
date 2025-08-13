import os
import requests
import os
from os.path import isfile
import json
import glob
import pandas as pd
from urllib.parse import quote
from fhirpathpy import evaluate
from utils import get_config, split_node_path
import logging

##
## get_valueset_title: Attempt to get ValueSet title from URL
##    Try to fetch from terminology server, fallback to name from URL
##
def get_valueset_title(vs_url, endpoint=None, local_packages=None):
    """
    Get the title of a ValueSet from its URL
    First try to find in local packages, then in FHIR package cache, then try terminology server if available
    Otherwise extract name from URL as fallback
    Clean up id|version format to show just the name/title
    """
    vs_name = vs_url.split('/')[-1] if '/' in vs_url else vs_url
    # Remove version suffix for comparison (e.g., "consent-data-meaning|4.0.1" -> "consent-data-meaning")
    base_vs_url = vs_url.split('|')[0] if '|' in vs_url else vs_url
    
    # First try to find ValueSet in local packages
    if local_packages:
        for package_path in local_packages:
            try:
                # Look for ValueSet files in the package
                package_dir = os.path.join(package_path, "package") if os.path.exists(os.path.join(package_path, "package")) else package_path
                
                if os.path.exists(package_dir):
                    for root, dirs, files in os.walk(package_dir):
                        for file in files:
                            if file.startswith("ValueSet") and file.endswith(".json"):
                                file_path = os.path.join(root, file)
                                try:
                                    with open(file_path, 'r') as f:
                                        vs_data = json.load(f)
                                    
                                    # Check with both versioned and unversioned URLs
                                    vs_file_url = vs_data.get("url", "")
                                    if (vs_data.get("resourceType") == "ValueSet" and 
                                        (vs_file_url == vs_url or vs_file_url == base_vs_url)):
                                        # Found the ValueSet locally
                                        title = vs_data.get("title")
                                        if title:
                                            logger.info(f"Found ValueSet title locally: {title}")
                                            return clean_valueset_name(title)
                                        # Fallback to name if no title
                                        name = vs_data.get("name")
                                        if name:
                                            return clean_valueset_name(name)
                                except Exception as e:
                                    logger.debug(f"Error reading ValueSet file {file_path}: {e}")
                                    continue
            except Exception as e:
                logger.debug(f"Error searching for ValueSets in {package_path}: {e}")
                continue
    
    # If not found in local packages, search the entire FHIR package cache
    try:
        fhir_package_cache = get_config('config/config.json', key='fhir-package-cache')
        if fhir_package_cache and os.path.exists(fhir_package_cache):
            logger.info(f"Searching FHIR package cache for ValueSet: {vs_url}")
            for package_dir in os.listdir(fhir_package_cache):
                package_path = os.path.join(fhir_package_cache, package_dir)
                if os.path.isdir(package_path):
                    package_subdir = os.path.join(package_path, "package")
                    if os.path.exists(package_subdir):
                        for file in os.listdir(package_subdir):
                            if file.startswith("ValueSet") and file.endswith(".json"):
                                file_path = os.path.join(package_subdir, file)
                                try:
                                    with open(file_path, 'r') as f:
                                        vs_data = json.load(f)
                                    
                                    # Check with both versioned and unversioned URLs
                                    vs_file_url = vs_data.get("url", "")
                                    if (vs_data.get("resourceType") == "ValueSet" and 
                                        (vs_file_url == vs_url or vs_file_url == base_vs_url)):
                                        # Found the ValueSet in cache
                                        title = vs_data.get("title")
                                        if title:
                                            logger.info(f"Found ValueSet title in cache: {title}")
                                            return clean_valueset_name(title)
                                        # Fallback to name if no title
                                        name = vs_data.get("name")
                                        if name:
                                            logger.info(f"Found ValueSet name in cache: {name}")
                                            return clean_valueset_name(name)
                                except Exception as e:
                                    logger.debug(f"Error reading ValueSet file {file_path}: {e}")
                                    continue
    except Exception as e:
        logger.debug(f"Error searching FHIR package cache: {e}")
    
    # If not found locally, try to fetch from terminology server
    if endpoint:
        try:
            # Try to fetch ValueSet from terminology server
            headers = {'Accept': 'application/fhir+json'}
            response = requests.get(f"{endpoint}/ValueSet?url={vs_url}", headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get("total", 0) > 0 and "entry" in data:
                    valueset = data["entry"][0].get("resource", {})
                    title = valueset.get("title")
                    if title:
                        # Clean up title - remove id|version format if present
                        logger.info(f"Found ValueSet title from terminology server: {title}")
                        return clean_valueset_name(title)
                    # Fallback to name if no title
                    name = valueset.get("name")
                    if name:
                        return clean_valueset_name(name)
        except Exception as e:
            logger.debug(f"Could not fetch ValueSet title from server for {vs_url}: {e}")
    
    # Fallback to name extracted from URL
    logger.warning(f"Could not find title for ValueSet: {vs_url}, using ID: {vs_name}")
    return clean_valueset_name(vs_name)

def clean_valueset_name(name):
    """
    Clean up ValueSet name by removing id|version format
    Examples: 
      "administrative-gender|4.0.1" -> "administrative-gender"
      "MaritalStatus|4.0.1" -> "MaritalStatus" 
    """
    if '|' in name:
        return name.split('|')[0]
    return name

logger = logging.getLogger(__name__)
SKIP_DIRS = ["assets", "temp", "templates"]
EXTS = ["json"]

logger = logging.getLogger(__name__)

##
## process_binding: interogate element binding
##    return valuesets for that category in the Structure Defn
##
def process_binding(category,profile,value_sets):
    with open(profile) as f:
       data = json.load(f)
    if data and data["resourceType"] == "StructureDefinition":         
        snapshot = evaluate(data,f"{category}.element") 
        # Ensure snapshot is iterable
        if not isinstance(snapshot, (list, tuple)):
            snapshot = [snapshot] if snapshot is not None else []
        for el in snapshot:
            # Ensure el is a dict before checking for keys
            if isinstance(el, dict):
                vs_canonical = ""
                if "binding" in el:              
                    if "valueSet" in el["binding"]:
                        vs = el["binding"]["valueSet"]
                        if vs != None:                                  
                            value_sets.append(vs)             
    return value_sets

##
## process_binding_with_profile: interogate element binding and return both valueset and profile info
##    return list of dicts with valueset and profile information
##
def process_binding_with_profile(category, profile, binding_results, config_options):
    with open(profile) as f:
        data = json.load(f)
    if data and data["resourceType"] == "StructureDefinition":
        profile_name = data.get("name", "Unknown Profile")
        profile_title = data.get("title", profile_name)  # Use title if available, fallback to name
        profile_url = data.get("url", "Unknown URL")
        
        # Get configuration options with defaults
        require_must_support = config_options.get("require-must-support", True)
        minimum_binding_strengths = config_options.get("minimum-binding-strength", ["required", "extensible", "preferred"])
        
        snapshot = evaluate(data, f"{category}.element") 
        # Ensure snapshot is iterable
        if not isinstance(snapshot, (list, tuple)):
            snapshot = [snapshot] if snapshot is not None else []
        for el in snapshot:
            # Ensure el is a dict before checking for keys
            if isinstance(el, dict):
                # Check if element is MustSupport (if required by config)
                must_support = el.get("mustSupport", False)
                
                # Apply MustSupport filter based on configuration
                if (not require_must_support or must_support):
                    # Process main binding
                    if "binding" in el and "valueSet" in el["binding"]:
                        vs = el["binding"]["valueSet"]
                        binding_strength = el["binding"].get("strength", "")
                        
                        # Only include if binding strength meets minimum requirements
                        if (vs is not None and 
                            binding_strength in minimum_binding_strengths):
                            
                            # Additional filter for Australian content when MustSupport is not required
                            include_valueset = True
                            if not require_must_support:
                                # Skip international HL7 content, but allow AU-specific content
                                if ('hl7.org/fhir' in vs or 'terminology.hl7.org/' in vs) and 'terminology.hl7.org.au' not in vs:
                                    include_valueset = False
                            
                            if include_valueset:
                                # Extract ValueSet name from URL (last part after /)
                                vs_name = vs.split('/')[-1] if '/' in vs else vs
                                binding_results.append({
                                    'valueset_name': vs_name,
                                    'valueset_url': vs,
                                    'profile_name': profile_name,
                                    'profile_title': profile_title,
                                    'profile_url': profile_url
                                })
                    
                    # Process additional bindings from extensions
                    if "binding" in el and "extension" in el["binding"]:
                        binding_extensions = el["binding"]["extension"]
                        # Ensure binding_extensions is iterable
                        if not isinstance(binding_extensions, (list, tuple)):
                            binding_extensions = [binding_extensions] if binding_extensions is not None else []
                        
                        for binding_ext in binding_extensions:
                            if (isinstance(binding_ext, dict) and 
                                binding_ext.get("url") == "http://hl7.org/fhir/tools/StructureDefinition/additional-binding" and
                                "extension" in binding_ext):
                                
                                # Parse the nested extensions to extract valueSet and purpose
                                vs_url = None
                                purpose = None
                                
                                nested_extensions = binding_ext["extension"]
                                if not isinstance(nested_extensions, (list, tuple)):
                                    nested_extensions = [nested_extensions] if nested_extensions is not None else []
                                
                                for nested_ext in nested_extensions:
                                    if isinstance(nested_ext, dict):
                                        if nested_ext.get("url") == "valueSet":
                                            vs_url = nested_ext.get("valueCanonical")
                                        elif nested_ext.get("url") == "purpose":
                                            purpose = nested_ext.get("valueCode")
                                
                                # If we found a ValueSet in the additional binding
                                if vs_url:
                                    # Use purpose as binding strength if available, otherwise use main binding strength
                                    binding_strength = purpose if purpose in minimum_binding_strengths else el["binding"].get("strength", "")
                                    
                                    # Only include if binding strength meets minimum requirements
                                    if binding_strength in minimum_binding_strengths:
                                        # Additional filter for Australian content when MustSupport is not required
                                        include_valueset = True
                                        if not require_must_support:
                                            # Skip international HL7 content, but allow AU-specific content
                                            if ('hl7.org/fhir' in vs_url or 'terminology.hl7.org/' in vs_url) and 'terminology.hl7.org.au' not in vs_url:
                                                include_valueset = False
                                        
                                        if include_valueset:
                                            # Extract ValueSet name from URL (last part after /)
                                            vs_name = vs_url.split('/')[-1] if '/' in vs_url else vs_url
                                            binding_results.append({
                                                'valueset_name': vs_name,
                                                'valueset_url': vs_url,
                                                'profile_name': profile_name,
                                                'profile_title': profile_title,
                                                'profile_url': profile_url
                                            })
                    
                    # Process legacy additional bindings (for backward compatibility)
                    if "binding" in el and "additionalBinding" in el["binding"]:
                        additional_bindings = el["binding"]["additionalBinding"]
                        # Ensure additional_bindings is iterable
                        if not isinstance(additional_bindings, (list, tuple)):
                            additional_bindings = [additional_bindings] if additional_bindings is not None else []
                        
                        for add_binding in additional_bindings:
                            if isinstance(add_binding, dict) and "valueSet" in add_binding:
                                vs = add_binding["valueSet"]
                                binding_strength = add_binding.get("strength", "")
                                
                                # Only include if binding strength meets minimum requirements
                                if (vs is not None and 
                                    binding_strength in minimum_binding_strengths):
                                    
                                    # Additional filter for Australian content when MustSupport is not required
                                    include_valueset = True
                                    if not require_must_support:
                                        # Skip international HL7 content, but allow AU-specific content
                                        if ('hl7.org/fhir' in vs or 'terminology.hl7.org/' in vs) and 'terminology.hl7.org.au' not in vs:
                                            include_valueset = False
                                    
                                    if include_valueset:
                                        # Extract ValueSet name from URL (last part after /)
                                        vs_name = vs.split('/')[-1] if '/' in vs else vs
                                        binding_results.append({
                                            'valueset_name': vs_name,
                                            'valueset_url': vs,
                                            'profile_name': profile_name,
                                            'profile_title': profile_title,
                                            'profile_url': profile_url
                                        })
    return binding_results

def process_profile(profile,value_sets):
    value_sets = process_binding("snapshot",profile,value_sets)
    value_sets = process_binding("differential",profile,value_sets)
    return value_sets

def process_profile_bindings(profile, binding_results, config_options):
    """Process a profile and collect ValueSet binding information from both differential and snapshot views"""
    # Process differential view (profile customizations)
    binding_results = process_binding_with_profile("differential", profile, binding_results, config_options)
    
    # Also process snapshot view (complete computed view)
    binding_results = process_binding_with_profile("snapshot", profile, binding_results, config_options)
    
    return binding_results

def process_dependencies_for_valuesets(npm_path_list, binding_results, config_options, config_file):
    """
    Process package dependencies to find additional ValueSets that meet binding strength criteria
    """
    dependency_binding_results = []
    processed_packages = set()
    
    for npm_path in npm_path_list:
        package_json_path = os.path.join(npm_path, "package", "package.json")
        if os.path.exists(package_json_path):
            try:
                with open(package_json_path, 'r') as f:
                    package_data = json.load(f)
                
                dependencies = package_data.get("dependencies", {})
                fhir_cache_path = get_config(config_file, key="fhir-package-cache")
                
                if not fhir_cache_path:
                    logger.warning("FHIR package cache path not configured")
                    continue
                
                # Process each dependency
                for dep_name, dep_version in dependencies.items():
                    if dep_name in processed_packages:
                        continue
                    processed_packages.add(dep_name)
                    
                    # Look for the dependency in the FHIR cache
                    dep_pattern = f"{dep_name}#{dep_version}"
                    dep_cache_path = os.path.join(fhir_cache_path, dep_pattern)
                    
                    # Handle version aliases
                    if not os.path.exists(dep_cache_path):
                        import glob
                        matching_deps = glob.glob(os.path.join(fhir_cache_path, f"{dep_name}#*"))
                        if dep_version in ['dev', 'current', 'cibuild'] and matching_deps:
                            for dep_path in matching_deps:
                                if dep_path.endswith(f"#{dep_version}"):
                                    dep_cache_path = dep_path
                                    break
                        
                        if not os.path.exists(dep_cache_path) and matching_deps:
                            # Use most recent version
                            matching_deps.sort(key=os.path.getmtime, reverse=True)
                            dep_cache_path = matching_deps[0]
                    
                    if os.path.exists(dep_cache_path):
                        logger.info(f"Processing dependency: {dep_name}")
                        # Process the dependency package for bindings
                        dep_package_path = os.path.join(dep_cache_path, "package")
                        if os.path.exists(dep_package_path):
                            dependency_binding_results = process_ig_bindings(dep_package_path, dependency_binding_results, config_options)
                    else:
                        logger.warning(f"Dependency package not found in cache: {dep_pattern}")
                        
            except Exception as e:
                logger.error(f"Error processing dependencies for {npm_path}: {e}")
    
    return dependency_binding_results

##
## process_ig: parse the ig folder and find all FHIR Profiles 
##   return valuesets for that IG
##
def process_ig(ig_folder,value_sets):
    # Check if the folder exists
    if os.path.exists(ig_folder):
        # Iterate through files in the folder
        for root, dirs, files in os.walk(ig_folder):
            for file in files:
                if file.startswith("StructureDefinition") and file.endswith(".json"):
                    logger.info(f'...IG Folder: {ig_folder}, Profile file: {file}')
                    file_path = os.path.join(root, file)
                    value_sets = process_profile(file_path,value_sets)
    return value_sets

##
## process_ig_bindings: parse the ig folder and find all FHIR Profiles 
##   return valueset bindings with profile information for that IG
##
def process_ig_bindings(ig_folder, binding_results, config_options):
    # Check if the folder exists
    if os.path.exists(ig_folder):
        # Iterate through files in the folder
        for root, dirs, files in os.walk(ig_folder):
            for file in files:
                if file.startswith("StructureDefinition") and file.endswith(".json"):
                    logger.info(f'...Processing bindings in IG Folder: {ig_folder}, Profile file: {file}')
                    file_path = os.path.join(root, file)
                    binding_results = process_profile_bindings(file_path, binding_results, config_options)
    return binding_results

##
## get_all_files: recursively find all files with a matching file extension
##
def get_all_files(root, exclude=SKIP_DIRS):
    for item in root.iterdir():
        if item.name in exclude:
            continue
        for ext in EXTS:
            if item.name.match(ext):
                yield item
        if item.is_dir():
            yield from get_all_files(item)

##
## get_json_files: find all json files 
##
def get_json_files(root,filter=None):
    if filter == None:
        pattern = "%s/*.json" % (root)
    else:
        pattern = "%s/%s*.json" % (root,filter)
    for item in glob.glob(pattern):
        if isfile(item):
            yield item


def validate_code_with_fhirpath(resource, fhirpath_expression, endpoint, cs_excluded, file):
    results = []
    codes = evaluate(resource, fhirpath_expression)
    # Ensure codes is iterable
    if not isinstance(codes, (list, tuple)):
        codes = [codes] if codes is not None else []
    for code_info in codes:
        if isinstance(code_info, dict):
            system = code_info.get('system')
            code = code_info.get('code')
            if system and code and isinstance(system, str) and isinstance(code, str) and system.strip() and code.strip():
                result = validate_example_code(endpoint, cs_excluded, file, system, code)
                results.append(result)
            else:
                logging.warning(f'Invalid system or code: system={system}, code={code}')
        else:
            logging.warning(f'Unexpected type for code_info: {type(code_info)}')
    return results


def validate_example_code(endpoint, cs_excluded, file, system, code):
    """
       Validate a code from an example resource instance
     
       Return: test_result dict , code and error
    """
    cmd = f'{endpoint}/CodeSystem/$validate-code?url='
    query = cmd + quote(system, safe='') + f'&code={code}'
    headers = {'Accept': 'application/fhir+json'}
    response = requests.get(query, headers=headers)
    data = response.json()
    test_result = {
        'file': split_node_path(file),
        'code': code,
        'system': system,
        'status_code': response.status_code,
        'reason': ''
    }
    excluded = False
    for exc in cs_excluded:
        if exc["uri"] == system:
            test_result['result'] = exc['result']
            test_result['reason'] = exc['reason']
            excluded = True
            break
    if not excluded:
        if response.status_code == 200:
            result_params = evaluate(data, "parameter.where(name = 'result').valueBoolean")
            # Ensure result_params is a list and has elements
            if isinstance(result_params, (list, tuple)) and len(result_params) > 0:
                if result_params[0]:
                    test_result['result'] = 'PASS'
                else:
                    test_result['result'] = 'FAIL'
                    test_result['reason'] = 'Not a valid code'
            else:
                test_result['result'] = 'FAIL'
                test_result['reason'] = 'Unable to parse validation result'
        else:
            test_result['result'] = 'FAIL'
            test_result['reason'] = f'http status: {response.status_code}'
    return test_result


##
## search_json_file: search a json file for FHIR coding elements
##

def search_json_file(endpoint, cs_excluded, file):
    with open(file, 'r') as f:
        resource = json.load(f)

    fhirpath_expressions = [
        "category.coding",
        "code.coding",
        "coding",
        "type.coding",
        "status",
        "priority.coding",
        "severity.coding",
        "clinicalStatus.coding",
        "verificationStatus.coding",
        "intent.coding",
        "use.coding",
        "action.coding",
        "outcome.coding",
        "subType.coding",
        "reasonCode.coding",
        "route.coding",
        "vaccineCode.coding",
        "medicationCodeableConcept.coding",
        "bodySite.coding",
        "relationship.coding",
        "sex.coding",
        "morphology.coding",
        "location.coding",
        "format.coding",
        "class.coding",
        "modality.coding",
        "jurisdiction.coding",
        "topic.coding",
        "contentType.coding",
        "connectionType.coding",
        "operationalStatus.coding",
        "color.coding",
        "measurementPeriod.coding",
        "doseQuantity.coding",
        "substanceCodeableConcept.coding",
        "valueCodeableConcept.coding",
        "valueCoding",
        "valueQuantity.coding",
        "ingredient.itemCodeableConcept.coding",
        "dosageInstruction.route.coding",
        "ingredient.quantity",
        "ingredient.quantity.numerator",
        "ingredient.quantity.denominator"
    ]

    test_result_list = []
    for expression in fhirpath_expressions:
        results = validate_code_with_fhirpath(resource, expression, endpoint, cs_excluded, file)
        if results:
            test_result_list.extend(results)

    return test_result_list


def run_capability_test(endpoint):
    """
       Fetch the capability statement from the endpoint and assert it 
       instantiates http://hl7.org/fhir/CapabilityStatement/terminology-server
    """
    query = f'{endpoint}/metadata'
    headers = {'Accept': 'application/fhir+json'}
    response = requests.get(query, headers=headers)
    if response.status_code == 200:
        data = response.json()
        server_type = evaluate(data, "instantiates[0]")
        fhirVersion = evaluate(data, "fhirVersion")
        
        # Ensure server_type and fhirVersion are lists with elements
        if (isinstance(server_type, (list, tuple)) and len(server_type) > 0 and
            isinstance(fhirVersion, (list, tuple)) and len(fhirVersion) > 0):
            if server_type[0] == "http://hl7.org/fhir/CapabilityStatement/terminology-server" and fhirVersion[0] == "4.0.1":
                return 200  # OK
            else:
                return 418  # I'm a teapot (have we upgraded to a new version??)
        else:
            return 418  # Unable to parse capability statement
    else:
        return response.status_code   # I'm most likely offline


def run_example_check(endpoint, testconf, npm_path_list, outdir):
    """
      Test that the IG example instance codes are in the terminology server
      results of the checks reported in an html file
    """
    outfile = os.path.join(outdir, 'ExampleCodeSystemChecks.html')  
    cs_excluded = get_config(testconf, 'codesystem-excluded')
    all_results = []

    for ig_folder in npm_path_list:
        example_dir = os.path.join(ig_folder, "example")

        for ex in get_json_files(example_dir):
            results = search_json_file(endpoint, cs_excluded, ex)
            all_results.extend(results)
    # Output as HTML  
    # Flatten the list of lists

    header = ['file','code','system','result','reason']
    df_results = pd.DataFrame(all_results, columns=header)
    exit_status = 1 if (df_results['result'] == 'FAIL').any() else 0
    html_content = df_results.to_html()

    with open(outfile, "w") as fh:
        fh.write(html_content)

    return exit_status


def run_valueset_binding_report(npm_path_list, outdir, config_file):
    """
      Generate a report of ValueSet bindings from FHIR profiles
      results reported in an HTML file with ValueSet and Profile information
      Filtering based on configuration options for MustSupport and binding strength
    """
    # Generate filename with package names
    try:
        packages_config = get_config(config_file, 'packages')
        if packages_config and len(packages_config) > 0:
            package_names = [pkg.get('name', 'unknown') for pkg in packages_config]
            package_suffix = '-'.join(package_names)
            filename = f'ValueSetBindings-{package_suffix}.html'
        else:
            filename = 'ValueSetBindings.html'
    except:
        filename = 'ValueSetBindings.html'
    
    outfile = os.path.join(outdir, filename)
    all_bindings = []
    
    # Load configuration options with defaults
    try:
        config_options = get_config(config_file, 'valueset-binding-options')
        if config_options is None:
            config_options = {
                "require-must-support": True,
                "minimum-binding-strength": ["required", "extensible", "preferred"]
            }
    except:
        # Fallback to defaults if config section doesn't exist
        config_options = {
            "require-must-support": True,
            "minimum-binding-strength": ["required", "extensible", "preferred"]
        }
    
    # Get endpoint for ValueSet title lookup
    try:
        endpoint_config = get_config(config_file, 'init')
        endpoint = endpoint_config[0].get('endpoint') if endpoint_config else None
    except:
        endpoint = None

    for ig_folder in npm_path_list:
        logger.info(f'Processing ValueSet bindings for IG folder: {ig_folder}')
        all_bindings = process_ig_bindings(ig_folder, all_bindings, config_options)

    logger.info(f'Total bindings found: {len(all_bindings)}')

    # Create DataFrame and output as HTML
    if all_bindings:
        df_bindings = pd.DataFrame(all_bindings)
        
        # Group by ValueSet and aggregate profiles
        grouped = df_bindings.groupby(['valueset_name', 'valueset_url']).agg({
            'profile_name': list,
            'profile_title': list,
            'profile_url': list
        }).reset_index()
        
        # Create the final table data with sorting information
        table_data = []
        for _, row in grouped.iterrows():
            vs_name = row['valueset_name']
            vs_url = row['valueset_url']
            profile_names = row['profile_name']
            profile_titles = row['profile_title']
            profile_urls = row['profile_url']
            
            # Get ValueSet title from local packages first, then external server
            vs_title = get_valueset_title(vs_url, endpoint, npm_path_list)
            
            # Create ValueSet link using title
            vs_link = f'<a href="{vs_url}" target="_blank">{vs_title}</a>'
            
            # Create profile links using titles (comma separated)
            # Remove duplicates by using a set of URLs to track unique profiles
            seen_urls = set()
            unique_profile_data = []
            for name, title, url in zip(profile_names, profile_titles, profile_urls):
                if url not in seen_urls:
                    seen_urls.add(url)
                    unique_profile_data.append((name, title, url))
            
            # Sort profiles alphabetically by title
            unique_profile_data.sort(key=lambda x: x[1].lower())
            
            # Create the profile links
            unique_profile_links = []
            for name, title, url in unique_profile_data:
                unique_profile_links.append(f'<a href="{url}" target="_blank">{title}</a>')
            profiles_combined = ', '.join(unique_profile_links)
            
            table_data.append({
                'ValueSet': vs_link,
                'Profiles': profiles_combined,
                'sort_title': vs_title.lower()  # Add sorting key
            })
        
        # Sort by ValueSet title alphabetically
        table_data.sort(key=lambda x: x['sort_title'])
        
        # Remove the sorting key from the final data
        for item in table_data:
            del item['sort_title']
        
        # Create DataFrame from processed data
        df_final = pd.DataFrame(table_data)
        
        # Build criteria description
        criteria_parts = []
        if config_options.get("require-must-support", True):
            criteria_parts.append("MustSupport elements")
        else:
            criteria_parts.append("all elements")
        
        min_strengths = config_options.get("minimum-binding-strength", ["required", "extensible", "preferred"])
        criteria_parts.append(f"binding strength: {', '.join(min_strengths)}")
        
        criteria_description = f"Includes ValueSets bound to {criteria_parts[0]} with {criteria_parts[1]} from the main IG package (both snapshot and differential views)."
        
        # Create a more readable HTML with custom styling
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FHIR Profile ValueSet Bindings Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                h2 {{ color: #34495e; margin-top: 30px; }}
                p {{ margin: 10px 0; }}
                table {{ border-collapse: collapse; width: 100%; margin-top: 20px; }}
                th, td {{ border: 1px solid #ddd; padding: 12px; text-align: left; vertical-align: top; }}
                th {{ background-color: #34495e; color: white; font-weight: bold; }}
                tr:nth-child(even) {{ background-color: #f9f9f9; }}
                tr:hover {{ background-color: #f5f5f5; }}
                a {{ color: #3498db; text-decoration: none; }}
                a:hover {{ text-decoration: underline; color: #2980b9; }}
                .valueset-col {{ width: 30%; }}
                .profiles-col {{ width: 70%; }}
                .info {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <h1>FHIR Profile ValueSet Bindings Report</h1>
            <div class="info">
                <p><strong>Generated on:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Total ValueSets found:</strong> {len(table_data)}</p>
                <p><strong>Criteria:</strong> {criteria_description}</p>
            </div>
            
            <h2>ValueSet Bindings</h2>
            <table>
                <thead>
                    <tr>
                        <th class="valueset-col">ValueSet</th>
                        <th class="profiles-col">Profiles</th>
                    </tr>
                </thead>
                <tbody>
        """
        
        # Add table rows
        for _, row in df_final.iterrows():
            html_content += f"""
                    <tr>
                        <td>{row['ValueSet']}</td>
                        <td>{row['Profiles']}</td>
                    </tr>
            """
        
        html_content += """
                </tbody>
            </table>
        </body>
        </html>
        """
        
        with open(outfile, "w") as fh:
            fh.write(html_content)
        
        logger.info(f'ValueSet bindings report written to: {outfile}')
        logger.info(f'Total ValueSets found: {len(table_data)}')
        logger.info(f'Configuration - Require MustSupport: {config_options.get("require-must-support", True)}')
        logger.info(f'Configuration - Minimum binding strengths: {config_options.get("minimum-binding-strength", ["required", "extensible", "preferred"])}')
    else:
        # Build criteria description for empty report
        criteria_parts = []
        if config_options.get("require-must-support", True):
            criteria_parts.append("MustSupport elements")
        else:
            criteria_parts.append("all elements")
        
        min_strengths = config_options.get("minimum-binding-strength", ["required", "extensible", "preferred"])
        criteria_parts.append(f"binding strength: {', '.join(min_strengths)}")
        criteria_description = f"Only includes ValueSets bound to {criteria_parts[0]} with {criteria_parts[1]} from the main IG package."
        
        # Create empty report
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>FHIR Profile ValueSet Bindings Report</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 20px; }}
                h1 {{ color: #2c3e50; }}
                .info {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <h1>FHIR Profile ValueSet Bindings Report</h1>
            <div class="info">
                <p><strong>Generated on:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Criteria:</strong> {criteria_description}</p>
                <p>No ValueSet bindings meeting the criteria were found in the processed profiles.</p>
            </div>
        </body>
        </html>
        """
        
        with open(outfile, "w") as fh:
            fh.write(html_content)
        
        logger.info(f'Empty ValueSet bindings report written to: {outfile}')
        logger.info(f'Configuration - Require MustSupport: {config_options.get("require-must-support", True)}')
        logger.info(f'Configuration - Minimum binding strengths: {config_options.get("minimum-binding-strength", ["required", "extensible", "preferred"])}')

    return 0

