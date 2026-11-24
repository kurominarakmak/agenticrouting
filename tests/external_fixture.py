"""Isolated MCP acceptance fixture. It has no external account or market data."""
import asyncio,os
from mcp import types
from mcp.server import Server
from mcp.server.stdio import stdio_server
async def listing(context,params):return types.ListToolsResult(tools=[types.Tool(name='read_number',description='Read synthetic acceptance data',inputSchema={'type':'object','properties':{'offset':{'type':'integer','minimum':0,'maximum':2}},'required':['offset'],'additionalProperties':False}),types.Tool(name='place_order',description='Forbidden fixture',inputSchema={'type':'object','properties':{}})])
async def call(context,params):
 if params.name!='read_number':raise ValueError('Forbidden fixture operation')
 return types.CallToolResult(content=[types.TextContent(type='text',text=str(740+params.arguments['offset'])+(' '+os.environ['READ_FIXTURE_KEY'] if os.environ.get('READ_FIXTURE_KEY') else ''))])
async def main():
 server=Server('external-readonly-fixture',on_list_tools=listing,on_call_tool=call)
 async with stdio_server() as (read,write):await server.run(read,write,server.create_initialization_options())
if __name__=='__main__':asyncio.run(main())
