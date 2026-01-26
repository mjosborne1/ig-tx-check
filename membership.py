import os
import json
import logging
import requests
from fhirpathpy import evaluate
from utils import get_config, split_node_path

logger = logging.getLogger(__name__)


def validate_code_in_valueset(endpoint, valueset_url, coding):
    """
    Validate a Coding against a ValueSet using $validate-code (POST Parameters)

    Args:
        endpoint: FHIR terminology server base URL
        valueset_url: canonical URL of the ValueSet (may include version after |, e.g., "...ValueSet/foo|4.0.1")
        coding: dict with keys {'system', 'code'}

    Returns:
        dict: {'result': 'PASS'|'CHECK'|'NOT_APPLICABLE', 'reason': str, 'status_code': int}
    """
    try:
        # Split versioned ValueSet URL
        if '|' in valueset_url:
            base_url, version = valueset_url.split('|', 1)
        else:
            base_url = valueset_url
            version = None

        # Build Parameters resource
        parameters = [
            {"name": "url", "valueUri": base_url},
            {"name": "coding", "valueCoding": {"system": coding.get("system"), "code": coding.get("code")}}
        ]
        
        # Add version if present
        if version:
            parameters.insert(1, {"name": "version", "valueString": version})

        params = {
            "resourceType": "Parameters",
            "parameter": parameters
        }
        
        headers = {
            'Accept': 'application/fhir+json',
            'Content-Type': 'application/fhir+json'
        }
        url = f"{endpoint}/ValueSet/$validate-code"
        response = requests.post(url, headers=headers, json=params, timeout=30)
        status = response.status_code
        reason = ''
        result_flag = 'CHECK'
        if status == 200:
            data = response.json()
            validation = evaluate(data, "parameter.where(name = 'result').valueBoolean")
            if isinstance(validation, (list, tuple)) and len(validation) > 0 and validation[0] is True:
                result_flag = 'PASS'
            else:
                # Check if failure is due to missing dependency ValueSet
                msg = evaluate(data, "parameter.where(name = 'message').valueString")
                if isinstance(msg, (list, tuple)) and msg:
                    message_text = msg[0]
                    # Detect missing dependency ValueSet scenario
                    if 'could not be found' in message_text.lower() and 'unable to check' in message_text.lower():
                        result_flag = 'CHECK'
                        reason = f'Cannot validate: dependency ValueSet missing on server - {message_text}'
                    else:
                        result_flag = 'CHECK'
                        reason = 'Not a member of ValueSet'
                else:
                    result_flag = 'CHECK'
                    reason = 'Not a member of ValueSet'
        elif status == 404:
            # Clearer message when ValueSet is absent on the terminology server
            if version:
                reason = f'ValueSet not found on terminology server: {base_url}|{version}'
            else:
                reason = f'ValueSet not found on terminology server (unversioned; no version in binding): {base_url}'
        else:
            # Try to extract operation outcome issue
            try:
                data = response.json()
                msg = evaluate(data, "issue.where(severity='error').details.text")
                if isinstance(msg, (list, tuple)) and msg:
                    reason = msg[0]
                else:
                    reason = f'http status: {status}'
            except Exception:
                reason = f'http status: {status}'
        return {"result": result_flag, "reason": reason, "status_code": status}
    except Exception as e:
        logger.debug(f"Error validating coding in ValueSet {valueset_url}: {e}")
        return {"result": 'CHECK', "reason": f'exception: {e}', "status_code": 0}


def find_profile_by_url(ig_package_dir, profile_url):
    """Locate a StructureDefinition in an IG package directory by its canonical URL"""
    try:
        for root, dirs, files in os.walk(ig_package_dir):
            for file in files:
                if file.startswith("StructureDefinition") and file.endswith(".json"):
                    path = os.path.join(root, file)
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if data.get('resourceType') == 'StructureDefinition' and data.get('url') == profile_url:
                        return path
    except Exception as e:
        logger.debug(f"Error finding profile {profile_url} in {ig_package_dir}: {e}")
    return None


def find_profiles_by_resource_type(ig_package_dir, resource_type):
    """
    Find all profiles in an IG package that constrain a given resource type.
    Returns list of profile paths that have baseDefinition constraining the resource type.
    """
    profiles = []
    try:
        for root, dirs, files in os.walk(ig_package_dir):
            for file in files:
                if file.startswith("StructureDefinition") and file.endswith(".json"):
                    path = os.path.join(root, file)
                    with open(path, 'r') as f:
                        data = json.load(f)
                    if data.get('resourceType') != 'StructureDefinition':
                        continue
                    # Check if this profile constrains the resource type
                    base = data.get('baseDefinition', '')
                    if resource_type in base and data.get('kind') == 'resource':
                        profiles.append(path)
    except Exception as e:
        logger.debug(f"Error finding profiles by resource type {resource_type} in {ig_package_dir}: {e}")
    return profiles


def build_binding_map(profile_path, config_options):
    """
    Build a mapping of element path -> list of bindings from a StructureDefinition.
    Includes main binding, additional-binding extension, and legacy additionalBinding.
    Filters by minimum binding strengths and optional MustSupport.
    """
    bindings = {}
    try:
        with open(profile_path, 'r') as f:
            sd = json.load(f)
        if sd.get('resourceType') != 'StructureDefinition':
            return bindings

        require_must_support = config_options.get("require-must-support", True)
        min_strengths = set(config_options.get("minimum-binding-strength", ["required", "extensible", "preferred"]))

        for view in ("snapshot", "differential"):
            elements = evaluate(sd, f"{view}.element")
            if not isinstance(elements, (list, tuple)):
                elements = [elements] if elements is not None else []
            for el in elements:
                if not isinstance(el, dict):
                    continue
                path = el.get('path')
                if not path:
                    continue
                must_support = el.get('mustSupport', False)
                if require_must_support and not must_support:
                    continue
                # Main binding
                if 'binding' in el:
                    b = el['binding']
                    vs = b.get('valueSet')
                    strength = b.get('strength')
                    if vs and strength in min_strengths:
                        bindings.setdefault(path, []).append({"valueSet": vs, "strength": strength})

                    # additional-binding extension
                    ext = b.get('extension')
                    if ext:
                        if not isinstance(ext, (list, tuple)):
                            ext = [ext]
                        for e in ext:
                            if isinstance(e, dict) and e.get('url') == 'http://hl7.org/fhir/tools/StructureDefinition/additional-binding':
                                nested = e.get('extension') or []
                                if not isinstance(nested, (list, tuple)):
                                    nested = [nested]
                                vs_url = None
                                purpose = None
                                for ne in nested:
                                    if not isinstance(ne, dict):
                                        continue
                                    if ne.get('url') == 'valueSet':
                                        vs_url = ne.get('valueCanonical')
                                    elif ne.get('url') == 'purpose':
                                        purpose = ne.get('valueCode')
                                chosen_strength = purpose if purpose in min_strengths else strength
                                if vs_url and chosen_strength in min_strengths:
                                    bindings.setdefault(path, []).append({"valueSet": vs_url, "strength": chosen_strength})

                    # legacy additionalBinding
                    add = b.get('additionalBinding')
                    if add:
                        if not isinstance(add, (list, tuple)):
                            add = [add]
                        for ab in add:
                            if isinstance(ab, dict):
                                vs2 = ab.get('valueSet')
                                st2 = ab.get('strength')
                                if vs2 and st2 in min_strengths:
                                    bindings.setdefault(path, []).append({"valueSet": vs2, "strength": st2})
    except Exception as e:
        logger.debug(f"Error building binding map from {profile_path}: {e}")
    return bindings


def collect_codings_with_paths(resource):
    """Traverse a resource and collect (path, coding) for any Coding dicts"""
    codings = []

    def walk(node, path):
        if isinstance(node, dict):
            # Detect Coding
            if 'system' in node and 'code' in node and isinstance(node.get('system'), str) and isinstance(node.get('code'), str):
                codings.append((path, {"system": node.get('system'), "code": node.get('code')}))
            for k, v in node.items():
                walk(v, f"{path}.{k}" if path else k)
        elif isinstance(node, list):
            for item in node:
                walk(item, path)

    root_path = resource.get('resourceType') or ''
    walk(resource, root_path)
    return codings


def best_binding_paths(coding_path, binding_keys):
    """
    Find best matching binding paths for a coding path.
    Normalises paths (removing slice names and value[x] polymorphism) before matching
    to avoid mapping extension codings onto unrelated element bindings.
    Returns only the MOST SPECIFIC (longest) match to prevent extension bindings
    from also matching parent element bindings.
    """

    def _normalise(path):
        parts = []
        for seg in path.split('.'):
            if seg.startswith('extension:'):
                parts.append('extension')
            elif seg.startswith('value'):
                parts.append('value')
            else:
                parts.append(seg)
        return '.'.join(parts)

    norm_path = _normalise(coding_path)
    # Some profiles bind at the element level (e.g., Medication.code.extension) while
    # instance codings sit under Medication.code.coding.extension; allow a variant with
    # the first '.coding.' segment removed to match those bindings.
    variants = [norm_path]
    if '.coding.' in norm_path:
        variants.append(norm_path.replace('.coding.', '.', 1))

    norm_keys = [(key, _normalise(key)) for key in binding_keys]
    keys_sorted = sorted(norm_keys, key=lambda kv: len(kv[1]), reverse=True)

    candidates = []

    # First pass: exact and prefix matches
    # If coding is in an extension context (.extension.), only match bindings that also contain .extension.
    coding_in_extension = '.extension.' in norm_path
    
    for raw_key, norm_key in keys_sorted:
        # If coding is in extension but binding is not, skip it (don't match parent element bindings to extension codings)
        if coding_in_extension and '.extension.' not in norm_key:
            continue
            
        for candidate_path in variants:
            if candidate_path == norm_key or candidate_path.startswith(norm_key + '.'):
                candidates.append((raw_key, len(norm_key)))
                break
    
    # Return only the longest (most specific) match(es)
    if candidates:
        max_len = max(c[1] for c in candidates)
        return [c[0] for c in candidates if c[1] == max_len]

    # If nothing and path ends with '.coding' or '.valueCoding', try parent using normalised values
    if coding_path.endswith('.coding') or coding_path.endswith('.valueCoding'):
        parent_norm = norm_path.rsplit('.', 1)[0]
        for raw_key, norm_key in keys_sorted:
            if parent_norm == norm_key or parent_norm.startswith(norm_key + '.') or norm_key.startswith(parent_norm + '.'):
                candidates.append((raw_key, len(norm_key)))
        # Return only the longest match from parent fallback
        if candidates:
            max_len = max(c[1] for c in candidates)
            return [c[0] for c in candidates if c[1] == max_len]

    return []


def run_example_valueset_membership_check(endpoint, config_file, npm_path_list, outdir):
    """
    Check example instance codings against ValueSets bound in referenced profiles.
    If example has no explicit meta.profile, infer profiles from resource type.
    Skips ValueSets in valueset-excluded config.
    Generates per-IG HTML reports to avoid overwrites when switching IGs.
    """

    # Load binding options
    try:
        config_options = get_config(config_file, 'valueset-binding-options') or {}
    except Exception:
        config_options = {}

    # Load excluded ValueSets
    try:
        excluded_vs_config = get_config(config_file, 'valueset-excluded') or []
    except Exception:
        excluded_vs_config = []
    
    # Build set of excluded ValueSet URIs (base URL without version)
    excluded_vs_uris = set()
    for exc in excluded_vs_config:
        uri = exc.get('uri', '')
        if uri:
            # Handle versioned URIs by storing base (without |version)
            base_uri = uri.split('|')[0] if '|' in uri else uri
            excluded_vs_uris.add(base_uri)

    # Load excluded CodeSystems
    try:
        excluded_cs_config = get_config(config_file, 'codesystem-excluded') or []
    except Exception:
        excluded_cs_config = []

    excluded_cs_uris = set()
    cs_reason_map = {}
    for exc in excluded_cs_config:
        uri = exc.get('uri', '')
        if uri:
            base_uri = uri.split('|')[0] if '|' in uri else uri
            excluded_cs_uris.add(base_uri)
            cs_reason_map[base_uri] = exc.get('reason', 'Codesystem is excluded')

    for ig_folder in npm_path_list:
        # Derive a stable filename suffix from the package folder
        ig_suffix = os.path.basename(ig_folder)
        outfile = os.path.join(outdir, f'ExampleValueSetMembershipChecks-{ig_suffix}.html')

        results_rows = []

        example_dir = os.path.join(ig_folder, 'package', 'example')
        package_dir = os.path.join(ig_folder, 'package')
        for ex in glob_json(example_dir):
            try:
                with open(ex, 'r') as f:
                    resource = json.load(f)
                
                # Try to get explicit profiles from meta.profile
                profiles = resource.get('meta', {}).get('profile', []) or []
                if not isinstance(profiles, (list, tuple)):
                    profiles = [profiles]
                profiles = [p for p in profiles if p]  # Filter out empty strings
                
                # Fallback: if no explicit profile, infer from resource type
                resource_type = resource.get('resourceType')
                if not profiles and resource_type:
                    logger.debug(f"No explicit profile for {resource_type} in {ex}, inferring from resource type")
                    inferred_profile_paths = find_profiles_by_resource_type(package_dir, resource_type)
                    if inferred_profile_paths:
                        # Extract URLs from inferred profiles and use those paths directly
                        for profile_path in inferred_profile_paths:
                            try:
                                with open(profile_path, 'r') as pf:
                                    profile_data = json.load(pf)
                                    profile_url = profile_data.get('url')
                                    if profile_url:
                                        profiles.append(profile_url)
                            except Exception:
                                pass
                
                # Build merged binding map from all referenced or inferred profiles
                merged_bindings = {}
                for purl in profiles:
                    profile_path = find_profile_by_url(package_dir, purl)
                    if not profile_path:
                        logger.debug(f"Profile not found for example {ex}: {purl}")
                        continue
                    bmap = build_binding_map(profile_path, config_options)
                    for k, v in bmap.items():
                        merged_bindings.setdefault(k, []).extend(v)

                if not merged_bindings:
                    # No binding info; skip this example
                    continue

                # Collect codings with their resource paths
                codings = collect_codings_with_paths(resource)
                for path, coding in codings:
                    bind_keys = list(merged_bindings.keys())
                    matched_paths = best_binding_paths(path, bind_keys)
                    if not matched_paths:
                        continue
                    for mp in matched_paths:
                        for entry in merged_bindings.get(mp, []):
                            vs_url = entry.get('valueSet')
                            strength = entry.get('strength')

                            # Check if CodeSystem is excluded
                            coding_system = coding.get('system')
                            cs_base = coding_system.split('|')[0] if coding_system and '|' in coding_system else coding_system
                            if cs_base in excluded_cs_uris:
                                reason = f"Codesystem is excluded"
                                if cs_base in cs_reason_map:
                                    reason = f"Codesystem is excluded: {cs_reason_map[cs_base]}"
                                results_rows.append({
                                    'file': split_node_path(ex),
                                    'source': ex,
                                    'path': path,
                                    'binding_path': mp,
                                    'system': coding_system,
                                    'code': coding.get('code'),
                                    'valueset': vs_url,
                                    'strength': strength,
                                    'vs_result': 'EXCLUDED',
                                    'reason': reason
                                })
                                continue
                            
                            # Check if ValueSet is excluded
                            vs_base = vs_url.split('|')[0] if '|' in vs_url else vs_url
                            if vs_base in excluded_vs_uris:
                                # Find the exclusion reason
                                reason = 'ValueSet excluded from validation'
                                for exc in excluded_vs_config:
                                    if exc.get('uri', '').split('|')[0] == vs_base:
                                        reason = exc.get('reason', reason)
                                        break
                                results_rows.append({
                                    'file': split_node_path(ex),
                                    'path': path,
                                    'binding_path': mp,
                                    'system': coding.get('system'),
                                    'code': coding.get('code'),
                                    'valueset': vs_url,
                                    'strength': strength,
                                    'vs_result': 'EXCLUDED',
                                    'reason': reason
                                })
                                continue
                            
                            check = validate_code_in_valueset(endpoint, vs_url, coding)
                            result_status = check['result']
                            result_reason = check['reason']
                            
                            # If validation checked but code not in ValueSet, detect if it's a system mismatch
                            if result_status == 'CHECK' and 'Not a member of ValueSet' in result_reason:
                                # Heuristic: detect system mismatch by checking if coding system is obviously incompatible
                                coding_system = coding.get('system', '').lower()
                                vs_url_lower = vs_url.lower()
                                # If code is from AIR/PBS/MIMS and ValueSet is for SNOMED/LOINC/AMT, mark as NOT_APPLICABLE
                                if ('air-' in coding_system or '/air/' in coding_system or 'pbs' in coding_system or 'mims' in coding_system) and \
                                   ('snomed' in vs_url_lower or 'loinc' in vs_url_lower or 'icd' in vs_url_lower or 'amt' in vs_url_lower):
                                    result_status = 'NOT_APPLICABLE'
                                    result_reason = f'Code system not applicable to this ValueSet'
                                # Reverse scenario: ValueSet is AIR and coding system is SNOMED/LOINC/AMT/ICD
                                elif ('air' in vs_url_lower or 'australian-immunisation-register' in vs_url_lower) and \
                                     ('snomed' in coding_system or 'loinc' in coding_system or 'icd' in coding_system or 'amt' in coding_system):
                                    result_status = 'NOT_APPLICABLE'
                                    result_reason = f'Code system not applicable to this ValueSet'
                            
                            results_rows.append({
                                'file': split_node_path(ex),
                                'source': ex,
                                'path': path,
                                'binding_path': mp,
                                'system': coding.get('system'),
                                'code': coding.get('code'),
                                'valueset': vs_url,
                                'strength': strength,
                                'vs_result': result_status,
                                'reason': result_reason
                            })
            except Exception as e:
                logger.debug(f"Error processing example {ex}: {e}")

        # Output HTML for this IG
        import pandas as pd
        if results_rows:
            # Deduplicate based on (file, path, binding_path, system, code, valueset, strength)
            seen = set()
            deduplicated_rows = []
            for row in results_rows:
                key = (row['file'], row['path'], row['binding_path'], row['system'], row['code'], row['valueset'], row['strength'])
                if key not in seen:
                    seen.add(key)
                    deduplicated_rows.append(row)

            # Build custom HTML with subtle status coloring for CHECK, NOT_APPLICABLE, and EXCLUDED
            columns = ['file','source','path','binding_path','system','code','valueset','strength','vs_result','reason']
            rows = deduplicated_rows
            html_parts = [
                "<!DOCTYPE html>",
                "<html>",
                "<head>",
                "<meta charset=\"utf-8\">",
                "<title>Example ValueSet Membership Checks</title>",
                "<style>",
                "body { font-family: Arial, sans-serif; margin: 20px; }",
                "table { border-collapse: collapse; width: 100%; }",
                "th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }",
                "th { background-color: #f4f6f8; font-weight: bold; }",
                "tr:nth-child(even) { background-color: #fafafa; }",
                ".status-check { background-color: #ffe5e5; }",
                ".status-not-applicable { background-color: #f0f0f0; }",
                ".status-excluded { background-color: #fff3e0; }",
                "h2 { color: #666; font-size: 14px; font-weight: normal; margin: 10px 0 20px 0; }",
                "</style>",
                "</head>",
                "<body>",
                "<h1>Example ValueSet Membership Checks</h1>",
                f"<h2>Terminology Server: {endpoint}</h2>",
                f"<h2>IG Package: {ig_suffix}</h2>",
                "<table>",
                "<thead>",
                "<tr>" + "".join(f"<th>{col}</th>" for col in columns) + "</tr>",
                "</thead>",
                "<tbody>"
            ]

            for r in rows:
                status_class = ""
                if r.get('vs_result') == 'CHECK':
                    status_class = "status-check"
                elif r.get('vs_result') == 'NOT_APPLICABLE':
                    status_class = "status-not-applicable"
                elif r.get('vs_result') == 'EXCLUDED':
                    status_class = "status-excluded"
                html_parts.append("<tr>")
                for col in columns:
                    val = r.get(col, "")
                    if col == 'vs_result' and status_class:
                        html_parts.append(f"<td class=\"{status_class}\">{val}</td>")
                    else:
                        html_parts.append(f"<td>{val}</td>")
                html_parts.append("</tr>")

            html_parts.extend(["</tbody>", "</table>", "</body>", "</html>"])

            with open(outfile, 'w') as fh:
                fh.write("\n".join(html_parts))
            logger.info(f"ValueSet membership checks written to: {outfile} ({len(deduplicated_rows)} unique rows)")
        else:
            # Write minimal empty report for this IG
            empty_html = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <title>Example ValueSet Membership Checks</title>
                <style>
                    body {{ font-family: Arial, sans-serif; margin: 20px; }}
                    h2 {{ color: #666; font-size: 14px; font-weight: normal; margin: 10px 0 20px 0; }}
                </style>
            </head>
            <body>
                <h1>Example ValueSet Membership Checks</h1>
                <h2>Terminology Server: {endpoint}</h2>
                <h2>IG Package: {ig_suffix}</h2>
                <p>No checks performed or no matching bindings found.</p>
            </body>
            </html>
            """
            with open(outfile, 'w') as fh:
                fh.write(empty_html)
            logger.info(f"No ValueSet membership checks found; wrote empty report to: {outfile}")

    return 0


def glob_json(root):
    import glob
    from os.path import isfile
    pattern = f"{root}/*.json"
    for item in glob.glob(pattern):
        if isfile(item):
            yield item
