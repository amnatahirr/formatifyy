import os
import tempfile
from pathlib import Path
from docx import Document
from services.heading_detector_v2 import detect_headings_v2

def run_test():
    with tempfile.TemporaryDirectory() as tmp:
        path = Path(tmp) / "test.docx"
        doc = Document()
        # 0. Normal text
        doc.add_paragraph("This is a normal paragraph.")
        # 1. Exact match, correct style
        p1 = doc.add_paragraph("Introduction")
        p1.style = "Heading 1"
        # 2. Exact match, wrong style
        doc.add_paragraph("Literature Review") # Normal style
        # 3. Synonym match
        doc.add_paragraph("Background Research") # Synonym for Literature Review
        # 4. Fuzzy match (typo)
        doc.add_paragraph("Methodolgy") # edit distance 1
        # 5. Wrongly styled (long body text)
        p5 = doc.add_paragraph("This is a very long body paragraph that happens to have the Heading 1 style applied by mistake in Microsoft Word because the user clicked it accidentally.")
        p5.style = "Heading 1"
        # 6. Another normal
        doc.add_paragraph("Conclusion") # Match for Conclusion
        
        doc.save(path)
        
        template_sections = [
            {"name": "Introduction", "aliases": []},
            {"name": "Literature Review", "aliases": ["Background Research", "Related Work"]},
            {"name": "Methodology", "aliases": []},
            {"name": "Conclusion", "aliases": []},
            {"name": "References", "aliases": []}
        ]
        
        results = detect_headings_v2(str(path), template_sections)
        print("Results:", results)
        
        # Simple assertions
        assert any(h["templateHeading"] == "Introduction" and h["styleCorrect"] for h in results["foundHeadings"])
        assert any(h["templateHeading"] == "Literature Review" for h in results["missingStyleHeadings"])
        assert any(h["templateHeading"] == "Methodology" for h in results["missingStyleHeadings"])
        assert len(results["wronglyStyledParagraphs"]) == 1
        assert any(h["templateHeading"] == "References" for h in results["truelyMissing"])
        print("All assertions passed!")

if __name__ == "__main__":
    run_test()
