import io
import json
from typing import Dict, List, Any, Optional, Tuple, Set
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, PatternFill, Border, Side
from reportlab.lib.pagesizes import letter, landscape, A4
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

import re

def _clean_for_reportlab(text: str) -> str:
    """Converts HTML / markdown to ReportLab safe XML Paragraph tags."""
    if not text or "Free / Self-Study" in text:
        return "<font color='#94a3b8'><i>Free / Self-Study</i></font>"
    # Clean HTML entities first
    t = text.replace("&nbsp;", " ")
    # Convert linebreaks and breaks
    t = t.replace("<br/>", "<br/>").replace("<br>", "<br/>")
    t = re.sub(r'</(div|p)>', '<br/>', t)
    t = re.sub(r'<hr[^>]*>', '<br/>---<br/>', t)
    # Strip div and span tags, but preserve content
    t = re.sub(r'<(div|span)[^>]*>', '', t)
    t = re.sub(r'</(div|span)>', '', t)
    # Convert markdown bold/italics
    t = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', t)
    t = re.sub(r'\*(.*?)\*', r'<i>\1</i>', t)
    # Escape & if not part of an XML entity
    t = re.sub(r'&(?!amp;|lt;|gt;|quot;|apos;)', '&amp;', t)
    # Strip any remaining unsupported HTML tags
    t = re.sub(r'<(?!b\b|/b\b|i\b|/i\b|u\b|/u\b|font\b|/font\b|br\b|/br\b)[^>]+>', '', t)
    # Clean multiple consecutive breaks
    t = re.sub(r'(<br/>\s*)+', '<br/>', t)
    t = re.sub(r'^(<br/>\s*)+|(<br/>\s*)+$', '', t).strip()
    return t

def _strip_html(text: str) -> str:
    """Strips HTML tags and standardizes newlines for Excel / Text exports."""
    if not text:
        return ""
    t = text.replace("<br/>", "\n").replace("<br>", "\n").replace("&nbsp;", " ")
    t = re.sub(r'<hr[^>]*>', '\n---\n', t)
    t = re.sub(r'</(div|p)>', '\n', t)
    t = re.sub(r'<[^>]+>', '', t)
    t = t.replace("**", "").replace("*", "")
    t = re.sub(r'\n\s*\n', '\n', t).strip()
    return t
DAYS_LIST = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"]
PERIODS_LIST = ["P1", "P2", "P3", "P4", "P5", "P6"]
PERIOD_TIMES = {
    "P1": "09:00 - 09:50",
    "P2": "09:50 - 10:40",
    "P3": "10:50 - 11:40",
    "P4": "11:40 - 12:30",
    "P5": "13:30 - 14:20",
    "P6": "14:20 - 15:10"
}

# =====================================================================
# INDEPENDENT CONFLICT DETECTION AND VALIDATION MODULE
# =====================================================================

class ConflictValidator:
    """
    Independent timetable audit engine.
    Audits any generated or modified timetable version against institutional
    regulations, NEP 2020 multidisciplinary rules, and resource limits.
    """
    def __init__(self, db_manager):
        self.db = db_manager

    def validate(self, version_id: str) -> Dict[str, Any]:
        """
        Validates the specified timetable version.
        Returns detailed list of conflicts, validation score, and breakdown.
        """
        entries_df = self.db.get_timetable_entries(version_id)
        courses_df = self.db.get_courses()
        classrooms_df = self.db.get_classrooms()
        faculty_df = self.db.get_faculty()
        avail_df = self.db.get_faculty_availability()
        enroll_df = self.db.get_student_enrollments()
        time_slots_df = self.db.get_time_slots()

        conflicts = []

        if entries_df.empty:
            return {
                "is_valid": False,
                "conflict_count": 1,
                "hard_conflicts": 1,
                "soft_conflicts": 0,
                "score": 0,
                "conflicts": [{
                    "type": "No Entries",
                    "severity": "Hard",
                    "entity": version_id,
                    "slot": "-",
                    "explanation": "No timetable entries exist for this version.",
                    "suggested_correction": "Generate the timetable using OR-Tools CP-SAT."
                }]
            }

        # Expand duration 2 entries into occupied slots: (day, period_id)
        # Period sequence
        p_seq = {p: i for i, p in enumerate(PERIODS_LIST)}
        rev_p = {i: p for p, i in p_seq.items()}

        expanded_records = []
        for _, row in entries_df.iterrows():
            dur = int(row["duration_periods"])
            day = row["day"]
            p_start = row["period_id"]
            p_idx = p_seq.get(p_start, 0)

            # First period
            rec1 = dict(row)
            rec1["slot_period"] = p_start
            rec1["slot_idx"] = p_idx
            expanded_records.append(rec1)

            # Second period if duration is 2
            if dur == 2:
                rec2 = dict(row)
                rec2["slot_period"] = rev_p.get(p_idx + 1, "P_EXT")
                rec2["slot_idx"] = p_idx + 1
                expanded_records.append(rec2)

        exp_df = pd.DataFrame(expanded_records)

        # 1. Faculty Clash Check
        fac_clashes = exp_df.groupby(["faculty_id", "day", "slot_period"]).filter(lambda g: len(g) > 1)
        if not fac_clashes.empty:
            for (fid, day, slot), grp in fac_clashes.groupby(["faculty_id", "day", "slot_period"]):
                courses_involved = grp["course_id"].unique().tolist()
                fname = grp["faculty_name"].iloc[0] if "faculty_name" in grp.columns else fid
                conflicts.append({
                    "type": "Faculty Clash",
                    "severity": "Hard",
                    "entity": f"{fname} ({fid})",
                    "slot": f"{day} {slot}",
                    "explanation": f"Faculty is double-booked for courses: {', '.join(courses_involved)} at the same time.",
                    "suggested_correction": "Reschedule one of the overlapping courses to another period."
                })

        # 2. Classroom Clash Check
        room_clashes = exp_df.groupby(["classroom_id", "day", "slot_period"]).filter(lambda g: len(g) > 1)
        if not room_clashes.empty:
            for (rid, day, slot), grp in room_clashes.groupby(["classroom_id", "day", "slot_period"]):
                courses_involved = grp["course_id"].unique().tolist()
                rname = grp["classroom_name"].iloc[0] if "classroom_name" in grp.columns else rid
                conflicts.append({
                    "type": "Classroom Clash",
                    "severity": "Hard",
                    "entity": f"{rname} ({rid})",
                    "slot": f"{day} {slot}",
                    "explanation": f"Classroom is assigned to multiple courses simultaneously: {', '.join(courses_involved)}.",
                    "suggested_correction": "Reassign one of the sessions to a different vacant room."
                })

        # 3. Student Clash Check
        # Build student course mapping
        student_courses = {}
        for _, r in enroll_df.iterrows():
            student_courses.setdefault(r["student_id"], set()).add(r["course_id"])

        # Check for each slot if any student is enrolled in 2 courses running at that slot
        slot_groups = exp_df.groupby(["day", "slot_period"])
        for (day, slot), grp in slot_groups:
            active_c = grp["course_id"].unique()
            if len(active_c) > 1:
                # Check pairwise intersection of students
                for i in range(len(active_c)):
                    for j in range(i + 1, len(active_c)):
                        c1, c2 = active_c[i], active_c[j]
                        enr1 = set(enroll_df[enroll_df["course_id"] == c1]["student_id"])
                        enr2 = set(enroll_df[enroll_df["course_id"] == c2]["student_id"])
                        common_stds = enr1.intersection(enr2)
                        if common_stds:
                            conflicts.append({
                                "type": "Student Conflict",
                                "severity": "Hard",
                                "entity": f"{len(common_stds)} Enrolled Students",
                                "slot": f"{day} {slot}",
                                "explanation": f"Students enrolled in both '{c1}' and '{c2}' have an overlapping class conflict.",
                                "suggested_correction": "Ensure elective and interdisciplinary courses do not clash for common students."
                            })

        # 4. Faculty Availability Check
        avail_map = {}
        for _, row in avail_df.iterrows():
            avail_map[(row["faculty_id"], row["day"], row["period_id"])] = int(row["is_available"])

        for _, row in exp_df.iterrows():
            fid = row["faculty_id"]
            day = row["day"]
            slot = row["slot_period"]
            is_av = avail_map.get((fid, day, slot), 1)
            if is_av == 0:
                fname = row.get("faculty_name", fid)
                conflicts.append({
                    "type": "Faculty Unavailability",
                    "severity": "Hard",
                    "entity": f"{fname} ({fid})",
                    "slot": f"{day} {slot}",
                    "explanation": f"Session {row['session_id']} is scheduled during faculty member's unavailable slot.",
                    "suggested_correction": f"Move session {row['session_id']} to an available slot or update faculty availability."
                })

        # 5. Classroom Capacity Violations
        # Compare room capacity with course expected/actual enrolment
        room_cap_map = classrooms_df.set_index("classroom_id")["capacity"].to_dict()
        course_enrol_map = courses_df.set_index("course_id")["expected_enrolment"].to_dict()

        for _, row in entries_df.iterrows():
            cid = row["course_id"]
            rid = row["classroom_id"]
            req_enrol = course_enrol_map.get(cid, 0)
            actual_enrol = len(enroll_df[enroll_df["course_id"] == cid])
            eff_enrol = max(req_enrol, actual_enrol) if actual_enrol > 0 else req_enrol
            cap = room_cap_map.get(rid, 0)

            if cap < eff_enrol:
                rname = row.get("classroom_name", rid)
                conflicts.append({
                    "type": "Capacity Violation",
                    "severity": "Hard",
                    "entity": f"Room {rname} vs Course {cid}",
                    "slot": f"{row['day']} {row['period_id']}",
                    "explanation": f"Room capacity is {cap}, but course enrollment is {eff_enrol} students.",
                    "suggested_correction": f"Assign course {cid} to a larger room."
                })

        # 6. Room Type Mismatch
        course_rtype_map = courses_df.set_index("course_id")["required_room_type"].to_dict()
        room_type_map = classrooms_df.set_index("classroom_id")["room_type"].to_dict()

        for _, row in entries_df.iterrows():
            cid = row["course_id"]
            rid = row["classroom_id"]
            req_type = course_rtype_map.get(cid, "Classroom")
            actual_type = room_type_map.get(rid, "Classroom")

            if req_type != actual_type:
                conflicts.append({
                    "type": "Room Type Mismatch",
                    "severity": "Hard",
                    "entity": f"Course {cid} in Room {rid}",
                    "slot": f"{row['day']} {row['period_id']}",
                    "explanation": f"Course requires '{req_type}', but was scheduled in '{actual_type}'.",
                    "suggested_correction": f"Move course {cid} to a {req_type} facility."
                })

        # 7. Required Weekly Sessions Check
        course_req_sessions = courses_df.set_index("course_id")["weekly_sessions"].to_dict()
        scheduled_sessions = entries_df.groupby("course_id")["session_id"].nunique().to_dict()

        for cid, req_w in course_req_sessions.items():
            sch_w = scheduled_sessions.get(cid, 0)
            if sch_w < req_w:
                conflicts.append({
                    "type": "Missing Sessions",
                    "severity": "Hard",
                    "entity": f"Course {cid}",
                    "slot": "Weekly Schedule",
                    "explanation": f"Course requires {req_w} weekly sessions, but only {sch_w} are scheduled.",
                    "suggested_correction": "Regenerate timetable with increased time limit or relaxed constraints."
                })

        # 8. Lab Duration & Block Integrity Check
        for _, row in entries_df.iterrows():
            dur = int(row["duration_periods"])
            p_start = row["period_id"]
            if dur == 2:
                # Must be P1, P3, or P5
                if p_start not in ["P1", "P3", "P5"]:
                    conflicts.append({
                        "type": "Invalid Lab Block",
                        "severity": "Hard",
                        "entity": f"Session {row['session_id']}",
                        "slot": f"{row['day']} {p_start}",
                        "explanation": f"Laboratory session starts at {p_start}, splitting across tea break, lunch, or end of day.",
                        "suggested_correction": "Align 2-period lab to start at P1 (morning 1), P3 (morning 2), or P5 (afternoon)."
                    })

        hard_count = sum(1 for c in conflicts if c["severity"] == "Hard")
        soft_count = sum(1 for c in conflicts if c["severity"] == "Soft")
        is_valid = (hard_count == 0)

        # Quality Score: 100 - (hard * 25 + soft * 5), clamped 0..100
        score = max(0, 100 - (hard_count * 25 + soft_count * 5))

        return {
            "is_valid": is_valid,
            "conflict_count": len(conflicts),
            "hard_conflicts": hard_count,
            "soft_conflicts": soft_count,
            "score": score,
            "conflicts": conflicts
        }

# =====================================================================
# TIMETABLE GRID BUILDER & VIEWS
# =====================================================================

def build_timetable_grid(entries_df: pd.DataFrame, view_type: str, filter_val: str,
                         students_df: Optional[pd.DataFrame] = None,
                         enroll_df: Optional[pd.DataFrame] = None,
                         locked_sessions: Optional[Set[str]] = None,
                         moved_sessions: Optional[Set[str]] = None) -> pd.DataFrame:
    """
    Constructs a 5-day x 6-period visual timetable grid based on view type:
    - Department-wise: filter_val = department_id
    - Faculty-wise: filter_val = faculty_id
    - Classroom-wise: filter_val = classroom_id
    - Student Group-wise: filter_val = student_group
    Includes indicators for 🔒 Locked and ✨ Moved / Updated sessions.
    """
    grid = {p: {d: "" for d in DAYS_LIST} for p in PERIODS_LIST}

    if entries_df.empty:
        return pd.DataFrame(grid).T

    # Filter entries
    filtered_entries = entries_df.copy()

    if view_type == "Department" and filter_val != "All":
        filtered_entries = filtered_entries[filtered_entries["department_id"] == filter_val]
    elif view_type == "Faculty" and filter_val != "All":
        filtered_entries = filtered_entries[filtered_entries["faculty_id"] == filter_val]
    elif view_type == "Classroom" and filter_val != "All":
        filtered_entries = filtered_entries[filtered_entries["classroom_id"] == filter_val]
    elif view_type == "Student Group" and filter_val != "All":
        if students_df is not None and enroll_df is not None:
            # Find all courses taken by students in this group
            group_students = students_df[students_df["student_group"] == filter_val]["student_id"].unique()
            group_courses = enroll_df[enroll_df["student_id"].isin(group_students)]["course_id"].unique()
            filtered_entries = filtered_entries[filtered_entries["course_id"].isin(group_courses)]

    p_seq = {p: i for i, p in enumerate(PERIODS_LIST)}
    rev_p = {i: p for p, i in p_seq.items()}
    locked_set = locked_sessions or set()
    moved_set = moved_sessions or set()

    for _, row in filtered_entries.iterrows():
        day = row["day"]
        p_start = row["period_id"]
        dur = int(row["duration_periods"])
        c_code = row["course_id"]
        sid = row.get("session_id", "")
        c_name = row.get("course_name", "")
        f_name = row.get("faculty_name", row["faculty_id"])
        room = row.get("classroom_name", row["classroom_id"])
        c_type = row.get("course_type", "")

        is_locked = (sid in locked_set or c_code in locked_set)
        is_moved = (sid in moved_set)

        status_badge = ""
        if is_moved:
            status_badge = " <span style='background:#D1FAE5; color:#065F46; font-size:10px; font-weight:700; padding:1px 5px; border-radius:4px;'>✨ Moved</span>"
        elif is_locked:
            status_badge = " <span style='background:#FEE2E2; color:#991B1B; font-size:10px; font-weight:700; padding:1px 5px; border-radius:4px;'>🔒 Locked</span>"

        # Format cell content
        type_badge = f"[{c_type}]" if c_type else ""
        content = f"**{c_code}**{status_badge} - {c_name}<br/>*{f_name}* | {room} {type_badge}"

        if day in DAYS_LIST and p_start in PERIODS_LIST:
            # Current cell
            existing = grid[p_start][day]
            grid[p_start][day] = f"{existing}<hr style='margin:2px 0;'/>{content}" if existing else content

            # If duration is 2, fill second period
            if dur == 2:
                p_idx = p_seq.get(p_start, 0)
                p2 = rev_p.get(p_idx + 1)
                if p2 and p2 in grid:
                    lab_content = f"**{c_code} (Lab Contd.)**{status_badge}<br/>*{f_name}* | {room}"
                    existing2 = grid[p2][day]
                    grid[p2][day] = f"{existing2}<hr style='margin:2px 0;'/>{lab_content}" if existing2 else lab_content

    # Return DataFrame indexed by Periods, columns = Days
    df_grid = pd.DataFrame(grid).T
    df_grid = df_grid[DAYS_LIST]
    return df_grid

def build_department_cohort_grid(entries_df: pd.DataFrame, target_dept: Optional[str],
                                students_df: pd.DataFrame, enroll_df: pd.DataFrame,
                                locked_sessions: Optional[Set[str]] = None,
                                moved_sessions: Optional[Set[str]] = None) -> pd.DataFrame:
    """
    Builds a clean 5-day x 6-period visual timetable grid tailored for specific student cohorts:
    - 'CSE': All courses attended by CSE students (30 students)
    - 'ECE': All courses attended by ECE students (15 students)
    - 'IT': All courses attended by IT students (15 students)
    - None or 'MULTI': Multidisciplinary & Open Electives across all departments
    Includes course code, name, category, faculty, classroom, exact registration counts,
    and visual badges for 🔒 Locked slots and ✨ Moved / Updated slots.
    """
    grid = {p: {d: "<div style='color:#94A3B8; font-style:italic; font-size:11px; padding:8px 0;'>Free / Self-Study</div>" for d in DAYS_LIST} for p in PERIODS_LIST}
    if entries_df.empty:
        return pd.DataFrame(grid).T[DAYS_LIST]

    # Calculate enrollment counts and department breakdown
    merged = enroll_df.merge(students_df, on="student_id", how="left")
    enr_counts = merged.groupby("course_id").size().to_dict()
    dept_counts = merged.groupby(["course_id", "department_id"]).size().unstack(fill_value=0).to_dict()

    if target_dept == "CSE":
        target_courses = ["C101", "C102", "C103", "C104", "C105", "X403", "X401", "I303"]
    elif target_dept == "ECE":
        target_courses = ["E201", "E202", "E203", "E204", "X403", "X401", "X402"]
    elif target_dept == "IT":
        target_courses = ["I301", "I302", "I303", "I304", "X404", "X401", "X402"]
    else:
        target_courses = ["X401", "X402", "X403", "X404", "I303", "C106"]

    sub = entries_df[entries_df["course_id"].isin(target_courses)]
    p_seq = {p: i for i, p in enumerate(PERIODS_LIST)}
    rev_p = {i: p for p, i in p_seq.items()}
    locked_set = locked_sessions or set()
    moved_set = moved_sessions or set()

    for _, r in sub.iterrows():
        d = r["day"]
        p = r["period_id"]
        dur = int(r["duration_periods"])
        cid = r["course_id"]
        sid = r.get("session_id", "")
        cname = r.get("course_name", "")
        ctype = r.get("course_type", "")
        fname = r.get("faculty_name", r["faculty_id"])
        room = r.get("classroom_name", r["classroom_id"])

        is_locked = (sid in locked_set or cid in locked_set)
        is_moved = (sid in moved_set)

        tot = enr_counts.get(cid, 0)
        if target_dept:
            reg_d = dept_counts.get(target_dept, {}).get(cid, 0)
            if reg_d == tot and tot > 0:
                badge_text = f"👥 {reg_d} {target_dept} Students"
                badge_bg = "#E0F2FE"
                badge_fg = "#0369A1"
            else:
                badge_text = f"👥 {reg_d} {target_dept} / {tot} Total"
                badge_bg = "#FEF3C7"
                badge_fg = "#B45309"
        else:
            c_cse = dept_counts.get("CSE", {}).get(cid, 0)
            c_ece = dept_counts.get("ECE", {}).get(cid, 0)
            c_it = dept_counts.get("IT", {}).get(cid, 0)
            badge_text = f"👥 Total: {tot} (CSE: {c_cse}, ECE: {c_ece}, IT: {c_it})"
            badge_bg = "#EDE9FE"
            badge_fg = "#5B21B6"

        # Determine border color & extra badges
        if is_moved:
            border_left = "4px solid #10B981"
            status_badge_html = "<span style='background:#D1FAE5; color:#065F46; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; margin-left:4px; border:1px solid #6EE7B7;'>✨ Moved / Updated</span>"
        elif is_locked:
            border_left = "4px solid #DC2626"
            status_badge_html = "<span style='background:#FEE2E2; color:#991B1B; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px; margin-left:4px; border:1px solid #FCA5A5;'>🔒 Locked</span>"
        else:
            border_left = "4px solid #2563EB"
            status_badge_html = ""

        card = (
            f"<div style='background:#FFFFFF; border:1px solid #CBD5E1; border-left:{border_left}; "
            f"border-radius:6px; padding:6px; margin-bottom:5px; box-shadow:0 1px 2px rgba(0,0,0,0.04);'>"
            f"<div style='font-weight:700; color:#0F172A; font-size:12px;'>{cid} - {cname}</div>"
            f"<div style='font-size:11px; color:#475569;'><i>{ctype}</i> | {fname}</div>"
            f"<div style='font-size:11px; color:#1E3A8A; font-weight:600;'>🏛️ {room}</div>"
            f"<div style='margin-top:4px;'><span style='background:{badge_bg}; color:{badge_fg}; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px;'>{badge_text}</span>{status_badge_html}</div>"
            f"</div>"
        )

        if "Free / Self-Study" in grid[p][d]:
            grid[p][d] = card
        else:
            grid[p][d] += card

        if dur == 2:
            p_idx = p_seq.get(p, 0)
            p2 = rev_p.get(p_idx + 1)
            if p2 and p2 in grid:
                lab_border = "4px solid #10B981" if is_moved else ("4px solid #DC2626" if is_locked else "4px solid #7C3AED")
                card2 = (
                    f"<div style='background:#FFFFFF; border:1px solid #CBD5E1; border-left:{lab_border}; "
                    f"border-radius:6px; padding:6px; margin-bottom:5px; box-shadow:0 1px 2px rgba(0,0,0,0.04);'>"
                    f"<div style='font-weight:700; color:#0F172A; font-size:12px;'>{cid} - {cname} (Lab Contd.)</div>"
                    f"<div style='font-size:11px; color:#475569;'><i>{ctype}</i> | {fname}</div>"
                    f"<div style='font-size:11px; color:#1E3A8A; font-weight:600;'>🏛️ {room}</div>"
                    f"<div style='margin-top:4px;'><span style='background:{badge_bg}; color:{badge_fg}; font-size:10px; font-weight:700; padding:2px 6px; border-radius:4px;'>{badge_text}</span>{status_badge_html}</div>"
                    f"</div>"
                )
                if "Free / Self-Study" in grid[p2][d]:
                    grid[p2][d] = card2
                else:
                    grid[p2][d] += card2

    df_grid = pd.DataFrame(grid).T
    return df_grid[DAYS_LIST]

# =====================================================================
# DYNAMIC VERSION COMPARISON & DIFF
# =====================================================================

def compare_timetable_versions(v1_entries: pd.DataFrame, v2_entries: pd.DataFrame) -> Dict[str, Any]:
    """
    Compares two timetable versions session by session.
    Detects unchanged, relocated, and modified sessions.
    """
    if v1_entries.empty or v2_entries.empty:
        return {
            "total_sessions": max(len(v1_entries), len(v2_entries)),
            "unchanged_count": 0,
            "changed_count": 0,
            "similarity_percentage": 0.0,
            "differences": []
        }

    # Map session_id -> entry row
    m1 = {r["session_id"]: r for _, r in v1_entries.iterrows()}
    m2 = {r["session_id"]: r for _, r in v2_entries.iterrows()}

    all_sessions = sorted(list(set(m1.keys()).union(set(m2.keys()))))
    unchanged = 0
    diffs = []

    for sid in all_sessions:
        r1 = m1.get(sid)
        r2 = m2.get(sid)

        if r1 is not None and r2 is not None:
            day_match = (r1["day"] == r2["day"])
            period_match = (r1["period_id"] == r2["period_id"])
            room_match = (r1["classroom_id"] == r2["classroom_id"])

            if day_match and period_match and room_match:
                unchanged += 1
            else:
                change_type = []
                if not (day_match and period_match):
                    change_type.append("Time Slot Relocated")
                if not room_match:
                    change_type.append("Room Changed")

                diffs.append({
                    "session_id": sid,
                    "course_id": r1["course_id"],
                    "faculty_id": r1["faculty_id"],
                    "change_type": ", ".join(change_type),
                    "old_schedule": f"{r1['day']} {r1['period_id']} ({r1['classroom_id']})",
                    "new_schedule": f"{r2['day']} {r2['period_id']} ({r2['classroom_id']})"
                })
        elif r1 is not None and r2 is None:
            diffs.append({
                "session_id": sid,
                "course_id": r1["course_id"],
                "faculty_id": r1["faculty_id"],
                "change_type": "Removed Session",
                "old_schedule": f"{r1['day']} {r1['period_id']} ({r1['classroom_id']})",
                "new_schedule": "None"
            })
        elif r1 is None and r2 is not None:
            diffs.append({
                "session_id": sid,
                "course_id": r2["course_id"],
                "faculty_id": r2["faculty_id"],
                "change_type": "Added Session",
                "old_schedule": "None",
                "new_schedule": f"{r2['day']} {r2['period_id']} ({r2['classroom_id']})"
            })

    total = len(all_sessions)
    changed = len(diffs)
    similarity = round((unchanged / total) * 100.0, 1) if total > 0 else 0.0

    return {
        "total_sessions": total,
        "unchanged_count": unchanged,
        "changed_count": changed,
        "similarity_percentage": similarity,
        "differences": diffs
    }

# =====================================================================
# REPORT EXPORT (PDF, EXCEL, TXT)
# =====================================================================

def export_timetable_pdf(version_id: str, version_name: str, view_title: str,
                         grid_df: pd.DataFrame, metrics: Dict[str, Any]) -> io.BytesIO:
    """
    Generates a formal, printable academic timetable in PDF format using ReportLab.
    """
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=landscape(A4),
        rightMargin=25,
        leftMargin=25,
        topMargin=25,
        bottomMargin=25
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontSize=15,
        leading=18,
        textColor=colors.HexColor('#1E293B'),
        alignment=1, # Center
        fontName='Helvetica-Bold'
    )
    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        parent=styles['Normal'],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor('#475569'),
        alignment=1,
        fontName='Helvetica'
    )
    cell_style = ParagraphStyle(
        'GridCell',
        parent=styles['Normal'],
        fontSize=7,
        leading=9,
        textColor=colors.HexColor('#0F172A'),
        alignment=0,
        fontName='Helvetica'
    )
    header_style = ParagraphStyle(
        'HeaderCell',
        parent=styles['Normal'],
        fontSize=8,
        leading=10,
        textColor=colors.white,
        alignment=1,
        fontName='Helvetica-Bold'
    )

    elements = []

    # Title & Metadata
    elements.append(Paragraph("NATIONAL EDUCATION POLICY (NEP 2020) ACADEMIC TIMETABLE", title_style))
    elements.append(Paragraph(f"Institution Multidisciplinary Schedule | Version: {version_name} ({version_id}) | View: {view_title}", subtitle_style))
    elements.append(Spacer(1, 10))

    # Table Data Construction
    # Headers: Period / Time, Monday, Tuesday, Wednesday, Thursday, Friday
    headers = [Paragraph("Period / Time", header_style)]
    for d in DAYS_LIST:
        headers.append(Paragraph(d, header_style))

    table_data = [headers]

    for p in PERIODS_LIST:
        time_str = PERIOD_TIMES.get(p, "")
        p_label = Paragraph(f"<b>{p}</b><br/>{time_str}", cell_style)
        row = [p_label]

        for d in DAYS_LIST:
            raw_cell = grid_df.loc[p, d] if (p in grid_df.index and d in grid_df.columns) else ""
            clean_cell = _clean_for_reportlab(raw_cell)
            row.append(Paragraph(clean_cell, cell_style))

        table_data.append(row)

    # Style table
    col_widths = [85] + [140] * 5
    t = Table(table_data, colWidths=col_widths, repeatRows=1)
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1E3A8A')),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor('#CBD5E1')),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.HexColor('#F8FAFC'), colors.white]),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
    ]))
    elements.append(t)

    elements.append(Spacer(1, 12))
    # Summary note & Approval Signatures
    stat_text = f"Total Scheduled Sessions: {metrics.get('scheduled_sessions', len(grid_df))} | Conflicts: {metrics.get('conflict_count', 0)} | Solver Status: {metrics.get('solver_status', 'Validated')}"
    elements.append(Paragraph(f"<b>Audit Summary:</b> {stat_text}", subtitle_style))
    elements.append(Spacer(1, 15))

    sig_data = [
        [Paragraph("Prepared By:<br/><b>Timetable Committee</b>", subtitle_style),
         Paragraph("Verified By:<br/><b>Head of Department / Dean</b>", subtitle_style),
         Paragraph("Approved By:<br/><b>Principal / Academic Director</b>", subtitle_style)]
    ]
    sig_table = Table(sig_data, colWidths=[260, 260, 260])
    sig_table.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
    ]))
    elements.append(sig_table)

    doc.build(elements)
    buffer.seek(0)
    return buffer

def export_timetable_excel(version_id: str, version_name: str, view_title: str,
                           entries_df: pd.DataFrame, grid_df: pd.DataFrame,
                           metrics: Dict[str, Any]) -> io.BytesIO:
    """
    Generates a styled, multi-sheet Excel workbook (.xlsx) containing both
    the visual schedule grid and full session master records.
    """
    wb = Workbook()

    # Sheet 1: Visual Timetable Grid
    ws_grid = wb.active
    ws_grid.title = "Weekly Timetable Grid"
    ws_grid.views.sheetView[0].showGridLines = True

    # Styling constants
    header_fill = PatternFill(start_color="1E3A8A", end_color="1E3A8A", fill_type="solid")
    header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
    title_font = Font(name="Calibri", size=14, bold=True, color="1E293B")
    sub_font = Font(name="Calibri", size=10, italic=True, color="475569")
    thin_border = Border(
        left=Side(style='thin', color='CBD5E1'),
        right=Side(style='thin', color='CBD5E1'),
        top=Side(style='thin', color='CBD5E1'),
        bottom=Side(style='thin', color='CBD5E1')
    )

    # Title Block
    ws_grid["A1"] = "NATIONAL EDUCATION POLICY (NEP 2020) ACADEMIC TIMETABLE"
    ws_grid["A1"].font = title_font
    ws_grid["A2"] = f"View: {view_title} | Version: {version_name} ({version_id})"
    ws_grid["A2"].font = sub_font

    # Grid Headers
    headers = ["Period", "Time Slot"] + DAYS_LIST
    for col_idx, h in enumerate(headers, start=1):
        cell = ws_grid.cell(row=4, column=col_idx, value=h)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = thin_border

    # Grid Data
    for r_idx, p in enumerate(PERIODS_LIST, start=5):
        time_slot = PERIOD_TIMES.get(p, "")
        c_p = ws_grid.cell(row=r_idx, column=1, value=p)
        c_p.font = Font(bold=True)
        c_p.alignment = Alignment(horizontal="center", vertical="center")
        c_p.border = thin_border

        c_t = ws_grid.cell(row=r_idx, column=2, value=time_slot)
        c_t.alignment = Alignment(horizontal="center", vertical="center")
        c_t.border = thin_border

        for c_idx, d in enumerate(DAYS_LIST, start=3):
            val = grid_df.loc[p, d] if (p in grid_df.index and d in grid_df.columns) else ""
            clean_val = _strip_html(str(val))
            cell = ws_grid.cell(row=r_idx, column=c_idx, value=clean_val)
            cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            cell.border = thin_border

    # Adjust column widths
    ws_grid.column_dimensions['A'].width = 10
    ws_grid.column_dimensions['B'].width = 16
    for col_letter in ['C', 'D', 'E', 'F', 'G']:
        ws_grid.column_dimensions[col_letter].width = 28

    # Sheet 2: Master Session Entries
    ws_master = wb.create_sheet(title="Session Master Entries")
    master_cols = ["Session ID", "Course ID", "Course Name", "Faculty Name", "Classroom", "Day", "Period", "Duration", "Type"]
    for c_idx, col_name in enumerate(master_cols, start=1):
        c = ws_master.cell(row=1, column=c_idx, value=col_name)
        c.fill = header_fill
        c.font = header_font
        c.alignment = Alignment(horizontal="center", vertical="center")
        c.border = thin_border

    if not entries_df.empty:
        for r_idx, (_, row) in enumerate(entries_df.iterrows(), start=2):
            vals = [
                row.get("session_id", ""),
                row.get("course_id", ""),
                row.get("course_name", ""),
                row.get("faculty_name", row.get("faculty_id", "")),
                row.get("classroom_name", row.get("classroom_id", "")),
                row.get("day", ""),
                row.get("period_id", ""),
                row.get("duration_periods", 1),
                row.get("course_type", "")
            ]
            for c_idx, v in enumerate(vals, start=1):
                cell = ws_master.cell(row=r_idx, column=c_idx, value=v)
                cell.border = thin_border
                cell.alignment = Alignment(vertical="center")

    for col in ws_master.columns:
        max_len = max(len(str(cell.value or '')) for cell in col)
        col_letter = col[0].column_letter
        ws_master.column_dimensions[col_letter].width = max(max_len + 3, 12)

    buffer = io.BytesIO()
    wb.save(buffer)
    buffer.seek(0)
    return buffer

def export_timetable_txt(version_id: str, version_name: str, view_title: str,
                         grid_df: pd.DataFrame, metrics: Dict[str, Any]) -> str:
    """
    Generates a clean, readable plain-text report of the academic timetable.
    """
    lines = []
    lines.append("=" * 80)
    lines.append("   NATIONAL EDUCATION POLICY (NEP 2020) ACADEMIC TIMETABLE SYSTEM")
    lines.append("=" * 80)
    lines.append(f"View Title  : {view_title}")
    lines.append(f"Version     : {version_name} ({version_id})")
    lines.append(f"Status      : {metrics.get('solver_status', 'Validated')}")
    lines.append(f"Sessions    : {metrics.get('scheduled_sessions', 0)} Scheduled | Conflicts: {metrics.get('conflict_count', 0)}")
    lines.append("-" * 80)
    lines.append("")

    for day in DAYS_LIST:
        lines.append(f"### {day.upper()} ###")
        lines.append("-" * 45)
        for p in PERIODS_LIST:
            time_slot = PERIOD_TIMES.get(p, "")
            val = grid_df.loc[p, day] if (p in grid_df.index and day in grid_df.columns) else ""
            clean_val = _strip_html(str(val)).replace("\n", " | ")
            if clean_val.strip() and "Free / Self-Study" not in clean_val:
                lines.append(f"  [{p} | {time_slot}] : {clean_val}")
            else:
                lines.append(f"  [{p} | {time_slot}] : [Free / Self-Study Period]")
        lines.append("")

    lines.append("=" * 80)
    lines.append("Generated by AI Timetable Generator with Google OR-Tools CP-SAT Optimization")
    lines.append("=" * 80)

    return "\n".join(lines)
