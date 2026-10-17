import asyncio
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client


async def main():
    """Connect to the MCP server and test its tools."""

    server_path = Path(__file__).resolve().with_name("server.py")

    if not server_path.exists():
        print(f"Error: MCP server not found at {server_path}")
        return

    server_parameters = StdioServerParameters(
        command=sys.executable,
        args=[str(server_path)],
    )

    try:
        async with stdio_client(server_parameters) as (
            read_stream,
            write_stream,
        ):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()

                print("Connected to the MCP server!")

                # Discover available tools.
                tools_result = await session.list_tools()

                print("\nAvailable tools:")

                for tool in tools_result.tools:
                    print(f"- {tool.name}: {tool.description}")

                available_tools = {
                    tool.name for tool in tools_result.tools
                }

                # Test calculate_total.
                if "calculate_total" not in available_tools:
                    print("Error: calculate_total is unavailable.")
                    return

                print("\nCalling calculate_total...")

                calculation_result = await session.call_tool(
                    "calculate_total",
                    arguments={
                        "quantity": 15,
                        "unit_price": 250,
                    },
                )

                if calculation_result.isError:
                    print("The calculation tool returned an error.")
                    return

                print("\nCalculation result:")

                for item in calculation_result.content:
                    if getattr(item, "type", None) == "text":
                        print(item.text)

                # Test check_stock.
                if "check_stock" not in available_tools:
                    print("Error: check_stock is unavailable.")
                    return

                print("\nCalling check_stock...")

                stock_result = await session.call_tool(
                    "check_stock",
                    arguments={
                        "product_name": "Keyboard",
                        "available_stock": 20,
                        "requested_quantity": 5,
                    },
                )

                if stock_result.isError:
                    print("The stock-check tool returned an error.")
                    return

                print("\nStock check result:")

                for item in stock_result.content:
                    if getattr(item, "type", None) == "text":
                        print(item.text)

                print("\nBoth MCP tool calls completed successfully.")

    except Exception as exc:
        print(f"MCP client failed: {exc}", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(main())