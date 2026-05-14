# Generates the 7 synthetic companies + boards + holders + history that
# CASCADE-2 runs against. Each company is deliberately tuned to exercise
# a different corner of the model:
#   ORCX - energy major, transition narrative
#   INDC - underperforming industrial conglomerate (designed Critical)
#   NVTC - stable high-performing tech (designed Low)
#   MDCO - controlled dual-class media (high gov concern, low legal feasibility)
#   RETR - retail with weak margins (designed High)
#   HMED - healthcare device, M&A speculation (Moderate)
#   CBNK - bank, governance-sensitive (Moderate)
import os
from pathlib import Path
from datetime import date, timedelta
import csv
import random


def _future_date(days):
    return (date.today() + timedelta(days=days)).isoformat()


def _past_date(days):
    return (date.today() - timedelta(days=days)).isoformat()


def generate_companies():
    return [
        {
            "company_id": "ORCX",
            "ticker": "ORCX",
            "name": "Oracle Resources Corp",
            "sector": "Energy",
            "industry": "Integrated Oil & Gas",
            "market_cap": 285_000_000_000,
            "enterprise_value": 320_000_000_000,
            "country": "United States",
            "exchange": "NYSE",
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 1.2,
            "annual_meeting_date": _future_date(95),
            "nomination_deadline": _future_date(35),
            "fiscal_year_end": "12-31",
            "has_poison_pill": False,
            "classified_board": False,
            "ceo_chair_combined": True,
            "majority_voting_standard": True,
        },
        {
            "company_id": "INDC",
            "ticker": "INDC",
            "name": "Industrial Diversified Corp",
            "sector": "Industrials",
            "industry": "Diversified Industrials",
            "market_cap": 18_400_000_000,
            "enterprise_value": 26_100_000_000,
            "country": "United States",
            "exchange": "NYSE",
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 2.4,
            "annual_meeting_date": _future_date(70),
            "nomination_deadline": _future_date(20),
            "fiscal_year_end": "12-31",
            "has_poison_pill": False,
            "classified_board": True,
            "ceo_chair_combined": True,
            "majority_voting_standard": False,
        },
        {
            "company_id": "NVTC",
            "ticker": "NVTC",
            "name": "Novatech Cloud Systems",
            "sector": "Technology",
            "industry": "Enterprise Software",
            "market_cap": 92_500_000_000,
            "enterprise_value": 85_000_000_000,
            "country": "United States",
            "exchange": "NASDAQ",
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 3.1,
            "annual_meeting_date": _future_date(140),
            "nomination_deadline": _future_date(85),
            "fiscal_year_end": "06-30",
            "has_poison_pill": False,
            "classified_board": False,
            "ceo_chair_combined": False,
            "majority_voting_standard": True,
        },
        {
            "company_id": "MDCO",
            "ticker": "MDCO",
            "name": "Meridian Media Holdings",
            "sector": "Communication Services",
            "industry": "Media & Entertainment",
            "market_cap": 14_200_000_000,
            "enterprise_value": 21_500_000_000,
            "country": "United States",
            "exchange": "NYSE",
            "controlled_company_flag": True,
            "dual_class_flag": True,
            "insider_ownership_pct": 38.0,
            "annual_meeting_date": _future_date(60),
            "nomination_deadline": _future_date(15),
            "fiscal_year_end": "12-31",
            "has_poison_pill": True,
            "classified_board": True,
            "ceo_chair_combined": True,
            "majority_voting_standard": False,
        },
        {
            "company_id": "RETR",
            "ticker": "RETR",
            "name": "Retailia Stores Inc",
            "sector": "Retail",
            "industry": "Specialty Retail",
            "market_cap": 6_800_000_000,
            "enterprise_value": 9_300_000_000,
            "country": "United States",
            "exchange": "NYSE",
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 4.7,
            "annual_meeting_date": _future_date(50),
            "nomination_deadline": _future_date(10),
            "fiscal_year_end": "01-31",
            "has_poison_pill": False,
            "classified_board": False,
            "ceo_chair_combined": True,
            "majority_voting_standard": True,
        },
        {
            "company_id": "HMED",
            "ticker": "HMED",
            "name": "Helix Medical Devices",
            "sector": "Healthcare",
            "industry": "Medical Devices",
            "market_cap": 11_900_000_000,
            "enterprise_value": 13_400_000_000,
            "country": "United States",
            "exchange": "NYSE",
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 5.2,
            "annual_meeting_date": _future_date(110),
            "nomination_deadline": _future_date(55),
            "fiscal_year_end": "12-31",
            "has_poison_pill": False,
            "classified_board": False,
            "ceo_chair_combined": False,
            "majority_voting_standard": True,
        },
        {
            "company_id": "CBNK",
            "ticker": "CBNK",
            "name": "Capital Bridge Bancorp",
            "sector": "Financials",
            "industry": "Regional Banks",
            "market_cap": 22_300_000_000,
            "enterprise_value": 24_800_000_000,
            "country": "United States",
            "exchange": "NYSE",
            "controlled_company_flag": False,
            "dual_class_flag": False,
            "insider_ownership_pct": 2.8,
            "annual_meeting_date": _future_date(80),
            "nomination_deadline": _future_date(25),
            "fiscal_year_end": "12-31",
            "has_poison_pill": False,
            "classified_board": False,
            "ceo_chair_combined": False,
            "majority_voting_standard": True,
        },
    ]


def generate_financials():
    """Financial features tuned to make each company's risk profile coherent."""
    return [
        # ORCX - Energy major, transition narrative, mid risk
        {
            "company_id": "ORCX",
            "tsr_1y_vs_peer": -4.0,
            "tsr_3y_vs_peer": -7.0,
            "tsr_5y_vs_peer": -10.0,
            "ev_ebitda_discount_vs_peer": -12.0,
            "pe_discount_vs_peer": -9.0,
            "roic_gap_vs_peer": -3.5,
            "ebitda_margin_gap_vs_peer": -2.0,
            "fcf_yield_vs_peer": 6.5,
            "capex_intensity_vs_peer": 4.0,
            "revenue_growth_vs_peer": -1.5,
            "leverage_vs_peer": 0.4,
            "guidance_miss_frequency": 0.20,
            "earnings_miss_frequency": 0.25,
            "mna_writeoff_history_score": 55.0,
            "say_on_pay_support_pct": 84.0,
            "director_vote_support_avg_pct": 91.0,
            "recent_stock_momentum_score": 48.0,
        },
        # INDC - Severely underperforming industrial conglomerate (CRITICAL)
        {
            "company_id": "INDC",
            "tsr_1y_vs_peer": -18.0,
            "tsr_3y_vs_peer": -34.0,
            "tsr_5y_vs_peer": -42.0,
            "ev_ebitda_discount_vs_peer": -28.0,
            "pe_discount_vs_peer": -24.0,
            "roic_gap_vs_peer": -8.5,
            "ebitda_margin_gap_vs_peer": -6.0,
            "fcf_yield_vs_peer": -2.5,
            "capex_intensity_vs_peer": 6.0,
            "revenue_growth_vs_peer": -3.5,
            "leverage_vs_peer": 1.8,
            "guidance_miss_frequency": 0.62,
            "earnings_miss_frequency": 0.58,
            "mna_writeoff_history_score": 84.0,
            "say_on_pay_support_pct": 71.0,
            "director_vote_support_avg_pct": 82.0,
            "recent_stock_momentum_score": 22.0,
        },
        # NVTC - Stable high-performing tech (LOW)
        {
            "company_id": "NVTC",
            "tsr_1y_vs_peer": 14.0,
            "tsr_3y_vs_peer": 22.0,
            "tsr_5y_vs_peer": 31.0,
            "ev_ebitda_discount_vs_peer": 8.0,
            "pe_discount_vs_peer": 6.0,
            "roic_gap_vs_peer": 5.0,
            "ebitda_margin_gap_vs_peer": 4.5,
            "fcf_yield_vs_peer": 3.5,
            "capex_intensity_vs_peer": -1.0,
            "revenue_growth_vs_peer": 6.5,
            "leverage_vs_peer": -0.6,
            "guidance_miss_frequency": 0.08,
            "earnings_miss_frequency": 0.10,
            "mna_writeoff_history_score": 25.0,
            "say_on_pay_support_pct": 95.0,
            "director_vote_support_avg_pct": 97.0,
            "recent_stock_momentum_score": 78.0,
        },
        # MDCO - Controlled media (governance-high, feasibility-low)
        {
            "company_id": "MDCO",
            "tsr_1y_vs_peer": -9.0,
            "tsr_3y_vs_peer": -15.0,
            "tsr_5y_vs_peer": -18.0,
            "ev_ebitda_discount_vs_peer": -18.0,
            "pe_discount_vs_peer": -14.0,
            "roic_gap_vs_peer": -4.0,
            "ebitda_margin_gap_vs_peer": -3.0,
            "fcf_yield_vs_peer": 1.0,
            "capex_intensity_vs_peer": 2.5,
            "revenue_growth_vs_peer": -2.0,
            "leverage_vs_peer": 1.1,
            "guidance_miss_frequency": 0.35,
            "earnings_miss_frequency": 0.32,
            "mna_writeoff_history_score": 60.0,
            "say_on_pay_support_pct": 65.0,
            "director_vote_support_avg_pct": 79.0,
            "recent_stock_momentum_score": 38.0,
        },
        # RETR - Retail with weak margins (HIGH)
        {
            "company_id": "RETR",
            "tsr_1y_vs_peer": -14.0,
            "tsr_3y_vs_peer": -22.0,
            "tsr_5y_vs_peer": -29.0,
            "ev_ebitda_discount_vs_peer": -16.0,
            "pe_discount_vs_peer": -13.0,
            "roic_gap_vs_peer": -5.5,
            "ebitda_margin_gap_vs_peer": -4.5,
            "fcf_yield_vs_peer": -0.5,
            "capex_intensity_vs_peer": 1.5,
            "revenue_growth_vs_peer": -4.0,
            "leverage_vs_peer": 0.9,
            "guidance_miss_frequency": 0.45,
            "earnings_miss_frequency": 0.50,
            "mna_writeoff_history_score": 45.0,
            "say_on_pay_support_pct": 75.0,
            "director_vote_support_avg_pct": 85.0,
            "recent_stock_momentum_score": 30.0,
        },
        # HMED - Healthcare, moderate, fixable
        {
            "company_id": "HMED",
            "tsr_1y_vs_peer": -6.0,
            "tsr_3y_vs_peer": -3.0,
            "tsr_5y_vs_peer": 2.0,
            "ev_ebitda_discount_vs_peer": -10.0,
            "pe_discount_vs_peer": -8.0,
            "roic_gap_vs_peer": -2.0,
            "ebitda_margin_gap_vs_peer": -1.5,
            "fcf_yield_vs_peer": 2.5,
            "capex_intensity_vs_peer": 1.0,
            "revenue_growth_vs_peer": 1.5,
            "leverage_vs_peer": 0.2,
            "guidance_miss_frequency": 0.18,
            "earnings_miss_frequency": 0.20,
            "mna_writeoff_history_score": 40.0,
            "say_on_pay_support_pct": 88.0,
            "director_vote_support_avg_pct": 93.0,
            "recent_stock_momentum_score": 55.0,
        },
        # CBNK - Bank, governance-sensitive
        {
            "company_id": "CBNK",
            "tsr_1y_vs_peer": -2.0,
            "tsr_3y_vs_peer": -5.0,
            "tsr_5y_vs_peer": -3.0,
            "ev_ebitda_discount_vs_peer": -7.0,
            "pe_discount_vs_peer": -5.0,
            "roic_gap_vs_peer": -1.5,
            "ebitda_margin_gap_vs_peer": -1.0,
            "fcf_yield_vs_peer": 4.0,
            "capex_intensity_vs_peer": 0.0,
            "revenue_growth_vs_peer": 0.0,
            "leverage_vs_peer": 0.5,
            "guidance_miss_frequency": 0.15,
            "earnings_miss_frequency": 0.18,
            "mna_writeoff_history_score": 50.0,
            "say_on_pay_support_pct": 82.0,
            "director_vote_support_avg_pct": 89.0,
            "recent_stock_momentum_score": 52.0,
        },
    ]


def generate_directors():
    """Generate at least 49 directors across the 7 companies (7 each)."""
    rows: List[Dict] = []

    director_seeds = {
        # company_id: list of (name, age, tenure, indep, committee, chair, boards,
        #                     prior_vote, sect_exp, capalloc_exp, tech_exp, climate_exp,
        #                     comp_flag, audit_flag, gov_flag)
        "ORCX": [
            ("Margaret R. Cole", 71, 16.0, True, "Audit", True, 3, 88.0, 80, 65, 30, 25, False, True, False),
            ("Robert Tanaka", 68, 13.0, True, "Compensation", True, 2, 84.0, 75, 55, 40, 30, True, False, False),
            ("Sarah Whitfield", 58, 4.0, True, "Governance", False, 1, 94.0, 70, 60, 50, 70, False, False, True),
            ("James A. Hollis", 65, 9.0, True, "Audit", False, 2, 92.0, 78, 70, 35, 28, False, True, False),
            ("Eleanor Park", 62, 7.0, True, "Nominating", False, 1, 90.0, 65, 55, 60, 65, False, False, True),
            ("Marcus L. Brennan", 67, 11.0, True, "Compensation", False, 2, 86.0, 72, 50, 30, 35, True, False, False),
            ("David Yusupov", 69, 14.0, False, "None", False, 0, 89.0, 85, 60, 25, 20, False, False, False),
        ],
        "INDC": [
            ("Theodore Blackwood", 73, 18.0, True, "Audit;Compensation", True, 4, 76.0, 70, 45, 25, 20, True, True, False),
            ("Patricia M. Gunn", 70, 15.0, True, "Compensation", True, 3, 78.0, 65, 50, 30, 22, True, False, False),
            ("Charles W. Eastman", 68, 12.0, True, "Audit", True, 3, 81.0, 60, 40, 28, 25, False, True, False),
            ("Helena Marquez", 64, 10.0, True, "Governance", False, 2, 84.0, 55, 45, 35, 30, False, False, True),
            ("Frank N. Doyle", 71, 16.0, True, "Strategy", False, 2, 79.0, 75, 35, 25, 18, False, False, False),
            ("Linda Trevino", 59, 5.0, True, "Audit", False, 1, 90.0, 60, 70, 50, 40, False, True, False),
            ("Walter J. Kim", 66, 13.0, False, "None", False, 1, 82.0, 80, 55, 30, 25, False, False, False),
        ],
        "NVTC": [
            ("Aiden Chen", 54, 3.0, True, "Audit", False, 1, 96.0, 80, 75, 90, 50, False, True, False),
            ("Dr. Rebecca Singh", 51, 4.0, True, "Compensation", True, 2, 95.0, 75, 65, 85, 55, True, False, False),
            ("Michael O'Brien", 59, 6.0, True, "Governance", True, 1, 97.0, 70, 70, 80, 50, False, False, True),
            ("Yuki Tanaka", 47, 2.0, True, "Audit", False, 1, 98.0, 78, 60, 92, 60, False, True, False),
            ("Carlos Mendez", 56, 5.0, True, "Nominating", False, 2, 94.0, 72, 75, 75, 45, False, False, True),
            ("Olivia Hartwell", 53, 4.0, True, "Compensation", False, 1, 96.0, 68, 70, 80, 55, True, False, False),
            ("Brian P. Foster", 60, 7.0, False, "None", False, 0, 95.0, 85, 80, 85, 50, False, False, False),
        ],
        "MDCO": [
            ("Vincent Caruso Jr.", 76, 24.0, False, "None", True, 1, 88.0, 80, 50, 35, 30, False, False, False),  # Founder
            ("Maria Caruso", 72, 22.0, False, "None", False, 0, 89.0, 70, 45, 30, 25, False, False, False),  # Family
            ("Anthony R. Levin", 70, 18.0, True, "Audit", True, 3, 75.0, 65, 55, 40, 30, False, True, False),
            ("Diane K. Mitsubishi", 67, 14.0, True, "Compensation", True, 2, 73.0, 60, 50, 45, 35, True, False, False),
            ("Howard Stelman", 69, 16.0, True, "Governance", False, 2, 78.0, 62, 48, 38, 30, False, False, True),
            ("Patricia O'Connell", 63, 8.0, True, "Audit", False, 1, 85.0, 65, 60, 50, 45, False, True, False),
            ("Gerald F. Stein", 71, 19.0, True, "Strategy", False, 1, 80.0, 70, 50, 35, 28, False, False, False),
        ],
        "RETR": [
            ("Stephen Holbrook", 66, 14.0, False, "None", True, 1, 81.0, 70, 50, 30, 25, False, False, False),
            ("Janet Greenwood", 65, 12.0, True, "Audit", True, 2, 80.0, 60, 55, 35, 30, False, True, False),
            ("Rashid Patel", 61, 9.0, True, "Compensation", True, 2, 84.0, 65, 50, 40, 35, True, False, False),
            ("Mary B. Sutherland", 68, 15.0, True, "Governance", True, 3, 78.0, 55, 45, 30, 28, False, False, True),
            ("Tom J. Wexler", 58, 6.0, True, "Nominating", False, 1, 89.0, 75, 65, 50, 40, False, False, True),
            ("Andrea Schulman", 56, 4.0, True, "Audit", False, 1, 92.0, 70, 60, 55, 45, False, True, False),
            ("Daniel R. Powell", 64, 11.0, True, "Compensation", False, 2, 83.0, 68, 55, 40, 30, True, False, False),
        ],
        "HMED": [
            ("Dr. Elena Rodriguez", 58, 5.0, True, "Audit", True, 1, 94.0, 80, 60, 50, 40, False, True, False),
            ("Bradley K. Yates", 62, 8.0, True, "Compensation", True, 2, 91.0, 75, 65, 45, 35, True, False, False),
            ("Patricia Liang MD", 55, 4.0, True, "Governance", False, 1, 95.0, 82, 55, 40, 38, False, False, True),
            ("Stephen Albright", 67, 11.0, True, "Audit", False, 2, 89.0, 70, 70, 50, 30, False, True, False),
            ("Karen M. Vasquez", 60, 7.0, True, "Nominating", False, 1, 92.0, 72, 60, 55, 40, False, False, True),
            ("Dr. Pavel Ostrovsky", 64, 9.0, True, "Compensation", False, 2, 90.0, 78, 55, 48, 35, True, False, False),
            ("Charles E. Devereaux", 69, 13.0, False, "None", False, 0, 88.0, 80, 65, 45, 30, False, False, False),
        ],
        "CBNK": [
            ("Walter G. Hampton", 70, 12.0, True, "Audit", True, 2, 87.0, 80, 65, 35, 25, False, True, False),
            ("Susan E. Lin", 64, 9.0, True, "Risk", True, 1, 90.0, 78, 70, 40, 30, False, True, False),
            ("Mohammad Rahman", 61, 7.0, True, "Compensation", True, 1, 89.0, 72, 60, 35, 28, True, False, False),
            ("Caroline B. Wright", 58, 5.0, True, "Governance", False, 2, 92.0, 70, 65, 45, 35, False, False, True),
            ("Joseph T. Marconi", 63, 8.0, True, "Audit", False, 1, 88.0, 75, 68, 38, 30, False, True, False),
            ("Margaret Yoshida", 56, 4.0, True, "Compliance", False, 1, 93.0, 73, 62, 42, 32, False, False, True),
            ("Robert J. Kim", 59, 6.0, False, "None", False, 0, 91.0, 80, 70, 35, 25, False, False, False),
        ],
    }

    counter = 1
    for company_id, dirs in director_seeds.items():
        for d in dirs:
            (name, age, tenure, indep, committee, chair, boards, prior_vote,
             sect, capalloc, tech, climate, comp_flag, audit_flag, gov_flag) = d
            rows.append({
                "director_id": f"D{counter:03d}",
                "company_id": company_id,
                "name": name,
                "age": age,
                "tenure_years": tenure,
                "independent": indep,
                "committee_roles": committee,
                "is_committee_chair": chair,
                "other_public_boards": boards,
                "prior_vote_support_pct": prior_vote,
                "sector_expertise_score": sect,
                "capital_allocation_expertise_score": capalloc,
                "technology_expertise_score": tech,
                "climate_transition_expertise_score": climate,
                "compensation_oversight_flag": comp_flag,
                "audit_oversight_flag": audit_flag,
                "governance_oversight_flag": gov_flag,
            })
            counter += 1
    return rows


def generate_shareholders():
    """Generate >= 25 unique shareholders representing the major holder types."""
    return [
        # Passive giants
        {"holder_id": "H001", "name": "Global Index Trust", "holder_type": "passive",
         "governance_sensitivity_score": 70, "activism_support_history_score": 35,
         "proxy_advisor_dependence_score": 80, "esg_sensitivity_score": 60,
         "value_orientation_score": 40, "settlement_preference_score": 55,
         "retail_mobilization_score": 5},
        {"holder_id": "H002", "name": "Sentinel Index Partners", "holder_type": "passive",
         "governance_sensitivity_score": 68, "activism_support_history_score": 32,
         "proxy_advisor_dependence_score": 78, "esg_sensitivity_score": 55,
         "value_orientation_score": 38, "settlement_preference_score": 60,
         "retail_mobilization_score": 5},
        {"holder_id": "H003", "name": "Liberty Passive Funds", "holder_type": "passive",
         "governance_sensitivity_score": 62, "activism_support_history_score": 30,
         "proxy_advisor_dependence_score": 75, "esg_sensitivity_score": 50,
         "value_orientation_score": 40, "settlement_preference_score": 58,
         "retail_mobilization_score": 5},
        # Active value
        {"holder_id": "H004", "name": "Crestwood Value Partners", "holder_type": "active",
         "governance_sensitivity_score": 60, "activism_support_history_score": 70,
         "proxy_advisor_dependence_score": 40, "esg_sensitivity_score": 35,
         "value_orientation_score": 90, "settlement_preference_score": 45,
         "retail_mobilization_score": 10},
        {"holder_id": "H005", "name": "Halberd Capital Mgmt", "holder_type": "active",
         "governance_sensitivity_score": 65, "activism_support_history_score": 75,
         "proxy_advisor_dependence_score": 35, "esg_sensitivity_score": 40,
         "value_orientation_score": 85, "settlement_preference_score": 40,
         "retail_mobilization_score": 15},
        {"holder_id": "H006", "name": "Pinnacle Quality Investors", "holder_type": "active",
         "governance_sensitivity_score": 55, "activism_support_history_score": 45,
         "proxy_advisor_dependence_score": 30, "esg_sensitivity_score": 45,
         "value_orientation_score": 75, "settlement_preference_score": 50,
         "retail_mobilization_score": 8},
        # Pension funds
        {"holder_id": "H007", "name": "Public Employees Retirement", "holder_type": "pension",
         "governance_sensitivity_score": 85, "activism_support_history_score": 60,
         "proxy_advisor_dependence_score": 70, "esg_sensitivity_score": 80,
         "value_orientation_score": 50, "settlement_preference_score": 50,
         "retail_mobilization_score": 5},
        {"holder_id": "H008", "name": "Teachers Pension Trust", "holder_type": "pension",
         "governance_sensitivity_score": 82, "activism_support_history_score": 55,
         "proxy_advisor_dependence_score": 68, "esg_sensitivity_score": 85,
         "value_orientation_score": 45, "settlement_preference_score": 55,
         "retail_mobilization_score": 5},
        {"holder_id": "H009", "name": "Northern Pension Alliance", "holder_type": "pension",
         "governance_sensitivity_score": 78, "activism_support_history_score": 50,
         "proxy_advisor_dependence_score": 65, "esg_sensitivity_score": 72,
         "value_orientation_score": 48, "settlement_preference_score": 60,
         "retail_mobilization_score": 5},
        # Activists
        {"holder_id": "H010", "name": "Hawk Ridge Activist Partners", "holder_type": "activist",
         "governance_sensitivity_score": 75, "activism_support_history_score": 95,
         "proxy_advisor_dependence_score": 30, "esg_sensitivity_score": 40,
         "value_orientation_score": 80, "settlement_preference_score": 60,
         "retail_mobilization_score": 30},
        {"holder_id": "H011", "name": "Granite Activist Capital", "holder_type": "activist",
         "governance_sensitivity_score": 72, "activism_support_history_score": 92,
         "proxy_advisor_dependence_score": 25, "esg_sensitivity_score": 35,
         "value_orientation_score": 85, "settlement_preference_score": 65,
         "retail_mobilization_score": 35},
        {"holder_id": "H012", "name": "Trident Engaged Holdings", "holder_type": "activist",
         "governance_sensitivity_score": 70, "activism_support_history_score": 90,
         "proxy_advisor_dependence_score": 30, "esg_sensitivity_score": 50,
         "value_orientation_score": 80, "settlement_preference_score": 55,
         "retail_mobilization_score": 40},
        # Insiders
        {"holder_id": "H013", "name": "CEO & Affiliated Trusts (ORCX)", "holder_type": "insider",
         "governance_sensitivity_score": 30, "activism_support_history_score": 5,
         "proxy_advisor_dependence_score": 20, "esg_sensitivity_score": 40,
         "value_orientation_score": 50, "settlement_preference_score": 50,
         "retail_mobilization_score": 5},
        {"holder_id": "H014", "name": "Caruso Family Holdings (MDCO)", "holder_type": "insider",
         "governance_sensitivity_score": 25, "activism_support_history_score": 5,
         "proxy_advisor_dependence_score": 15, "esg_sensitivity_score": 35,
         "value_orientation_score": 45, "settlement_preference_score": 45,
         "retail_mobilization_score": 5},
        {"holder_id": "H015", "name": "Founder Trust (NVTC)", "holder_type": "insider",
         "governance_sensitivity_score": 35, "activism_support_history_score": 10,
         "proxy_advisor_dependence_score": 25, "esg_sensitivity_score": 45,
         "value_orientation_score": 55, "settlement_preference_score": 50,
         "retail_mobilization_score": 5},
        # Retail aggregator (synthetic)
        {"holder_id": "H016", "name": "Retail Investor Aggregate", "holder_type": "retail",
         "governance_sensitivity_score": 45, "activism_support_history_score": 50,
         "proxy_advisor_dependence_score": 30, "esg_sensitivity_score": 50,
         "value_orientation_score": 55, "settlement_preference_score": 50,
         "retail_mobilization_score": 70},
        # Sovereign / SWF
        {"holder_id": "H017", "name": "Norwegian-Style Sovereign Fund", "holder_type": "sovereign",
         "governance_sensitivity_score": 85, "activism_support_history_score": 55,
         "proxy_advisor_dependence_score": 60, "esg_sensitivity_score": 90,
         "value_orientation_score": 60, "settlement_preference_score": 65,
         "retail_mobilization_score": 5},
        {"holder_id": "H018", "name": "Pacific Sovereign Allocator", "holder_type": "sovereign",
         "governance_sensitivity_score": 70, "activism_support_history_score": 45,
         "proxy_advisor_dependence_score": 55, "esg_sensitivity_score": 65,
         "value_orientation_score": 60, "settlement_preference_score": 70,
         "retail_mobilization_score": 5},
        # Specialized
        {"holder_id": "H019", "name": "Vanguard-Style Equity Index", "holder_type": "passive",
         "governance_sensitivity_score": 75, "activism_support_history_score": 38,
         "proxy_advisor_dependence_score": 65, "esg_sensitivity_score": 62,
         "value_orientation_score": 45, "settlement_preference_score": 55,
         "retail_mobilization_score": 5},
        {"holder_id": "H020", "name": "Marlin Long-Only Equity", "holder_type": "active",
         "governance_sensitivity_score": 65, "activism_support_history_score": 55,
         "proxy_advisor_dependence_score": 45, "esg_sensitivity_score": 55,
         "value_orientation_score": 70, "settlement_preference_score": 50,
         "retail_mobilization_score": 10},
        {"holder_id": "H021", "name": "Atlas Growth Capital", "holder_type": "active",
         "governance_sensitivity_score": 50, "activism_support_history_score": 40,
         "proxy_advisor_dependence_score": 35, "esg_sensitivity_score": 50,
         "value_orientation_score": 50, "settlement_preference_score": 55,
         "retail_mobilization_score": 12},
        {"holder_id": "H022", "name": "Bedrock Income Fund", "holder_type": "active",
         "governance_sensitivity_score": 60, "activism_support_history_score": 50,
         "proxy_advisor_dependence_score": 50, "esg_sensitivity_score": 45,
         "value_orientation_score": 75, "settlement_preference_score": 65,
         "retail_mobilization_score": 8},
        {"holder_id": "H023", "name": "Coastal Pension Board", "holder_type": "pension",
         "governance_sensitivity_score": 80, "activism_support_history_score": 58,
         "proxy_advisor_dependence_score": 72, "esg_sensitivity_score": 78,
         "value_orientation_score": 50, "settlement_preference_score": 60,
         "retail_mobilization_score": 5},
        {"holder_id": "H024", "name": "Heritage Family Office", "holder_type": "other",
         "governance_sensitivity_score": 55, "activism_support_history_score": 45,
         "proxy_advisor_dependence_score": 30, "esg_sensitivity_score": 50,
         "value_orientation_score": 65, "settlement_preference_score": 55,
         "retail_mobilization_score": 10},
        {"holder_id": "H025", "name": "Apex Hedge Fund Multi-Strat", "holder_type": "active",
         "governance_sensitivity_score": 55, "activism_support_history_score": 65,
         "proxy_advisor_dependence_score": 30, "esg_sensitivity_score": 35,
         "value_orientation_score": 75, "settlement_preference_score": 55,
         "retail_mobilization_score": 15},
        {"holder_id": "H026", "name": "Sigma Long-Short Equity", "holder_type": "active",
         "governance_sensitivity_score": 58, "activism_support_history_score": 60,
         "proxy_advisor_dependence_score": 32, "esg_sensitivity_score": 40,
         "value_orientation_score": 70, "settlement_preference_score": 50,
         "retail_mobilization_score": 12},
    ]


def generate_ownership():
    """Build ownership tables that approximate realistic float distributions."""
    ownership: List[Dict] = []

    # ORCX - widely held energy major
    orcx = [
        ("H001", 7.8, 0.1, 7.8), ("H002", 7.2, -0.2, 7.2), ("H019", 8.1, 0.3, 8.1),
        ("H003", 4.5, 0.0, 4.5), ("H007", 3.2, 0.1, 3.2), ("H008", 2.8, 0.0, 2.8),
        ("H017", 2.5, 0.4, 2.5), ("H004", 1.8, 0.5, 1.8), ("H020", 1.5, 0.2, 1.5),
        ("H013", 1.2, 0.0, 1.2), ("H016", 12.0, -0.5, 12.0), ("H010", 0.9, 0.7, 0.9),
        ("H023", 1.6, 0.1, 1.6),
    ]
    for h, pct, qoq, vp in orcx:
        ownership.append({"company_id": "ORCX", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    # INDC - mid-cap industrial with activist already accumulating
    indc = [
        ("H001", 8.5, 0.0, 8.5), ("H002", 7.8, 0.1, 7.8), ("H019", 7.4, 0.0, 7.4),
        ("H004", 4.2, 1.5, 4.2), ("H005", 5.8, 2.0, 5.8), ("H010", 6.4, 3.1, 6.4),
        ("H025", 2.8, 0.8, 2.8), ("H007", 3.1, 0.0, 3.1), ("H008", 2.6, 0.0, 2.6),
        ("H023", 2.1, 0.0, 2.1), ("H016", 14.0, -0.3, 14.0), ("H020", 2.0, 0.5, 2.0),
        ("H022", 1.7, 0.2, 1.7),
    ]
    for h, pct, qoq, vp in indc:
        ownership.append({"company_id": "INDC", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    # NVTC - tech, founder-aligned
    nvtc = [
        ("H001", 8.2, 0.0, 8.2), ("H002", 7.6, 0.0, 7.6), ("H019", 8.5, 0.1, 8.5),
        ("H021", 5.2, 0.6, 5.2), ("H015", 3.1, 0.0, 3.1), ("H006", 3.0, 0.3, 3.0),
        ("H007", 2.4, 0.0, 2.4), ("H017", 2.0, 0.2, 2.0), ("H020", 1.8, 0.4, 1.8),
        ("H016", 18.0, 0.2, 18.0), ("H024", 1.5, 0.0, 1.5),
    ]
    for h, pct, qoq, vp in nvtc:
        ownership.append({"company_id": "NVTC", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    # MDCO - controlled, dual-class (insiders dominate voting)
    mdco = [
        ("H014", 8.0, 0.0, 62.0),  # Caruso family - super-voting
        ("H001", 6.5, 0.0, 4.5), ("H002", 5.8, 0.0, 4.0), ("H019", 6.2, 0.0, 4.3),
        ("H004", 2.8, 0.3, 1.9), ("H010", 3.1, 0.8, 2.1), ("H022", 2.3, 0.1, 1.6),
        ("H007", 1.9, 0.0, 1.3), ("H008", 1.6, 0.0, 1.1), ("H016", 11.0, -0.4, 7.6),
        ("H024", 1.4, 0.0, 1.0),
    ]
    for h, pct, qoq, vp in mdco:
        ownership.append({"company_id": "MDCO", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    # RETR - small-mid retail
    retr = [
        ("H001", 8.8, 0.0, 8.8), ("H002", 7.6, 0.0, 7.6), ("H019", 6.9, 0.1, 6.9),
        ("H004", 4.7, 1.2, 4.7), ("H011", 5.2, 2.4, 5.2), ("H005", 3.8, 1.0, 3.8),
        ("H025", 2.6, 0.6, 2.6), ("H007", 2.4, 0.0, 2.4), ("H008", 2.1, 0.0, 2.1),
        ("H022", 2.0, 0.3, 2.0), ("H016", 13.0, -0.4, 13.0), ("H020", 1.9, 0.4, 1.9),
    ]
    for h, pct, qoq, vp in retr:
        ownership.append({"company_id": "RETR", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    # HMED - healthcare, M&A speculation
    hmed = [
        ("H001", 8.2, 0.1, 8.2), ("H002", 7.5, 0.0, 7.5), ("H019", 7.0, 0.2, 7.0),
        ("H006", 4.5, 0.5, 4.5), ("H004", 3.2, 0.8, 3.2), ("H020", 2.8, 0.3, 2.8),
        ("H007", 2.6, 0.0, 2.6), ("H008", 2.2, 0.0, 2.2), ("H012", 2.4, 0.6, 2.4),
        ("H017", 1.9, 0.2, 1.9), ("H016", 12.0, 0.1, 12.0), ("H021", 1.7, 0.4, 1.7),
    ]
    for h, pct, qoq, vp in hmed:
        ownership.append({"company_id": "HMED", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    # CBNK - regional bank
    cbnk = [
        ("H001", 8.0, 0.0, 8.0), ("H002", 7.3, 0.0, 7.3), ("H019", 7.5, 0.0, 7.5),
        ("H007", 3.0, 0.0, 3.0), ("H008", 2.6, 0.0, 2.6), ("H023", 2.4, 0.0, 2.4),
        ("H006", 3.4, 0.2, 3.4), ("H022", 2.6, 0.1, 2.6), ("H017", 2.0, 0.1, 2.0),
        ("H020", 1.8, 0.3, 1.8), ("H016", 13.0, -0.1, 13.0), ("H024", 1.5, 0.0, 1.5),
    ]
    for h, pct, qoq, vp in cbnk:
        ownership.append({"company_id": "CBNK", "holder_id": h, "ownership_pct": pct,
                          "qoq_change_pct": qoq, "voting_power_pct": vp})

    return ownership


def generate_campaigns():
    """Eight synthetic historical campaigns."""
    return [
        {"campaign_id": "C001", "company_id": "INDC", "activist_name": "Granite Activist Capital",
         "campaign_start_date": _past_date(420), "stake_pct": 5.4,
         "thesis_type": "Board Refresh + Capital Allocation Discipline",
         "board_seats_requested": 3, "board_seats_won": 2, "settled": True, "went_to_vote": False,
         "stock_reaction_1d": 6.8, "stock_reaction_30d": 12.5, "outcome": "Settled - 2 seats"},
        {"campaign_id": "C002", "company_id": "RETR", "activist_name": "Hawk Ridge Activist Partners",
         "campaign_start_date": _past_date(310), "stake_pct": 4.1,
         "thesis_type": "Margin Improvement / Operational Efficiency",
         "board_seats_requested": 2, "board_seats_won": 1, "settled": True, "went_to_vote": False,
         "stock_reaction_1d": 4.2, "stock_reaction_30d": 8.4, "outcome": "Settled - 1 seat + comp reform"},
        {"campaign_id": "C003", "company_id": "ORCX", "activist_name": "Trident Engaged Holdings",
         "campaign_start_date": _past_date(220), "stake_pct": 1.6,
         "thesis_type": "Climate / Transition Risk",
         "board_seats_requested": 2, "board_seats_won": 2, "settled": False, "went_to_vote": True,
         "stock_reaction_1d": 1.5, "stock_reaction_30d": 3.0, "outcome": "Activist won - shareholders sided with transition slate"},
        {"campaign_id": "C004", "company_id": "MDCO", "activist_name": "Granite Activist Capital",
         "campaign_start_date": _past_date(180), "stake_pct": 3.2,
         "thesis_type": "CEO Succession / Leadership Accountability",
         "board_seats_requested": 1, "board_seats_won": 0, "settled": False, "went_to_vote": True,
         "stock_reaction_1d": -2.1, "stock_reaction_30d": -3.4, "outcome": "Activist defeated - dual-class control held"},
        {"campaign_id": "C005", "company_id": "HMED", "activist_name": "Trident Engaged Holdings",
         "campaign_start_date": _past_date(150), "stake_pct": 2.4,
         "thesis_type": "Breakup or Strategic Alternatives",
         "board_seats_requested": 2, "board_seats_won": 1, "settled": True, "went_to_vote": False,
         "stock_reaction_1d": 5.8, "stock_reaction_30d": 11.2, "outcome": "Settled - strategic review committee formed"},
        {"campaign_id": "C006", "company_id": "INDC", "activist_name": "Hawk Ridge Activist Partners",
         "campaign_start_date": _past_date(90), "stake_pct": 6.4,
         "thesis_type": "Breakup or Strategic Alternatives",
         "board_seats_requested": 4, "board_seats_won": 0, "settled": False, "went_to_vote": False,
         "stock_reaction_1d": 8.4, "stock_reaction_30d": 14.0, "outcome": "Active - 13D filed"},
        {"campaign_id": "C007", "company_id": "CBNK", "activist_name": "Crestwood Value Partners",
         "campaign_start_date": _past_date(540), "stake_pct": 2.1,
         "thesis_type": "Compensation Alignment",
         "board_seats_requested": 1, "board_seats_won": 0, "settled": True, "went_to_vote": False,
         "stock_reaction_1d": 1.8, "stock_reaction_30d": 2.5, "outcome": "Settled - pay reform, no seat"},
        {"campaign_id": "C008", "company_id": "RETR", "activist_name": "Apex Hedge Fund Multi-Strat",
         "campaign_start_date": _past_date(45), "stake_pct": 3.7,
         "thesis_type": "Board Refresh + Capital Allocation Discipline",
         "board_seats_requested": 2, "board_seats_won": 0, "settled": False, "went_to_vote": False,
         "stock_reaction_1d": 5.2, "stock_reaction_30d": 7.8, "outcome": "Active - public letter filed"},
    ]


def generate_activist_archetypes():
    """Eight activist archetypes."""
    return [
        {"archetype_id": "A001", "name": "Confrontational Public-Letter Activist",
         "style": "public letter",
         "preferred_market_cap_min": 5_000_000_000, "preferred_market_cap_max": 200_000_000_000,
         "board_seat_preference": 3, "public_campaign_aggressiveness": 88,
         "settlement_preference": 35, "esg_weight": 20, "value_weight": 80,
         "governance_weight": 70, "operational_weight": 70, "typical_stake_pct": 5.0},
        {"archetype_id": "A002", "name": "Constructive Engagement Activist",
         "style": "quiet engagement",
         "preferred_market_cap_min": 2_000_000_000, "preferred_market_cap_max": 100_000_000_000,
         "board_seat_preference": 1, "public_campaign_aggressiveness": 35,
         "settlement_preference": 85, "esg_weight": 40, "value_weight": 65,
         "governance_weight": 60, "operational_weight": 65, "typical_stake_pct": 2.5},
        {"archetype_id": "A003", "name": "Operational Turnaround Activist",
         "style": "short-slate proxy contest",
         "preferred_market_cap_min": 1_000_000_000, "preferred_market_cap_max": 50_000_000_000,
         "board_seat_preference": 2, "public_campaign_aggressiveness": 70,
         "settlement_preference": 55, "esg_weight": 25, "value_weight": 60,
         "governance_weight": 50, "operational_weight": 90, "typical_stake_pct": 4.5},
        {"archetype_id": "A004", "name": "Breakup / Strategic-Alternatives Activist",
         "style": "strategic alternatives campaign",
         "preferred_market_cap_min": 3_000_000_000, "preferred_market_cap_max": 80_000_000_000,
         "board_seat_preference": 2, "public_campaign_aggressiveness": 75,
         "settlement_preference": 50, "esg_weight": 20, "value_weight": 85,
         "governance_weight": 55, "operational_weight": 60, "typical_stake_pct": 4.0},
        {"archetype_id": "A005", "name": "ESG / Transition Activist",
         "style": "ESG/transition campaign",
         "preferred_market_cap_min": 10_000_000_000, "preferred_market_cap_max": 500_000_000_000,
         "board_seat_preference": 2, "public_campaign_aggressiveness": 60,
         "settlement_preference": 60, "esg_weight": 95, "value_weight": 40,
         "governance_weight": 65, "operational_weight": 45, "typical_stake_pct": 1.2},
        {"archetype_id": "A006", "name": "Settlement-First Pragmatist",
         "style": "settlement-oriented pressure",
         "preferred_market_cap_min": 1_500_000_000, "preferred_market_cap_max": 60_000_000_000,
         "board_seat_preference": 1, "public_campaign_aggressiveness": 40,
         "settlement_preference": 90, "esg_weight": 30, "value_weight": 70,
         "governance_weight": 55, "operational_weight": 60, "typical_stake_pct": 3.0},
        {"archetype_id": "A007", "name": "Governance-Focused Pension/SWF Engager",
         "style": "quiet engagement",
         "preferred_market_cap_min": 20_000_000_000, "preferred_market_cap_max": 1_000_000_000_000,
         "board_seat_preference": 1, "public_campaign_aggressiveness": 25,
         "settlement_preference": 80, "esg_weight": 80, "value_weight": 45,
         "governance_weight": 95, "operational_weight": 30, "typical_stake_pct": 1.0},
        {"archetype_id": "A008", "name": "Control-Seeking Acquirer-Activist",
         "style": "control-oriented campaign",
         "preferred_market_cap_min": 500_000_000, "preferred_market_cap_max": 25_000_000_000,
         "board_seat_preference": 5, "public_campaign_aggressiveness": 90,
         "settlement_preference": 25, "esg_weight": 10, "value_weight": 80,
         "governance_weight": 60, "operational_weight": 85, "typical_stake_pct": 9.0},
    ]


def generate_proxy_advisor_cases():
    """15 synthetic proxy advisor reference cases for shadow model calibration."""
    return [
        {"case_id": "PA001", "context": "Director tenure>15y, audit chair, TSR -25% 3y",
         "outcome": "AGAINST director", "weight": 0.85},
        {"case_id": "PA002", "context": "Say-on-pay support 71%, no comp reform",
         "outcome": "AGAINST pay", "weight": 0.90},
        {"case_id": "PA003", "context": "Activist nominee with capital allocation track record",
         "outcome": "FOR 1 activist nominee", "weight": 0.70},
        {"case_id": "PA004", "context": "Dual-class with no sunset; underperforming",
         "outcome": "AGAINST governance; AGAINST CEO/chair", "weight": 0.80},
        {"case_id": "PA005", "context": "Outperforming tech firm, full board recommended",
         "outcome": "FOR all management nominees", "weight": 0.95},
        {"case_id": "PA006", "context": "Long-tenured comp chair, low SoP, expanded grants",
         "outcome": "AGAINST comp chair", "weight": 0.88},
        {"case_id": "PA007", "context": "Energy company, no climate-expert director, TSR-lag",
         "outcome": "FOR transition-expert activist nominee", "weight": 0.65},
        {"case_id": "PA008", "context": "Healthcare; M&A writeoffs; activist asks for strategic review",
         "outcome": "FOR strategic review committee", "weight": 0.72},
        {"case_id": "PA009", "context": "Industrial; persistent guidance misses, breakup thesis credible",
         "outcome": "FOR 2 activist nominees", "weight": 0.78},
        {"case_id": "PA010", "context": "Retail; weak margins, activist wants comp + ops reform",
         "outcome": "FOR 1 activist nominee; AGAINST pay", "weight": 0.74},
        {"case_id": "PA011", "context": "Bank; governance solid, narrow underperformance",
         "outcome": "FOR all management nominees", "weight": 0.80},
        {"case_id": "PA012", "context": "Media; controlled; activist publicly critical",
         "outcome": "AGAINST 2 long-tenured directors (limited practical effect)", "weight": 0.55},
        {"case_id": "PA013", "context": "Classified board obstructs activist; activist sues",
         "outcome": "FOR declassification proposal", "weight": 0.82},
        {"case_id": "PA014", "context": "Activist nominee with weaker resume than incumbents",
         "outcome": "AGAINST activist nominee", "weight": 0.70},
        {"case_id": "PA015", "context": "Company adopts ROIC/FCF comp metric pre-vote",
         "outcome": "FOR pay; FOR comp chair", "weight": 0.83},
    ]


def generate_events():
    """20 synthetic recent events."""
    return [
        {"event_id": "E001", "company_id": "INDC", "event_date": _past_date(15),
         "event_type": "earnings_miss", "severity_score": 80,
         "description": "Q4 EPS missed consensus by 18%; guidance cut for next year."},
        {"event_id": "E002", "company_id": "INDC", "event_date": _past_date(5),
         "event_type": "activist_13d", "severity_score": 90,
         "description": "Hawk Ridge filed 13D disclosing 6.4% stake."},
        {"event_id": "E003", "company_id": "INDC", "event_date": _past_date(35),
         "event_type": "guidance_cut", "severity_score": 75,
         "description": "FY guidance cut for second time this fiscal year."},
        {"event_id": "E004", "company_id": "RETR", "event_date": _past_date(20),
         "event_type": "failed_say_on_pay", "severity_score": 85,
         "description": "Say-on-pay support fell to 71%; binding vote in next AGM cycle."},
        {"event_id": "E005", "company_id": "RETR", "event_date": _past_date(8),
         "event_type": "media_controversy", "severity_score": 55,
         "description": "Wall Street Journal published critical capital allocation feature."},
        {"event_id": "E006", "company_id": "ORCX", "event_date": _past_date(40),
         "event_type": "director_departure", "severity_score": 50,
         "description": "Long-tenured independent director announced retirement."},
        {"event_id": "E007", "company_id": "ORCX", "event_date": _past_date(12),
         "event_type": "ma_announcement", "severity_score": 60,
         "description": "Announced $8B upstream acquisition; mixed analyst reaction."},
        {"event_id": "E008", "company_id": "MDCO", "event_date": _past_date(25),
         "event_type": "ceo_change_rumor", "severity_score": 65,
         "description": "Rumored CEO succession plan under review by board."},
        {"event_id": "E009", "company_id": "MDCO", "event_date": _past_date(10),
         "event_type": "stock_drop", "severity_score": 70,
         "description": "Stock dropped 12% in one week on streaming subscriber miss."},
        {"event_id": "E010", "company_id": "HMED", "event_date": _past_date(50),
         "event_type": "ma_announcement", "severity_score": 55,
         "description": "Analyst speculation of strategic review/sale process."},
        {"event_id": "E011", "company_id": "HMED", "event_date": _past_date(18),
         "event_type": "earnings_miss", "severity_score": 50,
         "description": "Q3 missed top-line by 3% but reaffirmed FY guide."},
        {"event_id": "E012", "company_id": "CBNK", "event_date": _past_date(30),
         "event_type": "director_departure", "severity_score": 35,
         "description": "Audit chair announced retirement effective AGM."},
        {"event_id": "E013", "company_id": "CBNK", "event_date": _past_date(60),
         "event_type": "guidance_cut", "severity_score": 50,
         "description": "Net interest margin guidance trimmed."},
        {"event_id": "E014", "company_id": "NVTC", "event_date": _past_date(40),
         "event_type": "earnings_beat", "severity_score": 20,
         "description": "Q2 earnings beat; raised guidance."},
        {"event_id": "E015", "company_id": "NVTC", "event_date": _past_date(80),
         "event_type": "buyback_announcement", "severity_score": 25,
         "description": "$3B buyback authorization approved."},
        {"event_id": "E016", "company_id": "ORCX", "event_date": _past_date(70),
         "event_type": "media_controversy", "severity_score": 60,
         "description": "Climate-disclosure shareholder proposal reached 38% support."},
        {"event_id": "E017", "company_id": "INDC", "event_date": _past_date(120),
         "event_type": "stock_drop", "severity_score": 65,
         "description": "12-month stock down 22%; underperformed peers by 18%."},
        {"event_id": "E018", "company_id": "RETR", "event_date": _past_date(75),
         "event_type": "ceo_change_rumor", "severity_score": 55,
         "description": "Board reportedly evaluating CEO succession."},
        {"event_id": "E019", "company_id": "MDCO", "event_date": _past_date(95),
         "event_type": "failed_say_on_pay", "severity_score": 70,
         "description": "Say-on-pay 65% support; below majority advisory comfort."},
        {"event_id": "E020", "company_id": "HMED", "event_date": _past_date(3),
         "event_type": "activist_13d", "severity_score": 80,
         "description": "Trident Engaged disclosed 2.4% stake and intent to seek strategic review."},
    ]


def _write_csv(path, rows):
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def generate_all(data_dir="data"):
    """Generate all CSVs in the given data directory. Returns mapping of name->path."""
    dp = Path(data_dir)
    dp.mkdir(parents=True, exist_ok=True)

    mapping = {
        "sample_companies.csv": generate_companies(),
        "sample_financials.csv": generate_financials(),
        "sample_directors.csv": generate_directors(),
        "sample_shareholders.csv": generate_shareholders(),
        "sample_ownership.csv": generate_ownership(),
        "sample_campaigns.csv": generate_campaigns(),
        "sample_activist_archetypes.csv": generate_activist_archetypes(),
        "sample_proxy_advisor_cases.csv": generate_proxy_advisor_cases(),
        "sample_events.csv": generate_events(),
    }
    out_paths = {}
    for fname, rows in mapping.items():
        out_paths[fname] = str(dp / fname)
        _write_csv(dp / fname, rows)
    return out_paths


if __name__ == "__main__":
    paths = generate_all("data")
    for n, p in paths.items():
        print(f"Wrote {p}")
