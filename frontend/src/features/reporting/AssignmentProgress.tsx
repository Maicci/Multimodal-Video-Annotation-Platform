import { useEffect, useState } from "react";
import { STATUS_LABEL, type AnnotationStatus } from "../../types/assignment";

type Dimension = "video" | "annotator";
type ProgressCount = { dimension: Dimension; id: string; name: string; status: AnnotationStatus; total: number };

export default function AssignmentProgress() {
  const [counts, setCounts] = useState<ProgressCount[]>([]);
  const [dimension, setDimension] = useState<Dimension>("video");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setError("");
      try {
        const response = await fetch(`${import.meta.env.VITE_API_URL || ""}/api/assignments/progress`, {
          headers: { Authorization: `Bearer ${localStorage.getItem("access_token")}` },
          signal: controller.signal,
        });
        if (!response.ok) throw new Error(`Could not load progress (${response.status}).`);
        const data: ProgressCount[] = await response.json();
        if (!controller.signal.aborted) setCounts(data);
      } catch (cause) {
        if (!controller.signal.aborted) setError(cause instanceof Error ? cause.message : "Could not load progress.");
      } finally {
        if (!controller.signal.aborted) setLoading(false);
      }
    }
    void load();
    return () => controller.abort();
  }, [refresh]);

  const rows = new Map<string, { name: string; assigned: number; statuses: Partial<Record<AnnotationStatus, number>> }>();
  for (const count of counts) {
    if (count.dimension !== dimension) continue;
    const row = rows.get(count.id) ?? { name: count.name, assigned: 0, statuses: {} };
    row.assigned += count.total;
    row.statuses[count.status] = count.total;
    rows.set(count.id, row);
  }

  return <section className="admin-section progress-report">
    <div className="section-header"><h1>Assignment progress</h1></div>
    <div className="progress-controls">
      <label>Group by <select value={dimension} onChange={(event) => setDimension(event.target.value as Dimension)}>
        <option value="video">Video</option><option value="annotator">Annotator</option>
      </select></label>
      <button type="button" disabled={loading} onClick={() => setRefresh(refresh + 1)}>Refresh progress</button>
    </div>
    {loading && <p role="status">Loading progress…</p>}
    {error && <p role="alert">{error}</p>}
    {!loading && !error && (rows.size === 0 ? <p>No videos assigned yet.</p> :
      <div className="video-table-wrapper"><table className="video-table" aria-label={`Progress by ${dimension}`}>
        <thead><tr><th scope="col">{dimension === "video" ? "Video" : "Annotator"}</th><th scope="col">Assigned</th>
          {Object.entries(STATUS_LABEL).map(([key, label]) => <th scope="col" key={key}>{label}</th>)}
        </tr></thead>
        <tbody>{Array.from(rows, ([id, row]) => <tr key={id}>
          <th scope="row">{row.name}</th><td>{row.assigned}</td>
          {(Object.keys(STATUS_LABEL) as AnnotationStatus[]).map((status) => <td key={status}>{row.statuses[status] ?? 0}</td>)}
        </tr>)}</tbody>
      </table></div>)}
  </section>;
}
