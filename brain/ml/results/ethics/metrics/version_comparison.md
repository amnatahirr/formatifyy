# Image ethics: saare versions ka comparison

Model har version mein ek hi qisam ka hai: frozen CLIP ViT-B/32 image embedding (512 numbers)
ke upar Logistic Regression head (transfer learning / linear probing). Versions mein sirf
**training data** aur **evaluation ka tareeqa** badla.

## 1. Version history (har qadam par kya badla aur kyun)

| Version | Kya badla | Us waqt ka number | Baad mein kya pata chala |
|---|---|---|---|
| v1 | Pehla head: 4 classes (safe, sexual, weapons, violence) | Sirf 1 split (seed 42) | Weapons aur violence aapas mein mix ho rahe the, isliye v2 mein merge kiye |
| v2 | 3 classes (weapons + violence = weapons_violence) | Seed 42: accuracy 99.1%, unsafe recall 99.8%, galat alarm 0.4% | 6 splits par accuracy 95.4% ± 4.5%, galat alarm 7.4% ± 8.5%. 18,036 report images mein se 13,663 duplicates thin (ek report CS03 ki 918 mein se sirf 43 alag), seed 42 lucky tha |
| v3 | v2 + medical hard negatives (syringe, stethoscope, lab coat, oxygen mask) | Seed 42: accuracy 98.9%, medical galat alarm 21.9% se 2.3% | Duplicates abhi bhi the, number optimistic tha |
| v4 (dedup) | v2 + duplicates hataye + test se leakage hataya | 6 splits: accuracy 99.0% ± 0.3%, galat alarm 1.8% ± 1.2% (threshold 0.4) | Pehla imandar number. Medical images par phir bhi galat alarm |
| v5_clean | v4 + medical hard negatives (100 per class) | 6 splits: accuracy 98.4% ± 0.2%, recall 98.1% ± 0.2% (threshold 0.6) | Naye outdoor photos (sadak, airfield, CCTV jaisi) mein se ~10% ko weapons kehta tha |
| **v6** | v5 + 25 photos per Places365 scene (37 scenes), threshold 0.5 | 6 splits: accuracy 98.0% ± 0.1%, recall 98.2% ± 0.1% | **Deployed.** Outdoor galat alarm ~0.3% |

## 2. Fair comparison: sab ek hi test set par

Har tareeqa 6 alag splits (seeds 1, 2, 3, 4, 5, 42) par dobara train hua, aur sab
ka test bilkul ek jaisa hai: duplicates hata kar, aur test se wo images nikaal kar jo kisi
train image se milti hon (~915 images per split).
Saath mein do alag test sets jo kisi training mein nahi gaye: medical 1227 images
(ImageNet) aur outdoor/real-world scenes 1101 images (Places365, 37 scenes).
Har row pichli row mein **sirf ek cheez** jodti hai. Numbers: mean ± std.

| Tareeqa | Versions | Unsafe pakda | Safe reports par galat alarm | Medical par galat alarm | Outdoor photos par galat alarm | 3-class accuracy |
|---|---|---|---|---|---|---|
| CLIP zero-shot (no training) | baseline | 96.0% ± 0.6% | 4.8% ± 1.2% | 46.5% ± 0.0% | 34.0% ± 0.0% | - |
| Head only (no hard negatives) | v2, v4 | 99.6% ± 0.0% | 0.4% ± 0.3% | 31.3% ± 1.2% | 41.0% ± 4.9% | 99.0% ± 0.3% |
| + medical hard negatives | v3, v5_clean | 98.1% ± 0.2% | 0.2% ± 0.3% | 2.2% ± 0.2% | 10.6% ± 1.0% | 98.4% ± 0.2% |
| + outdoor scenes (threshold 0.6) | - | 96.9% ± 0.2% | 0.1% ± 0.2% | 1.7% ± 0.3% | 0.1% ± 0.0% | 98.0% ± 0.1% |
| + outdoor scenes (threshold 0.5) | v6 (deployed) | 98.2% ± 0.1% | 0.2% ± 0.2% | 2.8% ± 0.1% | 0.3% ± 0.1% | 98.0% ± 0.1% |

Is table ko kaise parhein:
- **Zero-shot se trained head:** bina training CLIP medical aur outdoor photos ke bade hisse ko
  unsafe keh deta hai. Hamare data par train kiya head ye galtiyan bohut kam kar deta hai.
- **+ medical:** medical photos (injection, stethoscope) par galat alarm bohut kam hota hai.
- **+ outdoor scenes:** sadak, airfield, classroom jaisi photos par galat alarm ~0.3% reh jaata hai.
  Threshold 0.6 par weapons ki pakad thori girti hai, is liye 0.5 rakha (v6), jahan pakad pehle
  jitni hai.
- v2/v4 aur v3/v5 ka farq sirf duplicates ka tha. Saaf test par dono ka tareeqa ek hi row hai.
  Purane versions ke **zyada numbers** (99%+) duplicates aur lucky split ki wajah se the (table 1).

## 3. Asli misaalein (saved model files, p_unsafe)

p_unsafe = model ke hisaab se image ke unsafe hone ka imkaan (0 se 1). v6 ke liye 0.5 se upar
flag hota hai (purane versions mein 0.6). Ye images kisi version ki training mein nahi thin.

| Image | v2 | v3 | v4_dedup | v5_clean | v6 | App ka faisla (v6 + keyword) |
|---|---|---|---|---|---|---|
| University logo | 0.05 | 0.05 | 0.04 | 0.05 | 0.04 | Safe |
| Handgun (weapon) | 0.99 | 0.99 | 1.0 | 1.0 | 1.0 | Unethical: Weapons / Violence (head) |
| Sharaab + pills (drugs) | 0.49 | 0.12 | 0.58 | 0.13 | 0.09 | Unethical: Drugs (keyword) |
| Flow diagram | 0.01 | 0.0 | 0.0 | 0.0 | 0.0 | Safe |
| Blood draw (medical) | 0.52 | 0.14 | 0.67 | 0.15 | 0.18 | Safe |
| Graph | 0.01 | 0.0 | 0.0 | 0.0 | 0.0 | Safe |
| Email app screenshot | 0.01 | 0.01 | 0.0 | 0.0 | 0.0 | Safe |
| Text page screenshot | 0.01 | 0.0 | 0.01 | 0.0 | 0.0 | Safe |
| Blood draw (screenshot, alag version) | 0.7 | 0.23 | 0.74 | 0.18 | 0.15 | Safe |

- **Blood draw:** bina medical data wale v2 aur v4 is jaiz medical photo ko borderline ya 0.6 se upar le jaate
  the, yaani galti se unethical. Medical hard negatives ke baad (v3, v5, v6) ye saaf Safe hai.
- **Drugs:** head drugs par train nahi hua (data nahi tha), is liye uska number neeche hai.
  App phir bhi isse pakadta hai, kyunke keyword engine BLIP caption ("alcohol with pills") se
  Drugs category nikaalta hai.
- **Handgun:** har version 0.99 se upar, yaani asli unsafe image har version mein pakdi gayi.

## Note
- v1 ki model file save nahi thi, is liye wo sirf history table mein hai.
- Purane keyword engine (BLIP caption + keywords) ka number is table mein nahi, kyunke sexual aur
  weapons ki raw images delete ki ja chuki hain (sirf embeddings rakhi), aur caption ke liye raw
  image chahiye.
