#!/usr/bin/env python3

import os
import sys
import json
from tester import run_valueset_binding_report
from utils import get_config

def test_multiple_servers():
    """Test TSV generation with different terminology servers"""
    
    # Setup
    config_file = os.path.join(os.getcwd(), 'config', 'config.json')
    outdir = '.'  # Current directory for testing
    
    # Get npm packages from local directory
    npm_path_list = []
    packages_dir = os.path.join(os.getcwd(), 'packages')
    if os.path.exists(packages_dir):
        for item in os.listdir(packages_dir):
            item_path = os.path.join(packages_dir, item)
            if os.path.isdir(item_path):
                npm_path_list.append(item_path)
                print(f"Found local package: {item_path}")
    
    print(f"Using package paths: {npm_path_list}")
    
    # Test with different endpoints
    servers = [
        "https://tx.dev.hl7.org.au/fhir",
        "http://tx.fhir.org/r4"
    ]
    
    for server in servers:
        print(f"\n=== Testing with server: {server} ===")
        
        # Temporarily update config
        with open(config_file, 'r') as f:
            config = json.load(f)
        
        original_endpoint = config['init'][0]['endpoint']
        config['init'][0]['endpoint'] = server
        
        # Write temporary config
        temp_config = 'temp_config.json'
        with open(temp_config, 'w') as f:
            json.dump(config, f, indent=2)
        
        try:
            # Run the binding report
            run_valueset_binding_report(npm_path_list, outdir, temp_config)
            print(f"Report generated for {server}")
        except Exception as e:
            print(f"Error with {server}: {e}")
        finally:
            # Restore original config
            config['init'][0]['endpoint'] = original_endpoint
            with open(config_file, 'w') as f:
                json.dump(config, f, indent=2)
            
            # Clean up temp config
            if os.path.exists(temp_config):
                os.remove(temp_config)

if __name__ == '__main__':
    test_multiple_servers()
