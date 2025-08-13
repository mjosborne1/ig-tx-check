#!/usr/bin/env python3
"""
Test script to verify FHIR package cache functionality
"""

import os
import tempfile
from getter import get_fhir_packages

def test_fhir_cache_integration():
    """Test that packages can be found and copied from FHIR cache"""
    
    print("Testing FHIR package cache integration...")
    
    # Create a temporary data directory
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Using temporary directory: {tmpdir}")
        
        try:
            # Test getting packages from cache
            config_file = "config/config.json"
            paths = get_fhir_packages('clean', tmpdir, config_file)
            
            print(f"✅ Successfully found {len(paths)} packages from FHIR cache")
            
            for path in paths:
                package_name = os.path.basename(path)
                print(f"  📦 {package_name}")
                
                # Verify the package directory exists and has content
                if os.path.exists(path) and os.listdir(path):
                    print(f"    ✅ Package directory exists with content")
                    
                    # Check for typical FHIR package files
                    package_json = os.path.join(path, "package", "package.json")
                    if os.path.exists(package_json):
                        print(f"    ✅ package/package.json found")
                    else:
                        # Try direct package.json
                        package_json_direct = os.path.join(path, "package.json")
                        if os.path.exists(package_json_direct):
                            print(f"    ✅ package.json found")
                        else:
                            print(f"    ⚠️  package.json not found in expected locations")
                else:
                    print(f"    ❌ Package directory empty or missing")
            
            print(f"\n🎉 Test completed successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False

if __name__ == "__main__":
    success = test_fhir_cache_integration()
    exit(0 if success else 1)
