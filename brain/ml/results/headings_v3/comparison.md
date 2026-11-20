# Heading detection on GOLD: Rules vs v2 vs v3, normal vs stripped

| View | Model | Accuracy | Macro-F1 (95% CI) | Heading-vs-not F1 | F1 H1 | F1 H2 | F1 H3 | F1 Body | F1 Caption |
|---|---|---|---|---|---|---|---|---|---|
| normal | Rules | 0.919 | 0.924 (0.899-0.948) | 0.924 | 0.936 | 0.842 | 0.985 | 0.890 | 0.969 |
| normal | v2 (format) | 0.919 | 0.924 (0.899-0.948) | 0.924 | 0.936 | 0.842 | 0.985 | 0.890 | 0.969 |
| normal | v3 (text+context) | 0.889 | 0.892 (0.859-0.921) | 0.892 | 0.800 | 0.849 | 0.977 | 0.865 | 0.969 |
| stripped | Rules | 0.833 | 0.801 (0.764-0.836) | 0.797 | 0.347 | 0.891 | 0.985 | 0.815 | 0.969 |
| stripped | v2 (format) | 0.833 | 0.801 (0.764-0.836) | 0.797 | 0.347 | 0.891 | 0.985 | 0.815 | 0.969 |
| stripped | v3 (text+context) | 0.889 | 0.892 (0.859-0.921) | 0.892 | 0.800 | 0.849 | 0.977 | 0.865 | 0.969 |

Gold: 395 lines from test projects (leakage check passed). v3: no gold-informed changes. Stripped = same font size, no bold, no style for every line.
