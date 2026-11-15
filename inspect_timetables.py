import pandas as pd
from database import DatabaseManager
db = DatabaseManager()
versions = db.get_timetable_versions()
vid = versions['version_id'].iloc[0]
entries = db.get_timetable_entries(vid)
courses = db.get_courses().set_index('course_id')
students = db.get_students()
enroll = db.get_student_enrollments()
merged = enroll.merge(students, on='student_id')
enr_counts = merged.groupby('course_id').size().to_dict()
dept_breakdown = merged.groupby(['course_id', 'department_id']).size().unstack(fill_value=0).to_dict()

# Print detailed entries
days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
periods = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6']

print(f"Total sessions: {len(entries)}")
for _, r in entries.sort_values(by=['day', 'period_id', 'course_id']).iterrows():
    cid = r['course_id']
    tot = enr_counts.get(cid, 0)
    c_cse = dept_breakdown.get('CSE', {}).get(cid, 0)
    c_ece = dept_breakdown.get('ECE', {}).get(cid, 0)
    c_it = dept_breakdown.get('IT', {}).get(cid, 0)
    reg_str = f"Total {tot} (CSE:{c_cse}, ECE:{c_ece}, IT:{c_it})"
    print(f"{r['day'][:3]} {r['period_id']} [x{r['duration_periods']}]: {cid} - {r['course_name']} ({r['course_type']}) | {r['faculty_name']} | {r['classroom_name']} | Enrolled: {reg_str}")
