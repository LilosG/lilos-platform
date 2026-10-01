export type SampleValue = string | number | boolean;
type Changes = Record<string, Record<string, SampleValue>>;
const storageKey = "lilos-revision-10-sample-session";
function isChanges(value: unknown): value is Changes {
  if (typeof value !== "object" || value === null || Array.isArray(value))
    return false;
  return Object.entries(value).every(
    ([key, fields]) =>
      /^(client|action|opportunity|page|review|automation|report|lead|task|activity):[\w-]+$/.test(
        key,
      ) &&
      typeof fields === "object" &&
      fields !== null &&
      !Array.isArray(fields) &&
      Object.entries(fields).every(
        ([field, val]) =>
          /^[a-zA-Z]\w*$/.test(field) &&
          ["string", "number", "boolean"].includes(typeof val),
      ),
  );
}
export function createSampleSession() {
  let changes: Changes = {};
  try {
    const saved: unknown = JSON.parse(
      sessionStorage.getItem(storageKey) || "{}",
    );
    if (isChanges(saved)) changes = saved;
  } catch {
    sessionStorage.removeItem(storageKey);
  }
  function set(
    entity: string,
    id: string | number,
    fields: Record<string, SampleValue>,
  ) {
    const key = `${entity}:${id}`;
    changes[key] = { ...changes[key], ...fields };
    sessionStorage.setItem(storageKey, JSON.stringify(changes));
  }
  function get<T extends object>(
    entity: string,
    id: string | number,
    fixture: T,
  ): T {
    return { ...fixture, ...changes[`${entity}:${id}`] };
  }
  return { set, get, entries: () => Object.entries(changes) };
}
