import { Callout, Divider, Grid, H1, H2, Link, Stack, Stat, Table, Text } from "cursor/canvas";

export default function ProductionReadinessAudit() {
  return (
    <Stack gap={16}>
      <H1>RestaurantPro Production Readiness Audit</H1>
      <Text>
        End-to-end review across backend, frontend, and Supabase database. Verdict is based on security,
        data integrity, operational stability, and deployment risk.
      </Text>

      <Grid columns={4} gap={12}>
        <Stat label="Critical Findings" value="2" tone="critical" />
        <Stat label="High Findings" value="2" tone="warning" />
        <Stat label="Medium Findings" value="3" tone="info" />
        <Stat label="Current Verdict" value="NO-GO" tone="critical" />
      </Grid>

      <Callout tone="critical" title="Production Status: Not ready yet">
        Two critical blockers remain: insecure database TLS verification in production and client-side XSS risk
        in dynamic HTML rendering for order/menu flows.
      </Callout>

      <Divider />
      <H2>Top Findings</H2>
      <Table
        headers={["Severity", "Area", "Finding", "Impact", "Recommended Action"]}
        rows={[
          [
            "Critical",
            "Backend / Config",
            "DB SSL verification disabled in production (CERT_NONE, hostname check off).",
            "Possible MITM risk on DB traffic.",
            "Enable certificate validation (CERT_REQUIRED) with trusted Supabase CA.",
          ],
          [
            "Critical",
            "Frontend",
            "User/product fields are inserted via innerHTML without escaping in POS and digital menu.",
            "Stored/reflected XSS in operator and customer flows.",
            "Escape all dynamic values or render through textContent/DOM nodes only.",
          ],
          [
            "High",
            "Backend / Realtime",
            "menu.place_order commits and then emits AppSignal without a following commit.",
            "Realtime updates can be silently lost.",
            "Emit signal before final commit or add explicit commit after emit.",
          ],
          [
            "High",
            "Public API",
            "Digital menu order endpoint is public with only table/global per-minute DB counters.",
            "Abuse/spam possible under distributed traffic.",
            "Add IP/device-aware throttling and bot mitigation at edge/WAF.",
          ],
          [
            "Medium",
            "Ops",
            "No executable automated tests found in runtime (pytest missing).",
            "Higher regression risk at deploy time.",
            "Add smoke/integration test suite and run in CI.",
          ],
          [
            "Medium",
            "Database",
            "One cash session remains open.",
            "Operational/reporting inconsistencies if unintended.",
            "Confirm active shift; close if not intentional.",
          ],
          [
            "Medium",
            "Database Performance",
            "Supabase advisor reports 2 unused indexes.",
            "Minor storage/write overhead.",
            "Review and remove if still unused after observation period.",
          ],
        ]}
        rowTone={["critical", "critical", "warning", "warning", "info", "info", "info"]}
      />

      <Divider />
      <H2>Database Health Checks</H2>
      <Table
        headers={["Check", "Result"]}
        rows={[
          ["Connectivity and query execution", "PASS"],
          ["Schema alignment with SQLAlchemy models", "PASS"],
          ["Critical sequences present (order_number, boleta, factura)", "PASS"],
          ["FK orphan checks (orders/items/payments/invoices/expenses)", "PASS"],
          ["Negative amounts / stock anomalies", "PASS"],
          ["Paid orders without completed payment", "PASS"],
          ["Completed payments without invoice", "PASS"],
          ["RLS enabled and policies present", "PASS (service-role focused)"],
        ]}
      />

      <Divider />
      <H2>Supabase Advisor References</H2>
      <Text>Security advisor: no active lints.</Text>
      <Text>
        Performance advisor flagged unused indexes. Reference:{" "}
        <Link href="https://supabase.com/docs/guides/database/database-linter?lint=0005_unused_index">
          Unused Index Lint
        </Link>
      </Text>

      <Divider />
      <H2>Go-Live Gate</H2>
      <Table
        headers={["Gate", "Status", "Notes"]}
        rows={[
          ["Critical security blockers resolved", "Fail", "SSL + XSS fixes pending."],
          ["Core data integrity", "Pass", "No corruption/orphan anomalies detected."],
          ["Operational readiness", "Partial", "Open session + no automated tests."],
          ["Deployment confidence", "Partial", "Needs final smoke test after fixes."],
        ]}
        rowTone={["critical", "positive", "warning", "warning"]}
      />
    </Stack>
  );
}
