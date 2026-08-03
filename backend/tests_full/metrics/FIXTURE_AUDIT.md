# Accuracy fixture audit (Part A.1)
#
# Original 6 fixtures (before hardening) — why F1=1.000 was meaningless:
#
# | fixture | planted errors | hardness | compared against REAL detector? |
# |---------|----------------|----------|----------------------------------|
# | grammar_planted_errors | sentense, mispelled, he go, experiment were | EASY typos | NO — scorer searched fixture text for those same strings |
# | formatting_missing_sections | missing Conclusion heading | EASY | PARTIAL — reimplemented expectation, not field-match vs pipeline issues |
# | list_parallel_items | 3 dash bullets after trigger | EASY | YES — detect_list_groups, but only count match |
# | heading_template_match | Related Work absent | EASY | PARTIAL — set arithmetic, not issue field match |
# | toc_headings_present | 4 exact titles | EASY | PARTIAL — title list membership |
# | plagiarism_identical_passage | verbatim source_passage | EASY | YES jaccard, but source embedded in JSON guaranteeing high overlap |
#
# Diff logic NOW (accuracy_report._match_issues_fieldwise):
#   expected matches actual iff type matches AND location_hint in blob
#   AND (optional) keywords hit original/reason/text/paragraph_id.
#   Unused actual → FP; unmatched expected → FN.
#
# image_relevance was previously MISSING entirely — added in this pass.
