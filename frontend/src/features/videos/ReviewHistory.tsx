export type ReviewEvent = {
  id: string;
  version: number;
  action: string;
  actor_id: string | null;
  actor_name: string;
  comment: string;
  created_at: string;
};

export default function ReviewHistory({ events }: { events: ReviewEvent[] }) {
  if (!events.length) return null;
  return <section className="review-history" aria-label="Review history">
    <h2>Review history</h2>
    <ol>{events.map((event) => <li key={event.id}>
      <strong>{event.action[0].toUpperCase() + event.action.slice(1)}</strong>
      {` · ${event.actor_name} · ${new Date(event.created_at).toLocaleString()}`}
      {event.comment && <p style={{ whiteSpace: "pre-wrap", overflowWrap: "anywhere" }}>{event.comment}</p>}
    </li>)}</ol>
  </section>;
}
