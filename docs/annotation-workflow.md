# Annotation access, saving, and synchronization

Annotators can list and open assigned videos only. Administrators and reviewers
can access video media; annotation text endpoints return only the current user's
records. The separate [submission and review workflow](review-workflow.md) gives
reviewers and administrators read-only access to submitted revisions.
Uploads and video deletion require an administrator.

Browser playback uses `POST /api/videos/{id}/media-token` with bearer authentication.
The returned token expires in five minutes, is restricted to that video's media
endpoints, and cannot authenticate annotation writes. Every media request checks
the user's current account state and assignment. The frontend refreshes it every
four minutes. Keep these credential-bearing URLs private.

Segment and summary responses include `version`. Send that version on updates;
new summaries use version zero. Segment deletion takes `?version=...`.
Stale updates/deletes return 409. Preserve the current draft, reload the latest
record, and reconcile edits before saving again. The workspace warns when leaving
unsaved work and disables segment fields while saving.

`GET /api/videos/{id}/annotation-session` returns saved segments, summary, and
assignment status. `POST .../annotation-session/complete` requires at least one
segment, both descriptions on every segment, and a nonblank whole-video summary.
For silent segments, describe the absence of audible content. Editing or deleting
saved work resets completion. Completion is not submission or reviewer approval.
Submitted and approved work cannot be edited through the annotation APIs.
Returned work remains returned while edits are saved, until it is resubmitted.

Segment intervals are half-open: start is inclusive, end exclusive. Frame N,
where N is the frame count, denotes the end of the video. Timestamp edits and
timeline drags snap to the nearest stored boundary; ties choose the earlier one.
The final boundary uses the timestamp map's estimated last-frame duration.
New saves persist both frames and timestamps. Existing segments are normalized
when loaded if their timing artifact is available. Legacy ranges shorter than a
frame, or with missing timing, retain their text and must be corrected/reprocessed
before saving. Frame timing must be ready before creating or updating segments.

Uploads generate a stored waveform artifact alongside thumbnails and timing.
Older videos generate their waveform on first request. No-audio videos show an
explicit empty state. Failed waveform generation returns an actionable error.
Waveform navigation and video playback share the same playhead, and both timeline
and waveform display the selected segment.

Verification includes backend access/scope, version-conflict, completion, VFR
boundary tests and the Docker browser workflow for playback, waveform seeking,
segment dragging, saved text, navigation warnings, and saving-state controls.
