export function errorMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string" && detail.trim()) return detail;
  if (!Array.isArray(detail)) return fallback;

  const messages: string[] = [];
  for (const issue of detail) {
    if (typeof issue?.msg !== "string") continue;
    const field = Array.isArray(issue.loc) ? issue.loc.at(-1) : undefined;
    messages.push(typeof field === "string" ? `${field}: ${issue.msg}` : issue.msg);
  }
  return messages.join(" ") || fallback;
}
