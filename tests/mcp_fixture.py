"""Protocol fixture only: no real market data or external account access."""
import asyncio
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server

async def list_tools(context,params):
    return types.ListToolsResult(tools=[types.Tool(name='read_status',description='Read a local protocol-test status, not market data',inputSchema={'type':'object','properties':{},'additionalProperties':False}),types.Tool(name='place_order',description='Forbidden fixture operation',inputSchema={'type':'object','properties':{}})])

async def call_tool(context,params):
    if params.name!='read_status':raise ValueError('Fixture only supports read_status')
    return types.CallToolResult(content=[types.TextContent(type='text',text='Protocol fixture is reachable; this is not a real provider')],isError=False)

async def main():
    server=Server('personal-ai-work-test-fixture',on_list_tools=list_tools,on_call_tool=call_tool)
    async with stdio_server() as (read,write):await server.run(read,write,server.create_initialization_options())

if __name__=='__main__':asyncio.run(main())
