# Project review — 2026-10-22

Reviewed the local application source, README behavior claims, settings,
drag-and-drop and folder input, filename processing, Apply/Undo, dependencies,
and the rebuilt Windows executable. The original application source was compared
with GitHub `main` at commit `6ae3754` before preparing the release commit.

## Findings addressed in 1.2.1

| Finding | Result |
| --- | --- |
| Distributed builds bundle their own runtime; installing Python alone cannot patch them | Rebuilt using Python 3.14.9, PySide6 6.12.0, and PyInstaller 6.22.3; recorded dependency versions |
| Build collected an incompatible ICU DLL from unrelated tools on PATH | Added `build.ps1` with a minimal build PATH and verified the final archive excludes the unrelated runtime libraries |
| Apply retained obsolete source paths | Track new paths and refresh the preview after Apply and Undo |
| A repeated Apply discarded Undo history | Retain history when no new rename succeeds |
| File errors interrupted batches without recovery feedback | Stop with an error message and retain completed operations for Undo |
| Undo could discard unresolved operations | Keep unfinished history for retry, including missing-file and destination-conflict cases |
| Undo could move a replacement file | Compare the file's filesystem identity before restoring its old name |
| Conflict checks used stale, case-sensitive preview data | Refresh before Apply, compare normalized Windows paths, and check destinations before each operation |
| Invalid Windows targets and empty titles could be generated | Highlight invalid targets; preserve an episode-only name if cleanup would remove its title |
| Release tags could provide the wrong episode number | Remove selected metadata before episode detection and tighten token boundaries |
| Repeated drag-and-drop paths and video-like directory names entered batches | Deduplicate dropped paths and limit folder batches to files |
| Corrupt geometry or directory settings could break startup | Validate their types before use |
| README promised unsupported removal of dotted years/resolutions | Remove the incorrect example and test all remaining examples |

## Validation

- 22 regression tests passed using temporary files; no user video library used.
- Tests cover byte preservation, Apply/Undo paths, partial failures and retries,
  file replacement, files created after preview and during rename, Windows case
  collisions/reserved names, folder errors, settings, Delete, dropped URLs, and
  naming examples.
- Bandit reported no findings in application source, with no disabled checks.
- `pip check` reported no broken requirements.
- `pip-audit` reported no known vulnerabilities in the installed environment.
- Build/archive and packaged startup results are recorded in
  `dist/build-info.json` after verification of the final EXE.

## Security scope and remaining limits

The application does not execute filenames, launch shell commands, deserialize
Python objects, extract archives, decode video content, or intentionally make
network requests. The recent certificate incident primarily affects download
tooling for this project. The environment uses updated pip and certifi.

Official references:

- [Python 3.14.9 security release](https://www.python.org/downloads/release/python-3149/)
- [Certificate trust incident](https://discuss.python.org/t/information-for-python-users-regarding-emudhra-emsign-ca-certificate-security-incident/109576)
- [PyInstaller privilege-escalation advisory, fixed in 6.22.1](https://github.com/pyinstaller/pyinstaller/security/advisories/GHSA-9fxf-4qw3-ghmr)

These checks are not a guarantee that all vulnerabilities are absent. pip-audit
checks published Python-package advisories; it is not a full vulnerability scan
of every bundled native Qt/Windows library. The app is intended and tested for
Windows. Its no-overwrite behavior relies on Windows `os.rename` semantics.
File-identity checks reduce accidental Undo mistakes but are not a security
boundary against a process actively racing filesystem changes.

Batches are not transactions: a failure can leave a partially renamed batch.
Undo is stored in memory for the latest successful batch and is lost when the
app closes. Settings remain portable in an INI beside the script/EXE, so saving
preferences requires a writable app folder. Multi-episode and ambiguous naming
formats still require inspecting the preview. Release binaries and their build
information are distributed separately from the source.
