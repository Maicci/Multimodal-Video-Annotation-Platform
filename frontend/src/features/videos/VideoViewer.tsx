// Component for streaming a video, tracking playback time and frame,
// ...and controlling playback through the interactive frame timeline.

import { useRef, useState } from "react";
import "../../assets/css/VideoViewer.css";
import FrameTimeline from "./FrameTimelines";

// videoId is a number that identifies a specific video to be annotated
type Props = {
  videoId: number;
};

function VideoViewer({ videoId }: Props) {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentFrame, setCurrentFrame] = useState(0);
  // The API URL is defined in the .env file
  const API_URL = import.meta.env.VITE_API_URL;

  async function handleTimeUpdate() {
    if (!videoRef.current) {
      return;
    }

    const time = videoRef.current.currentTime;

    setCurrentTime(time);

    const response = await fetch(
      `${API_URL}/api/videos/${videoId}/frame?time=${time}`
    );

    const data = await response.json();

    setCurrentFrame(data.frame);
  }

  function handleLoadedMetadata() {
    if (!videoRef.current) {
      return;
    }

    setDuration(videoRef.current.duration);
  }

  function handleTimelineChange(time: number) {
    if (!videoRef.current) {
      return;
    }

    videoRef.current.currentTime = time;
    setCurrentTime(time);
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
            onLoadedMetadata={handleLoadedMetadata}
          >
            <source
              src={`${API_URL}/api/videos/${videoId}/stream`}
              type="video/mp4"
            />
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

      <FrameTimeline
        videoId={videoId}
        currentTime={currentTime}
        duration={duration}
        onTimeChange={handleTimelineChange}
      />

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