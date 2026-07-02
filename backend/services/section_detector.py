from typing import List, Dict
from difflib import SequenceMatcher

class SectionDetector:
    """Detect missing sections and suggest improvements"""
    
    # Common section names for academic reports
    SECTION_ALIASES = {
        "introduction": ["intro", "background", "overview"],
        "methodology": ["methods", "approach", "research design"],
        "results": ["findings", "outcomes", "data"],
        "conclusion": ["conclusions", "summary", "final remarks"],
        "abstract": ["summary", "synopsis"],
        "literature review": ["related work", "background research"],
        "implementation": ["development", "execution"],
        "evaluation": ["testing", "analysis", "performance"]
    }
    
    def __init__(self):
        pass
    
    def get_missing_sections(
        self, 
        detected_sections: List[str], 
        required_sections: List[str]
    ) -> List[str]:
        """Find missing required sections"""
        missing = []
        
        for required in required_sections:
            if not self._section_exists(required, detected_sections):
                missing.append(required)
        
        return missing
    
    def _section_exists(self, required: str, detected: List[str]) -> bool:
        """Check if required section exists in detected sections"""
        required_lower = required.lower().strip()
        
        for detected_section in detected:
            detected_lower = detected_section.lower().strip()
            
            # Exact match
            if required_lower == detected_lower:
                return True
            
            # Check aliases
            if required_lower in self.SECTION_ALIASES:
                aliases = self.SECTION_ALIASES[required_lower]
                if any(alias == detected_lower for alias in aliases):
                    return True
            
            # Fuzzy match
            similarity = SequenceMatcher(None, required_lower, detected_lower).ratio()
            if similarity > 0.8:
                return True
        
        return False
    
    def generate_suggestions(
        self, 
        missing_sections: List[str]
    ) -> Dict[str, Dict]:
        """Generate suggestions for missing sections"""
        suggestions = {}
        
        section_templates = {
            "abstract": {
                "reason": "Provides a concise overview of the entire report",
                "suggested_content": "This report presents an AI-driven solution for automated report formatting. The system utilizes Natural Language Processing to identify document structure and applies institution-specific formatting rules..."
            },
            "introduction": {
                "reason": "Introduces the problem and sets context for the report",
                "suggested_content": "The management of academic reports often involves tedious manual formatting tasks. Students must adhere to institution-specific guidelines, which can lead to inconsistencies and time wastage. This project addresses these challenges..."
            },
            "methodology": {
                "reason": "Explains the approach and methods used in your project",
                "suggested_content": "This project employs a multi-module architecture. The document parser extracts structural information using python-docx. Section detection uses both rule-based heuristics and semantic analysis with spaCy NLP..."
            },
            "results": {
                "reason": "Presents findings and outcomes",
                "suggested_content": "The system successfully detected sections in various document formats with 95% accuracy. The formatting engine applied template rules consistently across different document types..."
            },
            "conclusion": {
                "reason": "Summarizes findings and suggests future work",
                "suggested_content": "This project successfully demonstrates an automated approach to report formatting. Future enhancements include support for PDF documents and voice command interface..."
            },
            "references": {
                "reason": "Citations and bibliography - essential for academic integrity",
                "suggested_content": "All sources should be properly cited following your institution's citation style (APA, IEEE, Chicago, etc.)"
            }
        }
        
        for section in missing_sections:
            section_lower = section.lower()
            if section_lower in section_templates:
                suggestions[section] = section_templates[section_lower]
            else:
                suggestions[section] = {
                    "reason": f"Required section according to template",
                    "suggested_content": f"Please add content for the {section} section..."
                }
        
        return suggestions

# Singleton instance
detector = SectionDetector()
