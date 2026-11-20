# Heading detection: Rules vs XGBoost v1 vs v2 (GOLD set)

| Model | Version | Accuracy | Macro-F1 (95% CI) | Heading-vs-not F1 | F1 H1 | F1 H2 | F1 H3 | F1 Body | F1 Caption | Acc on 'Unsure' lines | % to Claude @0.70 | Acc on confident |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Rules (baseline) | - | 0.919 | 0.924 (0.899-0.948) | 0.924 | 0.936 | 0.842 | 0.985 | 0.890 | 0.969 | 0.985 | - | - |
| XGBoost v1 | before any gold-informed fix | 0.765 | 0.797 (0.763-0.832) | 0.794 | 0.678 | 0.762 | 0.985 | 0.594 | 0.969 | 0.046 | 13.2% | 0.878 |
| XGBoost v2 | after one gold-informed fix | 0.919 | 0.924 (0.899-0.948) | 0.924 | 0.936 | 0.842 | 0.985 | 0.890 | 0.969 | 0.985 | 0.0% | 0.919 |

Gold set: 395 hand-labelled lines from test projects only (leakage check passed).
v2 is 'after one gold-informed fix': the change was chosen after seeing v1's gold errors, so v2's gold score is slightly optimistic.
