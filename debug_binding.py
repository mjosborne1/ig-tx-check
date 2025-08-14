#!/usr/bin/env python3

import json
import os

def test_binding_name_extraction():
    """Test binding name extraction from ImagingStudy profile."""
    
    # Load the ImagingStudy profile
    profile_path = "packages/hl7.fhir.uv.ips#current/package/StructureDefinition-ImagingStudy-uv-ips.json"
    
    with open(profile_path, 'r') as f:
        profile = json.load(f)
    
    # Find the modality element
    modality_element = None
    for el in profile["snapshot"]["element"]:
        if el["path"] == "ImagingStudy.series.modality":
            modality_element = el
            break
    
    if not modality_element:
        print("❌ Could not find ImagingStudy.series.modality element")
        return
    
    print("✅ Found ImagingStudy.series.modality element")
    
    # Check if binding exists
    if "binding" not in modality_element:
        print("❌ No binding found")
        return
    
    binding = modality_element["binding"]
    print("✅ Found binding")
    print(f"  ValueSet: {binding.get('valueSet', 'None')}")
    print(f"  Strength: {binding.get('strength', 'None')}")
    
    # Check for extension
    if "extension" not in binding:
        print("❌ No extension found in binding")
        return
    
    extensions = binding["extension"]
    print(f"✅ Found {len(extensions)} extensions")
    
    # Look for binding name extension
    binding_name = None
    for ext in extensions:
        print(f"  Extension URL: {ext.get('url', 'None')}")
        if (ext.get("url") == "http://hl7.org/fhir/StructureDefinition/elementdefinition-bindingName" and
            "valueString" in ext):
            binding_name = ext["valueString"]
            print(f"  ✅ Found binding name: {binding_name}")
            break
    
    if binding_name is None:
        print("❌ No binding name found")
    else:
        print(f"🎯 Extracted binding name: {binding_name}")

if __name__ == "__main__":
    os.chdir("/Users/osb074/Development/tools/python/ig-tx-check")
    test_binding_name_extraction()
