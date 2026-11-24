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
        async def inventory():
            tools=[];cursor=None;seen=set()
            for _ in range(10):
                page=await session.list_tools(params=types.PaginatedRequestParams(cursor=cursor) if cursor else None)
                tools.extend(page.tools);cursor=page.next_cursor
                if not cursor:return tools
                if cursor in seen:raise ValueError('Repeated MCP pagination cursor')
                seen.add(cursor)
            raise ValueError('MCP pagination limit reached')
        if request['action']=='list':return {'tools':[x.model_dump(mode='json',by_alias=True) for x in await inventory()]}
        if request['action']=='call':
            from jsonschema import Draft202012Validator
            listed=await inventory()
            tool=next((t for t in listed if t.name==request['tool']),None)
            if tool is None:raise ValueError('Unknown MCP tool')
            schema=tool.model_dump(mode='json',by_alias=True)['inputSchema']
            def refs(value):
                if isinstance(value,dict):
                    if '$ref' in value and not str(value['$ref']).startswith('#/'):raise ValueError('Remote schema references refused')
                    for v in value.values():refs(v)
                elif isinstance(value,list):
                    for v in value:refs(v)
            if len(json.dumps(schema))>50000:raise ValueError('MCP argument schema too large')
            refs(schema);Draft202012Validator.check_schema(schema);Draft202012Validator(schema).validate(request.get('arguments',{}))
            result=await session.call_tool(request['tool'],request.get('arguments',{}))
            return {'result':result.model_dump(mode='json',by_alias=True)}
        raise ValueError('Unsupported MCP operation')


if __name__=='__main__':
    try:
        result=asyncio.run(asyncio.wait_for(main(json.load(sys.stdin)),30))
        print(json.dumps(result))
    except Exception as failure:
        # Server exceptions may contain credentials or URLs; return a bounded public error.
        from jsonschema.exceptions import ValidationError
        def invalid(exc):
            return isinstance(exc,ValidationError) or any(invalid(child) for child in getattr(exc,'exceptions',[]))
        print(json.dumps({'error':'MCP argument validation failed' if invalid(failure) else 'MCP negotiation, authorization or tool call failed','error_code':'invalid_arguments' if invalid(failure) else 'unavailable'}))
        sys.exit(1)
