"""Regression coverage for recovered uploads and live credential health (no I/O)."""
import importlib.util
import pathlib
import unittest
from datetime import date
from unittest.mock import mock_open, patch

ROOT = pathlib.Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('report', ROOT / 'rcn_report.py')
report = importlib.util.module_from_spec(spec)
with patch('builtins.open', mock_open(read_data='')):
    spec.loader.exec_module(report)

OID = 'RCN-20260912-113012-241b6731'
DAY = date(2026, 9, 12)


def node(value):
    return [{'data': {'main': [[{'json': value}]]}}]


def execution(upload=None, click_type='gclid'):
    body = {'lead_order_id': OID, 'submitted_at': '2026-09-12 11:30:13',
            'decision': 'send_to_sales', 'click_id_type': click_type,
            'click_id': 'test-click', 'email': 'test@example.test', 'phone': '4161234567'}
    rd = {'Build Signals': node({'body': body, '_features': {'phone_valid_veriphone': True}}),
          'Parse Score': node({'body': body}),
          'Get Google OAuth Token': [{'error': {'message': 'invalid_grant'}}]}
    if upload is not None:
        rd['Upload Click Conversion'] = node(upload)
    return {'id': 'test', 'startedAt': '2026-09-12T11:30:13Z',
            'data': {'resultData': {'runData': rd}}}


def ledger(action='7627192972', outcome='accepted', status='complete'):
    return {OID: {'status': status, 'lastOutcome': outcome,
                  'action': f'customers/5306933986/conversionActions/{action}'}}


class RecoveryTests(unittest.TestCase):
    def counts(self, executions, orders):
        return report.lead_breakdown(executions, DAY, DAY, recovery_orders=orders)[0]

    def test_recovery_supersedes_failed_original(self):
        e = execution({'partialFailureError': {'message': 'failed'}, 'results': [{}]})
        counts = self.counts([e], ledger())
        self.assertEqual((counts['good_uploaded'], counts['good_rejected']), (1, 0))

    def test_recovery_does_not_double_count_same_person(self):
        self.assertEqual(self.counts([execution(), execution({'results': [{'gclid': 'test'}]})], ledger())['good_uploaded'], 1)

    def test_wrong_action_and_terminal_failure_do_not_count(self):
        for orders in (ledger(action='7663805249'), ledger(outcome='permanent', status='terminal')):
            self.assertEqual(self.counts([execution()], orders)['good_uploaded'], 0)

    def test_braid_recovery_uses_braid_action(self):
        self.assertEqual(self.counts([execution(click_type='gbraid')], ledger(action='7663805249', outcome='duplicate'))['good_uploaded'], 1)

    def test_empty_results_are_not_accepted(self):
        self.assertEqual(self.counts([execution({'results': [{}]})], {})['good_uploaded'], 0)

    def test_resolved_oauth_is_not_pending(self):
        self.assertEqual(report.unresolved_oauth_orders([execution()], ledger(), '2026-09-12'), [])
        self.assertEqual(report.unresolved_oauth_orders([execution()], {}, '2026-09-12'), [OID])

    def test_live_probe_never_returns_access_token(self):
        with patch.object(report.subprocess, 'run') as run:
            run.return_value.stdout = '{"ok":true,"status":200,"error":null}'
            self.assertEqual(report.current_n8n_token_health(), {'ok': True, 'status': 200, 'error': None})
            self.assertIn('docker', run.call_args.args[0])

    def test_health_preview_recovery_and_current_failure(self):
        for current, expected_healthy in (({'ok': True}, True), ({'ok': False, 'error': 'invalid_grant'}, False)):
            with patch.multiple(report, ads_token=lambda: 'test', ads_search=lambda *a: [],
                                n8n_execs=lambda *a: [execution()] if not a else [],
                                n8n_workflow=lambda *a: {}, retry_orders=ledger,
                                ads_conv_by_action=lambda *a: {}, ads_metrics=lambda *a: {'cost': 1},
                                current_n8n_token_health=lambda: current), \
                 patch.object(report, 'send_email') as email, patch('builtins.print') as output:
                report.run_health(DAY, preview=True)
                import json
                result = json.loads(output.call_args_list[0].args[0])
                self.assertEqual(result['healthy'], expected_healthy)
                email.assert_not_called()


if __name__ == '__main__':
    unittest.main()
