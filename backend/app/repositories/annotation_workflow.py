"""Shared assignment lock used by annotation writes and workflow transitions."""
from fastapi import HTTPException

LOCKED_STATES = {"submitted", "approved"}


def lock_assignment(connection, video_id, author_id):
    return connection.execute(
        "SELECT * FROM video_assignments WHERE video_id = %s AND user_id = %s FOR UPDATE",
        (str(video_id), str(author_id)),
    ).fetchone()


def require_editable(connection, video_id, author_id):
    assignment = lock_assignment(connection, video_id, author_id)
    if assignment and assignment["status"] in LOCKED_STATES:
        raise HTTPException(409, "Submitted or approved annotations are read-only. A reviewer must return submitted work before editing.")
    return assignment


def review_history(connection, assignment_id):
    return connection.execute("""
        SELECT id, version, action, actor_id, actor_name, comment, created_at
        FROM annotation_review_events WHERE assignment_id = %s ORDER BY version
    """, (str(assignment_id),)).fetchall()
