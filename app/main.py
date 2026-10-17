import asyncio
import logging
import time

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from app.agent import ask_business_assistant
from app.schemas import ChatRequest, ChatResponse

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="MCP Control Center",
    description="Business Tools MCP Server powered by Ollama and FastAPI.",
    version="2.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


@app.get("/")
async def root():
    return {
        "message": "MCP Control Center API is running.",
        "docs": "/docs",
        "health": "/health",
    }


@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "service": "MCP Control Center",
    }


@app.get("/tools")
async def get_tools():
    """Discover tools exposed by the actual MCP server."""

    from pathlib import Path
    import sys

    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client

    server_path = Path(__file__).resolve().parent.parent / "server.py"

    parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    try:
        async with stdio_client(parameters) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                response = await session.list_tools()

                return {
                    "tools": [
                        {
                            "name": tool.name,
                            "description": tool.description,
                            "input_schema": tool.inputSchema,
                        }
                        for tool in response.tools
                    ],
                    "count": len(response.tools),
                }

    except Exception as exc:
        logger.exception("MCP tool discovery failed")

        raise HTTPException(
            status_code=502,
            detail="Unable to discover tools from the MCP server.",
        ) from exc


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Run the business assistant and return its actual execution trace."""

    started_at = time.perf_counter()
    question = request.question.strip()

    if not question:
        raise HTTPException(
            status_code=422,
            detail="Please enter a question.",
        )

    try:
        result = await asyncio.wait_for(
            ask_business_assistant(question),
            timeout=150,
        )

        elapsed_ms = (time.perf_counter() - started_at) * 1000

        # Verify the agent returned the expected structure.
        if not isinstance(result, dict):
            raise RuntimeError(
                "The business assistant returned an invalid response."
            )

        trace = result.get("trace", [])

        if not isinstance(trace, list):
            raise RuntimeError(
                "The business assistant returned an invalid execution trace."
            )

        response = ChatResponse(
            question=question,
            answer=result.get("answer") or "No answer was returned.",
            tool_used=result.get("tool_used"),
            tool_arguments=result.get("tool_arguments"),
            tool_result=result.get("tool_result"),
            tool_duration_ms=result.get("tool_duration_ms"),
            trace=trace,
            status=result.get("status", "success"),
            total_duration_ms=result.get(
                "total_duration_ms",
                round(elapsed_ms, 2),
            ),
        )

        logger.info(
            "Chat completed: status=%s, tool=%s, trace_events=%d",
            response.status,
            response.tool_used,
            len(response.trace),
        )

        return response

    except asyncio.TimeoutError as exc:
        logger.warning("AI request timed out")

        raise HTTPException(
            status_code=504,
            detail="The AI request timed out. Please try again.",
        ) from exc

    except HTTPException:
        raise

    except Exception as exc:
        logger.exception("Chat request failed")

        raise HTTPException(
            status_code=502,
            detail=(
                "The AI service or MCP tool failed. "
                "Check Ollama and the backend logs."
            ),
        ) from exc