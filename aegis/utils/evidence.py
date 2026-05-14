from dataclasses import dataclass
from .normalization import clamp, safe_float


@dataclass
class EvidenceItem:
    claim: str
    source_type: str = "synthetic"
    evidence_strength: float = 50.0
    explanation: str = ""
    confidence: float = 50.0

    def to_dict(self):
        return {
            "claim": self.claim,
            "source_type": self.source_type,
            "evidence_strength": clamp(self.evidence_strength),
            "explanation": self.explanation,
            "confidence": clamp(self.confidence),
        }


def create_evidence_item(claim, source_type="synthetic", evidence_strength=50.0,
                         explanation="", confidence=50.0):
    return EvidenceItem(
        claim=claim,
        source_type=source_type,
        evidence_strength=clamp(safe_float(evidence_strength, 50)),
        explanation=explanation,
        confidence=clamp(safe_float(confidence, 50)),
    ).to_dict()


def summarize_evidence(items):
    if not items:
        return {"n_items": 0, "avg_strength": 50.0, "max_strength": 0.0,
                "min_strength": 0.0, "claims": []}
    strengths = [clamp(safe_float(i.get("evidence_strength", 50), 50)) for i in items]
    claims = [str(i.get("claim", "")) for i in items if i.get("claim")]
    return {
        "n_items": len(items),
        "avg_strength": sum(strengths) / len(strengths),
        "max_strength": max(strengths),
        "min_strength": min(strengths),
        "claims": claims,
    }
