export type AnnotationStatus = "not_started" | "in_progress" | "completed";

export interface Assignment {
  video_id: string;
  title: string;
  original_filename: string;
  duration_seconds: number | null;
  protocol_group: "shared" | "individual";
  status: AnnotationStatus;
  segment_count: number;
  assigned_at: string;
  updated_at: string;
}
