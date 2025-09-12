import streamlit as st
import subprocess, tempfile, os, sqlite3, uuid, datetime

# ---------- App Config ----------
st.set_page_config("AutoChecker", "✅")

DB_FILE = "autochecker.db"
TEACHER_PASSWORD = "teacher123"   # 🔑 You can change this

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
            input=test_input.encode(),
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
st.title("✅ AutoChecker")

mode = st.sidebar.radio("Choose Mode", ["Teacher", "Student"])

# ---------- Teacher Mode ----------
if mode == "Teacher":
    password = st.text_input("Enter Teacher Password", type="password")
    if password == TEACHER_PASSWORD:
        st.success("Access Granted ✅")

        qid = st.text_input("Question ID (unique)", value="Q1")
        question = st.text_area("Enter Question Description")
        testcases = st.text_area(
            "Enter Test Cases (Format: INPUT ... OUTPUT ... )",
            height=200,
            placeholder="---\nINPUT\n1\n2\nOUTPUT\n3\n---\nINPUT\n..."
        )

        if st.button("Save Question & Test Cases"):
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
        code_file = st.file_uploader("Upload your Python file", type=["py"])

        if code_file and student_name:
            user_code = code_file.read().decode()

            # Parse test cases
            raw_cases = testcases.strip().split("---")
            results = []
            all_passed = True

            for case in raw_cases:
                if not case.strip():
                    continue
                parts = case.strip().split("OUTPUT")
                input_part = parts[0].replace("INPUT", "").strip()
                expected_output = parts[1].strip() if len(parts) > 1 else ""
                
                actual_output = run_code(user_code, input_part).strip()
                passed = (actual_output == expected_output)

                results.append({
                    "input": input_part,
                    "expected": expected_output,
                    "actual": actual_output,
                    "status": "✅ Passed" if passed else "❌ Failed"
                })
                if not passed:
                    all_passed = False

            # Save submission
            save_submission(qid, student_name, user_code,
                            "All Passed" if all_passed else "Some Failed")

            # Show results
            st.subheader("📝 Results")
            for r in results:
                st.write(f"**Input:**\n{r['input']}")
                st.write(f"**Expected:**\n{r['expected']}")
                st.write(f"**Got:**\n{r['actual']}")
                st.writ
