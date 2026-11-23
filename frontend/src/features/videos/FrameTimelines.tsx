import { useEffect, useRef } from "react";
import "../../assets/css/FrameTimeline.css";

type Selection = { start: number; end: number };
type DragTarget = "scrub" | "start" | "end";

type Props = {
  videoId: string;
  mediaToken: string;
  currentTime: number;
  duration: number;
  selection: Selection | null;
  onTimeChange: (time: number) => void;
  onSelectionChange: (start: number, end: number) => void;
};

const API_URL = import.meta.env.VITE_API_URL || "";
const THUMBNAIL_COUNT = 12;

function FrameTimeline({
  videoId, mediaToken, currentTime, duration, selection, onTimeChange, onSelectionChange,
}: Props) {
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const dragTarget = useRef<DragTarget | null>(null);
  const selectionRef = useRef(selection);

  useEffect(() => {
    selectionRef.current = selection;
  }, [selection]);

  function setBoundary(target: "start" | "end", value: number) {
    const current = selectionRef.current;
    if (!current || duration <= 0) return;
    const gap = Math.min(0.01, duration);
    const time = Math.min(duration, Math.round(Math.max(0, Math.min(value, duration)) * 100) / 100);
    const next = target === "start"
      ? { start: Math.min(time, current.end - gap), end: current.end }
      : { start: current.start, end: Math.max(time, current.start + gap) };
    selectionRef.current = next;
    onSelectionChange(next.start, next.end);
    onTimeChange(target === "start" ? next.start : next.end);
  }

  function updateFromPointer(clientX: number) {
    const rect = timelineRef.current?.getBoundingClientRect();
    if (!rect || rect.width <= 0 || duration <= 0) return;
    const fraction = Math.max(0, Math.min((clientX - rect.left) / rect.width, 1));
    const time = fraction * duration;
    if (dragTarget.current === "start" || dragTarget.current === "end") {
      setBoundary(dragTarget.current, time);
    } else {
      onTimeChange(time);
    }
  }

  function handlePointerDown(event: React.PointerEvent<HTMLDivElement>) {
    if (duration <= 0) return;
    const handle = event.target instanceof HTMLElement
      ? event.target.closest<HTMLElement>("[data-handle]")?.dataset.handle
      : undefined;
    dragTarget.current = handle === "start" || handle === "end" ? handle : "scrub";
    event.currentTarget.setPointerCapture(event.pointerId);
    updateFromPointer(event.clientX);
  }

  function handlePointerMove(event: React.PointerEvent<HTMLDivElement>) {
    if (dragTarget.current) updateFromPointer(event.clientX);
  }

  function stopDragging(event: React.PointerEvent<HTMLDivElement>) {
    dragTarget.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function handleBoundaryKey(event: React.KeyboardEvent<HTMLButtonElement>, target: "start" | "end") {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    const current = selectionRef.current;
    if (!current) return;
    const step = event.shiftKey ? 1 : 0.1;
    const change = event.key === "ArrowRight" ? step : -step;
    setBoundary(target, (target === "start" ? current.start : current.end) + change);
  }

  const position = (time: number) =>
    duration > 0 ? Math.max(0, Math.min((time / duration) * 100, 100)) : 0;
  const visibleSelection = selection && selection.end > selection.start && duration > 0
    ? selection : null;

  return (
    <div
      className="frame-timeline"
      ref={timelineRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={stopDragging}
      onPointerCancel={stopDragging}
    >
      <div className="thumbnail-strip">
        {duration > 0 && mediaToken && Array.from({ length: THUMBNAIL_COUNT }, (_, index) => (
          <img
            key={index + 1}
            src={`${API_URL}/api/videos/${videoId}/thumbnails/${index + 1}?media_token=${encodeURIComponent(mediaToken)}`}
            alt=""
            draggable={false}
          />
        ))}
      </div>
      {visibleSelection && (
        <>
          <div
            className="timeline-selection"
            style={{ left: `${position(visibleSelection.start)}%`, width: `${position(visibleSelection.end) - position(visibleSelection.start)}%` }}
          />
          <button
            type="button"
            className="selection-handle start-handle"
            data-handle="start"
            style={{ left: `${position(visibleSelection.start)}%`, transform: visibleSelection.start <= 0 ? "translateX(0)" : "translateX(-50%)" }}
            aria-label={`Segment start ${visibleSelection.start.toFixed(2)} seconds. Drag or use arrow keys.`}
            onKeyDown={(event) => handleBoundaryKey(event, "start")}
            title="Drag to set segment start"
          >S</button>
          <button
            type="button"
            className="selection-handle end-handle"
            data-handle="end"
            style={{ left: `${position(visibleSelection.end)}%`, transform: visibleSelection.end >= duration ? "translateX(-100%)" : "translateX(-50%)" }}
            aria-label={`Segment end ${visibleSelection.end.toFixed(2)} seconds. Drag or use arrow keys.`}
            onKeyDown={(event) => handleBoundaryKey(event, "end")}
            title="Drag to set segment end"
          >E</button>
        </>
      )}
      <div className="timeline-playhead" style={{ left: `${position(currentTime)}%` }} />
    </div>
  );
}

export default FrameTimeline;
