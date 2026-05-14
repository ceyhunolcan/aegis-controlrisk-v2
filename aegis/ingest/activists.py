# Real activist archetypes. This is the proprietary moat: a curated
# database of the actual major activists, their tactics, AUM, preferred
# target profiles, and signature campaign styles.
#
# Compiled from public sources: 13D filings, news coverage, fund
# letters, hedge-fund databases (Insightia summaries, SharkRepellent
# news). Updated periodically.
#
# Each archetype includes:
#   - archetype_id: stable identifier
#   - name: fund/firm name
#   - aum_usd: approximate assets under management (USD)
#   - typical_stake_pct: average position size when active
#   - typical_seats_requested: median board seats demanded
#   - preferred_market_cap_min/max: size range they hunt in
#   - preferred_thesis_types: their go-to playbooks
#   - campaign_style: aggressive/collaborative/operational/break-up
#   - signature_tactics: notable historical moves (free-form description)
#
# This is the data table the pipeline's activist_dna engine reads to
# match a target company's vulnerability profile to the most likely
# attacker.
import pandas as pd


# Each tuple: (id, name, aum_b_usd, stake_pct, seats, mc_min_b, mc_max_b,
#              thesis_types, style, signature)
ACTIVIST_ARCHETYPES = [
    # --- Tier 1: $5B+ AUM, multi-campaign per year ---
    (
        "ACT_ELLIOTT", "Elliott Investment Management",
        65.0, 3.5, 2, 5.0, 500.0,
        "operational_underperformance,capital_allocation,strategic_review,divestiture",
        "aggressive_multi_track",
        "Files 13D + parallel letter campaign. Often pursues both proxy "
        "and litigation simultaneously. Highest seat-win conversion rate "
        "in the industry. Recent: PYPL, SBUX, CRM, NRG, CTRA.",
    ),
    (
        "ACT_TRIAN", "Trian Fund Management",
        10.0, 4.0, 2, 3.0, 200.0,
        "operational_underperformance,segment_separation,capital_efficiency,governance",
        "collaborative_first_aggressive_second",
        "Peltz prefers private engagement before going public. Long "
        "holding periods (3-5 yr). Operating-partner model. Recent: "
        "DIS (twice), UN, GE, P&G.",
    ),
    (
        "ACT_STARBOARD", "Starboard Value",
        8.0, 5.5, 3, 0.5, 100.0,
        "cost_cuts,governance,capital_allocation,strategic_review",
        "operational_micro_engagement",
        "Detailed 200+ slide white papers. Wins by exposing specific "
        "operational waste. Mid-cap focused but goes larger. Recent: "
        "Salesforce (with Elliott), GoDaddy, Box, Papa John's.",
    ),
    (
        "ACT_VALUEACT", "ValueAct Capital",
        13.0, 5.0, 1, 5.0, 300.0,
        "long_horizon_governance,esg_transition,capital_allocation",
        "constructivist_long_horizon",
        "5-7 year holding periods. Often takes one board seat quietly. "
        "Mason Morfit on the board signals collaborative process. "
        "Recent: SVB pre-2023, Spotify, Salesforce.",
    ),
    (
        "ACT_JANA", "JANA Partners",
        2.5, 5.0, 2, 1.0, 50.0,
        "strategic_review,divestiture,merger_arb,capital_return",
        "catalyst_driven_short_horizon",
        "Looks for break-up value and M&A catalysts. 1-2 year horizons. "
        "Will partner with strategic buyer in some campaigns. Recent: "
        "Treehouse Foods, Macellum, Pinterest.",
    ),
    # --- Tier 2: $1-5B AUM, focused playbook ---
    (
        "ACT_ANCORA", "Ancora Holdings",
        6.0, 3.5, 2, 0.3, 30.0,
        "small_mid_cap_governance,capital_allocation,board_refresh",
        "small_cap_aggressive",
        "Heavy on small/mid-cap, often regional. High frequency of "
        "campaigns. Will run full slates. Recent: Norfolk Southern, "
        "Forrester Research.",
    ),
    (
        "ACT_ENGAGED", "Engaged Capital",
        1.2, 5.0, 2, 0.3, 5.0,
        "small_mid_cap_value,governance,cost_cuts",
        "small_cap_collaborative",
        "Glenn Welling's firm. Mid-cap value with governance angle. "
        "Often settles. Recent: VF Corp, Hain Celestial.",
    ),
    (
        "ACT_ENGINE1", "Engine #1",
        0.4, 0.02, 3, 50.0, 1000.0,
        "esg_transition,climate,governance,energy_transition",
        "esg_thematic_low_stake",
        "Won 3 ExxonMobil board seats with just 0.02% ownership by "
        "winning ISS + the Big Three indexers. The model for "
        "ESG-leveraged activism. Single most-cited campaign of 2021.",
    ),
    (
        "ACT_LEGION", "Legion Partners",
        0.6, 4.5, 2, 0.2, 5.0,
        "small_mid_cap_value,strategic_review,cost_cuts",
        "small_cap_operational",
        "Christopher Kiper's firm. Detailed campaign books, often "
        "with operating partners. Recent: Genesco, Bed Bath & Beyond.",
    ),
    (
        "ACT_CARRONADE", "Carronade Capital",
        0.5, 3.0, 1, 0.1, 3.0,
        "credit_arb_distressed,bondholder_activism,restructuring",
        "credit_focused",
        "Distressed/credit activism, often on equity side post-restructuring. "
        "Small set of campaigns, high concentration.",
    ),
    # --- Tier 3: $0.5-1B AUM, specialist ---
    (
        "ACT_PRAESIDIUM", "Praesidium Investment Management",
        0.8, 6.0, 1, 0.2, 5.0,
        "small_cap_value,governance,capital_return",
        "small_cap_value",
        "Small-cap value with constructive style. Long holding periods. "
        "Often gets one board seat quietly.",
    ),
    (
        "ACT_BARINGTON", "Barington Capital",
        0.3, 3.5, 2, 0.1, 5.0,
        "small_cap_value,cost_cuts,strategic_review,divestiture",
        "small_cap_aggressive",
        "Jim Mitarotonda's firm. Long history (founded 2000), "
        "small-cap focused. Recent: Mattel, Children's Place.",
    ),
    (
        "ACT_LANDDOWN", "Land & Buildings",
        0.5, 4.0, 1, 0.5, 20.0,
        "real_estate_underperformance,reit_strategy,sale_leaseback",
        "real_estate_specialist",
        "Litt firm specializing in real-estate-heavy companies. "
        "Recent: Brookdale Senior Living, Six Flags.",
    ),
    (
        "ACT_BLUEBELL", "Bluebell Capital Partners",
        0.1, 1.0, 1, 10.0, 200.0,
        "esg_governance,european_large_cap,board_refresh",
        "europe_esg_low_stake",
        "European Engine #1 analog. Tiny stakes, governance-only. "
        "Notably: Danone (2021 CEO ouster).",
    ),
    (
        "ACT_INCLUSIVE", "Inclusive Capital",
        2.0, 4.0, 1, 2.0, 100.0,
        "esg_transition,climate,governance",
        "esg_collaborative",
        "Jeff Ubben spin-off from ValueAct. ESG-themed long-horizon. "
        "Recent: Exxon (with Engine #1), Bayer.",
    ),
    # --- Generic archetypes for unmatched profiles ---
    (
        "ACT_GENERIC_LARGECAP", "Generic Large-Cap Activist",
        5.0, 3.0, 2, 5.0, 500.0,
        "operational_underperformance,capital_allocation,strategic_review",
        "moderate_multi_track",
        "Composite archetype representing the median large-cap "
        "activist when no specific fund is a strong match. Used by "
        "the matcher when no real archetype scores >70.",
    ),
    (
        "ACT_GENERIC_SMALLCAP", "Generic Small-Cap Activist",
        0.5, 5.0, 2, 0.1, 5.0,
        "small_mid_cap_value,governance,cost_cuts",
        "small_cap_aggressive",
        "Composite archetype for sub-$5B targets when no specific "
        "small-cap fund matches.",
    ),
    (
        "ACT_GENERIC_ESG", "Generic ESG Activist",
        0.3, 0.5, 2, 1.0, 500.0,
        "esg_transition,climate,governance",
        "esg_thematic",
        "Composite archetype for ESG-themed campaigns when no "
        "specific ESG fund matches.",
    ),
]


def build_archetypes_df():
    """Return the activist archetypes DataFrame matching the schema the
    pipeline expects (aegis/scoring/activist_dna.py)."""
    rows = []
    for (aid, name, aum_b, stake, seats, mc_min_b, mc_max_b,
         theses, style, signature) in ACTIVIST_ARCHETYPES:
        rows.append({
            "archetype_id": aid,
            "name": name,
            "aum_usd": aum_b * 1e9,
            "typical_stake_pct": stake,
            "typical_seats_requested": seats,
            "preferred_market_cap_min": mc_min_b * 1e9,
            "preferred_market_cap_max": mc_max_b * 1e9,
            "preferred_thesis_types": theses,
            "campaign_style": style,
            "signature_tactics": signature,
        })
    return pd.DataFrame(rows)


def write_archetypes_csv(output_path):
    """Write the archetypes table as a CSV at the given path."""
    df = build_archetypes_df()
    df.to_csv(output_path, index=False)
    return df


def find_archetype(archetype_id):
    """Look up one archetype by ID."""
    df = build_archetypes_df()
    matches = df[df["archetype_id"] == archetype_id]
    return matches.iloc[0].to_dict() if len(matches) else None
