# Pluggable data ingest layer.
#
# The current pipeline loads CSVs from disk via aegis.data.loader. The
# whole point of this module is to give real deployments a way to plug
# in EDGAR / Bloomberg / Capital IQ / ISS without rewriting the pipeline.
#
# A source is just a class that exposes load_companies / load_financials /
# load_directors / etc. and returns the same DataFrame shape the synthetic
# generator produces.
#
# When you implement a real source, register it in SOURCES below.
from ..data.loader import load_all_data


class SyntheticSource:
    """Default source - reads the synthetic CSVs shipped in /data."""

    name = "synthetic"

    def load_all(self, data_dir="data"):
        return load_all_data(data_dir)


class EDGARSource:
    """SEC EDGAR. STUB - implement when real data lands."""

    name = "edgar"

    def load_all(self, data_dir=None):
        # TODO: pull 13D/13G filings, DEF 14A proxy statements, 8-Ks
        # See https://www.sec.gov/edgar/sec-api-documentation
        raise NotImplementedError(
            "EDGAR ingest not yet implemented. See docs/ingest.md for the "
            "expected DataFrame schema each loader must return."
        )


class BloombergSource:
    """Bloomberg fundamentals + ownership. STUB."""

    name = "bloomberg"

    def load_all(self, data_dir=None):
        # TODO: Bloomberg Server API for fundamentals + EQS for ownership
        raise NotImplementedError(
            "Bloomberg ingest not yet implemented. Requires a BLPAPI session."
        )


class ISSSource:
    """ISS Voting Analytics + Governance QualityScore. STUB."""

    name = "iss"

    def load_all(self, data_dir=None):
        # TODO: ISS Data Services REST API
        raise NotImplementedError(
            "ISS ingest not yet implemented. Requires an ISS DataDesk license."
        )


# Source registry. To add a real source, write a class with .load_all()
# returning the same dict of DataFrames the synthetic generator produces.
SOURCES = {
    "synthetic": SyntheticSource,
    "edgar": EDGARSource,
    "bloomberg": BloombergSource,
    "iss": ISSSource,
}


def get_source(name="synthetic"):
    if name not in SOURCES:
        raise ValueError(
            f"unknown source: {name!r}. Available: {list(SOURCES)}"
        )
    return SOURCES[name]()


def merge_sources(sources_list, data_dir="data"):
    """
    Load from multiple sources and merge. Right-most source wins on
    conflicts. Useful when you want EDGAR for filings + Bloomberg for
    fundamentals + ISS for governance scores.
    """
    if not sources_list:
        return get_source("synthetic").load_all(data_dir)

    merged = {}
    for name in sources_list:
        try:
            partial = get_source(name).load_all(data_dir)
        except NotImplementedError as e:
            # Skip unimplemented sources rather than crashing the batch
            print(f"  [ingest] skipping {name}: {e}")
            continue
        for key, df in partial.items():
            merged[key] = df  # right-most wins
    return merged
