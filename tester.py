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
        for el in snapshot:
            vs_canonical = ""
            if "binding" in el:              
                if "valueSet" in el["binding"]:
                    vs = el["binding"]["valueSet"]
                    if vs != None:                                  
                        value_sets.append(vs)             
    return value_sets

def process_profile(profile,value_sets):
    value_sets = process_binding("snapshot",profile,value_sets)
    value_sets = process_binding("differential",profile,value_sets)
    return value_sets

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
            if evaluate(data, "parameter.where(name = 'result').valueBoolean")[0]:
                test_result['result'] = 'PASS'
            else:
                test_result['result'] = 'FAIL'
                test_result['reason'] = 'Not a valid code'
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
        if server_type[0] == "http://hl7.org/fhir/CapabilityStatement/terminology-server" and fhirVersion[0] == "4.0.1":
            return 200  # OK
        else:
            return 418  # I'm a teapot (have we upgraded to a new version??)
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

