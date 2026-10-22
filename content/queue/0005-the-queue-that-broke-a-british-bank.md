---
id: "0005"
title: "The Queue That Broke a British Bank: Northern Rock and the First Run in 150 Years"
slug: the-queue-that-broke-a-british-bank
status: draft             # DRAFT — awaiting human fact-check before approval (see originality note)
format: longform          # longform | short
niche: finance and business
category: education
voice: en-US-ChristopherNeural
target_minutes: 9
tags: [northern rock, bank run, 2007, credit crunch, bank of england, uk banking, financial crisis]
thumb_text: "THE FIRST RUN IN 150 YEARS"
description: |
  On Friday the fourteenth of September, two thousand and seven, people queued outside bank
  branches across Britain to take their money out. It was the first retail run on a British bank
  in roughly a century and a half, and the bank was not a reckless one. Northern Rock had funded
  a fifth of all new British mortgages by borrowing in wholesale markets instead of taking
  deposits. When those markets closed, the funding stopped — and the disclosure of that fact
  triggered exactly the event the funding model was supposed to avoid.

  This is the story of a funding model, a leaked letter, and three days in September.

  A money story, not money advice. No picks, no predictions — just the record.

  Sources (verify every claim against these before setting status: approved):
  - Bank of England (2007). Statements on Northern Rock, 14 and 17 September 2007.
    https://www.bankofengland.co.uk/
  - HM Treasury (2008). Northern Rock: announcement of temporary public ownership,
    22 February 2008. https://www.gov.uk/government/organisations/hm-treasury
  - House of Commons Treasury Committee (2008). The run on the Rock, HC 56-I.
    https://committees.parliament.uk/ (the official post-mortem — read this first)
  - Financial Services Authority (2008). The failure of Northern Rock — not primarily an
    FSA failure, but the supervisory record is set out here.
  - Banking (Special Provisions) Act 2008 (the instrument used to nationalise).
    https://www.legislation.gov.uk/
  - Note for the reviewer: the "first run in 150 years" framing refers to the 1866 failure of
    Overend, Gurney and Company. Check the precise wording before it goes on screen.
# One query per scene, in scene order (tests assert the coverage).
asset_queries:
  - "northern rock bank"                   # S1 hook — CC BY 2.0 photograph of the actual queue
  - "newcastle upon tyne street"           # S2 the building society
  - "bond certificate"                     # S3 wholesale funding — PD/CC BY certificates
  - "stock market chart"                   # S4 the securitisation machine — CC0/PD charts
  - "stock market crash chart"             # S5 August 2007 — CC0 + PD market charts
  - "bank of england london"               # S6 the letter — PD 1885–1895 Bank of England view
  - "bank run queue"                       # S7 the run — PD 19th-c. run + CC BY 2.0 Rock queue
  - "london financial district building"   # S8 the aftermath — PD 5 Canada Square exterior
# Evidence behind every query above. Verified 2026-10-22 against the Wikimedia Commons
# MediaWiki API (generator=search, filetype:bitmap, gsrnamespace=6, top 4 results) and
# scored with exactly the licence filter pipeline/assets.py:_wikimedia applies — a result
# is only usable if its LicenseShortName contains cc0 / public domain / cc by and does NOT
# contain share-alike, noncommercial or no-derivatives. "usable" counts those results.
#
# HONEST WARNING: four of these eight queries return only ONE usable hit in the top four,
# because Commons is dominated by CC BY-SA photography of British streets and buildings and
# the pipeline deliberately refuses share-alike. One usable hit is enough for the pipeline to
# succeed, but it means the scene's visual is effectively chosen for us. If a scene looks
# wrong in the dry-render, add a PEXELS_API_KEY or PIXABAY_API_KEY secret — those providers
# are tried first in pipeline/assets.py and give real choice.
asset_query_verification:
  verified_on: "2026-10-22"
  method: "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-4, filtered by pipeline/assets.py licence rule"
  queries:
    - query: "northern rock bank"
      verified: true
      usable: 1
      evidence: "CC BY 2.0 'Northern Rock Queue' is the only filter-passing hit; 'Birmingham Northern Rock bank run 2007' and 'Northern Rock, Briggate, Leeds' are CC BY-SA and rejected; 4th hit is irrelevant (Dome of the Rock)"
    - query: "newcastle upon tyne street"
      verified: true
      usable: 1
      evidence: "CC BY 2.0 'Tyne Theatre - Newcastle upon Tyne' passes; the three Dean/Grey/Grainger Street photos are all CC BY-SA and rejected"
    - query: "bond certificate"
      verified: true
      usable: 4
      evidence: "PD NARA war-bond poster 515403 + PD Papal states bond 1817 + 2x CC BY 4.0 museum bond certificates"
    - query: "stock market chart"
      verified: true
      usable: 4
      evidence: "PD Austrian stock market index + CC0 Stock market charts illustration + PD Stock Market April 5 2025 + CC BY 2.0 UK Stock Market"
    - query: "stock market crash chart"
      verified: true
      usable: 2
      evidence: "CC0 'Annual Income Growth by Income' + PD 'Stock Market April 5 2025 3 Months'; the DowJones2020crash chart is CC BY-SA and rejected"
    - query: "bank of england london"
      verified: true
      usable: 1
      evidence: "PD 'The Bank of England, London, 1885-1895' passes; the Diliff exterior, the Museum interior and the 2025 II photo are all CC BY-SA and rejected. Note: 'bank of england threadneedle street' returns 4/4 CC BY-SA — zero usable — which is why this query is the shorter one"
    - query: "bank run queue"
      verified: true
      usable: 2
      evidence: "PD 'NineteenthWardBankRunNYC' + CC BY 2.0 'Northern Rock Queue'; the other two hits are CC BY-SA and rejected"
    - query: "london financial district building"
      verified: true
      usable: 1
      evidence: "PD 'Exterior of 5 Canada Square' passes; the West India Quay / Canada Square photos are CC BY-SA and rejected"
originality:
  original_thesis: true      # argues the run was caused by the funding model, not by the depositors
  unique_structure: true     # funding-first structure: the model, then the leak, then the queue
  human_rewrite: false       # *** FALSE ON PURPOSE *** facts not yet human-verified — gate must block
  no_ai_persona: true        # documentary narration; no advisor persona, no recommendations
  source_notes: true         # sources listed in description
  ai_disclosure: false       # narration is synthetic voice; no photorealistic synthetic media
---

<!--
  MAINTAINER NOTE — read before approving.

  `human_rewrite` is deliberately `false`. `pipeline/originality.py` treats that as a hard
  block, so this job can be dry-rendered but can never be approved-and-uploaded until a
  human has:

    1. verified every figure and date against the sources listed in `description` — the House
       of Commons Treasury Committee report "The run on the Rock" is the primary document and
       should settle almost every disputed number in this script;
    2. rewritten the narration in their own words;
    3. flipped `human_rewrite` to `true` and `status` to `approved`.

  That is the human-creative / machine-labour split the whole repo is built on
  (PLAN.md §4.4). Do not flip the flag as a convenience.

  Two claims to check hardest, because they are the ones a British viewer will correct you on:
  the "first run in ~150 years" framing (Scene 1 / Scene 7) and the final public cost to the
  taxpayer (Scene 8). The script states the cost question rather than a figure precisely
  because secondary sources disagree; keep it that way unless you can cite the Treasury.
-->

## Scene 1 — The hook
On a Friday morning in September two thousand and seven, people began queueing outside bank
branches in Newcastle, in Birmingham, in London and in towns across Britain. They were not
there to open accounts. They were there to withdraw their savings, in cash, because they had
heard that their bank had gone to the Bank of England for emergency support. Britain had not
seen a retail run on a bank in roughly a century and a half. When it finally happened, the bank
was not a gambling operation. It was the country's fifth largest mortgage lender, regulated,
audited, and profitable right up until the week it nearly died. The queue was not caused by bad
loans. It was caused by how the bank funded itself — and by the fact that everybody found out
at the same time.

## Scene 2 — A building society from Newcastle
Northern Rock's roots were in the north-east of England, in the building society tradition. A
building society is a mutual: it is owned by its savers and borrowers rather than by
shareholders, and it funds mortgages almost entirely from the deposits of its members. That
model is slow, boring, and extremely hard to break, because the money it lends is money that
belongs to the people standing at the counter. In nineteen ninety-seven, Northern Rock
demutualised — it floated on the stock market and became a bank. What followed was one of the
fastest growth stories in British retail banking. The bank went from a regional lender to a
national one, and by the mid-two-thousands it was writing roughly a fifth of all new mortgages
in the country. Growth that fast requires money, and deposits were not arriving fast enough.

## Scene 3 — The funding model
So Northern Rock borrowed it. Instead of waiting for savers, the bank went to wholesale
markets — the market where banks, funds and institutions lend to each other — and issued bonds
and other securities to fund its mortgage book. In normal conditions this is cheap, fast, and
entirely ordinary. It is how a great many banks operate. But wholesale money has a property
deposits do not. Depositors do not review their decision every ninety days. Wholesale lenders
do. They lend short, they reassess constantly, and they can simply stop. A bank funded that way
has a structural exposure that has nothing to do with the quality of its loans: if confidence
in the funding market fails, the bank loses its money supply overnight, even while every
mortgage on its books is performing perfectly. Northern Rock's loans were fine. Its funding was
the risk.

## Scene 4 — The machine
The bank built an entire apparatus around that model. Mortgages were bundled into securities
and sold to investors — a process called securitisation — which turned illiquid twenty-five-year
home loans into tradeable paper and brought in fresh cash to lend again. That cash funded more
mortgages, which were bundled and sold again. The engine worked because the market for the
paper kept buying. British house prices kept rising, defaults stayed low, and the securities
were rated well enough that institutional investors were happy to hold them. On paper this was
a beautifully efficient machine: a regional lender had found a way to manufacture its own
funding supply. What the machine could not do was survive a moment when investors stopped
buying the paper. It had no alternative fuel tank.

## Scene 5 — August 2007
In August two thousand and seven, that moment arrived. Problems in the American subprime
mortgage market made it impossible for investors to tell which mortgage-backed securities were
safe, so they stopped buying all of them. Interbank lending — banks lending to each other —
seized up almost immediately, because nobody knew which institution was holding the losses.
Central banks on both sides of the Atlantic injected emergency liquidity into the system within
days. For most banks this was an expensive inconvenience. For a bank whose entire funding model
depended on short-term wholesale markets and on selling mortgage paper, it was existential. The
money that Northern Rock ran on simply was not there to be borrowed.

## Scene 6 — The letter
In early September, Northern Rock approached the Bank of England for emergency liquidity
assistance — the lender of last resort function that central banks exist to provide. The
approach was confidential, as such approaches always are. On the evening of Thursday the
thirteenth of September, the BBC reported it. The following morning, the Bank of England
publicly confirmed the facility. The reasoning at the time was that hiding it would be worse: a
bank quietly drawing emergency funding while telling depositors nothing is a bank that will
eventually be found out. But confirmation converted a private funding problem into a public
confidence problem in a single night. People who had never thought about how their bank was
funded now had a reason to think about it. And there was one crucial detail that made the
answer worse.

## Scene 7 — The run
At the time, British deposit protection did not cover the whole of a depositor's savings —
only the first portion was fully guaranteed. A saver with more than that in the bank had a
rational reason to withdraw. On Friday the fourteenth of September, the queues began. By the
weekend an estimated two billion pounds or more had been withdrawn. On the Monday, the
Chancellor appeared on television and announced that the government would guarantee all
deposits at Northern Rock — a guarantee extended beyond what the existing protection scheme
required. The queues stopped almost immediately. That sequence is the whole lesson. The run was
not caused by insolvency, and it was not caused by panic in the irrational sense. It was caused
by a funding structure that only worked while nobody asked, disclosed at the worst possible
moment, under a compensation regime that gave large savers a reason to move first.

## Scene 8 — The aftermath
The bank could not be sold quickly enough, and in February two thousand and eight the
government took it into temporary public ownership under emergency legislation passed for the
purpose. It was run down and eventually sold to the private sector over the following years.
Depositors lost nothing. Shareholders lost most of what they had, and the argument about
whether they should have been compensated ran for years afterwards. The Treasury Committee's
inquiry was blunt about where the failure lay: not primarily with the supervisors, but with a
funding model that no one had stress-tested against the closing of wholesale markets. Britain
rewrote its deposit guarantee rules afterwards. The durable point is uncomfortable for anyone
running a bank or judging one: the institutions that fail in a crisis are often not the ones
that made the worst loans. They are the ones that assumed the money would always be there.
