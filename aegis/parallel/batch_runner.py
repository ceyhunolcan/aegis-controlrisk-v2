# Parallel pipeline execution. Single-company analysis is ~150ms in the
# MVP, dominated by the two Monte Carlo passes (10K simulations each).
# That's tolerable on demand. For batch (overnight) jobs across hundreds
# of companies, we want concurrency.
#
# We use ThreadPoolExecutor by default because the pipeline does enough
# pandas/numpy work that the GIL gets released frequently. For pure-Python
# bottlenecks ProcessPoolExecutor would be better; the runner accepts
# either via the executor= kwarg.
from concurrent.futures import ThreadPoolExecutor, ProcessPoolExecutor, as_completed
import time

from .. import pipeline


def _wrap_one(company_id, data, as_of_date):
    """Wrapper that catches exceptions so one bad company doesn't kill the batch."""
    t0 = time.time()
    try:
        result = pipeline.run_company_analysis(company_id, data, as_of_date)
        result["_runtime_sec"] = round(time.time() - t0, 3)
        return company_id, result, None
    except Exception as e:
        return company_id, None, f"{type(e).__name__}: {e}"


def run_batch(company_ids, data, as_of_date=None, max_workers=4,
              executor="thread", progress_callback=None):
    """
    Run the pipeline for many companies concurrently.

    Returns dict: company_id -> {result: ..., error: ..., runtime_sec: ...}

    progress_callback (optional): callable invoked as
    progress_callback(completed, total, company_id) after each company.
    """
    if not company_ids:
        return {}

    Pool = ProcessPoolExecutor if executor == "process" else ThreadPoolExecutor

    results = {}
    total = len(company_ids)
    completed = 0

    with Pool(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_wrap_one, cid, data, as_of_date): cid
            for cid in company_ids
        }
        for future in as_completed(futures):
            cid, result, err = future.result()
            results[cid] = {
                "result": result,
                "error": err,
                "runtime_sec": (result or {}).get("_runtime_sec"),
            }
            completed += 1
            if progress_callback:
                try:
                    progress_callback(completed, total, cid)
                except Exception:
                    pass

    return results


def run_universe(data, as_of_date=None, max_workers=4):
    """
    Convenience: run every company in the loaded dataset.
    """
    companies_df = data.get("companies")
    if companies_df is None or len(companies_df) == 0:
        return {}
    ids = companies_df["company_id"].astype(str).tolist()
    return run_batch(ids, data, as_of_date=as_of_date, max_workers=max_workers)


def summarize_batch(batch_results):
    """Quick stats summary of a batch run."""
    n_total = len(batch_results)
    n_ok = sum(1 for v in batch_results.values() if v["result"] is not None)
    n_err = n_total - n_ok
    runtimes = [v["runtime_sec"] for v in batch_results.values()
                if v.get("runtime_sec") is not None]
    return {
        "n_total": n_total,
        "n_ok": n_ok,
        "n_error": n_err,
        "errors": {cid: v["error"] for cid, v in batch_results.items()
                   if v["error"]},
        "runtime_total_sec": round(sum(runtimes), 2) if runtimes else 0,
        "runtime_mean_sec": round(sum(runtimes) / len(runtimes), 3)
                            if runtimes else 0,
        "runtime_max_sec": round(max(runtimes), 3) if runtimes else 0,
    }
