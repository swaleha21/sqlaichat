import os
import streamlit as st
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine
from langchain_groq import ChatGroq
from langchain_community.utilities import SQLDatabase
from langchain_core.prompts import ChatPromptTemplate

# --------------------------------------------------
# Load environment variables
# --------------------------------------------------
load_dotenv()

# --------------------------------------------------
# Page config
# --------------------------------------------------
st.set_page_config(
    page_title="💬 DB Chat Assistant",
    layout="centered",
    initial_sidebar_state="expanded"
)

st.title("💼 DB Chat Assistant")

# --------------------------------------------------
# Session state
# --------------------------------------------------
if "chat" not in st.session_state:
    st.session_state.chat = []

if "uploaded_tables" not in st.session_state:
    st.session_state.uploaded_tables = []

if "last_modified_table" not in st.session_state:
    st.session_state.last_modified_table = None

# --------------------------------------------------
# LLM (Groq)
# --------------------------------------------------
llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0
)

# --------------------------------------------------
# Database helpers
# --------------------------------------------------
def connect_database(user, password, host, port, database):
    uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    engine = create_engine(uri)
    st.session_state.engine = engine
    st.session_state.db = SQLDatabase.from_uri(uri)
    st.session_state.connected = True
    st.success(f"✅ Connected to {database}")

def run_query(query: str):
    return st.session_state.db.run(query)

def get_schema():
    try:
        return st.session_state.db.get_table_info()
    except Exception:
        return ""

# --------------------------------------------------
# Upload CSV / Excel → SQL
# --------------------------------------------------
def upload_file_to_db(file, table_name):
    if not table_name.strip():
        st.error("❌ Table name required")
        return

    if file.name.endswith(".csv"):
        df = pd.read_csv(file)
    else:
        df = pd.read_excel(file)

    df.to_sql(
        table_name,
        con=st.session_state.engine,
        if_exists="replace",
        index=False
    )

    if table_name not in st.session_state.uploaded_tables:
        st.session_state.uploaded_tables.append(table_name)

    st.success(f"✅ Uploaded as table `{table_name}`")
    st.dataframe(df.head())

# --------------------------------------------------
# SQL safety
# --------------------------------------------------
def is_safe_sql(query: str):
    blocked = ["drop ", "truncate ", "alter "]
    return not any(word in query.lower() for word in blocked)

def is_delete_sql(query: str):
    return query.lower().startswith("delete")

def is_insert_sql(query: str):
    return query.lower().startswith("insert")

def is_update_sql(query: str):
    return query.lower().startswith("update")

# --------------------------------------------------
# Safe execution + TRACK CHANGES
# --------------------------------------------------
def safe_run_query(query: str):
    try:
        run_query(query)

        words = query.lower().split()
        table = None

        if words[0] == "insert":
            table = words[2]
        elif words[0] == "update":
            table = words[1]
        elif words[0] == "delete":
            table = words[2]

        st.session_state.last_modified_table = table

        return f"✅ Changes saved in `{table}`"

    except Exception as e:
        return f"❌ SQL Error: {e}"

# --------------------------------------------------
# LLM → SQL
# --------------------------------------------------
SQL_PROMPT = """
You are a SQL expert.

Schema:
{schema}

Rules:
- SELECT, INSERT, UPDATE allowed
- DELETE only if explicitly requested
- NEVER use DROP, TRUNCATE, ALTER
- Use only given tables & columns

User question:
{question}

Return ONLY SQL.
"""

def generate_sql(question):
    prompt = ChatPromptTemplate.from_template(SQL_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "schema": get_schema(),
        "question": question
    })
    return response.content.replace("```sql", "").replace("```", "").strip()

# --------------------------------------------------
# Sidebar
# --------------------------------------------------
with st.sidebar:
    st.header("🔌 Connect Database")
    host = st.text_input("Host", "localhost")
    port = st.text_input("Port", "3306")
    username = st.text_input("Username", "root")
    password = st.text_input("Password", type="password")
    database = st.text_input("Database", "rag_test")

    if st.button("Connect DB"):
        connect_database(username, password, host, port, database)

    st.markdown("---")

    if "connected" in st.session_state:
        st.header("📤 Upload CSV / Excel")
        uploaded_file = st.file_uploader("Upload file", type=["csv", "xlsx"])
        table_name = st.text_input("Table name")

        if uploaded_file and st.button("Upload"):
            upload_file_to_db(uploaded_file, table_name)

    # -------- Download uploaded tables --------
    if st.session_state.uploaded_tables:
        st.markdown("---")
        st.header("⬇️ Download Uploaded Table")

        table = st.selectbox("Select table", st.session_state.uploaded_tables)
        df = pd.read_sql(f"SELECT * FROM `{table}`", st.session_state.engine)

        st.download_button(
            "Download CSV",
            df.to_csv(index=False),
            file_name=f"{table}.csv",
            mime="text/csv"
        )

    # -------- Download modified table --------
    if st.session_state.last_modified_table:
        st.markdown("---")
        st.header("⬇️ Download Last Modified Table")

        table = st.session_state.last_modified_table
        df = pd.read_sql(f"SELECT * FROM `{table}`", st.session_state.engine)

        st.download_button(
            f"Download `{table}`",
            df.to_csv(index=False),
            file_name=f"{table}_updated.csv",
            mime="text/csv"
        )

    st.markdown("---")
    st.markdown("💬 DB Chat Assistant | Developed by Swaleha Sutar | 2026")

# --------------------------------------------------
# Chat input
# --------------------------------------------------
question = st.chat_input("Ask your database...")

if question:
    if "db" not in st.session_state:
        st.error("❌ Connect DB first")
    else:
        st.session_state.chat.append({"role": "user", "content": question})
        sql = generate_sql(question)

        if not is_safe_sql(sql):
            answer = "❌ Unsafe SQL blocked"
        elif is_insert_sql(sql) or is_update_sql(sql) or is_delete_sql(sql):
            answer = safe_run_query(sql)
        else:
            try:
                # Run the SQL query and get a DataFrame
                df = pd.read_sql(sql, st.session_state.engine)
                
                if df.empty:
                    answer = "ℹ️ Query executed successfully but returned 0 rows."
                else:
                    # ✅ Correct: no parentheses after df
                    md_table = df.to_markdown(index=False)
                    answer = f"### 📋 Query Result\n\n```markdown\n{md_table}\n```"
            except Exception as e:
                answer = f"❌ SQL Error: {e}"

        st.session_state.chat.append({"role": "assistant", "content": answer})
# --------------------------------------------------
# Render chat
# --------------------------------------------------
for msg in st.session_state.chat:
    st.chat_message(msg["role"]).markdown(msg["content"])
