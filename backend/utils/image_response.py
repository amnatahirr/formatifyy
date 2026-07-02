"""
Enhanced Image Response Utils
Wrapper for image relevance responses with tracking IDs
"""
import uuid
from typing import Optional, Dict, Any


class ImageRelevanceResponse:
    """Enhanced response for image relevance analysis with tracking"""
    
    def __init__(
        self,
        analysis_result: Dict[str, Any],
        image_path: str,
        image_index: int,
        document_id: Optional[int] = None,
    ):
        self.image_id = str(uuid.uuid4())
        self.image_path = image_path
        self.image_index = image_index
        self.document_id = document_id
        self.analysis_result = analysis_result
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response"""
        return {
            "image_id": self.image_id,
            "image_index": self.image_index,
            "image_path": self.image_path,
            "document_id": self.document_id,
            "is_relevant": self.analysis_result.get("is_relevant", False),
            "confidence": self.analysis_result.get("confidence", 0.0),
            "relevance_score": self.analysis_result.get("relevance_score", 0.0),
            "reasons": self.analysis_result.get("reasons", []),
            "suggestion": (
                "This image appears relevant to the section content."
                if self.analysis_result.get("is_relevant")
                else "Consider replacing this image with one more relevant to the section."
            ),
            "analysis_details": {
                "keyword_matches": self.analysis_result.get("keyword_matches", []),
                "semantic_similarity": self.analysis_result.get("semantic_similarity", 0.0),
                "caption": self.analysis_result.get("caption", ""),
                "ocr_text": self.analysis_result.get("ocr_text", "")[:200],  # First 200 chars
            },
        }


def wrap_image_issues_response(issues_list: list, document_id: int) -> list:
    """
    Wrap image issues with tracking IDs
    Each issue gets a unique ID for replacement operations
    """
    wrapped_issues = []
    
    for idx, issue in enumerate(issues_list):
        enhanced_issue = {
            **issue,
            "image_id": str(uuid.uuid4()),
            "image_index": idx,
            "document_id": document_id,
            "can_replace": True,  # Flag indicating this image can be replaced
        }
        wrapped_issues.append(enhanced_issue)
    
    return wrapped_issues
