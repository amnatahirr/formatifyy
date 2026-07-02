#!/usr/bin/env python3
"""
Migration Script: Update existing templates with new formatting fields
================================================================================

This script ensures all existing templates have the new fields:
  - spacing_unit (default: "mm")
  - heading{1-4}_italic (default: false)

Run this once after updating to the new version.

Usage:
    python scripts/migrate_formatting_rules.py
"""

import sqlite3
import json
import sys
from pathlib import Path

# Adjust this path based on your project structure
DB_PATH = Path(__file__).parent / "formatify.db"

def migrate_templates():
    """Update all templates with new formatting rule fields."""
    
    if not DB_PATH.exists():
        print(f"❌ Database not found at {DB_PATH}")
        sys.exit(1)
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        # Fetch all templates
        cursor.execute("SELECT id, formatting_rules FROM templates")
        templates = cursor.fetchall()
        
        if not templates:
            print("✓ No templates to migrate.")
            conn.close()
            return
        
        print(f"🔄 Found {len(templates)} template(s). Checking for missing fields...")
        
        updated_count = 0
        
        for template in templates:
            template_id = template["id"]
            rules_json = template["formatting_rules"]
            
            try:
                # Parse existing rules
                if not rules_json:
                    rules = {}
                else:
                    rules = json.loads(rules_json)
                
                original_rules = json.dumps(rules)  # For comparison
                
                # Add missing spacing_unit
                if "spacing_unit" not in rules:
                    rules["spacing_unit"] = "mm"
                    print(f"  → Template #{template_id}: Added spacing_unit = 'mm'")
                
                # Add missing heading italic flags
                for level in [1, 2, 3, 4]:
                    key = f"heading{level}_italic"
                    if key not in rules:
                        rules[key] = False
                        print(f"  → Template #{template_id}: Added {key} = False")
                
                # Only update if something changed
                if json.dumps(rules) != original_rules:
                    updated_json = json.dumps(rules)
                    cursor.execute(
                        "UPDATE templates SET formatting_rules = ? WHERE id = ?",
                        (updated_json, template_id)
                    )
                    updated_count += 1
            
            except json.JSONDecodeError as e:
                print(f"  ⚠️  Template #{template_id}: Invalid JSON - {e}")
            except Exception as e:
                print(f"  ❌ Template #{template_id}: Error - {e}")
        
        # Commit changes
        conn.commit()
        print(f"\n✓ Migration complete! Updated {updated_count} template(s).")
        
    except Exception as e:
        print(f"❌ Migration failed: {e}")
        conn.rollback()
        sys.exit(1)
    
    finally:
        conn.close()

def verify_migration():
    """Verify that all templates have required fields."""
    
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    try:
        cursor.execute("SELECT id, formatting_rules FROM templates")
        templates = cursor.fetchall()
        
        print("\n📋 Verification Results:")
        print("=" * 60)
        
        all_good = True
        for template in templates:
            template_id = template["id"]
            rules_json = template["formatting_rules"]
            
            try:
                rules = json.loads(rules_json) if rules_json else {}
                
                # Check required fields
                has_unit = "spacing_unit" in rules
                has_h1_italic = "heading1_italic" in rules
                has_h2_italic = "heading2_italic" in rules
                has_h3_italic = "heading3_italic" in rules
                has_h4_italic = "heading4_italic" in rules
                
                all_present = (has_unit and has_h1_italic and 
                               has_h2_italic and has_h3_italic and has_h4_italic)
                
                status = "✓ OK" if all_present else "⚠️  MISSING"
                print(f"Template #{template_id}: {status}")
                
                if not all_present:
                    all_good = False
                    if not has_unit:
                        print(f"    - Missing: spacing_unit")
                    for level in [1, 2, 3, 4]:
                        if not locals()[f"has_h{level}_italic"]:
                            print(f"    - Missing: heading{level}_italic")
            
            except json.JSONDecodeError:
                print(f"Template #{template_id}: ❌ Invalid JSON")
                all_good = False
        
        print("=" * 60)
        if all_good:
            print("\n✓ All templates have required fields!")
        else:
            print("\n⚠️  Some templates are missing fields. Run migration again.")
        
    finally:
        conn.close()

if __name__ == "__main__":
    print("🚀 Formatify Database Migration")
    print("=" * 60)
    
    migrate_templates()
    verify_migration()
    
    print("\n✓ Done!")
