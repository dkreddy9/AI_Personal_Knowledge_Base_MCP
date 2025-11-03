import os
import uvicorn
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
from fastapi_mcp import FastApiMCP
import psycopg2
from dotenv import load_dotenv
from typing import List, Optional
from datetime import datetime

# --- Configuration ---
load_dotenv()
MODEL_NAME = "all-mpnet-base-v2"
APP_PORT = 8000

# --- Pydantic Models ---
class TextToEmbed(BaseModel):
    text: str = Field(..., description="The string of text to generate an embedding for.")

class EmbeddingResponse(BaseModel):
    embedding: list[float] = Field(..., description="The generated embedding vector.")
    model: str = Field(MODEL_NAME, description="The model used to generate the embedding.")

class QueryRequest(BaseModel):
    query: str = Field(..., description="The SQL query to execute.")

class MemoryRecord(BaseModel):
    id: Optional[int] = None
    title: str
    content: str
    scope: str = "global"
    project: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[List[str]] = None
    source: Optional[str] = None
    priority: int = 0
    status: str = "active"
    usage_count: int = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

class SimilaritySearchRequest(BaseModel):
    query_text: str = Field(..., description="The text to use for similarity search.")
    top_k: int = Field(5, description="The number of top similar results to return.")

# --- Initialization ---
app = FastAPI(
    title="Gemini Embedding Service",
    description="A service for generating high-quality text embeddings and querying the memory database.",
    version="1.1.0"
)

model = None

@app.on_event("startup")
async def load_model():
    global model
    model = SentenceTransformer(MODEL_NAME, device='cpu')
    print(f"Successfully loaded model: {MODEL_NAME}")

# --- Database Connection ---
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv("POSTGRES_HOST"),
        port=os.getenv("POSTGRES_PORT"),
        dbname=os.getenv("POSTGRES_DATABASE"),
        user=os.getenv("POSTGRES_USER"),
        password=os.getenv("POSTGRES_PASSWORD")
    )
    return conn

# --- Application Endpoints ---
@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "model_loaded": model is not None,
        "model_name": MODEL_NAME
    }

@app.post("/embed", response_model=EmbeddingResponse)
async def generate_embedding(data: TextToEmbed):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not yet loaded or failed to load.")
    try:
        embedding = model.encode(data.text, convert_to_numpy=True).tolist()
        return EmbeddingResponse(embedding=embedding, model=MODEL_NAME)
    except Exception as e:
        print(f"Error during embedding generation: {e}")
        raise HTTPException(status_code=500, detail=f"Error during embedding generation: {e}")

@app.post("/db_query")
async def query_memory(request: QueryRequest):
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute(request.query)
        if request.query.strip().upper().startswith("SELECT"):
            colnames = [desc[0] for desc in cur.description]
            results = [dict(zip(colnames, row)) for row in cur.fetchall()]
        else:
            conn.commit()
            results = {"status": "success", "rows_affected": cur.rowcount}
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error during query execution: {e}")
        raise HTTPException(status_code=500, detail=f"Error during query execution: {e}")

@app.post("/mem_similarity")
async def similarity_memory_search(request: SimilaritySearchRequest):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not yet loaded or failed to load.")
    try:
        query_embedding = model.encode(request.query_text, convert_to_numpy=True).tolist()
        conn = get_db_connection()
        cur = conn.cursor()
        # Exclude the embedding column from the select statement
        select_columns = "id, title, content, scope, project, category, tags, source, priority, status, usage_count, created_at, updated_at, last_used_at"
        query = f"SELECT {select_columns}, embedding <=> ARRAY{query_embedding}::vector(768) AS similarity FROM public.memory ORDER BY similarity LIMIT {request.top_k};"
        cur.execute(query)
        colnames = [desc[0] for desc in cur.description]
        results = [dict(zip(colnames, row)) for row in cur.fetchall()]
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error during similarity search: {e}")
        raise HTTPException(status_code=500, detail=f"Error during similarity search: {e}")

@app.post("/mem_crud")
async def insert_update_memory(record: MemoryRecord):
    if model is None:
        raise HTTPException(status_code=503, detail="Model is not yet loaded or failed to load.")
    try:
        # Generate embedding for the content
        embedding = model.encode(record.content, convert_to_numpy=True).tolist()
        conn = get_db_connection()
        cur = conn.cursor()

        if record.id is None:
            # Insert new record
            query = """
                INSERT INTO public.memory (title, content, embedding, scope, project, category, tags, source, priority, status, usage_count, created_at, updated_at, last_used_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id;
            """
            cur.execute(query, (
                record.title, record.content, embedding, record.scope, record.project, record.category,
                record.tags, record.source, record.priority, record.status, record.usage_count,
                record.created_at if record.created_at else datetime.now(),
                record.updated_at if record.updated_at else datetime.now(),
                record.last_used_at
            ))
            record_id = cur.fetchone()[0]
            conn.commit()
            results = {"status": "success", "id": record_id, "operation": "insert"}
        else:
            # Update existing record
            query = """
                UPDATE public.memory
                SET title = %s, content = %s, embedding = %s, scope = %s, project = %s, category = %s, tags = %s, source = %s, priority = %s, status = %s, usage_count = %s, updated_at = %s, last_used_at = %s
                WHERE id = %s;
            """
            cur.execute(query, (
                record.title, record.content, embedding, record.scope, record.project, record.category,
                record.tags, record.source, record.priority, record.status, record.usage_count,
                record.updated_at if record.updated_at else datetime.now(),
                record.last_used_at, record.id
            ))
            conn.commit()
            results = {"status": "success", "id": record.id, "operation": "update", "rows_affected": cur.rowcount}
        cur.close()
        conn.close()
        return results
    except Exception as e:
        print(f"Error during insert/update memory: {e}")
        raise HTTPException(status_code=500, detail=f"Error during insert/update memory: {e}")

# --- FastApiMCP Integration ---
mcp = FastApiMCP(app)
mcp.mount_http()

# --- Server Startup ---
if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=APP_PORT)