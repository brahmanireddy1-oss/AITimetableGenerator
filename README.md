# AI-Based Timetable Generation System aligned with NEP 2020 for Multidisciplinary Education Structures

An enterprise-grade, constraint-optimized academic scheduling platform developed for undergraduate and multidisciplinary higher education institutions. Built in compliance with the **National Education Policy (NEP 2020)** guidelines, this system automates conflict-free timetable generation across departments, major and minor subjects, open electives, interdisciplinary courses, skill enhancement modules, and continuous laboratory blocks using **Google OR-Tools CP-SAT**.

---

## 1. Project Overview

Higher education under NEP 2020 requires institutions to transition from rigid branch silos into flexible, multidisciplinary learning pathways. Students from Computer Science, Electronics, and Information Technology choose interdisciplinary electives, skill courses, and cross-departmental minors.

Traditional manual or heuristic scheduling fails under this combinatorial complexity. This system formulates academic scheduling as a mathematical **Constraint Satisfaction Problem (CSP)** solved using **Google OR-Tools CP-SAT**:

- **Multidisciplinary Electives:** Resolves clashes among students taking cross-departmental courses (e.g., CSE students taking Cloud Computing from IT, ECE students taking Machine Learning).
- **Laboratory Continuity:** Enforces strict 2-period contiguous blocks (P1-P2, P3-P4, P5-P6) without fragmenting across the institutional lunch recess (12:30 – 13:30).
- **Resource Balancing:** Satisfies hard faculty availability and classroom capacity bounds while softly balancing faculty workload and minimizing student timetable gaps.
- **Dynamic Re-optimization:** Supports dynamic regeneration with session diff visualization when faculty availability or room constraints change.
- **Auditing & Governance:** Features independent 8-point rule verification, audit scoring, and a multi-stage approval workflow (`Draft` -> `Approved` -> `Published`).

---

## 2. Technology Stack

| Component | Technology | Role |
| :--- | :--- | :--- |
| **Frontend & UI** | Python 3.12 + Streamlit | Single-page reactive academic administration console |
| **Optimization Engine** | Google OR-Tools CP-SAT | Exact constraint programming solver for NP-hard scheduling |
| **Cloud Database** | Supabase (PostgreSQL) | Managed relational database with foreign-key integrity |
| **Local Fallback Engine** | SQLite3 (PRAGMA foreign_keys) | Fully functional offline mirrored storage for demos |
| **Data Processing** | Pandas & NumPy | Cross-sheet dataframes, joins, and matrix transforms |
| **Excel Handling** | OpenPyXL | Multi-worksheet validation, styling, and exports |
| **PDF Generation** | ReportLab | Publication-ready landscape printable academic timetables |
| **Visualization** | Plotly Express & Graph Objects | Interactive workload, room utilization, and donut charts |
| **Testing** | Pytest | Automated end-to-end integration and constraint tests |

---

## 3. Project Folder Structure

```text
AI_Timetable_Generator/
│
├── app.py                     # Main Streamlit web application & UI navigation
├── timetable_generator.py     # Google OR-Tools CP-SAT optimization engine
├── database.py                # Database manager (Supabase + Local SQLite mirror)
├── utils.py                   # Conflict validator, grid builder & PDF/Excel/TXT exports
│
├── data/
│   └── AI_Timetable_Demo_Data.xlsx # Primary input workbook (9 NEP 2020 worksheets)
│
├── database/
│   └── schema.sql             # Supabase PostgreSQL relational schema definition
│
├── tests/
│   └── test_timetable.py      # Pytest automated test suite (10 unit/integration tests)
│
├── requirements.txt           # Python dependency specification
├── README.md                  # Comprehensive documentation and demonstration guide
├── .env.example               # Template for Supabase environment variables
└── .gitignore                 # Version control exclusions
```

---

## 4. Python Installation Requirements

- **Python Version:** Python `3.10`, `3.11`, or `3.12` (64-bit recommended).
- **OS:** Windows 10/11, macOS, or Linux.

Verify your installed Python version:
```bash
python --version
```

---

## 5. Dependency Installation

1. Create and activate a Python virtual environment:
   ```bash
   # Windows (PowerShell)
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1

   # Linux / macOS
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Upgrade pip and install all required packages:
   ```bash
   pip install --upgrade pip
   pip install -r requirements.txt
   ```

---

## 6. Supabase Project Setup (Cloud PostgreSQL)

The system works **completely offline with SQLite** out of the box. To connect to a live Supabase PostgreSQL instance:

1. Create a free account at [Supabase](https://supabase.com).
2. Create a new project (e.g., `nep-timetable-system`).
3. Under **Project Settings -> API**, copy:
   - **Project URL**
   - **Project API Keys** (`anon` or `service_role`).

---

## 7. SQL Schema Execution

In your Supabase project:
1. Open the **SQL Editor** from the left navigation.
2. Click **New Query**.
3. Copy and paste the entire contents of [`database/schema.sql`](database/schema.sql).
4. Click **Run**. All 12 tables and performance indexes will be created.

---

## 8. Environment Variable Configuration

Create a `.env` file in the root directory (or use `.env.example` as a template):

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` and fill in your Supabase credentials:
```env
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_KEY=your-supabase-anon-or-service-role-key
```

*(Note: If left blank or unconfigured, the application runs seamlessly in local mode without errors!)*

---

## 9. Primary Dataset: Excel Workbook (9 Worksheets)

The primary dataset [`data/AI_Timetable_Demo_Data.xlsx`](data/AI_Timetable_Demo_Data.xlsx) contains 9 interconnected sheets:

1. **`Departments`**: Department code and full name (CSE, ECE, IT).
2. **`Students`**: 60 students categorized into 4 cohorts (`CSE2A`, `CSE2B`, `ECE2A`, `IT2A`).
3. **`Courses`**: 18 NEP 2020 courses classified into Major, Laboratory, Open Elective, Interdisciplinary, and Skill Enhancement.
4. **`Faculty`**: 12 faculty members with departmental affiliation and maximum weekly limits.
5. **`Classrooms`**: 10 facilities categorized as Classrooms, Computer Labs, and Electronics Labs with exact capacities.
6. **`Faculty_Availability`**: Period-by-period teaching availability across Monday to Friday.
7. **`Student_Enrollments`**: 390 student course registrations demonstrating elective cross-enrollment.
8. **`Time_Slots`**: 30 teaching slots per week (6 daily periods $\times$ 5 days).
9. **`Constraints`**: Institutional working days, solver limits, and soft penalty weights.

---

## 10. Running the Application

Launch the Streamlit web application with:

```bash
streamlit run app.py
```

The application will open automatically in your browser at:
`http://localhost:8501`

---

## 11. Complete Step-by-Step Demonstration Workflow

Follow these steps for a complete project evaluation or viva demonstration:

1. **Dashboard Overview (`📊 Dashboard`):**
   - View live statistics of departments, students, courses, faculty, and classrooms.
   - Inspect NEP 2020 course category breakdown and classroom utilization charts.

2. **Data Management (`📁 Data Management`):**
   - Under *Excel Workbook Import*, click **"Reload Primary Demo Dataset"** or upload a customized `.xlsx` workbook.
   - Preview individual worksheets.
   - Inspect the *Faculty Availability Matrix* to see visual heatmaps of available slots.

3. **Constraint Configuration (`⚙️ Constraint Configuration`):**
   - Review the 10 hard constraints enforced by the mathematical solver.
   - Adjust soft constraint weights (Faculty workload balance, Student gap reduction) and max solver time limit.

4. **Generate Timetable (`⚡ Generate Timetable`):**
   - Enter a version label (e.g., `NEP Schedule V1.0`).
   - Click **"Run OR-Tools Optimization Solver"**.
   - Watch the live progress as CP-SAT proves feasibility in seconds.
   - Timetable is saved as **`Draft`**.

5. **Timetable Views (`📅 View Timetable`):**
   - Switch between **Department-wise**, **Faculty-wise**, **Student Group-wise**, and **Classroom-wise** views.
   - View the formatted weekly schedule grid.
   - Notice color badges for Laboratories (double blocks), Open Electives, and Interdisciplinary courses.

6. **Independent Conflict Audit (`🛡️ Conflict Detection`):**
   - Click the audit section to run an independent 8-point verification.
   - Observe **100% Quality Score** and **0 Hard Conflicts**.

7. **Dynamic Regeneration Simulation (`🔄 Dynamic Regeneration`):**
   - Select a faculty member (e.g., `F001`) and mark them unavailable on a specific day/period.
   - Click **"Trigger Regeneration"**.
   - System re-runs OR-Tools, generates a new version (e.g. `V2.0`), and shows an automated **Session Relocation Diff Table** highlighting changed periods!

8. **Governance & Approval (`✅ Approval & Publication`):**
   - View the status of your timetable version (`Draft`).
   - Click **"Approve Timetable"** (records auditor name and timestamp in the audit trail).
   - Click **"Publish Timetable"** to make it officially accessible.

9. **Multi-Format Export (`📥 Reports & Export`):**
   - Select the desired timetable view (e.g. CSE Department, or Faculty Dr. Ananya Rao).
   - Click **"Download PDF Timetable"** -> Generates a formatted landscape PDF with institutional header and signature blocks.
   - Click **"Download Excel Workbook"** -> Generates a multi-sheet formatted workbook with styled cells.
   - Click **"Download Text Timetable"** -> Generates an ASCII campus notice board file.

---

## 12. Automated Testing

Run the automated Pytest test suite covering all 10 validation stages:

```bash
python -m pytest tests/test_timetable.py -v
```

**Expected Test Output:**
```text
tests/test_timetable.py::test_workbook_reading_and_validation PASSED     [ 10%]
tests/test_timetable.py::test_database_counts PASSED                     [ 20%]
tests/test_timetable.py::test_reference_integrity PASSED                 [ 30%]
tests/test_timetable.py::test_constraint_configuration PASSED            [ 40%]
tests/test_timetable.py::test_timetable_generation_cpsat PASSED          [ 50%]
tests/test_timetable.py::test_independent_conflict_validation PASSED     [ 60%]
tests/test_timetable.py::test_synthetic_faculty_clash_detection PASSED   [ 70%]
tests/test_timetable.py::test_dynamic_regeneration_and_comparison PASSED [ 80%]
tests/test_timetable.py::test_approval_and_publishing_workflow PASSED    [ 90%]
tests/test_timetable.py::test_export_formats PASSED                      [100%]

============================= 10 passed in 47.93s =============================
```

---

## 13. License & Academic Attribution

Developed as a B.Tech Computer Science and Engineering Mini Project.
Released under the MIT License for educational and institutional research purposes.
