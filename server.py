from mcp.server.fastmcp import FastMCP

mcp = FastMCP("Business Tools Server")


@mcp.tool()
def calculate_total(quantity: int, unit_price: float) -> float:
    """Calculate the total cost using quantity and unit price."""

    if isinstance(quantity, bool) or not isinstance(quantity, int):
        raise ValueError("Quantity must be a whole number.")

    if quantity <= 0:
        raise ValueError("Quantity must be greater than zero.")

    if isinstance(unit_price, bool) or not isinstance(unit_price, (int, float)):
        raise ValueError("Unit price must be a number.")

    if unit_price < 0:
        raise ValueError("Unit price cannot be negative.")

    return round(quantity * unit_price, 2)


@mcp.tool()
def check_stock(
    product_name: str,
    available_stock: int,
    requested_quantity: int,
) -> str:
    """Check whether sufficient stock is available for a product."""

    if not isinstance(product_name, str) or not product_name.strip():
        raise ValueError("Product name cannot be empty.")

    if len(product_name.strip()) > 100:
        raise ValueError("Product name cannot exceed 100 characters.")

    if isinstance(available_stock, bool) or not isinstance(available_stock, int):
        raise ValueError("Available stock must be a whole number.")

    if isinstance(requested_quantity, bool) or not isinstance(requested_quantity, int):
        raise ValueError("Requested quantity must be a whole number.")

    if available_stock < 0:
        raise ValueError("Available stock cannot be negative.")

    if requested_quantity <= 0:
        raise ValueError("Requested quantity must be greater than zero.")

    if available_stock >= requested_quantity:
        return (
            f"Sufficient stock for {product_name.strip()}. "
            f"Available: {available_stock}, requested: {requested_quantity}."
        )

    shortage = requested_quantity - available_stock

    return (
        f"Insufficient stock for {product_name.strip()}. "
        f"Available: {available_stock}, requested: {requested_quantity}, "
        f"shortage: {shortage}."
    )


if __name__ == "__main__":
    mcp.run()