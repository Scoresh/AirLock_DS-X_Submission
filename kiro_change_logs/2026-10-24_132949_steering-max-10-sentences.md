# Change summary logging: switch from exactly-10 to max-10 sentences

**Files changed:**
- `.kiro/steering/change-logging.md`

Updated the change-logging steering rule so summaries are capped at a maximum of 10 sentences rather than requiring exactly 10. Changed the primary rule line from "MUST be exactly 10 sentences" to "MUST be at most 10 sentences." Also updated the trailing content-description line to read "up to 10 sentences." This makes short, trivial changes easier to log without padding. No code behavior was affected; this is a documentation/instruction change only. The hook and agent config were left untouched. The steering file continues to load automatically under the default agent.
