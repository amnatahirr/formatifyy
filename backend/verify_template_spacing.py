#!/usr/bin/env python3
"""
Script to verify that template spacing properties are correctly being applied to documents.
This helps diagnose why spacing before/after and margins aren't showing up in generated documents.
"""

import json
import sqlite3
from pathlib import Path

def verify_template_spacing():
    """Verify that all templates have spacing properties defined"""
    
    db_path = Path("formatify.db")
    if not db_path.exists():
        print("[ERROR] formatify.db not found!")
        return
    
    conn = sqlite3.connect("formatify.db")
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Fetch all templates
        templates = cursor.execute("SELECT id, name, formatting_rules FROM templates").fetchall()
        
        print("\n" + "="*80)
        print("TEMPLATE SPACING VERIFICATION REPORT")
        print("="*80 + "\n")
        
        if not templates:
            print("[WARNING] No templates found in database!")
            return
        
        for template in templates:
            print(f"\nTemplate ID: {template['id']}")
            print(f"Template Name: {template['name']}")
            print("-" * 60)
            
            try:
                rules = json.loads(template['formatting_rules'])
                
                # Check critical spacing properties
                properties_to_check = [
                    ('body_space_before', 'Body Paragraph Space Before (pt)'),
                    ('body_space_after', 'Body Paragraph Space After (pt)'),
                    ('body_line_spacing', 'Body Line Spacing'),
                    ('heading1_space_before', 'Heading 1 Space Before (pt)'),
                    ('heading1_space_after', 'Heading 1 Space After (pt)'),
                    ('heading2_space_before', 'Heading 2 Space Before (pt)'),
                    ('heading2_space_after', 'Heading 2 Space After (pt)'),
                    ('bullet_space_before', 'Bullet Space Before (pt)'),
                    ('bullet_space_after', 'Bullet Space After (pt)'),
                    ('margin_top', 'Top Margin (inches)'),
                    ('margin_bottom', 'Bottom Margin (inches)'),
                    ('margin_left', 'Left Margin (inches)'),
                    ('margin_right', 'Right Margin (inches)'),
                    ('first_line_indent', 'First Line Indent (inches)'),
                ]
                
                missing_properties = []
                for prop_key, prop_label in properties_to_check:
                    if prop_key in rules:
                        value = rules[prop_key]
                        print(f"  ✓ {prop_label}: {value}")
                    else:
                        print(f"  ✗ {prop_label}: NOT DEFINED")
                        missing_properties.append(prop_key)
                
                if missing_properties:
                    print(f"\n  [WARNING] Missing {len(missing_properties)} properties!")
                    print(f"  Missing: {', '.join(missing_properties)}")
                else:
                    print(f"\n  [SUCCESS] All spacing properties defined!")
                    
            except json.JSONDecodeError as e:
                print(f"  [ERROR] Could not parse formatting_rules JSON: {str(e)}")
            except Exception as e:
                print(f"  [ERROR] Error processing template: {str(e)}")
        
        print("\n" + "="*80)
        print("RECOMMENDATIONS:")
        print("="*80)
        print("""
1. All templates MUST have these properties for proper formatting:
   - body_space_before, body_space_after (controls paragraph spacing)
   - margin_top, margin_bottom, margin_left, margin_right (document margins)
   - first_line_indent (for paragraph indentation)

2. If properties are missing, edit the template in the admin panel and set:
   - Body Space Before: 0-12 points
   - Body Space After: 0-12 points  
   - Margins: 0.5-1.5 inches each

3. The backend will automatically apply these during export if present.

4. Check the Flask console logs for "[v0]" messages which show actual spacing applied.
        """)
        
    finally:
        conn.close()

if __name__ == "__main__":
    verify_template_spacing()
