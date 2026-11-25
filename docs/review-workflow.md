# Annotation submission and review - issue #29

Implemented on `codex/annotation-submission-review`, 2026-11-25.

Annotators submit a saved revision of their assigned video annotation. A reviewer
or administrator can inspect that revision, approve it, or return it with a
comment. Reviewers cannot edit the submitted text. Approval is final in this
iteration; there is no reopen-approved or withdraw-submission action.

## States and transitions

The existing `not_started`, `in_progress`, and `completed` states remain valid.
`completed` records an annotator's own progress; it does not send work for review.
Marking complete is optional before submitting.

| Current state | Action | Next state |
| --- | --- | --- |
| Not started / in progress / completed | Annotator submits complete saved work | Submitted |
| Submitted | Reviewer approves (optional comment) | Approved |
| Submitted | Reviewer returns with a nonblank comment | Returned |
| Returned | Annotator saves edits | Returned |
| Returned | Annotator resubmits complete saved work | Submitted |
| Not started / in progress / completed / returned | Annotator skips, with optional reason | Skipped |
| Skipped | Annotator saves an edit | In progress |

Submission requires at least one segment, nonblank video and audio descriptions
on every segment, and a nonblank whole-video summary. Video processing and frame
timing must be ready; submitted frame/time boundaries are validated. Empty,
duplicate, unauthorized and invalid-state requests are rejected.

Submitted and approved segments and summaries are read-only in both the UI and
API. Creation, updates, deletion and the old Mark complete endpoint cannot bypass
the lock. Returned annotations are editable. Skipping keeps saved work; save an
edit to resume before submitting again.

## Persistence and consistency

`video_assignments.workflow_version` increments on submission, resubmission,
return, approval and skipping. Clients send the version they observed with every
workflow action. Stale versions receive HTTP 409 and must refresh.

`annotation_review_events` stores the action, version, actor ID and display name,
comment, and timestamp. Submission/resubmission events additionally contain a
JSON snapshot of segments, frame/time boundaries, descriptions and summary.
Reviewers read the latest submitted snapshot, including while the annotator is
revising returned work; they never read a changing draft through the review API.
Earlier events and snapshots remain stored after resubmission. The history UI
shows all actions and comments, while the review view displays the latest
submitted revision.

Annotation writes, submission and decisions lock the same assignment row before
reading/changing its state. This prevents a save from changing a revision while
it is being submitted and prevents a second reviewer from overwriting a decision.
Reviewers and administrators cannot approve or return their own authored work,
including after a role change. All active reviewers/administrators can see the
review queue; individual reviewer allocation is not part of this issue.

Initialization adds the new states and event table without changing existing
assignments or annotations. State and history persist in PostgreSQL across app
restarts. Existing administrative deletion semantics still apply: deleting a
video/assignment removes its dependent review records. This is workflow history,
not an independent archival store.

## API

All routes require the usual bearer authentication. Workflow action bodies:

```json
{"expected_version": 1, "comment": "Please clarify the audible speech."}
```

The comment is optional except when returning work. Comments are trimmed and
limited to 10,000 characters. Actions return `status`, `workflow_version`, and
`review_history`.

| Endpoint | Access / purpose |
| --- | --- |
| `GET /api/videos/{video_id}/annotation-session` | Existing video access; own status, workflow version and review history alongside own annotations |
| `POST /api/videos/{video_id}/annotation-session/submit` | Assigned annotator submits saved work |
| `POST /api/videos/{video_id}/annotation-session/resubmit` | Assigned annotator resubmits returned work |
| `POST /api/videos/{video_id}/annotation-session/skip` | Assigned annotator skips editable work |
| `GET /api/reviews` | Reviewer/administrator queue of submitted, returned and approved assignments; submitted first |
| `GET /api/reviews/{assignment_id}` | Reviewer/administrator reads the latest submitted snapshot and history |
| `POST /api/reviews/{assignment_id}/approve` | Reviewer/administrator approves submitted work |
| `POST /api/reviews/{assignment_id}/return` | Reviewer/administrator returns submitted work with feedback |

401 means missing/invalid authentication; 403 unauthorized role/access or
self-review; 404 missing review/submitted snapshot; 409 stale or invalid workflow
transition; 422 incomplete content, invalid boundaries, or missing return comment.

## Verification

- Backend: 36 tests passed, 1 optional Whisper smoke test skipped.
- Chromium: all 7 browser workflows passed, including the existing Sprint 2 checks.
- Firefox: the new submission/review workflow passed.
- Frontend lint, TypeScript and production build passed.

`backend/tests/api/test_annotation_reviews.py` checks incomplete submissions,
edit locks in submitted/approved states, permission failures, self-review after
a role change, stale decisions, skip/resume, immutable submitted revisions,
return/edit/resubmit/approve, and a fresh application startup over the same
database with the approved state/history intact.

`tests/e2e/review-workflow.spec.ts` uses separate annotator and reviewer browser
sessions with real upload, assignment and media endpoints. It verifies skip and
resume, save-before-submit controls, read-only submitted work, required feedback,
return, editing, resubmission, approval, refresh persistence and review history.
An approved-review screenshot is saved in the browser report.

Run using the existing Docker test environment:

```powershell
docker compose -f test-space/compose.yaml restart backend frontend
docker compose -f test-space/compose.yaml exec -T -w /workspace/backend backend pytest -q
docker compose -f test-space/compose.yaml --profile e2e run --rm --build --no-deps e2e
docker compose -f test-space/compose.yaml --profile e2e run --rm --no-deps -e E2E_BROWSER=firefox e2e npx playwright test --config=tests/e2e/playwright.config.ts review-workflow.spec.ts
```

Review queues update when opened or manually refreshed. Annotators should
refresh after a reviewer decision. The administrator's **Assignment progress**
view reports each state by video or annotator. The browser test also checks
these counts and compares two submitted revisions after one author edits a
returned draft.
