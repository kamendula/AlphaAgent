"""Data models that flow through the pipeline.

These are plain ``dataclasses`` on purpose: the M0 demo path depends on nothing
but the standard library, so ``clone && make demo`` works with zero install.
(Later milestones may layer richer validation on top, but the contracts live
here.)

Pipeline data flow::

    Candidate      -- what a PoolSource emits
      -> ScoredRow -- what a QuantFilter emits (keeps the score, not a bool)
      -> Verdict   -- what the AgentPanel emits          (M1)
      -> EntrySignal -- what EntryTiming emits           (M2)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from enum import Enum


class AssetType(str, Enum):
    """Coarse asset class, used by the symbol router to pick a data provider."""

    EQUITY = "equity"
    CRYPTO = "crypto"
    UNKNOWN = "unknown"


# --------------------------------------------------------------------------- #
# Market data
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Bar:
    """A single OHLCV bar."""

    d: date
    open: float
    high: float
    low: float
    close: float
    volume: float


@dataclass(frozen=True, slots=True)
class PriceSeries:
    """An ordered (oldest -> newest) OHLCV series for one symbol.

    ``as_of`` records the point-in-time boundary the data was fetched under; it
    is the hook the future PIT-Guard uses to prove no bar post-dates the run.
    """

    symbol: str
    bars: list[Bar]
    as_of: date | None = None

    def __post_init__(self) -> None:
        if self.as_of is not None:
            for b in self.bars:
                if b.d > self.as_of:
                    raise ValueError(
                        f"{self.symbol}: bar {b.d} is after as_of {self.as_of} "
                        "(point-in-time violation)"
                    )

    @property
    def closes(self) -> list[float]:
        return [b.close for b in self.bars]

    @property
    def last(self) -> Bar:
        return self.bars[-1]

    def __len__(self) -> int:
        return len(self.bars)


# --------------------------------------------------------------------------- #
# News
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class NewsItem:
    """One published news headline."""

    d: date
    title: str
    site: str = ""
    url: str = ""
    summary: str = ""


@dataclass(frozen=True, slots=True)
class NewsFeed:
    """A point-in-time news feed for one symbol (newest first).

    All items must be published on or before ``as_of`` — the PIT boundary for the
    sentiment analyst, so it never reads news that hadn't broken yet.
    """

    symbol: str
    items: tuple[NewsItem, ...] = ()
    as_of: date | None = None

    def __len__(self) -> int:
        return len(self.items)


# --------------------------------------------------------------------------- #
# Fundamentals
# --------------------------------------------------------------------------- #
@dataclass(frozen=True, slots=True)
class Fundamentals:
    """A point-in-time fundamentals snapshot for one symbol.

    ``latest_filing`` is the filing date of the most recent statement included;
    it is the PIT anchor — a provider must only include statements filed on or
    before the ``as_of`` boundary, so the agent never sees a report that hadn't
    been published yet.
    """

    symbol: str
    as_of: date | None = None
    eps_growth: tuple[float, ...] = ()  # newest-first YoY growth per period
    revenue_growth: float | None = None
    net_margin: float | None = None
    pe: float | None = None
    latest_period: date | None = None
    latest_filing: date | None = None


# --------------------------------------------------------------------------- #
# Selection chain
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Candidate:
    """A ticker proposed by a PoolSource, before any scoring."""

    symbol: str
    asset_type: AssetType = AssetType.UNKNOWN
    # Which source(s) surfaced it. Multiple tags == signal resonance.
    source_tags: list[str] = field(default_factory=list)
    raw_score: float | None = None


@dataclass(slots=True)
class ScoredRow:
    """A candidate after a QuantFilter has scored it.

    We keep the numeric ``score`` and the per-factor breakdown rather than a
    pass/fail bool, so post-mortems can ask "high score yet failed — why?".
    """

    symbol: str
    asset_type: AssetType
    score: float
    factors: dict[str, float] = field(default_factory=dict)
    source_tags: list[str] = field(default_factory=list)
    notes: str = ""


# A scored table is just an ordered list of rows (highest score first).
ScoredTable = list[ScoredRow]


# --------------------------------------------------------------------------- #
# Agent chain (defined now for a stable contract; wired up in M1)
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class Opinion:
    """One analyst's structured take on a symbol."""

    role: str
    stance: str  # e.g. bullish / bearish / neutral
    confidence: float  # 0..1
    rationale: str = ""
    key_risks: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    info_richness: str = "C"  # A/B/C, borrowed anti-bias grading


@dataclass(slots=True)
class Verdict:
    """The aggregated decision a CollaborationPolicy produces."""

    symbol: str
    rating: str  # e.g. strong_buy / buy / watch / avoid
    confidence: float
    key_support: list[str] = field(default_factory=list)
    key_risks: list[str] = field(default_factory=list)
    evidence_refs: list[str] = field(default_factory=list)
    opinions: list[Opinion] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Entry chain (contract now; wired up in M2)
# --------------------------------------------------------------------------- #
@dataclass(slots=True)
class EntrySignal:
    """A rule-based timing decision. No LLM involved by design."""

    symbol: str
    action: str  # buy / wait / pass
    trigger_price: float | None = None
    stop_hint: float | None = None
    rationale: str = ""
