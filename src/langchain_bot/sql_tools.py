from pathlib import Path
from langchain_community.utilities import SQLDatabase
from langchain_community.agent_toolkits.sql.toolkit import SQLDatabaseToolkit
from langchain_openai import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

root = Path(__file__).resolve().parents[2]
def get_database():
    return SQLDatabase.from_uri(f"sqlite:///{root / 'ecommerce.db'}")

def get_sql_tools():
    db = get_database()
    llm = ChatOpenAI(temperature=0)
    toolkit = SQLDatabaseToolkit(db=db, llm=llm)
    return toolkit.get_tools()
