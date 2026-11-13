"""Use Hermes' installed official MCP SDK; credentials arrive over stdin only."""
import asyncio
from contextlib import AsyncExitStack
import json
import os
import sys
import urllib.parse


async def main(request):
    from mcp import ClientSession, StdioServerParameters, types
    from mcp.client.stdio import stdio_client
    from mcp.client.streamable_http import streamable_http_client
    spec=request['server']
    async with AsyncExitStack() as stack:
        if spec.get('transport','stdio')=='stdio':
            executable=spec.get('command','')
            if not os.path.isabs(executable):raise ValueError('MCP executable must be an operator-configured absolute path')
            streams=await stack.enter_async_context(stdio_client(StdioServerParameters(command=executable,args=spec.get('args',[]),env=spec.get('env',{}))))
        else:
            url=urllib.parse.urlsplit(spec['url'])
            if url.scheme!='https' and not (url.scheme=='http' and url.hostname in ['127.0.0.1','localhost','::1']):raise ValueError('MCP requires HTTPS or loopback HTTP')
            import httpx2
            client=await stack.enter_async_context(httpx2.AsyncClient(headers=spec.get('headers',{}),timeout=25,follow_redirects=False))
            streams=await stack.enter_async_context(streamable_http_client(spec['url'],http_client=client))
        session=await stack.enter_async_context(ClientSession(streams[0],streams[1],read_timeout_seconds=25))
        await session.initialize()
        if request['action']=='list':
            tools=[];cursor=None
            for _ in range(10):
                result=await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor) if cursor else None)
                tools.extend(x.model_dump(mode='json',by_alias=True) for x in result.tools)
                cursor=result.next_cursor
                if not cursor:break
            return {'tools':tools}
        if request['action']=='call':
            result=await session.call_tool(request['tool'],request.get('arguments',{}))
            return {'result':result.model_dump(mode='json',by_alias=True)}
        raise ValueError('Unsupported MCP operation')


if __name__=='__main__':
    try:
        result=asyncio.run(asyncio.wait_for(main(json.load(sys.stdin)),30))
        print(json.dumps(result))
    except Exception:
        # Server exceptions may contain credentials or URLs; return a bounded public error.
        print(json.dumps({'error':'MCP negotiation, authorization or tool call failed'}))
        sys.exit(1)
