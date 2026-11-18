"""
delete_org_groups.py — find and delete FYP groups linked to an organization,
including groups left behind (orphans) by an earlier org delete.

Run from the backend folder (where database.py lives):

    python delete_org_groups.py 14                    # DRY-RUN for org 14
    python delete_org_groups.py 16 --orphans          # DRY-RUN incl. leftovers of a deleted org
    python delete_org_groups.py 14 --yes              # really delete
    python delete_org_groups.py 16 --orphans --yes

--orphans also picks up groups whose org no longer exists, or whose linked
users no longer exist (use it for an org that was already deleted, e.g. 16).
Take a copy of your .db file before using --yes.
"""
import sys

from database import get_db
from routes.super_admin_routes import (
    _delete_groups_fully,
    _find_org_group_ids,
    _safe_ids,
    _table_exists,
    _table_has_column,
    _user_cols_of,
)

if len(sys.argv) < 2:
    print("Usage: python delete_org_groups.py <org_id> [--orphans] [--yes]")
    sys.exit(1)

org_id = int(sys.argv[1])
orphans = "--orphans" in sys.argv
execute = "--yes" in sys.argv

conn = get_db()
cur = conn.cursor()

if not _table_exists(cur, "fyp_groups"):
    print("No fyp_groups table in this database.")
    sys.exit(0)

cur.execute("PRAGMA table_info(fyp_groups)")
gcols = [r[1] for r in cur.fetchall()]
print("fyp_groups columns:", ", ".join(gcols))

user_ids = _safe_ids(cur, "SELECT id FROM users WHERE org_id = ?", (org_id,))
ids = set(_find_org_group_ids(cur, org_id, user_ids))

if orphans:
    if "org_id" in gcols:
        ids |= set(_safe_ids(
            cur,
            "SELECT id FROM fyp_groups WHERE org_id IS NOT NULL "
            "AND org_id NOT IN (SELECT id FROM organizations)",
            (),
        ))
        # leftovers of this exact org id (org row already gone)
        cur.execute("SELECT 1 FROM organizations WHERE id = ?", (org_id,))
        if not cur.fetchone():
            ids |= set(_safe_ids(cur, "SELECT id FROM fyp_groups WHERE org_id = ?", (org_id,)))
    for c in _user_cols_of(cur, "fyp_groups"):
        ids |= set(_safe_ids(
            cur,
            f"SELECT id FROM fyp_groups WHERE {c} IS NOT NULL "
            f"AND {c} NOT IN (SELECT id FROM users)",
            (),
        ))

group_ids = sorted(ids)
print(f"\nGroups found for org {org_id}{' (+ orphans)' if orphans else ''}: {len(group_ids)}")
if group_ids:
    ph = ",".join("?" * len(group_ids))
    cur.execute(f"SELECT * FROM fyp_groups WHERE id IN ({ph}) ORDER BY id", tuple(group_ids))
    for r in cur.fetchall()[:60]:
        print("   ", {k: r[k] for k in r.keys() if k in ("id", "name", "title", "org_id", "project_title", "created_by", "supervisor_id")})

if not group_ids:
    print("Nothing to delete.")
    sys.exit(0)

if not execute:
    print("\nDRY-RUN only — nothing was deleted. Run again with --yes to delete.")
    sys.exit(0)

summary = {}
try:
    cur.execute("BEGIN")
    _delete_groups_fully(cur, group_ids, summary)
    ph = ",".join("?" * len(group_ids))
    cur.execute(f"SELECT COUNT(*) FROM fyp_groups WHERE id IN ({ph})", tuple(group_ids))
    left = int(cur.fetchone()[0] or 0)
    if left:
        raise RuntimeError(f"{left} group(s) could not be deleted (check foreign keys).")
    conn.commit()
except Exception as exc:
    conn.rollback()
    print(f"\nFAILED — everything rolled back, nothing deleted.\nReason: {exc}")
    conn.close()
    sys.exit(1)

conn.close()
print("\nDONE. Deleted rows:")
for k, v in summary.items():
    if v:
        print(f"   {k}: {v}")
print("\nRe-run without --yes to confirm: it should now show 0 groups.")