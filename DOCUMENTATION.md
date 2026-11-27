# AI-Powered Automatic Block Planning — Complete System Documentation

This document provides a detailed technical reference for every component of the **AI-Powered Automatic Block Planning** Django application.

---

## 1. System Overview

**AI-Powered Automatic Block Planning** is a Django web application for railway operations controllers, section engineers, and maintenance planners. It automates the scheduling of railway maintenance "blocks" (time windows where a track section is taken out of service for Track, OHE, or Signaling maintenance) to **minimize train traffic disruption** while enforcing **zero schedule conflicts** and strict operational constraints.

### Tech Stack
- **Backend Framework:** Django 5 (Python)
- **Database:** SQLite (`db.sqlite3`)
- **Frontend:** Server-rendered Django Templates + CSS Custom Properties (`:root` / `html.dark`) + Vanilla JavaScript
- **AI Integration:** Optional Google Gemini API (`ai/gemini.py`) with SHA-256 prompt caching (`AICache`) and deterministic rule-based fallbacks

---

## 2. Project Directory & File Reference

```text
AI-Powered-Automatic-Block-Planning/
├── blockplanner/                    # Django project configuration
│   ├── settings.py                  # Installed apps, DB, static files, auth settings
│   ├── urls.py                      # Root URL router (auth shortcuts + app namespaces)
│   ├── asgi.py / wsgi.py            # ASGI / WSGI entrypoints
├── core/                            # Railway infrastructure & user accounts
│   ├── models.py                    # UserAccount, Section, Asset, TrafficSlot
│   ├── views.py                     # Section/asset views + login/signup/logout/account
│   ├── urls.py                      # /core/* routes
│   ├── admin.py                     # Admin registration for core models
│   ├── management/commands/
│   │   └── seed_data.py             # Seeds 5 sections, 28 assets, 840 traffic slots
│   ├── templates/
│   │   ├── base.html                # Master layout, theme tokens, navbar, AI chatbot
│   │   └── core/                    # login, signup, account, section_list, section_detail, asset_list
│   └── tests.py                     # Core & auth tests
├── requests_app/                    # Maintenance request CRUD & seeding
│   ├── models.py                    # MaintenanceRequest
│   ├── forms.py                     # MaintenanceRequestForm (server-side validation)
│   ├── views.py                     # List (filtered), create, edit, delete
│   ├── urls.py                      # /requests/* routes
│   ├── admin.py                     # MaintenanceRequestAdmin
│   ├── management/commands/
│   │   └── seed_requests.py         # Seeds synthetic maintenance requests
│   ├── templates/requests_app/      # request_list, request_form, request_confirm_delete
│   └── tests.py                     # Request CRUD & form validation tests
├── planner/                         # Deterministic scheduling engine & plan comparison
│   ├── config.py                    # W_TRAFFIC, W_DAY, MAX_BLOCKS_PER_SECTION_DAY, MIN_GAP_HOURS
│   ├── models.py                    # PlanRun, Block
│   ├── engine.py                    # O(1) prefix-sum cost-optimized & FCFS baseline engines
│   ├── views.py                     # run_list, generate_plan, run_detail, compare_plans
│   ├── urls.py                      # /planner/* routes
│   ├── admin.py                     # PlanRun & Block admin
│   ├── management/commands/
│   │   └── benchmark.py             # Runs normal, overloaded, and blocked-section benchmarks
│   ├── templates/planner/           # run_list, generate, run_detail, compare
│   └── tests.py                     # Engine constraint, cost, and comparison tests
├── dashboard/                       # Main dashboard, 7x24 timeline & What-If simulator
│   ├── views.py                     # dashboard_home, whatif_view
│   ├── urls.py                      # / and /whatif/
│   ├── templates/dashboard/         # home.html, whatif.html
│   └── tests.py                     # Dashboard & non-destructive What-If tests
├── ai/                              # AI block explanations & interactive chat assistant
│   ├── models.py                    # AICache
│   ├── gemini.py                    # explain_block(), explain_block_with_gemini()
│   ├── views.py                     # explain_view (GET), chat_view (POST)
│   ├── urls.py                      # /ai/explain/<id>/, /ai/chat/
│   └── tests.py                     # AI endpoint & fallback tests
├── static/css/app.css               # Responsive, print, and shared form styles
├── manage.py                        # Django CLI entrypoint
├── requirements.txt                 # Python dependencies
├── README.md                        # Quick-start guide
├── HANDOFF_TO_PRASANTH.md           # Role A handoff notes
└── HANDOFF_TO_GANESH.md             # Role B handoff notes
```

---

## 3. Database Schema & Models

### 3.1 `core/models.py`
| Model | Key Fields | Purpose |
|---|---|---|
| `UserAccount` | `user` (OneToOne `User`), `employee_id` (unique), `role` (`PLANNER`, `SECTION_ENGINEER`, `CHIEF_CONTROLLER`, `ADMIN`), `department`, `phone_number`, `is_approved`, `created_at`, `last_login_at` | Stores railway staff profile, role, and approval status. |
| `Section` | `name`, `code` (unique, e.g., `LDH-SIR`), `length_km`, `is_blocked` | Represents a railway corridor section. Blocked sections receive zero scheduled blocks. |
| `Asset` | `section` (FK `Section`), `name`, `asset_type` (`TRACK`, `OHE`, `SIGNAL`), `health_score` (default `80`) | Physical track/OHE/signal asset belonging to a section. |
| `TrafficSlot` | `section` (FK `Section`), `day` (`0–6`), `hour` (`0–23`), `density` (`0–10`) | Hourly train traffic density per section/day (`unique_together = ('section', 'day', 'hour')`). |

### 3.2 `requests_app/models.py`
| Model | Key Fields | Purpose |
|---|---|---|
| `MaintenanceRequest` | `asset` (FK `Asset`), `description`, `duration_hours` (`1–8`), `priority` (`1–5`, 5 highest), `deadline_day` (`0–6`), `status` (`PENDING`, `SCHEDULED`, `DEFERRED`), `source` (`FORM`, `NL`, `WHATIF`), `created_at` | Work item requesting a maintenance block. Ordered by `['-priority', 'deadline_day', 'created_at']`. Exposes `.section` property via `asset.section`. |

### 3.3 `planner/models.py`
| Model | Key Fields | Purpose |
|---|---|---|
| `PlanRun` | `label`, `created_at`, `horizon_days` (default `7`), `is_baseline`, `is_whatif`, `total_requests`, `scheduled_count`, `deferred_count`, `conflicts`, `total_traffic_impact`, `availability_pct`, `deferred_reasons` (`JSONField`) | Metadata and aggregate KPIs for a single execution of the scheduling engine. |
| `Block` | `plan_run` (FK `PlanRun`), `request` (FK `MaintenanceRequest`), `section` (FK `Section`), `day` (`0–6`), `start_hour` (`0–23`), `end_hour` (exclusive, max `24`), `cost`, `score_breakdown` (`JSONField`), `explanation` (`TextField`) | An individual scheduled maintenance window assigned to a `PlanRun`. |

### 3.4 `ai/models.py`
| Model | Key Fields | Purpose |
|---|---|---|
| `AICache` | `key` (SHA-256 hex, `max_length=64`, unique), `response`, `created_at` | Caches Gemini API responses to prevent duplicate external API calls. |

---

## 4. Deterministic Scheduling Engine (`planner/`)

### 4.1 Configuration (`planner/config.py`)
- `W_TRAFFIC = 1.0` — Weight applied to total hourly traffic density inside the block window.
- `W_DAY = 0.5` — Weight applied to the day index (encourages earlier completion when traffic is tied).
- `MAX_BLOCKS_PER_SECTION_DAY = 3` — Maximum blocks allowed on one section on any single day.
- `MIN_GAP_HOURS = 1` — Minimum required buffer between consecutive blocks on the same section/day.
- `HORIZON_DAYS = 7` — Default 7-day planning window (`Day 0` to `Day 6`).
- `HOURS_PER_DAY = 24` — 24-hour daily grid.

### 4.2 Algorithm & Complexity (`planner/engine.py`)
1. **2D Prefix Sums (`_build_traffic_prefix_sums`):** Precomputes cumulative hourly traffic density for every section and day in $O(S \cdot D \cdot H)$ time, allowing any candidate window `[start_hour, end_hour)` traffic sum to be queried in **$O(1)$** via `prefix[d][end] - prefix[d][start]`.
2. **Ordering:**
   - **Optimized Mode:** Sorts requests by `(-priority, deadline_day, created_at)`.
   - **Baseline Mode (`is_baseline=True`):** First-Come-First-Served (FCFS) by `created_at`.
3. **Cost Function:**
   $$\text{Cost} = (W_{\text{TRAFFIC}} \times \text{traffic\_sum}) + (W_{\text{DAY}} \times \text{day})$$
4. **Hard Constraints (`_is_slot_feasible`):**
   - No midnight crossing (`start_hour + duration_hours <= 24`).
   - Deadline respected (`day <= request.deadline_day` and `day < horizon_days`).
   - Section is not blocked (`section.is_blocked == False` and not in `blocked_section_ids`).
   - Zero time overlap on the same section and day.
   - Minimum 1-hour safety gap between blocks (`MIN_GAP_HOURS = 1`).
   - Maximum 3 blocks per section per day (`MAX_BLOCKS_PER_SECTION_DAY = 3`).
5. **Non-Destructive What-If Mode (`persist_status=False`):** Evaluates the full schedule and records a `PlanRun` with `is_whatif=True` without mutating `MaintenanceRequest.status` or `Section.is_blocked`.

---

## 5. Application Modules & Views

### 5.1 `core/views.py`
- `section_list`: Lists all corridor sections with asset counts and operational/blocked status.
- `section_detail`: Displays a 7×24 color-coded Traffic Density Heat Table (`Low 1–3`, `Moderate 4–6`, `High 7–10`) and section assets.
- `asset_list`: Lists all assets with section and type filters.
- `login_view`, `signup_view`, `logout_view`, `account_view`: Full authentication and user profile management.

### 5.2 `requests_app/views.py` & `forms.py`
- `MaintenanceRequestForm`: Validates `duration_hours` (`1–8`), `priority` (`1–5`), and `deadline_day` (`0–6`).
- `request_list`: Filterable table (`?status=`, `?priority=`) of all maintenance requests.
- `request_create`, `request_edit`, `request_delete`: Full CRUD lifecycle with flash messages and delete confirmation.

### 5.3 `planner/views.py`
- `run_list`: Lists historical `PlanRun` executions (Optimized, Baseline, What-If).
- `generate_plan`: Form to trigger `run_plan` with custom label, `horizon_days` (`1–14`), and optional simulated `blocked_sections`.
- `run_detail`: Displays KPI metric cards, scheduled blocks table with `score_breakdown` and explanations, and deferred requests with deferral reasons.
- `compare_plans`: Side-by-side comparison of any Baseline run vs. Optimized run (traffic reduction %, scheduled diff, deferred diff, conflicts, availability %).

### 5.4 `dashboard/views.py`
- `dashboard_home`:
  - Fetches the latest optimized `PlanRun` (`is_baseline=False, is_whatif=False`).
  - Displays 6 KPI cards: Total Requests, Pending, Scheduled, Deferred, Traffic Impact, and Availability %.
  - Renders a 7×24 schedule timeline grid where clicking any block cell triggers `explainBlock(blockId)` via `GET /ai/explain/<block_id>/`.
  - Displays an empty-state call-to-action if no optimized plan exists.
- `whatif_view`: Lets controllers select a section to temporarily block and immediately view the simulated impact (`persist_status=False`).

---

## 6. Complete URL Routing Reference

| URL | View Name | Description |
|---|---|---|
| `/` | `dashboard:home` | Main KPI dashboard, 7×24 timeline grid, section overview |
| `/whatif/` | `dashboard:whatif` | Non-destructive What-If section blockage simulator |
| `/requests/` | `requests_app:request_list` | Maintenance request list with status/priority filters |
| `/requests/create/` | `requests_app:request_create` | Create new maintenance request |
| `/requests/<pk>/edit/` | `requests_app:request_edit` | Edit existing maintenance request |
| `/requests/<pk>/delete/` | `requests_app:request_delete` | Confirm and delete maintenance request |
| `/core/sections/` | `core:section_list_alt` | All railway corridor sections |
| `/core/sections/<code>/` | `core:section_detail` | Section 7×24 traffic density heatmap & assets |
| `/core/assets/` | `core:asset_list` | All Track/OHE/Signal assets |
| `/planner/` | `planner:run_list` | History of all `PlanRun` records |
| `/planner/generate/` | `planner:generate_plan` | Generate a new optimized or simulated plan |
| `/planner/runs/<pk>/` | `planner:run_detail` | Detailed block schedule, cost breakdowns & deferred items |
| `/planner/compare/` | `planner:compare_plans` | Baseline (FCFS) vs. Optimized KPI comparison |
| `/login/` & `/core/login/` | `core:login` | Sign in (auto-redirects unknown users to Sign Up) |
| `/signup/` & `/core/signup/` | `core:signup` | Register a new `User` + `UserAccount` |
| `/logout/` & `/core/logout/` | `core:logout` | Sign out |
| `/account/` & `/core/account/` | `core:account` | View/update user profile (`@login_required`) |
| `/ai/explain/<block_id>/` | `ai:explain_block` | JSON explanation for a block (`?use_gemini=1` optional) |
| `/ai/chat/` | `ai:chat` | JSON POST endpoint for the floating AI assistant chatbot |
| `/admin/` | `admin:index` | Django Admin interface |

---

## 7. Authentication & User Account System

- **Sign In (`/login/`):** Accepts username or email and password. If a submitted username/email does not exist in `User`, the view automatically redirects to `/signup/?username=...` with an informational message.
- **Sign Up (`/signup/`):** Creates a Django `User` and linked `UserAccount` (`employee_id`, `role`, `department`, `phone_number`) and logs the user in.
- **Account (`/account/`):** Protected view displaying employee ID, role badge, email, phone, approval status, and profile update form.

---

## 8. AI Subsystem (`ai/`)

### 8.1 Block Explanation (`GET /ai/explain/<block_id>/`)
- By default (`use_gemini=0`), `explain_block(block)` generates a deterministic explanation directly from `block.score_breakdown` (`traffic`, `day_penalty`, `slots_considered`).
- When `?use_gemini=1` is passed and `GEMINI_API_KEY` is configured, `explain_block_with_gemini(block)` checks `AICache` by SHA-256 prompt hash, calls the Gemini API on cache miss, stores the result, and falls back to `explain_block(block)` on any error.

### 8.2 Floating Assistant Chatbot (`POST /ai/chat/`)
- Embedded in `core/templates/base.html` across all pages.
- Queries live database context (`Section`, `Asset`, `MaintenanceRequest`, latest `PlanRun`) to answer questions about hard constraints, traffic cost formula, monitored sections, and Baseline vs. Optimized differences.

---

## 9. UI & Theme System (`base.html` & `static/css/app.css`)

### 9.1 Three-Mode Theme Switch (System / Light / Dark)
- **No-FOUC Pre-Paint Script:** Located in `<head>` of `core/templates/base.html`. Reads `localStorage.getItem('theme')` (defaults to `'system'`), evaluates `window.matchMedia('(prefers-color-scheme: dark)').matches` when in `system` mode, and applies `data-theme` and `html.dark` before first paint.
- **Accessible Toggle (`#theme-toggle`):** Located in the top navigation bar with `aria-label="Switch theme"`, inline Lucide SVG icons (`Sun`, `Moon`, `Monitor`), and keyboard focus styling (`--focus-ring`). Cycles `System → Light → Dark`.
- **Transitions:** `200ms ease` transitions restricted to `background-color`, `border-color`, and `color` (never layout properties).
- **Scrolled Navbar:** `header` uses `--brand` (`#0F2A47` / `#0A1B30`) at top and transitions to `.scrolled` (`--surface` background, `--border` bottom line, `--text` links) when `window.scrollY > 10`.

### 9.2 Design Tokens (`:root` & `html.dark`)
| Token | Light Theme | Dark Theme | Usage |
|---|---|---|---|
| `--bg` | `#F5F7FA` | `#0B1220` | Page background |
| `--surface` | `#FFFFFF` | `#111B2E` | Cards, inputs, modals, chatbot window |
| `--surface-muted` | `#EEF2F7` | `#16223A` | Table headers, alternating rows, tiles, skeleton |
| `--border` | `#E2E8F0` | `#1E2A40` | Borders, dividers, timeline grid lines |
| `--text` | `#1B2430` | `#E5EAF1` | Primary text |
| `--text-muted` | `#5B6776` | `#94A3B8` | Secondary labels & subtitles |
| `--brand` | `#0F2A47` | `#0A1B30` | Navbar & hero brand surface |
| `--brand-gradient-end` | `#16385F` | `#0F2A47` | Hero gradient endpoint |
| `--accent` | `#2F80ED` | `#3B82F6` | Primary buttons, links, active states |
| `--accent-hover` | `#1F6FDB` | `#60A5FA` | Hover states |
| `--accent-contrast` | `#FFFFFF` | `#FFFFFF` | Text on accent buttons |
| `--focus-ring` | `#2F80ED` | `#60A5FA` | Focus outlines |
| `--shadow` | `0 1px 3px rgba(15, 42, 71, 0.08)` | `0 1px 3px rgba(0, 0, 0, 0.5)` | Card & surface elevation |

### 9.3 Status Block Tokens
Used consistently across `.status-*` classes, badges, section heatmaps, What-If impact banners, and comparison summaries:
- **Completed:** Light `#DCFCE7` / `#16A34A` / `#14532D` | Dark `#12301F` / `#22C55E` / `#86EFAC`
- **In Progress:** Light `#DBEAFE` / `#2563EB` / `#1E3A8A` | Dark `#14284A` / `#3B82F6` / `#93C5FD`
- **Delayed / Warning:** Light `#FEF3C7` / `#D97706` / `#78350F` | Dark `#3A2A0B` / `#F59E0B` / `#FCD34D`
- **Conflict / Error:** Light `#FEE2E2` / `#DC2626` / `#7F1D1D` | Dark `#3F1518` / `#EF4444` / `#FCA5A5`
- **Unscheduled / Idle:** Light `#F1F5F9` / `#94A3B8` / `#475569` | Dark `#1A2538` / `#64748B` / `#94A3B8`

---

## 10. Management Commands

| Command | Description |
|---|---|
| `python manage.py migrate` | Applies all database migrations across `core`, `requests_app`, `planner`, `ai`, and Django built-ins |
| `python manage.py seed_data` | Seeds 5 sections (`LDH-SIR`, `SIR-UMB`, `LDH-JUC`, `JUC-ASR`, `LDH-MOG`), 28 assets, and 840 traffic slots (seed=42) |
| `python manage.py seed_requests` | Creates 15 synthetic maintenance requests (`--reset`, `--count N` supported) |
| `python manage.py benchmark` | Benchmarks Baseline vs. Optimized across `normal`, `overloaded`, and `blocked_section` scenarios |

---

## 11. Testing & Verification

Run the full test suite and system check:
```bash
python manage.py check
python manage.py test core planner requests_app dashboard ai --verbosity=1
```

**Latest Verified Results:**
- `python manage.py check` → `System check identified no issues (0 silenced).`
- `python manage.py test core planner requests_app dashboard ai --verbosity=1` → **55/55 tests passing** (`OK` in `22.586s`).
- HTTP route verification → **200 OK** across `/`, `/login/`, `/signup/`, `/whatif/`, `/requests/`, `/requests/create/`, `/core/sections/`, `/core/sections/LDH-SIR/`, `/core/assets/`, `/planner/`, `/planner/generate/`, and `/planner/compare/`.
