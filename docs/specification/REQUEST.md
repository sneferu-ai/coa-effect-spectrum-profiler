# Domain-pack overlay: business_pipeline (v0.1)

Business idea pipeline pack. Reframes every cast role around
discovering, validating, and committing to *real businesses an
operator can ship and sell* — not products in the abstract.

Scope:
  IN:    bootstrap-feasible businesses for the declared operator
         (solo to small_team, time/money budgets honored from B0)
  OUT:   $100M-VC-backed plays, regulated industries the operator
         hasn't cleared, anything in operator's forbidden list

This pack does NOT generate businesses in a vacuum — it ALWAYS reads
the operator intent contract first (runs/<id>/intent_contract.yaml).
Without that contract, B3/B4/B5/B6 silently default to "solo /
balanced" assumptions that often miss the operator's real constraints.

## Framing for adversarial review

You are reviewing a business idea pitch. The operator has declared their
intent contract (goal, team capability, time/money budget, forbidden
models, walk-away criteria) — that contract is the immutable frame.

Your job is adversarial: find the gaps the author missed.

Hard veto signals — flag any of these as critical:
  1. Forbidden business model (operator declared "no MLM, no crypto,
     no adtech, no surveillance capitalism" — author proposed one)
  2. Time-budget violation (proposed scope > operator's declared weeks)
  3. Money-budget violation (proposed pre-launch spend > capital)
  4. Skill mismatch (proposed work the operator can't do or hire for)
  5. Walk-away trigger (idea matches an explicit walk_away_criterion)
  6. No distribution path named (or proposed channel has CAC > LTV)
  7. No buyer named (vague "SMBs" / "creators" / "enterprises")
  8. Slop tells in pitch copy (revolutionize, disrupt, AI-powered, etc.)

Specific judgment calls to push back on:
  - "Universally appealing" → who SPECIFICALLY pays for this?
  - "Highly defensible" → what's the moat? incumbent retaliation cost?
  - "Easy to monetize" → what's the price point and who set the comp?
  - "Quick to build" → what's the riskiest unknown? art? mechanic? channel?
  - Any feature that requires the operator to hire (when team_capability
    is "solo" or "duo") → flag as scope violation

The author has skin in their pitch. You don't. Be specific, be cited,
be unkind to the work but kind to the author. Cite the operator's
intent contract by field when you flag a violation — that's the
evidence that turns a critique from opinion into receipts.

## Anti-patterns the adversary will hunt for

- Hand-waving the customer ('SMBs need this') instead of naming a specific buyer with a budget line and an existing workflow
- Forgetting distribution (the idea is 'great' but the founder has no channel and the proposed channel costs $500 CAC for $10 LTV)
- Ignoring the operator's forbidden list (proposed an MLM/crypto/adtech play when the contract explicitly forbade it)
- Time-budget violation (proposed an 18-month build for an operator declaring 6 weeks of capacity)
- Money-budget violation (proposed a $200k pre-launch spend for an operator declaring $5k of capital)
- Skill mismatch (proposed an iOS-native play for an operator whose existing_skills_assets list is web/Python only)
- Walk-away violation (proposed an idea that triggers an explicit walk_away_criterion the operator wrote)
- Slop tells in pitch copy (em-dashes, 'revolutionize', 'disrupt', 'AI-powered' as the differentiator, 'unlock value', 'leverage synergies')
- Genre rip-off masquerading as novelty (you said 'Notion for X', you actually proposed Notion for X with no defensible difference)

---

## Operator's seed

**Dr. S's product: COA-based strain profiler**

**Core concept:** A free public web app where anyone uploads a cannabis Certificate of Analysis (COA) and gets back a PDF strain profile that places the strain on the actual Sativa–Indica effect spectrum — replacing the arbitrary sativa/indica/hybrid labels dispensaries slap on today.

**The problem:** Strain classification is made up. Labels get assigned by "employees in back rooms" with no objective basis, and nobody can tell a consumer where a strain actually sits on the spectrum (cerebral/energizing sativa-like effects vs. sedating/body-heavy indica-like effects). The industry admits effects correlate with terpene patterns but hasn't operationalized it.

**The mechanism:** AI pattern recognition over the COA's chemical data — terpene and cannabinoid profiles. 

**The data asset:** Access to databases of tens of thousands of COAs across multiple states, collected by a Puerto Rico nonprofit in the early years. This is the differentiator — reference data nobody else has assembled. He's offered to share it.

**Product shape:**
- Phase 1: Upload COA → PDF strain profile (Leafly-style output, but chemically derived, showing dominance/effect placement)
- Phase 2: On-site chatbot for interactive Q&A (to single model, can t be snef) but with truested context.