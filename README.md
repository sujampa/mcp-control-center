# MCP Control Center

A local AI-powered business tool execution playground built with React, FastAPI, Ollama, and the Model Context Protocol (MCP).

MCP Control Center allows users to submit business requests in natural language, lets an AI model select the appropriate tool, and executes that tool through an MCP server. The interface displays validated arguments, actual tool results, execution status, and a detailed execution trace.

## Features

- **AI-Powered Tool Selection:** Uses Llama 3.2 through Ollama to interpret business requests.
- **MCP Integration:** Connects an MCP client to a Python MCP server using STDIO.
- **Business Tools:** Supports product cost calculations and stock availability checks.
- **Input Validation:** Validates tool arguments before execution.
- **Execution Trace:** Displays backend execution events and their statuses.
- **Tool Results:** Shows the selected tool, validated arguments, actual MCP result, and execution duration.
- **Local Execution:** Runs using locally configured services.

## Tech Stack

| Technology | Purpose |
|---|---|
| Python | MCP server and business logic |
| Model Context Protocol (MCP) | Tool discovery and execution |
| FastAPI | Backend API |
| React | Interactive frontend |
| Ollama | Local AI model runtime |
| Llama 3.2 | Natural-language understanding and tool selection |
| Node.js and npm | Frontend development |

## Architecture

```text
User Request
     |
     v
React Frontend
     |
     v
FastAPI Backend
     |
     v
Ollama - Llama 3.2
     |
     v
Tool Selection and Argument Validation
     |
     v
MCP Client (STDIO)
     |
     v
Python MCP Server
     |
     +----------------------+
     |                      |
     v                      v
calculate_total         check_stock
     |                      |
     +----------+-----------+
                |
                v
       Actual Tool Result
                |
                v
     Execution Trace and Answer
