import { describeFailure } from "./errors";
import { fetchLocations } from "../workspace";
import {
  createSchedule,
  listSchedules,
  listWorkflowRuns,
  listWorkflowTypes,
  startWorkflowRun,
  updateSchedule,
  type WorkflowRunSummary,
  type WorkflowScheduleEntry,
  type WorkflowTypeEntry,
} from "../workflows";

export type ProductAutomationDomain = "gbp" | "seo" | "content" | "reviews";

const definitions: Record<
  string,
  { label: string; domain: ProductAutomationDomain; cadence?: string }
> = {
  "gbp.sync": { label: "Profile sync", domain: "gbp", cadence: "0 * * * *" },
  "gbp.generate_post": {
    label: "Local posting",
    domain: "gbp",
    cadence: "0 16 * * 2",
  },
  "agent.gbp": {
    label: "Profile optimization",
    domain: "gbp",
    cadence: "0 16 * * 2",
  },
  "reviews.ingest": {
    label: "Review sync",
    domain: "reviews",
    cadence: "0 * * * *",
  },
  "agent.reviews": {
    label: "Review analysis",
    domain: "reviews",
    cadence: "0 18 * * *",
  },
  "agent.content": {
    label: "Content planning",
    domain: "content",
    cadence: "0 17 * * 2",
  },
  "agent.seo": { label: "SEO analysis", domain: "seo" },
  "gbp.publish_change": { label: "Profile changes", domain: "gbp" },
  "gbp.publish_post": { label: "Post publishing", domain: "gbp" },
  "gbp.upload_media": { label: "Media publishing", domain: "gbp" },
  "content.draft_revision": { label: "Draft generation", domain: "content" },
  "content.publish": { label: "Content publishing", domain: "content" },
  "reviews.publish_response": {
    label: "Response publishing",
    domain: "reviews",
  },
  "seo.crawl_or_analysis": { label: "Website crawl", domain: "seo" },
  "seo.analyze": { label: "Opportunity analysis", domain: "seo" },
};

function button(
  label: string,
  variant: "primary" | "secondary" = "secondary",
): HTMLButtonElement {
  const element = document.createElement("button");
  element.type = "button";
  element.className = `ui-button ui-button--${variant} ui-button--sm`;
  element.textContent = label;
  return element;
}

function formatDate(value: string | null): string {
  if (!value) return "Not run yet";
  const date = new Date(value);
  return Number.isNaN(date.getTime())
    ? "Date unavailable"
    : date.toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

export function createAutomationCard(
  workflow: WorkflowTypeEntry,
  schedule: WorkflowScheduleEntry | undefined,
  lastRun: WorkflowRunSummary | undefined,
  organizationId: string,
  locationId: () => string | null,
  refresh: () => Promise<void>,
  setStatus: (message: string) => void,
  canManageSchedules: boolean,
): HTMLElement {
  const definition = definitions[workflow.key];
  const article = document.createElement("article");
  article.className = "ui-automation-card";
  const identity = document.createElement("div");
  identity.className = "ui-automation-card__identity";
  const heading = document.createElement("h3");
  heading.textContent = definition?.label ?? workflow.display_name;
  const runnable =
    workflow.key.startsWith("agent.") ||
    ["gbp.sync", "gbp.generate_post", "reviews.ingest"].includes(workflow.key);
  const detail = document.createElement("p");
  const state = schedule
    ? schedule.status === "active"
      ? "Active"
      : "Paused"
    : runnable
      ? "On demand"
      : "Runs with product work";
  const cadence =
    schedule?.cron_expression === "0 * * * *"
      ? "Hourly"
      : schedule
        ? "Scheduled"
        : definition?.cadence
          ? "No schedule"
          : "As needed";
  detail.textContent = `${state} · ${cadence} · ${lastRun ? `Last result: ${lastRun.status.replaceAll("_", " ")} ${formatDate(lastRun.completed_at ?? lastRun.created_at)}` : "Not run yet"}`;
  identity.append(heading, detail);
  const actions = document.createElement("div");
  actions.className = "ui-automation-card__actions";
  const run = button("Run now", "primary");
  if (workflow.key.startsWith("agent.")) {
    run.dataset.productAgentWorkflow = workflow.key;
  } else {
    run.addEventListener("click", async () => {
      const selected = locationId();
      if (!selected) {
        setStatus("Choose a location first.");
        return;
      }
      run.disabled = true;
      const result = await startWorkflowRun(organizationId, workflow.key, {
        locationId: selected,
        idempotencyKey: `product-${workflow.key}-${organizationId}-${selected}-${Date.now()}`,
        execute: true,
      });
      setStatus(
        result.kind === "ok"
          ? `${heading.textContent} started.`
          : describeFailure(result, heading.textContent ?? "Automation"),
      );
      run.disabled = false;
      if (result.kind === "ok") await refresh();
    });
  }
  if (runnable) actions.append(run);
  if (definition?.cadence && canManageSchedules) {
    const manage = button(
      schedule
        ? schedule.status === "active"
          ? "Pause"
          : "Resume"
        : "Schedule",
    );
    manage.addEventListener("click", async () => {
      const selected = locationId();
      if (!selected) {
        setStatus("Choose a location first.");
        return;
      }
      manage.disabled = true;
      const result = schedule
        ? await updateSchedule(organizationId, schedule.id, {
            status: schedule.status === "active" ? "paused" : "active",
            next_run_at:
              schedule.status === "paused"
                ? new Date(Date.now() + 60_000).toISOString()
                : undefined,
          })
        : await createSchedule(organizationId, {
            workflow_key: workflow.key,
            key: `${workflow.key}.${selected}`,
            cron_expression: definition.cadence!,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC",
            next_run_at: new Date(Date.now() + 60_000).toISOString(),
            location_id: selected,
          });
      setStatus(
        result.kind === "ok"
          ? `${heading.textContent} schedule updated.`
          : describeFailure(result, "Schedule"),
      );
      manage.disabled = false;
      if (result.kind === "ok") await refresh();
    });
    actions.append(manage);
  }
  article.append(identity, actions);
  return article;
}

export async function mountProductAutomations(
  domain: ProductAutomationDomain,
  organizationId: string,
  canManageSchedules = false,
): Promise<void> {
  const root = document.querySelector<HTMLElement>(
    `[data-product-automations="${domain}"]`,
  );
  if (!root) return;
  const cards = root.querySelector<HTMLElement>(
    ".ui-product-automations__cards",
  )!;
  const status = root.querySelector<HTMLElement>(
    ".ui-product-automations__status",
  )!;
  const location = root.querySelector<HTMLElement>(
    ".ui-product-automations__location",
  )!;
  root.dataset.automationOrganizationId = organizationId;
  cards.replaceChildren();
  status.textContent = "";
  const places = await fetchLocations(organizationId);
  if (root.dataset.automationOrganizationId !== organizationId) return;
  location.replaceChildren();
  let selector: HTMLSelectElement | null = null;
  if (places.kind === "ok" && places.data.length > 1) {
    selector = document.createElement("select");
    selector.className = "ui-input";
    selector.setAttribute("aria-label", "Automation location");
    selector.append(new Option("Choose a location", ""));
    for (const place of places.data)
      selector.append(new Option(place.name, place.id));
    location.append(selector);
    location.hidden = false;
  } else location.hidden = true;
  const selectedLocation = (): string | null => {
    const pageSelection = document.querySelector<
      HTMLInputElement | HTMLSelectElement
    >("#location-select, [data-agent-location-id]");
    const explicit =
      pageSelection?.getAttribute("data-agent-location-id") ||
      pageSelection?.value;
    return (
      explicit ||
      selector?.value ||
      (places.kind === "ok" && places.data.length === 1
        ? places.data[0].id
        : null)
    );
  };
  const refresh = async (): Promise<void> => {
    const [catalog, schedules, runs] = await Promise.all([
      listWorkflowTypes(organizationId),
      listSchedules(organizationId),
      listWorkflowRuns(organizationId, { limit: 40 }),
    ]);
    if (root.dataset.automationOrganizationId !== organizationId) return;
    cards.replaceChildren();
    if (catalog.kind !== "ok") {
      status.textContent = describeFailure(catalog, "Automations");
      return;
    }
    const workflows = catalog.data.filter(
      (item) =>
        definitions[item.key]?.domain === domain || item.product_key === domain,
    );
    if (!workflows.length) {
      root.hidden = true;
      return;
    }
    root.hidden = false;
    const currentLocation = selectedLocation();
    for (const workflow of workflows) {
      const schedule =
        schedules.kind === "ok"
          ? schedules.data.find(
              (item) =>
                item.workflow_key === workflow.key &&
                item.location_id === currentLocation &&
                item.status !== "cancelled",
            )
          : undefined;
      const lastRun =
        runs.kind === "ok"
          ? runs.data.find(
              (item) =>
                item.workflow_key === workflow.key &&
                item.location_id === currentLocation,
            )
          : undefined;
      cards.append(
        createAutomationCard(
          workflow,
          schedule,
          lastRun,
          organizationId,
          selectedLocation,
          refresh,
          (message) => {
            status.textContent = message;
          },
          canManageSchedules,
        ),
      );
    }
  };
  selector?.addEventListener("change", () => {
    void refresh();
  });
  await refresh();
}
