"""
modules/fyp_module.py — University FYP features (plan-gated).
"""

from typing import Any

FYP_FEATURES = [
    "supervisor_management",  # admin supervisors
    "group_management",  # fyp_groups
    "milestone_tracking",  # group milestones
    "submission_flow",  # final_submissions
    "cover_page_generation",  # frontmatter_routes
    "meeting_notes",  # meeting notes
    "advisor_assignment",  # choose supervisor flow
]

FYP_MODULE_NAME = "fyp"


def check_fyp_access(org: Any) -> bool:
    if org is None:
        return False
    if isinstance(org, dict):
        modules = org.get("modules", "core") or "core"
    else:
        modules = getattr(org, "modules", "core") or "core"
    return "fyp" in [m.strip() for m in str(modules).split(",") if m.strip()]
