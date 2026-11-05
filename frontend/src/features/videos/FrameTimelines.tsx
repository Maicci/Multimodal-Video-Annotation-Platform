// This component creates a visual video timeline that displays thumbnail images and can be scrubbed with the mouse.
// This timeline can be used in segment creation in the future

import { useRef, useState } from "react";
import "../../assets/css/FrameTimeline.css";

type Props = {
  videoId: number;
  currentTime: number;
  duration: number;
  onTimeChange: (time: number) => void;
};

function FrameTimeline({
  videoId,
  currentTime,
  duration,
  onTimeChange,
}: Props) {
  const timelineRef = useRef<HTMLDivElement | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const API_URL = import.meta.env.VITE_API_URL;
  const thumbnailAmount = 12;
  const thumbnails = [];

  if (duration > 0) {
    for (let i = 0; i < thumbnailAmount; i++) {
      const time = (i / thumbnailAmount) * duration;

      thumbnails.push({
        number: Math.floor(time) + 1,
        time: time,
      });
    }
  }

  function updateTime(clientX: number) {
    if (!timelineRef.current || duration <= 0) {
      return;
    }

    const rect = timelineRef.current.getBoundingClientRect();

    let position = clientX - rect.left;

    // Keep position inside timeline
    position = Math.max(0, Math.min(position, rect.width));

    const percentage = position / rect.width;
    const time = percentage * duration;

    onTimeChange(time);
  }

  function handlePointerDown(
    event: React.PointerEvent<HTMLDivElement>
  ) {
    setIsDragging(true);

    event.currentTarget.setPointerCapture(event.pointerId);

    updateTime(event.clientX);
  }

  function handlePointerMove(
    event: React.PointerEvent<HTMLDivElement>
  ) {
    if (!isDragging) {
      return;
    }

    updateTime(event.clientX);
  }

  function handlePointerUp(
    event: React.PointerEvent<HTMLDivElement>
  ) {
    setIsDragging(false);

    event.currentTarget.releasePointerCapture(event.pointerId);
  }

  const playheadPosition =
    duration > 0 ? (currentTime / duration) * 100 : 0;

  return (
    <div
      className="frame-timeline"
      ref={timelineRef}
      onPointerDown={handlePointerDown}
      onPointerMove={handlePointerMove}
      onPointerUp={handlePointerUp}
    >
      <div className="thumbnail-strip">
        {thumbnails.map((thumbnail) => (
          <img
            src={`${API_URL}/api/videos/${videoId}/thumbnails/${thumbnail.number}`}
            alt=""
            draggable={false}
          />
        ))}
      </div>

      <div
        className="timeline-playhead"
        style={{ left: `${playheadPosition}%` }}
      />
    </div>
  );
}

export default FrameTimeline;
