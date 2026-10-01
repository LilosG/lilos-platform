import {
  clients,
  actions,
  opportunities,
  pageRecords,
  reviewRecords,
  automationRuns,
  automationDefs,
  reports,
  systems,
} from "../data/fixtures";
import { updateBadge } from "./status";
import { refreshRecordViews } from "./record-views";
import { fmt, required } from "./view";
import { connectionInfo } from "./selectors";
import { route } from "../config/routes";
import { createSampleSession } from "./sample-session";
import type { createDialogs } from "./dialogs";
export function createWorkflows(
  root: HTMLElement,
  dialogs: ReturnType<typeof createDialogs>,
  notify: (message: string) => void,
  onRecordsChanged: () => void,
) {
  const session = createSampleSession();
  const client = (id: string) =>
    session.get(
      "client",
      id,
      required(
        clients.find((c) => c.id === id),
        "client",
      ),
    );
  const editor = () =>
    required(
      dialogs.current()?.querySelector<HTMLTextAreaElement>("textarea"),
      "editor",
    );
  const badge = updateBadge;
  function patch(
    entity: string,
    id: string | number,
    fields: Record<string, string | number | boolean>,
  ) {
    session.set(entity, id, fields);
    for (const [field, value] of Object.entries(fields))
      root
        .querySelectorAll<HTMLElement>(
          `[data-entity="${entity}"][data-record-id="${CSS.escape(String(id))}"][data-field="${field}"]`,
        )
        .forEach((el) => {
          const b = el.querySelector<HTMLElement>(".badge");
          if (b) badge(b, String(value));
          else if (
            el instanceof HTMLInputElement ||
            el instanceof HTMLTextAreaElement ||
            el instanceof HTMLSelectElement
          )
            el.value = String(value);
          else el.textContent = String(value);
        });
    if (entity === "client") {
      root
        .querySelectorAll<HTMLElement>(`[data-connection-client="${id}"]`)
        .forEach((el) => {
          const info = connectionInfo(
            client(String(id)),
            Number(el.dataset.connectionSource),
          );
          const field = el.dataset.connectionField;
          const value =
            field === "status"
              ? info.status
              : field === "authorization"
                ? info.authorization
                : info.freshness;
          const b = el.querySelector<HTMLElement>(".badge");
          if (b) badge(b, value);
          else el.textContent = value;
        });
      const settingFields: Record<string, string> = {
        name: "settingname",
        location: "settinglocation",
        category: "settingcategory",
        contactEmail: "settingemail",
        responsePreference: "settingapproval",
        timezone: "settingtimezone",
      };
      for (const [field, value] of Object.entries(fields)) {
        const input = root.querySelector<HTMLInputElement | HTMLSelectElement>(
          "#" + settingFields[field],
        );
        if (input && root.dataset.clientId === String(id))
          input.value = String(value);
      }
      if (fields.name)
        root
          .querySelectorAll<HTMLElement>(
            `[data-client-title="${id}"],[data-context-client="${id}"]`,
          )
          .forEach((el) => (el.textContent = String(fields.name)));
      for (const i of [0, 1, 2])
        if (fields["sync" + i])
          root
            .querySelectorAll<HTMLElement>(
              `[data-source-client="${id}"][data-source-sync="${i}"]`,
            )
            .forEach((el) => (el.textContent = String(fields["sync" + i])));
    }
    if (entity === "page" && fields.status === "Indexed")
      root
        .querySelectorAll<HTMLButtonElement>(
          `[data-command="updatePage"][data-args='${JSON.stringify([String(id)])}']`,
        )
        .forEach((button) => (button.textContent = "Refresh sample check"));
    if (entity === "report" && typeof fields.status === "string")
      root
        .querySelectorAll<HTMLElement>(`main [data-report-id="${id}"]`)
        .forEach((row) => (row.dataset.status = String(fields.status)));
    if (entity === "automation")
      root
        .querySelectorAll<HTMLElement>(`main [data-automation-id="${id}"]`)
        .forEach((row) => {
          row.dataset.status = String(fields.status ?? row.dataset.status);
          row.dataset.outcome = String(
            fields.lastStatus ?? row.dataset.outcome,
          );
        });
    if (entity === "opportunity" && fields.started) {
      root
        .querySelectorAll<HTMLElement>(`[data-opportunity-status="${id}"]`)
        .forEach((el) => (el.hidden = false));
      root
        .querySelectorAll<HTMLButtonElement>('[data-command="startOpp"]')
        .forEach((b) => {
          if (b.dataset.args === JSON.stringify([Number(id)])) {
            b.disabled = true;
            b.textContent = "In progress";
          }
        });
    }
    if (entity === "opportunity" && fields.started) {
      root
        .querySelectorAll<HTMLElement>(`[data-opportunity-effort="${id}"]`)
        .forEach((el) => (el.textContent = "In progress"));
      root
        .querySelectorAll<HTMLElement>(
          `main [data-opportunity-id="${id}"][data-opportunity-mode="compact"]`,
        )
        .forEach((el) => (el.hidden = true));
    }
    if (entity === "action" && fields.done) {
      root
        .querySelectorAll<HTMLElement>(`[data-attention-id="${id}"]`)
        .forEach((el) => {
          el.classList.add("resolved");
          const icon = el.querySelector(".severity");
          if (icon) icon.textContent = "✓";
        });
    }
    if (entity === "action") {
      const openActions = actions.filter(
        (a) => !session.get("action", a.id, a).done,
      );
      root.querySelectorAll<HTMLElement>("section").forEach((section) => {
        const rows = [
          ...section.querySelectorAll<HTMLElement>(
            ":scope > [data-attention-limit]",
          ),
        ];
        if (!rows.length) return;
        const allowed = openActions.filter((a) =>
          rows.some((row) => row.dataset.attentionId === String(a.id)),
        );
        const limit = Number(rows[0].dataset.attentionLimit || 100);
        rows.forEach(
          (row) =>
            (row.hidden = !allowed
              .slice(0, limit)
              .some((a) => String(a.id) === row.dataset.attentionId)),
        );
        const count = section.querySelector("h2 .count");
        if (count) count.textContent = String(allowed.length);
        const empty = section.querySelector<HTMLElement>(
          "[data-attention-empty]",
        );
        if (empty) empty.hidden = allowed.length > 0;
      });
      root
        .querySelectorAll<HTMLElement>(
          '[aria-label="Client attention items"],[aria-label="Portfolio attention items"]',
        )
        .forEach(
          (el) =>
            (el.textContent =
              "⚑ " +
              openActions.filter(
                (a) =>
                  !root.dataset.clientId ||
                  a.client === Number(root.dataset.clientId) - 1,
              ).length),
        );
    }
    if (entity === "review" && typeof fields.status === "string") {
      const row = root.querySelector<HTMLElement>(
        `main [data-review-id="${id}"]`,
      );
      if (row) {
        row.dataset.status = fields.status;
        const b = row.querySelector<HTMLElement>(".reviewtop .badge");
        if (b) badge(b, fields.status);
        let response = row.querySelector<HTMLElement>(".savedresponse");
        if (!response) {
          response = document.createElement("div");
          response.className = "savedresponse";
          const label = document.createElement("b");
          const copy = document.createElement("p");
          response.append(label, copy);
          row.insertBefore(response, row.querySelector("button"));
        }
        response.querySelector("b")!.textContent =
          fields.status === "Published"
            ? "Published response"
            : "Response draft";
        response.querySelector("p")!.textContent = String(
          fields.response || "",
        );
      }
      const dialog = root.querySelector<HTMLDialogElement>(
        `#review-${CSS.escape(String(id))}`,
      );
      if (dialog) {
        const text = dialog.querySelector("textarea");
        if (text) text.readOnly = fields.status === "Published";
        const publish = dialog.querySelector<HTMLButtonElement>(
          '[data-command="saveReview"][data-args*=Published]',
        );
        if (publish)
          publish.textContent =
            fields.status === "Awaiting approval"
              ? "Approve & publish sample"
              : "Publish sample response";
        dialog
          .querySelectorAll<HTMLButtonElement>(
            '[data-command="saveReview"],[data-command="generateReviewResponse"]',
          )
          .forEach((b) => (b.hidden = fields.status === "Published"));
      }
    }
    if (entity === "task" || entity === "opportunity") {
      root
        .querySelectorAll<HTMLElement>("[data-upcoming-work]")
        .forEach((container) => {
          container.replaceChildren();
          const clientId = container.dataset.workClient;
          const work = session
            .entries()
            .filter(
              ([key, f]) =>
                (key.startsWith("task:") &&
                  (!clientId || f.client === clientId)) ||
                (key.startsWith("opportunity:") &&
                  f.started &&
                  (!clientId ||
                    opportunities.find(
                      (o) => o.id === Number(key.split(":")[1]),
                    )?.client ===
                      Number(clientId) - 1)),
            )
            .slice(-2);
          for (const [key, f] of work) {
            const o = key.startsWith("opportunity:")
              ? opportunities.find((o) => o.id === Number(key.split(":")[1]))
              : undefined;
            const row = document.createElement("div");
            row.className = "listrow";
            const content = document.createElement("div");
            content.textContent = o?.title || String(f.title);
            const small = document.createElement("small");
            small.textContent = o
              ? "Work started · " + clients[o.client].name
              : "Recovery task · Due today";
            content.append(small);
            const status = document.createElement("span");
            badge(status, o ? "In progress" : "Scheduled");
            row.append(content, status);
            container.append(row);
          }
        });
    }
    if (entity === "lead" && fields.status) {
      const [clientId, index] = String(id).split("-");
      const row = root
        .querySelector<HTMLButtonElement>(
          `[data-command="openLead"][data-args='${JSON.stringify([clientId, Number(index)])}']`,
        )
        ?.closest("tr");
      const b = row?.querySelector<HTMLElement>(".badge");
      if (b) badge(b, String(fields.status));
    }
    refreshRecordViews(root, session);
    onRecordsChanged();
  }
  function renderActivity() {
    root
      .querySelectorAll<HTMLElement>("[data-activity-feed]")
      .forEach((section) => {
        section
          .querySelectorAll("[data-session-activity]")
          .forEach((row) => row.remove());
        const entries = session
          .entries()
          .filter(
            ([key, fields]) =>
              key.startsWith("activity:") &&
              (!root.dataset.clientId ||
                fields.client === root.dataset.clientId),
          )
          .reverse()
          .slice(0, Number(section.dataset.activityLimit));
        for (const [, fields] of entries.reverse()) {
          const row = document.createElement("div");
          row.className = "listrow feed";
          row.dataset.sessionActivity = "";
          const icon = document.createElement("span");
          icon.className = "activitydot";
          icon.textContent = "✓";
          const content = document.createElement("div");
          content.textContent = String(fields.text);
          const small = document.createElement("small");
          const link = document.createElement("a");
          link.className = "link compact-link";
          link.href = route("client", String(fields.client));
          link.textContent = client(String(fields.client)).name;
          small.append(link);
          content.append(small);
          const time = document.createElement("time");
          time.textContent = "Just now";
          row.append(icon, content, time);
          const heading = section.querySelector(".panelhead");
          if (heading) heading.after(row);
          else section.prepend(row);
        }
        section
          .querySelectorAll<HTMLElement>("[data-activity-fixture]")
          .forEach(
            (row, i) =>
              (row.hidden =
                i >= Number(section.dataset.activityLimit) - entries.length),
          );
      });
  }
  function activity(text: string, clientId: string) {
    session.set(
      "activity",
      session.entries().filter(([key]) => key.startsWith("activity:")).length,
      { text, client: clientId, time: "Just now" },
    );
    renderActivity();
  }
  function finish(message: string) {
    dialogs.close();
    notify(message);
  }
  function download(id: number) {
    const c = client(String(id + 1));
    const r = session.get("report", id, reports[id]);
    const hospitality =
      root.dataset.clientId === c.id && c.workspaceProfile === "hospitality";
    const text = hospitality
      ? `${c.name} · September 1–30, 2026 · Sample data\nGA4 organic sessions: 4,110 (+31%)\nSearch Console clicks: 1,386 (+24%); impressions: 27,720 (+22%); CTR: 5.0%\nLocal visibility: 72%; average local rank: 6.2; Top 3: 46%; Top 10: 78%\nGBP interactions: 2,488 (515 calls, 1,201 website clicks, 772 direction requests)\nGA4 website events: 132 reservation clicks (−8%), 48 form submissions, 106 phone clicks\nTotal website action events: 286; not unique guests or confirmed bookings\nGoogle rating: 4.8; 18 new reviews; 342 total\nMenu organic sessions: 2,840; Reserve clicks: 45; click rate: 1.6%\nCompleted reservations: unavailable\nNext action: improve the mobile reservation path and build focused brunch coverage.`
      : `LILOs Growth — SAMPLE CLIENT REPORT\n${c.name} | ${r.period}\nLocal visibility: ${c.visibility}%\nOrganic traffic: ${fmt(c.organic)}\nWebsite leads: ${c.website === "Tracking issue" ? "Incomplete — tracking stopped" : c.leads}\nData readiness: ${r.note}\nRating: ${c.rating}\nNew reviews: ${c.newReviews}\nNext work: ${c.next}\n`;
    const a = document.createElement("a");
    const url = URL.createObjectURL(new Blob([text], { type: "text/plain" }));
    a.href = url;
    a.download = hospitality
      ? c.slug + "-september-2026-report.txt"
      : c.slug + "-report.txt";
    a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    notify(
      hospitality
        ? c.name + " sample report downloaded."
        : "Sample report downloaded.",
    );
  }
  function execute(
    name: string,
    args: (string | number)[],
    trigger?: HTMLElement,
  ) {
    const id = String(args[0] ?? "");
    const index = Number(args[1] ?? 0);
    const opening: Record<string, string> = {
      openOpp: "opportunity",
      openAction: "action",
      openSystem: "system",
      showProfile: "profile",
      openPost: "post",
      openPage: "page",
      openContent: "content",
      openLead: "lead",
      openReview: "review",
      openReviewRequest: "request",
      openAutomation: "automation",
      openHistoricalReport: "history",
      openReport: "report",
      openClientConnection: "connection",
      openOutcome: "outcome",
      openClientAttention: "client-attention",
    };
    if (opening[name]) {
      let key =
        opening[name] + (name === "openClientAttention" ? "" : "-" + id);
      if (["openLead", "openHistoricalReport"].includes(name))
        key += "-" + index;
      if (name === "openClientConnection") key = `connection-${id}-${args[1]}`;
      dialogs.open(key, trigger);
      return;
    }
    if (name === "nav") {
      location.href = route(
        id,
        args[1] ? String(args[1]) : null,
        String(args[2] || "Overview"),
        String(args[3] || "Overview"),
      );
      return;
    }
    switch (name) {
      case "startOpp": {
        const o = required(
          opportunities.find((o) => o.id === Number(id)),
          "opportunity",
        );
        patch("opportunity", o.id, { started: true });
        activity("Work started: " + o.title, String(o.client + 1));
        finish("Opportunity added to the client’s work queue.");
        break;
      }
      case "runRankScan":
      case "runWebsiteCheck":
        activity(
          name === "runRankScan"
            ? "Local ranking scan completed"
            : "Website technical check completed",
          id,
        );
        notify(
          name === "runRankScan"
            ? "Sample ranking scan completed."
            : "Sample technical check completed.",
        );
        break;
      case "savePost":
        patch("client", id, { postCopy: editor().value });
        activity("Scheduled GBP post updated", id);
        finish("Sample scheduled post updated.");
        break;
      case "saveContent":
        patch("page", id, { content: editor().value });
        finish("Content draft saved for this session.");
        break;
      case "updatePage": {
        const p = required(
          pageRecords.find((p) => p.id === id),
          "page",
        );
        patch("page", id, { status: "Indexed", health: 96, last: "Sep 29" });
        if (
          id === `${p.client}-2` &&
          client(p.client).workspaceProfile === "hospitality"
        ) {
          patch("client", p.client, { website: "Healthy", health: 96 });
          patch("action", 10, { done: true });
        }
        activity(p.name + " page updated", p.client);
        finish("Sample page updated. No live website was changed.");
        break;
      }
      case "markLead":
        patch("lead", id + "-" + index, { status: "Contacted" });
        activity("Sample lead marked contacted", id);
        finish("Lead status updated. No message was sent.");
        break;
      case "generateReviewResponse": {
        const r = required(
          reviewRecords.find((r) => r.id === id),
          "review",
        );
        editor().value =
          r.stars < 3
            ? `Thank you for bringing this to our attention, ${r.author.split(" ")[0]}. We’re sorry your appointment did not go as planned. Please contact our team so we can understand what happened and help resolve it.`
            : `Thank you for the thoughtful feedback, ${r.author.split(" ")[0]}. We’re glad you had a positive experience with our team and appreciate your recommendation.`;
        notify("Sample response generated. Edit it before publishing.");
        break;
      }
      case "saveReview": {
        const r = session.get(
          "review",
          id,
          required(
            reviewRecords.find((r) => r.id === id),
            "review",
          ),
        );
        const copy = editor().value.trim();
        if (!copy) {
          notify("Add a response before saving or publishing.");
          return;
        }
        let status = String(args[1]);
        if (
          status === "Published" &&
          client(r.client).responsePreference === "review" &&
          r.status !== "Awaiting approval"
        )
          status = "Awaiting approval";
        patch("review", id, { response: copy, status });
        if (status === "Published") {
          activity("Review response published in prototype", r.client);
          if (r.client === "4") patch("action", 5, { done: true });
        }
        finish(
          status === "Awaiting approval"
            ? "Response saved for client review, per this client’s preference."
            : status === "Published"
              ? "Sample response published. No real review was changed."
              : "Response draft saved.",
        );
        break;
      }
      case "stageReviewRequest": {
        const c = client(id);
        patch("client", id, {
          requestCopy: editor().value,
          requestCount: (c.requestCount || 0) + 1,
        });
        finish("Sample request staged. No email was sent.");
        break;
      }
      case "refreshConnection": {
        const c = client(id);
        if (
          (index === 0 && c.gbp !== "Healthy") ||
          (index === 2 && c.integration === "Not configured")
        ) {
          notify("Restore authorization or configure this source first.");
          return;
        }
        patch("client", id, { ["sync" + index]: "Just now" });
        activity(systems[index][0] + " sample data refreshed", id);
        finish("Sample source sync refreshed.");
        break;
      }
      case "markReport": {
        const status = String(args[1]);
        patch("report", id, {
          status,
          ...(status === "Sent" ? { date: "Sep 29" } : {}),
        });
        if (id === "7") patch("action", 4, { done: true });
        activity(
          status === "Sent"
            ? "Monthly report marked sent"
            : "Monthly report marked ready",
          String(Number(id) + 1),
        );
        finish(
          status === "Sent"
            ? "Marked sent in prototype. No email was sent."
            : "Report marked ready.",
        );
        break;
      }
      case "downloadReport":
        download(Number(id));
        break;
      case "downloadMonthlyReport":
        download(Number(root.dataset.clientId) - 1);
        break;
      case "completeAction": {
        const a = required(
          actions.find((a) => a.id === Number(id)),
          "action",
        );
        const c = client(String(a.client + 1));
        if (a.opportunityId) {
          dialogs.open("opportunity-" + a.opportunityId, trigger);
          return;
        }
        if (a.type === "Reports") {
          dialogs.open(`report-${a.client}`, trigger);
          return;
        }
        if (a.type === "Reviews") {
          location.href =
            route("client", c.id, "Reviews") +
            "?review=" +
            encodeURIComponent(c.id + "-r1");
          return;
        }
        if (a.type === "Automations") {
          dialogs.open("automation-" + c.id + "-a0", trigger);
          return;
        }
        patch("action", a.id, { done: true });
        if (a.type === "Rankings")
          patch("task", a.id, { title: a.next, client: c.id });
        if (a.type === "GBP" && a.severity === "Critical")
          patch("client", c.id, { gbp: "Healthy", integration: "Connected" });
        if (a.type === "Analytics")
          patch("client", c.id, {
            website: "Healthy",
            integration: "Connected",
          });
        if (a.type === "Integrations")
          patch("client", c.id, { integration: "Connected" });
        activity(a.title + " · action completed", c.id);
        finish(
          a.type === "Rankings"
            ? "Recovery task added to upcoming work."
            : "Sample action completed. No external account was changed.",
        );
        break;
      }
      case "runAutomation": {
        const r = required(
          automationRuns.find((r) => r.id === id),
          "automation",
        );
        const c = client(r.client);
        if (c.gbp === "Disconnected" && [0, 4].includes(r.def)) {
          notify("Reconnect this client’s GBP account before retrying.");
          return;
        }
        if (
          c.workspaceProfile === "hospitality" &&
          r.def === 3 &&
          c.website === "SEO issue"
        ) {
          notify("Repair the four legacy links before confirming this check.");
          return;
        }
        if (
          c.workspaceProfile === "hospitality" &&
          r.def === 1 &&
          c.responsePreference === "auto"
        )
          reviewRecords
            .filter((r) => r.client === c.id && r.status !== "Published")
            .forEach((r) =>
              patch("review", r.id, {
                response:
                  r.response ||
                  `Thank you for sharing your experience, ${r.author.split(" ")[0]}. We appreciate your visit to ${c.name} and your feedback.`,
                status: "Published",
              }),
            );
        patch("automation", id, {
          status: "Healthy",
          lastStatus: "Completed",
          last: "Just now",
          detail: "Completed successfully",
        });
        if (c.id === "3" && r.def === 0) patch("action", 8, { done: true });
        if (c.id === "3" && r.def === 4)
          patch("report", 2, {
            status: "Ready",
            note: "All sources available",
          });
        activity(automationDefs[r.def].name + " completed", c.id);
        finish("Sample run completed for " + c.name + ".");
        break;
      }
      case "setDemoRole": {
        sessionStorage.setItem("lilos-preview-role", id);
        applyRole(id);
        finish(
          "Navigation preview: " +
            (id === "owner" ? "Agency owner" : "Account manager"),
        );
        if (id !== "owner" && root.dataset.page === "administration")
          location.href = route();
        break;
      }
      default:
        throw new Error("Unknown sample action: " + name);
    }
  }
  function applyRole(role: string) {
    root
      .querySelectorAll<HTMLElement>("[data-owner-navigation]")
      .forEach((el) => (el.hidden = role === "manager"));
    root
      .querySelectorAll("[data-role-label]")
      .forEach(
        (el) =>
          (el.textContent =
            role === "manager" ? "Account manager" : "Agency owner"),
      );
  }
  function settings(form: HTMLFormElement) {
    const id = root.dataset.clientId;
    if (!id) return;
    const value = (field: string) =>
      required(
        form.querySelector<HTMLInputElement | HTMLSelectElement>("#" + field),
        "setting",
      ).value;
    patch("client", id, {
      name: value("settingname").trim(),
      location: value("settinglocation").trim(),
      category: value("settingcategory").trim(),
      contactEmail: value("settingemail"),
      responsePreference: value("settingapproval"),
      timezone: value("settingtimezone"),
    });
    notify("Client settings saved for this session.");
  }
  for (const [key, fields] of session.entries()) {
    const [entity, id] = key.split(":");
    patch(entity, id, fields);
  }
  renderActivity();
  applyRole(sessionStorage.getItem("lilos-preview-role") || "owner");

  return { execute, settings };
}
