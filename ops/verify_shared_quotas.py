"""Read only project quota/import metadata from the existing shared PostgreSQL ledger."""
from __future__ import annotations

import json
import shlex
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from bootstrap import SSH

REMOTE = '''
import json,os
from sqlalchemy import func,select,text
from sqlalchemy.orm import Session
from eventdesk.quota_transfer import QuotaImport
from eventdesk.quotas import ProviderState,ProviderUsage
from eventdesk.store import Store
store=Store(os.environ['DATABASE_URL'])
with Session(store.engine) as session,session.begin():
 session.execute(text('SET TRANSACTION READ ONLY'))
 imports=[{'ledger_id':r.ledger_id,'snapshot_sha256':r.snapshot_sha256,'usage_rows':r.usage_rows}
          for r in session.scalars(select(QuotaImport))]
 counts=[{'provider':name,'usage_rows':count} for name,count in session.execute(
    select(ProviderUsage.provider,func.count()).group_by(ProviderUsage.provider))]
 imported=session.scalar(select(func.count()).select_from(ProviderUsage).where(
    ProviderUsage.status=='sealed_research_import'))
print(json.dumps({'imports':imports,'provider_project_counts':counts,'sealed_usage_rows':imported,
                 'external_requests':0,'mode':'read_only'}))
'''


def main() -> None:
    command = ["sudo", "docker", "exec", "eventdesk-worker-1", "python", "-c", REMOTE]
    result = subprocess.run(SSH+[shlex.join(command)], capture_output=True)
    if result.returncode:
        raise RuntimeError("Shared ledger verification failed; database details withheld")
    record = json.loads(result.stdout)
    record["checked_at"] = datetime.now(UTC).isoformat()
    record["limits"] = "Actual project ledger/import metadata; not provider-wide capacity or billing usage"
    Path("reports/shared-quota-dublin.json").write_text(json.dumps(record, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(record))


if __name__ == "__main__":
    main()
