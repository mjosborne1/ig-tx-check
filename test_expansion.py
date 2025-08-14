#!/usr/bin/env python3

import os
import sys
from tester import run_valueset_binding_report
from utils import get_config

def test_expansion():
    """Test the ValueSet expansion functionality"""
    
    # Setup
    config_file = os.path.join(os.getcwd(), 'config', 'config.json')
    outdir = '.'  # Current directory for testing
    
    # Get npm packages from config  
    try:
        packages_config = get_config(config_file, 'packages')
        if packages_config and len(packages_config) > 0:
            npm_path_list = []
            for pkg in packages_config:
                package_name = pkg.get('name', '')
                # Construct the path to the local package
                cache_path = os.path.expanduser("~/.fhir/packages")
                if package_name:
                    # Look for any version of this package
                    pkg_path = os.path.join(cache_path, package_name)
                    if os.path.exists(pkg_path):
                        # Get the first (most recent) version directory
                        versions = [d for d in os.listdir(pkg_path) if os.path.isdir(os.path.join(pkg_path, d))]
                        if versions:
                            versions.sort(reverse=True)  # Most recent first
                            full_path = os.path.join(pkg_path, versions[0])
                            npm_path_list.append(full_path)
                            print(f"Found package: {full_path}")
                        else:
                            print(f"No versions found for package: {package_name}")
                    else:
                        print(f"Package not found: {package_name}")
        
        if not npm_path_list:
            print("No packages found, checking local packages directory...")
            packages_dir = os.path.join(os.getcwd(), 'packages')
            if os.path.exists(packages_dir):
                for item in os.listdir(packages_dir):
                    item_path = os.path.join(packages_dir, item)
                    if os.path.isdir(item_path):
                        npm_path_list.append(item_path)
                        print(f"Found local package: {item_path}")
        
        print(f"Using package paths: {npm_path_list}")
        
        # Run the binding report with expansion
        run_valueset_binding_report(npm_path_list, outdir, config_file)
        print("ValueSet binding report with expansion completed!")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    test_expansion()
