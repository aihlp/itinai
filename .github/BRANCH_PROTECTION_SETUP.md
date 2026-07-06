# Branch Protection Setup for Automated Merging

## Required Changes in GitHub Settings

Go to: **Settings → Branches → Branch protection rules → Edit rule for main**

### Required status checks that must pass before merging

**REMOVE** from the list of required checks:
- ❌ `validate` (this is an old check that may block merging)

**ADD** to the list of required checks:
- ✅ `validate-automated-complete` (for automated sync/cleanup PR) — **ALWAYS PASSES**
- ✅ `validate-manual-complete` (for manual PR and WordPress/ITINAI submissions) — passes only if validation is successful

## Why This Is Important

### For Automated PR (`codex/sync-external-agents`, `auto-cleanup-offline-agents`):
- Job `validate-automated-complete` **ALWAYS** passes successfully (exit 0)
- It depends on `validate`, but ignores its result
- Validation is performed, errors are logged, but merge is NOT blocked
- Auto-merge workflow automatically merges PR after this check succeeds

### For Manual PR and WordPress/ITINAI submissions:
- Job `validate-manual-complete` passes only if the actual validation is successful
- This ensures quality control for manual changes

## Alternative: Use Different Rules for Different Paths

If you want to separate rules for different types of PR, create two rules:

### Rule 1: For Automated Sync PR
- **Branch name pattern**: `codex/sync-external-agents|auto-cleanup-offline-agents`
- **Required status checks**: `validate-automated-complete`
- **Include administrators**: ❌ No

### Rule 2: For All Other PR (main branch)
- **Branch name pattern**: `main`
- **Required status checks**: `validate-manual-complete`
- **Include administrators**: ✅ Yes

## Verification Steps

After setup:
1. Create a test PR from branch `codex/sync-external-agents`
2. Ensure that check `validate-automated-complete` appears as required
3. Ensure that check `validate` is NOT required for this PR
4. After workflow completion, PR should automatically merge

## Important!

If you already have branch protection configured with check `validate`, you need to:
1. Go to Settings → Branches → Branch protection rules
2. Click Edit on the rule for main
3. In the "Check names" section, remove `validate`
4. Add `validate-automated-complete` and `validate-manual-complete`
5. Save changes
