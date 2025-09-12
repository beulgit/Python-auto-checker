import streamlit as st
import subprocess, tempfile, os, uuid, datetime, sqlite3, json, re

# ---------- App Config ----------
st.set_page_config(page_title="Python Auto-Checker IDE", layout="wide")

# ---------- Database Init ----------
@st.cache_resource
def get_conn():
    conn = sqlite3.connect("submissions.db", check_same_thread=False)
    c = conn.cursor()

    # Submissions table
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

    # Questions table
    c.execute("""
        CREATE TABLE IF NOT EXISTS questions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            text TEXT,
            created_at TEXT
        )
    """)

    # Testcases table
    c.execute("""
        CREATE TABLE IF NOT EXISTS testcases (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            question_id INTEGER,
            input TEXT,
            output TEXT,
            FOREIGN KEY(question_id) REFERENCES questions(id)
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
question_file = st.sidebar.file_uploader("Upload TXT/JSON file (Question + testcases)", type=["txt", "json"])

def parse_txt_format(content):
    """
    Parse teacher uploaded TXT format with INPUT/OUTPUT markers.
    """
    # First line should be question
    lines = content.strip().splitlines()
    if not lines[0].startswith("Question:"):
        return None, []
    question_text = lines[0].replace("Question:", "").strip()

    testcases = []
    blocks = re.split(r"---+", content)[1:]  # split after question
    for block in blocks:
        inp, out = [], []
        mode = None
        for line in block.strip().splitlines():
            if line.strip() == "INPUT":
                mode = "input"
                continue
            elif line.strip() == "OUTPUT":
                mode = "output"
                continue
            elif not line.strip():
                continue

            if mode == "input":
                inp.append(line.strip())
            elif mode == "output":
                out.append(line.strip())
        if inp and out:
            testcases.append(("\n".join(inp), "\n".join(out)))
    return question_text, testcases

if question_file:
    filename = question_file.name
    content = question_file.read().decode("utf-8")

    if filename.endswith(".txt"):
        question_text, testcases = parse_txt_format(content)
    elif filename.endswith(".json"):
        data = json.loads(content)
        question_text = data["question"]
        testcases = [("\n".join(tc["input"]), "\n".join(tc["output"])) for tc in data["testcases"]]
    else:
        question_text, testcases = None, []

    if question_text and testcases:
        # Save to DB
        with conn:
            cur = conn.cursor()
            cur.execute("INSERT INTO questions (text, created_at) VALUES (?, ?)",
                        (question_text, datetime.datetime.now().isoformat(timespec="seconds")))
            qid = cur.lastrowid
            for inp, out in testcases:
                cur.execute("INSERT INTO testcases (question_id, input, output) VALUES (?, ?, ?)",
                            (qid, inp, out))
        st.sidebar.success("✅ Question uploaded and saved successfully!")
    else:
        st.sidebar.error("Invalid format. Please follow the provided template.")

# ---------- Student Mode ----------
if mode == "Student":
    st.title("Python Learning IDE — Student Mode")

    row = conn.execute("SELECT id, text FROM questions ORDER BY id DESC LIMIT 1").fetchone()
    if row:
        qid, question_text = row
        st.subheader("Question")
        st.write(question_text)

        # Fetch testcases for latest question
        testcases = conn.execute("SELECT input, output FROM testcases WHERE question_id=?",
                                 (qid,)).fetchall()
    else:
        question_text = ""
        testcases = []
        st.warning("⚠️ No question uploaded yet by the teacher.")

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
                    input=expected_input + "\n",  # pass all inputs
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    timeout=5
                )

                actual = proc.stdout.replace("\r\n", "\n").rstrip()
                expected = expected_output.replace("\r\n", "\n").rstrip()

                st.write(f"---")
                st.subheader(f"Test Case {idx}")
                st.write("**Input:**")
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
