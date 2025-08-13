#!/usr/bin/env python3
"""
Test script to demonstrate the ValueSet name cleaning and duplicate profile removal
"""

import os
import json
from tester import run_valueset_binding_report, clean_valueset_name

def test_clean_valueset_name():
    """Test the clean_valueset_name function"""
    print("Testing ValueSet name cleaning function:")
    test_cases = [
        "administrative-gender|4.0.1",
        "MaritalStatus|4.0.1", 
        "contact-point-use|3.0.2",
        "simple-name",
        "complex-name-with-dashes",
        "name|1.2.3|extra"
    ]
    
    for test_case in test_cases:
        cleaned = clean_valueset_name(test_case)
        print(f"  '{test_case}' -> '{cleaned}'")

def create_test_structure_definition_with_duplicates():
    """Create profiles that will generate duplicate entries to test deduplication"""
    
    # Profile 1 - has two bindings to the same ValueSet
    profile1 = {
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
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1"  # id|version format
                    }
                },
                {
                    "id": "Patient.maritalStatus",
                    "path": "Patient.maritalStatus", 
                    "binding": {
                        "strength": "extensible",
                        "valueSet": "http://hl7.org/fhir/ValueSet/marital-status|4.0.1"  # id|version format
                    }
                }
            ]
        },
        "differential": {
            "element": [
                {
                    "id": "Patient.contact.gender",
                    "path": "Patient.contact.gender",
                    "binding": {
                        "strength": "required",
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1"  # Same VS, should deduplicate
                    }
                }
            ]
        }
    }
    
    # Profile 2 - also uses the same ValueSet
    profile2 = {
        "resourceType": "StructureDefinition",
        "id": "test-practitioner-profile",
        "url": "http://example.org/fhir/StructureDefinition/TestPractitioner",
        "name": "TestPractitionerProfile",
        "title": "Test Practitioner Profile",
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
                        "valueSet": "http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1"  # Same VS again
                    }
                }
            ]
        }
    }
    
    return profile1, profile2

def create_config_for_testing():
    """Create a test config file"""
    config = {
        "init": [{
            "mode": "dirty",
            "endpoint": "https://tx.ontoserver.csiro.au/fhir"
        }],
        "valueset-binding-options": {
            "require-must-support": False,  # Include all elements
            "minimum-binding-strength": ["required", "extensible", "preferred"]
        }
    }
    return config

def main():
    """Test the ValueSet name cleaning and duplicate removal"""
    print("Testing ValueSet name cleaning and duplicate profile removal")
    print("=" * 65)
    
    # Test the cleaning function
    test_clean_valueset_name()
    
    print(f"\n" + "=" * 65)
    print("Testing full report generation with duplicates:")
    
    # Create test directory structure
    test_dir = "/tmp/test_ig_cleanup"
    os.makedirs(test_dir, exist_ok=True)
    
    # Create test StructureDefinition files
    profile1, profile2 = create_test_structure_definition_with_duplicates()
    
    sd_file1 = os.path.join(test_dir, "StructureDefinition-test-patient.json")
    with open(sd_file1, 'w') as f:
        json.dump(profile1, f, indent=2)
    
    sd_file2 = os.path.join(test_dir, "StructureDefinition-test-practitioner.json")
    with open(sd_file2, 'w') as f:
        json.dump(profile2, f, indent=2)
    
    # Create config file
    config = create_config_for_testing()
    config_file = os.path.join(test_dir, "config.json")
    with open(config_file, 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"Created test files:")
    print(f"  - Profile 1: {sd_file1} (binds to administrative-gender twice)")
    print(f"  - Profile 2: {sd_file2} (also binds to administrative-gender)")
    print(f"  - ValueSet URLs include |version format")
    
    # Create output directory
    output_dir = "/tmp/test_reports_cleanup"
    os.makedirs(output_dir, exist_ok=True)
    
    # Run the ValueSet binding report
    npm_path_list = [test_dir]
    
    print(f"\nRunning ValueSet binding report...")
    run_valueset_binding_report(npm_path_list, output_dir, config_file)
    
    # Check if the report was created
    report_file = os.path.join(output_dir, "ValueSetBindings.html")
    if os.path.exists(report_file):
        print(f"Report generated successfully: {report_file}")
        
        # Read and analyze the report
        with open(report_file, 'r') as f:
            content = f.read()
        
        print(f"\nAnalyzing the report:")
        
        # Check if version info is cleaned from ValueSet link text (but preserved in URLs)
        has_clean_admin_gender = 'target="_blank">administrative-gender</a>' in content
        has_clean_marital_status = 'target="_blank">marital-status</a>' in content
        
        print(f"  - ValueSet link text is clean (administrative-gender): {has_clean_admin_gender}")
        print(f"  - ValueSet link text is clean (marital-status): {has_clean_marital_status}")
        
        # Count how many times each profile appears in the administrative-gender row specifically
        # This checks for proper deduplication within a single ValueSet
        import re
        admin_gender_row_match = re.search(r'<td><a href="[^"]*administrative-gender[^"]*"[^>]*>administrative-gender</a></td>\s*<td>([^<]*(?:<a[^>]*>[^<]*</a>[^<]*)*)</td>', content)
        
        if admin_gender_row_match:
            admin_gender_profiles = admin_gender_row_match.group(1)
            patient_count_in_admin_row = admin_gender_profiles.count("Test Patient Profile")
            practitioner_count_in_admin_row = admin_gender_profiles.count("Test Practitioner Profile")
            
            print(f"  - In administrative-gender row: 'Test Patient Profile' appears {patient_count_in_admin_row} time(s)")
            print(f"  - In administrative-gender row: 'Test Practitioner Profile' appears {practitioner_count_in_admin_row} time(s)")
        else:
            print(f"  - Could not parse administrative-gender row")
        
        # Count total profile occurrences across all rows (this should be higher since profiles can appear in multiple ValueSets)
        total_patient_count = content.count("Test Patient Profile")
        total_practitioner_count = content.count("Test Practitioner Profile")
        
        print(f"  - Total 'Test Patient Profile' appearances: {total_patient_count}")
        print(f"  - Total 'Test Practitioner Profile' appearances: {total_practitioner_count}")
        
        print(f"\nExpected results:")
        print(f"  - ValueSet link text should be clean (no |version)")
        print(f"  - In administrative-gender row: each profile should appear only once (deduplication)")
        print(f"  - Total appearances can be > 1 if profile uses multiple ValueSets (correct behavior)")
        
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
