# ASTRA 6 — FINAL MASTER PROMPT V3.3 — SAVED SPECIFICATION

Saved at the start of V3.3 work (2026-11-08) so that work can resume after a model/session interruption.
This document records every requirement of the V3.3 prompt. Sections follow the original numbering.

## 0. Role / objective
- Work inside the EXISTING ASTRA 6 project (`/Users/mangtay/qt_test`, repo `EdipMangtay/quantitative_for_Quarterly_theroy_mmxm_crt_ict-`).
- Input: populated workbook `Copy of EXCEL_TEST.xlsx` (repo root).
- Understand the methodology in the workbook, compare it with ASTRA 6, correct logical/architectural differences,
  run corrected research on EXISTING data only, produce a comprehensive TURKISH report.
- Logical reconstruction task, NOT data acquisition. Do not rebuild from scratch. Preserve verified functionality.
- Do not optimise toward the manual performance. Report evidence honestly.

## 1. ABSOLUTE DATA RESTRICTION (overrides everything)
- NO new historical data: no download/scrape/fetch/generation; no Dukascopy/OANDA/CME additions; no synthetic prices;
  no substitute instruments; do NOT start the ingestion pipeline; do NOT modify the raw price store (`data/store/`).
- Allowed: read existing price files, read quality manifests, resample existing M1/30s, rebuild derived candles/events,
  recompute caches, create new derived Parquet/DuckDB tables, recompute results with corrected algorithms.
- Unsupported timeframe/hypothesis => `DATA_RESOLUTION_LIMITATION`. Never invent values.
- Workbook trade dates (2019-12..2020-02) lie outside ASTRA data (2021-11..2026-11). This is acceptable; do not block,
  do not reconcile dates, do not claim manual trades were replayed.

## 2. Real problem
- Manual book is much better than ASTRA's broad backtest. Hypothesis: ASTRA does not research the same narratives.
- Do not conclude a priori that the strategy is invalid / manual results representative / selection bias explains all /
  MMXM or QT don't work / more indicators help. Check opportunity generation, context, confirmations, stops, targets,
  executable simulation.

## 3. Workbook as specification
- Read all sheets (Trade_Log, Strategy_DNA, Edge_Finder, Interaction_Lab, Contribution_Analysis, Filter_Simulator,
  Management_Lab, TP_Lab, Playbook, Settings, Dashboard, others).
- Extract at least: HTF Bias, Daily Bias, DOL, HTF Target, Target Price/Type, HTF PD Array, Premium/Discount,
  MMXM/MMBM/MMSM, QT Context, 90M Quarter, Micro Quarter, QT Model, Macro 90M SSMT, Micro SSMT, Standard SMT,
  Liquidity Sweep, Sweep TF, CISD Type, CISD TF, CRT, FVG, IFVG, FPFVG, Displacement, MSS/CHOCH, Entry Trigger,
  Entry TF, Structural Stop, Planned R, Realized R, MFE/MAE, Target Hit, Notes, Screenshots.
- Per field: meaning; ASTRA code; current method; genuine vs proxy; required change; correctness test.
- States: TRUE_CAUSAL_IMPLEMENTATION, SIMPLIFIED_PROXY, INCORRECT_IMPLEMENTATION, MISSING_IMPLEMENTATION, MANUAL_ONLY,
  AMBIGUOUS_DEFINITION, DATA_RESOLUTION_LIMITATION. A similarly named column is not completion.

## 4. Strategy narrative
HTF CONTEXT → LIQUIDITY OBJECTIVE → FRACTAL MMXM → QT PHASE → LIQUIDITY INTERACTION → SMT/SSMT/CRT/CISD →
EXECUTABLE ENTRY → STRUCTURAL INVALIDATION → PRE-EXISTING TARGET. Causal model, not a fixed sequence; event order varies.

## 5. Fractal dimensions (non-negotiable)
`origin_tf`, `mmxm_structure_tf`, `entry_tf`, `target_tf`, `qt_temporal_context`; no rigid hierarchy.
TFs: W, D, H6, H4, H2, H1, M90, M30, M15, M10, M5, M3, M1 (finer only where data supports).
Mandatory narratives A–E (+ bullish/bearish equivalents, reversal & continuation separately, cross-TF targets):
- A: M5 bull MMXM, M1 bull CISD, LONG → H1 BSL.
- B: H1 SSL sweep, H1 bull reversal candidate, M5 bull MMXM, 90M Q2, Micro bull SSMT, M15 bull CISD, LONG → H1 liq or M5 OC.
- C: H4 bear delivery, M15 bull corrective MMXM, M5 bear CISD, SHORT → Daily SSL.
- D: Daily bull, H1 bear correction, M15 SSL sweep, M5 bull reversal, M1 CISD, LONG → Weekly BSL.
- E: H1 BSL sweep, M15 bear MMXM, Micro bear SSMT, M5 bear CISD, SHORT → historical M5 OC.

## 6. MMXM semantics
Every stage = objectively observable event. OC independent & causal; departure observable; liquidity engineering
references real liquidity; HTF POI interaction references real POI; CISD/CRT/SMT confirmations reference real events;
targets use previously available levels; completion/failure at correct timestamps. Price-threshold transitions must
not be described as CRT/SMT/CISD/POI confirmation. Separate structural stages from external confirmations. Multiple
concurrent MMXM candidates across TFs. Nested/corrective structures (aligned, corrective, reversal/continuation mixes).
HTF direction from structure & liquidity, not candle colour.

## 7. MMXM × QT core engine
6H, 90M, 22.5M QT; Q1–Q4; transitions; True Open; Macro/Micro SSMT; supported alternative anchors.
Determine QT phase of MMXM start, sweep, SSMT order vs sweep, reversal same/next quarter, CISD phase, continuation
phases, conflicts. Test e.g. Q2+M5 MMXM rev+MicroSSMT+M1 CISD vs no MicroSSMT vs M15 CISD with genuine alternative
entries. Do not assume Q2 manipulates / Q3 distributes.

## 8. REQUIRED / DISABLED / ABSENT_ONLY
For CRT, Macro SSMT, Micro SSMT, SMT, CISD, MMXM, QT: REQUIRED (confirmed before entry), DISABLED (ignored),
ABSENT_ONLY (verified absence; separate experiment). 64 binary core = REQUIRED vs DISABLED. CRT OFF ≠ CRT absent.
Regression tests proving the distinction.

## 9. Independent execution
Common objective opportunity universe; for each opportunity simulate every eligible policy independently: evidence,
order, confirmation ts, expiry, eligibility, fill, stop, target, exit, net R. CISD comparison on SAME event:
none/M1/M3/M5/M15/M30/H1/H4/multi. No early signals (M15 CISD cannot fill before its close). Expired =>
`EXPIRED_BEFORE_ENTRY`; never clamp timestamps. Compare fill, delay, stop distance, target distance, actual R:R,
target-before-stop, net R, availability. Keep shared underlying event id.

## 10. Stops / targets
Enumerate targets existing BEFORE entry (OC across TFs; H1/H4/D/W liquidity; M5/M15 structural liquidity; FVG/PD;
CRT objectives; other pools). Stops: sweep extreme, CRT extreme, MMXM invalidation, structural swing, ATR-buffered.
Targets: nearest structural liquidity, MMXM objective, historical OC, opposing liquidity, fixed R, partials, BE,
structural trailing. No future-based selection. Actual target price used as TP. LONG Ask entry / Bid exit;
SHORT Bid entry / Ask exit. Outcomes: TARGET_HIT, STOP_HIT, AMBIGUOUS, TIMEOUT, DATA_END, MISSED_ENTRY,
EXPIRED_BEFORE_ENTRY. Target after stop never counts.

## 11. Manual workbook study
Ontology + example library; patterns, liquidity situations, MMXM descriptions, QT/SSMT, entry preferences, target
logic, failure causes, conflicts, discretionary criteria. Manual P&L = recorded observations. Detect populated rows
(no hardcoding). Separate A) manual suggests, B) ASTRA currently detects, C) corrected system detects, D) data supports.

## 12. Why original results were negative
Decompose 18 candidate causes (broad selection, MMXM proxies, HTF direction, QT misclassification, liquidity
definitions, SSMT association, CISD timing, entry early/late, stop mismatch, target mismatch, reversal vs
continuation, conflicting filters, costs, insufficient confirmation, excessive delay, population differences, small
manual sample, multiple testing). Measurable counterfactual per cause where feasible; report limitations.

## 13. Narrative research table
Dimensions: instrument, direction, rev/cont, origin TF, MMXM TF, MMXM stage, entry TF, target TF, liquidity source TF,
liquidity event type, QT 6H/90M/micro, macro/micro SSMT, SMT, CRT, CISD TF, FVG/FPFVG, HTF/LTF alignment,
confirmation order, session, entry minute, stop/target/exit model. Metrics: eligible count, executed, unique events,
unique days, WR, net exp R, PF, DD, MFE/MAE, target-before-stop, CI, chronological OOS, yearly stability, cost
sensitivity. All 64 configs. Registry statuses: TESTED, NO_SIGNAL, INVALID, INSUFFICIENT_DATA, PENDING,
DATA_RESOLUTION_LIMITATION. No invented outcomes; no silent dropping.

## 14. Discovery not curve fitting
Chronological train/dev/validation, walk-forward, purge/embargo, day-clustered CIs, matched-event comparisons,
multiple-testing correction, yearly robustness, parameter sensitivity, conservative execution. V1–V3-explored data is
not untouched validation. Report absence of edge if so.

## 15. Hardware
Detect CPU/RAM/disk; DuckDB/Polars/Parquet/PyArrow/NumPy/Numba; batching; event caching; checkpoint/resume; avoid
copies and nested parallelism; benchmark; never change numerics for speed; no ingestion.

## 16. Regression tests
Semantics (REQUIRED/DISABLED/ABSENT, 64 policies, common universe, distinct trade ids, shared event ids); timing (CISD
boundaries, no early M15/H1, QT boundaries, DST, OC known-before-entry, prefix invariance, no retrospective MMXM);
structure (M5→H1 liq, H1→M5 OC, HTF correction, true SSMT/CRT/CISD refs, POI, LONG/SHORT symmetry); execution
(bid/ask, stop/target, ambiguous bar, timeout, no future target, independent policies); reporting (no silent sampling,
unique counts, OOS partitions, reproducible stats, report↔parquet reconciliation, old vs new reconciliation, no
constant verified=True). Behavioural tests; never weaken tests.

## 17. Phases (sequential, no stopping after gap analysis)
A workbook semantic reconstruction → B causality & MMXM repair → C independent execution → D fractal narrative &
target engine → E existing-data research → F gap & robustness → G reporting & dashboard. Checkpoint after each.

## 18. Deliverables
`reports/ASTRA6_V3_3_FINAL_NARRATIVE_RESEARCH.{md,html,pdf}` (Turkish, 16 chapters: executive summary; strategy;
original defects; corrections; MMXM×QT; LONG/SHORT; reversal/continuation; CISD TF comparison; HTF/LTF targets;
Nasdaq open & sessions; why negative; promising combos; what does not work; manual vs algorithmic; technical quality &
hardware; conclusions) + `reports/V3_3_CODE_AUDIT.md`, `V3_3_EXCEL_SEMANTIC_MAPPING.md`,
`V3_3_BEFORE_AFTER_PERFORMANCE.md`, `V3_3_STATISTICAL_VALIDATION.md`, `V3_3_REPRODUCIBILITY.md`,
`V3_3_FINAL_TEST_RESULTS.md`. Visuals: narrative diagram, MMXM stage×QT heatmap, macro/micro SSMT, CISD TF comparison,
LONG vs SHORT, entry TF×target TF heatmap, NQ 09:30 5-min heatmap, stop/target comparison, old vs new, OOS stability,
≥10 traceable trade replays. All from actual results; no hardcoded conclusions.

## 19. PDF quality
Turkish characters, chapters, readable tables, no clipping, labelled charts, consistent R units, correct CIs, version
disclosure; HTML and PDF from same results; reopen & visually inspect rendered pages.

## 20. Checkpoint / resume
`docs/ASTRA6_V3_3_MASTER_SPEC.md` (this file), `docs/ASTRA6_V3_3_PROGRESS.md`, `data/results/v3_3_checkpoint.json`.
After every phase: completed tasks, changed files, tests passed/failed, output paths, algorithm version, data hash,
remaining work, exact resume command. Do not restart completed phases; do not delete project; do not reset git;
DO NOT PUSH without explicit authorisation; avoid huge un-checkpointed jobs.

## 21. Final acceptance test
Real historical opportunity from existing data showing: liquidity context, HTF narrative, MMXM structure/TF, stage &
evidence, QT 6H/90M/micro, macro/micro SSMT, CRT, M1/M5/M15 CISD times, independent entries per CISD policy, distinct
fill/stop/target, net R per policy, pre-existing HTF/LTF targets, why policies differ, full event trace + chart.
Plus a bearish SHORT example, an unsuccessful setup and a continuation setup. Ambiguous definitions marked.

