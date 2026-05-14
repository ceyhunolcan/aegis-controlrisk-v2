# Small ranking / calibration metrics. No sklearn dep so we can ship the
# backtest in environments without scientific Python set up.


def precision_at_k(ranked_ids, truth_ids, k):
    if k <= 0:
        return 0.0
    truth = set(truth_ids)
    top = list(ranked_ids)[:k]
    if not top:
        return 0.0
    return sum(1 for x in top if x in truth) / float(k)


def recall_at_k(ranked_ids, truth_ids, k):
    if not truth_ids:
        return 0.0
    truth = set(truth_ids)
    top = set(list(ranked_ids)[:k])
    return sum(1 for x in truth if x in top) / float(len(truth))


def recall_at_threshold(ranked_ids, scores, truth_ids, threshold):
    """Recall over the subset of items whose score >= threshold."""
    if not truth_ids:
        return 0.0
    truth = set(truth_ids)
    picked = [r for r, s in zip(ranked_ids, scores)
              if s is not None and float(s) >= float(threshold)]
    return sum(1 for x in truth if x in picked) / float(len(truth))


def average_rank_of_truth(ranked_ids, truth_ids):
    """Mean rank of each truth item (1-indexed). Missing items get end+1."""
    if not truth_ids:
        return 0.0
    n = len(ranked_ids)
    ranks = []
    for t in truth_ids:
        try:
            ranks.append(ranked_ids.index(t) + 1)
        except ValueError:
            ranks.append(n + 1)
    return sum(ranks) / float(len(ranks))


def simple_auc_proxy(scores, labels):
    """
    AUC via the Mann-Whitney probability: P(score_pos > score_neg) across all
    (pos, neg) pairs, ties counted as 0.5. With no pairs we return 0.5.
    """
    pos = [s for s, l in zip(scores, labels) if l == 1]
    neg = [s for s, l in zip(scores, labels) if l == 0]
    if not pos or not neg:
        return 0.5
    wins = 0.0
    for p in pos:
        for n in neg:
            if p > n:
                wins += 1.0
            elif p == n:
                wins += 0.5
    return wins / (len(pos) * len(neg))


def calibration_bins(probabilities, outcomes, n_bins=5):
    """Bucket predictions into bins, return mean predicted vs mean actual per bin."""
    if not probabilities or len(probabilities) != len(outcomes):
        return []
    width = 1.0 / float(n_bins)
    bins = []
    for i in range(n_bins):
        lo, hi = i * width, (i + 1) * width
        # last bin is inclusive on the upper end
        idxs = [j for j, p in enumerate(probabilities)
                if p >= lo and (p < hi or i == n_bins - 1)]
        if not idxs:
            bins.append({"bin_low": round(lo, 2), "bin_high": round(hi, 2),
                         "n": 0, "mean_predicted": None, "mean_actual": None})
            continue
        mp = sum(probabilities[j] for j in idxs) / len(idxs)
        ma = sum(outcomes[j]      for j in idxs) / len(idxs)
        bins.append({
            "bin_low": round(lo, 2),
            "bin_high": round(hi, 2),
            "n": len(idxs),
            "mean_predicted": round(mp, 3),
            "mean_actual": round(ma, 3),
        })
    return bins
