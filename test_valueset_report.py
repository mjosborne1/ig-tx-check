#!/usr/bin/env python3
"""
Test script to demonstrate the new ValueSet binding report functionality
"""

import os
import json
from tester import run_valueset_binding_report

def create_test_structure_definition():
    """Create a sample StructureDefinition for testing"""
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
                    "binding": {
                        "strength": "required",
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender"
                    }
                },
                {
                    "id": "Patient.maritalStatus",
                    "path": "Patient.maritalStatus",
                    "binding": {
                        "strength": "extensible",
                        "valueSet": "http://hl7.org/fhir/ValueSet/marital-status"
                    }
                }
            ]
        },
        "differential": {
            "element": [
                {
                    "id": "Patient.communication.language",
                    "path": "Patient.communication.language",
                    "binding": {
                        "strength": "preferred",
                        "valueSet": "http://hl7.org/fhir/ValueSet/languages"
                    }
                }
            ]
        }
    }
    return test_sd

def main():
    """Test the ValueSet binding report functionality"""
    # Create test directory structure
    test_dir = "/tmp/test_ig"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create test StructureDefinition file
    test_sd = create_test_structure_definition()
    sd_file = os.path.join(test_dir, "StructureDefinition-test-patient.json")
    
    with open(sd_file, 'w') as f:
        json.dump(test_sd, f, indent=2)
    
    print(f"Created test StructureDefinition: {sd_file}")
    
    # Create output directory
    output_dir = "/tmp/test_reports"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the ValueSet binding report
    npm_path_list = [test_dir]
    config_file = "config/config.json"
    
    print("Running ValueSet binding report...")
    run_valueset_binding_report(npm_path_list, output_dir, config_file)
    
    # Check if the report was created - should now include package name in filename
    report_file = os.path.join(output_dir, "ValueSetBindings-hl7.fhir.au.ereq.html")
    if os.path.exists(report_file):
        print(f"Report generated successfully: {report_file}")
        print("You can open this file in a web browser to view the results.")
    else:
        # Fallback to check default filename
        report_file = os.path.join(output_dir, "ValueSetBindings.html")
        if os.path.exists(report_file):
            print(f"Report generated with default filename: {report_file}")
        else:
            print("Report was not generated.")
    
    # Clean up test files
    os.remove(sd_file)
    os.rmdir(test_dir)
    print("Test completed.")

if __name__ == "__main__":
    main()
