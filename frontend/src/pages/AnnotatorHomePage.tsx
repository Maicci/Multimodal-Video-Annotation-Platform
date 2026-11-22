import AssignmentList from "../features/assignments/AssignmentList";

interface Props {
  token: string;
  onOpenVideo: (videoId: string) => void;
  onSignOut: () => void;
}

export default function AnnotatorHomePage({ token, onOpenVideo, onSignOut }: Props) {
  return (
    <main>
      <button type="button" onClick={onSignOut}>Sign out</button>
      <AssignmentList token={token} onOpenVideo={onOpenVideo} />
    </main>
  );
}
