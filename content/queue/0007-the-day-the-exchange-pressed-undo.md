---
id: "0007"
title: "The Day the Exchange Pressed Undo: Nickel, $13 Billion and the Trades That Never Happened"
slug: the-day-the-exchange-pressed-undo
status: draft             # DRAFT — awaiting human fact-check before approval (see originality note)
format: longform          # longform | short
niche: finance and business
category: education
voice: en-US-ChristopherNeural
target_minutes: 21
tags: [london metal exchange, nickel squeeze, tsingshan, commodity markets, market microstructure, clearing, financial regulation]
thumb_text: "THE EXCHANGE PRESSED UNDO"
description: |
  On the morning of 8 March 2022, the price of nickel on the London Metal Exchange passed
  one hundred thousand dollars a tonne. By eight fifteen the market was shut. By midday the
  exchange had cancelled every nickel trade executed that day: a notional thirteen point
  three seven three billion dollars, voided in a single decision.

  This documentary reconstructs what happened, using the exchange's own notices, the
  regulator's final notice, the Court of Appeal judgment, and contemporaneous reporting. It
  asks a narrower question than the headlines did. Not who was to blame, but which of the
  assumptions a modern market runs on stopped being true, and in what order.

  Sources (human verification still required before approval):
  - London Metal Exchange (2022). Notice 22/052, Suspension of LME Nickel Market, 8 March.
    https://www.lme.com/-/media/Files/News/Notices/2022/03/TRADING-22-052-SUSPENSION-OF-LME-NICKEL-MARKET.pdf
  - London Metal Exchange (2022). Notice 22/053, Delivery Deferral and Trade Cancellation, 8 March.
    https://www.lme.com/-/media/Files/News/Notices/2022/03/22-053-Nickel-Suspension---Further-Information---Delivery-Deferral-and-Trade-Cancellation.pdf
  - London Metal Exchange (2022). Notice 22/070, Nickel Official Prices, 16 March.
    https://www.lme.com/-/media/Files/News/Notices/2022/03/TRADING-22-070-Nickel-Official-Prices.pdf
  - Financial Conduct Authority (2025). Final Notice 207387, The London Metal Exchange, 19 March.
    https://www.fca.org.uk/publication/final-notices/london-metal-exchange-2025.pdf
  - Elliott Associates L.P. and others v London Metal Exchange and LME Clear [2024] EWCA Civ 1168.
    https://www.lme.com/-/media/Files/News/R-Elliott-Associates-v-London-Metal-Exchange-final-judgment.pdf
  - London Metal Exchange. LME nickel litigation — case status, 29 January 2025.
    https://www.lme.com/en/lme-nickel-litigation
  - Office of Financial Research (2024). Central Clearing and Trade Cancellation, working paper 24-09.
    https://www.financialresearch.gov/working-papers/files/OFRwp-24-09_central-clearing-and-trade-cancellation.pdf
  - Reuters (2022). LME forced to halt nickel trading, cancel deals, 8 March.
    https://www.reuters.com/markets/commodities/lme-suspends-nickel-trading-after-prices-top-100000-2022-03-08/
  - Reuters (2022). China's Tsingshan agrees standstill agreement on LME nickel margins, 14 March.
    https://www.reuters.com/markets/commodities/chinas-tsingshan-agrees-standstill-agreement-lme-nickel-margins-with-banks-2022-03-14/
  - Reuters (2022). Tsingshan inks deals to swap nickel products for LME delivery, 16 March.
    https://www.reuters.com/markets/commodities/tsingshan-inks-deals-swap-nickel-products-lme-delivery-2022-03-16/
  - Reuters (2022). Nickel market in disarray after chaotic London return, 16 March.
    https://www.reuters.com/markets/commodities/nickel-market-disarray-after-chaotic-london-return-2022-03-16/
  - Mining.com / Bloomberg (2022). LME says it saved nickel market from $20 billion death spiral, 28 November.
    https://www.mining.com/web/lme-says-it-had-regulatory-obligation-to-shut-nickel-market/

  A money story, not money advice. No picks, no predictions — just the record.
research_notes: content/research/0007-nickel-squeeze-dossier.md
# One query per scene, in scene order (tests assert the coverage).
asset_queries:
  - "london metal exchange"            # S1 the venue and the halt
  - "nickel ore"                       # S2 what the contract delivers
  - "warehouse metal storage"          # S3 warrants and physical delivery
  - "steel mill factory"               # S4 stainless steel demand
  - "smelting furnace molten metal"    # S5 nickel pig iron, Indonesia
  - "commodity price chart"            # S6 Monday's close
  - "financial district night city"    # S7 the overnight session
  - "stock exchange trading pit"       # S8 the suspension
  - "bond certificate"                 # S9 the cancellation
  - "gold bullion bars"                # S10 margin and clearing
  - "newspaper headlines"              # S11 the reopening chaos
  - "royal courts of justice london"   # S12 the courts
  - "press conference microphones"     # S13 the regulator
  - "abandoned office room"            # S14 verdict
# Every query above was probed against the Commons search API on 2026-10-23 and
# scored with pipeline/assets.py::licence_ok_for_monetized_use. Evidence per query
# is recorded in the block below; a zero-usable query was replaced, not shipped.
asset_query_verification:
  verified_on: "2026-10-23"
  method: "commons.wikimedia.org/w/api.php generator=search filetype:bitmap top-6, filtered by pipeline/assets.py licence rule"
  queries:
    - query: "london metal exchange"
      verified: true
      usable: 4
      evidence: "PD 'LME History' plate + CC BY 2.0 '10 Finsbury Square' + CC BY 2.0 'Inauguracion de la nueva sede' + CC BY 3.0 'LME entrance sign'; the CC BY-SA 3.0 entrance photo and the CC BY-SA 2.0 portrait of Martin Abbott are rejected. The original 'london metal exchange trading floor' returned only those two rejects"
    - query: "nickel ore"
      verified: true
      usable: 4
      evidence: "CC0 'Nickel Ore Assay Sheet' + PD 'World Nickel Production 1946' + 2x CC BY 3.0 CSIRO ScienceImage ore photographs; the two CC BY-SA 4.0 ore close-ups are rejected. The more obvious 'nickel metal' returned six Ni-MH battery photographs, all CC BY-SA, i.e. zero usable"
    - query: "warehouse metal storage"
      verified: true
      usable: 4
      evidence: "PD NPS Grand Canyon warehouse + CC0 Mazatlan metal sheds + 2x Public domain EFTA warehouse interiors; the CC BY-SA geograph and Cairo hits are rejected"
    - query: "steel mill factory"
      verified: true
      usable: 5
      evidence: "CC0 Geneva Steel 1942 + PD Pittsburgh/Monessen blast furnace + PD Western Steel Mill 1910 + CC BY 3.0 Cascade Steel + CC BY 4.0 Worcester Pressed Steel; the CC BY-SA geograph mill is rejected"
    - query: "smelting furnace molten metal"
      verified: true
      usable: 4
      evidence: "4x Public domain: Trumbull-Cliffs ladle, DPLA molten-iron pour, Trumbull-Cliffs chimney valves, DPLA tapping open-hearth furnaces; the CC BY-SA hits are rejected"
    - query: "commodity price chart"
      verified: true
      usable: 6
      evidence: "3x CC0 commodity-price charts + PD gold price 1979-2013 + 2x CC BY 4.0 OWID metals price indices"
    - query: "financial district night city"
      verified: true
      usable: 6
      evidence: "1x CC0 Unsplash diner sign + 5x CC BY 2.0 Toronto financial district night photographs"
    - query: "stock exchange trading pit"
      verified: true
      usable: 4
      evidence: "PD 'In the wheat pit of the Board of Trade of the city of Chicago' (jpg + tif) + PD 'Other people's money' theatre poster (jpg + tif); 'No restrictions' is not an accepted string"
    - query: "bond certificate"
      verified: true
      usable: 6
      evidence: "PD Austrian war bond + PD Papal States bond 1817 + PD Prussia bond 1927 + PD NARA war-bond poster + 2x CC BY 4.0 museum bond certificates"
    - query: "gold bullion bars"
      verified: true
      usable: 5
      evidence: "CC0 chip gold bar + CC0 'Gold bullion bars' + PD 'Gold Ingots on white background' + PD Menendez gold bar + CC BY 4.0 Banque de France ingot; 'bank vault gold bars' returned six CC BY-SA photographs, i.e. zero usable"
    - query: "newspaper headlines"
      verified: true
      usable: 4
      evidence: "PD 1918 Chicago influenza front page + PD Everett massacre headline + PD NARA Japanese relocation headlines + CC BY 2.0 newspaper stack; the CC BY-SA front pages are rejected"
    - query: "royal courts of justice london"
      verified: true
      usable: 1
      evidence: "CC0 'Royal Courts of Justice 2019' is the only usable hit; the CC BY-SA 4.0 2022 detail shots and the CC BY-SA 2.0 geograph view are rejected. Thin but sufficient for a two-shot scene"
    - query: "press conference microphones"
      verified: true
      usable: 4
      evidence: "CC BY 2.0 'News Microphones at Press Conference' + CC BY 3.0 McBride sentencing press conference + 2x Public domain Johanna Lawrenson press conference. Chosen after 'canary wharf london' returned six CC BY-SA photographs, i.e. zero usable"
    - query: "abandoned office room"
      verified: true
      usable: 3
      evidence: "2x Public domain (EFTA dark abandoned room, 'The abandoned room' plate) + CC BY 2.0 Mudna House blackboard room; 'trading floor empty' returned irrelevant hits and was dropped"
originality:
  original_thesis: true      # argues the failure was three broken promises, not one villain
  unique_structure: true     # mechanism-first: deliverability, then price, then finality
  human_rewrite: false       # *** FALSE ON PURPOSE *** facts not yet human-verified — gate must block
  no_ai_persona: true        # documentary narration; no advisor persona, no recommendations
  source_notes: true         # sources listed in description
  ai_disclosure: false       # narration is synthetic voice; no photorealistic synthetic media
---

## Scene 1 — Eight fifteen

On the morning of the eighth of March, two thousand and twenty-two, a price appeared on a screen in London that should not have been possible.

Nickel, an industrial metal used in stainless steel and electric-car batteries, had closed the previous evening at forty-eight thousand and seventy-eight dollars a tonne. That was already a record. By the early hours of Tuesday it had passed one hundred thousand. At its peak the screen showed one hundred and one thousand, three hundred and sixty-five dollars.

Then, at eight fifteen, the London Metal Exchange stopped. Not the price. The market. Every venue, every contract, every screen, switched off.

Later that day the exchange went further and cancelled every nickel trade executed since midnight. Not unwound. Not settled at a reference price. Cancelled, as though they had never been agreed.

The notional value of those trades was thirteen point three seven three billion dollars. It is, as far as anyone can establish, the largest cancellation of executed trades in the history of a modern exchange.

This is how that became the least bad option — and what it revealed about the promises a market makes to the people who use it.

## Scene 2 — What an exchange actually sells

The London Metal Exchange is not a stock market. Nobody is buying a share of a company. What it sells is narrower and more useful: a standardised promise about a specific quantity of a specific metal, delivered to a specific place, at a specific date.

For nickel, the contract is six tonnes. The metal that counts is defined in the rulebook: cathodes, pellets, briquettes and rounds. Not any nickel. Those forms, in approved warehouses, against recognised documents.

Uniformity is the product. A buyer need not inspect the metal, because the contract says exactly what will arrive. A seller need not find a buyer, because the exchange stands in the middle.

The exchange also sells a price. Every day it produces official prices used not only by traders but by physical industry, by lenders, by anyone who needs to value nickel.

And it sells finality. When a trade matches, it is done. That is the assumption under every hedge, every loan secured against inventory, every risk system in the market. You can lose money on a trade. You are not supposed to have the trade removed.

By the end of the first week of March, all three promises were about to break, in that order.

## Scene 3 — Why anyone would be short

In early twenty twenty-two, nickel was tight. Stainless steel production was recovering and battery makers were competing for the same material. Inventories in exchange warehouses were low, which meant very little metal was sitting around to absorb a shock.

Then, on the twenty-fourth of February, Russia invaded Ukraine. Russia was a significant supplier of refined nickel of the kind the exchange accepts. Sanctions, payment disruption and shipping uncertainty hit a market already short of slack.

On Friday the fourth of March, three-month nickel traded around thirty thousand dollars a tonne.

Rising prices are a problem for anyone who has sold forward. A producer expecting to dig nickel out next year might sell a futures contract today to lock in a price. That is a hedge, and it is the ordinary business of a commodity market. If the price falls, the producer loses on the futures and gains on the physical metal.

Unless the producer cannot deliver the metal the contract specifies. Then the hedge is not a hedge. It is a short position with a maturity date, and the only way out is to buy back at whatever the market demands.

## Scene 4 — The wrong kind of nickel

The company at the centre of this story was Tsingshan Holding Group, one of the largest nickel producers in the world. Its chairman, Xiang Guangda, built it on nickel pig iron, a cheaper grade used in stainless steel, and later added matte, an intermediate that can feed either steel or batteries.

Tsingshan produced enormous quantities of nickel, but not, in comparable quantities, the refined forms the London contract requires.

This is the hinge of the episode. Being short on a futures exchange is not a statement about the metal in general. It is a promise to hand over cathodes, pellets, briquettes or rounds at a stated date. If you cannot, you must close the position in cash — which means buying back the contract at the market price.

Reuters reported Tsingshan's nickel bets had at one stage amounted to around three hundred thousand tonnes at an average of eighteen to nineteen thousand dollars a tonne; other reporting put the position above one hundred and fifty thousand tonnes at the time of the halt. The company described them as hedges of its production. Hedge or not, the arithmetic was the same: as the price rose the position demanded more cash, and there was no warehouse of deliverable metal to make it good.

One more number matters. The exchange had raised its margin requirement on nickel by twelve and a half per cent, to two thousand two hundred and fifty dollars a tonne. Reuters calculated that a three hundred thousand tonne position would need six hundred and seventy-five million dollars of capital against it — before the price moved at all.

## Scene 5 — Monday

Monday the seventh of March was the day the market stopped pretending.

Nickel opened a little under thirty thousand dollars and closed at forty-eight thousand and seventy-eight. More than sixty per cent in a single session. In a market where warehouses were already depleted, that was a move that forced every short to find collateral at once.

Margins are the mechanism. Every participant posts collateral against their position, recalculated as the price moves. If the price moves against you, you get a call: post more money, or have the position closed. A margin call is not a punishment. It is the plumbing that stops one failure becoming everyone's failure.

But plumbing has a capacity, and it is tested by people who cannot post collateral fast enough.

That evening the clearing house recalculated margins on the closing prices. By then, the number of participants who would need very large sums by the next morning was no longer hypothetical.

## Scene 6 — The overnight session

The exchange trades through LMEselect, which opens at one in the morning London time for the Asian session. Seven of its nineteen daily trading hours are managed overnight from Hong Kong, where its parent company is based.

To understand what happened next, you need the price bands. The exchange operated automated limits that stopped a trade executing outside a range from the previous price. The regulator later found it used them as a guard against mistyped orders and runaway algorithms, not as a tool for a market in severe stress — an error-trade control wearing the clothes of a volatility control.

And on the morning of the eighth of March they were not running.

The Financial Conduct Authority's final notice records that the bands were suspended continuously for more than three hours, from four forty-nine until eight fifteen. In that window nickel ran from forty-eight thousand and seventy-eight dollars to a peak of one hundred and one thousand, three hundred and sixty-five, most of it in little more than an hour.

The regulator found something more uncomfortable. In twenty twenty-one the exchange's trading operations team had flagged in an internal report that it routinely suspended the bands during high volatility, and noted the risks. The practice continued. On some occasions the team overrode the bands when they appeared to block what it regarded as genuine trades, without consulting senior management and without specific training.

So the control existed, on paper. It had been switched off by people with the authority to switch it off, and no written instruction about when they should not.

## Scene 7 — The suspension

At eight fifteen the exchange suspended nickel trading on all venues. Notice twenty-two slash fifty-two is short and flat: the suspension took effect at eight fifteen London time, margin would be calculated on the previous day's closing prices, electronic trading was disabled.

The last price before the halt was around eighty thousand dollars a tonne. Three hours earlier it had been under fifty. An hour before, above a hundred.

The suspension is the part most easily misunderstood. The exchange did not stop because the price was too high in some abstract sense. It stopped because it could not answer a simpler question: at what price should the next trade clear? When a market moves that far, that fast, the orders on the book stop describing a market and start describing a queue of people trying to escape. A matching engine will match them happily. Whether the prices mean anything is another question.

By then the damage was not in the price. It was in the obligations. Positions had been struck at prices that no longer reflected any plausible view of nickel's worth, and those positions now had to be margined in cash by the following morning.

That was the problem. Not a number on a screen. A settlement.

## Scene 8 — Five past midday

At five past midday the exchange took the second decision, and it is the one that made the episode legally historic.

Notice twenty-two slash fifty-three cancelled every nickel trade executed on or after midnight that morning. All of them.

The Financial Conduct Authority put the notional value at thirteen point three seven three billion dollars. The Office of Financial Research, in a paper published two years later, counted somewhere between five thousand and nine thousand trades across roughly eight hours of the overnight session.

Three figures for this circulate in reporting. Early coverage cited three point nine billion dollars. Some litigation summaries used twelve billion. They are not competing estimates of one thing; they measure different slices of a complicated book. The regulator's figure is the one to hold, because it is attached to a formal finding with a defined scope.

The exchange's stated reason, in its own notices, was to take the market back to the last point at which it could be confident the market had been operating in an orderly way. It was not a rescue of any one participant. It was a decision that the overnight prices were not prices, and that contracts struck at them should not be honoured.

The traders on the other side saw it differently. They had dealt at prices the exchange's own system accepted, some were already counting the profits, and now they were told the trades had not happened.

## Scene 9 — What the exchange says it avoided

One number explains, though it does not justify, the decision. It comes from the exchange itself, and it is an account of what was avoided, not an audited fact.

The exchange said that if the eighth of March prices had stood, the market faced a margin call of nineteen point seven five billion dollars — roughly ten times the previous record. It said at least seven clearing members would have gone into default. The chief executive of its clearing house described the potential for what he called a death spiral: a member fails, the default fund is drawn, other members are asked to replenish it, and the replenishment triggers further failures.

The Office of Financial Research's independent reconstruction is consistent with that shape. It found the margin calls threatened to push twelve of the forty-five clearing members into default and to exhaust the default fund.

This is where the moral arithmetic gets hard. A clearing house that lets a member fail is doing its job; one that lets seven fail at once is doing something else. The exchange was not choosing between honouring trades and breaking them, but between breaking them and discovering live what happens when margin cannot be met.

That does not make the decision correct. It makes it a decision taken under a constraint — which is harder to be self-righteous about.

## Scene 10 — The standstill

The cancellation did not solve the underlying problem. It bought time.

On the fourteenth of March, six days after the halt, Tsingshan reached a standstill with its banks. They agreed not to close out the company's positions and not to make further margin calls, and to negotiate a secured liquidity facility behind the position. That is extraordinary in a market meant to resolve itself through margin: in effect, a private agreement to stop the clock until the price came down.

Tsingshan also began arranging to swap some of its nickel products into forms the exchange would accept for delivery. That closes the loop on Scene Four. The company's problem was never that it lacked nickel. It lacked the right nickel.

JPMorgan, exposed to the trade, took a one hundred and twenty million dollar provision for losses in April. Estimates of Tsingshan's own loss, from people familiar with the matter, put it around one billion dollars, and its position was reported cut from over one hundred and fifty thousand tonnes to under twenty thousand by the end of June.

None of those position numbers are disclosed facts. They are reports, and should be described that way.

## Scene 11 — The reopening

Nickel reopened on the sixteenth of March at eight in the morning, with a five per cent price limit. It did not go well.

The exchange fixed an opening price of forty-five thousand, five hundred and ninety dollars. Trading began, prices fell to the limit, and a systems error then allowed a small number of trades below it — two hundred and six lots, one thousand two hundred and thirty-six tonnes. The market was halted again, having allowed on its first morning back the exact trade its rules were built to prevent.

Trading resumed at two in the afternoon. The limit was widened to eight per cent the next day and twelve per cent the day after, and both days closed limit-down. The mechanism spent its first week as a one-way valve: prices could only move the way the market wanted.

The most striking consequence took longer to show. The exchange did not restore nickel trading during Asian hours until March twenty twenty-three. A full year. For twelve months the London nickel price was set only in a window that excluded the part of the world producing and consuming most of the metal.

That is the cost of an administrative fix. The cancellation resolved the settlement problem on the eighth of March. It did not restore a market. It replaced a broken price with a thinner one.

## Scene 12 — The courts

The traders whose profits were cancelled went to court.

Elliott Associates and Jane Street Global Trading brought judicial review, claiming four hundred and fifty-six million and fifteen point three million dollars in lost net profit respectively. Their argument, in essence: the exchange had expropriated the value of completed trades, and a private rulebook could not authorise that.

The Divisional Court dismissed the claims in November twenty twenty-three, holding the decision lawful and within the rules. The Court of Appeal dismissed the appeal in October twenty twenty-four.

The judgment is unusually direct about the constraint. Lord Justice Males described the price move as a once-in-a-generation event. To let the trades stand, he said, would have meant a real risk of what had been described as a death spiral, and the exchange had, in his words, effectively no choice.

The court also made a finer point. It accepted the trades were possessions under the European Convention on Human Rights, reversing the lower court, but held there was no unlawful interference, because the right to cancel was built into the rules under which the trades were made. The traders had not been deprived of property the rules protected. They had lost a benefit those rules let the exchange remove.

The Supreme Court refused permission to appeal on the twenty-ninth of January twenty twenty-five. That is where the legal question ended: the cancellation was lawful because the power to cancel was in the contract. Not because the morning was handled well, and not because the systems worked.

## Scene 13 — The regulator

Four years later, in March twenty twenty-five, the Financial Conduct Authority fined the London Metal Exchange nine million, two hundred and forty-five thousand, nine hundred pounds. Discounted by thirty per cent for early settlement; without it, thirteen million, two hundred and eight thousand, four hundred.

It was reported as the first enforcement action the regulator had ever brought against a UK exchange.

The findings matter more than the fine, and they are narrower than the headlines. The regulator did not find the cancellation wrong. It found the exchange's policies, controls and training had not sufficiently catered for the risks extreme volatility posed to market orderliness, between January twenty eighteen and the eighth of March twenty twenty-two. The prevailing philosophy — that trading and price discovery should not be restricted even in extreme volatility, unless the market became disorderly — had never been translated into written policy, or into training that would let front-line staff recognise a disorderly market or escalate one.

It found the price bands were treated as a defence against error trades rather than controls for severe stress; that seven of nineteen trading hours ran overnight from Hong Kong, making non-escalation acute; and that the exchange told the market nothing about its static price bands, which went almost unmentioned in its own manuals despite an explicit obligation to publish them.

That is a regulator saying: the outcome may have been the least bad available, and you were still not ready for it.

## Scene 14 — Three promises

So what actually broke on the eighth of March?

First, the promise that the metal you produce is the metal you owe. Tsingshan was one of the largest nickel producers alive and could not deliver against its own short. The contract was never about nickel in general but about a defined deliverable, and the gap between the two is where the squeeze lived.

Second, the promise that the price on your screen is a price you can trade at. For three hours and twenty-six minutes the exchange's only automated volatility control was switched off, by staff who had done it before and had flagged the risks a year earlier. A hundred and one thousand dollars happened because nothing was there to stop it.

Third, the promise that a completed trade is final. It is final until the exchange decides otherwise, and the rules let the exchange decide. The Court of Appeal confirmed that is not a loophole; it is the architecture. Finality on a clearing house is a promise made by a private rulebook, enforced by a regulator, and revocable by whoever wrote it.

None of that makes the exchange a villain. It made a decision under a constraint most of us will never face, and a court found it lawfully entitled to make it. What the episode shows is more uncomfortable than malfeasance: a system working exactly as designed, with a gap in the design, found on the morning it mattered.

The most expensive thing in the story was not the thirteen billion dollars of cancelled trades. It was the year in which the world's benchmark nickel price was set without the world's largest nickel market in the room.

A money story, not money advice. No picks, no predictions — just the record.
