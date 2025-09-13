import streamlit as st
import subprocess, tempfile, os, sqlite3, datetime, uuid

# ---------- App Config ----------
st.set_page_config(page_title="AutoChecker", page_icon="✅", layout="centered")

# ---------- Database Setup ----------
DB_FILE = "submissions.db"
conn = sqlite3.connect(DB_FILE)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS submissions 
             (id TEXT, timestamp TEXT, code TEXT, results TEXT)''')
conn.commit()

# ---------- App Title ----------
st.title("✅ AutoChecker App")

# ---------- Instructions ----------
st.markdown("""
### ℹ️ Instructions
1. Paste your Python code in the editor below.  
2. Choose test cases (given below or add your own).  
3. Click **Run Test Cases** to execute.  
4. Click **Quit App** when you’re done.  
""")

# ---------- Code Input ----------
student_code = st.text_area("✍️ Enter your Python code here:", height=200)

# ---------- Test Cases ----------
st.subheader("📌 Test Cases")

default_test_cases = [
    {"input": "5\n", "expected_output": "25\n"},
    {"input": "10\n", "expected_output": "100\n"},
    {"input": "0\n", "expected_output": "0\n"}
]

# Let students add extra cases
custom_case = st.text_area("➕ Add custom test case (format: input | expected_output)", "")
if custom_case:
    try:
        inp, exp = custom_case.split("|")
        default_test_cases.append({"input": inp.strip()+"\n", "expected_output": exp.strip()+"\n"})
    except:
        st.warning("⚠️ Use correct format: input | expected_output")

# ---------- Run Test Cases ----------
if st.button("▶️ Run Test Cases"):
    if not student_code.strip():
        st.error("⚠️ Please enter some code first!")
    else:
        results = []
        for i, case in enumerate(default_test_cases, 1):
            with tempfile.NamedTemporaryFile(delete=False, suffix=".py", mode="w") as tmp:
                tmp.write(student_code)
                tmp_path = tmp.name

            try:
                completed = subprocess.run(
                    ["python", tmp_path],
                    input=case["input"],
                    text=True,
                    capture_output=True,
                    timeout=5
                )
                output = completed.stdout.strip()
                expected = case["expected_output"].strip()
                status = "✅ Pass" if output == expected else f"❌ Fail (Got: {output})"
            except Exception as e:
                status = f"⚠️ Error: {e}"

            results.append(f"Test Case {i}: {status}")

            os.remove(tmp_path)

        # Show Results
        st.subheader("📊 Results")
        for r in results:
            st.write(r)

        # Save to DB
        submission_id = str(uuid.uuid4())
        timestamp = str(datetime.datetime.now())
        c.execute("INSERT INTO submissions VALUES (?, ?, ?, ?)",
                  (submission_id, timestamp, student_code, str(results)))
        conn.commit()
        st.success("✅ Submission saved!")

# ---------- Quit Button ----------
if st.button("❌ Quit App"):
    st.info("👋 Thank you! You may now close the tab.")
    st.stop()
