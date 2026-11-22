# Image ethics: defense results

Model: frozen CLIP ViT-B/32 + LogisticRegression head (linear probing).
Deployed: `ethics_head_v6` (backend HEAD_HIGH 0.5, HEAD_LOW 0.4).

Evaluation: 6 seeds (1, 2, 3, 4, 5, 42), har seed par head dobara train.
Near-duplicates (cos > 0.98) hataye, aur test se wo images nikaali jo kisi train image
se > 0.98 milti thin. Test images per seed: ~915.
Alag test sets (training mein kabhi nahi): medical 1227 images (ImageNet),
outdoor/real-world scenes 1101 images (Places365, 37 scenes).

## Zero-shot vs trained heads (mean ± std)

| Method | Unsafe pakda | Safe (reports) galat alarm | Medical galat alarm | Outdoor scenes galat alarm | 3-class accuracy |
|---|---|---|---|---|---|
| CLIP zero-shot | 96.0% ± 0.6% | 4.8% ± 1.2% | 46.5% ± 0.0% | 34.0% ± 0.0% | - |
| Head v5_clean (threshold 0.6) | 98.1% ± 0.2% | 0.2% ± 0.3% | 2.2% ± 0.2% | 10.6% ± 1.0% | 98.4% ± 0.2% |
| Head v6 (threshold 0.5) **deployed** | 98.2% ± 0.1% | 0.2% ± 0.2% | 2.8% ± 0.1% | 0.3% ± 0.1% | 98.0% ± 0.1% |

- v5_clean: dedup + medical hard negatives. Naye outdoor photos (highway, airfield,
  parking, classroom...) mein se ~10% ko weapons keh deta tha.
- v6: v5_clean + 25 images per Places365 scene. Threshold 0.6 se 0.5 kiya, taake
  weapons ki pakad v5 jitni rahe. Outdoor galat alarm ~0.3% reh gaya.
- Train accuracy 99.3% vs test 98.0% (v6): overfitting nahi.
- Held-out reports ki photo-jaisi images bohut kam hain (~18 per seed), is liye un ka
  galat-alarm number (4.2% ± 3.4%) bohut hilta hai.

## Per class, v6 (6 seeds ke saare test predictions jod kar)

| Class | Precision | Recall | F1 |
|---|---|---|---|
| safe | 96.9% | 99.8% | 98.3% |
| sexual | 96.5% | 99.8% | 98.2% |
| weapons_violence | 99.7% | 95.7% | 97.7% |

## Limitations
- Test images unhi datasets se hain jin par train hua, asli reports par number thora kam hoga.
- Scenes ki tadaad (25) aur threshold (0.5) isi 6-seed evaluation ko dekh kar chune gaye;
  alag validation split nahi tha, is liye v6 ke numbers thore optimistic ho sakte hain.
- Selfie filters, depth-camera images, close-up farsh/texture, CCTV frames par ab bhi kabhi
  galat alarm aata hai (Places365 scenes in ko cover nahi karti).
- Drugs, self-harm, hate, offensive: trained nahi, BLIP caption + keyword engine par hain.
