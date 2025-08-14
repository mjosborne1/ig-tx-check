#!/usr/bin/env python3

import os
import sys
from tester import get_valueset_expansion_count

def test_international_server():
    """Test expansion with international terminology server"""
    
    # Test a few ValueSets with both servers
    test_valuesets = [
        "http://hl7.org/fhir/ValueSet/administrative-gender|4.0.1",
        "http://hl7.org/fhir/uv/ips/ValueSet/allergies-intolerances-uv-ips"
    ]
    
    servers = [
        ("AU Server", "https://tx.dev.hl7.org.au/fhir"),
        ("International Server", "https://tx.fhir.org")
    ]
    
    for server_name, endpoint in servers:
        print(f"\n=== Testing {server_name} ({endpoint}) ===")
        for vs_url in test_valuesets:
            print(f"Testing: {vs_url}")
            count = get_valueset_expansion_count(vs_url, endpoint)
            if count is not None:
                print(f"  ✅ Expansion successful: {count} concepts")
            else:
                print(f"  ❌ Expansion failed")

if __name__ == '__main__':
    test_international_server()
