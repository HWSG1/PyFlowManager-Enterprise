import unittest
import tempfile
from pathlib import Path
from unittest.mock import patch
from datetime import date
from zoneinfo import ZoneInfo
import GNS_Reporte_Inbound_Diario as report


class ReportTests(unittest.TestCase):
    def test_send_payload_has_excel_and_inline_logo(self):
        with tempfile.TemporaryDirectory() as folder:
            excel = Path(folder) / 'inbound.xlsx'
            excel.write_bytes(b'PK-test-workbook')
            with patch.dict(report.os.environ, {'GRAPH_TENANT_ID':'test','GRAPH_CLIENT_ID':'test','GRAPH_CLIENT_SECRET':'test','GRAPH_SENDER_EMAIL':'sender@example.com'}):
                with patch.object(report, 'request_json', side_effect=[{'access_token':'test'}, {}]) as request:
                    report.send_report('<img src="cid:atlantida-logo">', ['manual@example.com'], [], date(2026,10,28), excel, b'chart-test')
            payload = request.call_args_list[1].args[1]
            attachments = payload['message']['attachments']
            self.assertEqual(attachments[0]['name'], 'inbound.xlsx')
            self.assertFalse(attachments[0]['isInline'])
            self.assertEqual(report.base64.b64decode(attachments[0]['contentBytes']), b'PK-test-workbook')
            self.assertEqual(attachments[1]['contentId'], 'atlantida-logo')
            self.assertTrue(attachments[1]['isInline'])
            self.assertEqual(attachments[2]['contentId'], 'inbound-daily-chart')
            self.assertEqual(report.base64.b64decode(attachments[2]['contentBytes']), b'chart-test')

    def test_chart_and_section_order_with_no_activity(self):
        daily = [['2026-10-01',0,0,0,'','','']]
        self.assertTrue(report.daily_chart(daily).startswith(b'\x89PNG'))
        html = report.render_report(date(2026,10,1),date(2026,10,1),'America/Tegucigalpa',daily,[],report.empty_stats())
        titles = ['Resumen acumulado del periodo','Acumulado por cola','Volumen y abandono diario','Detalle diario']
        positions = [html.index(title) for title in titles]
        self.assertEqual(positions, sorted(positions))

    def test_queue_selector_json_and_legacy_ids(self):
        self.assertEqual(report.selected_queue_ids('[{"id":"q1","name":"Atencion, BDA"},{"id":"q2","name":"AOL"}]'), ["q1", "q2"])
        self.assertEqual(report.selected_queue_ids("q1;q2;q1"), ["q1", "q2"])
        self.assertEqual(report.selected_queue_ids(""), [])
        self.assertEqual(report.selected_queue_ids("[]"), [])
        with self.assertRaises(ValueError):
            report.selected_queue_ids('[{"name":"Sin ID"}]')

    def test_first_day_reports_previous_month(self):
        self.assertEqual(report.period(date(2026, 11, 1)), (date(2026, 10, 1), date(2026, 10, 31)))

    def test_future_and_partial_day_rejected(self):
        with self.assertRaises(ValueError):
            report.period(date(2026, 10, 30), "2026-10-30")

    def test_local_interval_and_filters(self):
        body = report.query_body(date(2026, 10, 29), ZoneInfo("America/Tegucigalpa"), ["q1"])
        self.assertEqual(body["interval"], "2026-10-29T00:00:00-06:00/2026-10-30T00:00:00-06:00")
        self.assertEqual(body["filter"]["predicates"][0]["value"], "voice")
        self.assertEqual(body["filter"]["predicates"][1]["value"], "inbound")

    def test_weighted_metrics_and_zero(self):
        first = report.empty_stats()
        first["tAnswered"] = {"count": 1, "sum": 10000}
        second = report.empty_stats()
        second["tAnswered"] = {"count": 9, "sum": 180000}
        report.add_stats(first, second)
        self.assertEqual(report.row_values("total", first)[5], 19)
        self.assertEqual(report.row_values("empty", report.empty_stats())[4:], ["", "", ""])

    def test_queue_names_html_escaped(self):
        self.assertNotIn("<script>", report.html_table([["<script>", 0, 0, 0, "", "", ""]], "Cola"))


if __name__ == "__main__":
    unittest.main()
