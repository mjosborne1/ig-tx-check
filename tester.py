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

def validate_example_code(endpoint, cs_excluded, file, system, code):
    """
       Validate a code from an example resource instance
     
       Return: test_result dict , code and error
    """
    cmd=f'{endpoint}/CodeSystem/$validate-code?url='
    query= cmd + quote(system,safe='') + f'&code={code}'
    headers = {'Accept': 'application/fhir+json'}
    response = requests.get(query, headers=headers)
    data = response.json()
    test_result = {}
    test_result['file'] = split_node_path(file)
    test_result['code'] = code
    test_result['system'] = system
    test_result['status_code'] = response.status_code
    test_result['reason'] = ''
    excluded = False
    for exc in cs_excluded:
        if exc["uri"] == system:           
            test_result['result'] = f'{exc['result']}'
            test_result['reason'] = f'{exc['reason']}'
            excluded = True
            break
    if not excluded:    
        if response.status_code == 200:
            if evaluate(data,"parameter.where(name = 'result').valueBoolean")[0]:
                test_result['result'] = 'PASS'
            else:
                test_result['result'] = 'FAIL'       
                test_result['reason'] = 'Not a valid code'
        else:            
            test_result['result'] = 'FAIL'
            test_result['reason'] = f'http status: {response.status_code}'
    return test_result


def check_value_quantity_code(endpoint, cs_excluded, file, value_quantity):
    """
    Check if the valueQuantity.code is a valid code.
    
    Args:
        endpoint: The FHIR server base URL.
        cs_excluded: A list of code systems to ignore during validation.
        file: The file containing the resource.
        value_quantity: The valueQuantity object from the Observation resource.
        
    Returns:
        result: A dict with the validation result.
    """
    results = []
    
    if isinstance(value_quantity, dict) and 'code' in value_quantity and 'system' in value_quantity:
        code = value_quantity['code']
        system = value_quantity['system']
        result = validate_example_code(endpoint, cs_excluded, file, system, code)
        results.append(result)
        logging.info(f'check_value_quantity_code: {code} {system}')
    elif isinstance(value_quantity.values(), dict):
        for kv in value_quantity.values.items():
            if 'code' in kv:
                code = kv['code']
                system = kv["system"]
                result = validate_example_code(endpoint, cs_excluded, file, system, code)
                results.append(result) 

    return results

def check_ingredient_code(endpoint, cs_excluded, file, ingredient):
    """
    Check if the valueQuantity.code and substanceCodeableConcept.coding.code are valid codes.
    
    Args:
        endpoint: The FHIR server base URL.
        cs_excluded: A list of code systems to ignore during validation.
        file: The file containing the resource.
        ingredient: The ingredient object from the Medication resource.
        
    Returns:
        result: A list with the validation results.
    """
    results = []
    
    def process_coding(coding):
        for code_info in coding:
            system = code_info.get('system')
            code = code_info.get('code')
            if system and code:
                result = validate_example_code(endpoint, cs_excluded, file, system, code)
                results.append(result)
                logging.info(f'check_ingredient_code: {code} {system}')
    
    if isinstance(ingredient, list):
        for item in ingredient:
            if isinstance(item, dict):
                # Check quantity codes
                quantity = item.get('quantity', {})
                numerator = quantity.get('numerator', {})
                denominator = quantity.get('denominator', {})
                
                for q in [numerator, denominator]:
                    system = q.get('system')
                    code = q.get('code')
                    if system and code:
                        result = validate_example_code(endpoint, cs_excluded, file, system, code)
                        results.append(result)
                        logging.info(f'check_ingredient_code: {code} {system}')
                
                # Check substanceCodeableConcept codes
                substance = item.get('substanceCodeableConcept', {})
                coding = substance.get('coding', [])
                if coding:
                    process_coding(coding)
        
    return results

##
## check_extension: check that the values in the extension are valid
##
def process_extension(endpoint, cs_excluded, file, ele):
    results = []
    extensions = ele.get('extension', [])
    for ext in extensions:
        value_coding = ext.get('valueCoding', {})
        ext_system = value_coding.get('system')
        ext_code = value_coding.get('code')
        if ext_system and ext_code:
            result = validate_example_code(endpoint, cs_excluded, file, ext_system, ext_code)
            results.append(result)
            logging.info(f'check_ingredient_code (extension): {ext_code} {ext_system}')
    return results

##
## check_coding: check if the item is a FHIR coding and print the values
##
def check_coding(endpoint, cs_excluded, file, itm):
    results = []
    
    def process_item(item):
        if 'coding' in item:
            codes = evaluate(item['coding'], 'code')
            systems = evaluate(item['coding'], 'system')
            for index, code in enumerate(codes):
                system = systems[index]
                results.append(validate_example_code(endpoint, cs_excluded, file, system, code))
                logging.info(f'check_coding: {code} {system}')
             # Process extensions within coding
            for coding_item in item['coding']:
                results.extend(process_extension(endpoint, cs_excluded, file, coding_item))
        elif isinstance(item.values(), dict):
            for kv in item.values().items():
                if 'coding' in kv:
                    codes = evaluate(kv['coding'], 'code')
                    systems = evaluate(kv['coding'], 'system')
                    for index, code in enumerate(codes):
                        system = systems[index]
                        results.append(validate_example_code(endpoint, cs_excluded, file, system, code))
                        logging.info(f'check_coding: {code} {system}')
                    # Process extensions within coding
                    for coding_item in kv['coding']:
                        results.extend(process_extension(endpoint, cs_excluded, file, coding_item))
    if isinstance(itm, list):
        for element in itm:
            if isinstance(element, dict):                
                process_item(element)
    elif isinstance(itm, dict):
        process_item(itm)
    
    return results

def check_dosage_instruction(endpoint, cs_excluded, file, dosage_instruction):
    """
    Check the coding in the dosageInstruction and doseAndRate elements.
    
    Args:
        endpoint: The FHIR server base URL.
        cs_excluded: A list of code systems to ignore during validation.
        file: The file containing the resource.
        dosage_instruction: The dosageInstruction element from the MedicationRequest resource.
        
    Returns:
        result: A list with the validation results.
    """
    results = []
    
    if isinstance(dosage_instruction, list):
        for instruction in dosage_instruction:
            if isinstance(instruction, dict):
                # Check route codes
                route = instruction.get('route', {})
                coding = route.get('coding', [])
                if coding:
                    results.extend(check_coding(endpoint, cs_excluded, file, coding))
                
                # Check doseAndRate codes
                dose_and_rate = instruction.get('doseAndRate', [])
                for dose_rate in dose_and_rate:
                    dose_quantity = dose_rate.get('doseQuantity', {})
                    system = dose_quantity.get('system')
                    code = dose_quantity.get('code')
                    if system and code:
                        result = validate_example_code(endpoint, cs_excluded, file, system, code)
                        results.append(result)
                        logging.info(f'check_dosage_instruction: {code} {system}')
    
    return results

##
## search_json_file: search a json file for FHIR coding elements
##
def search_json_file(endpoint,cs_excluded,file,test_result_list):
    with open(file, 'r') as f:
        data = json.load(f)
        if isinstance(data,dict):
            for kv in data.items():
                element = kv[0]
                value = kv[1]
                results = {}
                if element in ('code','vaccineCode','medicationCodeableConcept','category','type', 'bodySite', 'reasonCode'):
                    results = check_coding(endpoint,cs_excluded,file,value)
                elif element in  ('valueQuantity'):
                    results = check_value_quantity_code(endpoint,cs_excluded,file,value)
                elif element in ('ingredient'):
                    results = check_ingredient_code(endpoint,cs_excluded,file,value)
                elif element in ('dosageInstruction'):
                    results = check_dosage_instruction(endpoint, cs_excluded, file, value)
                if results:
                    test_result_list.append(results)
    return test_result_list

##
## get_valueset_definition
## Generic ValueSet definition getter
## return: ValueSet as json string
def get_valueset_definition(endpoint,uri):
    vsexp = f'{endpoint}/ValueSet?url='
    vs_version = ""
    vs_url = uri
    if "|" in vs_url :
        uri, vs_version = vs_url.split("|")
    query = vsexp + quote(uri, safe='')
    if vs_version != "":
        query += f'&version={vs_version}'
    headers = {'Accept': 'application/fhir+json'}
    response = requests.get(query, headers=headers)

    test_result = {}
    test_result['status_code'] = response.status_code

    if response.status_code == 200:
        data = response.json()
        # Evaluate the result as an OperationOutcome
        test_result['result'] = 'OK'
        test_result['valsetdef'] = evaluate(data,'entry[0].resource[0]')
        test_result['id'] = evaluate(test_result['valsetdef'],'id')
    if response.status_code == 400 or response.status_code == 422:
        # Check if the error is an OperationOutcome (FHIR's "error" resource)
        try:
            error_data = response.json()
            try:
                issue = evaluate(error_data,"issue")
                test_result['result'] = f'{issue}'
            except:
                test_result['result'] = f'{error_data}'
        except (requests.exceptions.JSONDecodeError, Exception):
            test_result['result']= f'error unknown'
    return test_result


def run_capability_test(endpoint):
    """
       Fetch the capability statement from the endpoint and assert it 
       instantiates http://hl7.org/fhir/CapabilityStatement/terminology-server
    """
    server_type = fhirVersion = []
    query = f'{endpoint}/metadata'
    headers = {'Accept': 'application/fhir+json'}
    response = requests.get(query, headers=headers)
    if response.status_code == 200:
        data = response.json()
        server_type = evaluate(data,"instantiates[0]")
        fhirVersion = evaluate(data,"fhirVersion")
        if server_type[0] == "http://hl7.org/fhir/CapabilityStatement/terminology-server" and fhirVersion[0] == "4.0.1":
            return "200"  # OK
        else:
            return "418"  # I'm a teapot (have we upgraded to a new version??)
    else:
        return response.status_code   # I'm most likely offline



def run_example_check(endpoint, testconf, npm_path_list, outdir):
    """
      Test that the IG example instance codes are in the terminology server
      results of the checks reported in an html file
    """
    outfile = os.path.join(outdir,'ExampleCodeSystemChecks.html')  
    cs_excluded = get_config(testconf, 'codesystem-excluded')
    data = []
    exit_status = 0
    for ig_folder in npm_path_list:
        example_dir = os.path.join(ig_folder,"example")
        example_list = get_json_files(example_dir)
        for ex in example_list:
            data = search_json_file(endpoint,cs_excluded,ex,data)
    # Output as HTML  
    # Flatten the list of lists
    fdata = [item for sublist in data for item in sublist]
    header = ['file','code','system','result','reason']
    df_results = pd.DataFrame(fdata,columns=header)
    if (df_results['result']=='FAIL').any():
        exit_status = 1
    html = df_results.to_html()
    if os.path.exists(outfile):
        os.remove(outfile)
    with open(outfile,"w") as fh:
        fh.write(html)

    return exit_status
