import os
import re
import random
import fitz
from docx import Document


# ========= PATH CONFIG =========

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FOLDER = os.path.join(BASE_DIR, "dataset_sources", "formatted")

OUTPUT_FOLDER = os.path.join(BASE_DIR, "dataset_sources", "unformatted")

SAMPLES_PER_FILE = 3

os.makedirs(OUTPUT_FOLDER, exist_ok=True)


# ========= FILE READERS =========

def read_txt(path):

    with open(path, "r", encoding="utf-8", errors="ignore") as f:

        return f.read()


def read_pdf(path):

    text = ""

    doc = fitz.open(path)

    for page in doc:

        text += page.get_text()

    return text


def read_docx(path):

    doc = Document(path)

    return "\n".join(p.text for p in doc.paragraphs)


def extract_text(path):

    if path.endswith(".txt"):

        return read_txt(path)


    elif path.endswith(".pdf"):

        return read_pdf(path)


    elif path.endswith(".docx"):

        return read_docx(path)


    return None


# ========= UNFORMAT FUNCTIONS =========

def remove_line_breaks(text):

    return text.replace("\n", " ")


def remove_numbering(text):

    return re.sub(r'\d+\.', '', text)


def lowercase(text):

    return text.lower()


def uppercase(text):

    return text.upper()


def random_case(text):

    return ''.join(

        c.upper() if random.random() > 0.5 else c.lower()

        for c in text

    )


def remove_punctuation(text):

    return re.sub(r'[^\w\s]', '', text)


def merge_lines(text):

    lines = text.split("\n")

    random.shuffle(lines)

    return " ".join(lines)


def add_noise(text):

    noise = ["..", "...", "??", "!!"]

    words = text.split()

    for i in range(len(words)):

        if random.random() < 0.1:

            words[i] += random.choice(noise)

    return " ".join(words)


def remove_some_spaces(text):

    words = text.split()

    new = ""

    for w in words:

        if random.random() < 0.2:

            new += w

        else:

            new += w + " "

    return new


# ========= APPLY RANDOM OPS =========

def generate_unformatted(text):

    operations = [

        remove_line_breaks,
        remove_numbering,
        lowercase,
        uppercase,
        random_case,
        remove_punctuation,
        merge_lines,
        add_noise,
        remove_some_spaces

    ]

    selected = random.sample(operations, random.randint(3, 6))

    for op in selected:

        text = op(text)

    return text


# ========= MAIN LOOP =========

for filename in os.listdir(INPUT_FOLDER):

    filepath = os.path.join(INPUT_FOLDER, filename)

    print("Processing:", filename)


    text = extract_text(filepath)


    if not text:

        print("Skipped:", filename)

        continue


    base_name = os.path.splitext(filename)[0]


    for i in range(SAMPLES_PER_FILE):

        unformatted = generate_unformatted(text)


        save_name = f"{base_name}_unformatted_{i}.txt"


        save_path = os.path.join(OUTPUT_FOLDER, save_name)


        with open(save_path, "w", encoding="utf-8") as f:

            f.write(unformatted)


print("\nDONE — Unformatted dataset generated successfully")