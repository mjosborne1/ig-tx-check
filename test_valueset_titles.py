#!/usr/bin/env python3
"""
Test script to verify ValueSet title retrieval from local packages
"""

import os
from tester import get_valueset_title

def test_valueset_title_retrieval():
    """Test that ValueSet titles are retrieved correctly from local packages"""
    
    print("Testing ValueSet title retrieval from local packages...")
    
    # Test cases for AU eRequesting ValueSets (using actual URLs from the package)
    test_cases = [
        {
            "url": "http://terminology.hl7.org.au/ValueSet/au-erequesting-coverage-type",
            "expected_contains": "Coverage Type"
        },
        {
            "url": "http://terminology.hl7.org.au/ValueSet/au-erequesting-request-status",
            "expected_contains": "RequestStatus"
        }
    ]
    
    # Local package path
    local_packages = ["/Users/osb074/data/ig-tx-check/packages/hl7.fhir.au.ereq#dev"]
    endpoint = "https://tx.ontoserver.csiro.au/fhir"
    
    print(f"Using local packages: {local_packages}")
    print(f"Using endpoint: {endpoint}")
    
    for test_case in test_cases:
        url = test_case["url"]
        expected = test_case["expected_contains"]
        
        print(f"\nTesting: {url}")
        
        if os.path.exists(local_packages[0]):
            title = get_valueset_title(url, endpoint, local_packages)
            print(f"Retrieved title: '{title}'")
            
            if expected.lower() in title.lower():
                print(f"✅ Title contains expected text '{expected}'")
            else:
                print(f"⚠️  Title does not contain expected text '{expected}'")
                
            # Check if it's still showing the ID instead of title
            vs_id = url.split('/')[-1]
            if title == vs_id:
                print(f"❌ Still showing ID '{vs_id}' instead of title")
            else:
                print(f"✅ Showing proper title instead of ID")
        else:
            print(f"⚠️  Local package not found at {local_packages[0]}")
    
    print(f"\n🎉 ValueSet title test completed!")

if __name__ == "__main__":
    test_valueset_title_retrieval()
