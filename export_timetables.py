import pandas as pd
from database import DatabaseManager
from timetable_generator import TimetableOptimizer
from utils import ConflictValidator

db = DatabaseManager()
versions = db.get_timetable_versions()
if versions.empty:
    opt = TimetableOptimizer(db)
    res = opt.generate()
    db.save_timetable_version('V1.0', 'Master NEP 2020 Schedule', res['entries'], res['metrics'], 'Baseline')
    vid = 'V1.0'
else:
    vid = versions['version_id'].iloc[0]

entries = db.get_timetable_entries(vid)
validator = ConflictValidator(db)
audit = validator.validate(vid)
print(f"Version: {vid}, Entries: {len(entries)}, Score: {audit['score']}, Hard Conflicts: {audit['hard_conflicts']}")

courses = db.get_courses().set_index('course_id')
students = db.get_students()
enroll = db.get_student_enrollments()

# Calculate enrollments per course per department
merged = enroll.merge(students, on='student_id', how='left')
enr_counts = merged.groupby('course_id').size().to_dict()
dept_enr = merged.groupby(['course_id', 'department_id']).size().unstack(fill_value=0).to_dict()

days = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
periods = ["P1", "P2", "P3", "P4", "P5", "P6"]
period_times = {
    "P1": "09:00 - 09:50",
    "P2": "09:50 - 10:40",
    "P3": "10:50 - 11:40",
    "P4": "11:40 - 12:30",
    "P5": "13:30 - 14:20",
    "P6": "14:20 - 15:10"
}

# Function to build grid for a list of courses
def build_grid(target_courses, label):
    # filter entries
    sub = entries[entries['course_id'].isin(target_courses)]
    grid = {p: {d: "" for d in days} for p in periods}
    p_seq = {p: i for i, p in enumerate(periods)}
    rev_p = {i: p for p, i in p_seq.items()}
    
    for _, r in sub.iterrows():
        d = r['day']
        p = r['period_id']
        dur = int(r['duration_periods'])
        cid = r['course_id']
        cname = r['course_name']
        ctype = r['course_type']
        fname = r['faculty_name']
        room = r['classroom_name']
        reg_total = enr_counts.get(cid, 0)
        
        info = f"{cid} - {cname} ({ctype}) | Fac: {fname} | Rm: {room} [Reg: {reg_total}]"
        if grid[p][d]:
            grid[p][d] += " + " + info
        else:
            grid[p][d] = info
            
        if dur == 2:
            p2 = rev_p.get(p_seq[p] + 1)
            if p2:
                info2 = f"{cid} - {cname} (Lab Contd.) | Fac: {fname} | Rm: {room}"
                if grid[p2][d]:
                    grid[p2][d] += " + " + info2
                else:
                    grid[p2][d] = info2
    return pd.DataFrame(grid).T[days]

# 1. CSE
cse_courses = ['C101', 'C102', 'C103', 'C104', 'C105', 'X403', 'X401', 'I303', 'C106']
grid_cse = build_grid(cse_courses, "CSE")

# 2. ECE
ece_courses = ['E201', 'E202', 'E203', 'E204', 'X403', 'X401', 'X402']
grid_ece = build_grid(ece_courses, "ECE")

# 3. IT
it_courses = ['I301', 'I302', 'I303', 'I304', 'X404', 'X401', 'X402']
grid_it = build_grid(it_courses, "IT")

# 4. Multidisciplinary & Open Electives
multi_courses = ['X401', 'X402', 'X403', 'X404', 'I303', 'C106']
grid_multi = build_grid(multi_courses, "Multidisciplinary")

import json
print("=== CSE GRID ===")
print(grid_cse.to_string())
print("\n=== ECE GRID ===")
print(grid_ece.to_string())
print("\n=== IT GRID ===")
print(grid_it.to_string())
print("\n=== MULTIDISCIPLINARY GRID ===")
print(grid_multi.to_string())

# Save to json for quick reference
with open('data/timetables_summary.json', 'w') as f:
    json.dump({
        'cse': grid_cse.to_dict(),
        'ece': grid_ece.to_dict(),
        'it': grid_it.to_dict(),
        'multi': grid_multi.to_dict()
    }, f, indent=2)
