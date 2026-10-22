# Changelog

## 1.2.1 — 2026-10-22

- Rebuild with Python 3.14.9, PySide6 6.12.0, and PyInstaller 6.22.3.
- Record the build and audit dependencies in `requirements-build.txt`.
- Build with a minimal PATH to prevent unrelated tools from supplying incompatible DLLs.
- Refresh the preview and tracked file paths after Apply and Undo.
- Keep Undo available after a repeated Apply with no changes.
- Report locked or missing files and preserve successful operations for Undo
  when a batch stops partway through.
- Retain unfinished Undo operations so they can be retried after a conflict is fixed.
- Refuse Undo if the renamed file has been replaced by another file.
- Recheck destinations immediately before renaming and handle Windows filename
  collisions regardless of case. Existing destination files are not overwritten.
- Block empty titles and reserved Windows destination filenames.
- Ignore directories with video extensions and report folder loading errors.
- Ignore malformed window geometry and directory settings instead of failing at startup.
- Detect episodes after removing release tags, and avoid partial matches inside
  words or long episode numbers. Preserve names that would lose their entire title.
- Remove an unsupported dotted-movie example from the README.
- Add regression tests using temporary files.

This release updates the packaged runtime and dependencies. The source app does
not make network requests; no direct exposure to the recent certificate trust
incident was found in its application logic. Updating dependencies in a source
checkout does not update previously distributed EXEs.
