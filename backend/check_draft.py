import sqlite3

c = sqlite3.connect("formatify.db")
print([r[1] for r in c.execute("pragma table_info(project_sections)")])
rows = c.execute(
    "select * from project_sections where project_id = 16"
).fetchall()
for r in rows:
    print(r)