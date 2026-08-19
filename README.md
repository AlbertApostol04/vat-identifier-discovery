# UK VAT Identifier Discovery

**Can a dataset of UK company VAT numbers be built from public web sources, and at what cost?**

Partially, and the interesting part is where it fails. On a random sample of 150 active UK companies I confirmed a correctly-attributed VAT number for 2 of them — 1.3%. That number is small, and it is the honest one. A pipeline that skipped the attribution check would have reported a much larger number, and most of it would have been wrong.

The binding constraint is not crawling. It is that most UK companies have no findable website at all, and that HMRC's bulk verification API is no longer publicly accessible.

| | count | share of 150 | 95% CI (Wilson) |
|---|---|---|---|
| domain found **and proved** | 30 | 20.0% | 14.4 – 27.1% |
| VAT candidate extracted | 3 | 2.0% | 0.7 – 5.7% |
| **confirmed, correctly attributed** | **2** | **1.3%** | 0.4 – 4.7% |
| valid, but registered to a different company | 1 | — | — |
| nothing found | 147 | 98.0% | — |

The 147 are not all failures. About 36% of the sample had no candidate domain that resolves at all, and roughly two thirds of the UK register consists of dormant, micro-entity or never-filed companies that sit below the £90,000 VAT registration threshold. Separating "not registered" from "I failed" is the central measurement problem here, and section 2.7 says how far I got with it.

---

# Part 1 — Research

## 1.1 The shape of the problem

The verifier only runs backwards. HMRC will answer *"is this number valid, and whose is it?"* It will never answer *"what is company X's number?"* That is a deliberate design choice, not an oversight — the second question amounts to publishing a directory of taxpayers.

This turns the task into generate-and-test. Candidates must be produced from somewhere else and then tested, which means candidate *generation* — not verification — is where the design effort goes. The whole pipeline below is a funnel of progressively more expensive filters, cheapest first: a local checksum before any network call, a DNS lookup before any HTTP request.

The second half of the insight is what makes the project possible at all. HMRC's checker does not return a boolean. It returns the **registered business name and address**:

```
630968620  →  Valid UK VAT number
              CERTIKIN INTERNATIONAL LTD
              4 TUNGSTEN PARK, COLLETTS WAY, WITNEY, OX29 0AX, GB
```

That is an attribution oracle, not just a validity oracle. Comparing what HMRC returns against what Companies House holds is the only mechanism available for answering the question that actually matters: *is this number the right company's?* Without it, section 2.4 could not exist.

Evidence: [`evidence/hmrc_web_checker.png`](evidence/hmrc_web_checker.png)

## 1.2 HMRC's bulk API is closed

The brief lists the HMRC checker as *"also available as an API for bulk checks."* That appears to be out of date. Probed on 2026-08-16:

```
GET https://api.service.hmrc.gov.uk/organisations/vat/check-vat-number/lookup/123456782

no version header               → 404  MATCHING_RESOURCE_NOT_FOUND
Accept: ...vnd.hmrc.1.0+json    → 404  MATCHING_RESOURCE_NOT_FOUND
Accept: ...vnd.hmrc.2.0+json    → 401  MISSING_CREDENTIALS
                                       "Authentication information is not provided"
```

Raw responses with timestamps: [`evidence/hmrc_api_probe.txt`](evidence/hmrc_api_probe.txt)

The three probes are deliberately redundant. A 404 with no version header could mean either "v1 was withdrawn" or "the version header is now mandatory" — those are different claims and the first probe alone cannot distinguish them. Requesting v1 *explicitly* by version still returns 404, which settles it: the route is gone. v2 exists but rejects the request before routing, with `MISSING_CREDENTIALS`. There is no unauthenticated path.

Access requires registration on the HMRC Developer Hub, an API subscription and OAuth credentials — a process reported to take around two weeks, which does not fit inside this exercise.

**Two consequences.** For this proof of concept, verification moved to the public web checker, done by hand (section 2.6). For Part 3, this relocates the bottleneck entirely: at scale the constraint is verification throughput, not crawl capacity, and negotiated API access is the first thing I would secure before promising a customer delivery.

## 1.3 The step nobody mentions: Companies House has no website field

The bulk company data product has 55 columns. None of them is a website.

Every source in the brief that involves reading a company's own web pages therefore depends on an unstated prior step: mapping company name → domain. That step turned out to be harder than the extraction it feeds, and it is where most of the loss in this pipeline occurs. It is the real bottleneck, and it is measured in section 2.3.

⚠️ The `URI` column is not a website. It holds a linked-data identifier of the form `http://business.data.gov.uk/id/company/{number}` — the same value for every company with the number substituted. It is easy to mistake for a lead and it is not one.

## 1.4 What the register actually contains

Source: `BasicCompanyDataAsOneFile-2026-08-01`, 1.92 GB uncompressed, 55 columns.

| | count | share |
|---|---|---|
| rows in file | 3,893,238 | |
| `CompanyStatus == "Active"` | 3,547,675 | 91.1% |
| dormant, micro-entity, or no accounts filed | 2,697,493 | 69.3% |
| FULL / MEDIUM / GROUP / audited accounts | 83,713 | 2.2% |

Two things follow.

First, "live companies" does not mean "active companies" — 345,563 rows (8.9%) are in liquidation, administration or dissolution. I had assumed the product name meant what it says.

Second, and more important for interpreting any coverage figure: the UK VAT registration threshold is £90,000 of turnover, and roughly seven in ten companies on this register are dormant, micro-entities, or have never filed accounts. Most of them cannot plausibly be VAT-registered. Reporting a discovery rate against "all UK companies" therefore measures the composition of the register more than it measures the pipeline. Section 2.1 describes the sampling design I used to get around this.

### Postcode is not the discriminator it looks like

Before measuring it, I planned to use postcode as the primary address signal in the attribution check, on the assumption that it is more selective than a company name. That was wrong.

The 20 most common postcodes account for **276,795 companies — 7.1% of the entire register**. The single most common is shared by **59,168 companies**. These are formation agents and virtual office providers.

Within the sample itself, the distribution of *how many companies share each company's postcode*:

```
min 1  |  25% = 3  |  median 9  |  75% = 150  |  max 59,168  |  mean 2,393
```

The mean is 266× the median. For a company registered at a formation agent's address, "the postcode matches" narrows the field to one in tens of thousands and proves nothing.

I did not drop the signal; I gated it. Postcode contributes to the attribution score only when fewer than 20 companies share it — a threshold taken from the measured distribution above, not chosen by feel. For roughly half the sample the postcode is genuinely identifying; for a quarter it is useless.

Frequency table: `data/postcode_frequency.csv`, generated by `00_explore.py`.

## 1.5 Sources evaluated

| source | verdict | reason |
|---|---|---|
| HMRC bulk API | **closed** | 401 / 404, evidence above |
| HMRC web checker | **used** | no login; returns registered name and address |
| Companies House bulk data | **used** | defines the population; no websites |
| Common Crawl | **rejected, no code written** | see below |
| commercial search API | **rejected, no budget** | ~$5 / 1000 queries → ~$18,000 for 3.5M companies |
| domain guessing + proof of ownership | **used** | zero cost, no rate limits; measured in 2.3 |

**Common Crawl.** The brief's mention of bulk web corpora suggests that crawling site-by-site may be the wrong shape, and I think that is right — but not at the step where it matters. The Common Crawl index is organised by domain and URL, not by company name. There is no direct name → domain path through it; getting one would require full-text search across petabytes, which exceeds a laptop and would cost more than the commercial search API it was meant to replace. Common Crawl would be genuinely useful at step 3, where I already hold the domains and could pull pages from the corpus instead of fetching them. It does not help at step 2, which is the actual bottleneck. I spent research time on it and no implementation time, deliberately.

**What I did not test, and would test first with another day.** Three lines of enquiry were deprioritised for time rather than rejected on merit:

1. **EORI numbers.** A GB EORI number is the VAT number with a `GB` prefix and `000` suffix — a deterministic relationship between two identifiers. Anywhere EORI numbers are published (customs documentation, shipping paperwork, freight forwarders' pages), VAT numbers follow for free with no attribution ambiguity. This is the one I would do next, because it is the only candidate that avoids the discovery problem entirely rather than working around it.
2. **Marketplace seller pages.** UK marketplaces are required to display a seller's VAT number. That is legally compelled disclosure alongside a business name and address in a structured layout — high precision, narrow scope.
3. **Public sector spend data and The Gazette.** Sparse, but biased differently from websites, which matters when the website route caps out at 20%.

That taxonomy — *why is the number on this page at all?* — predicted source quality better than any technical property. Legally compelled disclosure beats voluntary publication beats transactional by-product; and a derived identifier beats all three, because there is nothing to discover.

---

# Part 2 — Proof of concept

## 2.1 Sample design

The brief warns that a sample of companies already known to publish their VAT number produces an impressive number and teaches nobody anything. Everything here is drawn at random from the full register, with a fixed seed, before anything was known about any of them.

- **`all`** — 75 drawn at random from 3,547,675 active companies
- **`trading`** — 75 drawn at random from 2,240,953 active companies, excluding `DORMANT` and `NO ACCOUNTS FILED`
- seed 42; overlap between the two strata: 0 companies (expected value for two draws of 75 from 3.5M is 0.0016, so zero is the ordinary outcome, not a check that passed)

Two strata rather than one because 69.3% of the register cannot plausibly be VAT-registered. A single uniform sample would be dominated by companies for which "not found" is the correct answer, and the resulting rate would be uninterpretable. Reporting both rates makes the difference between them informative in itself.

**A prediction recorded before the run.** The two pools overlap heavily — `trading` is 63.2% of `all` — so I expected the rates to come out close. I wrote down what that would mean if it happened: that the limiting factor is website availability rather than VAT registration status, and that filtering the population would therefore not help.

**Result:**

| stratum | domains proved | rate | 95% CI |
|---|---|---|---|
| `all` | 13 / 75 | 17.3% | 10.4 – 27.4% |
| `trading` | 17 / 75 | 22.7% | 14.7 – 33.3% |

Difference +5.3pp, standard error 6.5pp, z = 0.82 — not distinguishable from zero.

The prediction held. Excluding dormant and never-filed companies — 37% of the register — does not significantly improve the discovery rate. The constraint is not who is registered for VAT. It is who has a website that can be found. No amount of crawl budget changes that.

Sample: `data/sample.csv`. Reproducible by running `01_build_sample.py`.

## 2.2 The pipeline

```
00_explore.py        register statistics; writes the postcode frequency table
01_build_sample.py   150 companies, two strata, seed 42
02_find_websites.py  company name → domain, proved by Companies House number
03_extract_vat.py    up to 8 pages per domain → VAT candidates with context
04_verify.py         deduplicate; HMRC checked by hand
05_score.py          attribution scoring → CONFIRMED / MISMATCH / INVALID / NOT_FOUND
```

Each step reads a CSV and writes a CSV. Every intermediate file is in `data/`, so any number in this document can be traced back to the rows that produced it.

**Cheap filters first, everywhere.** The checksum runs locally before any request reaches HMRC; on 100,000 consecutive 9-digit numbers, 2,066 pass — it discards 97.9% of arbitrary candidates for free. A DNS lookup (~20ms) runs before any HTTP request (1–3s). The same principle appears at every stage, and it is what makes a 150-company run finish in minutes rather than hours.

**Two checksum algorithms, not one.** UK VAT numbers use mod-97 for older registrations and mod-9755 (add 55 before the modulo) for numbers issued from around 2010. Most sources present only the first as "the UK VAT checksum". Implementing both costs three lines; implementing one costs coverage you never see, because rejected numbers leave no trace.

This stopped being theoretical on the first real number I tested. `406782879`, confirmed by HMRC as belonging to Uber London Limited:

```
weighted sum of first 7 digits : 157
+ check digits                  :  79
= total                         : 236

236 % 97        = 42   → FAILS mod-97
(236 + 55) % 97 =  0   → passes mod-9755
```

A real, valid, HMRC-confirmed number fails the algorithm most sources describe as the standard one.

## 2.3 The funnel

The measurement, rather than the hit count, is the deliverable here.

| stage | count | share of 150 |
|---|---|---|
| no candidate domain resolves | 54 | 36.0% |
| domain resolves and serves a page, but it is not this company's | 52 | 34.7% |
| resolves but serves nothing | 14 | 9.3% |
| **domain proved** | **30** | **20.0%** |
| at least one VAT candidate found | 3 | 2.0% |
| confirmed | 2 | 1.3% |

Runtime: 8.6 min for step 2 (3.44 s/company), 17.3 min for step 3 (35 s/domain).

**The largest single loss is at the top.** 36% of companies have no guessable domain that exists at all. For those, the problem is not that extraction failed — there is nothing to crawl. Crawl budget cannot move that number; only a different class of source can.

### Domain-level false positives: 63.4%

82 pages were actually fetched and read. Only 30 of them belonged to the company being looked for.

Domain ownership was proved by searching the page for the company's Companies House registration number — which UK companies are required to display on their websites under the Companies Act 2006, and which is the exact primary key from the register. Where that failed, a normalised company-name match was accepted and recorded separately as the weaker signal (25 of the 30 confirmations were name-only).

Without that proof step, the natural thing to report is *"82 domains found — 55% coverage"*. Nearly two thirds of it would have been wrong: squatted domains, parked pages, unrelated companies with similar names. A large false number instead of a small correct one.

This is the same failure mode as the VAT-level false positive in the next section, one stage earlier in the pipeline. **Any coverage figure published without an attribution check should be read as an upper bound on nothing in particular.**

Full funnel per company: `data/websites.csv`.

## 2.4 The false positive that got caught

One of the three candidates was valid, confirmed by HMRC, and belonged to a different company.

```
company in sample   : HIGH LEVEL LIMITED            (Companies House 11147020)
domain proved       : highlevel.co.uk               (by company name only)
VAT number found    : 413473374
checksum            : passes
HMRC                : Valid UK VAT number
HMRC registered to  : HIGH LEVEL PHOTOGRAPHY LTD
name similarity     : 0.625  →  MISMATCH
```

Nothing about this looks wrong. `highlevel.co.uk` is exactly the domain one would expect a company called HIGH LEVEL LIMITED to own. The number is well-formed, passes both checksum variants, is displayed in the site's own footer, and HMRC confirms it as valid. Every check short of attribution says yes.

Had the pipeline stopped at *"is the number valid?"* — which is what a verifier is normally used for — this record would have shipped, and it would have looked indistinguishable from the two correct ones. The customer has no way to detect it: there is no missing field, no malformed value, no error to log. It is only visible by asking HMRC *whose* number it is and finding that the answer names someone else.

This is precisely the failure the brief describes: a plausible number attached to the wrong company is invisible, and it corrupts every join made downstream. On a sample of three candidates, one of them was exactly that.

### A confidence signal that predicted all three outcomes

Step 3 searched every fetched page for the company's Companies House number as well as for VAT numbers — no extra requests, since the pages were already downloaded. That flag turned out to line up perfectly with the verification result:

| company | Companies House number on site | outcome |
|---|---|---|
| Certikin International | yes | CONFIRMED |
| Enviro Clean Group | yes | CONFIRMED |
| High Level | **no** | **MISMATCH** |

The reason is visible in the extracted context. On the two correct records, the two identifiers sit side by side in the same footer line:

```
Company number: 03047290 | VAT registration number: GB630 968 620
Company number: 11498172 | VAT number: 339 2179 84 ... © 2025 Enviro Clean Group LTD
```

A company publishing both of its identifiers together is the strongest attribution evidence available on a web page. On the third, there was no company number anywhere on the site — and the VAT number was immediately followed by a web agency's credit line:

```
...Registration Number GB 413 4733 74 Website by Melt Design
```

Three observations is an observation, not a rule. But *"require the Companies House number on the same site before emitting a VAT number"* is a cheap production filter with a plausible mechanism behind it, and it is the first thing I would test on a larger sample.

Extracted candidates with surrounding context: `data/candidates.csv`.

## 2.5 A threshold that was validated by accident

Enviro Clean Group returned a **different postcode** from HMRC (`DA9 9UZ`) than the one Companies House holds (`CM15 9SG`). It was accepted anyway, on a name similarity of 1.000.

That is correct behaviour, and I did not design it deliberately. The VAT registration address is not the registered office; they are two registers maintained independently by two agencies, and they drift. Had the rule required name **and** postcode to agree, a correct match would have been rejected — a miss rather than a false positive, but an error either way.

The rule as written (name ≥ 0.85 accepts on its own; 0.65–0.85 accepts only with a *discriminating* postcode) survived a case it was not built for. The general lesson is that combining independent signals with AND assumes they fail independently, and here they do not: both are derived from registers that disagree with each other by design.

## 2.6 Verification method, and the false positive rate

HMRC's API being closed, the three deduplicated candidates were checked by hand at the public web checker — about twenty minutes of work, versus an estimated 60–90 minutes to automate a government form with session and CSRF handling.

The choice was not only about time. **Neither approach scales.** Two million automated requests against a public form is not a technical solution, it is abuse: it would be blocked within hours and would expose the company to reputational and legal risk. Automating the form would have demonstrated nothing about the production system. The finding worth reporting is that authorised API access is the only route that scales, and section 3.2 treats it as the primary bottleneck.

**Measured false positives: 1 of 3 decided candidates.**

I will not write that as 33%. A percentage implies a precision that three observations cannot support; the 95% interval on 1/3 spans most of the possible range. What can be said is that a false positive appeared in the first three candidates ever examined, which is enough to establish that the failure mode is common rather than theoretical, and not nearly enough to estimate its rate. Roughly 400–500 verified candidates would be needed to bound it within a few points — which, at a 2% extraction rate, means a sample of about 20,000 companies.

## 2.7 What these numbers do not capture

**Whether the 147 NOT_FOUND are unregistered or missed.** This is the most important gap. The evidence points mostly at "unregistered or no web presence": 36% had no resolving domain, and about 69% of the register sits below the VAT threshold by size. But I cannot separate the two categories on this data, and the honest position is that 1.3% is a floor on coverage, not an estimate of it.

**The real false positive rate**, for the reasons in 2.6.

**Cases the sample never contained.** Group structures where the VAT number belongs to a parent; franchises sharing a registration; companies publishing their VAT number only inside a PDF or an image; sites rendered entirely in JavaScript, which `requests` cannot see. Each is a known failure class that this run simply did not encounter, and each would need its own handling.

**Path-guessing for sub-pages did not work, and I could not test the hypothesis behind it.** Step 3 requested 8 conventional paths per domain (`/contact`, `/about`, `/terms`, …) and only 82 of 240 returned anything — 34%. Real sites do not name their pages the way I guessed. The correct design is to fetch the homepage, extract its links, and follow the ones whose text or href contains "contact", "about" or "terms". That is a design change, not a parameter change, and it is the second thing I would fix.

---

# Part 3 — With real resources

## 3.1 Cost, extrapolated from measurement

Everything below scales a measured figure rather than an assumed one: 3.44 seconds per company for domain discovery, single-threaded, on one laptop.

| | |
|---|---|
| 3,547,675 active companies, sequential | 141 days |
| with 200 parallel workers | ~0.7 days |
| DNS queries required (6 candidates each) | 21,286,050 |
| homepage traffic alone | ~846 GB |
| commercial search API instead of guessing | ~$18,000 |
| manual annotation for quality measurement (5,000 samples) | ~$2,000 |

Compute and bandwidth are minor at this scale — a few hundred dollars of cloud time and egress. The dominant costs are the search API, if used, and human annotation. Order of magnitude: **$0.005 – $0.01 per company** for a single full pass, excluding verification, which is not purchasable at any price without API access.

## 3.2 What breaks first

**1. DNS, not crawling.** 21 million lookups. No public resolver — Google, Cloudflare, an ISP's — tolerates that volume from one source; it is rate-limited or blocked within hours. Production requires a self-hosted recursive resolver with aggressive caching, sized for the query rate. This is an infrastructure requirement that "use a distributed crawler" does not cover, and it is invisible until you count the queries.

**2. Verification.** With HMRC's open API withdrawn, there is no compliant path to verifying millions of numbers. Manual checking does not scale; scraping the public form at that volume is abuse. Everything downstream of extraction is gated on negotiated API access, which is why I would treat that conversation as a precondition for committing to a customer, not an implementation detail.

**3. The 36% with no resolvable domain.** A ceiling that budget does not move. Past it, the website route is exhausted and coverage only grows by adding a different *class* of source — legally compelled disclosures (marketplace seller pages), transactional by-products (public spend, customs data), or derived identifiers (EORI). This is the argument for spending the next unit of effort on source diversity rather than on crawl depth.

## 3.3 What I would monitor

Without ground truth, correctness has to be inferred from internal structure and from drift:

- **VAT collisions.** The same number attributed to two different companies is a guaranteed error and requires no reference data to detect. This is the cheapest correctness signal available and it should be a hard alert.
- **Confirmation rate by cohort.** If the rate for a comparable slice drops from 12% to 4% between runs, something broke — a layout change, a blocked user agent, a parser regression. The absolute rate is uninformative; the change is not.
- **Mean attribution score over time.** Slow decay indicates that name matching is degrading, typically because more of the intake is drifting toward the weak-signal path.
- **Re-verification churn.** What fraction of previously-confirmed numbers now fail. Distinguishes genuine deregistration from pipeline decay.

**A free labelled test set.** The customer in the brief already holds VAT numbers for roughly a third of their 40,000 suppliers — about 13,000 company/VAT pairs. That is a ready-made evaluation set, and it is more valuable than anything I could build: it measures precision directly, on exactly the population the customer cares about, at no annotation cost. It does not measure recall — those are the suppliers they already solved — so it needs pairing with a manually annotated random sample to see the other half.

I applied the same reasoning to my own pipeline. Checking that `DORMANT (436,446) + NO ACCOUNTS FILED (985,311) = 1,421,757` reconciled against the 1,306,722 actually removed from the active pool, with the 115,035 difference explained by companies already excluded as non-active, confirmed the filters were doing what I believed. Two counts that should agree are the cheapest possible safety net.

## 3.4 Keeping it current

Registrations and deregistrations are continuous, so a dataset like this decays from the day it ships. Tiered re-verification: large and high-value companies monthly, the long tail quarterly or annually. Between cycles, event-driven triggers — a name change at Companies House, a domain that starts redirecting elsewhere, an insolvency notice — should force an out-of-cycle check on that record. Incremental re-verification is a small fraction of the initial build; a full rebuild is not, and should not be the default answer to staleness.

---

# Discussion topics

## Brute-forcing the checksum space

The arithmetic is worth doing rather than hand-waving. There are 10⁹ nine-digit numbers; accepting both checksum variants, 2.066% pass — measured, not estimated, on 100,000 consecutive numbers. That is roughly **20.6 million** plausible numbers. Against approximately 2.18 million live UK VAT registrations, about **one in nine** checksum-valid numbers is a real registration. At 10 requests per second the entire space is about 24 days of traffic, and it would return a name and address for every registration in the country.

So it is feasible, and I want to be clear that I noticed. I would not do it, and the reasons are not that it is slow:

- It violates the terms of use of a public service funded by taxpayers, and would be blocked long before completion once the traffic pattern was obvious.
- It is not "collecting public data" — it is enumerating a register that HMRC deliberately made non-enumerable. The design of the endpoint is the answer to whether they intended it to be traversed.
- The resulting dataset would be commercially worthless. No corporate customer will buy data whose provenance they cannot defend to their own compliance function, and provenance is the first question a buyer asks.
- The reputational and legal exposure falls on the company, not on the pipeline.

The interesting part of this question is not whether the maths works. It is that the same reasoning applies, in weaker form, to automating the public web form — which is why section 2.6 verified by hand instead.

## Keeping the dataset current

Covered in 3.4. The point I would add here: the refresh strategy should be driven by *what the customer joins on*. If VAT numbers are used for invoice matching, a stale number is caught immediately by the customer's own reconciliation and is cheap. If they are used for entity resolution across systems, a stale number silently merges two entities and is expensive. Refresh cadence should follow the cost of being wrong, not the rate of change.

## Knowing the dataset is wrong at scale, with no reference to compare against

Four mechanisms, in increasing cost:

1. **Internal consistency.** Collisions, reconciliation between counts that should agree, format invariants. Free, catches whole classes of error, and requires no external data.
2. **Distribution monitoring.** Confirmation rates, score distributions, source mix. Detects breakage, not incorrectness — but breakage is the more common failure.
3. **The customer's own data.** The 13,000 known pairs described in 3.3.
4. **Manual annotation.** A few hundred records per cycle, sampled randomly and adjudicated by a human. The only method that measures precision and recall honestly, and the only one that can calibrate the other three.

The pattern across all four: you cannot verify the dataset, but you can verify the *process*, and you can make silent failures loud. The five bugs in the appendix are the argument — every one of them produced clean, plausible output, and each was caught by a check on the process rather than on the result.

## Sources I would not sell

- **Scraped aggregators** (Endole, Company Check and similar). Redistribution of someone else's compiled data, against their terms. The legal exposure travels with the dataset to the customer.
- **Marketplace data with usage restrictions.** Fine to read, not fine to resell; the restriction is in the platform's terms and survives the extraction.
- **Anything built by brute-force enumeration.** Unsellable for the provenance reason above, regardless of accuracy.
- **Anything I cannot explain the origin of.** If I cannot name the source, the date and the method for a given record, it should not be in a product a customer joins their own data against.

---

# Beyond the UK

Germany is the instructive comparison, because the difficulty inverts.

| | UK | Germany |
|---|---|---|
| **Discovery** | Hard. No general publication duty; the number appears on unstandardised pages, if at all. Measured: 20% domain coverage, 2% extraction. | Nearly solved. §5 TMG makes an *Impressum* mandatory on every commercial site, with a predictable URL (`/impressum`) and a predictable label (`Umsatzsteuer-Identifikationsnummer`). |
| **Verification** | Rich. HMRC returns registered name and address, so attribution is checkable. | Blind. Germany does not return name and address through VIES; qualified confirmation at the BZSt requires the requester to hold a German VAT number. |

The pipeline built here does not survive the move. Step 5 — the step the whole project is about — becomes impossible, because there is nothing to compare the number against. Germany would need a different trust mechanism entirely: leaning on the fact that the Impressum is legally attached to the entity, or cross-referencing the Handelsregister.

Two countries, both "hard", failing in opposite places. Which suggests the useful question when prioritising a new market is not *how hard is discovery* but *which half of the problem is hard here*.

**And the opposite extreme.** In Denmark the VAT number is `DK` plus the CVR number, and the CVR register is fully open with a free API. There is no discovery problem — it is a string transformation. Sweden is similar (organisation number plus `01`).

The practical implication: **before building anything for a new market, check whether the VAT number is derived from the registry identifier.** Where it is, the market costs a day and reaches complete coverage. Those should be built first, and the effort saved spent on the UK, where it is actually needed.

---

# Repository

```
vat_checksum.py        mod-97 and mod-9755 validation
00_explore.py          register statistics; writes data/postcode_frequency.csv
00b_columns.py         prints column positions and first values
00c_probe_hmrc.py      HMRC API probe; writes evidence/hmrc_api_probe.txt
01_build_sample.py     two-stratum sample of 150, seed 42
02_find_websites.py    domain discovery and proof of ownership
03_extract_vat.py      VAT extraction with ±100 characters of context
04_verify.py           deduplication; builds the manual verification sheet
05_score.py            attribution scoring → data/results.csv
config.py              paths and chunk size

data/                  every input and output; each number above is traceable here
evidence/              raw HMRC API responses and web checker screenshot
notes.md               the lab notebook this document was written from
```

**To reproduce.** Download `BasicCompanyDataAsOneFile-YYYY-MM-01.zip` from
`https://download.companieshouse.gov.uk/en_output.html`, set `CSV_PATH` in `config.py`, then run the scripts in numerical order. `04_verify.py` writes a sheet with four blank columns to be filled in by hand from the HMRC web checker; it will not overwrite an existing `data/verified.csv`, because that file contains work that cannot be regenerated.

Requirements: `pandas`, `requests`.

---

# Appendix — five results that were wrong and raised no error

Every bug below produced clean, well-formed, plausible output. None raised an exception. Each was found by checking a value against an expectation, never by the program complaining.

**1. `names=` instead of `usecols=` in `pd.read_csv`.** Given three column names for a 55-column file, pandas silently made the first 52 columns an index and applied my names to the *last three* — which happen to be date fields. The script reported confirmation-statement dates as postcodes, formatted perfectly, with exit code 0. Caught only because "31/03/2026" is not a postcode.

**2. An exhausted iterator.** A second `for` loop over the same pandas reader. Iterators traverse once; the first loop had consumed it. The second loop never executed. Output: `pool_all: 0`, exit code 0, no warning.

**3. `pool_all = pool_all.extend(...)`.** `.extend()` mutates in place and returns `None`, so the list would have become `None`. This one never fired — it was hidden behind bug 2. Found by reading the code, not by running it.

**4. A doubled URL in the HMRC probe.** The base URL already contained the test number, and the code appended it again, producing an 18-digit request. The response was `404 MATCHING_RESOURCE_NOT_FOUND` — which reads exactly like *"the endpoint has been withdrawn"*. That conclusion, with a saved raw response as evidence, would have entered this document as a finding and been wrong. The evidence file contained the bug; the URL was printed in it.

**5. `str(nan) == "nan"` in the attribution scorer.** Missing names normalised to the literal string `"NAN"`, so two absent names scored 1.000 similarity against each other — a perfect match between two companies with no name. Had verification data been present, this would have produced CONFIRMED at maximum confidence. It sat inside `normalise()`, the function whose entire purpose is preventing false matches.

The pattern is the point. In this pipeline the dominant failure mode is not the exception — it is the plausible result. A valid VAT number attached to the wrong company is the same failure, at the output rather than the input: well-formed, confidently produced, and wrong.

That is why step 5 checks attribution rather than validity, and why section 2.4 exists. The argument is not one I read somewhere. It is one this project demonstrated five times before it demonstrated it on the data.
