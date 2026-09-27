import {
  createRecommendation,
  decideRecommendation,
  fetchPageIntelligence,
  verifyImplementationTask,
  type SearchIntelligenceItem,
  type SearchIntelligenceWorkspace,
  type SearchIntelligenceReadiness,
  type SEOPageIntelligence,
  type SEOReasoningPass,
} from "../seo";
import { statusLabel, statusTone } from "../status-language";
import {
  detailFact,
  emptyState,
  errorAlert,
  formatTimestamp,
  sectionCard,
  statusBadge,
} from "./index";

type Section = "attention" | "growth" | "technical" | "measuring" | "learned";

function text(value: unknown, fallback = "Unavailable"): string {
  if (typeof value === "string" && value.trim()) return value;
  if (typeof value === "number" && Number.isFinite(value)) return String(value);
  return fallback;
}

function record(value: unknown): Record<string, unknown> {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : {};
}

function items(value: unknown): Record<string, unknown>[] {
  const rows = record(value).items;
  return Array.isArray(rows) ? rows.map(record) : [];
}

function date(value: unknown): string {
  return typeof value === "string" ? formatTimestamp(value) : "Unavailable";
}

function pageName(item: SearchIntelligenceItem): string {
  if (item.page) {
    try {
      const url = new URL(item.page.normalized_url);
      return `${item.website.name} · ${url.pathname || "/"}`;
    } catch {
      return item.page.normalized_url;
    }
  }
  const query = item.opportunity.evidence.query;
  return typeof query === "string"
    ? `Unattributed query · “${query}”`
    : "Page unresolved";
}

function evidenceSummary(item: SearchIntelligenceItem): string {
  const evidence = item.opportunity.evidence;
  const parts: string[] = [];
  for (const key of [
    "issue",
    "query",
    "impressions",
    "clicks",
    "ctr",
    "position",
  ]) {
    const value = evidence[key];
    if (typeof value === "string" || typeof value === "number") {
      parts.push(`${statusLabel(key)}: ${value}`);
    }
  }
  return parts.length
    ? parts.join(" · ")
    : "Supporting source details are unavailable.";
}

function attentionReasons(
  item: SearchIntelligenceItem,
  readiness?: SearchIntelligenceReadiness,
): string[] {
  const reasons: string[] = [];
  if (item.recommendation?.status === "awaiting_approval")
    reasons.push("A human decision is required before implementation.");
  if (item.task?.status === "verification_failed")
    reasons.push("The latest implementation check failed.");
  if (item.task?.status === "failed" || item.task?.status === "cancelled")
    reasons.push("The governed implementation did not complete.");
  const verification = record(item.task?.verification_evidence);
  if (item.task && verification.result === "unavailable")
    reasons.push(
      text(
        (verification.limitations as unknown[])?.[0],
        "Verification evidence is unavailable.",
      ),
    );
  if (item.task?.status === "verification_pending")
    reasons.push(
      "Implementation completed, but the approved change is not verified.",
    );
  if (
    item.active_change &&
    item.active_change.revision_id !== item.recommendation?.id
  )
    reasons.push(
      `Another page change is ${statusLabel(item.active_change.state)}.`,
    );
  const limitation = item.opportunity.evidence.evidence_limitation;
  if (!item.recommendation && typeof limitation === "string" && limitation)
    reasons.push(limitation);
  if (
    item.opportunity.evidence.source === "google_search_console" &&
    readiness &&
    readiness.gsc !== "fresh"
  )
    reasons.push(
      `Search Console evidence is ${statusLabel(readiness?.gsc)}; review the mapping in Integrations.`,
    );
  return reasons;
}

export function searchIntelligenceSections(
  workspace: SearchIntelligenceWorkspace,
): Record<Section, SearchIntelligenceItem[]> {
  const sections: Record<Section, SearchIntelligenceItem[]> = {
    attention: [],
    growth: [],
    technical: [],
    measuring: [],
    learned: [],
  };
  const readiness = new Map(
    workspace.readiness.map((site) => [site.website_id, site]),
  );
  for (const item of workspace.items) {
    if (attentionReasons(item, readiness.get(item.website.id)).length)
      sections.attention.push(item);
    if (item.opportunity.recommendation_class === "technical_regression") {
      if (!item.outcome) sections.technical.push(item);
    } else if (!item.outcome && !item.task?.verified_at) {
      sections.growth.push(item);
    }
    if (
      item.opportunity.recommendation_class === "growth_change" &&
      item.task?.verified_at &&
      !item.outcome
    )
      sections.measuring.push(item);
    if (item.latest_measured) sections.learned.push(item);
  }
  return sections;
}

function actionButton(label: string, onClick: () => void): HTMLButtonElement {
  const button = document.createElement("button");
  button.type = "button";
  button.className = "ui-button ui-button--secondary ui-button--sm";
  button.textContent = label;
  button.addEventListener("click", onClick);
  return button;
}

function appendLines(parent: HTMLElement, values: string[]): void {
  if (!values.length) return;
  const list = document.createElement("ul");
  list.className = "ui-stack ui-stack--2";
  for (const value of values) {
    const row = document.createElement("li");
    row.textContent = value;
    list.append(row);
  }
  parent.append(list);
}

function renderReadiness(workspace: SearchIntelligenceWorkspace): HTMLElement {
  const card = sectionCard(
    "Acceptance journey readiness",
    "Recorded prerequisites for a controlled operator walkthrough. This is not live acceptance.",
  );
  const body = card.querySelector<HTMLElement>(".ui-card__body")!;
  if (!workspace.readiness.length) {
    body.append(
      emptyState(
        "No website resolved",
        "Set up a website before selecting a page.",
      ),
    );
  }
  for (const site of workspace.readiness) {
    const block = document.createElement("div");
    block.className = "ui-stack ui-stack--2";
    const name = document.createElement("h4");
    name.textContent = site.website_name;
    block.append(
      name,
      detailFact(
        "Organization/location",
        site.location_id ? "Resolved" : "Organization-wide",
      ),
      detailFact("GSC mapping and freshness", statusLabel(site.gsc)),
      detailFact("GA4 mapping and freshness", statusLabel(site.ga4)),
      detailFact("Page inventory", statusLabel(site.page_inventory)),
    );
    body.append(block);
  }
  const link = document.createElement("a");
  link.href = "/integrations";
  link.className = "ui-button ui-button--secondary ui-button--sm";
  link.textContent = "Manage integrations";
  body.append(link);
  if (workspace.readiness_has_more) {
    const note = document.createElement("p");
    note.className = "ui-text-secondary";
    note.textContent = "Readiness shows the first 100 websites.";
    body.append(note);
  }
  return card;
}

function renderSection(
  section: Section,
  rows: SearchIntelligenceItem[],
  workspace: SearchIntelligenceWorkspace,
  open: (item: SearchIntelligenceItem) => void,
): HTMLElement {
  const headings: Record<Section, [string, string]> = {
    attention: [
      "Requires Attention",
      "Decisions, failed checks, and material limitations requiring operator action.",
    ],
    growth: [
      "Growth Opportunities",
      "Deterministic priority and business evidence for intentional changes.",
    ],
    technical: [
      "Technical Regressions",
      "Corrective work remains independently actionable.",
    ],
    measuring: [
      "Currently Measuring",
      "Verified changes waiting for a mature observation window or outcome.",
    ],
    learned: [
      "Completed / Learned",
      "Observed after a verified change; classification does not prove causality.",
    ],
  };
  const [heading, description] = headings[section];
  const card = sectionCard(heading, description);
  const body = card.querySelector<HTMLElement>(".ui-card__body")!;
  if (!rows.length) {
    body.append(
      emptyState(
        `No ${heading.toLowerCase()} on this page`,
        "The current evidence and work states have no items here.",
      ),
    );
    return card;
  }
  const list = document.createElement("ul");
  list.className = "ui-record-list";
  const readiness = new Map(
    workspace.readiness.map((site) => [site.website_id, site]),
  );
  for (const item of rows) {
    const row = document.createElement("li");
    const info = document.createElement("div");
    const title = document.createElement("h4");
    title.textContent = pageName(item);
    const summary = document.createElement("p");
    summary.textContent =
      section === "learned"
        ? `Observed after this change: ${statusLabel(item.latest_measured?.outcome.classification)}.`
        : section === "measuring"
          ? `${statusLabel(item.measurement?.maturity)} · ${text(item.measurement?.metric, "Metric unavailable")}`
          : `${statusLabel(item.opportunity.opportunity_type)} · Priority ${item.opportunity.priority_score}`;
    info.append(title, summary);
    if (section === "attention")
      appendLines(info, attentionReasons(item, readiness.get(item.website.id)));
    else if (section === "growth" || section === "technical") {
      const evidence = document.createElement("p");
      evidence.className = "ui-text-secondary";
      evidence.textContent = evidenceSummary(item);
      info.append(evidence);
      const business = record(item.opportunity.evidence.business_importance);
      const context = document.createElement("p");
      context.className = "ui-text-secondary";
      context.textContent =
        section === "growth"
          ? `Business importance: ${statusLabel(text(business.business_importance_state))} · ${item.recommendation ? statusLabel(item.recommendation.status) : "No recommendation yet"}`
          : `Implementation: ${item.task ? statusLabel(item.task.status) : "Not delegated"}`;
      info.append(context);
    }
    if (section === "measuring") {
      const dates = document.createElement("p");
      dates.className = "ui-text-secondary";
      dates.textContent = `Verified ${date(item.task?.verified_at)} · Baseline ${date(item.measurement?.baseline_start)} to ${date(item.measurement?.baseline_end)} · Observation ${date(item.measurement?.measurement_start)} to ${date(item.measurement?.measurement_end)}`;
      info.append(dates);
    }
    if (section === "learned" && item.latest_measured) {
      const hypothesis = document.createElement("p");
      hypothesis.className = "ui-text-secondary";
      hypothesis.textContent =
        item.latest_measured.recommendation.expected_result_hypothesis;
      info.append(hypothesis);
    }
    row.append(
      info,
      actionButton("Review", () => open(item)),
    );
    list.append(row);
  }
  body.append(list);
  return card;
}

function pageEvidenceCard(
  title: string,
  facts: [string, string][],
  limitation?: string,
): HTMLElement {
  const card = sectionCard(title);
  const body = card.querySelector<HTMLElement>(".ui-card__body")!;
  for (const [label, value] of facts) body.append(detailFact(label, value));
  if (limitation) {
    const note = document.createElement("p");
    note.className = "ui-text-secondary";
    note.textContent = limitation;
    body.append(note);
  }
  return card;
}

function renderPageIntelligence(model: SEOPageIntelligence): HTMLElement[] {
  const identity = model.identity;
  const current = model.current_page;
  const crawl = model.crawl;
  const sitemap = record(crawl.sitemap);
  const gsc = model.gsc;
  const ga4 = model.ga4_organic_landing;
  const links = model.internal_links;
  const content = model.content;
  const gscRows = items(gsc.page).slice(0, 3);
  const ga4Rows = items(ga4.page).slice(0, 3);
  return [
    pageEvidenceCard("Page identity", [
      ["Canonical page", text(identity.normalized_url)],
      ["Website", text(identity.website_id)],
      ["Page", text(identity.page_id)],
    ]),
    pageEvidenceCard(
      "Access and technical",
      [
        ["HTTP", text(current.http_status)],
        ["Indexability", statusLabel(text(current.indexability))],
        ["Canonical", text(identity.canonical_url)],
        ["Redirect", text(current.redirect_destination)],
        [
          "Robots",
          items(current.robots_directives).length
            ? `${items(current.robots_directives).length} recorded directives`
            : "No directives recorded",
        ],
        [
          "Sitemap",
          sitemap.availability === "observed"
            ? sitemap.listed === true
              ? "Listed"
              : "Not listed"
            : "Unavailable",
        ],
        [
          "Internal links",
          `${text(links.mapped_inbound_count)} inbound · ${text(links.mapped_outbound_count)} outbound`,
        ],
        ["Last crawl", date(crawl.observed_at)],
      ],
      text(crawl.limitation),
    ),
    pageEvidenceCard(
      "Search evidence",
      [
        ["GSC", statusLabel(text(gsc.availability))],
        ["Window", `${date(gsc.period_start)} to ${date(gsc.period_end)}`],
        ["Mapped page records", String(items(gsc.page).length)],
        [
          "GSC freshness",
          statusLabel(text(items(gsc.properties)[0]?.freshness)),
        ],
        ...gscRows.map((row): [string, string] => [
          text(row.query, "Page total"),
          `${text(row.clicks)} clicks · ${text(row.impressions)} impressions · CTR ${text(row.ctr)} · position ${text(row.average_position)}`,
        ]),
        [
          "Query-only demand",
          `${items(gsc.website_query_only).length} website-scoped records`,
        ],
      ],
      text(gsc.limitation),
    ),
    pageEvidenceCard(
      "Conversion and content",
      [
        ["GA4 Organic Landing", statusLabel(text(ga4.availability))],
        [
          "GA4 freshness",
          statusLabel(text(items(ga4.properties)[0]?.freshness)),
        ],
        ...ga4Rows.map((row): [string, string] => [
          statusLabel(text(row.metric_key)),
          `${text(row.value)} · ${statusLabel(text(row.quality))}`,
        ]),
        ["Title", text(content.title)],
        ["Description", text(content.meta_description)],
        ["H1", text(content.h1)],
        [
          "Structured data",
          content.structured_data_present === true
            ? "Observed"
            : "Not observed",
        ],
      ],
      text(ga4.limitation),
    ),
  ];
}

function renderPass(
  name: string,
  pass: SEOReasoningPass | undefined,
): HTMLElement {
  const card = pageEvidenceCard(
    name,
    [["Availability", statusLabel(pass?.availability)]],
    pass?.limitation ??
      "A governed recommendation has not recorded this reasoning pass.",
  );
  return card;
}

async function renderDetail(
  panel: HTMLElement,
  item: SearchIntelligenceItem,
  organizationId: string,
  back: () => void,
): Promise<void> {
  panel.replaceChildren();
  panel.append(actionButton("Back to workspace", back));
  const intro = sectionCard(
    pageName(item),
    "Canonical evidence and governed decision history for this work item.",
  );
  const introBody = intro.querySelector<HTMLElement>(".ui-card__body")!;
  introBody.append(
    statusBadge(
      statusTone(item.opportunity.status),
      statusLabel(item.opportunity.status),
    ),
    detailFact("Opportunity", statusLabel(item.opportunity.opportunity_type)),
    detailFact("Class", statusLabel(item.opportunity.recommendation_class)),
    detailFact("Priority", String(item.opportunity.priority_score)),
    detailFact("Search evidence", evidenceSummary(item)),
  );
  if (!item.page)
    introBody.append(
      emptyState(
        "Page attribution unavailable",
        "Query-only demand remains website scoped. No landing page has been inferred.",
      ),
    );
  panel.append(intro);

  if (item.page) {
    const result = await fetchPageIntelligence(
      organizationId,
      item.website.id,
      item.page.id,
    );
    if (result.kind === "ok") {
      const grid = document.createElement("div");
      grid.className = "ui-card-grid ui-card-grid--lg";
      grid.append(...renderPageIntelligence(result.data));
      panel.append(grid);
    } else
      panel.append(
        errorAlert("Page Intelligence is unavailable in this scope."),
      );
  }

  const decision = item.recommendation?.decision_context;
  const decisionCard = sectionCard(
    "Decision",
    "Approved evidence and recommendation revisions remain authoritative.",
  );
  const decisionBody =
    decisionCard.querySelector<HTMLElement>(".ui-card__body")!;
  decisionBody.append(
    detailFact(
      "Business importance",
      statusLabel(decision?.business_importance_state),
    ),
    detailFact("Business value", text(decision?.business_importance_value)),
    detailFact("Business policy", text(decision?.business_importance_version)),
    detailFact(
      "Score policy",
      text(decision?.opportunity_score_policy_version),
    ),
    detailFact("Evidence quality", text(decision?.evidence_quality)),
    detailFact("Evidence freshness", text(decision?.evidence_freshness)),
    detailFact(
      "Evidence references",
      decision?.evidence_references.join(", ") ?? "Unavailable",
    ),
  );
  if (decision?.evidence_limitation)
    appendLines(decisionBody, [decision.evidence_limitation]);
  if (item.active_change)
    appendLines(decisionBody, [
      `Active page change ${item.active_change.revision_id}: ${statusLabel(item.active_change.state)}.`,
    ]);
  if (item.recommendation) {
    decisionBody.append(
      detailFact("Hypothesis", item.recommendation.expected_result_hypothesis),
      detailFact("Proposed change", item.recommendation.proposed_action),
      detailFact(
        "Risk / effort",
        `${statusLabel(item.recommendation.risk)} / ${statusLabel(item.recommendation.effort)}`,
      ),
      detailFact("Approval", statusLabel(item.recommendation.status)),
    );
    if (item.recommendation.status === "awaiting_approval") {
      const actions = document.createElement("div");
      actions.className = "ui-inline ui-inline--center";
      for (const [label, approve] of [
        ["Approve", true],
        ["Reject", false],
      ] as const) {
        const button = actionButton(label, () => {
          button.disabled = true;
          void decideRecommendation(
            organizationId,
            item.recommendation!.id,
            approve,
          ).then((result) => {
            if (result.kind === "ok") back();
            else {
              button.disabled = false;
              decisionBody.append(
                errorAlert("Decision could not be recorded."),
              );
            }
          });
        });
        actions.append(button);
      }
      decisionBody.append(actions);
    }
  } else {
    const link = document.createElement("a");
    link.href = "/automations?agent=agent.seo";
    link.className = "ui-button ui-button--secondary ui-button--sm";
    link.textContent = "Run SEO analysis";
    decisionBody.append(link);
    const form = document.createElement("form");
    form.className = "ui-form-grid";
    const action = document.createElement("textarea");
    action.required = true;
    action.rows = 3;
    action.setAttribute("aria-label", "Proposed change");
    const hypothesis = document.createElement("textarea");
    hypothesis.required = true;
    hypothesis.rows = 2;
    hypothesis.setAttribute("aria-label", "Expected result hypothesis");
    const risk = document.createElement("select");
    const effort = document.createElement("select");
    for (const value of ["low", "medium", "high"]) {
      risk.add(new Option(statusLabel(value), value));
      effort.add(new Option(statusLabel(value), value));
    }
    risk.setAttribute("aria-label", "Risk");
    effort.setAttribute("aria-label", "Effort");
    const submit = document.createElement("button");
    submit.type = "submit";
    submit.className = "ui-button ui-button--primary ui-button--sm";
    submit.textContent = "Submit recommendation for approval";
    form.append(action, hypothesis, risk, effort, submit);
    form.addEventListener("submit", (event) => {
      event.preventDefault();
      submit.disabled = true;
      void createRecommendation(organizationId, item.opportunity.id, {
        proposedAction: action.value,
        expectedResultHypothesis: hypothesis.value,
        risk: risk.value as "low" | "medium" | "high",
        effort: effort.value as "low" | "medium" | "high",
      }).then((result) => {
        if (result.kind === "ok") back();
        else {
          submit.disabled = false;
          form.append(
            errorAlert(
              "Recommendation could not be created. Review the evidence limitation or active page change.",
            ),
          );
        }
      });
    });
    decisionBody.append(form);
  }
  panel.append(decisionCard);

  const passes = decision?.passes;
  const passGrid = document.createElement("div");
  passGrid.className = "ui-card-grid ui-card-grid--lg";
  for (const [key, name] of [
    ["access", "Access"],
    ["competition", "Competition"],
    ["answer_engines", "Answer Engines"],
    ["conversion", "Conversion"],
  ] as const)
    passGrid.append(renderPass(name, passes?.[key]));
  panel.append(passGrid);

  const task = item.task;
  const verification = record(task?.verification_evidence);
  const expected = record(verification.expected_change);
  const actual = record(verification.actual);
  const implementation = pageEvidenceCard(
    "Implementation and verification",
    [
      ["Task", task ? statusLabel(task.status) : "Not delegated"],
      ["Workflow", text(task?.workflow_run_id)],
      ["Target", text(task?.target_reference)],
      ["Verified at", date(task?.verified_at)],
      ["Verification result", statusLabel(text(verification.result))],
      ["Verification source", text(verification.verification_method)],
      [
        "Expected change",
        text(expected.issue_absent, text(expected.target_reference)),
      ],
      ["Observed target", text(actual.title, text(actual.http_status))],
      [
        "Evidence references",
        Array.isArray(verification.evidence_references)
          ? verification.evidence_references
              .map((value) => text(value))
              .join(", ")
          : "Unavailable",
      ],
    ],
    Array.isArray(verification.limitations)
      ? verification.limitations.map((value) => text(value)).join(" ")
      : undefined,
  );
  const implementationBody =
    implementation.querySelector<HTMLElement>(".ui-card__body")!;
  if (task && !task.verified_at) {
    const verify = actionButton("Check implementation evidence", () => {
      verify.disabled = true;
      void verifyImplementationTask(organizationId, task.id).then((result) => {
        if (result.kind === "ok") back();
        else {
          verify.disabled = false;
          implementationBody.append(
            errorAlert("Verification could not be checked."),
          );
        }
      });
    });
    implementationBody.append(verify);
  }
  panel.append(implementation);

  const outcome = item.outcome ?? item.latest_measured?.outcome;
  const measurement = item.measurement;
  const baselineValues = record(outcome?.metrics.baseline);
  const measurementValues = record(outcome?.metrics.measurement);
  panel.append(
    pageEvidenceCard(
      "Measurement and observed outcome",
      [
        [
          "Metric",
          text(
            measurement?.metric ?? record(outcome?.metrics.measurement).metric,
          ),
        ],
        [
          "Maturity",
          outcome ? "Outcome recorded" : statusLabel(measurement?.maturity),
        ],
        [
          "Baseline",
          outcome
            ? `${date(outcome.baseline_start)} to ${date(outcome.baseline_end)}`
            : `${date(measurement?.baseline_start)} to ${date(measurement?.baseline_end)}`,
        ],
        [
          "Measurement",
          outcome
            ? `${date(outcome.measurement_start)} to ${date(outcome.measurement_end)}`
            : `${date(measurement?.measurement_start)} to ${date(measurement?.measurement_end)}`,
        ],
        [
          "Observed after this change",
          outcome ? statusLabel(outcome.classification) : "Pending",
        ],
        ["Baseline value", text(baselineValues.value)],
        ["Observed value", text(measurementValues.value)],
      ],
      outcome?.limitations.join(" ") ?? measurement?.limitation ?? undefined,
    ),
  );
}

export function renderSearchIntelligenceWorkspace(
  panel: HTMLElement,
  workspace: SearchIntelligenceWorkspace,
  organizationId: string,
  reload: (offset?: number) => void,
): void {
  panel.replaceChildren();
  panel.append(renderReadiness(workspace));
  if (workspace.history_truncated) {
    panel.append(
      errorAlert(
        "Older recommendation or implementation history exceeds this bounded view. Open the canonical record for full history.",
      ),
    );
  }
  const sections = searchIntelligenceSections(workspace);
  const open = (item: SearchIntelligenceItem) => {
    void renderDetail(panel, item, organizationId, () =>
      reload(workspace.pagination.offset),
    );
  };
  for (const key of [
    "attention",
    "growth",
    "technical",
    "measuring",
    "learned",
  ] as const)
    panel.append(renderSection(key, sections[key], workspace, open));
  const pagination = document.createElement("nav");
  pagination.className = "ui-inline ui-inline--center";
  pagination.setAttribute("aria-label", "Search Intelligence work pages");
  if (workspace.pagination.offset > 0)
    pagination.append(
      actionButton("Previous 50", () =>
        reload(Math.max(0, workspace.pagination.offset - 50)),
      ),
    );
  if (workspace.pagination.next_offset !== null)
    pagination.append(
      actionButton("Next 50", () => reload(workspace.pagination.next_offset!)),
    );
  panel.append(pagination);
}
