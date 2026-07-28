from mcp.server import FastMCP

from tools import register_tools
from resources import register_resources
from prompts import register_prompts

mcp = FastMCP("Brightpeak Academy MCP Server")

# Register components
register_tools(mcp)
register_resources(mcp)
register_prompts(mcp)

if __name__ == "__main__":
    print("Brightpeak Academy MCP Server Started")
    mcp.run()