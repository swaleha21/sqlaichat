import os
import streamlit as st
from dotenv import load_dotenv
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
# LLM (Groq)
# --------------------------------------------------
llm = ChatGroq(
    groq_api_key=os.getenv("GROQ_API_KEY"),
    model_name="llama-3.1-8b-instant",
    temperature=0
)

# --------------------------------------------------
# Database helpers (MySQL ONLY)
# --------------------------------------------------
def connect_database(db_type, user, password, host, port, database):
    uri = f"mysql+mysqlconnector://{user}:{password}@{host}:{port}/{database}"
    st.session_state.db = SQLDatabase.from_uri(uri)
    st.session_state.connected = True
    st.success(f"✅ Connected to {database} (MySQL)")

def run_query(query: str):
    return st.session_state.db.run(query)

def get_schema():
    if "db" not in st.session_state:
        return {}
    try:
        tables = st.session_state.db.get_table_info()
        return tables
    except Exception as e:
        st.error(f"Error fetching tables: {e}")
        return {}

# --------------------------------------------------
# SQL safety
# --------------------------------------------------
def is_safe_sql(query: str) -> bool:
    blocked = ["drop ", "truncate ", "alter "]
    return not any(word in query.lower() for word in blocked)

def is_delete_sql(query: str):
    return query.strip().lower().startswith("delete")

def is_insert_sql(query: str):
    return query.strip().lower().startswith("insert")

def is_update_sql(query: str):
    return query.strip().lower().startswith("update")

# --------------------------------------------------
# Safe execution for all write operations
# --------------------------------------------------
def safe_run_query(query: str):
    try:
        result = run_query(query)
        return "✅ SQL executed successfully.", result
    except Exception as e:
        error_str = str(e)
        if "1451" in error_str:
            return "❌ Cannot perform operation: Related child rows exist (foreign key constraint).", None
        elif "1452" in error_str:
            return "❌ Cannot perform operation: Foreign key constraint violated.", None
        else:
            return f"❌ SQL Error: {e}", None

# --------------------------------------------------
# LLM → SQL
# --------------------------------------------------
SQL_PROMPT = """
You are a SQL expert.

Below is the EXACT database schema.
You MUST use ONLY the table and column names provided.
DO NOT guess table names or columns.

Schema:
{schema}

Rules:
- SELECT, INSERT are allowed
- DELETE is allowed ONLY if user explicitly asks
- UPDATE is allowed
- NEVER use DROP, TRUNCATE, ALTER

User question:
{question}

Return ONLY the SQL query.
"""

def generate_sql(question: str):
    prompt = ChatPromptTemplate.from_template(SQL_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "schema": get_schema(),
        "question": question
    })
    sql = response.content.strip()
    sql = sql.replace("```sql", "").replace("```", "").strip()
    return sql

# --------------------------------------------------
# SQL result → Natural language
# --------------------------------------------------
RESPONSE_PROMPT = """
You are a data analyst.

User question:
{question}

SQL query:
{query}

SQL result:
{result}

Write a short, clear response.
"""

def generate_response(question, query, result):
    prompt = ChatPromptTemplate.from_template(RESPONSE_PROMPT)
    chain = prompt | llm
    response = chain.invoke({
        "question": question,
        "query": query,
        "result": result
    })
    return response.content.strip()

# --------------------------------------------------
# Chat state
# --------------------------------------------------
if "chat" not in st.session_state:
    st.session_state.chat = []

if "pending_delete" not in st.session_state:
    st.session_state.pending_delete = None

# --------------------------------------------------
# Sidebar – DB connection + footer
# --------------------------------------------------
with st.sidebar:
    st.header("🔌 Connect to Database")
    db_type = "MySQL"  # Fixed to MySQL only
    host = st.text_input("Host", value="localhost")
    port = st.text_input("Port", value="3306")
    username = st.text_input("Username", value="root")
    password = st.text_input("Password", type="password")
    database = st.text_input("Database Name", value="rag_test")

    if st.button("Connect DB"):
        connect_database(db_type, username, password, host, port, database)

    st.markdown("---")
    st.markdown("💬 DB Chat Assistant | Developed by Swaleha Sutar | 2026")

# --------------------------------------------------

# --------------------------------------------------
# User input
# --------------------------------------------------
question = st.chat_input("Ask a question:")

if question:
    if "db" not in st.session_state:
        st.error("❌ Please connect to the database first.")
    else:
        st.session_state.chat.append({"role": "user", "content": question})

        if question == "CONFIRM DELETE" and st.session_state.pending_delete:
            message, _ = safe_run_query(st.session_state.pending_delete)
            answer = message
            st.session_state.pending_delete = None
        else:
            sql_query = generate_sql(question)

            if not is_safe_sql(sql_query):
                answer = "❌ Unsafe SQL detected. Query blocked."
            elif is_delete_sql(sql_query):
                st.session_state.pending_delete = sql_query
                answer = "⚠️ Type **CONFIRM DELETE** to proceed."
            elif is_insert_sql(sql_query) or is_update_sql(sql_query):
                message, _ = safe_run_query(sql_query)
                answer = message
            else:
                try:
                    result = run_query(sql_query)
                    answer = generate_response(question, sql_query, result)
                except Exception as e:
                    answer = f"❌ SQL Error:\n{e}"

        st.session_state.chat.append({"role": "assistant", "content": answer})

# --------------------------------------------------
# Render chat messages
# --------------------------------------------------
for msg in st.session_state.chat:
    st.chat_message(msg["role"]).markdown(msg["content"])