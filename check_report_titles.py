#!/usr/bin/env python3
"""
Script to check ValueSet titles in the generated HTML report
"""

import re

def check_report_titles():
    """Check what ValueSet titles appear in the generated report"""
    
    report_file = "/Users/osb074/data/ig-tx-check/reports/ValueSetBindings-hl7.fhir.au.ereq.html"
    
    try:
        with open(report_file, 'r') as f:
            content = f.read()
        
        # Find all ValueSet links in the report
        # Look for pattern: <a href="..." target="_blank">Title</a>
        pattern = r'<a href="[^"]*ValueSet[^"]*" target="_blank">([^<]+)</a>'
        matches = re.findall(pattern, content)
        
        print(f"Found {len(matches)} ValueSet titles in the report:")
        print("=" * 60)
        
        for i, title in enumerate(matches, 1):
            print(f"{i:2d}. {title}")
            
            # Check if it looks like an ID (all lowercase with hyphens, no spaces)
            if re.match(r'^[a-z0-9-]+$', title) and ' ' not in title:
                print(f"    ⚠️  This looks like an ID rather than a title")
            else:
                print(f"    ✅ This looks like a proper title")
        
        print("=" * 60)
        
        # Count how many look like IDs vs titles
        id_like = sum(1 for title in matches if re.match(r'^[a-z0-9-]+$', title) and ' ' not in title)
        title_like = len(matches) - id_like
        
        print(f"Summary: {title_like} proper titles, {id_like} ID-like entries")
        
    except FileNotFoundError:
        print(f"Report file not found: {report_file}")
    except Exception as e:
        print(f"Error reading report: {e}")

if __name__ == "__main__":
    check_report_titles()
