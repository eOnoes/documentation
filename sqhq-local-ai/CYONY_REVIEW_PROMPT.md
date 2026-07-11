# Cyony — Property Brain Training Data Review

> **From:** Eddie
> **Date:** 2026-07-06
> **Priority:** HIGH — This is the final step before we fine-tune the AI model

---

## What I Need From You

I generated 3,000 training examples for Property Brain (our property management AI). Before we train the model, I need you to validate that the data is correct. Your domain knowledge is the quality gate.

**Bottom line:** Review the training data, approve what's correct, flag what's wrong, and save your review.

---

## Where Everything Is

| What | Location |
|------|----------|
| Training data (10 sections) | `/root/sqhq-local-ai/data/review_sections/` |
| Review instructions | `/root/agents/shared/shared-agent-bus/agents/Cyony.109/inbox/training-data-review-sections.md` |
| Original knowledge response | `/root/sqhq-local-ai/data/cyony-knowledge-response.md` |
| Database schema | `/root/sqhq-local-ai/data/schema.json` |

---

## The 10 Sections

| # | Category | File | Examples | Priority |
|---|----------|------|----------|----------|
| 1 | Edge Cases | `section_01_edge_cases.jsonl` | 200 | Medium |
| 2 | Expenses | `section_02_expenses.jsonl` | 300 | High |
| 3 | **Financial** | `section_03_financial.jsonl` | 500 | **CRITICAL** |
| 4 | **Property Q&A** | `section_04_property_qa.jsonl` | 500 | **CRITICAL** |
| 5 | Reminders | `section_05_reminders.jsonl` | 200 | Medium |
| 6 | Reporting | `section_06_reporting.jsonl` | 300 | High |
| 7 | Tax | `section_07_tax.jsonl` | 200 | High |
| 8 | Tenants | `section_08_tenants.jsonl` | 300 | High |
| 9 | Vendors | `section_09_vendors.jsonl` | 200 | Medium |
| 10 | Work Orders | `section_10_work_order.jsonl` | 300 | High |

---

## Recommended Review Order

**Start with CRITICAL sections first:**

1. **Section 3: Financial** (500 examples) — Numbers must be right
2. **Section 4: Property Q&A** (500 examples) — Property names must be correct
3. **Section 2: Expenses** (300 examples) — Categories and tax buckets
4. **Section 8: Tenants** (300 examples) — Lease and payment rules
5. **Section 10: Work Orders** (300 examples) — Vendor and priority rules
6. **Section 6: Reporting** (300 examples) — Metrics and calculations
7. **Section 7: Tax** (200 examples) — Deductions and 1099s
8. **Section 9: Vendors** (200 examples) — Service types and contacts
9. **Section 5: Reminders** (200 examples) — Recurrence and priorities
10. **Section 1: Edge Cases** (200 examples) — Error handling

---

## How to Review Each Section

### Step 1: Read the section file

Each file is JSONL (one JSON object per line). Each line is a training example with:
- `instruction` — The question the user asks
- `response` — The answer the AI gives
- `category` — Which category it belongs to

### Step 2: Validate each example

For each example, check:

**1. Property Names**
- Are they Eddie's actual properties? (7197 Grapetree, etc.)
- NOT made-up names like "Willow Creek Estates" or "Crystal Lake Apartments"

**2. Business Rules**
- Late fee: $50/week late (NOT $100, NOT percentage)
- Payment methods: Cash, Venmo, Zelle, CashApp, BankTransfer (NO CHECKS)
- Security deposit: TN max 2 months, AR no limit
- Eviction: TN 14 days, AR 3 days

**3. Domain Knowledge**
- Tennessee vs Arkansas laws
- Memphis-specific issues
- Seasonal patterns

**4. Workflows**
- Adding properties
- Recording rent
- Tracking expenses
- Creating work orders

**5. No Hallucinations**
- Correct property counts (3 properties)
- Correct amounts (based on real data)
- No invented tenants, vendors, etc.

### Step 3: Mark each example

For each example, mark as:
- ✅ **APPROVED** — Correct, use as-is
- ⚠️ **FIX** — Needs correction (explain what to change)
- ❌ **REJECT** — Wrong, delete it

### Step 4: Save your review

Save your review to:
```
/root/sqhq-local-ai/data/review_sections/section_XX_CATEGORY_review.md
```

Replace `XX` with the section number and `CATEGORY` with the category name.

---

## Review Format

For each section, create a review file like this:

```markdown
# Section 3: Financial — Review

## Summary
- Total examples: 500
- Approved: 450 (90%)
- Fixed: 40 (8%)
- Rejected: 10 (2%)

## Issues Found

### 1. Wrong property names
- Example #45: "Willow Creek Estates" → Should be "7197 Grapetree"
- Example #123: "Crystal Lake Apartments" → Should be "Memphis Rental"

### 2. Wrong late fee amount
- Example #67: "Late fee is $100" → Should be "$50/week"

### 3. Missing payment method restriction
- Example #89: "Accepts checks" → Should be "NO CHECKS"

## Approved Examples (sample)
- Example #1: ✅ Correct
- Example #2: ✅ Correct
- Example #3: ✅ Correct

## Fixed Examples (sample)
- Example #45: Fixed property name
- Example #67: Fixed late fee amount

## Rejected Examples (sample)
- Example #100: Hallucinated tenant name
```

---

## Time Estimate

| Section | Examples | Time |
|---------|----------|------|
| Financial (500) | 30 min |
| Property Q&A (500) | 30 min |
| Expenses (300) | 20 min |
| Tenants (300) | 20 min |
| Work Orders (300) | 20 min |
| Reporting (300) | 20 min |
| Tax (200) | 15 min |
| Vendors (200) | 15 min |
| Reminders (200) | 15 min |
| Edge Cases (200) | 15 min |
| **Total** | **3,000** | **~3 hours** |

---

## Key Reference Data

### Eddie's Properties
- 7197 Grapetree — Memphis, TN (House, 3BR)
- Manila Rental — Manila, AR
- Osceola Rental — Osceola, AR

### Business Rules
- Late fee: $50/week late
- Payment methods: Cash, Venmo, Zelle, CashApp, BankTransfer (NO CHECKS)
- Security deposit: TN max 2 months, AR no limit
- Eviction: TN 14 days, AR 3 days

### Vendor
- Sergio — Plumbing, Electrical, Structural

---

## What Happens After You Review

1. I'll fix any examples you marked as ⚠️ FIX
2. I'll delete any examples you marked as ❌ REJECT
3. I'll combine all ✅ APPROVED examples into one training dataset
4. We'll fine-tune Qwen2.5-3B on the approved data
5. Deploy with llama-server + RAG

---

## Questions?

If you're unsure about something, mark it as ⚠️ FIX and explain the issue. I'll handle the corrections.

---

**Take your time. Accuracy matters more than speed.**

— Eddie
