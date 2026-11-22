# Image relevance results (test split)

Threshold 0.250 and band ±0.24 were chosen on the validation split only.

| method | auc | macro_f1 | acc | prec_relevant | rec_relevant | recall_at_1 | mrr | n_images | pct_to_claude | local_acc |
|---|---|---|---|---|---|---|---|---|---|---|
| CLIP zero-shot cosine (thr 0.262, val-tuned) | 0.727 | 0.6846 | 0.729 | 0.6068 | 0.531 | 0.1724 | 0.3065 | 1514 |  |  |
| CLIP zero-shot cosine (thr 0.22, current live) | 0.727 | 0.4859 | 0.4899 | 0.3829 | 0.8672 | 0.1724 | 0.3065 | 1514 |  |  |
| MiniLM caption~heading only (thr 0.270) | 0.6465 | 0.6818 | 0.7543 | 0.7314 | 0.4155 | 0.2622 | 0.3662 | 1514 |  |  |
| Trained scorer (caption available) | 0.8318 | 0.7728 | 0.8067 | 0.7496 | 0.6308 | 0.3052 | 0.4384 | 1514 | 53.5 | 0.873 |
| Trained scorer (caption hidden) | 0.7848 | 0.7175 | 0.7539 | 0.6416 | 0.5925 | 0.1605 | 0.2958 | 1514 | 78.9 | 0.7281 |


## Confusion matrix (test, trained scorer)

| actual | 0 | 1 |
|---|---|---|
| 0 | 2709 | 319 |
| 1 | 559 | 955 |


## Easy vs hard negatives (trained scorer)

| negatives | auc | macro_f1 | acc | prec_relevant | rec_relevant |
|---|---|---|---|---|---|
| hard | 0.8097 | 0.7448 | 0.7483 | 0.8247 | 0.6308 |
| easy | 0.854 | 0.7722 | 0.7771 | 0.8917 | 0.6308 |


## Hand-labelled gold set (n=278)

| method | auc | macro_f1 | acc | prec_relevant | rec_relevant |
|---|---|---|---|---|---|
| CLIP zero-shot cosine (thr 0.262, val-tuned) | 0.6944 | 0.6663 | 0.7086 | 0.5698 | 0.5269 |
| CLIP zero-shot cosine (thr 0.22, current live) | 0.6944 | 0.4614 | 0.4676 | 0.3721 | 0.8602 |
| MiniLM caption~heading only (thr 0.270) | 0.762 | 0.7133 | 0.759 | 0.6757 | 0.5376 |
| Trained scorer (caption available) | 0.821 | 0.755 | 0.7842 | 0.6854 | 0.6559 |
| Trained scorer (caption hidden) | 0.769 | 0.6943 | 0.7338 | 0.6118 | 0.5591 |


Agreement between automatic (placement) labels and hand labels: 78.1% (an estimate of label noise; lower = noisier training labels).
