import sqlite3
import json

conn = sqlite3.connect("formatify.db")   # change if DB name is different
conn.row_factory = sqlite3.Row

templates = conn.execute(
    "SELECT id, name, required_sections FROM templates"
).fetchall()

for t in templates:
    sections = json.loads(t["required_sections"])
    print(f"Template {t['id']}: {t['name']}")
    print(f"required_sections count: {len(sections)}")
    print(f"first 3: {sections[:3]}")
    print()

conn.close()