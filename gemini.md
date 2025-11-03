# Gemini Instructions

## How to start the Docker container

To start the Docker container for this project, run the following commands:

1.  **Build the Docker image:**
    ```bash
    docker build -t ai_personal_knowledge_base_mcp .
    ```

2.  **Run the Docker container:**
    ```bash
    docker run -d --name AI_Personal_Knowledge_Base_MCP -p 8000:8000 ai_personal_knowledge_base_mcp
    ```

## Configuration

The `.gemini/settings.json` file contains the following configuration for the service:

```json
"AI_Personal_Knowledge_Base_MCP": {
  "httpUrl": "http://localhost:8000/mcp"
}
```
This is used by the Gemini CLI to connect to the running service.
