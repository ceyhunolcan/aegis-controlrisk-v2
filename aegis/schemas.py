# Pydantic models. These aren't strictly used at runtime - the pipeline
# operates on dicts/DataFrames directly - but they document the expected
# shape of inputs and are useful when validating real-world data later.
#
# Falls back to a no-op stub when pydantic isn't installed.

try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    # ridiculous tiny shim so this module imports without pydantic
    class BaseModel:
        def __init__(self, **kw):
            for k, v in kw.items():
                setattr(self, k, v)
        def model_dump(self):
            return {k: v for k, v in self.__dict__.items() if not k.startswith("_")}
    def Field(*a, **kw): return kw.get("default")
    def ConfigDict(**kw): return kw


class Company(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_id: str
    ticker: str
    name: str
    sector: str
    industry: str
    market_cap: float
    enterprise_value: float
    country: str
    exchange: str
    controlled_company_flag: bool = False
    dual_class_flag: bool = False
    insider_ownership_pct: float = 0.0
    annual_meeting_date: str = ""
    nomination_deadline: str = ""
    fiscal_year_end: str = ""
    has_poison_pill: bool = False
    classified_board: bool = False
    ceo_chair_combined: bool = False
    majority_voting_standard: bool = True


class FinancialFeatures(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_id: str
    tsr_1y_vs_peer: float = 0.0
    tsr_3y_vs_peer: float = 0.0
    tsr_5y_vs_peer: float = 0.0
    ev_ebitda_discount_vs_peer: float = 0.0
    pe_discount_vs_peer: float = 0.0
    roic_gap_vs_peer: float = 0.0
    ebitda_margin_gap_vs_peer: float = 0.0
    fcf_yield_vs_peer: float = 0.0
    capex_intensity_vs_peer: float = 0.0
    revenue_growth_vs_peer: float = 0.0
    leverage_vs_peer: float = 0.0
    guidance_miss_frequency: float = 0.0
    earnings_miss_frequency: float = 0.0
    mna_writeoff_history_score: float = 50.0
    say_on_pay_support_pct: float = 90.0
    director_vote_support_avg_pct: float = 95.0
    recent_stock_momentum_score: float = 50.0


class Director(BaseModel):
    model_config = ConfigDict(extra="ignore")
    director_id: str
    company_id: str
    name: str
    age: int = 60
    tenure_years: float = 5.0
    independent: bool = True
    committee_roles: str = ""
    is_committee_chair: bool = False
    other_public_boards: int = 0
    prior_vote_support_pct: float = 95.0
    sector_expertise_score: float = 50.0
    capital_allocation_expertise_score: float = 50.0
    technology_expertise_score: float = 50.0
    climate_transition_expertise_score: float = 50.0
    compensation_oversight_flag: bool = False
    audit_oversight_flag: bool = False
    governance_oversight_flag: bool = False


class Shareholder(BaseModel):
    model_config = ConfigDict(extra="ignore")
    holder_id: str
    name: str
    holder_type: str = "passive"
    governance_sensitivity_score: float = 50.0
    activism_support_history_score: float = 50.0
    proxy_advisor_dependence_score: float = 50.0
    esg_sensitivity_score: float = 50.0
    value_orientation_score: float = 50.0
    settlement_preference_score: float = 50.0
    retail_mobilization_score: float = 50.0


class Ownership(BaseModel):
    model_config = ConfigDict(extra="ignore")
    company_id: str
    holder_id: str
    ownership_pct: float = 0.0
    qoq_change_pct: float = 0.0
    voting_power_pct: float = 0.0


class Campaign(BaseModel):
    model_config = ConfigDict(extra="ignore")
    campaign_id: str
    company_id: str
    activist_name: str
    campaign_start_date: str = ""
    stake_pct: float = 0.0
    thesis_type: str = ""
    board_seats_requested: int = 0
    board_seats_won: int = 0
    settled: bool = False
    went_to_vote: bool = False
    stock_reaction_1d: float = 0.0
    stock_reaction_30d: float = 0.0
    outcome: str = ""


class ActivistArchetype(BaseModel):
    model_config = ConfigDict(extra="ignore")
    archetype_id: str
    name: str
    style: str = ""
    preferred_market_cap_min: float = 0.0
    preferred_market_cap_max: float = 1e15
    board_seat_preference: int = 1
    public_campaign_aggressiveness: float = 50.0
    settlement_preference: float = 50.0
    esg_weight: float = 0.0
    value_weight: float = 0.0
    governance_weight: float = 0.0
    operational_weight: float = 0.0
    typical_stake_pct: float = 5.0


class Event(BaseModel):
    model_config = ConfigDict(extra="ignore")
    event_id: str
    company_id: str
    event_date: str
    event_type: str
    severity_score: float = 50.0
    description: str = ""


def model_to_dict(m):
    if m is None:
        return {}
    if hasattr(m, "model_dump"):
        return m.model_dump()
    if hasattr(m, "dict"):
        return m.dict()
    return dict(m)
