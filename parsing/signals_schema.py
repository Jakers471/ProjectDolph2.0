"""Signal dataclass — the output contract for the parser.

Every message produces exactly one Signal regardless of content:
  ENTRY | TRIM | EXIT | ADD | UNSURE | NOISE
"""
from dataclasses import dataclass, field


@dataclass
class RuleResult:
    """What one rule found, how confident, and why."""
    value: object          # the detected value (string, tuple, dict, None)
    confidence: float      # 0.0 – 1.0
    evidence: list = field(default_factory=list)  # human-readable strings


@dataclass
class Signal:
    analyst: str
    timestamp: str
    raw_content: str
    action: str                          # ENTRY | TRIM | EXIT | ADD | UNSURE | NOISE
    confidence: float                    # 0.0 – 1.0
    side: str | None = None              # LONG | SHORT
    asset_type: str | None = None        # CRYPTO | STOCK | OPTION
    symbol: str | None = None
    entry_price: float | None = None
    exit_pct: float | None = None        # percentage gain/loss reported on exit ("up 25%" = 25.0)
    targets: list = field(default_factory=list)
    stop: float | None = None
    size_hint: str | None = None         # "20x", "$500", "15 contracts" — verbatim
    unsure_reasons: list = field(default_factory=list)
    source_message_id: str | None = None

    def to_dict(self) -> dict:
        return {
            "analyst": self.analyst,
            "timestamp": self.timestamp,
            "action": self.action,
            "confidence": round(self.confidence, 3),
            "side": self.side,
            "asset_type": self.asset_type,
            "symbol": self.symbol,
            "entry_price": self.entry_price,
            "targets": self.targets,
            "stop": self.stop,
            "size_hint": self.size_hint,
            "unsure_reasons": self.unsure_reasons,
            "source_message_id": self.source_message_id,
            "raw_content": self.raw_content,
        }
