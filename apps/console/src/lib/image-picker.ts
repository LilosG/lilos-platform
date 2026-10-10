import { z } from "zod";
import { ApiFailure, action } from "./api-client";
const assets = z.array(z.object({ path: z.string().min(1), name: z.string() }));
export interface ImageAsset {
  path: string;
  name: string;
}
/** "/blog/2026/" for "/blog/2026/pizza.webp"; the site root for a file in public/. */
export const folderOf = (path: string): string => {
  const cut = path.lastIndexOf("/");
  return cut <= 0 ? "Top level" : path.slice(0, cut + 1);
};
/** Images whose name or folder contains every word typed, in the order the repository lists them. */
export function filterAssets(list: ImageAsset[], query: string): ImageAsset[] {
  const words = query.toLowerCase().split(/\s+/).filter(Boolean);
  return list.filter((a) =>
    words.every((w) => a.path.toLowerCase().includes(w)),
  );
}
const failureText = (error: unknown) =>
  error instanceof ApiFailure &&
  (error.code === "CONTENT_TARGET_NOT_CONFIGURED" || error.code === "HTTP_409")
    ? "This website repository is not connected right now. Check Integrations."
    : "GitHub did not answer, so the images could not be listed.";
/** Wire up the searchable picker inside a publish form; it fills the form's `image` value. */
export function initImagePicker(root: HTMLElement) {
  const form = root.closest("form")!;
  const target = form.querySelector<HTMLSelectElement>("[name=target]")!;
  const value = root.querySelector<HTMLInputElement>("[data-picker-value]")!;
  const search = root.querySelector<HTMLInputElement>("[data-picker-search]")!;
  const list = root.querySelector<HTMLElement>("[data-picker-list]")!;
  const part = (name: string) =>
    root.querySelector<HTMLElement>(`[data-picker-${name}]`)!;
  const manual = root.querySelector<HTMLInputElement>("[data-picker-manual]")!;
  let loaded: ImageAsset[] = [];
  let token = 0;
  const show = (which: "loading" | "empty" | "error" | "list") => {
    for (const name of ["loading", "empty", "error", "list"])
      part(name).hidden = name !== which;
    search.hidden = which !== "list";
  };
  const choose = (path: string, label: string) => {
    value.value = path;
    part("selected").textContent = path ? `Selected: ${label}` : "";
    render();
  };
  function render() {
    const rows = filterAssets(loaded, search.value);
    list.replaceChildren();
    for (const asset of rows) {
      const item = document.createElement("li");
      const pick = document.createElement("button");
      pick.type = "button";
      pick.setAttribute("aria-pressed", String(asset.path === value.value));
      const name = document.createElement("b");
      name.textContent = asset.name;
      const folder = document.createElement("small");
      folder.textContent = folderOf(asset.path);
      pick.append(name, folder);
      pick.addEventListener("click", () => choose(asset.path, asset.name));
      item.append(pick);
      list.append(item);
    }
    part("none").hidden = rows.length > 0 || loaded.length === 0;
  }
  async function load() {
    const mine = ++token;
    value.value = "";
    part("selected").textContent = "";
    search.value = "";
    show("loading");
    try {
      const url = `${root.dataset.assetsUrl}?target_id=${encodeURIComponent(target.value)}`;
      const result = assets.parse(await action(url, {}, "GET"));
      if (mine !== token) return;
      loaded = result;
      if (!loaded.length) return show("empty");
      render();
      show("list");
    } catch (error) {
      if (mine !== token) return;
      part("error-text").textContent = failureText(error);
      show("error");
    }
  }
  search.addEventListener("input", render);
  target.addEventListener("change", load);
  part("retry").addEventListener("click", load);
  part("toggle").addEventListener("click", () => {
    const typing = part("manualbox").hidden;
    part("manualbox").hidden = !typing;
    part("browse").hidden = typing;
    part("toggle").textContent = typing
      ? "Choose from the repository instead"
      : "Enter a path instead";
    if (typing) {
      value.value = manual.value;
      manual.focus();
    } else void load();
  });
  manual.addEventListener("input", () => (value.value = manual.value.trim()));
  void load();
}
