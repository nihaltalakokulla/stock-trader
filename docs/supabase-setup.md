# Supabase setup

1. Create a free Supabase project and open the SQL editor.
2. Run `supabase/migrations/0001_init.sql`.
3. In Project Settings -> API, copy the project URL and the `service_role`
   key into GitHub Actions secrets (`SUPABASE_URL`, `SUPABASE_SERVICE_KEY`).
4. Copy the URL and the `anon` key into `dashboard/config.local.js`.
5. The engine and Worker use the service key (RLS bypass); the dashboard uses
   the anonymous key and can only read the four `dashboard_*` views.

## Approval notification path

Supabase Database Webhooks send a fixed event payload that does not match
GitHub's `repository_dispatch` body, so the Worker calls the GitHub Actions
workflow-dispatch API directly after inserting the approval row. Add these
Worker secrets/variables:

- `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`
- `TWILIO_AUTH_TOKEN`, `ALLOWED_PHONE`
- `GITHUB_DISPATCH_TOKEN` (fine-grained token with Actions: write on this repo)
- `GITHUB_OWNER`, `GITHUB_REPO`, `GITHUB_REF` (branch the executor runs from)

The executor workflow accepts an `approval_key` input. The Worker passes the
approval's idempotency key so the run is traceable and safe to retry.

## Row-level security checks

After applying the migration, verify with the anon key:

```bash
curl "$SUPABASE_URL/rest/v1/dashboard_positions" \
  -H "apikey: $SUPABASE_ANON_KEY" \
  -H "Authorization: Bearer $SUPABASE_ANON_KEY"
```

A POST to `proposals` with the anon key must be rejected.
