FORMATTING_PROMPT = lambda rules, file: f"""
You are a formatting agent working with PDF, DOCX and TXT files.

You will be given:
1. A formatting.md file containing formatting rules.
2. A document that needs to be formatted.

Your task is to go line by line and format the document according to the rules.
DO NOT add anything that is not specified in the formatting rules.

Here are some examples of how you should format:

EXAMPLE 1:
...
(Output omitted for brevity)
...

========================
Formatting Rules (formatting.md):
{rules}

========================
Document to Format:
{file}

========================
Return ONLY the formatted document.
"""

rules = """
- Introduction should be the first section.
- All headings should be bold.
- Font size should be 16px.
"""

document = """
Benefits of Reading

Reading improves knowledge...

Introduction

Reading books is important...
"""

prompt = FORMATTING_PROMPT(rules, document)

print(prompt)