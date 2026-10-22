---
id: "0006"
title: "How One Trader Deleted a 233-Year-Old Bank: Barings and Account 88888"
slug: how-one-trader-deleted-a-bank
status: draft             # DRAFT — awaiting human fact-check before approval (see originality note)
format: longform          # longform | short
niche: finance and business
category: education
voice: en-US-ChristopherNeural
target_minutes: 9
tags: [barings bank, nick leeson, rogue trader, account 88888, simex, risk management, banking history]
thumb_text: "ACCOUNT 88888"
description: |
  In February 1995, Barings — the merchant bank that had financed the Louisiana Purchase and
  survived the Panic of 1890 — was declared insolvent. The cause was a single trader in
  Singapore who had been given control of both the trading floor and the back office that was
  supposed to check him. He hid his losses in an error account numbered 88888 and kept doubling
  down until the losses exceeded the entire capital of the bank.

  This is not a story about a criminal mastermind. It is a story about what happens when one
  person is allowed to make the bets and also record whether they won.

  A money story, not money advice. No picks, no predictions — just the record.

  Sources (verify every claim against these before setting status: approved):
  - Board of Banking Supervision (1995). Report of the Board of Banking Supervision Inquiry
    into the circumstances surrounding the collapse of Barings Bank ("the Middleton report").
    The definitive official account of the control failures — read this first.
  - House of Commons Treasury Committee / Public Accounts Committee hearings on Barings, 1995.
    https://committees.parliament.uk/
  - Barings plc (1995). Announcement of reconstruction, 5 March 1995 — the terms under which
    ING acquired the business for a nominal sum.
  - Singapore Exchange / SIMEX and the Monetary Authority of Singapore statements on the
    conduct of Barings' futures business in Singapore, 1995.
  - Leeson, N. (1996). Rogue Trader. (first-person account — useful for sequence, NOT a
    reliable source for the control failures or for any figure; treat as a hostile witness)
# One query per scene, in scene order (tests assert the coverage).
asset_queries:
  - "royal exchange london interior"       # S1 hook — CC0 historic exchange interiors
  - "barings bank"                         # S2 the merchant bank — PD 1892 letter of credit, PD portraits
  - "bond certificate"                     # S3 the back office — PD/CC BY financial paper
  - "stock market chart"                   # S4 Singapore — CC0/PD market charts
  - "stock market chart"                   # S5 account 88888 (deliberate repeat of S4)
  - "abandoned office room"                # S6 Kobe — PD damaged/empty interiors (mood plate, see note)
  - "london financial district building"   # S7 the bank dies — PD City building exterior
  - "royal exchange london interior"       # S8 the lesson (deliberate repeat of S1)
# Evidence behind every query above. Verified 2026-10-22 against the Wikimedia Commons
# MediaWiki API (generator=search, filetype:bitmap, gsrnamespace=6, top 4 results) and
# scored with exactly the licence filter pipeline/assets.py:_wikimedia applies — a result
# is only usable if its LicenseShortName contains cc0 / public domain / cc by and does NOT
# contain share-alike, noncommercial or no-derivatives. "usable" counts those results.
#
# QUERIES REJECTED DURING VERIFICATION (recorded so nobody re-adds them):
#   "singapore business district"      → 4/4 CC BY-SA, 0 usable
#   "singapore shenton way building"   → 3/4 CC BY-SA + 1 "Copyrighted free use", 0 usable
#   "trading floor london"             → 2/4 CC BY-SA, 2/4 "No restrictions", 0 usable
# Commons has no licence-clean photography of Singapore or of a London trading floor, which is
# why this job uses the Royal Exchange interiors and market charts as plates. If the human
# reviewer wants real Singapore footage, add a PEXELS_API_KEY or PIXABAY_API_KEY secret — those
# providers run before Wikimedia in pipeline/assets.py.
asset_query_verification:
  verified_on: "2026-10-22"
  method: "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-4, filtered by pipeline/assets.py licence rule"
  queries:
    - query: "royal exchange london interior"
      verified: true
      usable: 2
      evidence: "2x CC0 Yale Center for British Art engravings of the Interior of the Royal Exchange, London (John Greig and anonymous); the two 2025 photographs are CC BY-SA and rejected"
    - query: "barings bank"
      verified: true
      usable: 3
      evidence: "PD 'Barings circular letter of credit 1892' + PD Thomas Lawrence 'BaringBaringWall' portrait + PD Ambrose McEvoy 'Messrs Baring Brothers & Co'; the two Baring Road Barclays branch photos are CC BY-SA and rejected (and are the wrong bank anyway)"
    - query: "bond certificate"
      verified: true
      usable: 4
      evidence: "PD NARA war-bond poster 515403 + PD Papal states bond 1817 + 2x CC BY 4.0 museum bond certificates"
    - query: "stock market chart"
      verified: true
      usable: 4
      evidence: "PD Austrian stock market index + CC0 Stock market charts illustration + PD Stock Market April 5 2025 + CC BY 2.0 UK Stock Market"
    - query: "abandoned office room"
      verified: true
      usable: 3
      evidence: "3x Public domain damaged/empty interior photographs; the CC BY-SA 3.0 hit is rejected. Used as a destruction/aftermath mood plate, not as documentary evidence of Kobe"
    - query: "london financial district building"
      verified: true
      usable: 1
      evidence: "PD 'Exterior of 5 Canada Square' passes; the West India Quay / Canada Square photos are CC BY-SA and rejected"
originality:
  original_thesis: true      # argues the cause was the settlement/trading control breach, not one man
  unique_structure: true     # control-first structure: the bank, then the desk, then the hole
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

    1. verified every figure and date against the sources listed in `description` — the Board
       of Banking Supervision inquiry (the Middleton report) is the primary document and
       settles the control-failure narrative;
    2. rewritten the narration in their own words;
    3. flipped `human_rewrite` to `true` and `status` to `approved`.

  That is the human-creative / machine-labour split the whole repo is built on
  (PLAN.md §4.4). Do not flip the flag as a convenience.

  Check these three hardest, because the popular retelling gets them wrong:
    - the loss figure (commonly quoted as about £827 million — confirm against the inquiry);
    - whether the sale to ING was for a nominal £1 and what liabilities came with it;
    - the precise sequence and dates between the Kobe earthquake, the margin calls and the
      declaration of insolvency.
  Do NOT source anything from Leeson's own book beyond sequence; it is a self-interested
  account and the inquiry contradicts parts of it.

  Visual note: Scene 6 uses PD damaged-interior photographs as a mood plate for the Kobe
  earthquake, not as documentary images of it. If that reads as misleading once rendered,
  rewrite the scene to be about the position rather than the earthquake, or replace the plate.
-->

## Scene 1 — The hook
In February nineteen ninety-five, a London bank that had been trading for two hundred and
thirty-three years was declared insolvent. It had financed the American government's purchase
of Louisiana. It had survived wars, revolutions and the financial panic of eighteen ninety,
when it was rescued by a consortium organised by the Bank of England. It was not brought down
by a war or a recession. It was brought down by one junior trader in Singapore, using an error
account numbered eight-eight-eight-eight-eight, and by the fact that nobody in the building
had checked his paperwork for years. The loss was larger than the bank's entire capital. The
question worth asking is not how one man did it. It is how an institution that old let him.

## Scene 2 — The merchant bank
Barings was founded in London in the seventeen-sixties by Francis Baring, and it became the
archetype of the British merchant bank. A merchant bank in that tradition did not take your
savings and lend them out. It dealt in acceptance and credit — it put its name behind other
people's trade, financed governments, and traded on reputation. Its name was the product. In
eighteen hundred and three it helped finance the Louisiana Purchase. In eighteen ninety it very
nearly died, when its exposure to Argentine debt became unpayable; it was saved only because
the Bank of England organised a rescue fund and a new entity took over the good business. So
Barings had already survived one existential crisis, and the memory of it shaped the culture:
a firm built on the idea that its own name was worth more than any single position. That idea
is what made what happened next so strange.

## Scene 3 — The back office
Every trading operation has two halves. The front office makes the bets. The back office
settles them — it confirms what was actually traded, reconciles the cash and the positions, and
tells management what the firm really owns and owes. Those two functions are kept separate for
one reason, and it is not bureaucracy. If the person who makes the trade is also the person who
records whether it made money, then there is no such thing as a check. In Singapore, Barings
put one man in charge of both. He ran the futures trading operation on the floor, and he was
also responsible for settlement. Auditors flagged the arrangement. The concern was raised in
writing. The structure stayed. That single organisational decision is the actual subject of
this story — everything that follows is just what it made possible.

## Scene 4 — Singapore
The trader was Nick Leeson, and by the early nineties he was running Barings' futures business
on the Singapore International Monetary Exchange. The exchange traded futures on the Nikkei
stock index, and Barings was one of the largest players on the floor. The business was
genuinely profitable: arbitrage between the futures price in Singapore and related prices
elsewhere, executed at scale, earning commission and spreads. From London's point of view this
was a star operation, and Leeson was reporting profits that made him look like the best trader
the firm had. Nobody could see the other half of the ledger, because the other half of the
ledger was being written by the same man.

## Scene 5 — Account 88888
Trading desks use error accounts to park mistakes — a trade booked wrongly sits there briefly
until it is corrected. That is normal and it is supposed to be small and short-lived. Leeson
used an error account numbered eight-eight-eight-eight-eight to park losses instead, and then
did not correct them. As losses accumulated, he covered them by taking larger positions, on the
reasoning that a big enough winning trade would erase the hole and nobody would ever have to
look. This is the pattern that destroys trading desks, and it is almost never sophisticated.
The losses were reported away from London by faking documents and by exploiting the fact that
the person reconciling the accounts was also the person creating them. To the head office, the
Singapore operation looked profitable right up until the day it did not exist.

## Scene 6 — Kobe
In January nineteen ninety-five, the Kobe earthquake struck Japan. The disaster killed
thousands, and it hit Japanese markets directly. Leeson's positions were heavily exposed to
Japanese equity prices, and the earthquake made them worse rather than better. His response was
not to close out. It was to increase the bet, in the expectation that Japanese markets would
recover quickly and that the recovery would wipe out the accumulated losses in the error
account. This is the moment where the story stops being about accounting and becomes about
something more familiar and more human. A hole that could have been confessed to at one size
was being defended at a much larger one, and the cost of confessing grew every single day the
position was held.

## Scene 7 — The bank dies
By late February nineteen ninety-five the losses exceeded the entire capital of Barings plc.
The bank could not meet its obligations on the exchange and was declared insolvent. Trading in
its shares was suspended. The parent group put itself into administration, and the business
was ultimately acquired by the Dutch bank ING for a nominal sum, with the liabilities left
behind in the administration to be dealt with separately. Two hundred and thirty-three years of
continuous history ended in a weekend. The official inquiry that followed was unambiguous about
the cause. It did not describe a genius criminal. It described a failure of management, of
internal control, and of supervision — a firm whose board did not understand the exposures it
was carrying, and a regulator that had not required it to.

## Scene 8 — The lesson
Leeson left Singapore before the collapse, was arrested months later, and served a prison
sentence. He has since written and spoken about the episode, and it is worth being careful
about whose account you believe: the man who created the hole has obvious reasons to describe
the controls as worse than they were, and the official inquiry does not accept everything he
says. The finding that matters is not in dispute, though. Barings failed because one person
could both place a trade and record whether it had worked. Every control rule in modern finance
about separating those two jobs exists because of cases like this one. It is a small, boring,
procedural idea, and it is worth more than every warning about rogue traders ever filmed: if
nobody independent is checking the record, the record is not a record. It is a story someone
is telling you.
