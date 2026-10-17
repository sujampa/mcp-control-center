import json
import math
import re
import sys
import time

from pathlib import Path
from typing import Any

import httpx

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


# ============================================================
# CONFIGURATION
# ============================================================

OLLAMA_URL = "http://localhost:11434/api/chat"
OLLAMA_MODEL = "llama3.2"

SERVER_PATH = Path(__file__).resolve().parent.parent / "server.py"

ALLOWED_TOOLS = {"calculate_total", "check_stock"}

MAX_QUANTITY = 1_000_000
MAX_UNIT_PRICE = 1_000_000_000


# ============================================================
# TOOL DEFINITIONS
# ============================================================

TOOL_DEFINITIONS = [
    {
        "type": "function",
        "function": {
            "name": "calculate_total",
            "description": (
                "Calculate product cost when quantity and unit_price "
                "are known. Never invent missing values."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "quantity": {"type": "integer"},
                    "unit_price": {"type": "number"},
                },
                "required": ["quantity", "unit_price"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_stock",
            "description": (
                "Check stock sufficiency using the product name, "
                "available stock and requested quantity."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "product_name": {"type": "string"},
                    "available_stock": {"type": "integer"},
                    "requested_quantity": {"type": "integer"},
                },
                "required": [
                    "product_name",
                    "available_stock",
                    "requested_quantity",
                ],
            },
        },
    },
]


# ============================================================
# TRACE HELPERS
# ============================================================

def add_event(
    trace: list[dict[str, Any]],
    stage: str,
    status: str,
    message: str,
    duration_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an event that actually occurred."""

    event: dict[str, Any] = {
        "stage": stage,
        "status": status,
        "message": message,
    }

    if duration_ms is not None:
        event["duration_ms"] = round(duration_ms, 2)

    if details is not None:
        event["details"] = details

    trace.append(event)


def finish_event(
    trace: list[dict[str, Any]],
    stage: str,
    status: str,
    message: str,
    duration_ms: float | None = None,
    details: dict[str, Any] | None = None,
) -> bool:
    """Update an existing running event with its final status and details."""

    for event in reversed(trace):
        if event.get("stage") == stage and event.get("status") == "running":
            event["status"] = status
            event["message"] = message

            if duration_ms is not None:
                event["duration_ms"] = round(duration_ms, 2)

            if details is not None:
                event["details"] = details

            return True

    return False


def make_result(
    answer: str,
    trace: list[dict[str, Any]],
    started_at: float,
    tool_used: str | None = None,
    tool_arguments: dict[str, Any] | None = None,
    tool_result: str | None = None,
    tool_duration_ms: float | None = None,
    status: str = "success",
) -> dict[str, Any]:
    """Build the complete result returned to FastAPI."""

    return {
        "answer": answer,
        "tool_used": tool_used,
        "tool_arguments": tool_arguments,
        "tool_result": tool_result,
        "tool_duration_ms": tool_duration_ms,
        "trace": trace,
        "status": status,
        "total_duration_ms": round(
            (time.perf_counter() - started_at) * 1000,
            2,
        ),
    }


# ============================================================
# OLLAMA
# ============================================================

async def ask_ollama(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": False,
        "options": {"temperature": 0},
    }

    if tools:
        payload["tools"] = tools

    async with httpx.AsyncClient(timeout=120.0) as client:
        response = await client.post(OLLAMA_URL, json=payload)
        response.raise_for_status()
        data = response.json()

    message = data.get("message")

    if not isinstance(message, dict):
        raise RuntimeError("Ollama returned an invalid response.")

    return message


# ============================================================
# ARGUMENT PARSING AND VALIDATION
# ============================================================

def parse_json_arguments(raw_arguments: Any) -> dict[str, Any]:
    if isinstance(raw_arguments, dict):
        return raw_arguments

    if isinstance(raw_arguments, str):
        try:
            parsed = json.loads(raw_arguments)
        except json.JSONDecodeError as exc:
            raise ValueError("Tool arguments are not valid JSON.") from exc

        if isinstance(parsed, dict):
            return parsed

    raise ValueError("Tool arguments must be a JSON object.")


def parse_integer(value: Any, field_name: str) -> int:
    if value is None:
        raise ValueError(f"Please provide {field_name}.")

    if isinstance(value, bool):
        raise ValueError(f"{field_name.capitalize()} must be a whole number.")

    if isinstance(value, int):
        return value

    if isinstance(value, str):
        cleaned = value.strip()

        if cleaned and cleaned.isdigit():
            return int(cleaned)

    raise ValueError(f"{field_name.capitalize()} must be a whole number.")


def parse_number(value: Any, field_name: str) -> float:
    if value is None:
        raise ValueError(f"Please provide {field_name}.")

    if isinstance(value, bool):
        raise ValueError(f"{field_name.capitalize()} must be a number.")

    if not isinstance(value, (int, float, str)):
        raise ValueError(f"{field_name.capitalize()} must be a number.")

    if isinstance(value, str) and not value.strip():
        raise ValueError(f"Please provide {field_name}.")

    try:
        number = float(value)
    except (ValueError, TypeError, OverflowError) as exc:
        raise ValueError(f"{field_name.capitalize()} must be a number.") from exc

    if not math.isfinite(number):
        raise ValueError(f"{field_name.capitalize()} must be finite.")

    return number


def validate_arguments(
    tool_name: str,
    arguments: dict[str, Any],
) -> dict[str, Any]:
    if tool_name not in ALLOWED_TOOLS:
        raise ValueError("This tool is not allowed.")

    if not isinstance(arguments, dict):
        raise ValueError("Tool arguments must be an object.")

    if tool_name == "calculate_total":
        quantity = parse_integer(arguments.get("quantity"), "quantity")
        unit_price = parse_number(arguments.get("unit_price"), "unit price")

        if quantity <= 0:
            raise ValueError("Quantity must be greater than zero.")

        if quantity > MAX_QUANTITY:
            raise ValueError(f"Quantity cannot exceed {MAX_QUANTITY:,}.")

        if unit_price < 0:
            raise ValueError("Unit price cannot be negative.")

        if unit_price > MAX_UNIT_PRICE:
            raise ValueError(
                f"Unit price cannot exceed ₹{MAX_UNIT_PRICE:,.2f}."
            )

        return {
            "quantity": quantity,
            "unit_price": unit_price,
        }

    if tool_name == "check_stock":
        product_name = arguments.get("product_name")

        if not isinstance(product_name, str) or not product_name.strip():
            raise ValueError("Please provide a valid product name.")

        product_name = product_name.strip()

        if len(product_name) > 100:
            raise ValueError("Product name cannot exceed 100 characters.")

        available = parse_integer(
            arguments.get("available_stock"),
            "available stock",
        )

        requested = parse_integer(
            arguments.get("requested_quantity"),
            "requested quantity",
        )

        if available < 0:
            raise ValueError("Available stock cannot be negative.")

        if available > MAX_QUANTITY:
            raise ValueError(f"Available stock cannot exceed {MAX_QUANTITY:,}.")

        if requested <= 0:
            raise ValueError("Requested quantity must be greater than zero.")

        if requested > MAX_QUANTITY:
            raise ValueError(
                f"Requested quantity cannot exceed {MAX_QUANTITY:,}."
            )

        return {
            "product_name": product_name,
            "available_stock": available,
            "requested_quantity": requested,
        }

    raise ValueError("Unsupported tool.")


# ============================================================
# GREETING HANDLING
# ============================================================

async def classify_greeting(question: str) -> bool:
    messages = [
        {
            "role": "system",
            "content": (
                "Return exactly GREETING for a simple greeting such as "
                "hi, hello, hey bro or good morning. Return exactly "
                "NOT_GREETING for business questions or substantive tasks."
            ),
        },
        {"role": "user", "content": question},
    ]

    try:
        message = await ask_ollama(messages)
        return message.get("content", "").strip().upper() == "GREETING"
    except Exception:
        return False


def is_calculation_request(question: str) -> bool:
    q = question.lower()

    return any(
        phrase in q
        for phrase in (
            "calculate",
            "calculation",
            "total cost",
            "cost of",
            "how much",
            "what is the cost",
            "price for",
            "bill for",
            "total price",
        )
    )


# ============================================================
# MCP EXECUTION
# ============================================================

async def execute_mcp_tool(
    session: ClientSession,
    tool_name: str,
    arguments: dict[str, Any],
) -> str:
    """Execute an MCP tool after independent validation."""

    safe_arguments = validate_arguments(tool_name, arguments)

    result = await session.call_tool(
        tool_name,
        arguments=safe_arguments,
    )

    if result.isError:
        raise RuntimeError("The MCP tool reported an execution error.")

    text_parts = [
        content.text
        for content in result.content
        if getattr(content, "type", None) == "text"
    ]

    if not text_parts:
        raise RuntimeError("The MCP tool returned no readable result.")

    return "\n".join(text_parts)


# ============================================================
# MAIN AGENT
# ============================================================

async def ask_business_assistant(question: str) -> dict[str, Any]:
    started_at = time.perf_counter()
    trace: list[dict[str, Any]] = []

    question = question.strip()

    add_event(
        trace,
        "request_received",
        "success",
        "Backend received the user's request.",
        details={"question": question},
    )

    if not question:
        add_event(
            trace,
            "validation",
            "error",
            "The request was empty.",
        )

        return make_result(
            "Please enter a question.",
            trace,
            started_at,
            status="error",
        )

    # --------------------------------------------------------
    # 1. Greeting classification
    # --------------------------------------------------------

    classification_started = time.perf_counter()

    is_greeting = await classify_greeting(question)

    classification_duration = (
        time.perf_counter() - classification_started
    ) * 1000

    add_event(
        trace,
        "greeting_classification",
        "success",
        "Greeting classification completed.",
        duration_ms=classification_duration,
        details={"is_greeting": is_greeting},
    )

    if is_greeting:
        answer = (
            "Hi! I'm Business Tools AI. I can calculate product costs "
            "and check stock availability. What would you like to do?"
        )

        add_event(
            trace,
            "completed",
            "success",
            "Responded to a greeting without executing an MCP tool.",
        )

        return make_result(answer, trace, started_at)

    # --------------------------------------------------------
    # 2. Catch incomplete calculations
    # --------------------------------------------------------

    if is_calculation_request(question):
        numbers = re.findall(
            r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?",
            question,
        )

        if len(numbers) < 2:
            answer = (
                "Please provide both the quantity and unit price. "
                "For example: Calculate the cost of 15 keyboards "
                "at 250 rupees each."
            )

            add_event(
                trace,
                "input_validation",
                "waiting_for_input",
                "The calculation is missing a quantity or unit price.",
            )

            return make_result(
                answer,
                trace,
                started_at,
                status="needs_input",
            )

    # --------------------------------------------------------
    # 3. Ask Ollama to select a tool
    # --------------------------------------------------------

    system_message = """
You are Business Tools AI.

Available tools:
- calculate_total(quantity, unit_price)
- check_stock(product_name, available_stock, requested_quantity)

Rules:
- Never invent business values.
- Use only values explicitly provided by the user.
- For calculations, quantity and unit price are required.
- For stock checks, product name, available stock and requested quantity
  are required.
- Never change a negative quantity to a positive quantity.
- Never execute tools with missing or invalid values.
- For incomplete requests, ask for missing information.
- Use Indian rupees when the user specifies rupees or INR.
- Do not claim a tool ran unless it actually ran.
"""

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": question},
    ]

    model_started = time.perf_counter()

    add_event(
        trace,
        "model_request",
        "running",
        "Sending the request and available tool definitions to Ollama.",
    )

    try:
        assistant_message = await ask_ollama(
            messages,
            tools=TOOL_DEFINITIONS,
        )
    except Exception as exc:
        duration = (time.perf_counter() - model_started) * 1000

        finish_event(
            trace,
            "model_request",
            "error",
            "Ollama request failed.",
            duration_ms=duration,
            details={"error": str(exc)},
        )

        return make_result(
            "I couldn't reach the local AI service. Check Ollama and "
            "the llama3.2 model.",
            trace,
            started_at,
            status="error",
        )

    model_duration = (time.perf_counter() - model_started) * 1000

    finish_event(
        trace,
        "model_request",
        "success",
        "Ollama request completed successfully.",
        duration_ms=model_duration,
        details={"tool_call_requested": bool(assistant_message.get("tool_calls"))},
    )

    tool_calls = assistant_message.get("tool_calls") or []

    add_event(
        trace,
        "model_response",
        "success",
        "Ollama returned a response.",
        duration_ms=model_duration,
        details={
            "tool_call_requested": bool(tool_calls),
        },
    )

    # --------------------------------------------------------
    # 4. No tool requested
    # --------------------------------------------------------

    if not tool_calls:
        answer = assistant_message.get("content", "").strip()

        if not answer:
            answer = (
                "I couldn't determine the answer. Please rephrase "
                "your question or provide the missing details."
            )

        add_event(
            trace,
            "completed",
            "success",
            "The assistant responded without an MCP tool call.",
        )

        return make_result(answer, trace, started_at)

    # --------------------------------------------------------
    # 5. Parse and validate the selected tool
    # --------------------------------------------------------

    tool_call = tool_calls[0]
    function_data = tool_call.get("function", {})

    tool_name = function_data.get("name")
    raw_arguments = function_data.get("arguments", {})

    add_event(
        trace,
        "tool_selected",
        "success",
        "Ollama requested an MCP tool.",
        details={"tool_name": tool_name},
    )

    try:
        arguments = parse_json_arguments(raw_arguments)
        safe_arguments = validate_arguments(tool_name, arguments)

    except ValueError as exc:
        add_event(
            trace,
            "argument_validation",
            "error",
            "Tool arguments were rejected before MCP execution.",
            details={"error": str(exc)},
        )

        return make_result(
            f"I couldn't execute the tool safely: {exc}",
            trace,
            started_at,
            status="error",
        )

    add_event(
        trace,
        "argument_validation",
        "success",
        "Tool arguments passed validation.",
        details={"arguments": safe_arguments},
    )

    # --------------------------------------------------------
    # 6. Start MCP client and initialize the session
    # --------------------------------------------------------

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(SERVER_PATH)],
    )

    try:
        client_started = time.perf_counter()

        add_event(
            trace,
            "mcp_client",
            "running",
            "Starting the MCP client and launching the server over STDIO.",
        )

        async with stdio_client(server_parameters) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                client_duration = (
                    time.perf_counter() - client_started
                ) * 1000

                finish_event(
                    trace,
                    "mcp_client",
                    "success",
                    "MCP client session initialized successfully.",
                    duration_ms=client_duration,
                    details={"transport": "STDIO", "server_path": str(SERVER_PATH)},
                )

                add_event(
                    trace,
                    "mcp_initialized",
                    "success",
                    "MCP client session initialized successfully.",
                    duration_ms=client_duration,
                )

                # ------------------------------------------------
                # 7. Discover tools from the actual MCP server
                # ------------------------------------------------

                discovery_started = time.perf_counter()

                listed_tools = await session.list_tools()

                discovery_duration = (
                    time.perf_counter() - discovery_started
                ) * 1000

                discovered_names = [
                    item.name for item in listed_tools.tools
                ]

                add_event(
                    trace,
                    "tool_discovery",
                    "success",
                    "Retrieved the available tools from the MCP server.",
                    duration_ms=discovery_duration,
                    details={"tools": discovered_names},
                )

                if tool_name not in discovered_names:
                    raise ValueError(
                        f"{tool_name} was not exposed by the MCP server."
                    )

                # ------------------------------------------------
                # 8. Call the actual MCP tool
                # ------------------------------------------------

                tool_started = time.perf_counter()

                add_event(
                    trace,
                    "mcp_tool_call",
                    "running",
                    f"Calling MCP tool: {tool_name}.",
                    details={
                        "tool_name": tool_name,
                        "arguments": safe_arguments,
                    },
                )

                raw_result = await session.call_tool(
                    tool_name,
                    arguments=safe_arguments,
                )

                tool_duration = (
                    time.perf_counter() - tool_started
                ) * 1000

                finish_event(
                    trace,
                    "mcp_tool_call",
                    "error" if raw_result.isError else "success",
                    (
                        f"MCP tool {tool_name} returned an execution error."
                        if raw_result.isError
                        else f"MCP tool {tool_name} completed successfully."
                    ),
                    duration_ms=tool_duration,
                    details={
                        "tool_name": tool_name,
                        "arguments": safe_arguments,
                    },
                )

                if raw_result.isError:
                    add_event(
                        trace,
                        "mcp_tool_result",
                        "error",
                        "The MCP server reported a tool execution error.",
                        duration_ms=tool_duration,
                        details={"tool_name": tool_name},
                    )

                    return make_result(
                        "The MCP tool reported an execution error.",
                        trace,
                        started_at,
                        tool_used=tool_name,
                        tool_arguments=safe_arguments,
                        tool_duration_ms=tool_duration,
                        status="error",
                    )

                result_parts = [
                    content.text
                    for content in raw_result.content
                    if getattr(content, "type", None) == "text"
                ]

                actual_tool_result = "\n".join(result_parts)

                if not actual_tool_result:
                    actual_tool_result = (
                        "The tool returned no readable text content."
                    )

                add_event(
                    trace,
                    "mcp_tool_result",
                    "success",
                    "The MCP tool returned a result.",
                    duration_ms=tool_duration,
                    details={
                        "tool_name": tool_name,
                        "result": actual_tool_result,
                    },
                )

    except ValueError as exc:
        failure_duration = (time.perf_counter() - client_started) * 1000 if "client_started" in locals() else None
        finish_event(
            trace,
            "mcp_client",
            "error",
            "MCP client execution failed.",
            duration_ms=failure_duration,
            details={"error": str(exc)},
        )
        finish_event(
            trace,
            "mcp_tool_call",
            "error",
            "MCP tool call failed before returning a result.",
            details={"error": str(exc), "tool_name": tool_name},
        )

        add_event(
            trace,
            "mcp_execution",
            "error",
            "MCP execution could not be completed.",
            details={"error": str(exc)},
        )

        return make_result(
            f"I couldn't execute the tool safely: {exc}",
            trace,
            started_at,
            tool_used=tool_name,
            tool_arguments=safe_arguments,
            status="error",
        )

    except Exception as exc:
        print(f"MCP execution failed: {exc}", file=sys.stderr)

        failure_duration = (time.perf_counter() - client_started) * 1000 if "client_started" in locals() else None
        finish_event(
            trace,
            "mcp_client",
            "error",
            "MCP client execution failed.",
            duration_ms=failure_duration,
            details={"error": str(exc)},
        )
        finish_event(
            trace,
            "mcp_tool_call",
            "error",
            "MCP tool call failed before returning a result.",
            details={"error": str(exc), "tool_name": tool_name},
        )

        add_event(
            trace,
            "mcp_execution",
            "error",
            "An error occurred during MCP execution.",
            details={"error": str(exc)},
        )

        return make_result(
            "The MCP tool could not be executed. Check the backend logs.",
            trace,
            started_at,
            tool_used=tool_name,
            tool_arguments=safe_arguments,
            status="error",
        )

    # --------------------------------------------------------
    # 9. Build a reliable answer from the validated inputs
    # --------------------------------------------------------

    if tool_name == "calculate_total":
        total = round(
            safe_arguments["quantity"] * safe_arguments["unit_price"],
            2,
        )

        answer = (
            f"Total cost: ₹{total:,.2f}\n"
            f"Quantity: {safe_arguments['quantity']}\n"
            f"Unit price: ₹{safe_arguments['unit_price']:,.2f}"
        )

    elif tool_name == "check_stock":
        available = safe_arguments["available_stock"]
        requested = safe_arguments["requested_quantity"]
        product = safe_arguments["product_name"]

        if available >= requested:
            answer = (
                f"The stock level of {available} {product}(s) is sufficient "
                f"to meet the requested quantity of {requested}."
            )
        else:
            shortage = requested - available

            answer = (
                f"Stock is insufficient for {product}. "
                f"Available: {available}; requested: {requested}; "
                f"shortage: {shortage}."
            )

    else:
        answer = actual_tool_result

    add_event(
        trace,
        "completed",
        "success",
        "MCP execution completed and the final answer was prepared.",
    )

    return make_result(
        answer=answer,
        trace=trace,
        started_at=started_at,
        tool_used=tool_name,
        tool_arguments=safe_arguments,
        tool_result=actual_tool_result,
        tool_duration_ms=tool_duration,
        status="success",
    )