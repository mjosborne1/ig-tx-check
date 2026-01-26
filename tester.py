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
def get_valueset_title(vs_url, endpoint=None, local_packages=None, binding_name=None):
    """
    Get the title of a ValueSet from its URL
    Try local packages first, then remote terminology server,
    finally fall back to binding name from profile or URL-based name
    
    Args:
        vs_url: ValueSet canonical URL
        endpoint: FHIR terminology server endpoint (optional)
        local_packages: List of local FHIR package paths to search (optional)
        binding_name: Binding name from elementdefinition-bindingName extension (optional)
    
    Returns:
        Clean ValueSet title/name
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
    
    # Try binding name from profile if available
    if binding_name:
        logger.info(f"Using binding name from profile for ValueSet {vs_url}: {binding_name}")
        return clean_valueset_name(binding_name)
    
    # Final fallback to name extracted from URL
    vs_name = vs_url.split('/')[-1] if '/' in vs_url else vs_url
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

def get_valueset_expansion_count(vs_url, endpoint=None):
    """
    Get the expansion count for a ValueSet by calling the $expand operation
    
    Args:
        vs_url: ValueSet URL
        endpoint: FHIR terminology server endpoint
        
    Returns:
        int: Number of concepts in the expansion, or None if expansion failed
    """
    if not endpoint:
        return None
        
    def try_expand(url):
        """Helper function to try expanding a single URL"""
        try:
            headers = {'Accept': 'application/fhir+json'}
            expand_url = f"{endpoint}/ValueSet/$expand?url={quote(url)}&count=0"
            response = requests.get(expand_url, headers=headers, timeout=30)
            
            if response.status_code == 200:
                data = response.json()
                
                # Check if expansion was successful
                if data.get("resourceType") == "ValueSet" and "expansion" in data:
                    expansion = data["expansion"]
                    
                    # Get total count from expansion.total
                    total = expansion.get("total")
                    if total is not None:
                        logger.debug(f"ValueSet {url} expansion count: {total}")
                        return total
                    
                    # Fallback: count contains array if present
                    contains = expansion.get("contains", [])
                    if contains:
                        count = len(contains)
                        logger.debug(f"ValueSet {url} expansion count (from contains): {count}")
                        return count
                        
                    # If neither total nor contains, might be empty set
                    logger.debug(f"ValueSet {url} expansion appears empty")
                    return 0
                    
            logger.debug(f"Failed to expand ValueSet {url}: HTTP {response.status_code}")
            return None
            
        except Exception as e:
            logger.debug(f"Error expanding ValueSet {url}: {e}")
            return None
    
    # First try the original URL
    result = try_expand(vs_url)
    if result is not None:
        return result
    
    # If failed and URL contains version (|), try without version
    if '|' in vs_url:
        unversioned_url = vs_url.split('|')[0]
        logger.debug(f"Retrying expansion without version: {unversioned_url}")
        result = try_expand(unversioned_url)
        if result is not None:
            return result
    
    # If all attempts failed, log warning and return None
    logger.warning(f"Failed to expand ValueSet {vs_url} (tried versioned and unversioned)")
    return None

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
                        
                        # Extract binding name from extension if available
                        binding_name = None
                        if "extension" in el["binding"]:
                            binding_extensions = el["binding"]["extension"]
                            if not isinstance(binding_extensions, (list, tuple)):
                                binding_extensions = [binding_extensions] if binding_extensions is not None else []
                            
                            for ext in binding_extensions:
                                if (isinstance(ext, dict) and 
                                    ext.get("url") == "http://hl7.org/fhir/StructureDefinition/elementdefinition-bindingName" and
                                    "valueString" in ext):
                                    binding_name = ext["valueString"]
                                    break
                        
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
                                    'binding_name': binding_name,  # Add binding name
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
                                                'binding_name': None,  # No binding name available for additional bindings
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
                                            'binding_name': None,  # No binding name available for legacy additional bindings
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
            # This is a Coding object with system and code
            system = code_info.get('system')
            code = code_info.get('code')
            if system and code and isinstance(system, str) and isinstance(code, str) and system.strip() and code.strip():
                result = validate_example_code(endpoint, cs_excluded, file, system, code)
                results.append(result)
            else:
                logging.debug(f'Invalid system or code in coding: system={system}, code={code}')
        elif isinstance(code_info, str):
            # Skip string values - these are usually status codes or other non-coded elements
            logging.debug(f'Skipping string value from FHIRPath expression "{fhirpath_expression}": {code_info}')
        else:
            logging.debug(f'Unexpected type for code_info from expression "{fhirpath_expression}": {type(code_info)} - {code_info}')
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

    # Base FHIRPath expressions for individual resources
    base_expressions = [
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
    
    # Check if this is a Bundle resource and add Bundle-specific expressions
    fhirpath_expressions = base_expressions.copy()
    if resource.get("resourceType") == "Bundle":
        # Add Bundle-specific expressions that traverse into entries
        bundle_expressions = [
            "entry.resource.category.coding",
            "entry.resource.code.coding", 
            "entry.resource.coding",
            "entry.resource.type.coding",
            "entry.resource.status",
            "entry.resource.priority.coding",
            "entry.resource.severity.coding", 
            "entry.resource.clinicalStatus.coding",
            "entry.resource.verificationStatus.coding",
            "entry.resource.intent.coding",
            "entry.resource.use.coding",
            "entry.resource.action.coding",
            "entry.resource.outcome.coding",
            "entry.resource.subType.coding",
            "entry.resource.reasonCode.coding",
            "entry.resource.route.coding",
            "entry.resource.vaccineCode.coding",
            "entry.resource.medicationCodeableConcept.coding",
            "entry.resource.bodySite.coding",
            "entry.resource.relationship.coding",
            "entry.resource.sex.coding",
            "entry.resource.morphology.coding",
            "entry.resource.location.coding",
            "entry.resource.format.coding",
            "entry.resource.class.coding",
            "entry.resource.modality.coding",
            "entry.resource.jurisdiction.coding",
            "entry.resource.topic.coding",
            "entry.resource.contentType.coding",
            "entry.resource.connectionType.coding",
            "entry.resource.operationalStatus.coding",
            "entry.resource.color.coding",
            "entry.resource.measurementPeriod.coding",
            "entry.resource.doseQuantity.coding",
            "entry.resource.substanceCodeableConcept.coding",
            "entry.resource.valueCodeableConcept.coding",
            "entry.resource.valueCoding",
            "entry.resource.valueQuantity.coding",
            "entry.resource.ingredient.itemCodeableConcept.coding",
            "entry.resource.dosageInstruction.route.coding",
            "entry.resource.ingredient.quantity",
            "entry.resource.ingredient.quantity.numerator",
            "entry.resource.ingredient.quantity.denominator"
        ]
        fhirpath_expressions.extend(bundle_expressions)

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
      Results are reported in per-IG html files to avoid overwrite across runs.
    """
    cs_excluded = get_config(testconf, 'codesystem-excluded')
    overall_fail = False

    for ig_folder in npm_path_list:
        ig_suffix = os.path.basename(ig_folder)
        outfile = os.path.join(outdir, f'ExampleCodeSystemChecks-{ig_suffix}.html')

        ig_results = []
        example_dir = os.path.join(ig_folder, "package", "example")

        for ex in get_json_files(example_dir):
            results = search_json_file(endpoint, cs_excluded, ex)
            if results:
                ig_results.extend(results)

        # Output as HTML per IG
        header = ['file','code','system','result','reason']
        df_results = pd.DataFrame(ig_results, columns=header)
        if not df_results.empty and (df_results['result'] == 'FAIL').any():
            overall_fail = True
        html_content = df_results.to_html()

        with open(outfile, "w") as fh:
            fh.write(html_content)
        logger.info(f"Example CodeSystem checks written to: {outfile} ({len(ig_results)} rows)")

    return 1 if overall_fail else 0


def run_valueset_binding_report(npm_path_list, outdir, config_file):
    """
      Generate per-IG reports of ValueSet bindings from FHIR profiles.
      Each IG produces its own HTML with ValueSet and Profile information.
      Filtering based on configuration options for MustSupport and binding strength.
    """
    # Load configuration options with defaults
    try:
        config_options = get_config(config_file, 'valueset-binding-options')
        if config_options is None:
            config_options = {
                "require-must-support": True,
                "minimum-binding-strength": ["required", "extensible", "preferred"]
            }
    except:
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
        ig_suffix = os.path.basename(ig_folder)
        outfile = os.path.join(outdir, f'ValueSetBindings-{ig_suffix}.html')

        logger.info(f'Processing ValueSet bindings for IG folder: {ig_folder}')
        ig_bindings = process_ig_bindings(ig_folder, [], config_options)

        logger.info(f'Total bindings found for {ig_suffix}: {len(ig_bindings)}')

        # Create DataFrame and output as HTML for this IG
        if ig_bindings:
            df_bindings = pd.DataFrame(ig_bindings)

            # Group by ValueSet and aggregate profiles
            grouped = df_bindings.groupby(['valueset_name', 'valueset_url']).agg({
                'profile_name': list,
                'profile_title': list,
                'profile_url': list,
                'binding_name': list
            }).reset_index()

            # Create the final table data with sorting information
            table_data = []
            for _, row in grouped.iterrows():
                vs_name = row['valueset_name']
                vs_url = row['valueset_url']
                profile_names = row['profile_name']
                profile_titles = row['profile_title']
                profile_urls = row['profile_url']
                binding_names = row['binding_name']

                # Get the first non-null binding name for this ValueSet
                binding_name = None
                for bn in binding_names:
                    if bn is not None:
                        binding_name = bn
                    # Get ValueSet title from local packages first, then external server, then binding name
                    vs_title = get_valueset_title(vs_url, endpoint, [ig_folder], binding_name)
                # Get ValueSet title from local packages first, then external server, then binding name
                vs_title = get_valueset_title(vs_url, endpoint, [ig_folder], binding_name)
            
            # Get ValueSet expansion count
            expansion_count = get_valueset_expansion_count(vs_url, endpoint)
            if expansion_count is not None:
                expansion_display = str(expansion_count)
            else:
                expansion_display = "N/A"
            
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
                'Expansion Count': expansion_display,
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
        
        # Prepare IG package information for display
        try:
            packages_config = get_config(config_file, 'packages')
            if packages_config and len(packages_config) > 0:
                ig_info_parts = []
                for pkg in packages_config:
                    name = pkg.get('name', 'unknown')
                    version = pkg.get('version', 'unknown')
                    title = pkg.get('title', name)
                    ig_info_parts.append(f"{title} ({name}#{version})")
                ig_info = ', '.join(ig_info_parts)
            else:
                ig_info = 'Not configured'
        except:
            ig_info = 'Not configured'
        
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
                .valueset-col {{ width: 25%; }}
                .expansion-col {{ width: 10%; text-align: center; }}
                .profiles-col {{ width: 65%; }}
                .info {{ background-color: #ecf0f1; padding: 15px; border-radius: 5px; margin: 15px 0; }}
            </style>
        </head>
        <body>
            <h1>FHIR Profile ValueSet Bindings Report</h1>
            <div class="info">
                <p><strong>Generated on:</strong> {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                <p><strong>Implementation Guide:</strong> {ig_info}</p>
                <p><strong>Total ValueSets found:</strong> {len(table_data)}</p>
                <p><strong>Terminology Server:</strong> {endpoint if endpoint else 'Not configured'}</p>
                <p><strong>Criteria:</strong> {criteria_description}</p>
            </div>
            
            <h2>ValueSet Bindings</h2>
            <table>
                <thead>
                    <tr>
                        <th class="valueset-col">ValueSet</th>
                        <th class="expansion-col">Expansion Count</th>
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
                        <td style="text-align: center;">{row['Expansion Count']}</td>
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
        
        # Create TSV file for cross-server analysis
        try:
            # Create TSV filename with IG ID and server info
            packages_config = get_config(config_file, 'packages')
            if packages_config and len(packages_config) > 0:
                ig_id = packages_config[0].get('name', 'unknown')
            else:
                ig_id = 'unknown'
            
            # Clean server URL for filename (remove protocol, replace special chars)
            server_name = 'no-server'
            if endpoint:
                server_name = endpoint.replace('http://', '').replace('https://', '').replace('/', '_').replace(':', '_')
            
            tsv_filename = f'ValueSetBindings-{ig_id}-{server_name}.tsv'
            tsv_outfile = os.path.join(outdir, tsv_filename)
            
            # Prepare TSV data (remove HTML tags from values)
            tsv_data = []
            for _, row in df_final.iterrows():
                # Extract clean text from HTML links
                import re
                
                # Extract ValueSet name from HTML link
                vs_match = re.search(r'>([^<]+)</a>', row['ValueSet'])
                vs_name = vs_match.group(1) if vs_match else row['ValueSet']
                
                # Extract ValueSet URL from HTML link
                vs_url_match = re.search(r'href="([^"]+)"', row['ValueSet'])
                vs_url = vs_url_match.group(1) if vs_url_match else ''
                
                # Extract profile names from HTML links
                profile_matches = re.findall(r'>([^<]+)</a>', row['Profiles'])
                profile_names = ', '.join(profile_matches) if profile_matches else row['Profiles']
                
                # Extract profile URLs from HTML links
                profile_url_matches = re.findall(r'href="([^"]+)"', row['Profiles'])
                profile_urls = ', '.join(profile_url_matches) if profile_url_matches else ''
                
                tsv_data.append({
                    'ValueSet_Name': vs_name,
                    'ValueSet_URL': vs_url,
                    'Expansion_Count': row['Expansion Count'],
                    'Profile_Names': profile_names,
                    'Profile_URLs': profile_urls,
                    'IG_ID': ig_id,
                    'Terminology_Server': endpoint if endpoint else 'Not configured'
                })
            
            # Write TSV file
            import csv
            with open(tsv_outfile, 'w', newline='', encoding='utf-8') as tsvfile:
                fieldnames = ['ValueSet_Name', 'ValueSet_URL', 'Expansion_Count', 'Profile_Names', 'Profile_URLs', 'IG_ID', 'Terminology_Server']
                writer = csv.DictWriter(tsvfile, fieldnames=fieldnames, delimiter='\t')
                writer.writeheader()
                writer.writerows(tsv_data)
            
            logger.info(f'TSV report written to: {tsv_outfile}')
            
        except Exception as e:
            logger.warning(f'Failed to create TSV file: {e}')
        
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

