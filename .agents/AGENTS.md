# Workspace Rules

## Testing Policy
- **Prefer scope-limited testing during development**: When modifying code and validating changes, do NOT run the entire test suite if it is large.
- **Use `pytest-picked` first**: Prioritize running tests only on files that have changed (modified but not yet committed in Git) by using the `--picked` flag:
  ```bash
  pytest --picked
  ```
- **Fallback**: If no changed files are detected or if `--picked` doesn't find any relevant tests, fall back to running the specific test module or function associated with the file you modified. Only run the full test suite if explicitly requested or if it's a small suite.
