#!/usr/bin/env python3
"""
Test script to demonstrate the title-based linking functionality
"""

import os
import json
from tester import run_valueset_binding_report

def create_test_structure_definition_with_titles():
    """Create a sample StructureDefinition with titles for testing"""
    test_sd = {
        "resourceType": "StructureDefinition",
        "id": "test-patient-profile",
        "url": "http://example.org/fhir/StructureDefinition/TestPatient",
        "name": "TestPatientProfile",
        "title": "Test Patient Profile with Custom Title",  # This should appear in links
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
                    "binding": {
                        "strength": "extensible",
                        "valueSet": "http://hl7.org/fhir/ValueSet/marital-status"
                    }
                }
            ]
        }
    }
    return test_sd

def create_second_test_profile_with_title():
    """Create a second profile with a different title"""
    test_sd = {
        "resourceType": "StructureDefinition",
        "id": "test-practitioner-profile",
        "url": "http://example.org/fhir/StructureDefinition/TestPractitioner",
        "name": "TestPractitionerProfile",
        "title": "Advanced Practitioner Profile",  # This should appear in links
        "status": "draft",
        "kind": "resource",
        "abstract": False,
        "type": "Practitioner",
        "baseDefinition": "http://hl7.org/fhir/StructureDefinition/Practitioner",
        "derivation": "constraint",
        "snapshot": {
            "element": [
                {
                    "id": "Practitioner.gender",
                    "path": "Practitioner.gender",
                    "binding": {
                        "strength": "required",
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender"
                    }
                }
            ]
        }
    }
    return test_sd

def create_config_with_titles():
    """Create a test config file"""
    config = {
        "init": [{
            "mode": "dirty",
            "endpoint": "https://tx.ontoserver.csiro.au/fhir"
        }],
        "valueset-binding-options": {
            "require-must-support": False,  # Include all elements to see more examples
            "minimum-binding-strength": ["required", "extensible", "preferred"]
        }
    }
    return config

def main():
    """Test the title-based linking functionality"""
    print("Testing title-based linking functionality for ValueSets and Profiles")
    print("=" * 70)
    
    # Create test directory structure
    test_dir = "/tmp/test_ig_titles"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create test StructureDefinition files
    test_sd1 = create_test_structure_definition_with_titles()
    sd_file1 = os.path.join(test_dir, "StructureDefinition-test-patient.json")
    
    with open(sd_file1, 'w') as f:
        json.dump(test_sd1, f, indent=2)
    
    test_sd2 = create_second_test_profile_with_title()
    sd_file2 = os.path.join(test_dir, "StructureDefinition-test-practitioner.json")
    
    with open(sd_file2, 'w') as f:
        json.dump(test_sd2, f, indent=2)
    
    # Create config file
    config = create_config_with_titles()
    config_file = os.path.join(test_dir, "config.json")
    
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created test files:")
    print(f"  - Profile 1: {sd_file1}")
    print(f"    Name: TestPatientProfile")
    print(f"    Title: Test Patient Profile with Custom Title")
    print(f"  - Profile 2: {sd_file2}")
    print(f"    Name: TestPractitionerProfile") 
    print(f"    Title: Advanced Practitioner Profile")
    print(f"  - Config: {config_file}")
    
    # Create output directory
    output_dir = "/tmp/test_reports_titles"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the ValueSet binding report
    npm_path_list = [test_dir]
    
    print(f"\nRunning ValueSet binding report with title-based linking...")
    run_valueset_binding_report(npm_path_list, output_dir, config_file)
    
    # Check if the report was created
    report_file = os.path.join(output_dir, "ValueSetBindings.html")
    if os.path.exists(report_file):
        print(f"Report generated successfully: {report_file}")
        
        # Read and check for titles in the report
        with open(report_file, 'r') as f:
            content = f.read()
        
        print(f"\nChecking link texts in the report:")
        
        # Check if profile titles are used in links
        has_patient_title = "Test Patient Profile with Custom Title" in content
        has_practitioner_title = "Advanced Practitioner Profile" in content
        
        print(f"  - Uses 'Test Patient Profile with Custom Title': {has_patient_title}")
        print(f"  - Uses 'Advanced Practitioner Profile': {has_practitioner_title}")
        
        # Check if ValueSet titles are fetched (or names as fallback)
        has_admin_gender = "administrative-gender" in content
        has_marital_status = "marital-status" in content
        
        print(f"  - Contains administrative-gender ValueSet: {has_admin_gender}")
        print(f"  - Contains marital-status ValueSet: {has_marital_status}")
        
        print(f"\nExpected behavior:")
        print(f"  - Profile links should show titles instead of names")
        print(f"  - ValueSet links should show titles if available from server, otherwise names")
        print(f"  - Both profiles should be linked to administrative-gender ValueSet")
        
    else:
        print("Report was not generated.")
    
    # Clean up test files
    os.remove(sd_file1)
    os.remove(sd_file2)
    os.remove(config_file)
    os.rmdir(test_dir)
    print(f"\nTest completed. Report available at: {report_file}")

if __name__ == "__main__":
    main()
