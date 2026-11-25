# 🚆 AI-Powered Automatic Block Planning

A Django-based intelligent railway maintenance scheduling system that optimizes maintenance block assignments across corridor sections using a **deterministic priority-and-cost scheduling engine** with optional **Google Gemini AI** explanations.

## Project Overview

Railway maintenance requires "blocks" — scheduled time windows where a track section is taken out of service for repair work. This system automates the planning of these blocks to **minimize disruption to train traffic** while satisfying hard operational constraints.

### Key Features

- **Deterministic Scheduling Engine** — Priority-based, cost-optimized scheduling with O(1) prefix-sum traffic lookups
- **Zero Conflicts Guaranteed** — Hard constraints enforce no overlap, midnight boundaries, deadlines, safety gaps, and daily limits
- **FCFS Baseline Comparison** — First-Come-First-Served baseline for benchmarking optimization improvements
- **What-If Simulation** — Block a section and instantly see the impact on the schedule (non-destructive)
- **Visual Timeline Grid** — 7-day × 24-hour color-coded dashboard showing all scheduled blocks
- **AI Explanations** — Deterministic rule-based explanations with optional Gemini API enhancement
- **Full CRUD** — Create, edit, delete, and filter maintenance requests through the web UI

---

## Architecture

```
blockplanner/          # Django project settings & root URL config
├── core/              # Sections, Assets, TrafficSlots (Role A — Ganesh)
├── planner/           # PlanRun, Block, scheduling engine, benchmark (Role A)
├── requests_app/      # MaintenanceRequest CRUD, forms, seed_requests (Role B — Prasanth)
├── dashboard/         # Dashboard home, timeline grid, What-If analysis (Role B)
├── ai/                # Gemini AI explanations with deterministic fallback (Role B)
├── templates/         # Shared base template
└── static/css/        # Custom styles
```

### Scheduling Algorithm

The engine (`planner/engine.py`) implements a **deterministic priority-and-cost scheduling algorithm**:

1. **Priority Ordering**: Requests sorted by priority (descending), then deadline (ascending)
2. **Cost Function**: `Cost = W_TRAFFIC × traffic_sum + W_DAY × day` (W_TRAFFIC=1.0, W_DAY=0.5)
3. **O(1) Traffic Lookups**: 2D prefix sums enable constant-time window traffic queries
4. **Hard Constraints**:
   - No midnight crossing (start + duration ≤ 24)
   - Deadline respect (day ≤ deadline_day)
   - Section availability (blocked sections get zero blocks)
   - Non-overlapping blocks on same section/day
   - Minimum 1-hour safety gap between blocks
   - Maximum 3 blocks per section per day

**Time Complexity**: O(R log R + S·D·H + R·D·H) — executes in <20ms for standard workloads.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Django 5.0+

### Setup

```bash
# 1. Clone and install
git clone <repo-url>
cd AI-Powered-Automatic-Block-Planning
pip install -r requirements.txt

# 2. Apply migrations
python manage.py migrate

# 3. Seed railway data (5 sections, 28 assets, 840 traffic slots)
python manage.py seed_data

# 4. Seed maintenance requests (15 synthetic requests)
python manage.py seed_requests

# 5. Run the development server
python manage.py runserver
```

### Quick Workflow

1. Visit `http://127.0.0.1:8000/` — Dashboard (empty state initially)
2. Go to **Requests** → create or seed maintenance requests
3. Go to **Generate Plan** → run the optimization engine
4. Return to **Dashboard** to see the schedule timeline and KPIs
5. Try **What-If** to simulate blocking a section
6. Use **Comparison** to compare FCFS baseline vs. optimized schedule

---

## Management Commands

| Command | Description |
|---|---|
| `python manage.py seed_data` | Seeds 5 sections, 28 assets, 840 traffic slots (repeatable, seed=42) |
| `python manage.py seed_requests` | Creates 15 synthetic maintenance requests |
| `python manage.py seed_requests --reset --count 20` | Reset and create 20 requests |
| `python manage.py benchmark` | Runs normal, overloaded, and blocked-section benchmark scenarios |
| `python manage.py test core planner requests_app dashboard ai` | Run the full test suite |

---

## URL Routes

| URL | View | Description |
|---|---|---|
| `/` | Dashboard Home | KPI cards, timeline grid, section overview |
| `/whatif/` | What-If Analysis | Simulate blocking a section |
| `/requests/` | Request List | All maintenance requests with filters |
| `/requests/create/` | Create Request | New maintenance request form |
| `/requests/<pk>/edit/` | Edit Request | Modify existing request |
| `/requests/<pk>/delete/` | Delete Request | Confirm and delete request |
| `/core/sections/` | Section List | All railway sections |
| `/core/sections/<code>/` | Section Detail | Traffic heatmap + assets |
| `/core/assets/` | Asset List | All assets with filters |
| `/planner/` | Plan Run List | History of plan runs |
| `/planner/generate/` | Generate Plan | Run the scheduling engine |
| `/planner/runs/<pk>/` | Run Detail | Blocks, scores, deferred items |
| `/planner/compare/` | Compare Plans | Baseline vs. Optimized KPI comparison |
| `/ai/explain/<block_id>/` | AI Explain (JSON) | Deterministic/Gemini explanation |
| `/admin/` | Django Admin | Admin interface |

---

## AI Explanation System

The `/ai/explain/<block_id>/` endpoint returns a JSON response with scheduling explanations:

```json
{
  "block_id": 1,
  "section": "LDH-SIR",
  "asset": "Up Main Line",
  "window": "Day 0, 01:00 - 04:00",
  "explanation": "Scheduled during Day 0, 01:00 - 04:00 based on minimum traffic disruption...",
  "source": "deterministic",
  "score_breakdown": {
    "traffic": 4.0,
    "day_penalty": 0.0,
    "total": 4.0,
    "window": "Day 0, 01:00 - 04:00",
    "slots_considered": 32,
    "avg_traffic_that_day": 4.71
  }
}
```

For Gemini-enhanced explanations, set `GEMINI_API_KEY` environment variable and add `?use_gemini=1` to the URL.

---

## Benchmark Results

| Scenario | FCFS Impact | Optimized Impact | Reduction | Conflicts |
|---|---|---|---|---|
| Normal (15 requests) | 218.0 | 59.0 | **72.9%** | 0 / 0 |
| Overloaded (9 heavy) | 149.0 | 96.0 | **35.6%** | 0 / 0 |
| Blocked Section | 51.0 | 17.0 | **66.7%** | 0 / 0 |

---

## Configuration

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | (dev key) | Django secret key |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `GEMINI_API_KEY` | (empty) | Google Gemini API key for AI explanations |
| `GEMINI_MODEL` | `gemini-1.5-flash` | Gemini model name |

### Engine Constants (`planner/config.py`)

| Constant | Value | Description |
|---|---|---|
| `W_TRAFFIC` | 1.0 | Traffic density weight in cost function |
| `W_DAY` | 0.5 | Day penalty weight in cost function |
| `MAX_BLOCKS_PER_SECTION_DAY` | 3 | Hard limit on blocks per section per day |
| `MIN_GAP_HOURS` | 1 | Minimum safety gap between consecutive blocks |
| `HORIZON_DAYS` | 7 | Default planning horizon |

---

## Project Team

| Role | Owner | Responsibility |
|---|---|---|
| **Role A** | Ganesh | Django foundation, data models, scheduling engine, benchmark |
| **Role B** | Prasanth | Request CRUD, dashboard, AI explanations, templates, README |

---

## License

Academic project — Northern Railways maintenance block planning system.
