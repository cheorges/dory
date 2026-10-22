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
| S5: clean up the existing vault | 0.5 | | | | | dropped on 2026-10-17: a fresh vault instead (Record 002, decision 4); the reset took a few minutes and is not measured |

## Record 003: One knowledge file per project

| Story | Est. (h) | Start | Impl. done | Actual (agent / human) | Review/DoD | Note |
|-------|----------|-------|------------|------------------------|------------|------|
| D: design review | 0.3 | 2026-10-19 12:20 | 12:35 | 14 min / 13 min | ok 12:47 | architect review against the code, 19 findings (3 P1) worked in, one question to the user; the design itself (09:58 to 12:20) was a conversation with the user and is not counted |
| S1: entries and post-run checks | 1 | 2026-10-19 12:48 | 13:16 | 28 min / 36 min | ok 13:52 | agent time includes three review passes (two reviewers, then one); 9 findings, one P1 that changed the baseline from per entry to per attempt; human time is reading the review package |
| S2: the worker keeps one knowledge file per scope | 1.5 | 2026-10-19 13:53 | 14:55 | 62 min / 21 min | ok 15:16 | agent time includes about 110 live runs (8 min of probes, five suite rounds), two review passes (three reviewers, then one) and two rule fixes after failed live rounds |
| S3: the session start loads the files | 0.5 | 2026-10-19 15:18 | 15:35 | 17 min / 0.2 min | ok 15:35 | agent time includes two review passes (three reviewers, then one); 5 findings, one P2 found by all three; no live runs |
| S4: a summary over the limit | 1.5 | 2026-10-19 15:36 | 16:03 | 27 min / 1.7 min | ok 16:05 | agent time includes a live probe with positive control and two live checks (12 runs, about 0.01 USD), seven mutations, two review passes (three reviewers, then one); 1 P1 (tests started a real worker on the user's state), 1 P2, 5 P3 |
| S5: `/dory:note` writes the user's notes | 0.5 | 2026-10-19 16:06 | 16:31 | 26 min / 14 min | ok 16:45 | agent time includes five live rounds of the seven note checks (about 70 s each), two review passes (three reviewers, then one); 1 P2 found by all three (no lock between add-note and a running worker), 2 P3; human time is reading the review package |
| S6: search finds single entries | 0.3 | 2026-10-19 16:45 | 16:56 | 11 min / 15 min | ok 17:11 | agent time includes three live rounds of the two search checks and one review pass (three reviewers, all `correct`, 3 small findings); human time is reading the review package |
| S7: release 0.4.0 prepared | 0.3 | 2026-10-19 17:12 | 17:21 | 10 min / 45 min | ok 18:05 | agent time includes one documentation review (6 findings, one P2 on deleting private overviews too early); human time is reading the release package |

## Record 004: Notes as files and one folder without a project

| Story | Est. (h) | Start | Impl. done | Actual (agent / human) | Review/DoD | Note |
|-------|----------|-------|------------|------------------------|------------|------|
| S1: file names and post-run checks for the new layout | 1.5 | 2026-10-21 22:16 | 22:39 | 23 min / 2 min | not reviewed: the user let the build go on without a halt per story (2026-10-21 22:41) | agent time includes two review passes (two reviewers, then one; 3 findings, P2 and two P3); human time is the review of this package, read at sign-off; the design (conversation and one architect review) is not counted |
| S2 to S7: worker, session start, summaries, `/dory:note`, search, release text | 2 for S2, none for the rest | 2026-10-21 22:42 | 23:11 | 29 min / not reviewed yet | | built in one run without a halt per story (the user's instruction of 22:41), so the stories are not measured one by one; includes the deny probe (11 runs), the live rule suite once and the changed checks twice more, the note checks three times, one combined review pass (two reviewers, 2 P3) |
