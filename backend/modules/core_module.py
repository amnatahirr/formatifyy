"""
modules/core_module.py — Features available to ALL organizations.
"""

CORE_FEATURES = [
    "document_analyze",  # dispatcher.py — AI checks
    "grammar_check",  # functions/grammar.py
    "formatting_check",  # functions/formatting.py
    "image_ethics",  # functions/image_ethics.py
    "image_relevance",  # functions/image_relevance.py
    "plagiarism_check",  # plagiarism/
    "para_relevance",  # functions/para_relevance.py
    "templates_crud",  # templates / admin templates
    "reports_history",  # existing reports / documents
    "collaboration",  # vc/ — version control
    "document_download",  # outputs /
]

CORE_MODULE_NAME = "core"
