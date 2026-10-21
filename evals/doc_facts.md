# Retrieval and agent ground truth (synthetic docs, Aug 2023 to Apr 2026)

Each row: a question, the exact expected answer, and the source file.
Answers were copied from the documents. Re-verify a row after editing
its doc.

Questions name the player or team, never the file. Score the number,
name or date, not the phrasing.

## How each section is scored

| Section | Retrieval test (`tests/test_retrieval.py`) | Agent eval (Friday) |
|---|---|---|
| Core (D) | Source file in the top 3; top-1 rate reported | Final answer contains the expected value |
| Stress (X) | Same | Same; distractors in the same doc must not be chosen |
| Paraphrase (P) | Same, with wording that shares few words with the doc | Same |
| Unanswerable (U) | Not scored. Similarity cannot detect these | Final answer says it is not in the documents |
| Combined (C) | Not scored | Manual rubric: numbers from SQL, context from docs |

## Core questions (one per document)

| ID | Source file | Question | Expected answer | Type |
|----|-------------|----------|-----------------|------|
| D01 | 01_scouting_kael.md | What asking price did FC Kystborg's sporting director indicate for Joren Kael? | €5.4 million | number |
| D02 | 02_briefing_aston_villa.md | What PPDA is Aston Villa described as allowing? | 9.8 | number |
| D03 | 03_memo_expected_threat.md | What new base xT reward applies to a successful byline cut-back? | 0.16 (up from 0.09) | number |
| D04 | 04_scouting_garza.md | What release clause does Garza's agency claim? | $3.2 million | number |
| D05 | 05_briefing_newcastle.md | How many long passes per match does Newcastle's goalkeeper average? | 12.4 | number |
| D06 | 06_memo_sprint_threshold.md | What will the squad's average high-intensity running volume per match become under the new sprint framework? | 1,620 metres (down from 1,850) | number |
| D07 | 07_scouting_leka.md | What transfer fee is FC Dunavska Zora reportedly demanding for Dariusz Leka? | €2.8 million | number |
| D08 | 08_briefing_brighton.md | What vertical progression speed does Brighton average in the initial build-up phase? | 1.4 metres per second | number |
| D09 | 09_scouting_vostrel.md | What percentage of his crosses and shots does Radim Vostrel attempt with his right foot? | 12.4% | number |
| D10 | 10_memo_roster_age.md | What does the average age target for the match day squad drop to? | 25.8 years (down from 26.5) | number |
| D11 | 11_scouting_odegard.md | What release clause can foreign clubs trigger for Stefan Odegard at Fjordvik IF? | €3.8 million | number |
| D12 | 12_briefing_wolves.md | What PPDA is Wolverhampton Wanderers recorded as having? | 16.2 | number |

## Stress tests (distractors exist in other docs)

| ID | Source file | Question | Expected answer | Why it is hard |
|----|-------------|----------|-----------------|----------------|
| X01 | 06_memo_sprint_threshold.md | What is the new sprint speed threshold? | 25.2 km/h | Old value 24.5 km/h is in the same doc |
| X02 | 06_memo_sprint_threshold.md | What is the new acceleration parameter for maximum exertion bursts? | 3.5 m/s² | Old value 3.0 m/s² is in the same doc |
| X03 | 06_memo_sprint_threshold.md | When does the new sprint threshold take effect? | 15 November 2024 | Memo date is 8 November 2024; doc 10 has a similar effective date |
| X04 | 10_memo_roster_age.md | When does the new squad age target take effect? | 10 November 2025 | Doc date is 3 November 2025 |
| X05 | 02_briefing_aston_villa.md | Which opponent favours out-swinging deliveries to the back post on offensive set pieces? | Aston Villa | Back post also appears in the Odegard report (aerial weakness) |
| X06 | 05_briefing_newcastle.md | How many players does Newcastle keep inside the penalty area on defensive corners? | 8 | Zonal marking is mentioned in other context too |
| X07 | 12_briefing_wolves.md | What type of attacking corner routine do Wolves favour? | Short corners | Other briefings describe different set pieces |
| X08 | 04_scouting_garza.md | When does Mateo Garza's contract run until? | December 2026 | Other docs have June 2027/2028/2029 and December 2027 |
| X09 | 03_memo_expected_threat.md | What variance do historical shot-creating actions show for wide players? | 4.3% positive | Doc 03 also cites 0.12 and 0.09 to 0.16 |
| X10 | 08_briefing_brighton.md | What do Brighton's defensive lines do on defensive set pieces? | Step up together as an offside trap | Villa's doc also mentions a high line and offsides |
| X11 | 09_scouting_vostrel.md | What xA per 90 does Radim Vostrel supply? | 0.21 | Doc 04 and 11 have other per-90 stats |

## Paraphrase questions (little shared wording with the docs)

These describe the content without using the document's own phrasing, so
they test meaning-based retrieval and not keyword overlap.

| ID | Source file | Question | Expected answer | Type |
|----|-------------|----------|-----------------|------|
| P01 | 01_scouting_kael.md | What price did the Danish club's sporting director hint at for the 21-year-old holding midfielder? | €5.4 million | paraphrase |
| P02 | 02_briefing_aston_villa.md | Which opponent hunts the ball hardest in the middle third, with a very low PPDA? | 9.8 | paraphrase |
| P03 | 03_memo_expected_threat.md | How was our threat model changed to reward passes cut back from the byline? | 0.16 | paraphrase |
| P04 | 04_scouting_garza.md | How much is the Chilean teenage winger's buyout, according to his representatives? | $3.2 million | paraphrase |
| P05 | 05_briefing_newcastle.md | Which side's goalkeeper avoids short distribution and kicks long under pressure? | 12.4 long passes per match | paraphrase |
| P06 | 06_memo_sprint_threshold.md | What did the department change about how fast a player must run for it to count as a sprint? | 25.2 km/h | paraphrase |
| P07 | 07_scouting_leka.md | Which Bulgarian centre-back wins nearly three quarters of his aerial duels, and what fee is demanded? | €2.8 million | paraphrase |
| P08 | 08_briefing_brighton.md | Which opponent builds up slowly with the goalkeeper involved and invites us to press? | 1.4 metres per second | paraphrase |
| P09 | 09_scouting_vostrel.md | Which Czech winger is weak with his right foot, and what asking price was reported? | €8.5 million | paraphrase |
| P10 | 10_memo_roster_age.md | What is the policy on how old the matchday squad should be on average? | 25.8 years | paraphrase |
| P11 | 11_scouting_odegard.md | Which Norwegian full-back is weak in the air at the back post, and what clause could we trigger? | €3.8 million | paraphrase |
| P12 | 12_briefing_wolves.md | Which opponent sits deep in a low block and commits tactical fouls to stop counter-attacks? | 16.2 | paraphrase |

## Unanswerable (scored on the agent's final answer, not on retrieval)

Expected agent behaviour: say the information is not in the documents.
Do not guess and do not borrow a nearby figure.

Retrieval cannot detect these. Similarity measures topic, not whether the
passage answers the question. In a real run, U01 returned the Kael
report at 0.703, higher than the correct Newcastle match scored for D05
(0.664). So these rows test the agent's instructions, not a score cutoff.

| ID | Question | Retrieval will likely return | Why it is a good trap |
|----|----------|------------------------------|-----------------------|
| U01 | What is Joren Kael's weekly wage? | 01_scouting_kael.md | Doc gives asking price and bid, not wages |
| U02 | What is Newcastle United's PPDA? | 05_briefing_newcastle.md | Doc gives goalkeeper long passes, not PPDA (Villa and Wolves have PPDA) |
| U03 | Who is Dariusz Leka's agent? | 07_scouting_leka.md | Doc cites "intermediary sources" without a name |
| U04 | How many set-piece goals have Wolves scored? | 12_briefing_wolves.md | Doc describes routines, with no goal counts |

## Combined stats + documents questions (for the multi-agent demo)

These need both the SQL tools and the documents. Scored manually or with
a rubric, since the numeric half comes from the database.

| ID | Question | Stats part | Docs part |
|----|----------|------------|-----------|
| C01 | Brighton's 2024/25 away form, and do our notes describe how they build up? | home_away_split / form for Brighton 2024/25 | Doc 08 (back four, double pivot, low vertical speed) |
| C02 | How did Newcastle perform in September 2024, and what did the briefing flag about them? | team results around 12 Sep 2024 | Doc 05 (direct goalkeeper, 8 in the box on corners) |
| C03 | Wolves' 2025/26 goals conceded versus the briefing's description of their shape | team_record Wolves 2025/26 | Doc 12 (back five, PPDA 16.2) |

Verify the matchday and date alignment (see `tests/test_docs.py`) before
you rely on C01 to C03.

## Rules

- Do not write questions about match results; those come from SQL.
- If two docs could answer a question, rewrite it or drop it.
- After any doc edit, re-copy the answer from the text.