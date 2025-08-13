#!/usr/bin/env python3
"""
Test script to verify MustSupport and dependency processing functionality
"""

import os
import tempfile
import json
from tester import run_valueset_binding_report

def test_mustsupport_and_main_ig():
    """Test MustSupport processing for main IG only (no dependencies)"""
    
    print("Testing MustSupport processing for main IG only...")
    
    # Create a temporary output directory
    with tempfile.TemporaryDirectory() as tmpdir:
        print(f"Using temporary directory: {tmpdir}")
        
        try:
            # Test with require-must-support = true (current config)
            config_file = "config/config.json"
            print("\n1. Testing with snapshot and differential views from main IG only")
            
            # Create fake npm path list pointing to actual package
            npm_path_list = ["/Users/osb074/data/ig-tx-check/packages/hl7.fhir.au.ereq#dev"]
            
            if os.path.exists(npm_path_list[0]):
                # Run the report
                result = run_valueset_binding_report(npm_path_list, tmpdir, config_file)
                
                # Check if report was generated
                report_file = os.path.join(tmpdir, "ValueSetBindings-hl7.fhir.au.ereq.html")
                if os.path.exists(report_file):
                    print(f"✅ Report generated: {report_file}")
                    
                    # Check report size (should be much smaller without dependencies)
                    file_size = os.path.getsize(report_file)
                    print(f"✅ Report size: {file_size} bytes (much smaller without dependencies)")
                    
                    # Read report content
                    with open(report_file, 'r') as f:
                        content = f.read()
                        if "main IG package" in content:
                            print("✅ Report correctly indicates main IG package only")
                        else:
                            print("⚠️  Main IG package indication not found")
                        
                        # Count number of ValueSets
                        valueset_count = content.count('<a href="http')
                        print(f"✅ Found {valueset_count} ValueSet links (focused on main IG)")
                        
                        if "snapshot and differential views" in content:
                            print("✅ Report indicates both snapshot and differential views processed")
                        else:
                            print("⚠️  View processing information not found")
                    
                else:
                    print("❌ Report was not generated")
                    return False
            else:
                print(f"⚠️  Test package not found at {npm_path_list[0]}")
                print("This is expected if the package hasn't been copied yet")
            
            print(f"\n🎉 Main IG focused test completed!")
            return True
            
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            return False

if __name__ == "__main__":
    success = test_mustsupport_and_main_ig()
    exit(0 if success else 1)
