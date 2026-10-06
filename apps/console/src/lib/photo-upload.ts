import { ApiFailure, failureText, upload } from "./api-client";
import {
  checkPhotoDimensions,
  checkPhotoFile,
  photoProblemText,
  sizeText,
} from "./photo-check";
const root = document.querySelector<HTMLElement>("[data-gbp]");
const org = root?.dataset.org ?? "";
const location = root?.dataset.location ?? "";
const profile = root?.dataset.profile ?? "";
const dialog =
  root?.querySelector<HTMLDialogElement>('dialog[data-gbp-dialog="photo"]') ??
  document.querySelector<HTMLDialogElement>('dialog[data-gbp-dialog="photo"]');
const form = dialog?.querySelector<HTMLFormElement>("form");
if (dialog && form) {
  const input = form.querySelector<HTMLInputElement>("[data-photo-input]")!;
  const drop = form.querySelector<HTMLElement>("[data-photo-drop]")!;
  const chosen = form.querySelector<HTMLElement>("[data-photo-chosen]")!;
  const preview = form.querySelector<HTMLImageElement>("[data-photo-preview]")!;
  const facts = form.querySelector<HTMLElement>("[data-photo-facts]")!;
  const clear = form.querySelector<HTMLButtonElement>("[data-photo-clear]")!;
  const message = form.querySelector<HTMLElement>("[data-form-status]")!;
  const bar = form.querySelector<HTMLElement>("[data-upload-progress]")!;
  const fill = bar.querySelector<HTMLElement>("i")!;
  const submit = form.querySelector<HTMLButtonElement>(
    'button[type="submit"]',
  )!;
  let current: { file: File; key: string } | null = null;
  let objectUrl = "";
  const reset = () => {
    current = null;
    if (objectUrl) URL.revokeObjectURL(objectUrl);
    objectUrl = "";
    preview.removeAttribute("src");
    chosen.hidden = true;
    drop.hidden = false;
    bar.hidden = true;
    input.value = "";
    submit.disabled = true;
  };
  const refuse = (code: keyof typeof photoProblemText) => {
    reset();
    message.textContent = photoProblemText[code];
  };
  async function choose(file: File | undefined) {
    message.textContent = "";
    if (!file) return;
    const problem = checkPhotoFile(file);
    if (problem) return refuse(problem);
    const url = URL.createObjectURL(file);
    const size = await new Promise<{ w: number; h: number } | null>(
      (resolve) => {
        const image = new Image();
        image.onload = () =>
          resolve({ w: image.naturalWidth, h: image.naturalHeight });
        image.onerror = () => resolve(null);
        image.src = url;
      },
    );
    if (!size) {
      URL.revokeObjectURL(url);
      return refuse("MEDIA_TYPE_UNSUPPORTED");
    }
    const tooSmall = checkPhotoDimensions(size.w, size.h);
    if (tooSmall) {
      URL.revokeObjectURL(url);
      return refuse(tooSmall);
    }
    reset();
    objectUrl = url;
    current = { file, key: crypto.randomUUID() };
    preview.src = url;
    facts.textContent = `${file.type === "image/png" ? "PNG" : "JPG"} · ${size.w} × ${size.h} px · ${sizeText(file.size)}`;
    chosen.hidden = false;
    drop.hidden = true;
    submit.disabled = false;
  }
  input.addEventListener("change", () => void choose(input.files?.[0]));
  clear.addEventListener("click", () => {
    reset();
    message.textContent = "";
    input.focus();
  });
  for (const name of ["dragenter", "dragover"])
    drop.addEventListener(name, (event) => {
      event.preventDefault();
      drop.classList.add("dragging");
    });
  for (const name of ["dragleave", "drop"])
    drop.addEventListener(name, () => drop.classList.remove("dragging"));
  drop.addEventListener("drop", (event) => {
    event.preventDefault();
    void choose(event.dataTransfer?.files[0]);
  });
  dialog.addEventListener("close", () => {
    reset();
    message.textContent = "";
  });
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    message.textContent = "";
    const rights = String(new FormData(form).get("rights_authority") ?? "");
    if (!current) {
      message.textContent = "Choose a photo first.";
      return;
    }
    if (!rights) {
      message.textContent = "Say who may use this photo.";
      return;
    }
    const body = new FormData();
    body.set("file", current.file);
    body.set("media_type", String(new FormData(form).get("media_type")));
    body.set("rights_authority", rights);
    body.set("idempotency_key", current.key);
    submit.disabled = true;
    bar.hidden = false;
    fill.style.width = "0%";
    try {
      await upload(
        `/api/organizations/${org}/locations/${location}/gbp/operations/locations/${profile}/media/`,
        body,
        (fraction) => {
          const percent = Math.round(fraction * 100);
          fill.style.width = `${percent}%`;
          bar.setAttribute("aria-valuenow", String(percent));
        },
      );
      window.location.reload();
    } catch (error) {
      bar.hidden = true;
      message.textContent = failureText(
        error instanceof ApiFailure ? error : new ApiFailure("UPLOAD_FAILED"),
      );
      submit.disabled = false;
    }
  });
}
