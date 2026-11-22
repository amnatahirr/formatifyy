# Image relevance results (test split)

Threshold 0.363 and band ±0.2 were chosen on the validation split only.

| method | auc | macro_f1 | acc | prec_relevant | rec_relevant | recall_at_1 | mrr | n_images | pct_to_claude | local_acc |
|---|---|---|---|---|---|---|---|---|---|---|
| CLIP zero-shot cosine (thr 0.262, val-tuned) | 0.727 | 0.6846 | 0.729 | 0.6068 | 0.531 | 0.1724 | 0.3065 | 1514 |  |  |
| CLIP zero-shot cosine (thr 0.22, current live) | 0.727 | 0.4859 | 0.4899 | 0.3829 | 0.8672 | 0.1724 | 0.3065 | 1514 |  |  |
| MiniLM caption~heading only (thr 0.270) | 0.6465 | 0.6818 | 0.7543 | 0.7314 | 0.4155 | 0.2622 | 0.3662 | 1514 |  |  |
| Trained scorer (caption available) | 0.8261 | 0.765 | 0.7988 | 0.7297 | 0.6295 | 0.3038 | 0.4394 | 1514 | 27.7 | 0.8566 |
| Trained scorer (caption hidden) | 0.7782 | 0.7061 | 0.7417 | 0.6178 | 0.5905 | 0.1552 | 0.2906 | 1514 | 47.8 | 0.8307 |


## Confusion matrix (test, trained scorer)

| actual | 0 | 1 |
|---|---|---|
| 0 | 2675 | 353 |
| 1 | 561 | 953 |


## Easy vs hard negatives (trained scorer)

| negatives | auc | macro_f1 | acc | prec_relevant | rec_relevant |
|---|---|---|---|---|---|
| hard | 0.802 | 0.7356 | 0.7388 | 0.8056 | 0.6295 |
| easy | 0.8501 | 0.7693 | 0.7741 | 0.8857 | 0.6295 |


## Hand-labelled gold set (n=278)

| method | auc | macro_f1 | acc | prec_relevant | rec_relevant |
|---|---|---|---|---|---|
| CLIP zero-shot cosine (thr 0.262, val-tuned) | 0.6944 | 0.6663 | 0.7086 | 0.5698 | 0.5269 |
| CLIP zero-shot cosine (thr 0.22, current live) | 0.6944 | 0.4614 | 0.4676 | 0.3721 | 0.8602 |
| MiniLM caption~heading only (thr 0.270) | 0.762 | 0.7133 | 0.759 | 0.6757 | 0.5376 |
| Trained scorer (caption available) | 0.8341 | 0.7529 | 0.7806 | 0.6739 | 0.6667 |
| Trained scorer (caption hidden) | 0.763 | 0.6849 | 0.7194 | 0.5806 | 0.5806 |


Agreement between automatic (placement) labels and hand labels: 78.1% (an estimate of label noise; lower = noisier training labels).
