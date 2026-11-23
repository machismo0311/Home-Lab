# Change Record (DRAFT): NetFRAME Dashboard serve.py Deploy to Ares, r2 through r6

## 1. Document control

| Field | Value |
| --- | --- |
| Document ID | `CHANGE-RECORD-NETFRAME-DASHBOARD-SERVE-DEPLOY-20261122` (descriptive ID; an NF-series ID, NF-OP or NF-GV, has not been assigned and none is invented here) |
| Status | **DRAFT (documentation revision r3).** Not a run yes and not a push yes. Nothing here is approved to paste, run, commit or push. |
| Proposed repo path (not approved) | `docs/03-operations/change-record-netframe-dashboard-serve-deploy.md` |
| Date | Change executed 2026-11-22. This documentation revision drafted 2026-11-23 (America/New_York, EST, 24-hour clock). |
| Drafter | Stratt |
| Approver | Kyle (own words, relayed by Rocky; see section 4) |
| Owner | Infrastructure Engineering |
| Host | Ares, user `machismo` |
| Change summary | Replace `serve.py` in `/home/machismo/netframe-dashboard`, sha256 `e7c5d72c` to `656ee904`, and restart the user unit `netframe-dashboard.service`. |
| Risk | No risk rating is stated in the sources. Observed impact of the completed change: a restart of one user unit; no rollback; no outage attributed to it in the record. The restart gap duration is not in the record. |
| Rollback | Package blocks ROLLBACK-01 (restore), the shared restart block, ROLLBACK-02 (verify). Not used. |
| Related documents | `AAR-NETFRAME-DASHBOARD-SERVE-DEPLOY-20261122` (LaTeX, proposed `docs/90-governance/aar-netframe-dashboard-serve-deploy.tex`); master change log entries CL 339, 342, 343, 347, 349, 353, 360, 362, 433 to 457, 460 to 462, 465 |
| Review history of this documentation | r1 (two LaTeX drafts, written 2026-11-22, authority CL 456): one inline Codex check on 2026-11-23, verdict BLOCK on six factual errors (CL 460). r2 (authority CL 461) fixed those six findings and converted this record to Markdown: one inline Codex check on 2026-11-23, verdict BLOCK on one finding (CL 462), that both documents said CL 339 and CL 360 were not pasted. This r3 (authority CL 465) is a diff-only fix of that finding. This r3 has not been Codex-checked. SUMS for this documentation are not sealed (sealing only on sign-off, per CL 465). |

## 2. Purpose, scope, assumptions, prerequisites

**Purpose.** Record, for anyone operating NetFRAME, what the netframe-dashboard serve.py deploy to Ares was, why it took six package revisions, who approved each step and in whose words, what each revision produced, what the live system looks like now, and what remains open.

**Scope.** The serve.py deploy only, from the r2 package through the completed r6 run on 2026-11-22. The companion AAR covers the incidents and the corrective actions.

**Assumptions.**

- Every fact comes from the pasted sources: master CL entries 339, 342, 343, 347, 349, 353, 360, 362, 433 to 457, 460 to 462 and 465; the r1 documents and the r1 Codex result; the r4, r5 and r6 package files; the delivery tgz listings; the repo and Markdown conventions; and the relayed run outputs.
- A fact the sources do not establish is marked UNKNOWN or "not in the record".
- Facts taken from Rocky's relay of Kyle's run outputs are marked **(relayed)**.
- Times are America/New_York, EST, 24-hour clock. UTC (Z) stamps in file names were converted by subtracting five hours.
- Hash values are 8-hex prefixes unless a full value is needed.
- Costs appear only where a pasted CHANGE-LOG section or SHA-PIN states them, as historical figures.

**Prerequisites for the reader.** None.

## 3. Summary

On 2026-11-22 the file serve.py in the live netframe-dashboard tree on Ares was replaced, changing its sha256 from `e7c5d72c` to `656ee904`, and the user unit `netframe-dashboard.service` was restarted. The change completed with no rollback. At the end of the run (CL 455) the live serve.py was byte-identical to the reference copy in the package, process 677518 owned TCP 8088 and answered `/healthz` with ok, the four application rows of the dashboard moved from state `u` (unknown, no detail) to state `g` with detail, and the eight other service rows were unchanged (relayed).

Reaching that point took six package revisions. Three revisions did not reach a deploy:

| Rev | Result | Cause |
| --- | --- | --- |
| r3 | Halted before delivery (CL 433) | Sealed checksum list had three columns; the verify step reads two. |
| r4 | Run, stopped at precheck-05 (CL 442). Nothing changed on Ares. | A compared literal had a comma where the live unit text has an em dash. |
| r5 | Drafted, then held, never copied, never run (CL 449) | Corrected literal was missing a space. |

**r6** was run on Ares. It stopped at block CHANGE-01 because the block had already completed once (a double run); the guard refused as designed; Kyle accepted the earlier verified backup and told the run to continue (CL 453, CL 454). It then completed (CL 455). **Push of this documentation is not approved.**

## 4. Approvals: who approved what

All approvals below are Kyle's own words as relayed by Rocky and logged by Stratt, except where marked. Quoted text is verbatim from the master CL. Where a model name appears in a quote it is replaced by "[model name omitted here]".

| CL | Date and time (EST) | Kind | What Kyle said, or what is recorded |
| --- | --- | --- | --- |
| 339 | 2026-11-21 16:13 (logged 16:15) | r1 draft yes (initial draft approval) | "Yes, have Stratt draft the NetFRAME dashboard serve.py deploy to Ares (e7c5d72c to 656ee904, backup plus restart plus rollback), [model name omitted here], one Codex check, draft only". Rocky's read-only diagnosis (Kyle on Ares, 16:10 to 16:13), as recorded in the entry: `/api/state` on localhost:8088 returns the 4 app rows as s='u' with no 'd' field; PID 340294 runs live serve.py sha `e7c5d72c` (mtime 2026-10-07 20:09:31), while the box repo serve.py is `656ee904`. Package under `stratt/netframe-dashboard-serve-deploy-20261121/r1/`. |
| 343 | 2026-11-21 17:22 (logged 17:24) | r2 draft yes | "Yes, have Stratt draft the NetFRAME dashboard serve.py deploy r2 fixing the two Codex findings (status-1 checks and rollback relaunch with no listener), [model name omitted here], one Codex check, draft only". Fixes the CL 342 BLOCK. Launch method answered by Kyle's read on Ares at 17:22 (relayed): PID 340294 has PPID 924, no tty, tmux and screen not installed, and user unit `netframe-dashboard.service` is loaded active running. |
| 349 | 2026-11-21 18:55 (logged 18:57) | r3 draft yes | "After ZFS r5, run alert rules r2 then serve.py r3 as diff-only patches of the flagged lines with the status-check rule, [model name omitted here], Codex checks the diff only, draft only". Status-check rule: every remote read and cat checks its exit status before its output is compared. CL 349 states it also approves serve.py r3 (the CL 347 finding) as a diff-only draft. |
| 360 | 2026-11-21 20:15 | r3 Codex retry yes | "Yes, run one more Codex check on Stratt's serve.py deploy r3 diff (SHA-PIN 1c873b7d), read-only, node_repl with absolute paths, every list printed in batches of 60 or fewer, text in line ranges of 60 lines or fewer, one expected-hash table, seal SUMS only on sign-off, draft only". Relayed by Rocky and logged by Stratt. The result is logged in CL 362. |
| 433 | 2026-11-22 18:06 | start of r3 | "Kyle asked at 18:06 to start r3 under his standing run yes" (log text). Rocky halted before delivery. |
| 434 | 2026-11-22 18:07 | r4 draft yes | "Yes, have Stratt do a diff-only fix of the serve.py r3 SUMS format and file naming so the D2 `sha256sum -c --strict` check works, [model name omitted here], one Codex check with the inputs pasted inline, draft only." |
| 439 | 2026-11-22 18:23 | r4 run yes | "Yes, run Stratt's serve.py deploy r4 (SUMS 5904269b) with me pasting each line, stop on any STOP, rollback per the package if a postcheck fails" |
| 443 | 2026-11-22 18:33 | r5 draft yes | "Yes, have Stratt draft serve.py deploy r5 as a diff-only fix of the precheck-05 Description literal to match the live em dash exactly, plus its Gate G row and a sweep for other rewritten compared literals, [model name omitted here], one Codex check with inputs pasted inline, draft only" (item 1 of two yeses in that entry). The serve.py rerun needs a new run yes. |
| 450 | 2026-11-22 19:17 | r6 draft yes | "Yes, have Stratt patch serve.py r5 as r6, adding the missing space before the em dash in the precheck-05 WANT and fixtures, plus a test using the exact live Description bytes, [model name omitted here], one Codex check limited to that fix with inputs pasted inline, seal SUMS only on sign-off, draft only" |
| 452 | 2026-11-22 19:47 | r6 run yes | "Yes, run Stratt's serve.py deploy r6 (SUMS e511eb8d) from D1 into the fresh Ares directory nfmdash-serve-r6-20261122, with me pasting each line, stop on any STOP, rollback per the package if a postcheck fails" |
| 454 | 2026-11-22 20:15 | CHANGE-01 continue yes | "Yes, treat serve.py r6 CHANGE-01 as passed on the verified 20:14:51 backup, lift the HALT, and continue the r6 run at CHANGE-02 with me pasting each line, stop on any STOP, rollback per the package if a postcheck fails" |
| 456 | 2026-11-22 20:26 | this documentation, r1 | "Yes, have Stratt draft the serve.py deploy change record and AAR as GitHub docs (r4 precheck-05 STOP, r5 missing space, r6 CHANGE-01 double run and sourced-marker noise, with marker-safe blocks as a corrective action), [model name omitted here], one Codex check with inputs pasted inline, draft only, no push" |
| 460 | 2026-11-23 10:35 (log time) | review of r1 docs | Not a Kyle yes. Stratt's log of the one inline Codex check (10:31:28 to 10:31:51 EST, exit 0, 0 tool calls, prompt sha `46b73328`, 39 blocks): verdict BLOCK on six factual errors. States that a diff-only fix round needs Kyle's own-words yes. |
| 461 | 2026-11-23 10:34 (logged 10:36) | this documentation, r2 | "Yes, have Stratt patch the serve.py deploy change record and AAR as r2, fixing the six Codex findings in CL 460 and converting the change record to Markdown (AAR stays LaTeX), [model name omitted here], one Codex check with inputs pasted inline, seal SUMS only on sign-off, draft only, no push". Scope: r2 under the r2 workdir; r1 outputs kept unchanged as evidence. Result in the next CL. |
| 462 | 2026-11-23 10:46 (log time) | review of r2 docs | Not a Kyle yes. Stratt's log of the one inline Codex check (10:43:03 to 10:43:21 EST, exit 0, 0 tool calls, prompt `57cfa0f8`, 46 blocks): verdict BLOCK on one finding, that both documents said CL 339 and CL 360 were not pasted. Codex confirmed all six CL 460 findings fixed. States that an r3 fix round needs Kyle's own-words yes. |
| 465 | 2026-11-23 11:20 (logged 11:21) | this documentation, r3 | "Yes, have Stratt patch the serve.py docs r2 as r3, a diff-only fix of the CL 339 and CL 360 finding in CL 462 with those entries given to Claude, [model name omitted here], one Codex check with inputs pasted inline, seal SUMS only on sign-off, draft only, no push". Scope: r3 under the r3 workdir; r1 and r2 kept unchanged as evidence. Result in the next CL. |

Notes on the approvals:

- **No run yes was ever given for r5.** The CL 439 run yes was for r4 and, per the r5 and r6 runpath text, does not carry over.
- **Push is not approved.** CL 455 and CL 456 both state that a push needs its own yes. CL 461 and CL 465 repeat "draft only, no push".
- **Independent byte check.** Before the r6 run, Rocky reported a PASS on an independent byte check: SUMS 29 of 29 under strict mode, tgz `909e770e`, WANT spaced (CL 452).
- **Standing rules** adopted by Kyle at 18:21 EST on 2026-11-22 (relayed; CL 437, CL 438): grep the team records for the target host, IP or MAC before drafting any change, and absence checks use one narrow pattern with `grep -c`, never `head`. The record does not show whether the serve.py drafts recorded that grep result in the package; this is not established.
- **CL 362 and the r3 Codex check.** CL 362 (logged 2026-11-21 20:26) records the r3 Codex "retry1" (20:22:20 to 20:24:31 EST): SIGN-OFF, no blocking findings, CODEX-RESULT `55a67d5f`, official SHA256SUMS `01b7d335` (29 entries), run under CL 360 (Kyle's approval, in the table above). It references a preceding attempt; that attempt's result is not pasted here.

## 5. What changed and why

### 5.1 What was changed and where

| Item | Value as recorded |
| --- | --- |
| Host and user | Ares, user `machismo` |
| Live tree | `/home/machismo/netframe-dashboard` |
| Artifact changed | `serve.py` only. The package contains the target file as `in/reference/serve.py`. |
| Live pin (before) | `e7c5d72c0428f95b21504055227d215da17279660447793b20d4a57627ebd795`, 55253 bytes |
| Target pin (after) | `656ee904d839d920e0683c414075ce34b03fdda7f3275e28ca311c73c2be1c1a`, 71660 bytes |
| Unit | `netframe-dashboard.service`, systemd user manager (`systemctl --user`) |
| Restart command | exactly one: `systemctl --user restart netframe-dashboard.service` |
| Unit Restart= value | `Restart=always` as printed by precheck-05 in the run output (relayed). Other unit properties printed there: `NeedDaemonReload=no`, one Environment line. |
| Port and process | TCP 8088. Before the change: PID 340294, `/usr/bin/python3 /home/machismo/netframe-dashboard/serve.py 8088` |
| Live html (not changed) | sha `164c0d1f` (the b09feab-tree page). Precheck-11 required this value; the change is conditional on it. |
| Dependency verdict | serve.py only, per the package DEPENDENCY-REVIEW (full text not pasted here). No html, collector, Prometheus, CT 103, pve3 or other-unit change. |
| Backup | `serve.py.pre-nfmdash-serve-r2-20261123T011451Z` in the live tree (UTC stamp; 2026-11-22 20:14:51 EST) with a `.sha256` sidecar |
| Change window | Blocks refuse 23:30 to 03:59 EST (allowed 04:00 to 23:29). Kyle's run yes of CL 452 states the window ends 23:29 EST. |

### 5.2 Why the change was made, as far as the record states

The pasted sources describe the effect: before the change the four application rows showed state `u` with no detail field, and after it they showed state `g` with detail (precheck-10 and postcheck-04, relayed). The package's dependency review concluded serve.py alone was needed (full text not pasted). The business reason beyond that is not stated in the pasted sources.

## 6. Delivery steps D1 and D2

The package carries two non-paste delivery steps that were added after an earlier lesson. That lesson is recorded in CL 353 (2026-11-21 19:44, logged 19:50), written for the svc probe alert rules r2 package: Rocky found that no step delivered a required file to Ares or ran an on-host sha check, a gap missed by the draft and by Codex. Stratt gave Rocky a delivery method with no new keys or routes (Kyle copies the file with his existing ssh login after a hash match, then verifies on the host), and the entry's corrective was: "future runpaths include a delivery and on-host sha step". The serve.py package text cites this as "the CL 353 lesson".

- **D1** copies the sealed package tree from Quixote to a directory on Ares with Kyle's existing ssh login (no new keys, no new routes).
- **D2** verifies it on Ares. The command has been the same text since r3 (the directory name changes with the revision). Shown for r6:

```
cd "$HOME/nfmdash-serve-r6-20261122" && sha256sum SHA256SUMS && sha256sum -c --strict SHA256SUMS
```

The first printed sha must equal the published sha, each of the 29 listed files must print OK, and the exit status must be 0.

In r4 and later, D1 uses a single delivery tgz built from SHA256SUMS, DIFF-r2-r3.patch, out/ and in/reference/serve.py (31 files per CL 439). `in/reference/serve.py` is copied but deliberately not listed in SHA256SUMS; precheck-02 verifies it on the host.

### 6.1 Ares package directory per revision

| Rev | Ares package directory | Status as recorded |
| --- | --- | --- |
| r2, r3 | `$HOME/nfmdash-serve-r2-20261121` | r2 and r3 were never delivered (CL 433: nothing copied or run). |
| r4 | `$HOME/nfmdash-serve-r2-20261121` (the r2 name was kept on purpose; CL 439 extracts into it) | Delivered and run to precheck-05; its `rec/` exists and the CL 455 evidence list keeps it. Not a fresh directory name. |
| r5 | `$HOME/nfmdash-serve-r5-20261122` (fresh, specified in the r5 package) | r5 was never copied, so the directory should not exist (CL 451). Whether it exists is not verified in the record. |
| r6 | `$HOME/nfmdash-serve-r6-20261122` (fresh, specified in the r6 package and in CL 452) | Delivered and used for the completed run; its `rec/` holds the records. |

## 7. Revision history and results

| Rev | Outcome | Reason, in one line |
| --- | --- | --- |
| r1 | Codex BLOCK (CL 342) | Checks accepted failed commands (status 1 treated as a no-match; one `tr` and `grep` status ignored), and rollback restarted through a branch that needs an existing 8088 owner. |
| r2 | Codex BLOCK (CL 347) | A sidecar test compared only printed text, so a failed `cat` that printed the expected line could pass. |
| r3 | Halted before delivery (CL 433) | Sealed SUMS had three columns; D2 reads two. |
| r4 | Run, STOP at precheck-05 (CL 442) | Compared literal had a comma where the live Description has an em dash. |
| r5 | Drafted, HELD (CL 449) | Corrected literal omitted the space before the em dash. Never copied, never run. |
| r6 | Run, HALT at CHANGE-01, then COMPLETE (CL 453 to CL 455) | Double run of CHANGE-01 refused by the guard; Kyle accepted the verified backup. |

### 7.1 r1 (CL 342) and r2 (authority CL 343; Codex BLOCK CL 347)

**r1** (under CL 339, Kyle's 2026-11-21 16:13 draft yes, see section 4; logged in CL 342, 2026-11-21 16:17 to 17:14:30 EST, logged 17:22). Box tests 575 ok, 0 FAIL (an earlier attempt, 458 ok and 24 FAIL, came from a wrapper bug and was kept). Codex 17:11:47 to 17:14:30, verdict BLOCK, CODEX-RESULT `a1d48a45`, SHA-PIN `338d7ca1`, no official SUMS. Findings: (1) precheck-01 line 9 and precheck-05 line 12 treat any status 1 as a no-match, and postcheck-02 line 10 ignores the `tr | grep` status, so a failed command can PASS; (2) rollback restarts through the CHANGE-03 branch, which requires an existing 8088 owner, so with no listener it restores the file but cannot relaunch. No dependency STOP: serve.py only, if live html is `164c0d1f`. Open at that time: the PID 340294 launch method, the package transfer path to Ares, the hostname check. Nothing ran on Ares.

**r2** (authority CL 343, 2026-11-21 17:22; run logged in CL 347, 18:03 to 18:42:42 EST, logged 18:45). Fixes the two CL 342 findings: every remote read tests its exit status before comparing output; the restart block is shared by CHANGE and ROLLBACK and does not require an existing 8088 listener; the launch method is fixed to the systemd user unit with no tmux, screen or nohup branch (CL 343 records Kyle's 17:22 read). Box tests 802 ok, 0 FAIL. Codex 18:38:49 to 18:42:42 (30 files read in full, 3 sha-only), verdict BLOCK, CODEX-RESULT `6c4deb63`, SHA-PIN `0048a2a3`, no official SUMS. Finding: block-CHANGE-02-stage-replace line 23 and block-ROLLBACK-01-restore line 20 compare the text of `cat "$B.sha256"` without checking the exit status of `cat`, so a failed read that printed the expected line could still reach the replace or the restore. Nothing ran on Ares. Nothing in the record says r2 was delivered or run.

### 7.2 r3 (authority CL 349); halted before delivery (CL 433)

r3 patched the r2 sidecar test (capture the `cat` first, test its status, then compare the captured text) in the two blocks CHANGE-02 and ROLLBACK-01, and added the D1 and D2 delivery steps. CL 362 records the r3 Codex retry1 (a preceding attempt is referenced, its result not pasted here): SIGN-OFF, no blocking findings, official SHA256SUMS `01b7d335` (29 entries). CL 433 confirms a Codex SIGN-OFF was logged under CL 362.

On 2026-11-22 Kyle asked at 18:06 to start r3; Rocky halted before delivery; nothing was copied or run on any host. The sealed file `SHA256SUMS-NETFRAME-DASHBOARD-SERVE-DEPLOY-r3-20261121.txt` (`01b7d335`) listed sha, size and path; `sha256sum -c --strict SHA256SUMS` reads the size as part of the file name. Rocky tested a copy: all 29 entries failed to open or read, and all 29 verified when cut to two columns. Stratt confirmed on the box at 18:17. D1 and D2 also named the file SHA256SUMS, not the sealed long name. Root cause (Stratt, CL 433): the seal step wrote a three-column manifest, and neither the tests nor the CL 362 Codex check compared the seal format with D2. r3 was kept unchanged as evidence (tree `5760c449`, 69 files; SUMS `01b7d335`).

### 7.3 r4 (authority CL 434); run, STOP at precheck-05 (CL 439, CL 442)

**Fix.** The sealed file is named exactly SHA256SUMS and uses the standard two-column GNU format (64 lowercase hex, two spaces, relative path), 29 entries (DIFF-r2-r3.patch plus 28 files under out/). No size column and no SIZES file. A new format test was added at the package root. No deploy block and no serve.py was changed (DIFF-r3-r4.patch `f6c98169`).

**Tests and review.** Format test 12 ok; D2 on a D1-layout tree 29 OK, exit 0; tree-mode test 9 ok. One inline Codex check with no tools: SIGN-OFF (CODEX-RESULT `11aab94e`, 18:20:25 to 18:20:38 EST). SUMS sealed after sign-off at 18:21:46 EST: `5904269bf726865588ece6abfcba3cc1a1f214e680b4f6849c5d9876f327cee5`. Delivery tgz `5fbf0eea` (77997 bytes). Drafting-run cost as stated in CL 437: 3.31 USD (historical figure).

**Run.** Kyle's run yes was at 18:23 (CL 439). Rocky verified SUMS and D2 on the box. Kyle hashed the tgz on Quixote, copied it to Ares and extracted it into the r4 directory (the r2-named directory). D1 and D2 (29 OK, exit 0) passed and prechecks 01 to 04 passed. precheck-05 printed "STOP precheck-05 Description is not that unit" with the live Description, which contains U+2014 between "dashboard" and "serve" (CL 442, 18:33). The compared literal WANT, the Gate G row, the runpath, NOTES, the CHANGE-LOG-ENTRY and the test fixtures (lines 239 and 282) all expected a comma. Root cause recorded by Stratt: the prose no-dash rule was applied to a literal compared against live bytes, and the fixtures shared the error. **Impact: none.** Nothing changed; the r4 `rec/` exists on Ares; the service was untouched. Sweep: WANT was the only compared literal holding this text.

### 7.4 r5 (authority CL 443); drafted, then HELD (CL 447, CL 449)

**Fix.** WANT was written with the bash byte escape `\xe2\x80\x94` inside `$'...'` so the file stays ASCII and the compare does not depend on locale; a fresh Ares directory `$HOME/nfmdash-serve-r5-20261122` was named in D1, D2, Gate G row 01 and all 19 NFM_D defaults. Tests: official 911 ok, 0 FAIL; format 12 ok; sealed-tree 9 ok. Codex inline SIGN-OFF (`fddae3f1`, 18:53:25 to 18:53:39 EST) with one residual note about a fixture-claim wording. SUMS sealed 18:54 EST: `4c265a5f45a46579bdd9bb05465958178e151f62b62246021ffdc7f1c60b848d`; delivery tgz `eeaa1caf` (86446 bytes); DIFF-r4-r5 `3025e755`. Drafting-run cost as stated in CL 447: 6.50 USD (historical figure). CL 447 was logged 19:15.

**Hold.** At 19:14 EST Rocky identified that Kyle's relayed live STOP text has a space before and after U+2014, while the r5 WANT omitted the space before it (50 bytes instead of 51). The r5 claim that WANT matched the live bytes was incorrect; the tests and the Codex check shared the same expected bytes and so did not establish live compatibility (CL 449). r5 was not copied and not run. All r5 evidence was preserved. Impact: none on any host.

### 7.5 r6 (authority CL 450); run, HALT, accepted, COMPLETE (CL 452 to CL 455)

**Fix.** WANT is now `$'NetFRAME wall dashboard \xe2\x80\x94 serve + live-data proxy'`, which evaluates to the 51 bytes below (space, U+2014, space). A new official-test block ("C1b") compares against a hardcoded hex literal that is independent of WANT and of the FACTS file. A fresh directory `$HOME/nfmdash-serve-r6-20261122` replaces r5's.

The expected Description as one 102-digit lowercase hex string (shown on one line, not separated by anything):

```
4e65744652414d452077616c6c2064617368626f61726420e28094207365727665202b206c6976652d646174612070726f7879
```

**Tests and review.** Official test first run 986 ok, 1 FAIL at 19:28:49 EST: a false hit of the attribution scan on a NOTES clause; after one clause was rephrased, 987 ok, 0 FAIL at 19:30:19. Format 12 ok; sealed-tree 9 ok; D2 29 OK, exit 0. Codex inline check, no tools, limited to that fix: SIGN-OFF with no residual notes (`78ccc60d`, 19:32:50 to 19:33:04 EST). SUMS sealed 19:33 EST: `e511eb8df755e6c98c04e26c4bd48614852132c0486c663eda8029553afd5d2e`; delivery tgz `909e770e23595206356188827e5e5834c3735a43e6965da5115c13ac73ba2f7c` (91792 bytes); DIFF-r5-r6 `320265ee`; SHA-PIN `17456e15`. Drafting-run cost as stated in CL 451 and the r6 SHA-PIN: 7.35 USD, including a one-clause NOTES rephrase (historical figure). Evidence: r5 and r5-delivery unchanged. Nothing was copied to Ares before the run yes.

## 8. Execution log: the r6 run

Source: CL 453 to CL 455 and the RUN-OUTPUTS file saved by Stratt under `r6-run-20261122`, which is Kyle's raw output as relayed verbatim by Rocky at 20:26 EST. Every row below is **(relayed)** unless marked.

| Step | Recorded result |
| --- | --- |
| D1 | D1-1: Quixote hash of the tgz printed as `909E770E...2BA2F7C`. D1-2: scp 100 percent, 90 KB. D1-3: `MKDIR_OK`. D1-4: `EXTRACT_OK`. The first D1-3 paste went into Quixote PowerShell by mistake: parse error, nothing ran. Kyle pasted it again on Ares. |
| D2 | First sha `e511eb8d...d5d2e`, 29 OK, rc 0. |
| precheck-01 | PASS, user machismo, host ares, live and package paths as expected, hooks none, 2026-11-22 19:54:56 EST. |
| precheck-02 | PASS, staged source sha `656ee904`, 71660 bytes. |
| precheck-03 | PASS, live serve.py sha `e7c5d72c`, 55253 bytes, mode 644, owner machismo, mtime 2026-10-07 20:09:31 -0400. |
| precheck-04 | PASS, pid 340294 owns 8088. |
| precheck-05 | Description printed with a space either side of the em dash; `Restart=always`, `NeedDaemonReload=no`, Env lines=1; PASS; record `rec/unit-20261123T011222Z-676084.txt` (20:12:22 EST). The Restart= value is recorded here as printed in the relayed RUN-OUTPUTS. The record file itself is not pasted. |
| precheck-06 to 09 | PASS: MainPID 340294 equals the 8088 listener; 134915104 KiB free; protected-file shas `5d758914`, `6bb34bf8`, `0cc1c6c2`; 10 svc probe pairs present. |
| precheck-10 | 4 app rows `s=u d=absent`, 12 services rows; PASS; record `rec/api-state-pre-20261123T011401Z-676423.json`. |
| precheck-11 | PASS, html `164c0d1f`; record `rec/html-20261123T011417Z-676512.sha256`. |
| CHANGE-01 | The first run's PASS line was not captured. Captured: noise line, "HALT a backup is already recorded: .../serve.py.pre-nfmdash-serve-r2-20261123T011451Z", "HALT block-CHANGE-01-backup", noise line. Read-only verification by Kyle: `rec/backup.path` names that file; sidecar OK; live and backup both `e7c5d72c`. Accepted as PASS by CL 454. |
| CHANGE-02 | PASS, live serve.py is now `656ee904`. |
| CHANGE-03 | Before the restart, 8088 owner was 677259 (the unit had restarted itself; `Restart=always` is the recorded unit value). PASS: pid before 677259, new pid 677518 is MainPID. Why the unit restarted itself before the block: **UNKNOWN**. |
| postcheck-01, 02 | PASS: 677518 owns 8088, `/healthz` ok; unit active (running); MainPID 677518 is the only 8088 listener. |
| postcheck-03 | PASS, `656ee904` byte-identical to `in/reference/serve.py`. |
| postcheck-04 | OPNsense, Headscale, Home Assistant and Jellyfin each `s=g` with detail (OPNsense: tcp+app, authenticated API answering; Home Assistant and Jellyfin: tcp+app+health); PASS; capture `rec/api-state-post-20261123T012006Z-678039.json` (20:20:06 EST). |
| postcheck-05, 06 | Other rows pre 8, now 8, PASS; protected files and live html unchanged, PASS. |
| Rollback | None needed. |

**Noise.** The line `-bash: ===: command not found` printed on every block run with `source` (CL 454, CL 455, RUN-OUTPUTS). Cause: each block file contains a bare `=== BEGIN block-... ===` line and a matching END line, which are not comments. Any shell that receives those lines, whether the file is sourced or the marker lines are pasted along with the body, will attempt them as commands. Sourcing explains how Kyle ran the r6 blocks (the recorded execution method), but it is not the only way to trigger the noise. The noise was harmless. See the AAR for the corrective actions.

## 9. Evidence and artifacts

| Artifact | Value |
| --- | --- |
| SUMS r3 (kept as evidence) | `01b7d335`, three columns, long name; tree `5760c449`, 69 files |
| SUMS r4 | `5904269b`, 29 two-column entries, name SHA256SUMS |
| SUMS r5 | `4c265a5f`, 29 entries |
| SUMS r6 (used) | `e511eb8d`, 29 entries |
| Delivery tgz r4, r5, r6 | `5fbf0eea` (77997 B), `eeaa1caf` (86446 B), `909e770e` (91792 B); sizes and tar listings are pasted, the binary bytes are not |
| Diffs | DIFF-r2-r3 `8acd959b`; r3-r4 `f6c98169`; r4-r5 `3025e755`; r5-r6 `320265ee` |
| Codex results | r1 `a1d48a45` (BLOCK); r2 `6c4deb63` (BLOCK); r3 retry1 `55a67d5f` (SIGN-OFF); r4 `11aab94e`; r5 `fddae3f1`; r6 `78ccc60d`. r4 to r6 each inline, zero tools, SIGN-OFF. |
| Ares, keep, do not delete (CL 455) | the r4 directory and its `rec/`; the r6 directory and its `rec/`; the backup `serve.py.pre-nfmdash-serve-r2-20261123T011451Z` with its `.sha256` sidecar |
| Package CHANGE-LOG-ENTRY files | r4, r5, r6 entries exist as drafts "for Kyle to append himself". Whether Kyle appended them is not in the record. |
| Documentation review | r1 docs: `.tex` sha `f3d42614` (change record) and `ed77ee33` (AAR), CODEX-RESULT `042df626` (BLOCK, CL 460). Kept unchanged as evidence. |

Every regular file in the r4, r5 and r6 packages and the three delivery directories is listed by sha in PACKAGE-FILE-INVENTORY (pasted). Files whose bodies were not pasted (for example the DEPENDENCY-REVIEW, the test scripts and the diffs) are cited by sha only; their contents are not described here beyond what the pasted packages say about them.

## 10. Operating posture after the change

- Live serve.py on Ares: `656ee904`. Unit `netframe-dashboard.service`, MainPID 677518, sole 8088 listener, `Restart=always` (relayed) (CL 455).
- Rollback blocks (ROLLBACK-01 restore, restart block, ROLLBACK-02 verify) exist in the r6 package and were not used. The backup and sidecar above are what ROLLBACK-01 would restore from. A rollback is subject to the same 23:30 to 03:59 EST refusal window.
- The package is single-shot: `rec/backup.path` is recorded once and CHANGE-01 refuses a second backup. A second deploy attempt needs a new revision or Kyle's ruling.
- Any new run must use a new directory and a new run yes. A run yes names one package; a yes for r4 or r6 is not a yes for another revision.

## 11. Open items

1. **Push.** This change record and the AAR are drafts. Push to GitHub needs its own yes from Kyle (CL 455, CL 456, CL 461, CL 465). Proposed repository paths, not approved: `docs/03-operations/change-record-netframe-dashboard-serve-deploy.md` and `docs/90-governance/aar-netframe-dashboard-serve-deploy.tex`. PDFs are not committed under docs/. The style file stays at `docs/style/netframe-doc.sty`; no second copy is proposed.
2. **Codex check of these r3 documents.** CL 465 asks for one inline check. It has not been started by this draft. SUMS for these documents are sealed only on sign-off.
3. **NF-series IDs.** Not assigned; descriptive IDs are used.
4. **Memory notes.** CL 447 and CL 455 record that the r5 drafting run left two memory notes on Quixote, outside its workdir, left in place; Kyle decides. No decision is in the record.
5. **CHANGE-LOG.md entries** for r4, r5 and r6: appending is Kyle's. Whether Kyle appended the r4, r5 and r6 package CHANGE-LOG-ENTRY texts is not in the record. Master CL entries after CL 456 exist: CL 457 (azuh rule 92213 grouping draft parked, unrelated to serve.py), and CL 460, CL 461, CL 462 and CL 465 (this documentation). Other entries after 457 are not pasted and this record makes no claim about them.
6. **Evidence retention** on Ares (directories and backup above): no retention end date is in the record.
7. **Corrective actions** proposed in the AAR (marker-safe blocks, independent hex anchor, no-dash rule for prose only, plus a PASS/HALT log and host and shell naming on every paste line) are not yet adopted or implemented.
8. **Unit self-restart** between CHANGE-02 and CHANGE-03 (pid 677259): cause **UNKNOWN**. The unit's Restart= value is `always` (relayed in the RUN-OUTPUTS); the cause of this particular restart is still not established.
9. **Restart gap** duration on 8088 during the restart: not in the record.

## 12. Source differences and caveats

| # | Point |
| --- | --- |
| 1 | The r5 package (runpath, NOTES, SHA-PIN, CODEX-RESULT) states that WANT matches the live bytes at 50 bytes with no space before the em dash. CL 449 and the r6 package state this was incorrect (51 bytes, space on both sides). Reported as stated; the r5 files are kept as evidence and are not edited. |
| 2 | The r5 SHA-PIN labels its hex as "FACTS CL442"; the pasted CL 442 says only that the Description contains U+2014 between "dashboard" and "serve" and does not paste bytes. The r6 NOTES attribute the correct bytes to a FACTS file for CL 449, whose body is not pasted. |
| 3 | CL 453 lists two noise lines before the HALT lines. The relayed RUN-OUTPUTS show one noise line before and one after, which is what BEGIN and END marker lines at the start and end of the file would produce. Both are reported; the order in the RUN-OUTPUTS is the later and fuller relay. |
| 4 | CL 442 (halt, 18:33, logged 18:36) and CL 443 (Kyle's r5 yes, 18:33, logged 18:35) carry the same minute. The order within that minute is not in the record. |
| 5 | CL 453 (logged 20:20) and CL 454 are both headed 20:15 EST, and the first CHANGE-01 run finished at 20:14:51 EST. The record does not separate the second run, the read-only verification and Kyle's yes inside that interval. |
| 6 | CL 453 said "most likely the block ran twice" and marked it unconfirmed; CL 454 confirmed it by the read-only verification. |
| 7 | CL 453 said the outputs of prechecks 01 to 11 had not been seen by Stratt; they appear later in the RUN-OUTPUTS file. |
| 8 | The CL 451 note says the r5 Ares directory should not exist; no check of Ares for it is in the record. |
| 9 | Not pasted: the bodies of the r2 and r3 CHANGE-LOG-ENTRY files, the DEPENDENCY-REVIEW, any packaged test script, the preceding attempt of the r3 Codex check. |
| 10 | CL 453, CL 454 and CL 455 attribute the `===: command not found` noise to sourcing the block files (CL 453: "marker lines are not comment-safe when a block file is sourced"). The pasted block-CHANGE-01 file shows the BEGIN and END lines as bare text, so they would also be attempted as commands whenever they are included in shell input by any method. Both facts are reported; sourcing is the recorded method, not the sole cause. |
| 11 | The Restart= value (`always`) appears in the relayed RUN-OUTPUTS precheck-05 line. The precheck-05 record file (`rec/unit-20261123T011222Z-676084.txt`) is not pasted. The r4, r5 and r6 package text says the Restart= value was "not known to this draft"; that was true at drafting time and was resolved by the run output. |
| 12 | CL 353 concerns a different package (svc probe alert rules r2). It is cited here only for the delivery-step lesson that the serve.py package text names. |
| 13 | The r1 documents said CL 343, CL 349 and CL 353 were not pasted, said the Restart= value was UNKNOWN, and treated master CL numbering after 456 as absent. All three were incorrect (CL 460). They were corrected in r2. |
| 14 | The r2 documents said CL 339 and CL 360 were not pasted. That was incorrect (CL 462): both entries are pasted and are cited in section 4. It is corrected in this r3. |

## 13. Sources cited

Master CL entries 339, 342, 343, 347, 349, 353, 360, 362, 433 to 457, 460 to 462 and 465; RUN-OUTPUTS-r6-20261122-as-relayed; the r1 documents and r1 CODEX-RESULT; the r2 documents and r2 CODEX-RESULT; for r4, r5 and r6: SHA-PIN, CODEX-RESULT, CHANGE-LOG-ENTRY, TEST-RESULTS, SHA256SUMS, runpath, NOTES, precheck-05 and block-CHANGE-01 files; the three delivery tgz listings; PACKAGE-FILE-INVENTORY; PASTED-SOURCE-SHAS; REPO-CONVENTION; MARKDOWN-CONVENTION; netframe-doc.sty. Costs appear only where those sources state them, as historical figures.
