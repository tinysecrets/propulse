#!/usr/bin/env bash
set -euo pipefail
REPO="${1:-tinysecrets/propulse}"

gh api -X PATCH "repos/$REPO" \
  -f allow_squash_merge=true -f allow_merge_commit=false -f allow_rebase_merge=false \
  -f squash_merge_commit_title=PR_TITLE -f squash_merge_commit_message=PR_BODY \
  -f delete_branch_on_merge=true -f allow_auto_merge=true -f allow_update_branch=true \
  -f has_wiki=false -f has_projects=false -F has_discussions=true

gh api -X PUT "repos/$REPO/branches/main/protection" --input - <<'JSON'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["ci-required", "security"]
  },
  "enforce_admins": true,
  "required_pull_request_reviews": {
    "required_approving_review_count": 1,
    "require_code_owner_reviews": true,
    "dismiss_stale_reviews": true,
    "require_last_push_approval": true
  },
  "restrictions": null,
  "required_linear_history": true,
  "allow_force_pushes": false,
  "allow_deletions": false,
  "required_conversation_resolution": true
}
JSON

gh api -X POST "repos/$REPO/rulesets" --input - <<'JSON'
{
  "name": "merge-queue",
  "target": "branch",
  "enforcement": "active",
  "conditions": { "ref_name": { "include": ["refs/heads/main"], "exclude": [] } },
  "rules": [
    { "type": "merge_queue", "parameters": {
        "merge_method": "SQUASH", "grouping_strategy": "ALLGREEN",
        "max_entries_to_build": 5, "max_entries_to_merge": 5,
        "min_entries_to_merge": 1, "min_entries_to_merge_wait_minutes": 5,
        "check_response_timeout_minutes": 60 } },
    { "type": "required_signatures" },
    { "type": "non_fast_forward" }
  ]
}
JSON

gh api -X PATCH "repos/$REPO" \
  -F 'security_and_analysis.secret_scanning.status=enabled' \
  -F 'security_and_analysis.secret_scanning_push_protection.status=enabled' \
  -F 'security_and_analysis.dependabot_security_updates.status=enabled'

gh api -X PUT "repos/$REPO/private-vulnerability-reporting"
gh api -X PATCH "repos/$REPO/actions/permissions/workflow" \
  -f default_workflow_permissions=read \
  -F can_approve_pull_request_reviews=true

echo "repo $REPO hardened."
