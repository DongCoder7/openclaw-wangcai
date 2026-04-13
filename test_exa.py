#!/root/.openclaw/workspace/venv/bin/python3
import os
import json
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio

async def main():
    # Exa MCP 配置
    async with stdio_client(
        StdioServerParameters(
            command="mcporter",
            args=["call", "exa.contents_search", "query=当红利低波遇上凯利公式", "limit:10"],
            env=os.environ.copy()
        )
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            result = await session.call_tool("contents_search", {"query": "当红利低波遇上凯利公式", "limit": 10})
            print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    asyncio.run(main())
