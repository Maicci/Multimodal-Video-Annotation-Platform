from typing import Any
from uuid import UUID

from app.db.database import Database

LIST_FOR_USER = """
SELECT v.id            AS video_id,
       v.title,
       v.original_filename,
       v.duration_seconds,
       v.protocol_group,
       CASE
           WHEN a.status IN ('completed', 'submitted', 'returned', 'approved', 'skipped') THEN a.status
           WHEN s.n > 0 OR EXISTS (SELECT 1 FROM video_summaries vs WHERE vs.video_id = a.video_id AND vs.author_id = a.user_id AND trim(vs.summary) <> '') THEN 'in_progress'
           ELSE 'not_started'
       END             AS status,
       a.assigned_at,
       a.updated_at,
       s.n             AS segment_count
  FROM video_assignments a
  JOIN videos v ON v.id = a.video_id
  CROSS JOIN LATERAL (
        SELECT count(*) AS n
          FROM segments sg
         WHERE sg.video_id = a.video_id
           AND sg.author_id = a.user_id
  ) s
 WHERE a.user_id = %(user_id)s
 ORDER BY (a.status = 'completed'), v.protocol_group, v.title
"""

CREATE_ASSIGNMENT = """
INSERT INTO video_assignments (
    video_id,
    user_id
)
VALUES (
    %(video_id)s,
    %(user_id)s
)
RETURNING video_id, user_id, status, assigned_at, updated_at
"""


class AssignmentRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def list_for_user(self, user_id: UUID) -> list[dict[str, Any]]:
        with self.database.connect() as connection:
            return connection.execute(LIST_FOR_USER, {"user_id": user_id}).fetchall()
        
        
    def create(
        self,
        video_id: UUID,
        user_id: UUID,
    ) -> dict[str, Any]:
        with self.database.connect() as connection:
            return connection.execute(
                CREATE_ASSIGNMENT,
                {
                    "video_id": video_id,
                    "user_id": user_id,
                },
            ).fetchone()
