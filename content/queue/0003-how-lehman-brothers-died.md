---
id: "0003"
title: "How Lehman Brothers Failed: Repo 105, Leverage and the Funding Run"
slug: how-lehman-brothers-died
status: draft             # Research revision, NOT human approval.
format: longform
niche: finance and business
category: education
voice: en-US-ChristopherNeural
target_minutes: 9
tags: [lehman brothers, 2008 financial crisis, repo 105, wall street, business documentary, bankruptcy]
thumb_text: "LOOKING SAFER"
description: |
  Lehman Brothers Holdings Inc. filed for Chapter 11 on September 15, 2008.
  This documentary examines its risky assets, dependence on market funding,
  failed rescue negotiations, and the temporary quarter-end transactions
  reconstructed by the bankruptcy examiner in 2010. Repo 105 is part of the
  story, not a demonstrated single cause of Lehman's failure or the crisis.

  A money story, not money advice. No picks, no predictions — just the record.

  Sources (human verification still required before approval):
  - Valukas, Anton R. (2010). Examiner's Report, Volume 3, Repo 105 executive summary.
    https://web.stanford.edu/~jbulow/lehmandocs/VOLUME%203.pdf
  - Financial Crisis Inquiry Commission (2011). Final Report, Chapter 18.
    https://fcic-static.law.stanford.edu/cdn_media/fcic-reports/fcic_final_report_chapter18.pdf
  - Lehman Brothers Holdings Inc. (2007). Fiscal 2007 Form 10-K.
    https://www.sec.gov/Archives/edgar/data/806085/000110465908005476/a08-3530_110k.htm
  - Wiggins and Metrick (2019). Yale case C: Managing the Balance Sheet Through Repo 105.
    https://elischolar.library.yale.edu/cgi/viewcontent.cgi?article=1002&context=journal-of-financial-crises
  - Harvard Baker Library. Lehman Brothers archival timeline.
    https://www.library.hbs.edu/special-collections-and-archives/exhibits/lehman/timeline
  - Baxter, Thomas (2010). Testimony to the Financial Crisis Inquiry Commission.
    https://www.newyorkfed.org/newsevents/speeches/2010/bax100901
  - Reserve Primary Fund (2008). September 16 notice and November 26 NAV correction.
    https://www.sec.gov/spotlight/reserve_primary_fund_investors/osnato_declaration_exhibit_14.pdf
    https://www.sec.gov/spotlight/reserve_primary_fund_investors/osnato_declaration_exhibit_13.pdf
  - Federal Reserve (2008). AIG authorization, September 16, 9 p.m. EDT.
    https://www.federalreserve.gov/newsevents/pressreleases/other20080916a.htm
  - Treasury (2008). Money-fund guarantee opening, September 29; announced September 19.
    https://home.treasury.gov/news/press-releases/hp1161
  - Lehman Brothers Holdings Inc. (2008). Asset-sale Form 8-K, September 22/23 events.
    https://www.sec.gov/Archives/edgar/data/806085/000110465908060737/a08-22764_88k.htm
  - Lehman Brothers Holdings Inc. (2012). Plan-effective-date Form 8-K.
    https://www.sec.gov/Archives/edgar/data/806085/000090951812000100/mm03-1212_8k.htm
  - SIPC (2022). Conclusion of the separate Lehman Brothers Inc. liquidation.
    https://www.sipc.org/news-and-media/news-releases/20220928
  - LBIE administrators (2025). Final administration report, October 14.
    https://www.pwc.co.uk/business-recovery/administrations/lehman/lbie/LBIE_Final_Report_October_2025.pdf
research_notes: content/research/0003-lehman-dossier.md
claim_audit: content/research/0003-lehman-claim-audit.md
# One query per scene, in scene order (tests assert the coverage). Revised
# 2026-10-21: every query below was verified against the Wikimedia Commons
# search API to return multiple CC0 / public-domain / CC-BY matches — the
# keyless providers must be able to source each scene (MAINTENANCE.md §3).
asset_queries:
  - "new york stock exchange trading floor"   # S1 hook — PD floor photos
  - "financial district skyscraper manhattan" # S2 Lehman's world
  - "ledger accounting book"                  # S3 balance sheet — CC0/PD ledgers
  - "stock certificate"                       # S4 Repo 105 — securities paper
  - "courtroom judge bench"                   # S5 examiner's report
  - "Federal Reserve Bank of New York"        # S6 the weekend at the NY Fed
  - "bank run"                                # S7 contagion — run on the funds
  - "wall street sign"                        # S8 verdict
# Evidence behind every query above, recorded 2026-10-22.
#
# These eight queries were NOT re-probed against the Commons search API on 2026-10-22 — the
# sandbox running that check had no TLS egress to commons.wikimedia.org. What they have
# instead is stronger evidence: the advisory `pipeline-dry-run` job actually rendered this
# job on a keyless GitHub runner, which means `_wikimedia()` (or a sibling keyless provider)
# returned a usable, licence-clean asset for every one of the eight scenes.
#
# Verified 2026-10-22 via `gh run view 39734567120 --json jobs`:
#   job "General pipeline dry-run (needs network)" → conclusion=success
#   on main @ af63d2c4ae4f5c4972ff87027ce7fcdd19461b57
# `dry-run.yml` renders `content/queue/*.md | head -n1`, and 0003 sorts first, so 0003 is
# the job that run exercised. (Jobs 0004–0006 are therefore NOT covered by that run — they
# carry Commons probe counts in their own verification blocks instead.)
asset_query_verification:
  verified_on: "2026-10-22"
  method: "end-to-end: dry-run.yml job 'General pipeline dry-run (needs network)' sourced all 8 scenes with no API keys (commons.wikimedia.org search API not reachable from the recording sandbox)"
  ci_run: "39734567120"
  ci_sha: "af63d2c4ae4f5c4972ff87027ce7fcdd19461b57"
  queries:
    - query: "new york stock exchange trading floor"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 1 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "financial district skyscraper manhattan"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 2 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "ledger accounting book"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 3 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "stock certificate"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 4 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "courtroom judge bench"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 5 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "Federal Reserve Bank of New York"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 6 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "bank run"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 7 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
    - query: "wall street sign"
      verified: true
      ci_verified: 39734567120
      evidence: "scene 8 sourced on the keyless runner in dry-run 39734567120 (main @ af63d2c); no Commons probe recorded for this query"
originality:
  original_thesis: true      # Reported leverage was not a substitute for durable funding.
  unique_structure: true     # Balance sheet, accounting, rescue, then entity-specific outcomes.
  human_rewrite: false       # Machine-assisted research is NOT a human rewrite or sign-off.
  no_ai_persona: true
  source_notes: true
  ai_disclosure: false       # Existing production setting; re-evaluate against the final visuals.
---

<!--
MAINTAINER NOTE — this is a machine-assisted research revision, not approval.
Read content/research/0003-lehman-dossier.md and the companion claim audit.
The worksheet is mechanical and verifies nothing. A human must check the evidence,
rewrite the narration in their own words, review the actual visuals/disclosure needs,
and sign off before changing human_rewrite or status. Never bypass that gate.
Historical asset-query evidence above applies to the earlier render, not to a new cut.
-->

## Scene 1 — The hook
Early on September fifteenth, two thousand and eight, Lehman Brothers Holdings filed for
Chapter Eleven bankruptcy. But the failure was not born in a single weekend. It followed
months of losses, difficult assets, and growing doubts about the firm's ability to fund itself.

There was also something the public reporting did not reveal. Lehman was using temporary
transactions to make its quarter-end balance sheet look smaller. A court-appointed examiner
would reconstruct that practice in two thousand and ten. To understand it, we need to separate
three things: what Lehman owned, how it borrowed, and what its published numbers showed.

## Scene 2 — A name built over generations
Its roots reached back to a dry-goods store opened by Henry Lehman in Alabama in eighteen
forty-four. His brothers later joined him, and the enterprise became Lehman Brothers.
The business grew far beyond that store. By nineteen ninety-four, when it was spun off from
American Express, Richard Fuld was leading a major Wall Street firm.

By two thousand and eight, that history could not answer the question confronting lenders:
how much were Lehman's assets worth, and could the firm meet its obligations? Concern was
already visible after Bear Stearns nearly failed in March. Lehman's reputation was real.
So were the warnings. Its eventual bankruptcy was a shock, not a possibility nobody had imagined.

## Scene 3 — The balance sheet and the clock
At its fiscal year-end in November two thousand and seven, Lehman reported roughly six hundred
and ninety-one billion dollars of assets and twenty-two and a half billion dollars of
stockholders' equity. That was about thirty-one dollars of assets for each dollar of equity.
It was the firm's gross leverage ratio, not the different net leverage measure we will come to.

Lehman held substantial commercial and residential real-estate exposures. Some assets were
hard to sell without accepting losses. Meanwhile, continued access to secured borrowing was
essential. If lenders demanded more collateral or stopped renewing funding, assets that might
eventually pay could still fail to produce cash when Lehman needed it.

That is the dangerous interaction between asset risk and funding risk. A quarter-end ratio
can describe a balance sheet. It cannot promise that tomorrow's lenders will renew their loans.

## Scene 4 — What Repo 105 changed
A repurchase agreement, or repo, exchanges securities for cash with an agreement to buy the
securities back. An ordinary repo is accounted for as secured borrowing. The securities remain
on the borrower's books, alongside the obligation to repay the cash.

Lehman's Repo one-oh-five program used a different accounting treatment. It supplied at least
one hundred and five dollars of fixed-income securities for every hundred dollars of cash.
Related equity transactions were called Repo one-oh-eight. The examiner generally grouped
both under the Repo one-oh-five name.

Lehman recorded these transactions as sales. It removed the securities and did not record an
ordinary repo borrowing. Then came the crucial second step: it used the cash to pay down other
liabilities. That made reported assets and liabilities smaller at the reporting date.
Shortly afterward, Lehman borrowed again, paid to repurchase the securities, and brought them back.

At the end of its second fiscal quarter in two thousand and eight, the combined program
amounted to about fifty billion dollars. That was not fifty billion dollars stolen or lost.
Yale researchers, drawing on the examiner, report that net leverage would have been thirteen
point nine times without the program, rather than the reported twelve point one.
This was a temporary improvement in a reported measure, not a permanent solution to the
firm's difficult assets. The securities transferred were not necessarily those troubled assets.

## Scene 5 — What the examiner actually concluded
In March two thousand and ten, bankruptcy examiner Anton Valukas described the program and
Lehman's failure to disclose it. His report found evidence supporting claims that the financial
reporting was materially misleading. That is not the same thing as a criminal conviction.

The legal-opinion detail matters. According to the examiner, Lehman could not obtain the needed
opinion under United States law. Linklaters did provide an opinion under English law for its
European broker-dealer. Lehman routed the transactions through that London entity.
An opinion about legal sale treatment did not settle whether investors received fair disclosure.

The report distinguished those questions. Its disclosure conclusion did not depend on resolving
whether the transactions technically complied with the relevant accounting standard.
And its detailed public account came after the collapse. We should not pretend that lenders
spent the final weekend reacting to a report that would not appear until two thousand and ten.

## Scene 6 — The rescue that did not close
By September, Lehman's share price and funding were under intense pressure. After markets
closed on Friday, September twelfth, officials brought financial-sector leaders to the
Federal Reserve Bank of New York to work on a solution. Bank of America pursued Merrill Lynch
instead. Barclays remained a potential buyer.

But buying Lehman required more than agreeing a price. Someone had to deal with difficult
assets and guarantee trading obligations between signing and completion. Barclays faced a
shareholder-approval obstacle. British authorities did not provide the waiver needed to get
that arrangement done on the crisis timetable.

Why did American officials not bridge the gap? Their later explanations emphasized legal powers,
collateral and the absence of an executable buyer arrangement. The Financial Crisis Inquiry
Commission also emphasized policy choices and errors. The feasibility of a rescue remains
contested; a simple story that one government could not, or merely would not, save Lehman
leaves out that disagreement.

The rescue failed. Early Monday, the parent company filed. That did not put every Lehman
subsidiary into the same proceeding, and the Federal Reserve subsequently financed the United
States broker-dealer during its wind-down. Supporting that entity was not the same as rescuing
the parent as a going concern.

## Scene 7 — The contagion and the response
On September sixteenth, the Reserve Primary Fund announced a share value of ninety-seven cents
after marking its Lehman debt to zero. A later correction said its value had already been
ninety-nine cents for part of that day. For investors accustomed to a stable dollar share price,
the message was alarming: a money-market fund could lose value.

The episode intensified an already developing scramble for liquidity. That evening, the
Federal Reserve authorized lending of up to eighty-five billion dollars to AIG. The insurer
had problems of its own; its crisis was not created solely by Lehman's bankruptcy.

On September nineteenth, Treasury announced a temporary guarantee program for participating
money-market funds. The program opened ten days later, with eligibility rules and a cutoff
for the holdings it covered. It was not an unlimited promise to repay every investor in every fund.
The financial system was already under strain, and Lehman's failure made that emergency worse.

## Scene 8 — Several different endings
Parts of the operating business survived under new owners. Barclays completed its purchase of
specified North American businesses and assets on September twenty-second. Nomura announced
purchases of selected Asian and European businesses, not every Lehman trading asset and liability.

For the parent, a Chapter Eleven plan became effective in March two thousand and twelve.
That was a step in a long wind-down, not the return of the old investment bank.
There is no single recovery percentage for everyone called a Lehman creditor.

When the separate United States broker-dealer liquidation closed in September two thousand and
twenty-two, SIPC reported full satisfaction of customer claims, while general unsecured creditors
had received about forty-one cents on the dollar. Further trust distributions remained possible.
In a different proceeding, the European broker-dealer's administrators reported full repayment
of creditors plus statutory interest before a solvent winding-down process began in October
two thousand and twenty-five. Neither outcome describes all of Lehman.

The lesson is not that one accounting transaction caused the entire crisis. It is that a
cleaner-looking balance sheet cannot substitute for assets people trust and funding that remains
available. Ask what a ratio measures, whether the improvement will last, and what happens when
the next loan comes due.

For more source-led stories about the businesses behind the headlines, subscribe.
