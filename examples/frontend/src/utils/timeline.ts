export function frameToSeconds(frame: number, framesPerSecond: number): number {
  if (framesPerSecond <= 0) {
    throw new RangeError("framesPerSecond must be greater than zero");
  }
  return frame / framesPerSecond;
}
