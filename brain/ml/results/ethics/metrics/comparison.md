# Image ethics: test set results

Test set: {np.str_('safe'): 540, np.str_('sexual'): 119, np.str_('weapons_violence'): 400} (+ 1235 medical safe images)

| Method | Unsafe pakda | Safe par galat alarm | Medical par galat alarm | 3-class accuracy |
|---|---|---|---|---|
| CLIP zero-shot | 95.0% | 15.7% | 46.2% | - |
| Head v2 (threshold 0.6) | 99.0% | 0.2% | 21.9% | 99.1% |
| Head v3 (threshold 0.6) | 98.1% | 0.2% | 2.3% | 98.9% |
