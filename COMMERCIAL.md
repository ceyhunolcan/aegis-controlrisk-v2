# Commercial licensing

Aegis ControlRisk OS is **source-available but not free to use in
production**. The source code is published on GitHub so prospective
customers, partners, and contributors can evaluate the technology, but
running it in any commercial, internal-tooling, or revenue-generating
context requires a paid license.

If that's you, read on.

---

## Who needs a license

You need a commercial license if you want to:

- **Run Aegis internally** at a hedge fund, investment bank, law firm,
  PR firm, corporate IR team, board advisory, proxy solicitor, or any
  organization that uses the outputs in its business
- **Embed Aegis** in a product or service you sell to clients
- **Offer Aegis as a hosted service** (SaaS, API, dashboard portal)
- **Use Aegis as part of a consulting engagement** (delivering memos,
  reports, or recommendations to a client)
- **Train derivative models** on Aegis outputs, methodology, or scoring
  weights
- **Run Aegis against real data** about identifiable companies, even
  for an internal pilot

You do *not* need a commercial license to:

- Read the code on GitHub
- Fork the repo for evaluation
- Use the synthetic dataset for academic research or classroom teaching
  (see "Research and Education Exception" in `LICENSE`)
- Submit issues or pull requests

---

## What you get with a commercial license

The base offering includes:

- Right to use Aegis ControlRisk OS in your licensed scope
- Access to updates and bug fixes for the term of the license
- Email support with defined response times (SLA varies by tier)
- The right to integrate with your own data sources (EDGAR, Bloomberg,
  ISS, etc. — you bring your own data subscriptions)

Optional add-ons:

- Custom scoring weight calibration against your historical campaign
  database
- Real-data ingest implementation (EDGAR / Bloomberg / FactSet / ISS)
- White-label / co-brand for client-facing deliverables
- On-prem deployment vs. private cloud vs. shared SaaS
- Custom scoring engines, new theses, or new archetypes for your sector
- Direct integration with your CRM, calendar, or alerting infrastructure
- Implementation services and analyst training

---

## Pricing model (indicative)

Pricing depends on use case, deployment model, number of seats, and
data scope. The four common tiers:

| Tier | Use case | Indicative range |
|---|---|---|
| **Evaluation** | 30-day pilot, capped at ≤10 companies, synthetic-data only | No charge |
| **Single-team** | Internal tool, one team, up to N seats, your data | Annual fee |
| **Enterprise** | Multi-team, multi-region, SLA, custom calibration | Annual + per-seat |
| **OEM / White-label** | Embed in your product or client deliverable | Per-engagement or revenue-share |

Numbers omitted on purpose — pricing happens in conversation. The
first call is free and covers what you'd actually pay.

---

## How to get a license

Email: **[YOUR-EMAIL@DOMAIN.com]**
Subject: `Aegis license inquiry — [your org]`

Include:

1. Your organization and role
2. Intended use case (internal tool, embedded, SaaS resale, consulting)
3. Approximate number of users / clients / companies covered
4. Timeline (evaluating / piloting / deploying)
5. Data sources you'd want to integrate

Response within two business days. Initial call is 30 minutes and
covers scope, pricing, and what the path to a signed agreement looks
like.

---

## What about open-source alternatives?

There aren't any with the same scope. If there were, this wouldn't be
a viable business. Specific projects in adjacent space:

- **OpenCorporates** — corporate registry data, not activism analytics
- **Shareholder Commons** — advocacy, not modeling
- **ISS Voting Analytics** — proprietary, the dataset you'd license
  separately if you want to power Aegis with real holder data

Aegis fills a gap that doesn't have an open-source equivalent. That's
why this is licensed the way it is.

---

## FAQ

**Can I read the code?**
Yes. The whole repository is public. Read, learn, evaluate.

**Can I fork it?**
For evaluation, yes. To run it commercially or distribute it, no.

**Can I copy the methodology into my own product?**
No. The scoring engines, weights, claim graph design, MC formulation,
and overall pipeline architecture are proprietary IP and protected
under the LICENSE.

**Can I submit a pull request?**
Yes, and we welcome contributions. Submitting a PR grants the
copyright holder a license to incorporate it (see `LICENSE` clause 1).

**Are you open to revenue sharing for a strategic partner?**
Yes. Talk to us.

**What happens if my license lapses?**
You must stop using the Software and destroy any copies. Re-licensing
is straightforward as long as the lapse wasn't due to breach.

**Can a competitor read this and just build their own version?**
They can read it. Reimplementing it well takes months and the
methodology details (weights, claim ordering, MC tuning) are not
trivially copyable. The legal protection is real but not the only
moat — speed of execution and the data integrations matter more.

---

## Compliance reminder

Aegis is a model, not legal advice. Every licensed deployment carries
the `COMPLIANCE_NOTE` from `config.py` through into board memos and
war-room outputs, and that note must not be removed. Your license
includes the obligation to make this clear to end users of any
derivative deliverable.
