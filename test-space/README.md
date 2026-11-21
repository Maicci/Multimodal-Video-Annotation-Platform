# Local test space

This Docker Compose setup runs the current frontend and backend with a private
PostgreSQL database and video storage. It uses test credentials and binds web
ports to your own computer only. Do not use it for real data or deployment.

## Start

1. Start Docker Desktop.
2. From the repository root, run:

   ```powershell
   docker compose -f test-space/compose.yaml up --build
   ```

3. Open the frontend at http://127.0.0.1:5173 and the API documentation at
   http://127.0.0.1:8000/docs. The API health check is at
   http://127.0.0.1:8000/api/health.

The test administrator is `admin@example.com` with password
`test-password-123`. Source edits are mounted into the containers, and the
frontend and backend reload when files change.

To stop, press Ctrl+C, then run
`docker compose -f test-space/compose.yaml down`. To erase only this test
space's database and uploaded videos, run
`docker compose -f test-space/compose.yaml down -v`.

In the frontend, sign in, upload an MP4 or MOV, then select **View** from the
video list. The player and annotation controls are still a prototype; the API
documentation exposes the backend endpoints for more direct testing.

After a backend schema change, restart the backend with
`docker compose -f test-space/compose.yaml restart backend`. A video that already
shows `FAILED` will not be processed again automatically; delete that test
upload and upload it again. The list refreshes every few seconds, and **View**
becomes available after processing reaches `COMPLETED`.

To test annotation saving, open a completed video, choose **+ New segment**,
enter a title, time range, and description, then choose **Save segment**. Go
back to the video list and reopen the video; the saved segment should appear.
To remove one, select it and choose **Delete segment**.
While creating or editing a segment, drag the blue and orange bars on the
thumbnail timeline to set its start and end. The time inputs stay in sync.

After rebuilding the backend image, run the segment API test with
`docker compose -f test-space/compose.yaml exec backend python -m pytest backend/tests/api/test_segments_api.py`.
Run the frontend type check and production build with
`docker compose -f test-space/compose.yaml exec frontend npm run build`.

To run the full browser workflow in a fresh Playwright container, use
`docker compose -f test-space/compose.yaml --profile e2e up --build --abort-on-container-exit --exit-code-from e2e e2e`.
It generates a small test video, uploads it, checks playback and thumbnails,
then creates, edits, reloads, and deletes a segment. The command stops the
Compose services when the test finishes; restart the app with
`docker compose -f test-space/compose.yaml up -d` if you want to keep testing.
