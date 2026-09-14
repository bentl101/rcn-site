"""Exercise production Code-node snippets using Node, with synthetic input only."""
import json
import subprocess
import unittest
import deploy_dct_email_actions as d


def run(code, item, upstream=None):
    js = 'const item=' + json.dumps(item) + '; const upstream=' + json.dumps(upstream or {}) + ';'
    js += 'const $json=item; const $input={first:()=>({json:item})}; const $=name=>({first:()=>({json:upstream[name]})});'
    js += 'console.log(JSON.stringify((function(){' + code + '})()));'
    return json.loads(subprocess.check_output(['node', '-e', js], text=True))


class RoutingTests(unittest.TestCase):
    def lead(self, **fields):
        return {'lead_order_id': 'DCT-TEST-ROUTING', 'submitted_at': '2026-09-13T12:00:00Z', **fields}

    def test_gclid_wins_and_queues_for_every_mixed_bundle(self):
        for extras in ({}, {'gbraid': 'privacy'}, {'wbraid': 'privacy'}, {'gbraid': 'one', 'wbraid': 'two'}):
            out = run(d.BUILD_ADS_UPLOAD_JS, self.lead(gclid='click', **extras))[0]['json']
            cv = out['google_ads_request']['conversions'][0]
            self.assertEqual(out['ads_action_id'], '7762251563')
            self.assertTrue(out['queue_data_manager'])
            self.assertEqual(cv['gclid'], 'click')
            self.assertNotIn('gbraid', cv); self.assertNotIn('wbraid', cv)
            self.assertNotIn('userIdentifiers', cv)

    def test_privacy_only_routes_remain_supported(self):
        for key in ('gbraid', 'wbraid'):
            out = run(d.BUILD_ADS_UPLOAD_JS, self.lead(**{key: 'privacy'}))[0]['json']
            self.assertEqual(out['ads_action_id'], '7748270854')
            self.assertFalse(out['queue_data_manager'])
            self.assertEqual(out['google_ads_request']['conversions'][0][key], 'privacy')

    def test_qa_and_empty_attribution_do_not_upload(self):
        for lead in (self.lead(), self.lead(gclid='click', is_qa=True)):
            self.assertEqual(run(d.BUILD_ADS_UPLOAD_JS, lead), [])

    def test_empty_result_is_failure(self):
        out = run(d.PARSE_ADS_UPLOAD_JS, {'results': [{}]}, {'Build Ads Upload': {'ads_route': 'braid'}})
        self.assertFalse(out[0]['json']['ads_upload_accepted'])

    def test_bad_lead_preserves_historical_action(self):
        for action, stop_queue in (('7748270854', False), ('7762251563', True), ('7748271517', False)):
            row = self.lead(gclid='click', gbraid='privacy', action_token_hash='a'*64,
                            ads_conversion_action='customers/3639225242/conversionActions/'+action)
            event = {'lead_order_id': row['lead_order_id'], 'requested_action': 'bad', 'token_hash': 'a'*64}
            out = run(d.DECIDE_EVENT_JS, row, {'Pick Next DCT Action': event})[0]['json']
            self.assertEqual(out['ads_conversion_action'], row['ads_conversion_action'])
            self.assertEqual(out['_disable_data_manager'], stop_queue)


if __name__ == '__main__':
    unittest.main()
