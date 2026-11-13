"""Graph, transactions, approval and trusted publication boundary integration tests."""
from copy import deepcopy
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/tooling'))
from test_scl import mini_model, rel
from scl.approval import SSHApproval, UnavailableApproval, verifier_from_environment
from scl.contracts import ServiceError
from scl.domain import canonical, digest
from scl.export import generated_findings, write_generated
from scl.governance import verify_transition
from scl.model import load_model, structural_findings
from scl.service import ModelService
from scl.storage import JsonStorage, json_bytes


def seed(root):
    model = root / 'knowledge'
    (model/'nodes').mkdir(parents=True)
    (model/'relationships').mkdir()
    config = {'model': 'knowledge', 'metamodel': 'iomr-evolved', 'metamodelVersion': '2.0.0', 'sources': []}
    (root/'imk.json').write_bytes(json_bytes(config))
    shutil.copy(ROOT/'meta/iomr-model/metamodel.json', model/'metamodel.json')
    fixture = mini_model()
    fixture.root = root
    fixture.model_location = "knowledge"
    (model/'nodes/domain.json').write_bytes(json_bytes(fixture.nodes[:4]))
    (model/'nodes/context.json').write_bytes(json_bytes(fixture.nodes[4:]))
    (model/'relationships/graph.json').write_bytes(json_bytes(fixture.relationships))
    write_generated(root, fixture)
    return root


def requirement(name='New rule'):
    return {'name': name, 'description': 'The system shall preserve the submitted reason.',
            'metadata': {'inference': 'Inferred from the requested reason preservation.',
                         'acceptance': 'Given a reason, when stored, then the exact reason can be read.'}}


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.keys = tempfile.TemporaryDirectory()
        cls.key = Path(cls.keys.name)/'review'
        subprocess.run(['ssh-keygen','-q','-t','ed25519','-N','','-f',str(cls.key)], check=True)
        cls.signers = Path(cls.keys.name)/'allowed_signers'
        cls.signers.write_text('test-reviewer ' + cls.key.with_suffix('.pub').read_text())

    @classmethod
    def tearDownClass(cls):
        cls.keys.cleanup()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = seed(Path(self.temp.name)/'project')
        self.verifier = SSHApproval(self.signers)
        self.service = ModelService(self.root, approval=self.verifier)
        self.revision = self.call('get_model_revision')['model_revision']

    def tearDown(self):
        self.temp.cleanup()

    def call(self, operation_name, **params):
        return self.service.execute(operation_name, **params)

    def propose(self, name='New rule'):
        result = self.call('add_requirement',record=requirement(name),parent_id='model-a',expected_revision=self.revision)
        self.assertEqual(result['status'],'ok',result)
        return result['data']

    def sign(self, payload):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory)/'payload'
            path.write_bytes(canonical(payload))
            subprocess.run(['ssh-keygen','-Y','sign','-f',str(self.key),'-n','scl-iomr-v1',str(path)],check=True,capture_output=True)
            return path.with_suffix('.sig').read_text()

    def approve(self, proposal_id):
        preview = self.call('preview_change',proposal_id=proposal_id,reviewer='test-reviewer')
        self.assertEqual(preview['data']['validation_status'],'valid',preview)
        signature = self.sign(preview['data']['approval_payload'])
        response = self.call('approve_change', proposal_id=proposal_id,identity='test-reviewer',signature=signature,expected_revision=self.revision)
        self.assertEqual(response['status'],'ok',response)
        return signature

    def commit(self, proposal_id):
        self.approve(proposal_id)
        response = self.call('commit_change',proposal_id=proposal_id,expected_revision=self.revision)
        self.assertEqual(response['status'],'ok',response)
        return response

    def test_requirement_workflow_and_provenance(self):
        proposal = self.propose()
        self.assertEqual(proposal['validation_status'],'valid',proposal)
        self.assertNotIn('requirement-new-rule',load_model(self.root).by_id)
        self.commit(proposal['proposal_id'])
        loaded = load_model(self.root)
        self.assertEqual(structural_findings(loaded),[])
        self.assertEqual(generated_findings(self.root,loaded),[])
        self.assertIn('Source: knowledge', (self.root/'TRACEABILITY.md').read_text())
        node = loaded.by_id['requirement-new-rule']
        self.assertEqual(node['metadata']['basis'],'derived')
        self.assertEqual(node['metadata']['provenance'][0]['original_basis'],'inferred')
        self.assertEqual(node['metadata']['provenance'][0]['reviewer'],'test-reviewer')
        self.assertIn('inference',node['metadata'])
        self.assertTrue((self.root/'knowledge/nodes/domain.json').exists())
        self.assertFalse((self.root/'knowledge/nodes/records.json').exists())

    def test_default_mode_has_no_approval_capability(self):
        self.service = ModelService(self.root,approval=UnavailableApproval())
        p = self.propose()
        response = self.call('approve_change',proposal_id=p['proposal_id'],identity='test-reviewer',signature='forged',expected_revision=self.revision)
        self.assertEqual(response['findings'][0]['rule'],'approval.unavailable')

    def test_self_declared_approval_and_human_origin_grant_nothing(self):
        p = self.call('add_requirement',record=requirement(),parent_id='model-a',expected_revision=self.revision,origin='human-authored')['data']
        blocked = self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision)
        self.assertEqual(blocked['findings'][0]['rule'],'approval.required')
        forged = self.call('approve_change',proposal_id=p['proposal_id'],identity='test-reviewer',signature='approved: true',expected_revision=self.revision)
        self.assertEqual(forged['findings'][0]['rule'],'approval.invalid')
        bad = self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision,approved=True)
        self.assertEqual(bad['status'],'error')

    def test_invalid_candidate_preserves_canonical_bytes(self):
        before = self.service.storage.snapshot()
        result = self.call('link_records',type='delivers',source='requirement-a',target='intent-a',rationale='This is deliberately an illegal graph relationship.',expected_revision=self.revision)
        p = result['data']
        self.assertEqual(p['validation_status'],'invalid')
        self.assertIn('rel.legality',{f['rule'] for f in p['validation_findings']})
        self.assertEqual(before,self.service.storage.snapshot())
        self.assertEqual(self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision)['status'],'error')

    def test_invalid_change_can_be_corrected(self):
        p = self.call('link_records',type='delivers',source='requirement-a',target='intent-a',rationale='This link must use an appropriate context relationship.',expected_revision=self.revision)['data']
        stored = self.call('get_proposal',proposal_id=p['proposal_id'])['data']['proposal']
        stored['changes'][0]['relationship']['type']='depends_on'
        updated=self.call('update_proposal',proposal_id=p['proposal_id'],changes=stored['changes'],expected_revision=self.revision,expected_proposal_revision=p['proposal_revision'])
        self.assertEqual(updated['data']['validation_status'],'valid',updated)
        self.commit(p['proposal_id'])

    def test_complete_multi_record_interaction(self):
        r = requirement('Interaction guard');r.update(type='Requirement',id='requirement-guard')
        result=self.call('add_model',record={'name':'New interaction','interaction':['system-system'],
            'description':'Record a reason between systems.', 'steps':[{'from':'system-a','to':'system-interaction','message':'reason'}],
            'metadata':{'inference':'Interaction inferred from the request.'}},parent_id='outcome-a',participants=['system-a','system-interaction'],
            related_changes=[{'op':'add_record','record':{'id':'system-interaction','type':'System','name':'Interaction system','description':'The receiving system in the proposed interaction.','metadata':{'inference':'A distinct receiving participant is proposed.'}}},{'op':'add_record','record':r},{'op':'add_relationship','relationship':rel('specifies','requirement-guard','model-new-interaction')}],expected_revision=self.revision)
        self.assertEqual(result['data']['validation_status'],'valid',result)
        self.commit(result['data']['proposal_id'])

    def test_whole_graph_coverage_blocks_locally_legal_removal(self):
        p=self.call('propose_change',title='Remove coverage',changes=[{'op':'remove_relationship','id':'requirement-a-specifies-model-a','reason':'Remove this link while leaving the model uncovered.'}],expected_revision=self.revision)['data']
        rules={f['rule'] for f in p['validation_findings']}
        self.assertIn('trace.coverage',rules)
        self.assertIn('trace.reach-intent',rules)

    def test_duplicate_ids_and_names(self):
        for patch_record in ({'id':'requirement-a'}, {'name':'A'}):
            record=requirement();record.update(patch_record)
            p=self.call('add_requirement',record=record,parent_id='model-a',expected_revision=self.revision)['data']
            self.assertEqual(p['validation_status'],'invalid',p)

    def test_missing_endpoint(self):
        p=self.call('add_requirement',record=requirement(),parent_id='model-missing',expected_revision=self.revision)['data']
        self.assertIn('rel.legality',{f['rule'] for f in p['validation_findings']})

    def test_evidence_and_acceptance(self):
        for metadata, rule in [({'evidence':['missing:path#L1']},'ref.evidence'),({'acceptance':''},'record.acceptance')]:
            record=requirement();record['metadata'].update(metadata)
            p=self.call('add_requirement',record=record,parent_id='model-a',expected_revision=self.revision)['data']
            self.assertIn(rule,{f['rule'] for f in p['validation_findings']})

    def test_participants_steps_and_refinement(self):
        for changes, rule in [
            ([{'op':'remove_relationship','id':'model-a-involves-system-b','reason':'Remove an essential system participant from this interaction.'}],'model.participants'),
            ([{'op':'update_record','id':'model-a','patch':{'steps':[{'from':'system-missing','to':'system-b','message':''}]}}],'model.steps'),
            ([{'op':'add_relationship','relationship':rel('refines','model-a','model-a')}],'refines.discipline')]:
            p=self.call('propose_change',title=rule,changes=changes,expected_revision=self.revision)['data']
            self.assertIn(rule,{f['rule'] for f in p['validation_findings']})

    def test_invalid_lifecycle_and_immutable_identity(self):
        for patch_value in ({'id':'requirement-new'},{'status':'retired'},{'status':'nonsense'}):
            p=self.call('update_requirement',record_id='requirement-a',patch=patch_value,expected_revision=self.revision)['data']
            self.assertEqual(p['validation_status'],'invalid')

    def test_retirement_keeps_history_and_requires_same_type_successor(self):
        p=self.propose('Replacement rule')
        changes=self.call('get_proposal',proposal_id=p['proposal_id'])['data']['proposal']['changes']
        changes.append({'op':'retire_record','id':'requirement-a','superseded_by':'requirement-replacement-rule','reason':'The new requirement replaces the original constraint.'})
        updated=self.call('update_proposal',proposal_id=p['proposal_id'],changes=changes,expected_revision=self.revision,expected_proposal_revision=p['proposal_revision'])
        self.assertEqual(updated['data']['validation_status'],'valid')
        self.commit(p['proposal_id'])
        self.assertEqual(load_model(self.root).by_id['requirement-a']['status'],'retired')

    def test_rejected_proposal_cannot_commit_or_reopen(self):
        before=self.service.storage.snapshot();p=self.propose()
        rejected=self.call('reject_proposal',proposal_id=p['proposal_id'],reason='Not needed',expected_proposal_revision=p['proposal_revision'])
        self.assertEqual(rejected['status'],'ok')
        self.assertEqual(before,self.service.storage.snapshot())
        self.assertEqual(self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision)['status'],'error')

    def test_stale_revision_and_explicit_rebase(self):
        first=self.propose('First');second=self.propose('Second')
        self.commit(first['proposal_id'])
        self.assertEqual(self.call('commit_change',proposal_id=second['proposal_id'],expected_revision=self.revision)['findings'][0]['rule'],'revision.conflict')
        current=self.call('get_model_revision')['model_revision']
        old=self.call('get_proposal',proposal_id=second['proposal_id'])['data']
        updated=self.call('update_proposal',proposal_id=second['proposal_id'],changes=old['proposal']['changes'],expected_revision=current,expected_proposal_revision=old['proposal_revision'])
        self.assertEqual(updated['data']['validation_status'],'valid')
        self.revision=current;self.commit(second['proposal_id'])
        self.assertIn('requirement-first',load_model(self.root).by_id)
        self.assertIn('requirement-second',load_model(self.root).by_id)

    def test_material_update_invalidates_approval(self):
        p=self.propose();signature=self.approve(p['proposal_id'])
        old=self.call('get_proposal',proposal_id=p['proposal_id'])['data'];changes=old['proposal']['changes']
        changes[0]['record']['description']='The system shall store something different.'
        updated=self.call('update_proposal',proposal_id=p['proposal_id'],changes=changes,expected_revision=self.revision,expected_proposal_revision=old['proposal_revision'])
        self.assertEqual(updated['data']['state'],'proposed')
        forged=self.call('approve_change',proposal_id=p['proposal_id'],identity='test-reviewer',signature=signature,expected_revision=self.revision)
        self.assertEqual(forged['findings'][0]['rule'],'approval.invalid')

    def test_approval_is_bound_to_identity(self):
        p=self.propose();preview=self.call('preview_change',proposal_id=p['proposal_id'],reviewer='test-reviewer')['data']
        signature=self.sign(preview['approval_payload'])
        r=self.call('approve_change',proposal_id=p['proposal_id'],identity='other-person',signature=signature,expected_revision=self.revision)
        self.assertEqual(r['findings'][0]['rule'],'approval.invalid')

    def test_retries_are_idempotent(self):
        a=self.propose();b=self.propose();self.assertEqual(a['proposal_id'],b['proposal_id'])
        self.commit(a['proposal_id'])
        again=self.call('commit_change',proposal_id=a['proposal_id'],expected_revision=self.revision)
        self.assertTrue(again['data']['already_committed'])

    def test_stale_proposal_edit_is_rejected(self):
        p=self.propose()
        r=self.call('update_proposal',proposal_id=p['proposal_id'],changes=[],expected_revision=self.revision,expected_proposal_revision='old')
        self.assertEqual(r['findings'][0]['rule'],'proposal.conflict')

    def test_write_failure_rolls_back_model_docs_and_approval(self):
        p=self.propose();self.approve(p['proposal_id']);before=self.service.storage.snapshot()
        old_proposal=self.call('get_proposal',proposal_id=p['proposal_id'])['data']
        storage=self.service.storage; original=storage._replace; calls=0
        def fail_once(name,data):
            nonlocal calls
            calls+=1
            if calls==4: raise OSError('injected disk failure')
            original(name,data)
        with patch.object(storage,'_replace',side_effect=fail_once):
            response=self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision)
        self.assertEqual(response['status'],'error')
        self.assertEqual(before,storage.snapshot())
        self.assertEqual(old_proposal,self.call('get_proposal',proposal_id=p['proposal_id'])['data'])
        self.assertFalse((self.root/'.scl/transaction.json').exists())

    def test_crash_journal_recovers_before_next_read(self):
        import base64
        path='knowledge/nodes/domain.json';original=(self.root/path).read_bytes()
        (self.root/'.scl/transaction.json').write_bytes(json_bytes({path:base64.b64encode(original).decode()}))
        (self.root/path).write_text('[]')
        response=ModelService(self.root).execute('get_record',record_id='requirement-a')
        self.assertEqual(response['status'],'ok',response)
        self.assertEqual((self.root/path).read_bytes(),original)

    def test_competing_writer_gets_busy(self):
        with self.service.storage.locked():
            other=ModelService(self.root).execute('get_model_revision')
        self.assertEqual(other['findings'][0]['rule'],'storage.busy')
        self.assertTrue(other['retryable'])

    def test_trusted_ci_accepts_signed_and_rejects_direct_edits(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        p=self.propose();self.commit(p['proposal_id'])
        self.assertEqual(verify_transition(base,self.root,self.verifier),[])
        path=self.root/'knowledge/nodes/domain.json';nodes=json.loads(path.read_text());nodes[0]['description']='Forged direct edit';path.write_bytes(json_bytes(nodes))
        findings=verify_transition(base,self.root,self.verifier)
        self.assertEqual(findings[0].rule,'governance.unsigned')

    def test_untrusted_receipt_cannot_establish_approval(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        p=self.propose();self.commit(p['proposal_id'])
        receipt=next((self.root/'.scl/receipts').glob('*.json'));data=json.loads(receipt.read_text());data['approval']['signature']='forged';receipt.write_bytes(json_bytes(data))
        self.assertEqual(verify_transition(base,self.root,self.verifier)[0].rule,'approval.invalid')

    def test_ci_rejects_tampered_proposal(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        p=self.propose();self.commit(p['proposal_id'])
        path=self.root/self.service.storage.proposal_path(p['proposal_id']);data=json.loads(path.read_text());data['title']='Unreviewed';path.write_bytes(json_bytes(data))
        self.assertEqual(verify_transition(base,self.root,self.verifier)[0].rule,'governance.proposal')

    def test_changed_generated_document_is_rejected(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        (self.root/'TRACEABILITY.md').write_text('forged')
        self.assertEqual(verify_transition(base,self.root,self.verifier)[0].rule,'governance.unsigned')

    def test_trust_configuration_cannot_be_in_checkout(self):
        with patch.dict(os.environ,{'SCL_ALLOWED_SIGNERS':str(self.root/'keys')}):
            with self.assertRaises(ServiceError): verifier_from_environment(self.root)

    def test_pagination_and_context_reuse(self):
        r=self.call('get_context',query='observable',limit=1)['data']
        self.assertEqual(r['projects'][0]['id'],'project-a')
        self.assertEqual(r['related_records']['items'][0]['id'],'outcome-a')
        self.assertEqual(self.call('find_records',limit=101)['findings'][0]['rule'],'query.page')
        trace=self.call('get_trace',record_id='requirement-a')['data']['records']['items']
        self.assertIn('intent-a',{r['id'] for r in trace})
        self.assertIn('requirement-a',self.call('get_dependants',record_id='model-a')['data']['items'])

    def test_malformed_requests_are_structured(self):
        for params in ({'changes':None},{'changes':[None]},{'changes':[{'op':'add_record','record':{}}]}):
            r=self.call('propose_change',title='bad',expected_revision=self.revision,**params)
            self.assertEqual(r['status'],'error',r)
            self.assertEqual(set(r),{'status','model_revision','findings','retryable','data'})

    def test_source_declaration_is_reviewed_with_content(self):
        source=self.root/'evidence.md';source.write_text('# Request\nA reason must be preserved.\n')
        record=requirement();record.update(type='Requirement');record['metadata']['evidence']=['request:evidence.md#Request']
        # Evidence sources enable evidence requirements for every chain record,
        # so use a source-free auxiliary change to test declaration semantics.
        loaded=load_model(self.root)
        changes=[{'op':'declare_source','source':{'alias':'request','path':'evidence.md','ref':'revision-1'}}]
        for n in loaded.nodes:
            if n['type'] in ('Intent','Outcome','Model','Requirement'):
                changes.append({'op':'update_record','id':n['id'],'patch':{'metadata':{'evidence':['request:evidence.md#Request']}}})
        p=self.call('propose_change',title='Capture source',changes=changes,expected_revision=self.revision)['data']
        self.assertEqual(p['validation_status'],'valid',p)
        self.commit(p['proposal_id'])
        self.assertEqual(load_model(self.root).sources[0]['alias'],'request')

    def test_path_escape_and_symlink_rejected(self):
        config=json.loads((self.root/'imk.json').read_text());config['model']='../escape';(self.root/'imk.json').write_bytes(json_bytes(config))
        with self.assertRaises(ServiceError): JsonStorage(self.root)

    def test_legacy_integration_is_disabled(self):
        from scl.slice import integrate_slice
        with self.assertRaises(ServiceError): integrate_slice(self.root,'anything')

    def test_multiple_signed_commits_form_a_verifiable_chain(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        first=self.propose('One');self.commit(first['proposal_id'])
        self.revision=self.call('get_model_revision')['model_revision']
        second=self.propose('Two');self.commit(second['proposal_id'])
        self.assertEqual(verify_transition(base,self.root,self.verifier),[])

    def test_declared_evidence_change_invalidates_review(self):
        p=self.propose();self.approve(p['proposal_id'])
        config=json.loads((self.root/'imk.json').read_text());config['expect']=['missing-record']
        (self.root/'imk.json').write_bytes(json_bytes(config))
        response=self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision)
        self.assertEqual(response['findings'][0]['rule'],'revision.conflict')

    def test_shared_readers_do_not_contend_on_posix(self):
        if os.name=='nt': self.skipTest('Windows uses exclusive locks')
        with self.service.storage.locked(readonly=True):
            response=ModelService(self.root).execute('get_model_revision')
        self.assertEqual(response['status'],'ok',response)

    def test_malformed_line_anchor_returns_findings(self):
        from scl.model import _evidence_finding
        path=self.root/'source.md';path.write_text('a\nb\n')
        finding=_evidence_finding(self.root,{'source':{'path':'source.md'}},'source:source.md#L1-bad','requirement-a')
        self.assertEqual(finding.rule,'ref.evidence')

    def test_api_schema_exposes_exact_parameters(self):
        schema=self.call('get_api_schema',operation='get_record')['data']['input_schema']
        self.assertEqual(schema['required'],['record_id'])
        schema=self.call('get_api_schema',operation='add_requirement')['data']['input_schema']
        self.assertIn('acceptance',schema['properties']['record']['properties']['metadata']['properties'])

    def test_forged_committed_state_is_not_a_successful_retry(self):
        p=self.propose()
        stored=self.service.storage.read_proposal(p['proposal_id']);stored.update(state='committed',committed_revision='forged')
        with self.service.storage.locked():self.service.storage.save_proposal(stored)
        result=self.call('commit_change',proposal_id=p['proposal_id'],expected_revision=self.revision)
        self.assertEqual(result['findings'][0]['rule'],'approval.required')

    def test_candidate_code_is_never_executed_by_trusted_verifier(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        p=self.propose();self.commit(p['proposal_id'])
        (self.root/'sitecustomize.py').write_text('raise RuntimeError("candidate code executed")')
        (self.root/'src').mkdir();(self.root/'src/model.py').write_text('raise RuntimeError("candidate code executed")')
        self.assertEqual(verify_transition(base,self.root,self.verifier),[])

    def test_update_preserves_previous_authorship_history(self):
        p=self.propose();self.commit(p['proposal_id'])
        self.revision=self.call('get_model_revision')['model_revision']
        updated=self.call('update_requirement',record_id='requirement-new-rule',patch={'description':'The system shall retain all Unicode in the reason.'},expected_revision=self.revision)['data']
        self.commit(updated['proposal_id'])
        history=load_model(self.root).by_id['requirement-new-rule']['metadata']['provenance']
        self.assertEqual(len(history),2)
        self.assertEqual(history[0]['original_basis'],'inferred')
        self.assertTrue(history[1]['previous_record_digest'])

    def test_consumer_source_transaction_passes_boundary(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        self.test_source_declaration_is_reviewed_with_content()
        self.assertEqual(verify_transition(base,self.root,self.verifier),[])

    def test_simultaneous_processes_never_lose_a_commit(self):
        from concurrent.futures import ThreadPoolExecutor
        first=self.propose('Parallel one');second=self.propose('Parallel two')
        self.approve(first['proposal_id']);self.approve(second['proposal_id'])
        code="""import json,sys
from pathlib import Path
from scl.service import execute
print(json.dumps(execute(Path(sys.argv[1]),'commit_change',proposal_id=sys.argv[2],expected_revision=sys.argv[3])))
"""
        env={**os.environ,'PYTHONPATH':str(ROOT/'src/tooling'),'SCL_ALLOWED_SIGNERS':str(self.signers)}
        def worker(pid):
            completed=subprocess.run([sys.executable,'-c',code,str(self.root),pid,self.revision],capture_output=True,text=True,env=env,check=True)
            return json.loads(completed.stdout)
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses=list(pool.map(worker,[first['proposal_id'],second['proposal_id']]))
        self.assertEqual(sum(r['status']=='ok' for r in responses),1,responses)
        loser=next(r for r in responses if r['status']=='error')
        self.assertIn(loser['findings'][0]['rule'],{'storage.busy','revision.conflict'})
        ids=load_model(self.root).by_id
        self.assertEqual(sum(rid in ids for rid in ['requirement-parallel-one','requirement-parallel-two']),1)

    def test_evidence_cannot_overwrite_service_outputs(self):
        for path in ['knowledge/nodes/domain.json', 'TRACEABILITY.md', '.scl/lock', 'imk.json']:
            changes=[{'op':'declare_source','source':{'alias':'collision','path':path,'ref':'r1'}}]
            for n in load_model(self.root).nodes:
                if n['type'] in ('Intent','Outcome','Model','Requirement'):
                    # Existing source-free fixture needs valid evidence after declaration.
                    changes.append({'op':'update_record','id':n['id'],'patch':{'metadata':{'evidence':['collision:'+path+'#L1']}}})
            before=self.service.storage.snapshot()
            response=self.call('propose_change',title='Source collision '+path,changes=changes,expected_revision=self.revision)
            self.assertEqual(response['data']['validation_status'],'invalid',response)
            self.assertEqual(before,self.service.storage.snapshot())

    def test_signed_file_map_must_match_reviewed_operations(self):
        base=Path(self.temp.name)/'base';shutil.copytree(self.root,base)
        p=self.propose();self.commit(p['proposal_id'])
        path=self.root/'knowledge/nodes/domain.json';nodes=json.loads(path.read_text());nodes[0]['description']='Unrelated signed edit';path.write_bytes(json_bytes(nodes))
        write_generated(self.root,load_model(self.root))
        receipt_path=next((self.root/'.scl/receipts').glob('*.json'));receipt=json.loads(receipt_path.read_text())
        receipt['payload']['after']=self.service.storage.snapshot()
        receipt['payload']['candidate_revision']=digest(receipt['payload']['after'])
        receipt['approval']['signature']=self.sign(receipt['payload'])
        receipt_path.write_bytes(json_bytes(receipt))
        self.assertEqual(verify_transition(base,self.root,self.verifier)[0].rule,'governance.replay')


if __name__ == '__main__': unittest.main()
