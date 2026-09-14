"""Patch only four DCT Code nodes; preserve all other live configuration."""
import copy
import json
import subprocess
import deploy_dct_email_actions as d


def main():
    api = d.N8nApi(d.load_key())
    changes = {
        d.MAIN_WORKFLOW_ID: {'Build Ads Upload': d.BUILD_ADS_UPLOAD_JS,
                            'Parse Ads Upload': d.PARSE_ADS_UPLOAD_JS},
        'Gd8fvkAJjC4rJuJy': {'Decide DCT Action': d.DECIDE_EVENT_JS,
                           'Prepare DCT Retraction': d.PREPARE_RETRACTION_JS},
    }
    for replacements in changes.values():
        for code in replacements.values():
            subprocess.run(['node', '--check'], input='function run(){\n'+code+'\n}',
                           text=True, capture_output=True, check=True)
    for workflow_id, replacements in changes.items():
        live = api.call('GET', '/workflows/' + workflow_id)
        assert live.get('active'), 'Refusing to change inactive workflow'
        candidate = copy.deepcopy(live)
        matched = set()
        for node in candidate['nodes']:
            if node['name'] in replacements:
                node['parameters']['jsCode'] = replacements[node['name']].strip() + '\n'
                matched.add(node['name'])
        assert matched == set(replacements)
        backup = d.BACKUP_DIR / ('dct-routing-before-' + workflow_id + '-' + d.stamp() + '.json')
        d.write_json(backup, live)
        backup.chmod(0o600)
        fresh = api.call('GET', '/workflows/' + workflow_id)
        assert fresh['versionId'] == live['versionId'], 'Workflow changed during preparation'
        payload = d.writable_workflow(candidate)
        if 'staticData' in candidate:
            payload['staticData'] = candidate['staticData']
        api.call('PUT', '/workflows/' + workflow_id, payload)
        api.call('POST', '/workflows/' + workflow_id + '/activate')
        verified = api.call('GET', '/workflows/' + workflow_id)
        assert verified.get('active')
        for node in verified['nodes']:
            if node['name'] in replacements:
                assert node['parameters']['jsCode'].strip() == replacements[node['name']].strip()
        print(json.dumps({'workflow': workflow_id, 'verified_nodes': sorted(matched),
                          'version': verified.get('versionId'), 'active_version': verified.get('activeVersionId')}))


if __name__ == '__main__':
    main()
