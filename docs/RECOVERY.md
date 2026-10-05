# Recoverable artifacts, not just a scheduled copy

Dublin encrypts a `pg_dump` custom-format snapshot, fitted model, model card,
Compose/configuration files and existing secret files with age **before** upload.
Plaintext staging is root-only and temporary. Upload uses a separate receive-only
SSH key constrained to the current Dublin source IP, command and pinned host key.
The receiver accepts bounded ciphertext filenames and cannot extract or overwrite.

Frankfurt stores encrypted files in `/home/ubuntu/eventdesk-backups/`. The age
identity stays root-only at `/etc/eventdesk-backup/identity.txt`; private key values
are never copied into this repository. Dublin retains local encrypted snapshots.
No old bot journals or Fly Brain files are included or changed.

## Verification

`python ops/verify_backup.py` checks ciphertext and every archived-file hash on
Frankfurt, then streams only the database dump through the existing authenticated
SSH sessions into a newly created disposable Dublin database. It probes schema
and record counts, then removes only that test database. It never restores over
the production database. The public aggregate is `reports/backup-restore.json`.

The archive model's hash is verified against the deployed artifact. No untrusted
joblib artifact is loaded on the backup host. There is no raw secret-file output.

## Production recovery procedure

1. Read the latest verified backup receipt and check its ciphertext hash.
2. On Frankfurt, decrypt under a root-only temporary directory using the existing
   age identity. Check every regular member against `manifest.json`; reject links,
   duplicate names, absolute paths and parent traversal.
3. Restore into a new database first. Check Alembic schema, evidence and expected
   records; verify the fitted model/configuration hashes before changing routing.
4. Install the existing environment files root-owned mode 600, mount the verified
   model read-only, deploy reviewed source and migrate to the recorded schema.
5. Check receiver/worker health, immutable pending payloads and public HTTPS before
   resuming traffic. Public API acceptance alone is not scoring eligibility.

An isolated restore drill does not establish a measured full-host recovery time.
The decryption identity still depends on Frankfurt: loss of both hosts is not
covered by an offline recovery copy. No automated destructive production restore
is provided, and nightly copies are not deleted by a guessed retention policy.
