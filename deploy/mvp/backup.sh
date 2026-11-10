#!/bin/sh
# Daily backup to S3 (cron: 15 3 * * * /opt/sdtreasury/deploy/mvp/backup.sh).
# Needs the AWS CLI and an instance role allowed to write to the bucket.
set -eu
BUCKET="${SDT_BACKUP_BUCKET:?set SDT_BACKUP_BUCKET}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
pg_dump --format=custom --no-owner "${SDT_BACKUP_DATABASE_URL:?set SDT_BACKUP_DATABASE_URL}" \
  | aws s3 cp - "s3://${BUCKET}/sdtreasury/${STAMP}.dump" --storage-class STANDARD_IA
