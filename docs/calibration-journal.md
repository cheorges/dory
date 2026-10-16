# Calibration journal

Estimated against actual time per iteration. Actual times come from the herdr journal (`~/.herdr-journal/dory/dory.jsonl`): agent time while a pane computes, human time while the workspace has focus and no pane computes. The numbers check the estimates; they are not a price.

## Record 002: Note quality and recall value

| Story | Est. (h) | Start | Impl. done | Actual (agent / human) | Review/DoD | Note |
|-------|----------|-------|------------|------------------------|------------|------|
| D: finalize Record 002 | 0.5 | 2026-10-15 13:25 | 13:35 | 10 min / 4 min | ok 13:39 | design review by an architect agent, 13 findings worked in |
| S3: remove open items | 0.5 | 2026-10-15 13:40 | 13:50 | 12.5 min / 23.7 min | ok 14:16 | human time includes the question about recent sessions and decision 5 |
| S4: remove recent sessions | 0.5 | 2026-10-15 14:18 | 14:21 | 4 min / 4.5 min | ok 14:26 | rewritten after decision 5; was the `0` fix at 0.2 h |
| S1: repository documents for the worker | 3 | 2026-10-15 14:27 | 14:51 | 25 min / 0.6 min | ok 14:53 | estimate raised from 2.5 after the design review; includes 4 live rounds and a control run on the old code |
| S2: writing rules | 2 | 2026-10-15 14:55 | 15:25 | 34 min / 0.6 min | ok 15:30 | estimate raised from 1.5 after the design review; includes 154 live worker runs (control runs on the old rules, two review fixes reproduced before and after) and a second review pass |
| S7: living notes with telling names | 3 | 2026-10-16 11:56 | 13:03 | 72 min / 50 min | ok 13:58 | five review passes, the retry mechanism built and removed again, the language check fixed in a third attempt; human time includes reading the review packages and two decisions |
| S6: release 0.3.0 prepared | 0.2 | 2026-10-15 15:30 | 15:45 | 19 min / not measurable | ok 2026-10-16 08:42 | human time spans the pause for the usage limit and the night; includes two review rounds on the CHANGELOG text |
| S5: clean up the existing vault | 0.5 | | | | | estimate raised from 0.3 after the design review |
