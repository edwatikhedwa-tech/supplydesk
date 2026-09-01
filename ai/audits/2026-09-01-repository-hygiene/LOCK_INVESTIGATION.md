# Lock investigation

Status: PASS — the missing `mail-data\\supplier.sqlite3.live-mail.lock` is not a missing data file.

## Finding

| Field | Evidence-based result |
|---|---|
| Path | `mail-data\\supplier.sqlite3.live-mail.lock` |
| Owner process | PID `16704`, `python.exe`, correlated with `runtime/canonical_manifest.json` and the process listening on `127.0.0.1:8000` |
| Created/managed by | `mail/runtime.py`, class `LiveMailLock` (`acquire`/`release`), called by `RuntimeSession.start`; application shutdown calls `RuntimeSession.close` |
| Purpose | Exclusive OS byte-range lock and informational JSON metadata for the live canonical runtime |
| Data category | `LOCAL_RUNTIME`, not application data, source code, configuration, or database journal |
| Classification | `EPHEMERAL_RUNTIME` |
| Restore required | `NO` |
| Snapshot treatment | `INTENTIONALLY_EXCLUDED` |

## Code evidence

- `mail/runtime.py:89-130` opens or creates the path, acquires the exclusive OS lock, and writes runtime metadata.
- `mail/runtime.py:132-146` releases the OS lock and closes the handle; it does not treat the file as a durable data store.
- `mail/runtime.py:214-220` creates the marker only after the canonical database check passes.
- `mail/runtime.py:298-305` requires ownership of the live lock for production outgoing-mail permission; this is a runtime safety gate, not persisted business state.
- `mail/runtime.py:460-465` releases the lock during normal session close.
- `supplier_app.py:1253-1258` starts the runtime session; `supplier_app.py:2515` closes it in the application shutdown path.

## Behaviour proof

An isolated temporary file was exercised with the same `LiveMailLock` implementation: first acquisition succeeded, the file existed while held, release succeeded, the file still existed as a marker, and a second acquisition succeeded. The test reported `restoration_relevant_data=false`. This demonstrates that the lock state is the OS handle, not the file bytes.

The source lock could not be read or copied while PID 16704 held it. A privileged backup copy was not available (`robocopy /B` returned exit 16 because the required Windows privilege was unavailable). No process was stopped merely to copy the marker.

## Restore conclusion

On startup, the application recreates the path if needed and reacquires the OS lock. Preserving a stale marker would not preserve the live lock ownership and could be less useful than recreating it. The source `runtime/canonical_manifest.json` records the current owner and confirms that the marker is held by the live runtime.

Therefore, the one-file physical difference is explained and intentional. It is not a failed critical file and does not keep the snapshot blocked.

## Limits

Exact Windows kernel handle enumeration was not performed: `handle.exe` was unavailable and `openfiles.exe` was not used to interrupt or alter the process. Ownership is established by process inspection plus the application’s canonical runtime manifest and code path.
