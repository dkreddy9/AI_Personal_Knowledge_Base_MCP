# AI Personal Knowledge Base MCP

This document outlines the setup, usage, and configuration of the AI Personal Knowledge Base MCP, a comprehensive system designed to manage and interact with your long-term memory and knowledge base. It leverages text embeddings for semantic search, similarity comparisons, and efficient storage in a PostgreSQL database with Pgvector.

## 1. Introduction

The AI Personal Knowledge Base MCP is a FastAPI application that leverages Sentence Transformers to convert text into dense numerical vectors (embeddings). These embeddings can then be used for tasks such as semantic search, similarity comparisons, and clustering in vector databases like Pgvector.

## 2. Features

*   **Text Embedding Generation:** Converts input text into a high-dimensional vector representation.
*   **Health Check Endpoint:** Provides a simple endpoint to check the service's status and loaded model.
*   **Pgvector Integration:** Designed to work seamlessly with PostgreSQL databases using the Pgvector extension for efficient vector storage and similarity search.
*   **SQL Query Execution:** Allows direct execution of SQL queries against the memory database.
*   **Memory Similarity Search:** Facilitates searching for similar memory records based on text input.
*   **Memory CRUD Operations:** Supports creating, reading, updating, and deleting memory records.

## 3. Embedding Model

The service currently uses the **`all-mpnet-base-v2`** Sentence Transformer model, which produces **768-dimensional** embeddings.

*   **Note on Dimension:** While the service was initially configured to explore 1536-dimensional embeddings using the `diwank/dfe-base-en-1` model, that model presented an "Input did not specify any keys and allow_empty_key is False" error. This was resolved by passing input as a dictionary `[{"text": data.text}]` to `model.encode()`. However, for broader compatibility and stability, `all-mpnet-base-v2` (768 dimensions) is currently in use.

## 4. Setup

### Prerequisites

*   **Docker:** Ensure Docker is installed and running on your system.
*   **Gemini CLI:** The Gemini Command Line Interface is required to interact with the service.
*   **PostgreSQL with Pgvector:** A PostgreSQL database with the `pgvector` extension installed and enabled.

### Docker Commands

Follow these steps to build and run the embedding service using Docker:

1.  **Build the Docker Image:**
    ```bash
    docker build -t embedding-mcp .
    ```
    This command builds the Docker image and tags it as `embedding-mcp`.

2.  **Run the Docker Container:**
    ```bash
    docker run -d --name embedding-mcp -p 8000:8000 embedding-mcp
    ```
    This command runs the container in detached mode (`-d`), names it `embedding-mcp`, and maps port 8000 of the container to port 8000 on your host machine.

3.  **Stop the Docker Container:**
    ```bash
    docker stop embedding-mcp
    ```

4.  **Remove the Docker Container:**
    ```bash
    docker rm embedding-mcp
    ```

### PostgreSQL Database Setup

Ensure your PostgreSQL database has the `pgvector` extension enabled and a table configured to store embeddings. The `memory` table is used in this context:

1.  **Enable Pgvector Extension:**
    ```sql
    CREATE EXTENSION IF NOT EXISTS vector;
    ```

2.  **`memory` Table Schema:**
    The `memory` table is designed to store long-term memory entries. The `embedding` column is crucial for similarity searches.

    ```sql
    CREATE TYPE memory_scope AS ENUM ('personal', 'project', 'global');
    CREATE TYPE memory_category AS ENUM ('Code', 'Idea', 'Instruction', 'Fix', 'Doc', 'Other');

    CREATE TABLE memory (
        id SERIAL PRIMARY KEY,
        title TEXT NOT NULL,
        content TEXT NOT NULL,
        embedding VECTOR(768) NOT NULL, -- Current dimension is 768
        scope memory_scope NOT NULL DEFAULT 'personal',
        project TEXT,
        category memory_category,
        tags TEXT[],
        source TEXT,
        priority INTEGER DEFAULT 0,
        status memory_status DEFAULT 'active',
        usage_count INTEGER DEFAULT 0,
        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
        last_used_at TIMESTAMP WITH TIME ZONE
    );
    ```

3.  **Create HNSW Index for Similarity Search:**
    For efficient similarity searches, an HNSW (Hierarchical Navigable Small World) index should be created on the `embedding` column. This significantly speeds up queries involving the `<=>` (cosine distance) operator.

    ```sql
    CREATE INDEX ON memory USING hnsw (embedding vector_cosine_ops);
    ```

## 5. API Endpoints

The AI Personal Knowledge Base MCP exposes the following API endpoints:

### 5.1. GET /health

*   **Description:** Checks the health and status of the service, including whether the embedding model is loaded.
*   **Response:**
    ```json
    {
        "status": "ok",
        "model_loaded": true,
        "model_name": "all-mpnet-base-v2"
    }
    ```

### 5.2. POST /embed

*   **Description:** Generates a high-quality text embedding for the provided input text.
*   **Request Body (application/json):**
    ```json
    {
        "text": "The string of text to generate an embedding for."
    }
    ```
*   **Response (application/json):**
    ```json
    {
        "embedding": [0.1, 0.2, ..., 0.N], // N is the dimension of the embedding (e.g., 768)
        "model": "all-mpnet-base-v2"
    }
    ```

### 5.3. POST /db_query

*   **Description:** Executes a raw SQL query against the connected PostgreSQL database.
*   **Request Body (application/json):**
    ```json
    {
        "query": "SELECT * FROM public.memory LIMIT 5;"
    }
    ```
*   **Response (application/json):**
    *   For `SELECT` queries: An array of JSON objects, where each object represents a row.
    *   For `INSERT`, `UPDATE`, `DELETE` queries:
        ```json
        {
            "status": "success",
            "rows_affected": 1
        }
        ```

### 5.4. POST /mem_similarity

*   **Description:** Performs a similarity search within the `memory` table based on a query text. It generates an embedding for the query text and then finds the most similar memory records.
*   **Request Body (application/json):**
    ```json
    {
        "query_text": "Your search query here",
        "top_k": 5
    }
    ```
*   **Response (application/json):** An array of JSON objects, each representing a similar memory record with an added `similarity` score.

### 5.5. POST /mem_crud

*   **Description:** Inserts a new memory record or updates an existing one in the `memory` table. It automatically generates an embedding for the `content` field.
*   **Request Body (application/json):**
    ```json
    {
        "id": null, // Optional: Provide ID for update, omit for insert
        "title": "My New Memory",
        "content": "This is the content of my new memory.",
        "scope": "personal",
        "project": "AI_Personal_Knowledge_Base_MCP",
        "category": "Idea",
        "tags": ["AI", "memory"],
        "source": "Gemini CLI",
        "priority": 1,
        "status": "active",
        "usage_count": 0,
        "created_at": null,
        "updated_at": null,
        "last_used_at": null
    }
    ```
*   **Response (application/json):**
    *   For insert:
        ```json
        {
            "status": "success",
            "id": 123,
            "operation": "insert"
        }
        ```
    *   For update:
        ```json
        {
            "status": "success",
            "id": 123,
            "operation": "update",
            "rows_affected": 1
        }
        ```

## 6. Usage with Gemini CLI

The Gemini CLI interacts with the embedding service via defined tools.

### Generating Embeddings

Use the `generate_embedding_embed_post` tool to generate embeddings for a given text:

```
<tool_code>
print(default_api.generate_embedding_embed_post(text = "Your text here"))
</tool_code>
```

### Performing Similarity Search

To perform a similarity search in your `memory` table:

1.  **Generate Embedding for your Query:**
    ```
    <tool_code>
    print(default_api.generate_embedding_embed_post(text = "Your search query here"))
    </tool_code>
    ```
    Copy the `embedding` array from the output.

2.  **Execute SQL Query:**
    Use the `execute_sql` tool with the generated embedding and the `<=>` operator for cosine distance. Replace `[YOUR_QUERY_EMBEDDING]` with the actual embedding array.

    ```
    <tool_code>
    print(default_api.execute_sql(sql = "SELECT id, title, content, embedding <=> ARRAY[YOUR_QUERY_EMBEDDING]::vector(768) AS similarity FROM postgres.public.memory ORDER BY similarity LIMIT 5;"))
    </tool_code>
    ```
    *Note: Ensure `postgres.public.memory` matches your database, schema, and table names.*

## 7. Troubleshooting

*   **"Error during embedding generation: Input did not specify any keys and allow_empty_key is False"**: This error typically occurs when the `diwank/dfe-base-en-1` model expects a dictionary-like input. The fix involves modifying `app.py` to pass input as `[{"text": data.text}]` to `model.encode()`.
*   **Slow Similarity Searches:** If similarity searches are slow, ensure you have created an HNSW index on your `embedding` column as described in the PostgreSQL Setup section. For very small tables, PostgreSQL might not use the index, but it will become effective as your data grows.
*   **"No valid session ID provided"**: This error indicates an issue with the `FastApiMCP` integration requiring a session ID that is not being provided. This usually requires external configuration or bypassing `FastApiMCP` for direct tool calls.

## 8. Gemini CLI Configuration

To use the embedding service with the Gemini CLI, you need to configure the `mcpServers` in your `settings.json` file. This allows the CLI to route tool calls to the running Docker container.

Add the following configuration to your `settings.json`:`

```json
"mcpServers": {
    "MCP_DOCKER": {
      "command": "docker",
      "args": [
        "mcp",
        "gateway",
        "run"
      ]
    },
    "embedding": {
      "httpUrl": "http://localhost:8000/mcp"
    }
}
```

*   **`MCP_DOCKER`**: This entry defines a command to run the MCP gateway via Docker.
*   **`embedding`**: This entry points to the HTTP URL of the embedding service, making its tools available to the Gemini CLI.

With this configuration, you can call the `generate_embedding_embed_post` tool and other tools from the embedding service directly from the Gemini CLI.

## 9. Future Enhancements

*   **Batch Embedding Generation:** Implement batch processing for embedding generation to improve efficiency when dealing with multiple text inputs. This would require modifying the embedding service API to accept a list of texts.
*   **Optimized Database Inserts:** Explore more optimized methods for bulk inserting data into the PostgreSQL database, such as using the `COPY` command or batching `INSERT` statements.