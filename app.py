import streamlit as st
import subprocess, tempfile, os, sqlite3, uuid, datetime

# ---------- App Config ----------
st.set_page_config("Python AutoChecker", "wide")

DB_FILE = "autochecker.db"
TEACHER_PASSWORD = "teacher123"  # Can be changed or removed

# ---------- Database Setup ----------
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS questions (
                    qid TEXT PRIMARY KEY,
                    question TEXT,
                    testcases TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS submissions (
                    sid TEXT PRIMARY KEY,
                    qid TEXT,
                    student_name TEXT,
                    code TEXT,
                    result TEXT,
                    timestamp TEXT
                )''')
    conn.commit()
    conn.close()
init_db()

# ---------- Helper Functions ----------
def run_code(user_code, test_input):
    """Run Python code with given input and return output or error."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as tmp:
        tmp.write(user_code)
        tmp_filename = tmp.name

    try:
        result = subprocess.run(
            ["python", tmp_filename],
            input=test_input,
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.stdout.strip() if result.returncode == 0 else result.stderr.strip()
    except subprocess.TimeoutExpired:
        return "⏰ Timeout: Code took too long"
    finally:
        os.remove(tmp_filename)

def save_question(qid, question, testcases):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("REPLACE INTO questions (qid, question, testcases) VALUES (?, ?, ?)",
              (qid, question, testcases))
    conn.commit()
    conn.close()

def get_question(qid):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT question, testcases FROM questions WHERE qid=?", (qid,))
    row = c.fetchone()
    conn.close()
    return row if row else (None, None)

def save_submission(qid, student_name, code, result):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    sid = str(uuid.uuid4())
    timestamp = str(datetime.datetime.now())
    c.execute("INSERT INTO submissions VALUES (?, ?, ?, ?, ?, ?)",
              (sid, qid, student_name, code, result, timestamp))
    conn.commit()
    conn.close()

# ---------- UI ----------
st.title("✅ Python AutoChecker")

mode = st.sidebar.radio("Choose Mode", ["Teacher", "Student"])

# ---------- Teacher Mode ----------
if mode == "Teacher":
    password = st.text_input("Enter Teacher Password", type="password")
    if password == TEACHER_PASSWORD:
        st.success("Access Granted ✅")
        qid = st.text_input("Question ID (unique)", value="Q1")
        question = st.text_area("Enter Question Description")
        testcases = st.text_area(
            "Enter Test Cases (Format: --- INPUT ... OUTPUT ... ---)",
            height=200,
            placeholder="---\nINPUT\n20000\n1\n3\nOUTPUT\nBalance: 20000\n---\nINPUT\n..."
        )

        if st.button("Save Question & Test Cases"):
            if not qid.strip() or not question.strip() or not testcases.strip():
                st.warning("Fill all fields before saving.")
            else:
                save_question(qid, question, testcases)
                st.success("Question & test cases saved ✅")

    else:
        st.warning("Enter correct teacher password")

# ---------- Student Mode ----------
elif mode == "Student":
    qid = st.text_input("Enter Question ID to Attempt", value="Q1")
    question, testcases = get_question(qid)

    if not question:
        st.error("No such question found. Ask teacher to set it first.")
    else:
        st.subheader("📌 Question")
        st.write(question)

        student_name = st.text_input("Your Name")
        code_area = st.text_area("Enter / Paste your Python Code here", height=250)

        run_clicked = st.button("Run Code")
        submit_clicked = st.button("Submit Code")

        # ---------- Run Code ----------
        if run_clicked and student_name and code_area:
            raw_cases = testcases.strip().split("---")
            results = []
            all_passed = True

            for case in raw_cases:
                if not case.strip():
                    continue
                parts = case.strip().split("OUTPUT")
                input_part = parts[0].replace("INPUT", "").strip()
                expected_output = parts[1].strip() if len(parts) > 1 else ""

                actual_output = run_code(code_area, input_part).strip()
                passed = (actual_output == expected_output)

                results.append({
                    "input": input_part,
                    "expected": expected_output,
                    "actual": actual_output,
                    "status": "✅ Passed" if passed else "❌ Failed"
                })
                if not passed:
                    all_passed = False

            # Show results
            st.subheader("📝 Test Results")
            for r in results:
                st.write(f"**Input:**\n{r['input']}")
                st.write(f"**Expected Output:**\n{r['expected']}")
                st.write(f"**Actual Output:**\n{r['actual']}")
                st.write(f"**Status:** {r['status']}")
                st.markdown("---")

            if all_passed:
                st.success("🎉 All test cases passed!")
            else:
                st.error("⚠️ Some test cases failed")

            # Save in session for submission
            st.session_state["last_results"] = results
            st.session_state["last_code"] = code_area

        # ---------- Submit ----------
        if submit_clicked:
            if not student_name.strip():
                st.warning("Enter your name before submitting.")
            elif "last_results" not in st.session_state:
                st.warning("Please run your code first before submitting.")
            else:
                save_submission(
                    qid,
                    student_name,
                    st.session_state["last_code"],
                    "All Passed" if all(r['status']=="✅ Passed" for r in st.session_state["last_results"]) else "Some Failed"
                )
                st.success("📬 Submission saved!")
