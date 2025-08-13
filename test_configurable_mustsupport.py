#!/usr/bin/env python3
"""
Test script to demonstrate the configurable MustSupport flag functionality
"""

import os
import json
import tempfile
from tester import run_valueset_binding_report

def create_test_structure_definition_mixed():
    """Create a sample StructureDefinition with mixed MustSupport elements for testing"""
    test_sd = {
        "resourceType": "StructureDefinition",
        "id": "test-patient-profile",
        "url": "http://example.org/fhir/StructureDefinition/TestPatient",
        "name": "TestPatientProfile",
        "title": "Test Patient Profile",
        "status": "draft",
        "kind": "resource",
        "abstract": False,
        "type": "Patient",
        "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Patient",
        "derivation": "constraint",
        "snapshot": {
            "element": [
                {
                    "id": "Patient.gender",
                    "path": "Patient.gender",
                    "mustSupport": True,
                    "binding": {
                        "strength": "required",
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender"
                    }
                },
                {
                    "id": "Patient.maritalStatus",
                    "path": "Patient.maritalStatus",
                    # No mustSupport flag - should only appear when require-must-support is false
                    "binding": {
                        "strength": "extensible",
                        "valueSet": "http://hl7.org/fhir/ValueSet/marital-status"
                    }
                },
                {
                    "id": "Patient.telecom.use",
                    "path": "Patient.telecom.use",
                    "mustSupport": True,
                    "binding": {
                        "strength": "preferred",
                        "valueSet": "http://hl7.org/fhir/ValueSet/contact-point-use"
                    }
                }
            ]
        }
    }
    return test_sd

def create_config_with_must_support(require_must_support=True):
    """Create a test config file with the specified MustSupport setting"""
    config = {
        "init": [{
            "mode": "dirty",
            "endpoint": "https://tx.ontoserver.csiro.au/fhir"
        }],
        "valueset-binding-options": {
            "require-must-support": require_must_support,
            "minimum-binding-strength": ["required", "extensible", "preferred"]
        }
    }
    return config

def test_configuration(require_must_support, test_name):
    """Test with a specific configuration"""
    print(f"\n=== Testing {test_name} ===")
    
    # Create test directory structure
    test_dir = f"/tmp/test_ig_config_{test_name.lower().replace(' ', '_')}"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create test StructureDefinition file
    test_sd = create_test_structure_definition_mixed()
    sd_file = os.path.join(test_dir, "StructureDefinition-test-patient.json")
    
    with open(sd_file, 'w') as f:
        json.dump(test_sd, f, indent=2)
    
    # Create config file
    config = create_config_with_must_support(require_must_support)
    config_file = os.path.join(test_dir, "config.json")
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    # Create output directory
    output_dir = f"/tmp/test_reports_config_{test_name.lower().replace(' ', '_')}"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the ValueSet binding report
    npm_path_list = [test_dir]
    
    print(f"Running ValueSet binding report with require-must-support={require_must_support}...")
    run_valueset_binding_report(npm_path_list, output_dir, config_file)
    
    # Check if the report was created
    report_file = os.path.join(output_dir, "ValueSetBindings.html")
    if os.path.exists(report_file):
        print(f"Report generated successfully: {report_file}")
        
        # Read and display relevant parts of the report
        with open(report_file, 'r') as f:
            content = f.read()
            
        # Count ValueSets in the report
        vs_count = content.count('<a href="http://hl7.org/fhir/ValueSet/')
        print(f"ValueSets found in report: {vs_count}")
        
        if require_must_support:
            print("Expected: 2 ValueSets (administrative-gender, contact-point-use) - only MustSupport elements")
        else:
            print("Expected: 3 ValueSets (administrative-gender, marital-status, contact-point-use) - all elements")
        
        # Check specific ValueSets
        has_gender = "administrative-gender" in content
        has_marital = "marital-status" in content
        has_telecom = "contact-point-use" in content
        
        print(f"Contains administrative-gender: {has_gender}")
        print(f"Contains marital-status: {has_marital}")
        print(f"Contains contact-point-use: {has_telecom}")
        
    else:
        print("Report was not generated.")
    
    # Clean up
    os.remove(sd_file)
    os.remove(config_file)
    os.rmdir(test_dir)
    # Leave report directory for inspection
    
    return report_file if os.path.exists(report_file) else None

def main():
    """Test the configurable MustSupport functionality"""
    print("Testing configurable MustSupport flag functionality")
    print("=" * 60)
    
    # Test with MustSupport required (default)
    report1 = test_configuration(True, "MustSupport Required")
    
    # Test with MustSupport not required
    report2 = test_configuration(False, "MustSupport Not Required")
    
    print(f"\n=== Summary ===")
    print("Configuration option 'require-must-support' controls whether elements")
    print("without the mustSupport flag are included in the ValueSet binding report.")
    print(f"")
    print(f"Report with MustSupport required: {report1}")
    print(f"Report with MustSupport not required: {report2}")
    print(f"")
    print("You can open these files in a web browser to compare the differences.")

if __name__ == "__main__":
    main()
