import sqlite3
import os

db_path = os.path.join('backend', 'formatify.db')
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cursor = conn.cursor()
cursor.execute("SELECT id, filename, user_id, template_id, file_path FROM documents WHERE id = 406")
row = cursor.fetchone()
print(dict(row))
conn.close()
