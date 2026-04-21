     1|     1|# Asset Pack Index — Agent Launch Closeout Kit
     2|     2|
     3|     3|## Purpose
     4|     4|Tie the final-mile launch surface into one reusable package so a proof-backed MVP can move from "ready in theory" to an actually executed launch without hidden steps.
     5|     5|
     6|     6|Use this index to keep four things aligned:
     7|     7|1. product-proof anchors
     8|     8|2. launch copy source
     9|     9|3. media / attachment source
    10|    10|4. execution logging
    11|    11|
    12|    12|## Narrow ship line
    13|    13|This kit is for **launch closeout only**.
    14|    14|
    15|    15|It does not prove the underlying product. It packages and executes the last mile for a product that already has an honest ship line.
    16|    16|
    17|    17|## Separate these two truths
    18|    18|### Product proof
    19|    19|Evidence that the MVP claim is true.
    20|    20|
    21|    21|Required fields:
    22|    22|- Product name: Agentic Cron Orchestration Kit
    23|    23|- Ship line: starter-workflow claim only
    24|    24|- Proof artifact path: `starter-kits/agentic-cron-orchestration-kit/qa/clean-room-proof-run-2026-04-17.md`
    25|    25|- Proof command or run reference: `bash starter-kits/agentic-cron-orchestration-kit/scripts/preflight.sh`
    26|    26|- Key metric / evidence: fresh-context proof recorded at **1.74 minutes**
    27|    27|- Hidden setup contract to disclose: inject the exact note paths and workspace path into the prompt templates before claiming a fresh-context run
    28|    28|
    29|    29|### Launch execution
    30|    30|Evidence that the launch actually happened or is fully publish-ready.
    31|    31|
    32|    32|Required fields:
    33|    33|- Launch thread source path: `starter-kits/agentic-cron-orchestration-kit/launch/launch-thread.md`
    34|    34|- Publish runbook path: `starter-kits/agent-launch-closeout-kit/publish-runbook.md`
    35|    35|- Demo runbook path: `starter-kits/agent-launch-closeout-kit/demo-capture-runbook.md`
    36|    36|- Launch execution log path: `starter-kits/agent-launch-closeout-kit/launch-execution-log.md`
    37|    37|- Primary attachment: short walkthrough cut using `starter-kits/agentic-cron-orchestration-kit/launch/demo-captions.srt`
    38|    38|- Fallback attachment: proof-artifact still showing **1.74 minutes**
    39|    39|- Current closeout state: pending publish / pending capture
    40|    40|
    41|    41|## Canonical asset set
    42|    42|### Copy
    43|    43|- README / product page: `starter-kits/agent-launch-closeout-kit/README.md`
    44|    44|- Ship note: `starter-kits/agentic-cron-orchestration-kit/launch/ship-note.md`
    45|    45|- Launch thread: `starter-kits/agentic-cron-orchestration-kit/launch/launch-thread.md`
    46|    46|
    47|    47|### Proof
    48|    48|- QA / proof artifact: `starter-kits/agentic-cron-orchestration-kit/qa/clean-room-proof-run-2026-04-17.md`
    49|    49|- Clean-room notes or verification log: `starter-kits/agentic-cron-orchestration-kit/launch/launch-execution-log.md`
    50|    50|- Screenshot or still source: proof-artifact still showing **1.74 minutes**
    51|    51|
    52|    52|### Media
    53|    53|- Demo outline: `starter-kits/agentic-cron-orchestration-kit/launch/demo-outline.md`
    54|    54|- Demo capture runbook: `starter-kits/agent-launch-closeout-kit/demo-capture-runbook.md`
    55|    55|- Captions file: `starter-kits/agentic-cron-orchestration-kit/launch/demo-captions.srt`
    56|    56|- Edited asset path: record in `starter-kits/agent-launch-closeout-kit/launch-execution-log.md`
    57|    57|
    58|    58|### Execution tracking
    59|    59|- Launch execution log: `starter-kits/agent-launch-closeout-kit/launch-execution-log.md`
    60|    60|- MVP ship checklist: `Projects/Hermes/Agent Launch Closeout Kit — Ship Checklist.md`
    61|    61|- Proof-surface ship checklist: `Projects/Hermes/Agentic Cron Orchestration Kit — Ship Checklist.md`
    62|    62|- Weekly pipeline note: `Projects/Hermes/MVP Pipeline — Week of 2026-04-20.md`
    63|    63|- CEO note: `Projects/Hermes/Agent Launch Closeout Kit — CEO Note.md`
    64|    64|- Factory note: `Projects/Hermes/Weekly MVP Factory.md`
    65|    65|
    66|    66|## Attachment priority
    67|    67|1. short walkthrough cut
    68|    68|2. proof-artifact still showing the key metric
    69|    69|3. verification screenshot
    70|    70|
    71|    71|Record the exact file or URL chosen in the launch execution log.
    72|    72|
    73|    73|## Closeout gate
    74|    74|The asset pack is only complete when:
    75|    75|- the launch copy matches the proved ship line
    76|    76|- the attachment choice is explicit
    77|    77|- the publish path has no hidden steps
    78|    78|- the execution log has a URL or a named publish-ready fallback state
    79|    79|- the weekly notes and CEO notes can be updated from the same artifact set without reinterpretation
    80|    80|
    81|    81|## Week-one proof surface
    82|    82|Use this real before/after case when filling the template:
    83|    83|- Product: `starter-kits/agentic-cron-orchestration-kit/`
    84|    84|- Source asset pack: `starter-kits/agentic-cron-orchestration-kit/launch/asset-pack.md`
    85|    85|- Source execution log: `starter-kits/agentic-cron-orchestration-kit/launch/launch-execution-log.md`
    86|    86|- Source publish runbook: `starter-kits/agentic-cron-orchestration-kit/launch/publish-runbook.md`
    87|    87|
    88|    88|## First operator move
    89|    89|Before writing new launch copy, fill the proof fields and closeout-state fields above. If those are vague, the launch surface is not ready and the next block should tighten proof or execution logging instead of adding more assets.
    90|    90|
    91|## Auth validation
    92|- Live browser auth audit: `starter-kits/agent-launch-closeout-kit/live-browser-auth-audit.md`
    93|- Rule: `x-access.json` is a marker, not publish proof. Trust the actual publish session.
    94|