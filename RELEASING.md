# Releasing Script Manager

Script Manager uses one application version source:

```text
core/version.py -> APP_VERSION
```

Git tags and Windows release assets must match that value exactly.

## Version strategy before 1.0

- **Patch** (`0.x.Y`): bug fixes, hardening, documentation, packaging fixes, or behavior-preserving refactors.
- **Minor** (`0.X.0`): operator-visible features, meaningful workflow changes, or database/schema evolution that remains migration-safe.
- **1.0.0**: only after the Phase 9 release-readiness checklist is complete and representative user-acceptance workflow has passed.

## Release procedure

1. Make sure Engine Tests, Qt Runtime, and Windows Package are green on the intended commit.
2. Update `APP_VERSION` in `core/version.py`.
3. Run the full test suite again and merge through the normal PR flow.
4. Create and push tag `v<APP_VERSION>`.
5. The Release workflow validates that tag and `APP_VERSION` match.
6. The workflow builds and smoke-tests:
   - portable Windows ZIP;
   - per-user Windows installer;
   - `.smproj` file association.
7. The workflow generates SHA-256 checksums and creates the GitHub Release.
8. Verify Help → Check for Updates against the published release before considering the release complete.

Do not create a release tag from an unmerged feature branch.
