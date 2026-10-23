# 0007 — The Day the Exchange Pressed Undo: source dossier

**Story:** the March 2022 nickel squeeze on the London Metal Exchange, and the cancellation of every nickel trade executed on 8 March 2022.
**Compiled:** 23 October 2026. **Status:** research notes for a draft script. Not a fact-check. Every claim below still needs a human tick in `content/factcheck/0007-*.md` before approval.
**Angle:** mechanism, not villain. Three promises stopped being true at once: that the metal you produce is the metal you owe; that the price on your screen is a price you can trade at; that a completed trade is final.

---

## 1. The cast

| Party | Role |
|---|---|
| London Metal Exchange (LME) | The venue. Founded 1877; 145 years old in March 2022. Owned by Hong Kong Exchanges and Clearing (HKEX) since 2012 |
| LME Clear | The clearing house. Stands between buyer and seller; collects margin |
| Tsingshan Holding Group | Chinese stainless-steel and nickel producer. The large short. Chairman Xiang Guangda |
| JPMorgan, BNP Paribas, Standard Chartered, CCB International, UOB, DBS, BOC International, Sucden | Banks and brokers on the other side, and Tsingshan's margin lenders |
| Elliott Associates / Jane Street Global Trading | Traders whose 8 March profits were cancelled. Claimants |
| FCA | UK regulator. Fined the LME in March 2025 |
| Matthew Chamberlain | LME chief executive at the time |
| Adrian Farnham | LME Clear chief executive at the time |

---

## 2. Timeline

| Time | Event | Source |
|---|---|---|
| Fri 4 Mar 2022 | 3M nickel around $30,000/t | Reuters, 8 Mar 2022 |
| Mon 7 Mar | Opens just under $30,000; closes **$48,078** | Court of Appeal judgment, para 2 |
| Tue 8 Mar, 01:00 | LMEselect opens for Asian hours | FCA Final Notice §2.1 |
| 04:49–08:15 | **Price bands suspended continuously for more than three hours** — the LME's only automated volatility controls | FCA Final Notice §2.28 |
| Early hours | 3M nickel peaks at **$101,365/t** (record); most of the rise in little over an hour | FCA §2.2; Reuters |
| 08:15 | Trading suspended on all venues — Notice 22/052 | LME Notice 22/052 |
| 12:05 | All trades executed on or after 00:00 cancelled — Notice 22/053 | LME Notice 22/053; CoA para 3 |
| Same day | Notional value of cancelled trades: **$13.373bn** | FCA Final Notice §4.105 |
| Mon 14 Mar | Tsingshan announces **standstill** with banks: no close-outs, no further margin calls | Reuters, 14 Mar 2022 |
| 15 Mar | LME announces reopening 16 Mar, 5% nickel limit | LME Notice 22/067 |
| Wed 16 Mar, 08:00 | Reopens at 5% limit ($45,590). Price falls immediately. Systems error lets trades through below the limit. Halted within seconds after **206 lots / 1,236 tonnes** | Reuters; Fortune; LME Notice 22/070 |
| 16 Mar, 14:00 | Electronic trading reopens | Reuters |
| 17 Mar | Limit widened to 8%; limit down | CNBC; Wikipedia summary |
| 18 Mar | Limit widened to 12%; limit down | Wikipedia summary |
| Mar 2023 | Nickel finally reopens in Asian hours | FCA Final Notice §2.3 |
| 29 Nov 2023 | Divisional Court dismisses Elliott and Jane Street — [2023] EWHC 2969 (Admin) | LME litigation page |
| 7 Oct 2024 | Court of Appeal dismisses appeal — [2024] EWCA Civ 1168 | LME litigation page |
| 29 Jan 2025 | Supreme Court refuses permission to appeal | LME litigation page |
| 19 Mar 2025 | FCA fines LME **£9,245,900** (30% discount; otherwise £13,208,400) | FCA Final Notice §1.1–1.2 |

---

## 3. The three failures the script is built on

### 3.1 The metal you produce is not the metal you owe
Reuters, 16 March 2022: *"The LME only accepts nickel cathodes, pellets, briquettes and rounds for physical delivery, while Tsingshan's products nickel pig iron and nickel matte — an intermediate product that can be used in both stainless steel and batteries — cannot be traded on the exchange."*

This is the mechanism. Tsingshan produced nickel, but not the deliverable kind. A short futures position is a promise about a specified deliverable. When the price ran, the position had to be closed in cash rather than settled in metal — which is exactly what turns a producer's hedge into a scramble.

**Careful:** Tsingshan described the positions as hedges. Do not call them a naked speculative bet without attribution. Reuters reported its bets had amounted to around 300,000 tonnes at an average of $18,000–$19,000; Bloomberg reported over 150,000 tonnes at the time of the halt. Both figures are reported, not disclosed.

### 3.2 The price on screen was not a tradable price
FCA §2.28: the operation of the price bands was suspended continuously for more than three hours, from 4.49am to 8.15am. §2.11: in 2021 the trading operations team had already flagged in an internal incident report its practice of suspending the bands during high volatility — and the risks that followed.

FCA §2.10: when the bands appeared to be inhibiting "genuine" trades, the team would override or disapply them, and on some occasions suspend their operation altogether, without consulting senior management and without specific training.

The bands were designed under MiFID II as automatic volatility controls. The LME treated them in practice as error-trade controls (FCA §2.7).

### 3.3 A completed trade is not final
LME Rule TR22 (referred to in the judgments as Rule 22 / TR22) permits the exchange to cancel or vary an agreed trade where it considers it appropriate. The Divisional Court and Court of Appeal both held the power existed and was lawfully used.

LME Notice 22/057: cancellations were made "in order to take the market back to the last point in time at which the LME could be confident that the market was operating in an orderly way."

---

## 4. The size of what was avoided

- The LME's own account: had the 8 March prices stood, the market faced a **$19.75bn margin call**, about ten times the previous record; at least **seven clearing members** would have gone into default; LME Clear's chief executive described the potential for a "death spiral." (Reported by Mining.com/Bloomberg, 28 Nov 2022.)
- OFR working paper (2024): the margin calls threatened to put **12 of 45 clearing members** into default and exhaust the default fund; the cancellation covered **eight hours** of trades, **5,000–9,000** trades.
- Elliott's claim: **$456m** of lost net profit. Jane Street: **$15.3m**.

**Do not** present the $19.75bn as an independently audited figure. It is the exchange's own account of what it avoided.

---

## 5. What the courts actually decided

- Divisional Court, 29 Nov 2023: dismissed on all grounds; the decision was lawful, rational and within the rules. The LME was not required to consult traders first.
- Court of Appeal, 7 Oct 2024: dismissed. Males LJ: the price move was "a once-in-a-generation event"; to have allowed the trades to stand "would have meant a real risk of what has been graphically described as a 'death spiral'"; the LME had "effectively no choice."
- Notable nuance: the Court of Appeal **accepted** that Elliott's agreed trades were "possessions" under Article 1 of Protocol 1 ECHR — reversing the Divisional Court on that point — but held there was no unlawful interference because the right to cancel was built into the rules the parties traded under.
- Supreme Court, 29 Jan 2025: permission to appeal refused.

**The precise holding:** the cancellation was lawful because the power to cancel was in the contract. Not because it was wise, and not because the systems worked.

---

## 6. What the regulator found

FCA Final Notice 207387, 19 March 2025. Penalty £9,245,900 after a 30% stage-1 discount; otherwise £13,208,400.

Findings, in the FCA's words:
- The LME's policies, controls and training had not sufficiently catered for the risks to market orderliness presented by extreme volatility, over 3 January 2018 – 8 March 2022 (§2.4).
- The prevailing philosophy was that trading and price discovery should not be restricted even in extreme volatility unless the market became disorderly — but the LME failed to implement written policies or train front-line staff to recognise a disorderly market, or to escalate (§2.4).
- Price bands were treated as a control against error trades and rogue algorithms, not as part of the controls for severe market stress (§2.7).
- Seven of nineteen daily trading hours were managed overnight in Hong Kong, making the risk of non-escalation "acute" (§2.8).
- The LME told the market nothing about its static price bands, and they went "almost unmentioned" in internal operational manuals, despite an explicit regulatory obligation to publish them (§2.9).
- The price bands were suspended for more than three hours on the morning of 8 March (§2.28).
- Reported by Reuters as the FCA's **first ever enforcement action against a UK exchange**.

**Do not say** the FCA found the cancellation itself was wrong. It did not. It found the controls and escalation around the market were inadequate. That distinction is the spine of Scene 8.

---

## 7. The Tsingshan resolution

- 14 March: standstill — banks agree not to close out positions or make further margin calls; a standby secured liquidity facility to be negotiated (Reuters).
- Tsingshan agreed to reduce the position in an orderly manner as abnormal conditions subsided (company statement via Reuters/S&P Global).
- JPMorgan took a **$120m provision** for a loss from the nickel crisis in April 2022 (Reuters).
- Estimated loss on the trade: around **$1bn** (people familiar, via Bloomberg/Fortune/Straits Times). Position cut from over 150,000 tonnes to under 20,000 tonnes by end-June 2022.
- Reuters calculated that at the raised margin rate of $2,250/t, 300,000 tonnes would require **$675m** of capital — before the price moved.

**Careful:** the $1bn loss figure is an estimate from unnamed sources. Attribute it.

---

## 8. What the script should NOT claim

- That Tsingshan was "the" cause. It was a large short in a market already repricing on Russia's invasion of Ukraine. The Court of Appeal said the cause was not known at the time; a later investigation suggested large short positions built up by a number of market participants.
- That the LME "stole" the trades. The courts held the cancellation was lawful under the rules.
- That the cancellation "saved the system" as established fact. That is the LME's account of what it avoided.
- That the FCA fine proves the cancellation was unlawful. It does not.
- Any specific figure for Tsingshan's position as a disclosed fact. All position figures are reported estimates.

---

## 9. Source register

**Primary**
1. LME Notice 22/052, *Suspension of LME Nickel Market*, 8 March 2022. https://www.lme.com/-/media/Files/News/Notices/2022/03/TRADING-22-052-SUSPENSION-OF-LME-NICKEL-MARKET.pdf
2. LME Notice 22/053, *Nickel Suspension — Further Information: Delivery Deferral and Trade Cancellation*, 8 March 2022. https://www.lme.com/-/media/Files/News/Notices/2022/03/22-053-Nickel-Suspension---Further-Information---Delivery-Deferral-and-Trade-Cancellation.pdf
3. LME Notice 22/057, explanation of the suspension and cancellation decisions, 8 March 2022. https://www.lme.com/api/sitecore/MemberNoticesSearchApi/Download?id=7f00b96e-136a-4896-9a43-f57e671dffea
4. LME Notice 22/067 / 22/070, reopening and official prices, 16 March 2022. https://www.lme.com/-/media/Files/News/Notices/2022/03/TRADING-22-070-Nickel-Official-Prices.pdf
5. LME Notice 22/099, interim trading measures and independent review, 4 April 2022. https://www.lme.com/-/media/Files/News/Notices/2022/04/TRADING-22-099-NICKEL-INTERIM-TRADING-MEASURES-AND-INDEPENDENT-REVIEW.pdf
6. FCA Final Notice 207387, *The London Metal Exchange (RIE)*, 19 March 2025. https://www.fca.org.uk/publication/final-notices/london-metal-exchange-2025.pdf
7. *Elliott Associates L.P. and Elliott International L.P. v London Metal Exchange and LME Clear* [2024] EWCA Civ 1168, 7 October 2024. https://www.lme.com/-/media/Files/News/R-Elliott-Associates-v-London-Metal-Exchange-final-judgment.pdf
8. Divisional Court, [2023] EWHC 2969 (Admin), 29 November 2023.
9. LME, *LME nickel litigation* — case status and Supreme Court refusal, 29 January 2025. https://www.lme.com/en/lme-nickel-litigation

**Secondary (reported, attribute in narration)**
10. Reuters, *LME forced to halt nickel trading, cancel deals, after prices top $100,000*, 8 March 2022.
11. Reuters, *China's Tsingshan fires nickel rally as it cuts costly exposure*, 8 March 2022.
12. Reuters, *China's Tsingshan agrees standstill agreement on LME nickel margins with banks*, 14 March 2022.
13. Reuters, *Tsingshan inks deals to swap nickel products for LME delivery*, 16 March 2022 — the deliverability detail.
14. Reuters, *Nickel market in disarray after chaotic London return*, 16 March 2022.
15. Reuters, *Hedge fund Elliott loses appeal against dismissal of LME nickel lawsuit*, 7 October 2024.
16. Reuters, *Hedge fund Elliott says it may take further action on LME voided nickel trades*, 24 March 2025.
17. Bloomberg, *Nickel Reopens Limit-Down in a Shambolic Day of False Starts*, 16 March 2022.
18. Fortune, *'What a debacle': Nickel trading stops just minutes after reopening as prices plunge*, 16 March 2022.
19. CNBC, *Systems error triggers fresh chaos as LME suspends nickel trading once again*, 16 March 2022.
20. Mining.com / Bloomberg, *LME says it saved nickel market from $20 billion 'death spiral'*, 28 November 2022.
21. Office of Financial Research, *Central Clearing and Trade Cancellation: The Case of LME Nickel Contracts on March 8, 2022*, working paper 24-09, 2024. https://www.financialresearch.gov/working-papers/files/OFRwp-24-09_central-clearing-and-trade-cancellation.pdf
22. BBC, *London Metal Exchange sued for $456m over cancelled nickel trades*, June 2022.
23. Bloomberg / Fortune / Straits Times, Tsingshan loss estimate around $1bn, July 2022.

**Limits recorded:** position sizes, the $1bn loss, the $19.75bn avoided margin call and the "seven clearing members" figure are all reported or self-reported, not disclosed. Price-band times and the $13.373bn notional come from the FCA. The reopening sequence comes from contemporaneous reporting, not from a single official account.
