"""Repeatable A-F usability scenarios; fixture signatures are NOT human approval."""
import json
from pathlib import Path
import sys

sys.path[:0]=[str(Path(__file__).parent),str(Path(__file__).resolve().parents[1]/'src/tooling')]
from test_service import ServiceTests, requirement, rel


class Scenario(ServiceTests):
    def call(self, operation_name, **params):
        response=super().call(operation_name,**params)
        self.operations.append({'operation':operation_name,'response_bytes':len(json.dumps(response,ensure_ascii=False).encode()),'status':response['status']})
        return response


def evaluate():
    Scenario.setUpClass()
    reports=[]
    try:
        for label,description in [
            ('A','Add a Requirement under a known Model'),
            ('B','Add an interaction, participants and constraints together'),
            ('C','Discover and reuse an existing Intent/Outcome chain'),
            ('D','Correct an illegal relationship from structured findings'),
            ('E','Rebase after a competing revision commits'),
            ('F','Block unauthenticated inferred integration')]:
            fixture=Scenario();fixture.operations=[];fixture.setUp()
            try:
                if label=='A':
                    p=fixture.propose();fixture.commit(p['proposal_id'])
                elif label=='B':
                    fixture.test_complete_multi_record_interaction()
                elif label=='C':
                    found=fixture.call('find_records',type='Outcome',query='observable',limit=1)
                    outcome=found['data']['items'][0]['id']
                    trace=fixture.call('get_trace',record_id=outcome,limit=5)
                    assert 'intent-a' in {n['id'] for n in trace['data']['records']['items']}
                    p=fixture.call('add_requirement',record=requirement('Reuse chain'),parent_id='model-a',expected_revision=fixture.revision)['data']
                    fixture.commit(p['proposal_id'])
                elif label=='D': fixture.test_invalid_change_can_be_corrected()
                elif label=='E': fixture.test_stale_revision_and_explicit_rebase()
                else: fixture.test_self_declared_approval_and_human_origin_grant_nothing()
                reports.append({'scenario':label,'description':description,'passed':True,
                    'operations':len(fixture.operations),'response_bytes':sum(x['response_bytes'] for x in fixture.operations),
                    'max_response_bytes':max(x['response_bytes'] for x in fixture.operations),
                    'direct_file_knowledge_required':False,'calls':fixture.operations})
            finally:fixture.tearDown()
    finally:Scenario.tearDownClass()
    return reports


if __name__=='__main__':
    print(json.dumps(evaluate(),indent=2))
