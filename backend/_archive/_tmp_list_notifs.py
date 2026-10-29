from database import get_db

conn = get_db()
c = conn.cursor()
c.execute(
    """
    SELECT id, recipient_email, title, message, type, related_type, related_id, created_at
    FROM notifications
    WHERE LOWER(recipient_email) LIKE '%supervisor%'
       OR LOWER(title) LIKE '%alpha%'
       OR LOWER(title) LIKE '%beta%'
       OR LOWER(message) LIKE '%alpha%'
       OR LOWER(message) LIKE '%beta%'
       OR LOWER(message) LIKE '%gamma%'
       OR LOWER(message) LIKE '%delta%'
       OR LOWER(message) LIKE '%zeta%'
       OR LOWER(message) LIKE '%omega%'
       OR LOWER(message) LIKE '%nova%'
    ORDER BY id DESC
    LIMIT 50
    """
)
rows = [dict(r) for r in c.fetchall()]
print("count", len(rows))
for r in rows:
    print(r["id"], r["title"], "|", (r["message"] or "")[:90], "|", r["recipient_email"])

c.execute("SELECT COUNT(*) AS n FROM notifications")
print("total notifications", c.fetchone()["n"])
c.execute(
    """
    SELECT recipient_email, COUNT(*) AS n
    FROM notifications
    GROUP BY recipient_email
    ORDER BY n DESC
    """
)
print("by recipient", [dict(r) for r in c.fetchall()])
conn.close()
