import { useRef, useState } from "react";
import "../../assets/css/VideoViewer.css";

function VideoViewer() {
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const [currentTime, setCurrentTime] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);

  const fps = 30;
  const currentFrame = Math.floor(currentTime * fps);

  function handleTimeUpdate() {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  }

  function togglePlayback() {
    if (!videoRef.current) {
      return;
    }

    if (videoRef.current.paused) {
      videoRef.current.play();
      setIsPlaying(true);
    } else {
      videoRef.current.pause();
      setIsPlaying(false);
    }
  }

  return (
    <section className="annotation-workspace">
      <div className="top-row">
        <div className="video-panel">
          <video
            ref={videoRef}
            className="video-player"
            onTimeUpdate={handleTimeUpdate}
          >
            <source src="/example.mp4" type="video/mp4" />
          </video>

          <div className="video-controls">
            <button type="button" onClick={togglePlayback}>
              {isPlaying ? "Pause" : "Play"}
            </button>

            <span>{currentTime.toFixed(2)} s</span>
            <span>Frame {currentFrame}</span>
          </div>
        </div>

        <aside className="segments-panel">
          <div className="segments-header">
            <h2>Segments</h2>

            <button type="button">
              + New segment
            </button>
          </div>

          <div className="segment-item">
            <strong>00:00 – 00:12</strong>
            <span>Introduction</span>
          </div>

        </aside>
      </div>

      <div className="timeline">
        Timeline / waveform
      </div>

      <section className="annotation-details">
        <h2>Annotation details</h2>

        <div className="annotation-grid">
          <div className="annotation-left">
            
            <label>
              Segment
              <select>
                <option value="1">Introduction</option>
                </select>
                </label>

            <label>
              Description
              <textarea
                defaultValue="Describe what happens in the segment."
              />
            </label>
          </div>

          <div className="annotation-right">
            <label>
              Summary
              <textarea
                defaultValue="Summarization of the whole video"
              />
            </label>

          </div>
        </div>

        <div className="annotation-actions">
          <button type="button">Save segment</button>
          <button type="button">Mark as complete</button>
          <button type="button">Next</button>
        </div>
      </section>
    </section>
  );
}

export default VideoViewer;