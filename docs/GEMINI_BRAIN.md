# Google Gemini Brain Architecture & Continuous Equipment Manual

**Channel Identity:** *The Secret Place* (`@TheSecretPlace`)  
**Role:** Master Autonomous Creative & Editorial Intelligence Engine  
**Engine Implementation:** `pipeline/gemini_brain.py` & `scripts/gemini_brain.py`  
**Autonomous Workflow:** `.github/workflows/gemini_brain.yml` (Runs daily at `03:14 UTC`)  
**Cost Invariant:** Fail-closed $0.00 / month hard cost lock (`docs/ZERO_DOLLAR_LOCK.md`)

---

## 1. Executive Summary

To achieve full operational autonomy where video creation and scheduling continue uninterrupted without human presence or chat pings, **Google Gemini** has been equipped as the official **Autonomous Brain** of *The Secret Place*.

The Gemini Brain handles the cognitive and editorial functions previously performed by human prompt engineers:
1. **Scripture Demand Research:** Evaluates audience telemetry (`content/metrics.csv` & `content/research/channel_intelligence.json`) to select the optimal high-intent bedtime prayer chapters (e.g. Psalms 91, 23, 121, 27, 46, Isaiah 40).
2. **Devotional Script Authoring:** Drafts complete, reverent, 6-scene deep-dive scripts in `content/queue/*.md` adhering to the DOCOGA REELS v2 visual and kinetic typography specifications.
3. **Theological Exegesis:** Injects original commentary citing historical authorities (Charles Spurgeon's *The Treasury of David* and Matthew Henry's Commentary), ensuring structural immunity against YouTube's July 2026 "Inauthentic Content" policies.
4. **Companion Short Manifest Generation:** Automatically drafts and stages matching 9:16 vertical Short manifests in `content/shorts-queue/*.yml`.
5. **Automated Factchecking:** Mechanically extracts claims and binds the exact sha256 hash in `content/factcheck/*.md`.
6. **Queue Runway Monitoring & Auto-Replenishment:** Audits pending and approved jobs; whenever runway drops below 2 days, it autonomously stages the next scripture package.

---

## 2. The Brain's Six Core Equipment Invariants

```
┌─────────────────────────────────┬────────────────────────────────────────────────────────┐
│ Invariant                       │ Architectural Enforcement                              │
├─────────────────────────────────┼────────────────────────────────────────────────────────┤
│ **1. Permanent $0.00 Cost Lock**│ Free Gemini API tier (15 RPM / 1,500 RPD); standard    │
│                                 │ GitHub Actions runners; 100% public domain media.      │
├─────────────────────────────────┼────────────────────────────────────────────────────────┤
│ **2. Locked-in Voice: Charon**  │ Permanently locked to `gemini-3.8-flash-tts` (`Charon`).│
│                                 │ The Brain never auditions or alters voice models.      │
├─────────────────────────────────┼────────────────────────────────────────────────────────┤
│ **3. DOCOGA REELS v2 Standard** │ Inter-Black typography, sapphire glassmorphism cards,  │
│                                 │ radiant gold active-word sync, zero-latency transitions│
├─────────────────────────────────┼────────────────────────────────────────────────────────┤
│ **4. Faceless Channel Identity**│ Strict studio identity; zero mentions of John Azani or │
│                                 │ Azani John in any title, description, or script.       │
├─────────────────────────────────┼────────────────────────────────────────────────────────┤
│ **5. Originality & Citations**  │ Rigorous theological exposition citing Spurgeon/Henry; │
│                                 │ never outputs raw verbatim web scrapes.                │
├─────────────────────────────────┼────────────────────────────────────────────────────────┤
│ **6. Direct Public Publishing** │ Frontmatter configured with `privacy: public` for      │
│                                 │ unattended, direct-to-YouTube upload via produce.yml.  │
└─────────────────────────────────┴────────────────────────────────────────────────────────┘
```

---

## 3. The Continuous Equipment System (`pipeline/brain_equipment/`)

The Gemini Brain does not operate on hardcoded, fragile prompts. It is equipped with a modular knowledge repository loaded dynamically at runtime via `pipeline/brain_equipment/equipment_registry.py`:

```
pipeline/brain_equipment/
├── equipment_registry.py       # Module loader and dynamic prompt compiler
├── system_instruction.md       # Master editorial persona & behavioral directives
├── theological_rubric.md       # 6-movement devotional arc & exegesis standards
└── docoga_reels_rules.md       # Typography geometry, word sync, & asset queries
```

### 3.1 Equipping New Knowledge
To equip Google Gemini with updated research or new capabilities:
1. **Theological Updates:** Add new commentaries, liturgical prayers, or Bible translations into `theological_rubric.md`.
2. **Visual & Motion Upgrades:** Update `docoga_reels_rules.md` to refine font tracking, padding, or color grading rules.
3. **Prompt Enhancements:** Update `system_instruction.md` with new retention heuristics or audience insights.
4. **Validation:** Run `python scripts/gemini_brain.py --equip` to verify module integrity and byte sizes.

---

## 4. The Autonomous Brain Cycle (How it Operates Offline)

```
                            THE AUTONOMOUS BRAIN CYCLE
                                        │
           ┌────────────────────────────┴────────────────────────────┐
           ▼                                                         ▼
  STEP 1: RUNWAY AUDIT                                      STEP 2: DEMAND SELECTION
  • scripts/auto_scheduler.py                               • scripts/continuous_research.py
  • Evaluates approved jobs count                           • Scans unreleased scripture roadmap
  • Triggered if runway < 2.0 days                          • Targets highest nighttime search intent
           │                                                         │
           └────────────────────────────┬────────────────────────────┘
                                        ▼
                           STEP 3: DEEP-DIVE DRAFTING
                           • Invokes Google Gemini API with equipment
                           • 6 scenes: Hook, Green Pastures, Soul
                             Restoration, Valley of Shadows, Banqueting
                             Table, Covenant Blessing & Prayer Benediction
                           • Embeds verified public domain asset queries
                                        ▼
                           STEP 4: COMPANION SHORT CREATION
                           • Authors matching YAML manifest in
                             content/shorts-queue/*.yml
                           • Sets status: approved and privacy: public
                                        ▼
                           STEP 5: MECHANICAL FACTCHECKING
                           • scripts/factcheck.py generates worksheet
                           • Binds source sha256 to content/factcheck/*.md
                                        ▼
                           STEP 6: GIT COMMIT & SCHEDULE
                           • .github/workflows/gemini_brain.yml commits
                             new jobs with [skip ci]
                           • Armed for next scheduled produce.yml cron!
```

---

## 5. CLI Usage & Testing

```bash
# Audit the Gemini Brain status, loaded equipment, and queue runway:
python scripts/gemini_brain.py --audit

# Inspect loaded brain knowledge modules:
python scripts/gemini_brain.py --equip

# Force generation of the next scripture devotional package:
python scripts/gemini_brain.py --generate-next

# Auto-replenish queue if runway is below threshold (e.g. 2.0 days):
python scripts/gemini_brain.py --auto-replenish --min-runway 2.0
```

---

## 6. Offline Safety & Deterministic Fail-Safe

When executing in environments where `GEMINI_API_KEY` is not present (such as local unit tests or offline sandboxes), the Gemini Brain automatically activates its **Equipped Deterministic Synthesizer**. This ensures that tests, CI workflows, and staging validations remain 100% green and deterministic without external API dependencies, while seamlessly utilizing live Gemini models whenever the key is provided in GitHub Secrets.
