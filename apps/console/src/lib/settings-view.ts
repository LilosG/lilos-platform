import type {
  FactAuthority,
  FactRecord,
  LocationRecord,
  LocationStatus,
} from "../adapters/administration";
import {
  factSourceChips,
  locationChip,
  waitingForApprovalChip,
  type Chip,
} from "./status";
/** The lifecycle calls a location accepts; each is one route of the API. */
export type LocationStep =
  "activate" | "pause" | "close-temporarily" | "close-permanently" | "archive";
export type LocationAction = LocationStep | "retire";
/**
 * The API's own lifecycle table (apps/api/app/locations/service.py TRANSITIONS), restated as the
 * calls this screen may make. A button is offered only when the API will accept it.
 */
const ALLOWED: Record<LocationStatus, readonly LocationStep[]> = {
  setup_required: ["activate", "archive"],
  active: ["pause", "close-temporarily", "close-permanently"],
  paused: ["activate", "close-temporarily", "close-permanently", "archive"],
  closed_temporarily: ["activate", "pause", "close-permanently"],
  closed_permanently: ["archive"],
  archived: [],
};
/** Retiring is closing for good and then archiving: the order the lifecycle requires. */
export function retirePlan(status: LocationStatus): LocationStep[] {
  if (status === "archived") return [];
  if (status === "setup_required" || status === "closed_permanently")
    return ["archive"];
  return ["close-permanently", "archive"];
}
export interface LocationActionView {
  action: LocationAction;
  label: string;
}
const LABELS: Record<LocationStep, (status: LocationStatus) => string> = {
  activate: (status) =>
    status === "setup_required"
      ? "Activate"
      : status === "paused"
        ? "Resume"
        : "Reopen",
  pause: () => "Pause",
  "close-temporarily": () => "Close temporarily",
  "close-permanently": () => "Close permanently",
  archive: () => "Archive",
};
/** What can be done to a location now: the lifecycle steps, then Retire when it can be done. */
export function locationActions(status: LocationStatus): LocationActionView[] {
  const steps = ALLOWED[status]
    // Archiving a paused or setup location is what Retire does; one button says it.
    .filter((step) => step !== "archive")
    .map((step) => ({ action: step, label: LABELS[step](status) }));
  const plan = retirePlan(status);
  return plan.length
    ? [...steps, { action: "retire", label: "Retire location" }]
    : steps;
}
export interface LocationRow {
  id: string;
  name: string;
  address: string;
  chip: Chip;
  primary: boolean;
  retired: boolean;
  actions: LocationActionView[];
  version: number;
  status: LocationStatus;
}
/** An address a person reads: street, city, state and postal code, or the service area. */
export function addressText(location: LocationRecord): string {
  const street = [location.address_line_1, location.address_line_2]
    .filter(Boolean)
    .join(", ");
  const area = [
    location.city,
    [location.region, location.postal_code].filter(Boolean).join(" "),
  ]
    .filter(Boolean)
    .join(", ");
  return (
    [street, area].filter(Boolean).join(", ") ||
    location.service_area_description ||
    "No address on file"
  );
}
export function locationRows(locations: LocationRecord[]): LocationRow[] {
  const order: Record<LocationStatus, number> = {
    active: 0,
    setup_required: 1,
    paused: 2,
    closed_temporarily: 3,
    closed_permanently: 4,
    archived: 5,
  };
  return [...locations]
    .sort(
      (a, b) =>
        Number(b.is_primary) - Number(a.is_primary) ||
        order[a.status] - order[b.status] ||
        a.name.localeCompare(b.name),
    )
    .map((location) => ({
      id: location.id,
      name: location.name,
      address: addressText(location),
      chip: locationChip(location.status),
      primary: location.is_primary,
      retired: location.status === "archived",
      actions: locationActions(location.status),
      version: location.version,
      status: location.status,
    }));
}
export interface LocationConfirm {
  title: string;
  lines: string[];
  accept: string;
  tone: "normal" | "danger";
}
/** Exactly what will happen to the location, asked before it does. */
export function locationConfirm(
  action: LocationAction,
  name: string,
): LocationConfirm {
  switch (action) {
    case "retire":
      return {
        title: `Retire ${name}?`,
        lines: [
          `${name} stops all of its automations and is hidden from reports.`,
          "It is closed for good and then archived. This cannot be undone.",
        ],
        accept: "Retire location",
        tone: "danger",
      };
    case "close-permanently":
      return {
        title: `Close ${name} permanently?`,
        lines: [
          `${name} stops all of its automations and is hidden from reports.`,
          "You can still archive it afterwards. It cannot be reopened.",
        ],
        accept: "Close permanently",
        tone: "danger",
      };
    case "close-temporarily":
      return {
        title: `Close ${name} temporarily?`,
        lines: [`${name} is marked as closed for now. Reopen it any time.`],
        accept: "Close temporarily",
        tone: "normal",
      };
    case "pause":
      return {
        title: `Pause ${name}?`,
        lines: [`${name} is marked as paused. Resume it any time.`],
        accept: "Pause location",
        tone: "normal",
      };
    case "archive":
      return {
        title: `Archive ${name}?`,
        lines: ["This cannot be undone."],
        accept: "Archive location",
        tone: "danger",
      };
    default:
      return {
        title: `Activate ${name}?`,
        lines: [`${name} becomes an active location.`],
        accept: "Activate",
        tone: "normal",
      };
  }
}
const STEP_DONE: Record<LocationStep, string> = {
  activate: "activated",
  pause: "paused",
  "close-temporarily": "closed temporarily",
  "close-permanently": "closed permanently",
  archive: "archived",
};
const STEP_ING: Record<LocationStep, string> = {
  activate: "activating it",
  pause: "pausing it",
  "close-temporarily": "closing it temporarily",
  "close-permanently": "closing it permanently",
  archive: "archiving it",
};
/** Which step of a retirement a failure reached, in words. */
export function retireProgress(done: LocationStep[], failed: LocationStep) {
  return done.length
    ? `It was ${done.map((step) => STEP_DONE[step]).join(" and ")}, but ${STEP_ING[failed]} did not go through.`
    : `${STEP_ING[failed][0].toUpperCase()}${STEP_ING[failed].slice(1)} did not go through, so nothing changed.`;
}
const LOCATION_FAILURES: Record<string, string> = {
  LOCATION_VERSION_CONFLICT:
    "This location changed since you opened the page. Refresh to see its current state.",
  LOCATION_TRANSITION_CONFLICT:
    "That change is not available for this location in its current state. Refresh to see its state.",
  LOCATION_PARENT_STATE_CONFLICT:
    "This client's own state does not allow that change right now.",
  LOCATION_NOT_FOUND: "This location no longer exists. Refresh the page.",
  AUTHORIZATION_DENIED: "You do not have permission to change locations.",
  DATABASE_INTEGRITY_CONFLICT:
    "Another request changed this location at the same moment. Refresh and try again.",
  MUTATION_OUTCOME_UNCERTAIN:
    "We could not confirm what happened. Refresh to see the location's current state.",
  AUTH_REQUIRED: "Your session ended. Sign in again to continue.",
  CSRF_INVALID: "Your session expired. Refresh the page and try again.",
};
export const settingsFailureText = (code: string): string =>
  LOCATION_FAILURES[code] ??
  "That did not go through. Refresh to see the current state, then try again.";

/** The business facts a person may add or change here, with a plain label for each. */
export const FACT_FIELDS = [
  {
    id: "name",
    key: "business.name",
    label: "Business name",
    type: "string",
    hint: "The name used in content and replies.",
  },
  {
    id: "website",
    key: "business.website",
    label: "Website",
    type: "string",
    hint: "The address of the client's website.",
  },
  {
    id: "address",
    key: "business.address",
    label: "Address",
    type: "object",
    hint: "The street address customers are sent to.",
  },
  {
    id: "claims",
    key: "brand.approved_claims",
    label: "Approved claims",
    type: "string_list",
    hint: "Things we may say about the business, one per line.",
  },
] as const;
export type FactField = (typeof FACT_FIELDS)[number];
const FACT_LABELS: Record<string, string> = {
  ...Object.fromEntries(FACT_FIELDS.map((f) => [f.key, f.label])),
  "business.hours": "Opening hours",
};
/** A plain label for a fact; a key this app does not know is "Other detail", never the key. */
export const factLabel = (key: string): string =>
  FACT_LABELS[key] ??
  (key.startsWith("claim.") ? "Approved claim" : "Other detail");
const DAYS = 7;
const asRecord = (value: unknown): Record<string, unknown> | null =>
  value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
/** A fact's value as a person reads it. Null means there is nothing sensible to say. */
export function factValueText(key: string, value: unknown): string | null {
  if (typeof value === "string") return value.trim() || null;
  if (typeof value === "boolean") return value ? "Yes" : "No";
  if (typeof value === "number") return String(value);
  if (Array.isArray(value)) {
    const items = value.filter((v): v is string => typeof v === "string");
    return items.length ? items.join(" · ") : null;
  }
  const record = asRecord(value);
  if (!record) return null;
  if (key === "business.address") {
    const street = [record.address_line_1, record.address_line_2]
      .filter((v) => typeof v === "string" && v)
      .join(", ");
    const area = [
      record.city,
      [record.region, record.postal_code]
        .filter((v) => typeof v === "string" && v)
        .join(" "),
    ]
      .filter((v) => typeof v === "string" && v)
      .join(", ");
    return [street, area].filter(Boolean).join(", ") || null;
  }
  if (key === "business.hours") {
    const periods = Array.isArray(record.periods) ? record.periods : [];
    const days = new Set(
      periods.flatMap((p) => {
        const day = asRecord(p)?.openDay;
        return typeof day === "string" ? [day] : [];
      }),
    );
    return days.size
      ? days.size === DAYS
        ? "Open every day"
        : `Open ${days.size} ${days.size === 1 ? "day" : "days"} a week`
      : null;
  }
  return null;
}
export interface FactRow {
  label: string;
  value: string;
  chip: Chip;
  /** True for a proposal still waiting for approval. */
  waiting: boolean;
  /** The field this fact is edited through, when it is one of the editable ones. */
  field: FactField["id"] | null;
  /** The stored value, for filling the form when the fact is changed. */
  raw: unknown;
  identity: string;
  locationId: string | null;
}
const editable = (key: string): FactField["id"] | null =>
  FACT_FIELDS.find((field) => field.key === key)?.id ?? null;
/** Facts as readable rows: proposals waiting for approval first, then what is in effect. */
export function factRows(
  effective: FactRecord[],
  waiting: FactRecord[],
): FactRow[] {
  const row = (fact: FactRecord, isWaiting: boolean): FactRow[] => {
    const value = factValueText(fact.fact_key, fact.value);
    if (value === null) return [];
    return [
      {
        label: factLabel(fact.fact_key),
        value,
        chip: isWaiting
          ? waitingForApprovalChip
          : factSourceChips[fact.authority satisfies FactAuthority],
        waiting: isWaiting,
        field: editable(fact.fact_key),
        raw: fact.value,
        identity: fact.fact_identity,
        locationId: fact.location_id,
      },
    ];
  };
  return [
    ...waiting.flatMap((fact) => row(fact, true)),
    ...effective.flatMap((fact) => row(fact, false)),
  ];
}
export type FactForm = Record<string, string>;
/** The proposal the dialog sends: typed by the field chosen, never built from free text keys. */
export function factProposal(
  field: FactField,
  form: FactForm,
  existing?: { identity: string; locationId: string | null },
  /** Where a new address is filed: the primary location, like the one LILOs derives. */
  primaryLocationId: string | null = null,
) {
  const lines = (form.value ?? "")
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean);
  const value =
    field.type === "string_list"
      ? lines
      : field.type === "object"
        ? {
            address_line_1: form.address_line_1?.trim() ?? "",
            address_line_2: form.address_line_2?.trim() || null,
            city: form.city?.trim() ?? "",
            region: form.region?.trim() ?? "",
            postal_code: form.postal_code?.trim() ?? "",
            country_code: form.country_code?.trim() || "US",
          }
        : (form.value ?? "").trim();
  return {
    ...(existing
      ? {
          fact_identity: existing.identity,
          location_id: existing.locationId,
        }
      : field.key === "business.address" && primaryLocationId
        ? { location_id: primaryLocationId }
        : {}),
    fact_key: field.key,
    value_type: field.type,
    value,
    source: "console" as const,
    authority: "operator_verified" as const,
    change_reason: form.reason?.trim() || "Updated from client settings",
  };
}
/** Whether a form holds something to send. */
export function factFormComplete(field: FactField, form: FactForm): boolean {
  if (field.type === "object")
    return Boolean(
      form.address_line_1?.trim() && form.city?.trim() && form.region?.trim(),
    );
  return Boolean(form.value?.trim());
}
const FACT_FAILURES: Record<string, string> = {
  AUTHORIZATION_DENIED: "You do not have permission to change business facts.",
  ADMINISTRATION_CONFLICT:
    "This detail changed since you opened the page. Refresh and try again.",
  VALIDATION_FAILED: "Check the details and try again.",
  BODY_INVALID: "Check the details and try again.",
  MUTATION_OUTCOME_UNCERTAIN:
    "We could not confirm what happened. Refresh to see the current details.",
  AUTH_REQUIRED: "Your session ended. Sign in again to continue.",
  CSRF_INVALID: "Your session expired. Refresh the page and try again.",
};
export const factFailureText = (code: string): string =>
  FACT_FAILURES[code] ??
  "That did not go through. Refresh to see the current details, then try again.";
