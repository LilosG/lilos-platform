/** Google's limits for a Business Profile photo, checked in the browser before anything is sent.
 * The API checks the same limits again from the bytes; these only save a round trip. */
export const MIN_BYTES = 10 * 1024;
export const MAX_BYTES = 5 * 1024 * 1024;
export const MIN_SIDE = 250;
export type PhotoProblem =
  | "MEDIA_TYPE_UNSUPPORTED"
  | "MEDIA_TOO_SMALL"
  | "MEDIA_TOO_LARGE"
  | "MEDIA_DIMENSIONS_TOO_SMALL";
/** One sentence per typed problem, whether it was found here or answered by the API. */
export const photoProblemText: Record<PhotoProblem, string> = {
  MEDIA_TYPE_UNSUPPORTED: "Use a JPG or PNG image.",
  MEDIA_TOO_SMALL: "That file is under 10 KB. Choose a larger photo.",
  MEDIA_TOO_LARGE: "That file is over 5 MB. Choose a smaller photo.",
  MEDIA_DIMENSIONS_TOO_SMALL:
    "That photo is smaller than 250 × 250 pixels. Choose a larger one.",
};
const TYPES = ["image/jpeg", "image/png"];
/** The file's own type and size; null when it is acceptable so far. */
export function checkPhotoFile(file: {
  type: string;
  size: number;
}): PhotoProblem | null {
  if (file.size > MAX_BYTES) return "MEDIA_TOO_LARGE";
  if (!TYPES.includes(file.type)) return "MEDIA_TYPE_UNSUPPORTED";
  if (file.size < MIN_BYTES) return "MEDIA_TOO_SMALL";
  return null;
}
export const checkPhotoDimensions = (
  width: number,
  height: number,
): PhotoProblem | null =>
  width < MIN_SIDE || height < MIN_SIDE ? "MEDIA_DIMENSIONS_TOO_SMALL" : null;
/** "340 KB" or "1.2 MB": a size a person reads. */
export const sizeText = (bytes: number): string =>
  bytes >= 1024 * 1024
    ? `${(bytes / (1024 * 1024)).toFixed(1)} MB`
    : `${Math.max(1, Math.round(bytes / 1024))} KB`;
