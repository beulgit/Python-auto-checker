import streamlit as st
import subprocess, tempfile, os, uuid, datetime, sqlite3

# ---------- App Config ----------
st.set_page_config(page_title="Python Auto-Checker IDE", layout="wide")

# ---------- Database Init ----------
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("submissions.db", check_same_thread=False)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_name TEXT,
            question TEXT,
            code TEXT,
            stdout TEXT,
            stderr TEXT,
            correct INTEGER,
            created_at TEXT
        )
    """)
    conn.commit()
    return conn

conn = get_conn()

# ---------- Student Identification ----------
student_name = st.text_input("Enter your Name / Roll No:")
if not student_name.strip():
    st.warning("⚠️ Please enter your name before running or submitting code.")

# ---------- Mode Selection ----------
mode = st.sidebar.selectbox("Mode", ["Student", "Teacher"])

# ---------- Teacher Upload Section ----------
st.sidebar.header("Upload Question File (Teacher)")
question_file = st.sidebar.file_uploader("Upload TXT file (Question + testcases)", type=["txt"])

question_text = ""
testcases = []  # 🔹 store multiple testcases

if question_file:
    content = question_file.read().decode("utf-8").split("###")
    # First element is the question
    question_text = content[0].strip()
    # Remaining should come in pairs (input, output)
    if (len(content) - 1) % 2 == 0:
        for i in range(1, len(content), 2):
            inp, out = content[i].strip(), content[i+1].strip()
            testcases.append((inp, out))
    else:
        st.sidebar.error("Invalid format. Use: Question###Input1###Output1###Input2###Output2###...")

# ---------- Student Mode ----------
if mode == "Student":
    st.title("Python Learning IDE — Student Mode")
    if question_text:
        st.subheader("Question")
        st.write(question_text)

    code = st.text_area("Write your Python Code here:", height=250)

    run_clicked = st.button("Run Code")
    submit_clicked = st.button("Submit to Teacher")

    if run_clicked and code.strip() != "" and testcases:
        tmp_path = os.path.join(tempfile.gettempdir(), f"student_{uuid.uuid4().hex}.py")
        with open(tmp_path, "w", encoding="utf-8") as f:
            f.write(code)

        all_correct = True
        combined_stdout = []
        combined_stderr = []

        for idx, (expected_input, expected_output) in enumerate(testcases, start=1):
            try:
                proc = subprocess.run(
                    ["python", "-I", tmp_path],
                    input=expected_input,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5
                )

                actual = proc.stdout.replace("\r\n", "\n").rstrip()
                expected = expected_output.replace("\r\n", "\n").rstrip()

                st.write(f"---")
                st.subheader(f"Test Case {idx}")
                st.write(f"**Input:**")
                st.code(expected_input)
                st.write("**Program Output:**")
                st.code(actual if actual else "(no output)")

                if proc.stderr:
                    st.subheader("Runtime Error")
                    st.code(proc.stderr)

                if actual == expected:
                    st.success("✅ Passed")
                else:
                    st.error("❌ Failed")
                    st.write("**Expected Output:**")
                    st.code(expected)
                    st.write("**Actual Output:**")
                    st.code(actual)
                    all_correct = False

                combined_stdout.append(actual)
                combined_stderr.append(proc.stderr)

            except subprocess.TimeoutExpired:
                st.error(f"⏳ Timeout in Test Case {idx}: took longer than 5 seconds.")
                all_correct = False

        # Save in session state
        st.session_state["last_correct"] = 1 if all_correct else 0
        st.session_state["last_stdout"] = "\n---\n".join(combined_stdout)
        st.session_state["last_stderr"] = "\n---\n".join(filter(None, combined_stderr))

        try:
            os.remove(tmp_path)
        except OSError:
            pass

    # ---------- Submit ----------
    if submit_clicked:
        if not student_name.strip():
            st.warning("⚠️ Enter your name before submitting.")
        elif not code.strip():
            st.warning("⚠️ Write some code before submitting.")
        else:
            correct = st.session_state.get("last_correct", 0)
            stdout = st.session_state.get("last_stdout", "")
            stderr = st.session_state.get("last_stderr", "")
            with conn:
                conn.execute(
                    "INSERT INTO submissions (student_name, question, code, stdout, stderr, correct, created_at) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        student_name.strip(),
                        question_text.strip() if question_text else "(No question provided)",
                        code,
                        stdout,
                        stderr,
                        correct,
                        datetime.datetime.now().isoformat(timespec="seconds")
                    )
                )
            st.success("📬 Submitted to teacher!")

# ---------- Teacher Mode ----------
else:
    st.title("Teacher Dashboard — View Submissions")
    st.caption("Submissions are listed below. Filter by name or question.")

    student_filter = st.text_input("Filter by student name (optional)")
    q_filter = st.text_input("Filter by question text (optional)")

    query = "SELECT id, student_name, question, substr(code,1,200)||'...' as code_snippet, correct, created_at FROM submissions"
    cond = []
    params = []

    if student_filter.strip():
        cond.append("student_name LIKE ?")
        params.append(f"%{student_filter.strip()}%")
    if q_filter.strip():
        cond.append("question LIKE ?")
        params.append(f"%{q_filter.strip()}%")

    if cond:
        query += " WHERE " + " AND ".join(cond)
    query += " ORDER BY id DESC"

    rows = conn.execute(query, params).fetchall()

    if not rows:
        st.info("No submissions yet.")
    else:
        import pandas as pd
        df = pd.DataFrame(rows, columns=["ID", "Student Name", "Question", "Code (snippet)", "Correct (1/0)", "Submitted At"])
        st.dataframe(df, use_container_width=True)

        sel = st.number_input("Open submission ID", min_value=0, value=0, step=1)
        if sel:
            row = conn.execute("SELECT * FROM submissions WHERE id=?", (int(sel),)).fetchone()
            if row:
                _, student, q, code_full, stdout, stderr, correct, ts = row
                st.write(f"**Student:** {student} | **Submitted At:** {ts} | **Correct:** {'✅' if correct else '❌'}")
                with st.expander("Question"):
                    st.write(q)
                with st.expander("Code"):
                    st.code(code_full, language="python")
                with st.expander("Program Output"):
                    st.code(stdout or "(no output)")
                if stderr:
                    with st.expander("Runtime Error"):
                        st.code(stderr)
