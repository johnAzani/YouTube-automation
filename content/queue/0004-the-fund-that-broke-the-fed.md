---
id: "0004"
title: "The Fund That Broke the Fed: How Long-Term Capital Almost Took Down Wall Street"
slug: the-fund-that-broke-the-fed
status: draft             # DRAFT — awaiting human fact-check before approval (see originality note)
format: longform          # longform | short
niche: finance and business
category: education
voice: en-US-ChristopherNeural
target_minutes: 9
tags: [long term capital management, ltcm, 1998 financial crisis, russian default, hedge fund, wall street history]
thumb_text: "THE $4 BILLION BET"
description: |
  In 1998 a hedge fund run by two Nobel Prize winners and the most respected bond trader of his
  generation lost almost all of its capital in a few weeks. The Federal Reserve Bank of New York
  convened the largest banks on Wall Street and brokered a private bailout, because the
  alternative was an uncontrolled unwind of positions that touched the whole system.

  This is the story of Long-Term Capital Management: the model, the leverage, the month it broke,
  and the weekend the Fed decided it could not be allowed to fail disorderly.

  A money story, not money advice. No picks, no predictions — just the record.

  Sources (verify every claim against these before setting status: approved):
  - Lowenstein, R. (2000). When Genius Failed: The Rise and Fall of Long-Term Capital
    Management. Random House. (the standard narrative account)
  - Federal Reserve Bank of New York (1998). Statements and press briefing on the LTCM
    assistance, 23 September 1998. https://www.newyorkfed.org/
  - President's Working Group on Financial Markets (1999). Hedge Funds, Leverage, and the
    Lessons of Long-Term Capital Management. https://home.treasury.gov/
  - GAO (1999). Long-Term Capital Management: Testimony on the hedge fund and federal
    involvement, GAO/T-GGD-99-150. https://www.gao.gov/
  - Lowenstein / PWG report for the specific capital, loss and bailout figures — the numbers
    below are stated conservatively and must be checked against the primary documents.
# One query per scene, in scene order (tests assert the coverage).
asset_queries:
  - "trading floor new york"                  # S1 hook — PD Library of Congress floor photos
  - "bond certificate"                        # S2 the convergence trade
  - "stock market chart"                      # S3 the machine
  - "greenwich connecticut colonial house"    # S4 One Greenwich — PD Cos Cob, Greenwich CT
  - "stock exchange building moscow"          # S5 Russia defaults — PD 1876 Moscow Exchange
  - "federal reserve building washington"     # S6 the Fed steps in — CC BY 4.0
  - "abandoned office room"                   # S7 the aftermath — PD abandoned interiors
  - "stock market chart"                      # S8 the lesson (deliberate repeat of S3)
# Evidence behind every query above. Verified 2026-10-22 against the Wikimedia Commons
# MediaWiki API (generator=search, filetype:bitmap, gsrnamespace=6, top 4 results) and
# scored with exactly the licence filter pipeline/assets.py:_wikimedia applies — a result
# is only usable if its LicenseShortName contains cc0 / public domain / cc by and does NOT
# contain share-alike, noncommercial or no-derivatives. "usable" counts those results.
asset_query_verification:
  verified_on: "2026-10-22"
  method: "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-4, filtered by pipeline/assets.py licence rule"
  queries:
    - query: "trading floor new york"
      verified: true
      usable: 4
      evidence: "4x Public domain — Library of Congress NYSE trading-floor scans (LCCN2011630168, LCCN2011632435, LCCN2011634218, Highsmith 6718386525)"
    - query: "bond certificate"
      verified: true
      usable: 4
      evidence: "PD NARA war-bond poster 515403 + PD Papal states bond 1817 + 2x CC BY 4.0 museum bond certificates"
    - query: "stock market chart"
      verified: true
      usable: 4
      evidence: "PD Austrian stock market index + CC0 Stock market charts illustration + PD Stock Market April 5 2025 + CC BY 2.0 UK Stock Market"
    - query: "greenwich connecticut colonial house"
      verified: true
      usable: 2
      evidence: "PD Colonial Cottage, Cos Cob (Greenwich CT) + PD Stanwich Church 1804; remaining hits are 'No restrictions', which the pipeline filter does not accept"
    - query: "stock exchange building moscow"
      verified: true
      usable: 2
      evidence: "PD 'Moscow, Iliynka Street Exchange by A.S.Kaminsky, 1876' + CC BY 2.0 old Moscow Exchange building; FAL-licensed hits are rejected by the filter"
    - query: "federal reserve building washington"
      verified: true
      usable: 4
      evidence: "4x CC BY 4.0 photographs of the Eccles Federal Reserve Building, Washington DC"
    - query: "abandoned office room"
      verified: true
      usable: 3
      evidence: "3x Public domain abandoned/empty interior photographs; the CC BY-SA 3.0 hit is rejected by the filter"
originality:
  original_thesis: true      # argues the failure was convergence risk + funding fragility, not bad maths
  unique_structure: true     # model-first structure: the machine, then the month, then the rescue
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

    1. verified every figure against the sources listed in `description` (start with the
       President's Working Group report and the GAO testimony — they are the primary
       official accounts of the rescue and its terms);
    2. rewritten the narration in their own words;
    3. flipped `human_rewrite` to `true` and `status` to `approved`.

  That is the human-creative / machine-labour split the whole repo is built on
  (PLAN.md §4.4). Do not flip the flag as a convenience.

  Specific figures that most need a second pair of eyes: the capital and notional-exposure
  numbers in Scene 3, the loss figures in Scene 6, and the composition and size of the
  bailout in Scene 7. Secondary sources disagree on the exact notional, which is why the
  script hedges the phrasing — keep that hedging.
-->

## Scene 1 — The hook
In September nineteen ninety-eight, the Federal Reserve Bank of New York did something it had
almost never done. It called the largest banks on Wall Street into a room and told them to
rescue a hedge fund. Not a bank. Not a brokerage. A four-year-old fund in Connecticut with
fewer than thirty people on its payroll. The reason was not that the fund mattered in itself.
It was that the fund had borrowed so much, from so many counterparties, in so many markets at
once, that nobody could say what would happen if it simply stopped paying. Two of its founders
had won the Nobel Prize in economics the year before. The models were not the problem. The
borrowing was.

## Scene 2 — The convergence trade
Long-Term Capital Management opened in nineteen ninety-four. The founding partner was John
Meriwether, the trader who had built Salomon Brothers' bond arbitrage desk into the most
profitable operation in the firm. Two of his partners, Myron Scholes and Robert Merton, were
the academics whose option-pricing work would win the Nobel Prize in nineteen ninety-seven. The
strategy was called convergence trading. The idea is simple: find two securities that are
economically almost the same thing but priced slightly differently, buy the cheap one, sell the
expensive one, and wait for the gap to close. The gap usually closes. The trades are small,
safe-looking, and individually unremarkable. The profit on each one is tiny. So to make the
business worth running, you do an enormous number of them, and you borrow the money to do it.

## Scene 3 — The machine
That borrowing is the whole story. By nineteen ninety-eight the fund had roughly four point
seven billion dollars of capital, which for a hedge fund is a lot of money. Against it, the
fund had built positions measured in the hundreds of billions of dollars of notional value,
mostly in interest-rate derivatives across more than a dozen countries. Reported leverage on
the balance sheet was somewhere around twenty-five to one. The total exposure, including
derivatives that never appear as balance-sheet borrowing, was far larger — official reports
describe it in the trillions of dollars of notional. The fund also had a financing advantage
that made the structure possible: it was so respected that banks lent to it on unusually thin
collateral. In some trades it paid almost no margin at all. The machine worked beautifully,
right up until the moment when every trade moved the same way.

## Scene 4 — One Greenwich
The fund operated out of One Greenwich, an office building in Connecticut, deliberately away
from the noise of Manhattan. It ran itself like a research institute rather than a trading
floor: shared bonuses, a single capital pool, academics and traders arguing in the same rooms.
Its partners were famously collegial and famously confident. That confidence had a basis. For
its first three years the returns were extraordinary, and the losses were small. But the
structure had a property that no one on the inside liked to state out loud. Every one of these
convergence trades had the same failure mode. If markets stopped behaving normally at the same
time, every position lost at once. Diversification across a hundred trades is worth nothing if
all a hundred are the same bet wearing different clothes.

## Scene 5 — Russia defaults
On the seventeenth of August, nineteen ninety-eight, Russia devalued the ruble and defaulted on
its own domestic debt. This was not supposed to be possible. The conventional view at the time
was that a sovereign state would always pay debts in its own currency, because it could print
the money. Russia printed it and still did not pay. The consequence went far beyond Russia.
Investors around the world stopped lending against anything complicated, and fled into the
simplest, safest assets they could find. In market language, they fled to quality. That is
exactly the wrong event for a convergence fund. The spreads Long-Term Capital was betting would
narrow blew out instead, violently, in almost every position simultaneously, within days.

## Scene 6 — The month it broke
The fund lost roughly half its capital in August. It kept the positions, on the reasoning that
the spreads would eventually close and that selling into the panic would lock in the loss. That
reasoning was not obviously wrong. It was simply unaffordable. Its lenders began to demand more
collateral, and the fund did not have enough left to give. In September, in a matter of weeks,
capital that had stood at four point seven billion dollars was down to a few hundred million.
The partners asked their banks for time. Some began talking to potential buyers. And the
Federal Reserve Bank of New York started to worry about a different problem entirely: an
uncontrolled liquidation, in which every one of the fund's counterparties tried to close its
own exposure at the same moment, in markets that were already not functioning.

## Scene 7 — The room on Liberty Street
On the twenty-third of September, nineteen ninety-eight, the Federal Reserve Bank of New York
hosted a meeting of the fund's largest counterparties. Fourteen banks were involved in the
final discussions. The result was a private rescue: a consortium contributed roughly three and
a half billion dollars, took control of the fund's positions, and agreed to wind them down in
an orderly way over time. No public money was used. The Federal Reserve did not guarantee
anything and did not become a lender. What it did supply was the room, the deadline, and the
pressure. The partners were effectively diluted to a fraction of what they had owned. Merrill
Lynch withdrew from an earlier bid. Two of the largest banks ended up providing the money that
saved a competitor, because the alternative was worse for everyone.

## Scene 8 — The lesson
Long-Term Capital was wound up over the following two years. The banks that took it over
ultimately recovered most of what they put in, because the positions were given time to settle.
The fund's own investors lost nearly everything. The official response was measured: a
President's Working Group report on hedge funds, leverage, and the lessons of the episode, and
a lasting argument about whether the rescue had been necessary or merely convenient. The
narrowest and most durable lesson is not about intelligence. Scholes and Merton understood risk
better than almost anyone alive. It is about funding. A portfolio can be right about value and
still be destroyed by the terms on which it borrowed. Being right eventually is worthless if
you cannot survive until then.
