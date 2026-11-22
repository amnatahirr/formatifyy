# Image Ethics Detection: A se Z tak (aasan zubaan mein)

> Ye document un logon ke liye hai jinhon ne Machine Learning (ML) nahi parhi. Har mushkil lafz
> ka matlab saath mein likha hai, aur aakhir mein ek chhoti dictionary (glossary) bhi hai.

---

## 1. Masla kya tha?

Formatify ek tool hai jo students ki FYP reports check aur format karta hai. Is ka ek function
**Image Ethics** hai. Report mein koi aisi tasveer ho jo academic report mein nahi honi chahiye
(nangi tasveer, hathiyaar, khoon kharaba, drugs wagairah), to ye usay pakad kar student ko batata
hai ke "ye tasveer badlo".

**Evaluator ne kaha tha:** FYP sirf bahar ki APIs (jaise ChatGPT ya Claude ko image bhejna) par nahi
chal sakta. Apna model hona chahiye jo **hamare apne data par train** ho. Is liye ye kaam kiya.

---

## 2. Pehle kya hota tha (purana tareeqa) aur us mein kya kami thi?

Purana tareeqa 3 qadam ka tha:

1. **BLIP** naam ka model tasveer dekh kar ek jumla likhta tha (caption). Maslan: "a man holding a gun".
2. Us jumle mein **keywords** dhoonde jaate the, jaise "gun", "knife", "naked".
3. Keyword mila to tasveer unethical.

**Kami:**
- Sab kuch caption par tha. BLIP ne tasveer ko alag lafzon mein bayan kiya to keyword nahi milta
  tha. Maslan sharaab aur pills wali tasveer ka caption "alcohol **with** pills" aaya, jabke list
  mein sirf "alcohol **and** pills" tha, to wo tasveer chhoot gayi.
- Is mein koi **training** nahi thi. Ye sirf rules the. Evaluator ki shart puri nahi hoti thi.

---

## 3. Pehle kuch bunyaadi baatein (bilkul aasan)

**Model kya hota hai?**
Ek computer program jo misaalein dekh kar khud seekhta hai ke faisla kaise karna hai. Jaise bachay
ko 100 billiyan aur 100 kutte dikhao, to wo khud farq pehchan'na seekh jata hai.

**Training kya hai?**
Model ko bohut saari misaalein dikhana, saath mein sahi jawab ke saath ("ye safe hai", "ye hathiyaar
hai"), taake wo pattern seekh le.

**Testing kya hai?**
Training ke baad model ko **nayi** tasveerein dikhana jo usne kabhi nahi dekhin, aur check karna ke
wo kitni sahi pehchanta hai. Jaise exam mein wo sawal jo class mein nahi karwaye gaye.

**Fingerprint (embedding) kya hai?**
Computer tasveer ko seedha nahi samajhta. Ek bara model (hamare case mein **CLIP**) har tasveer ko
**512 numbers** ki list mein badal deta hai. Ye list us tasveer ka "fingerprint" hai. Milti julti
tasveeron ke fingerprint bhi milte julte hote hain. Bandooq ki do alag tasveeron ke numbers
ek doosre ke qareeb honge, aur graph ki tasveer ke numbers un se door.

**Classifier kya hai?**
Ek chhota model jo fingerprint dekh kar bata deta hai ke tasveer kis "class" (qisam) ki hai:
safe, sexual, ya weapons/violence.

---

## 4. Hamara tareeqa ek misaal se

Socho ek **tajurbakar doctor** hai (ye CLIP hai). Usne apni zindagi mein 40 crore tasveerein dekhi
hain aur duniya ki har cheez pehchanta hai. Hum usay dobara medical college nahi bhejte (ye
**fine-tuning** hota). Hum us ke saath ek **naya assistant** (classifier) rakhte hain, aur assistant
ko sirf itna sikhate hain: "doctor jo report (fingerprint) de, us se ye faisla karo ke tasveer
academic report ke qabil hai ya nahi."

- Doctor (CLIP) ko **bilkul nahi badla**. Is ko **frozen** kehte hain.
- Sirf assistant (classifier) ko hamare data par **train** kiya.
- Is tareeqe ka technical naam **Transfer Learning**, aur khaas taur par **Linear Probing** hai.

> Ye fine-tuning **nahi** hai. Defense mein ye fark saaf rakhna hai.

---

## 5. CLIP hi kyun chuna?

| Wajah | Tafseel |
|---|---|
| Pehle se project mein tha | Image Relevance function bhi CLIP use karta hai. Naya model download nahi karna pada |
| Free aur open-source | OpenAI ne public kiya hai (`openai/clip-vit-base-patch32`) |
| Offline chalta hai | Ek dafa download ke baad internet ya API nahi chahiye |
| Tasveer ki "samajh" bohut achhi | 40 crore tasveer + text pairs par train hua hai, aam cheezein khud pehchanta hai |
| Chhota aur tez | Base size (ViT-B/32), aam laptop ke CPU par chal jata hai |
| Seedha fingerprint deta hai | Har tasveer ke 512 numbers, jo classifier ke liye bilkul munasib hain |

### Classifier ke liye Logistic Regression kyun?

Logistic Regression sab se seedha classifier hai. Ye har class ke liye ek "score" banata hai aur
phir probability deta hai (0 se 1, maslan "is tasveer ke unsafe hone ka imkaan 0.93 hai").

- **Probability deta hai.** Hum is par threshold laga sakte hain (section 10).
- **Bohut tez train hota hai.** Laptop CPU par seconds mein. Is liye hum har tabdeeli 6 dafa test kar sake.
- **Kam data par bhi theek chalta hai** aur ratta kam maarta hai.
- **File bohut chhoti hai:** sirf 13 KB.

---

## 6. Baaki options kyun nahi chune?

| Option | Kya hota | Kyun nahi chuna |
|---|---|---|
| **Purana BLIP + keywords** | Caption mein lafz dhoondna | Training nahi, aur caption ke lafzon par bohut depend. Sirf un classes ke liye rakha jin ka data nahi tha (drugs, self-harm, hate, offensive) |
| **CLIP zero-shot** (bina training, sirf text se poochna: "kya ye hathiyaar ki photo hai?") | CLIP khud andaza lagata | Hamne test kiya: medical photos mein se **46.5%** aur aam outdoor photos mein se **34%** ko galti se unsafe kaha. Bohut zyada galat alarm |
| **CLIP ko poora fine-tune karna** | CLIP ke 8.8 crore numbers dobara seekhna | (1) Hamare paas sirf ~4,000 saaf tasveerein thin, itne kam data par ye ratta maar leta. (2) Research batati hai ke kam data par fine-tuning naye qisam ki tasveeron par nateeja kharab karti hai, aur hamara asal masla yahi tha. (3) Is ke liye GPU aur ghante chahiye. (4) Wahi CLIP Image Relevance bhi chalata hai, badalte to wo kharab hota. (5) NSFW tasveerein rakh kar bahar ke server (Colab) par bhejni padti |
| **Apna model zero se banana** (CNN from scratch) | Bilkul naya model | Laakhon tasveerein aur bohut zyada computing chahiye |
| **Bahar ki API** (ChatGPT / Claude / Google Vision) | Tasveer bahar bhejna | Evaluator ne mana kiya tha. Paise lagte hain, internet chahiye, aur students ki tasveerein bahar jaati hain |
| **Bara CLIP** (ViT-L/14) | Zyada taqatwar version | ~3 guna bara aur dheema. Image Relevance ke liye bhi badalna padta |

---

## 7. Data: kya, kahan se, kitna

Model ko seekhne ke liye 3 qisam ki misaalein chahiye thin:

| Class (qisam) | Kahan se | Kitni (duplicates hata kar) |
|---|---|---|
| **Safe** | Hamari apni 265 FYP reports ki tasveerein (diagrams, screenshots, photos) | 18,036 mein se 4,373 alag nikli. Training mein ~2,200 (saari photo wali + 2,000 random) |
| **Sexual** | HuggingFace par ek public dataset | 552 |
| **Weapons / Violence** | HuggingFace `Subh775/WeaponDetection` (cc-by-4.0 licence) | ~1,270 |

**"Hard negatives" (mushkil safe misaalein):** ye safe tasveerein jaan boojh kar daali gayin jo unsafe
jaisi **lagti** hain, taake model galti na kare:

| Hard negatives | Kahan se | Kyun |
|---|---|---|
| Weapons dataset ki bina-hathiyaar tasveerein | Weapons dataset khud | Taake "bahar ki photo" ko hi hathiyaar na samjhe |
| Medical (syringe, stethoscope, lab coat, oxygen mask) | ImageNet (HuggingFace `mlnomad/imnet1k_*`) | Model blood test ki photo ko hathiyaar keh raha tha |
| Aam jagahein (sadak, highway, airfield, parking, classroom, office... 37 qisam) | Places365 (HuggingFace `rumenguin/places365-val`) | Model dashcam, drone aur CCTV jaisi photos ko hathiyaar keh raha tha |

**Jin classes ka data nahi mila:** drugs, self-harm, hate symbols, offensive. Ye purane keyword
engine par hi hain. Drugs ke liye combos bhi daale gaye (maslan caption mein "pills" aur "alcohol"
dono hon, kisi bhi tarteeb mein, to drugs).

**Data ki hifazat:** NSFW aur weapons ki asli tasveerein kisi ne khol kar nahi dekhin. Script ne
sirf unke fingerprints (numbers) nikale, aur phir asli tasveerein **delete** kar di gayin. Git mein
sirf numbers (`.npy` files) hain.

---

## 8. Training kaise hui (qadam ba qadam)

1. **Fingerprint nikaale:** har tasveer ko CLIP se guzaar kar 512 numbers banaye aur `.npy` files
   mein save kiye. Ye kaam ek dafa hota hai.
   Scripts: `extract_ethics_embeddings.py`, `extract_weapon_embeddings.py`,
   `mine_hard_negatives.py`, `extract_medical_embeddings.py`, `extract_scene_embeddings.py`
2. **Duplicates hataye:** jo do tasveerein 98% se zyada milti thin, unmein se ek rakhi.
3. **Classifier train kiya:** Logistic Regression ko fingerprints aur sahi jawab diye. Isne seekha
   ke kaunse numbers safe ki taraf aur kaunse unsafe ki taraf ishara karte hain.
   Script: `train_ethics_v6.py` (data ka code: `ethics_split.py`)
4. **Save kiya:** trained classifier `ethics_head_v6.joblib` (13 KB) ban gaya. Ye
   `backend/ml_weights/` mein hai aur app isi ko use karta hai.

Poori training laptop ke CPU par chand seconds mein ho jaati hai. GPU ki zaroorat nahi.

---

## 9. Testing kaise ki (imandari ke saath)

Ye sab se aham hissa hai, kyunke yahin asal galtiyan pakdi gayin.

**a) Train aur test alag:** data ka 80% seekhne ke liye, 20% test ke liye. Safe tasveerein
**report ke hisaab** se baanti gayin, yaani ek report ki saari tasveerein ya to train mein ya test
mein. Is tarah model test mein bilkul nayi reports dekhta hai.

**b) 6 dafa alag alag baant kar test (6 seeds):** ek hi dafa baantne se kismat ka number aa sakta
hai. Hum ne 6 alag tareeqon se baanta, har dafa model dobara train kiya, aur average ± kitna hilta
hai (mean ± std) report kiya.

**c) Duplicates hataye:** pata chala ke 18,036 report images mein se **13,663 duplicates** thin (ek hi
tasveer har page par). Ek report (CS03) ki 918 tasveeron mein se sirf 43 alag thin.

**d) Leakage hataya:** test ki wo tasveerein nikaal di gayin jo kisi train tasveer se 98% se zyada
milti thin. Warna model "pehle dekha hua sawal" exam mein hal karta.

**e) Alag "anjaan" test sets:** 1,227 medical aur 1,101 outdoor tasveerein, jo **kisi bhi training mein
nahi** gayin. Ye check karta hai ke model asli duniya ki nayi tasveeron par kaisa hai.

### Hum ne kya naapa?

| Naam | Matlab | Achha kab |
|---|---|---|
| **Accuracy** | 100 tasveeron mein se kitni ki class sahi bataayi | Zyada |
| **Unsafe pakda (Recall)** | Jitni asli unsafe tasveerein thin, unmein se kitni pakdi | Zyada (sab se zaroori) |
| **Galat alarm (False alarm)** | Safe tasveerein jinhein galti se unsafe kaha | Kam |

---

## 10. Safar: v1 se v6 tak (kya galti mili, kaise theek ki)

| Version | Kya kiya | Kya masla nikla |
|---|---|---|
| **v1** | Pehla classifier, 4 classes (safe, sexual, weapons, violence alag) | Weapons aur violence aapas mein mix ho rahe the |
| **v2** | Weapons + violence ko ek class banaya (3 classes) | Ek split par 99.1% dikha. 6 splits par asal mein **95.4% ± 4.5%**. Wajah: duplicates aur kismat wala split |
| **v3** | Medical hard negatives daale | Blood test wali photo theek hui, lekin duplicates abhi bhi the |
| **v4** | Duplicates aur leakage hataye | Pehla imandar number (~99%). Lekin medical photos par phir galat alarm |
| **v5** | Saaf data + medical hard negatives | Aam outdoor photos (sadak, airfield, CCTV) mein se ~10% ko hathiyaar kehta tha |
| **v6** ✅ | + 37 qisam ki aam jagahon ki photos, threshold 0.5 | **Yahi app mein laga hai** |

**Threshold kya hai?** Model har tasveer ka "unsafe hone ka imkaan" deta hai (0 se 1). Threshold wo
had hai jis se upar tasveer flag hoti hai. v6 mein ye **0.5** hai. Hamne 0.4, 0.5, 0.55 aur 0.6
aazmaaye. 0.5 par hathiyaar pakadna pehle jitna rahta hai, aur galat alarm bohut kam rahta hai.

---

## 11. Final nateeje

### Sab ek hi test par (6 splits ka average)

| Tareeqa | Unsafe pakda | Safe reports par galat alarm | Medical par galat alarm | Outdoor par galat alarm | Accuracy |
|---|---|---|---|---|---|
| CLIP zero-shot (bina training) | 96.0% | 4.8% | 46.5% | 34.0% | - |
| Sirf classifier (v2/v4) | 99.6% | 0.4% | 31.3% | 41.0% | 99.0% |
| + medical (v3/v5) | 98.1% | 0.2% | 2.2% | 10.6% | 98.4% |
| **+ outdoor, threshold 0.5 (v6)** | **98.2%** | **0.2%** | **2.8%** | **0.3%** | **98.0%** |

### Is table ka matlab, aasan zubaan mein

- **Training ka faida:** bina training CLIP har 2 medical photos mein se 1 ko, aur har 3 outdoor
  photos mein se 1 ko galat flag karta. v6 mein ye 100 mein se 3 aur 1000 mein se 3 reh gaya.
- **Sirf accuracy kaafi nahi:** "sirf classifier" ki accuracy sab se zyada (99%) dikhti hai, lekin wo
  medical aur outdoor photos par bohut galti karta hai. Asli reports ke liye v6 behtar hai.
- **Stable:** 6 alag splits par number sirf ±0.1% hilta hai, yaani ye kismat ka number nahi.
- **Har class ka hisaab (v6):** Safe 99.8% sahi pehchani, Sexual 99.8% pakdi, Weapons 95.7% pakdi.

### Asli misaal (ek test document)

| Tasveer | v2 | v6 | App ka faisla |
|---|---|---|---|
| Handgun | 0.99 | 1.00 | 🚨 Weapons / Violence |
| Sharaab + pills | 0.49 | 0.09 | 🚨 Drugs (keyword engine ne pakda) |
| Blood test (medical) | **0.70 (galat)** | 0.15 | ✅ Safe |
| Logo, graph, diagram, screenshots | ~0.01 | ~0.00 | ✅ Safe |

Poori tables: `brain/ml/results/ethics/metrics/version_comparison.md` aur `comparison.md`

---

## 12. App mein ye kaise kaam karta hai

Jab student report upload karta hai, to har tasveer ke liye:

1. CLIP tasveer ka fingerprint banata hai, aur classifier "unsafe hone ka imkaan" (p) deta hai.
2. BLIP tasveer ka caption likhta hai, aur keyword engine us mein drugs, self-harm, hate dhoondta hai.
3. Faisla:
   - **p 0.5 ya zyada** → unethical (classifier ki class: Sexual ya Weapons/Violence)
   - **Keyword engine ko drugs, self-harm, hate ya offensive mila** → unethical
   - **p 0.4 se 0.5 (shak wala ilaqa)** aur keyword bhi mila → unethical (dono ka ittefaq)
   - **Warna** → safe
4. Student ko seedha jumla dikhta hai, maslan: *"This image appears to show weapons or violence.
   Detection confidence: 100%..."*. Saath mein tasveer badalne ka option bhi.
5. Student nayi tasveer lagaye to wahi check dobara chalta hai.

Sab kuch **offline** hai. Koi tasveer kisi bahar ke server par nahi jaati.

---

## 13. Kamzoriyan (defense mein imandari se batani hain)

- Test tasveerein unhi datasets se hain jin par training hui. Asli duniya mein number thora kam ho sakta hai.
- Drugs, self-harm, hate aur offensive ka **trained** model nahi hai (public data nahi mila). Ye
  caption + keywords par hain, aur caption ajeeb aaye to chhoot sakti hain.
- Selfie filters, depth-camera images, farsh jaisi close-up textures aur kuch CCTV frames par ab bhi
  kabhi galat alarm aata hai.
- Medical images ki tadaad (100 per class), scenes ki tadaad (25) aur threshold (0.5) test ke
  numbers dekh kar chune gaye. Alag validation set nahi tha, is liye numbers thore optimistic ho sakte hain.
- Sexual data internet se jama kiya hua (scraped) hai, sirf academic istemal ke liye.
- CLIP fine-tune nahi hua. Sirf us ke upar classifier train hua (ye soch samajh kar faisla tha, section 6).

**Future work:** drugs/self-harm ka labelled data mile to unki bhi class train karna, zyada data ke
saath LP-FT (pehle classifier, phir halki fine-tuning) aazmana, aur ek alag validation set rakhna.

---

## 14. Files ka naqsha

| Kaam | File |
|---|---|
| Final training | `brain/ml/train_ethics_v6.py` |
| Data load, duplicates, train/test split | `brain/ml/ethics_split.py` |
| Defense ke numbers | `brain/ml/evaluate_ethics.py` → `results/ethics/metrics/comparison.md` |
| Saare versions ka comparison | `brain/ml/compare_ethics_versions.py` → `results/ethics/metrics/version_comparison.md` |
| Fingerprints (numbers) | `brain/ml/results/ethics/*.npy` |
| Trained model (app wala) | `backend/ml_weights/ethics_head_v6.joblib` |
| Model load karna | `backend/functions/ethics_head.py` |
| Faisla + keyword engine | `backend/functions/image_ethics.py` |

---

## 15. Evaluator ke mumkina sawal aur chhote jawab

**"Kya ye aap ka apna model hai?"**
Haan. Classifier hamare apne labelled data par train hua hai, aur us ka apna train/test evaluation hai.
CLIP sirf tasveer ka fingerprint banata hai.

**"Fine-tune kyun nahi kiya?"**
~4,000 saaf tasveeron par 8.8 crore parameters badalna ratta (overfitting) aur nayi qisam ki tasveeron
par kharab nateeje deta hai, aur hamara asal masla nayi qisam ki tasveerein hi thin. CLIP Image
Relevance ke saath share bhi hota hai. Is liye CLIP frozen rakha aur classifier train kiya (Linear Probing).

**"99% to bohut zyada hai, kaise?"**
Pehle 99.1% aaya tha, lekin wo kismat ka split aur duplicates ki wajah se tha. Hamne khud ye pakda,
duplicates aur leakage hataye, aur 6 splits ka average diya. Final number 98.0% ± 0.1% hai.

**"Pehle se behtar kaise hua?"**
Bina training CLIP medical photos par 46.5% aur outdoor photos par 34% galat alarm deta tha. Hamara
model 2.8% aur 0.3% deta hai, jabke unsafe tasveerein 98.2% pakadta hai.

**"Drugs ka kya?"**
Public labelled data nahi mila, aur drugs ki tasveerein medical tasveeron (syringe, pills) se bohut
milti hain. Is liye drugs caption + keywords par hai, combos ke saath. Ye future work hai.

**"Data kahan se aaya, licence?"**
Safe: hamari apni reports. Weapons: cc-by-4.0 dataset. Medical: ImageNet. Scenes: Places365.
ImageNet aur Places365 research aur academic use ke liye hain. Sexual data scraped hai, sirf academic
use. NSFW aur weapons ki asli tasveerein delete kar di gayin, sirf numbers rakhe.

---

## 16. Chhoti dictionary (Glossary)

| Lafz | Aasan matlab |
|---|---|
| Model | Program jo misaalon se seekhta hai |
| Training | Model ko jawab ke saath misaalein dikha kar sikhana |
| Testing | Nayi misaalon par model ka imtehan |
| CLIP | OpenAI ka model jo tasveer ko 512 numbers (fingerprint) mein badalta hai |
| BLIP | Salesforce ka model jo tasveer ka caption (jumla) likhta hai |
| Embedding / fingerprint | Tasveer ke 512 numbers |
| Classifier / head | Chhota model jo fingerprint se class batata hai |
| Logistic Regression | Sab se seedha classifier, probability deta hai |
| Frozen | Model jise badla nahi gaya |
| Transfer Learning | Bare model ki samajh ko naye kaam ke liye istemal karna |
| Linear Probing | Bare model ko frozen rakh kar sirf upar ka chhota classifier train karna |
| Fine-tuning | Bare model ke andar ke numbers bhi dobara train karna |
| Zero-shot | Bina kisi training ke, sirf text se model se poochna |
| Hard negatives | Safe tasveerein jo unsafe jaisi lagti hain, model ko sikhane ke liye |
| Duplicates | Ek jaisi tasveerein jo kai dafa aayin |
| Leakage | Test mein wo cheez aa jana jo training mein dekhi ja chuki ho |
| Seed | Data ko baantne ka ek tareeqa. 6 seeds = 6 alag tareeqe |
| Mean ± std | Average, aur kitna upar neeche hota hai |
| Accuracy | Kitni sahi |
| Recall | Asli unsafe mein se kitni pakdi |
| False alarm | Safe ko galti se unsafe kehna |
| Threshold | Wo had jis se upar tasveer flag hoti hai (v6 mein 0.5) |
| Overfitting / ratta | Model ne training ki misaalein yaad kar lin, lekin naye sawal par kamzor |
