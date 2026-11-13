"""Real CLI and official MCP SDK contract tests, including stdio transport."""
import asyncio
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from test_service import ROOT, seed, requirement
from scl.service import ModelService, OPERATIONS

try:
    from mcp import Client
    from mcp.client.stdio import StdioServerParameters
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False


class InterfaceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.root=seed(Path(self.temp.name)/'project')

    def tearDown(self): self.temp.cleanup()

    def cli(self, operation, params=None):
        completed=subprocess.run([sys.executable,str(ROOT/'imk'),'--root',str(self.root),'api',operation,'--json',json.dumps(params or {})],capture_output=True,text=True)
        return completed,json.loads(completed.stdout)

    def test_cli_and_service_context_match(self):
        completed,response=self.cli('get_context',{'query':'observable','limit':1})
        self.assertEqual(completed.returncode,0,completed.stderr)
        self.assertEqual(response,ModelService(self.root).execute('get_context',query='observable',limit=1))

    def test_cli_errors_are_json_and_nonzero(self):
        completed,response=self.cli('add_requirement',{'record':{}})
        self.assertEqual(completed.returncode,1)
        self.assertEqual(response['findings'][0]['rule'],'request.shape')
        self.assertNotIn('Traceback',completed.stderr)

    def test_cli_proposal_is_service_proposal(self):
        revision=ModelService(self.root).execute('get_model_revision')['model_revision']
        params={'record':requirement(),'parent_id':'model-a','expected_revision':revision}
        _,response=self.cli('add_requirement',params)
        self.assertEqual(response,ModelService(self.root).execute('add_requirement',**params))

    @unittest.skipUnless(MCP_AVAILABLE,'install .[mcp] to run MCP contract tests')
    def test_mcp_schemas_and_calls_match_service(self):
        from scl.mcp_server import create_server
        async def run():
            server=create_server(self.root)
            async with Client(server) as client:
                listed=await client.list_tools()
                # SDK returns a result envelope for list operations.
                tools=listed.tools if hasattr(listed,'tools') else listed
                self.assertEqual({t.name for t in tools},{'scl_'+op for op in OPERATIONS})
                requirement_tool=next(t for t in tools if t.name=='scl_add_requirement')
                self.assertIn('expected_revision',requirement_tool.input_schema['required'])
                self.assertIn('acceptance',requirement_tool.input_schema['properties']['record']['properties']['metadata']['properties'])
                self.assertIn('model_revision',requirement_tool.output_schema['required'])
                response=await client.call_tool('scl_get_context',{'query':'observable','limit':1})
                self.assertEqual(response.structured_content,ModelService(self.root).execute('get_context',query='observable',limit=1))
                rev=response.structured_content['model_revision']
                params={'record':requirement(),'parent_id':'model-a','expected_revision':rev}
                proposed=await client.call_tool('scl_add_requirement',params)
                self.assertEqual(proposed.structured_content,ModelService(self.root).execute('add_requirement',**params))
                bad=await client.call_tool('scl_commit_change',{'proposal_id':proposed.structured_content['data']['proposal_id'],'expected_revision':rev})
                self.assertEqual(bad.structured_content['findings'][0]['rule'],'approval.required')
        asyncio.run(run())

    @unittest.skipUnless(MCP_AVAILABLE,'install .[mcp] to run MCP stdio test')
    def test_mcp_stdio_startup_and_discovery(self):
        async def run():
            # Module entry is the same command documented for MCP clients.
            params=StdioServerParameters(command=sys.executable,args=['-m','scl.mcp_server','--root',str(self.root)],env={'PYTHONPATH':str(ROOT/'src/tooling')})
            async with Client(params) as client:
                response=await client.call_tool('scl_get_model_revision',{})
                self.assertEqual(response.structured_content['status'],'ok')
                self.assertEqual(response.structured_content,ModelService(self.root).execute('get_model_revision'))
        asyncio.run(run())
