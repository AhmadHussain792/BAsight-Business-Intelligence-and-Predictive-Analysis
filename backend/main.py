from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from io import StringIO
from typing import Optional
import pandas as pd
from pydantic import BaseModel
from dotenv import load_dotenv
import os
from langchain_mistralai import ChatMistralAI
from langchain_experimental.agents import create_pandas_dataframe_agent
import sqlite3

load_dotenv()

app = FastAPI(title="CSV Statistics")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)

class ChatRequest(BaseModel):
    question: str

dataset_id = {"id": []}
current_df = []

def csv_statistics(uploaded_file: bytes):
    cur_df = pd.read_csv(StringIO(uploaded_file.decode("utf-8")))
    cur_df = cur_df.dropna(how="all")
    try:
        id = dataset_id["id"][-1]
        dataset_id["id"].append(id + 1)
        store_data(id, df)
    except:
        dataset_id["id"].append(1)
        #store_data(1, df)

    return {
        "total_rows": int(cur_df.shape[0]),
        "total_columns": int(cur_df.shape[1]),
        "columns": cur_df.columns.tolist()
    }

def build_agent(current_df):
    MISTRAL_API_KEY = os.getenv("MISTRAL_API_KEY")
    if not MISTRAL_API_KEY:
        raise ValueError("MISTRAL_API_KEY is not set. Please set it before calling /chat.")

    llm = ChatMistralAI(
        model="mistral-small",
        api_key=MISTRAL_API_KEY
    )

    return create_pandas_dataframe_agent(
        llm,
        current_df,
        verbose=True,
        allow_dangerous_code=True,
    )

def store_data(id, df):
    # store df in database
    connection = sqlite3.connect("server_database.db")
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS data (
        id INTEGER PRIMARY KEY
        DataFrame pd.DataFrame
        )    
""")

    cursor.execute("""
        INSERT INTO data (id, DataFrame) VALUES (?, ?)
""", (id, df)) 

@app.post("/file-upload")
async def upload_file(uploaded_file: UploadFile = File(...)):

    if not uploaded_file.filename:
        raise HTTPException(status_code=400, detail="No file uploaded")

    if not uploaded_file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="Please upload a CSV file")

    try:
        contents = await uploaded_file.read()
        current_df = pd.read_csv(StringIO(contents.decode("utf-8")))
        current_df = current_df.dropna(how="all")
        summary = csv_statistics(contents)
        return summary
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not read CSV: {e}")

@app.post("/chat")
async def chat(request: ChatRequest):
    if current_df is None:
        raise HTTPException(status_code=400, detail="Please upload a CSV first")

    try:
        agent = build_agent(current_df)
        answer = agent.run(request.question)
        return {"answer": answer}
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Chat Error: {e}")
