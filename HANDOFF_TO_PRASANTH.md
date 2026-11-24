# Hand-off to Prasanth (Role B)
**From:** Ganesh (Role A — Django Foundation, Data Layer & Scheduling Engine)  
**Date:** November 2026  
**Status:** Foundation & Scheduling Engine Complete, 18/18 Tests Passing  

---

## 1. Executive Summary & Foundation Status

The Django foundation, database models, initial migrations, repeatable seed data generator, and deterministic scheduling engine have been successfully implemented, verified, and tested.

### What is in place:
1. **Django Project Skeleton & Settings (`blockplanner/`)**:
   - Registered all 5 apps: `core`, `planner`, `requests_app`, `dashboard`, `ai`.
   - Configured `TEMPLATES` directory pointing to `BASE_DIR / 'templates'`.
   - Configured `STATIC_URL` and `STATICFILES_DIRS`.
   - Safe environment variable loading for optional `GEMINI_API_KEY` and `GEMINI_MODEL`.
2. **Database Models & Initial Migrations**:
   - `core`: `Section`, `Asset`, `TrafficSlot`.
   - `requests_app`: `MaintenanceRequest` (ready for your forms, CRUD views, and `seed_requests`).
   - `planner`: `PlanRun`, `Block`.
   - `ai`: `AICache` (ready for optional caching if implemented).
   - Initial migrations applied cleanly to SQLite (`db.sqlite3`).
3. **Root URL Routing (`blockplanner/urls.py`)**:
   - `/` &rarr; `dashboard.urls`
   - `/core/` &rarr; `core.urls`
   - `/requests/` &rarr; `requests_app.urls`
   - `/planner/` &rarr; `planner.urls`
   - `/ai/` &rarr; `ai.urls`
   - `/admin/` &rarr; Django Admin

---

## 2. Shared Integration Interfaces

As agreed in the technical contract, you can directly import and call the following functions in `dashboard` and `requests_app`:

### A. Latest Plan Query for Dashboard
```python
from planner.models import PlanRun

latest_plan = (
    PlanRun.objects
    .filter(is_baseline=False, is_whatif=False)
    .order_by('-created_at')
    .first()
)
```
If `latest_plan` is `None`, show your dashboard empty state with a link to `/planner/generate/`.

### B. What-If Simulation Engine Call
For your What-If page (`dashboard/whatif` or `dashboard/`):
```python
from planner.engine import run_plan

whatif_run = run_plan(
    horizon_days=7,
    blocked_section_ids=[selected_section_id],  # IDs of sections simulated as blocked
    label=f"What-If: Section {section.code} Blocked",
    persist_status=False  # Crucial: Does NOT alter persistent request statuses
)
```
- `whatif_run.is_whatif` will be `True`.
- Blocked sections receive zero blocks; their requests are automatically deferred with reasons in `whatif_run.deferred_reasons`.
- Section `is_blocked` flag in the DB is NOT modified.

### C. First-Come-First-Served (FCFS) Baseline
```python
from planner.engine import run_baseline

baseline_run = run_baseline(horizon_days=7)
# Saves PlanRun with is_baseline=True and never mutates MaintenanceRequest.status
```

### D. Reading Block Score Breakdown & Deterministic Explanation
Every `Block` instance stores detailed scoring parameters in `block.score_breakdown`:
```python
# block.score_breakdown schema:
{
    "traffic": 4.0,              # Sum of hourly traffic density across window
    "day_penalty": 0.5,          # W_DAY * day
    "total": 4.5,                # Total candidate cost
    "window": "Day 1, 01:00 - 04:00",
    "slots_considered": 32,      # Valid (day, hour) candidate slots evaluated
    "avg_traffic_that_day": 4.71 # Average density on that section on that day
}
```
You can use these values directly for deterministic explanations in `ai.gemini.explain_block(block)`:
```python
def explain_block(block):
    breakdown = block.score_breakdown or {}
    traffic = breakdown.get('traffic', block.cost)
    window = breakdown.get('window', f"Day {block.day}")
    slots = breakdown.get('slots_considered', 'multiple')
    return (
        f"Scheduled during {window} based on minimum traffic disruption "
        f"(density impact: {traffic}). Evaluated {slots} candidate windows."
    )
```

---

## 3. Algorithm & Architecture Notes for Presentation

### Scheduling Engine Architecture
The scheduler is located in `planner/engine.py` and implements a **deterministic priority-and-cost scheduling algorithm** without third-party solver dependencies:

1. **Hard Constraints Enforced**:
   - **No Midnight Crossing:** $start\_hour + duration \le 24$ (exclusive end hour max 24).
   - **Deadline Constraint:** $day \le request.deadline\_day$ and $day < horizon\_days$.
   - **Section Availability:** Sections with `is_blocked=True` or included in `blocked_section_ids` receive 0 blocks.
   - **Non-overlapping Blocks:** No two maintenance blocks on the same section and day can overlap in time.
   - **Safety Gap Buffer:** Strict minimum 1-hour spacing buffer between consecutive blocks ($MIN\_GAP\_HOURS = 1$).
   - **Maximum Daily Limit:** Maximum 3 blocks per section per day ($MAX\_BLOCKS\_PER\_SECTION\_DAY = 3$).

2. **Cost Objective Function**:
   $$\text{Cost} = W_{\text{TRAFFIC}} \cdot \text{traffic\_sum} + W_{\text{DAY}} \cdot \text{day}$$
   Where $W_{\text{TRAFFIC}} = 1.0$ and $W_{\text{DAY}} = 0.5$.
   Ties broken deterministically: earlier day, then earlier start hour.

3. **High-Performance Prefix Sums ($O(1)$ Window Queries)**:
   A 2D matrix of prefix sums is built per section and day:
   $$P[day][h] = \sum_{k=0}^{h-1} \text{density}(day, k)$$
   Any candidate window $[start, end)$ traffic sum is queried in $O(1)$:
   $$\text{traffic\_sum} = P[day][end] - P[day][start]$$

4. **Time Complexity**:
   $$O(R \log R + S \cdot D \cdot H + R \cdot D \cdot H)$$
   Where $R$ = number of requests, $S = 5$ sections, $D = 7$ horizon days, $H = 24$ hours.
   Executes in under 20ms for standard workloads. Zero conflicts guaranteed.

---

## 4. Benchmark Verification Results

Running `python manage.py benchmark` outputs:

| Scenario | FCFS Traffic Impact | Optimized Traffic Impact | Disruption Reduction % | Conflicts |
| :--- | :--- | :--- | :--- | :--- |
| **Normal** (15 requests) | 218.0 | 59.0 | **72.9%** | Base: 0 / Opt: 0 |
| **Overloaded** (9 heavy requests) | 149.0 | 96.0 | **35.6%** | Base: 0 / Opt: 0 |
| **Blocked Section** (LDH-SIR down) | 51.0 | 17.0 | **66.7%** | Base: 0 / Opt: 0 |

---

## 5. File Ownership & Next Steps for Prasanth

### Files Owned by You (Role B):
- `requests_app/` (forms, admin, views, URLs, templates, tests, `seed_requests`)
- `dashboard/` (views, URLs, templates, tests, timeline grid)
- `ai/` (optional Gemini service with deterministic fallback, views, URLs, templates, tests)
- `templates/base.html` (root template with navigation and messages block)
- `static/css/app.css`
- `README.md`
- `HANDOFF_TO_GANESH.md`

### Commands You Can Run Immediately:
```bash
# Seed synthetic sections, assets, and 840 traffic slots
python manage.py seed_data

# Run baseline and optimized benchmark
python manage.py benchmark

# Run test suite
python manage.py test core planner
```

All core and planner endpoints (`/core/sections/`, `/core/assets/`, `/planner/`, `/planner/generate/`, `/planner/compare/`) are active and functioning.
