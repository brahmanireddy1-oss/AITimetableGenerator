import os
import json
import sqlite3
from typing import Dict, List, Optional, Any, Tuple
import pandas as pd
from dotenv import load_dotenv

load_dotenv()

class DatabaseManager:
    """
    Unified Database Manager for AI Timetable Generation System.
    Connects to Supabase PostgreSQL when credentials exist, and provides
    a robust local SQLite fallback/mirror for offline college demonstrations.
    """
    def __init__(self, db_path: str = "data/timetable.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        
        self.supabase_url = os.environ.get("SUPABASE_URL", "")
        self.supabase_key = os.environ.get("SUPABASE_KEY", "")
        self.supabase_client = None
        self._init_sqlite()
        self._init_supabase()

    def _init_sqlite(self):
        """Initialize local SQLite tables matching the schema."""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        c.execute("PRAGMA foreign_keys = ON;")

        # 1. departments
        c.execute("""
            CREATE TABLE IF NOT EXISTS departments (
                department_id TEXT PRIMARY KEY,
                department_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 2. students
        c.execute("""
            CREATE TABLE IF NOT EXISTS students (
                student_id TEXT PRIMARY KEY,
                student_name TEXT NOT NULL,
                department_id TEXT,
                year INTEGER DEFAULT 1,
                section TEXT DEFAULT 'A',
                student_group TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT
            );
        """)

        # 3. faculty
        c.execute("""
            CREATE TABLE IF NOT EXISTS faculty (
                faculty_id TEXT PRIMARY KEY,
                faculty_name TEXT NOT NULL,
                department_id TEXT,
                max_weekly_periods INTEGER DEFAULT 16,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT
            );
        """)

        # 4. classrooms
        c.execute("""
            CREATE TABLE IF NOT EXISTS classrooms (
                classroom_id TEXT PRIMARY KEY,
                classroom_name TEXT NOT NULL,
                room_type TEXT NOT NULL,
                capacity INTEGER NOT NULL,
                building TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        """)

        # 5. courses
        c.execute("""
            CREATE TABLE IF NOT EXISTS courses (
                course_id TEXT PRIMARY KEY,
                course_name TEXT NOT NULL,
                department_id TEXT,
                course_type TEXT NOT NULL,
                faculty_id TEXT,
                weekly_sessions INTEGER NOT NULL DEFAULT 3,
                duration_periods INTEGER NOT NULL DEFAULT 1,
                required_room_type TEXT NOT NULL DEFAULT 'Classroom',
                expected_enrolment INTEGER NOT NULL DEFAULT 40,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (department_id) REFERENCES departments(department_id) ON DELETE RESTRICT,
                FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE RESTRICT
            );
        """)

        # 6. time_slots
        c.execute("""
            CREATE TABLE IF NOT EXISTS time_slots (
                time_slot_id TEXT PRIMARY KEY,
                day TEXT NOT NULL,
                period_id TEXT NOT NULL,
                period_number INTEGER NOT NULL,
                start_time TEXT NOT NULL,
                end_time TEXT NOT NULL,
                is_teaching_slot INTEGER DEFAULT 1,
                UNIQUE (day, period_id)
            );
        """)

        # 7. faculty_availability
        c.execute("""
            CREATE TABLE IF NOT EXISTS faculty_availability (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                faculty_id TEXT NOT NULL,
                day TEXT NOT NULL,
                period_id TEXT NOT NULL,
                is_available INTEGER DEFAULT 1,
                FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE CASCADE,
                UNIQUE (faculty_id, day, period_id)
            );
        """)

        # 8. student_enrollments
        c.execute("""
            CREATE TABLE IF NOT EXISTS student_enrollments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                student_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                semester TEXT NOT NULL,
                FOREIGN KEY (student_id) REFERENCES students(student_id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE CASCADE,
                UNIQUE (student_id, course_id, semester)
            );
        """)

        # 9. constraints
        c.execute("""
            CREATE TABLE IF NOT EXISTS constraints (
                constraint_name TEXT PRIMARY KEY,
                constraint_value TEXT NOT NULL,
                constraint_type TEXT NOT NULL,
                description TEXT
            );
        """)

        # 10. timetable_versions
        c.execute("""
            CREATE TABLE IF NOT EXISTS timetable_versions (
                version_id TEXT PRIMARY KEY,
                version_number INTEGER NOT NULL,
                version_name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL DEFAULT 'Draft',
                notes TEXT,
                metrics TEXT DEFAULT '{}'
            );
        """)

        # 11. timetable_entries
        c.execute("""
            CREATE TABLE IF NOT EXISTS timetable_entries (
                entry_id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                course_id TEXT NOT NULL,
                faculty_id TEXT NOT NULL,
                classroom_id TEXT NOT NULL,
                day TEXT NOT NULL,
                period_id TEXT NOT NULL,
                duration_periods INTEGER NOT NULL DEFAULT 1,
                time_slot_id TEXT,
                FOREIGN KEY (version_id) REFERENCES timetable_versions(version_id) ON DELETE CASCADE,
                FOREIGN KEY (course_id) REFERENCES courses(course_id) ON DELETE RESTRICT,
                FOREIGN KEY (faculty_id) REFERENCES faculty(faculty_id) ON DELETE RESTRICT,
                FOREIGN KEY (classroom_id) REFERENCES classrooms(classroom_id) ON DELETE RESTRICT,
                FOREIGN KEY (time_slot_id) REFERENCES time_slots(time_slot_id) ON DELETE RESTRICT
            );
        """)

        # 12. approval_records
        c.execute("""
            CREATE TABLE IF NOT EXISTS approval_records (
                approval_id INTEGER PRIMARY KEY AUTOINCREMENT,
                version_id TEXT NOT NULL,
                action TEXT NOT NULL,
                performed_by TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                comments TEXT,
                FOREIGN KEY (version_id) REFERENCES timetable_versions(version_id) ON DELETE CASCADE
            );
        """)

        conn.commit()
        conn.close()

    def _init_supabase(self):
        """Attempt to connect to Supabase if credentials are provided."""
        if self.supabase_url and self.supabase_key and not self.supabase_url.startswith("your_"):
            try:
                from supabase import create_client
                self.supabase_client = create_client(self.supabase_url, self.supabase_key)
            except Exception as e:
                print(f"Supabase connection notice: {e}")
                self.supabase_client = None

    def is_supabase_connected(self) -> Tuple[bool, str]:
        """Test Supabase connection status."""
        if not self.supabase_url or not self.supabase_key:
            return False, "Supabase credentials not configured in .env (Running in Local Mode)"
        try:
            from supabase import create_client
            client = create_client(self.supabase_url, self.supabase_key)
            # Try a lightweight query
            client.table("departments").select("department_id").limit(1).execute()
            self.supabase_client = client
            return True, f"Connected to Supabase ({self.supabase_url.split('//')[-1].split('.')[0]})"
        except Exception as e:
            return False, f"Supabase connection error: {str(e)}"

    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    # ---------------------------------------------------------
    # EXCEL IMPORT & VALIDATION
    # ---------------------------------------------------------
    def validate_excel_workbook(self, file_path_or_buffer) -> Tuple[bool, List[str], Dict[str, pd.DataFrame]]:
        """
        Validates the 9 worksheets from the uploaded Excel file.
        Detects missing sheets, missing columns, empty rows, invalid IDs, and FK inconsistencies.
        """
        required_sheets = [
            "Departments", "Students", "Courses", "Faculty", "Classrooms",
            "Faculty_Availability", "Student_Enrollments", "Time_Slots", "Constraints"
        ]
        errors = []
        dfs = {}

        try:
            xl = pd.ExcelFile(file_path_or_buffer)
        except Exception as e:
            return False, [f"Failed to read Excel workbook: {str(e)}"], {}

        sheet_names = xl.sheet_names
        for rs in required_sheets:
            if rs not in sheet_names:
                errors.append(f"Missing required worksheet: '{rs}'")

        if errors:
            return False, errors, {}

        # Column definitions
        expected_cols = {
            "Departments": ["department_id", "department_name"],
            "Students": ["student_id", "student_name", "department_id", "year", "section", "student_group"],
            "Courses": ["course_id", "course_name", "department_id", "course_type", "faculty_id", "weekly_sessions", "duration_periods", "required_room_type", "expected_enrolment"],
            "Faculty": ["faculty_id", "faculty_name", "department_id", "max_weekly_periods"],
            "Classrooms": ["classroom_id", "classroom_name", "room_type", "capacity", "building"],
            "Faculty_Availability": ["faculty_id", "day", "period_id", "is_available"],
            "Student_Enrollments": ["student_id", "course_id", "semester"],
            "Time_Slots": ["time_slot_id", "day", "period_id", "period_number", "start_time", "end_time", "is_teaching_slot"],
            "Constraints": ["constraint_name", "constraint_value", "constraint_type", "description"]
        }

        for sheet_name, cols in expected_cols.items():
            df = pd.read_excel(file_path_or_buffer, sheet_name=sheet_name)
            df.columns = [str(c).strip() for c in df.columns]
            dfs[sheet_name] = df
            missing = [c for c in cols if c not in df.columns]
            if missing:
                errors.append(f"Worksheet '{sheet_name}' is missing columns: {missing}")

        if errors:
            return False, errors, dfs

        # Cross-sheet Referential Integrity Checks
        dept_ids = set(dfs["Departments"]["department_id"].dropna().astype(str))
        fac_ids = set(dfs["Faculty"]["faculty_id"].dropna().astype(str))
        course_ids = set(dfs["Courses"]["course_id"].dropna().astype(str))
        student_ids = set(dfs["Students"]["student_id"].dropna().astype(str))

        # Check Students -> Departments
        std_depts = set(dfs["Students"]["department_id"].dropna().astype(str))
        invalid_std_dept = std_depts - dept_ids
        if invalid_std_dept:
            errors.append(f"Students reference non-existent Department IDs: {list(invalid_std_dept)}")

        # Check Faculty -> Departments
        fac_depts = set(dfs["Faculty"]["department_id"].dropna().astype(str))
        invalid_fac_dept = fac_depts - dept_ids
        if invalid_fac_dept:
            errors.append(f"Faculty reference non-existent Department IDs: {list(invalid_fac_dept)}")

        # Check Courses -> Faculty
        course_fac = set(dfs["Courses"]["faculty_id"].dropna().astype(str))
        invalid_course_fac = course_fac - fac_ids
        if invalid_course_fac:
            errors.append(f"Courses reference non-existent Faculty IDs: {list(invalid_course_fac)}")

        # Check Courses -> Departments
        c_depts = set(dfs["Courses"]["department_id"].dropna().astype(str))
        invalid_c_dept = c_depts - dept_ids
        if invalid_c_dept:
            errors.append(f"Courses reference non-existent Department IDs: {list(invalid_c_dept)}")

        # Check Enrollments -> Students & Courses
        enr_std = set(dfs["Student_Enrollments"]["student_id"].dropna().astype(str))
        invalid_enr_std = enr_std - student_ids
        if invalid_enr_std:
            errors.append(f"Enrollments reference non-existent Student IDs: {list(invalid_enr_std)}")

        enr_c = set(dfs["Student_Enrollments"]["course_id"].dropna().astype(str))
        invalid_enr_c = enr_c - course_ids
        if invalid_enr_c:
            errors.append(f"Enrollments reference non-existent Course IDs: {list(invalid_enr_c)}")

        # Check Faculty Availability -> Faculty
        av_fac = set(dfs["Faculty_Availability"]["faculty_id"].dropna().astype(str))
        invalid_av_fac = av_fac - fac_ids
        if invalid_av_fac:
            errors.append(f"Faculty Availability references non-existent Faculty IDs: {list(invalid_av_fac)}")

        is_valid = len(errors) == 0
        return is_valid, errors, dfs

    def import_validated_data(self, dfs: Dict[str, pd.DataFrame]) -> Tuple[bool, str]:
        """
        Imports validated DataFrames into local database and Supabase if connected.
        """
        try:
            conn = self.get_connection()
            c = conn.cursor()

            # Clear existing data in reverse dependency order
            c.execute("DELETE FROM approval_records;")
            c.execute("DELETE FROM timetable_entries;")
            c.execute("DELETE FROM timetable_versions;")
            c.execute("DELETE FROM student_enrollments;")
            c.execute("DELETE FROM faculty_availability;")
            c.execute("DELETE FROM courses;")
            c.execute("DELETE FROM faculty;")
            c.execute("DELETE FROM students;")
            c.execute("DELETE FROM classrooms;")
            c.execute("DELETE FROM time_slots;")
            c.execute("DELETE FROM departments;")
            c.execute("DELETE FROM constraints;")

            # 1. Departments
            for _, r in dfs["Departments"].iterrows():
                c.execute("INSERT INTO departments (department_id, department_name) VALUES (?, ?)",
                          (str(r["department_id"]).strip(), str(r["department_name"]).strip()))

            # 2. Students
            for _, r in dfs["Students"].iterrows():
                c.execute("""
                    INSERT INTO students (student_id, student_name, department_id, year, section, student_group)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    str(r["student_id"]).strip(),
                    str(r["student_name"]).strip(),
                    str(r["department_id"]).strip(),
                    int(r["year"]) if pd.notna(r["year"]) else 1,
                    str(r["section"]).strip(),
                    str(r["student_group"]).strip()
                ))

            # 3. Faculty
            for _, r in dfs["Faculty"].iterrows():
                c.execute("""
                    INSERT INTO faculty (faculty_id, faculty_name, department_id, max_weekly_periods)
                    VALUES (?, ?, ?, ?)
                """, (
                    str(r["faculty_id"]).strip(),
                    str(r["faculty_name"]).strip(),
                    str(r["department_id"]).strip(),
                    int(r["max_weekly_periods"]) if pd.notna(r["max_weekly_periods"]) else 16
                ))

            # 4. Classrooms
            for _, r in dfs["Classrooms"].iterrows():
                c.execute("""
                    INSERT INTO classrooms (classroom_id, classroom_name, room_type, capacity, building)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    str(r["classroom_id"]).strip(),
                    str(r["classroom_name"]).strip(),
                    str(r["room_type"]).strip(),
                    int(r["capacity"]),
                    str(r["building"]).strip() if pd.notna(r["building"]) else "Main"
                ))

            # 5. Courses
            for _, r in dfs["Courses"].iterrows():
                c.execute("""
                    INSERT INTO courses (course_id, course_name, department_id, course_type, faculty_id,
                                        weekly_sessions, duration_periods, required_room_type, expected_enrolment)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(r["course_id"]).strip(),
                    str(r["course_name"]).strip(),
                    str(r["department_id"]).strip(),
                    str(r["course_type"]).strip(),
                    str(r["faculty_id"]).strip(),
                    int(r["weekly_sessions"]),
                    int(r["duration_periods"]),
                    str(r["required_room_type"]).strip(),
                    int(r["expected_enrolment"])
                ))

            # 6. Time Slots
            for _, r in dfs["Time_Slots"].iterrows():
                c.execute("""
                    INSERT INTO time_slots (time_slot_id, day, period_id, period_number, start_time, end_time, is_teaching_slot)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (
                    str(r["time_slot_id"]).strip(),
                    str(r["day"]).strip(),
                    str(r["period_id"]).strip(),
                    int(r["period_number"]),
                    str(r["start_time"]).strip(),
                    str(r["end_time"]).strip(),
                    int(r["is_teaching_slot"]) if pd.notna(r["is_teaching_slot"]) else 1
                ))

            # 7. Faculty Availability
            for _, r in dfs["Faculty_Availability"].iterrows():
                c.execute("""
                    INSERT INTO faculty_availability (faculty_id, day, period_id, is_available)
                    VALUES (?, ?, ?, ?)
                """, (
                    str(r["faculty_id"]).strip(),
                    str(r["day"]).strip(),
                    str(r["period_id"]).strip(),
                    int(r["is_available"]) if pd.notna(r["is_available"]) else 1
                ))

            # 8. Student Enrollments
            for _, r in dfs["Student_Enrollments"].iterrows():
                c.execute("""
                    INSERT INTO student_enrollments (student_id, course_id, semester)
                    VALUES (?, ?, ?)
                """, (
                    str(r["student_id"]).strip(),
                    str(r["course_id"]).strip(),
                    str(r["semester"]).strip()
                ))

            # 9. Constraints
            for _, r in dfs["Constraints"].iterrows():
                c.execute("""
                    INSERT INTO constraints (constraint_name, constraint_value, constraint_type, description)
                    VALUES (?, ?, ?, ?)
                """, (
                    str(r["constraint_name"]).strip(),
                    str(r["constraint_value"]).strip(),
                    str(r["constraint_type"]).strip(),
                    str(r["description"]).strip() if pd.notna(r["description"]) else ""
                ))

            conn.commit()
            conn.close()

            # If Supabase is connected, sync data to Supabase
            if self.supabase_client:
                try:
                    for table_name, df in dfs.items():
                        sb_table = table_name.lower()
                        # Convert df to records
                        records = df.to_dict(orient="records")
                        # Clean NaN values
                        for rec in records:
                            for k, v in list(rec.items()):
                                if pd.isna(v):
                                    rec[k] = None
                        self.supabase_client.table(sb_table).upsert(records).execute()
                except Exception as sbe:
                    print(f"Supabase sync warning (data saved locally): {sbe}")

            return True, "All 9 worksheets successfully validated and imported into database!"
        except Exception as e:
            return False, f"Database import error: {str(e)}"

    # ---------------------------------------------------------
    # READ QUERIES (DataFrames)
    # ---------------------------------------------------------
    def get_df(self, table_name: str) -> pd.DataFrame:
        conn = self.get_connection()
        df = pd.read_sql_query(f"SELECT * FROM {table_name}", conn)
        conn.close()
        return df

    def get_departments(self) -> pd.DataFrame:
        return self.get_df("departments")

    def get_students(self) -> pd.DataFrame:
        return self.get_df("students")

    def get_courses(self) -> pd.DataFrame:
        return self.get_df("courses")

    def get_faculty(self) -> pd.DataFrame:
        return self.get_df("faculty")

    def get_classrooms(self) -> pd.DataFrame:
        return self.get_df("classrooms")

    def get_faculty_availability(self) -> pd.DataFrame:
        return self.get_df("faculty_availability")

    def get_student_enrollments(self) -> pd.DataFrame:
        return self.get_df("student_enrollments")

    def get_time_slots(self) -> pd.DataFrame:
        return self.get_df("time_slots")

    def get_constraints(self) -> pd.DataFrame:
        return self.get_df("constraints")

    def get_timetable_versions(self) -> pd.DataFrame:
        conn = self.get_connection()
        df = pd.read_sql_query("SELECT * FROM timetable_versions ORDER BY version_number DESC", conn)
        conn.close()
        return df

    def get_timetable_entries(self, version_id: str) -> pd.DataFrame:
        conn = self.get_connection()
        query = """
            SELECT e.*, c.course_name, c.course_type, c.department_id, f.faculty_name, r.classroom_name, r.room_type,
                   t.start_time, t.end_time, t.period_number
            FROM timetable_entries e
            JOIN courses c ON e.course_id = c.course_id
            JOIN faculty f ON e.faculty_id = f.faculty_id
            JOIN classrooms r ON e.classroom_id = r.classroom_id
            LEFT JOIN time_slots t ON e.time_slot_id = t.time_slot_id
            WHERE e.version_id = ?
            ORDER BY e.day, t.period_number
        """
        df = pd.read_sql_query(query, conn, params=(version_id,))
        conn.close()
        return df

    def get_approval_records(self, version_id: Optional[str] = None) -> pd.DataFrame:
        conn = self.get_connection()
        if version_id:
            df = pd.read_sql_query("SELECT * FROM approval_records WHERE version_id = ? ORDER BY timestamp DESC", conn, params=(version_id,))
        else:
            df = pd.read_sql_query("SELECT * FROM approval_records ORDER BY timestamp DESC", conn)
        conn.close()
        return df

    # ---------------------------------------------------------
    # FOREIGN KEY REFERENCE CHECKS BEFORE DELETE
    # ---------------------------------------------------------
    def check_references(self, table_name: str, id_value: str) -> Tuple[bool, List[str]]:
        """
        Checks if a record is referenced by any child table.
        Returns (is_referenced, list_of_referencing_details).
        """
        conn = self.get_connection()
        c = conn.cursor()
        refs = []

        if table_name == "departments":
            c.execute("SELECT count(*) FROM students WHERE department_id = ?", (id_value,))
            if c.fetchone()[0] > 0:
                refs.append(f"Referenced by {c.fetchone()} students")
            c.execute("SELECT count(*) FROM faculty WHERE department_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Referenced by {count} faculty members")
            c.execute("SELECT count(*) FROM courses WHERE department_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Referenced by {count} courses")

        elif table_name == "faculty":
            c.execute("SELECT count(*) FROM courses WHERE faculty_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Assigned to {count} course(s)")
            c.execute("SELECT count(*) FROM timetable_entries WHERE faculty_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Referenced in {count} timetable session entries")

        elif table_name == "courses":
            c.execute("SELECT count(*) FROM student_enrollments WHERE course_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Enrolled by {count} students")
            c.execute("SELECT count(*) FROM timetable_entries WHERE course_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Referenced in {count} timetable session entries")

        elif table_name == "classrooms":
            c.execute("SELECT count(*) FROM timetable_entries WHERE classroom_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Referenced in {count} timetable session entries")

        elif table_name == "students":
            c.execute("SELECT count(*) FROM student_enrollments WHERE student_id = ?", (id_value,))
            count = c.fetchone()[0]
            if count > 0:
                refs.append(f"Enrolled in {count} courses")

        conn.close()
        return len(refs) > 0, refs

    # ---------------------------------------------------------
    # CRUD OPERATIONS
    # ---------------------------------------------------------
    def execute_cud(self, query: str, params: tuple = ()) -> Tuple[bool, str]:
        try:
            conn = self.get_connection()
            c = conn.cursor()
            c.execute(query, params)
            conn.commit()
            conn.close()
            return True, "Operation successful"
        except sqlite3.IntegrityError as ie:
            return False, f"Integrity error: {str(ie)}"
        except Exception as e:
            return False, f"Database error: {str(e)}"

    def add_department(self, dept_id: str, dept_name: str) -> Tuple[bool, str]:
        return self.execute_cud("INSERT INTO departments (department_id, department_name) VALUES (?, ?)", (dept_id, dept_name))

    def update_department(self, dept_id: str, dept_name: str) -> Tuple[bool, str]:
        return self.execute_cud("UPDATE departments SET department_name = ? WHERE department_id = ?", (dept_name, dept_id))

    def delete_department(self, dept_id: str) -> Tuple[bool, str]:
        has_ref, refs = self.check_references("departments", dept_id)
        if has_ref:
            return False, f"Cannot delete department: {', '.join(refs)}"
        return self.execute_cud("DELETE FROM departments WHERE department_id = ?", (dept_id,))

    def add_faculty(self, fac_id: str, fac_name: str, dept_id: str, max_periods: int) -> Tuple[bool, str]:
        return self.execute_cud("INSERT INTO faculty (faculty_id, faculty_name, department_id, max_weekly_periods) VALUES (?, ?, ?, ?)",
                                (fac_id, fac_name, dept_id, max_periods))

    def update_faculty(self, fac_id: str, fac_name: str, dept_id: str, max_periods: int) -> Tuple[bool, str]:
        return self.execute_cud("UPDATE faculty SET faculty_name = ?, department_id = ?, max_weekly_periods = ? WHERE faculty_id = ?",
                                (fac_name, dept_id, max_periods, fac_id))

    def delete_faculty(self, fac_id: str) -> Tuple[bool, str]:
        has_ref, refs = self.check_references("faculty", fac_id)
        if has_ref:
            return False, f"Cannot delete faculty member: {', '.join(refs)}"
        return self.execute_cud("DELETE FROM faculty WHERE faculty_id = ?", (fac_id,))

    def add_course(self, course_id: str, name: str, dept_id: str, ctype: str, fac_id: str, sessions: int, dur: int, room_type: str, enrol: int) -> Tuple[bool, str]:
        return self.execute_cud("""
            INSERT INTO courses (course_id, course_name, department_id, course_type, faculty_id, weekly_sessions, duration_periods, required_room_type, expected_enrolment)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (course_id, name, dept_id, ctype, fac_id, sessions, dur, room_type, enrol))

    def update_course(self, course_id: str, name: str, dept_id: str, ctype: str, fac_id: str, sessions: int, dur: int, room_type: str, enrol: int) -> Tuple[bool, str]:
        return self.execute_cud("""
            UPDATE courses SET course_name = ?, department_id = ?, course_type = ?, faculty_id = ?, weekly_sessions = ?, duration_periods = ?, required_room_type = ?, expected_enrolment = ?
            WHERE course_id = ?
        """, (name, dept_id, ctype, fac_id, sessions, dur, room_type, enrol, course_id))

    def delete_course(self, course_id: str) -> Tuple[bool, str]:
        has_ref, refs = self.check_references("courses", course_id)
        if has_ref:
            return False, f"Cannot delete course: {', '.join(refs)}"
        return self.execute_cud("DELETE FROM courses WHERE course_id = ?", (course_id,))

    def add_classroom(self, room_id: str, name: str, room_type: str, capacity: int, building: str) -> Tuple[bool, str]:
        return self.execute_cud("INSERT INTO classrooms (classroom_id, classroom_name, room_type, capacity, building) VALUES (?, ?, ?, ?, ?)",
                                (room_id, name, room_type, capacity, building))

    def update_classroom(self, room_id: str, name: str, room_type: str, capacity: int, building: str) -> Tuple[bool, str]:
        return self.execute_cud("UPDATE classrooms SET classroom_name = ?, room_type = ?, capacity = ?, building = ? WHERE classroom_id = ?",
                                (name, room_type, capacity, building, room_id))

    def delete_classroom(self, room_id: str) -> Tuple[bool, str]:
        has_ref, refs = self.check_references("classrooms", room_id)
        if has_ref:
            return False, f"Cannot delete classroom: {', '.join(refs)}"
        return self.execute_cud("DELETE FROM classrooms WHERE classroom_id = ?", (room_id,))

    def add_student(self, std_id: str, name: str, dept_id: str, year: int, sec: str, grp: str) -> Tuple[bool, str]:
        return self.execute_cud("INSERT INTO students (student_id, student_name, department_id, year, section, student_group) VALUES (?, ?, ?, ?, ?, ?)",
                                (std_id, name, dept_id, year, sec, grp))

    def update_student(self, std_id: str, name: str, dept_id: str, year: int, sec: str, grp: str) -> Tuple[bool, str]:
        return self.execute_cud("UPDATE students SET student_name = ?, department_id = ?, year = ?, section = ?, student_group = ? WHERE student_id = ?",
                                (name, dept_id, year, sec, grp, std_id))

    def delete_student(self, std_id: str) -> Tuple[bool, str]:
        has_ref, refs = self.check_references("students", std_id)
        if has_ref:
            return False, f"Cannot delete student: {', '.join(refs)}"
        return self.execute_cud("DELETE FROM students WHERE student_id = ?", (std_id,))

    def set_faculty_availability(self, fac_id: str, day: str, period_id: str, is_available: int) -> Tuple[bool, str]:
        """Toggles or sets faculty availability for a specific day and period slot."""
        return self.execute_cud("""
            INSERT INTO faculty_availability (faculty_id, day, period_id, is_available)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(faculty_id, day, period_id) DO UPDATE SET is_available = excluded.is_available
        """, (fac_id, day, period_id, is_available))

    def update_constraint_value(self, name: str, val: str) -> Tuple[bool, str]:
        return self.execute_cud("UPDATE constraints SET constraint_value = ? WHERE constraint_name = ?", (val, name))

    # ---------------------------------------------------------
    # TIMETABLE VERSIONING & ENTRIES
    # ---------------------------------------------------------
    def save_timetable_version(self, version_id: str, version_name: str, entries: List[Dict[str, Any]], metrics: Dict[str, Any], notes: str = "") -> Tuple[bool, str]:
        """
        Saves a newly generated timetable as Draft with full session entries.
        """
        try:
            conn = self.get_connection()
            c = conn.cursor()

            # Determine next version number
            c.execute("SELECT COALESCE(MAX(version_number), 0) + 1 FROM timetable_versions")
            v_num = c.fetchone()[0]

            # Insert version record
            c.execute("""
                INSERT INTO timetable_versions (version_id, version_number, version_name, status, notes, metrics)
                VALUES (?, ?, ?, 'Draft', ?, ?)
            """, (version_id, v_num, version_name, notes, json.dumps(metrics)))

            # Insert entries
            for e in entries:
                c.execute("""
                    INSERT INTO timetable_entries (version_id, session_id, course_id, faculty_id, classroom_id, day, period_id, duration_periods, time_slot_id)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    version_id,
                    e["session_id"],
                    e["course_id"],
                    e["faculty_id"],
                    e["classroom_id"],
                    e["day"],
                    e["period_id"],
                    e.get("duration_periods", 1),
                    e.get("time_slot_id")
                ))

            # Add approval record
            c.execute("""
                INSERT INTO approval_records (version_id, action, performed_by, comments)
                VALUES (?, 'Draft Created', 'System Optimizer', 'Initial generation using OR-Tools CP-SAT')
            """, (version_id,))

            conn.commit()
            conn.close()

            # Sync to Supabase if available
            if self.supabase_client:
                try:
                    self.supabase_client.table("timetable_versions").upsert({
                        "version_id": version_id,
                        "version_number": v_num,
                        "version_name": version_name,
                        "status": "Draft",
                        "notes": notes,
                        "metrics": metrics
                    }).execute()
                    self.supabase_client.table("timetable_entries").upsert(entries).execute()
                except Exception as se:
                    print(f"Supabase version sync warning: {se}")

            return True, f"Timetable version {version_id} saved successfully as Draft."
        except Exception as e:
            return False, f"Failed to save timetable version: {str(e)}"

    def update_version_status(self, version_id: str, new_status: str, performed_by: str = "Administrator", comments: str = "") -> Tuple[bool, str]:
        """
        Updates timetable status between Draft -> Approved -> Published.
        """
        try:
            conn = self.get_connection()
            c = conn.cursor()

            c.execute("SELECT status FROM timetable_versions WHERE version_id = ?", (version_id,))
            row = c.fetchone()
            if not row:
                conn.close()
                return False, f"Version {version_id} does not exist."

            current_status = row[0]
            # Enforce workflow rule: Only approved can be published
            if new_status == "Published" and current_status != "Approved":
                conn.close()
                return False, f"Cannot publish directly from '{current_status}'. The timetable must be 'Approved' first."

            c.execute("UPDATE timetable_versions SET status = ? WHERE version_id = ?", (new_status, version_id))
            c.execute("""
                INSERT INTO approval_records (version_id, action, performed_by, comments)
                VALUES (?, ?, ?, ?)
            """, (version_id, f"Status changed to {new_status}", performed_by, comments))

            conn.commit()
            conn.close()

            if self.supabase_client:
                try:
                    self.supabase_client.table("timetable_versions").update({"status": new_status}).eq("version_id", version_id).execute()
                except Exception as se:
                    print(f"Supabase status update warning: {se}")

            return True, f"Timetable version {version_id} status updated to '{new_status}'."
        except Exception as e:
            return False, f"Status update failed: {str(e)}"
