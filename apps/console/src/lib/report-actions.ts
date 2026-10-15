import { z } from "zod";
import { ApiFailure, call } from "./api-client";
import { confirmDialog, openConfirm } from "./confirm-dialog";
import {
  approveCopy,
  compareHelp,
  draftFailureText,
  periodErrorText,
  reportFailureText,
  sendCopy,
} from "./report-view";
import {
  PREVIOUS,
  baselineError,
  comparisonBody,
  comparisonFromQuery,
  periodError,
  reportHref,
  type ComparisonRef,
  type PeriodRef,
  type PresetId,
} from "./report-period";
import { FAILURE_CODES } from "../adapters/reports";
const codeOf = (error: unknown) =>
  error instanceof ApiFailure ? error.code : "UNKNOWN";
const failure = z.enum(FAILURE_CODES);
const drafted = z.object({
  outcome: z.enum(["drafted", "not_used"]),
  failure: failure.nullable().optional(),
});
const generated = z.object({
  report: z.object({ revision: z.number().int().min(1) }),
});
function say(text: string, error = false) {
  const status = document.querySelector<HTMLElement>("[data-report-status]");
  if (!status) return;
  status.textContent = text;
  status.classList.toggle("error", error);
}
function bindNewReport() {
  const form = document.querySelector<HTMLFormElement>("[data-new-report]");
  if (!form) return;
  const lastEnded = form.dataset.lastEnded!;
  const presets = JSON.parse(form.dataset.presets!) as Record<
    PresetId,
    PeriodRef
  >;
  const field = <T extends HTMLElement>(selector: string) =>
    form.querySelector<T>(selector)!;
  const select = (name: string) =>
    field<HTMLSelectElement>(`select[name="${name}"]`);
  // The button sits in the dialog's footer, outside the form, and submits it by id.
  const submit = document.querySelector<HTMLButtonElement>(
    "[data-generate-submit]",
  )!;
  const period = (): PeriodRef => ({
    start: select("start").value,
    end: select("end").value,
  });
  const comparison = (): ComparisonRef => {
    const chosen = select("compare").value;
    if (chosen === "year-ago") return { kind: "year-ago" };
    if (chosen === "baseline")
      return {
        kind: "baseline",
        start: select("baseline_start").value,
        end: select("baseline_end").value,
      };
    return PREVIOUS;
  };
  const show = (name: string, text: string | null) => {
    const element = field<HTMLElement>(`[data-error-for="${name}"]`);
    element.hidden = text === null;
    element.textContent = text ?? "";
  };
  const validate = () => {
    const wrong = periodError(period(), lastEnded);
    const chosen = comparison();
    const baseline =
      chosen.kind === "baseline" ? baselineError(chosen, period()) : null;
    show("period", wrong ? periodErrorText[wrong] : null);
    show("baseline", baseline ? periodErrorText[baseline] : null);
    submit.disabled = wrong !== null || baseline !== null;
    return !submit.disabled;
  };
  const matching = () =>
    (Object.entries(presets) as [PresetId, PeriodRef][]).find(
      ([, value]) =>
        value.start === period().start && value.end === period().end,
    )?.[0] ?? "custom";
  select("preset").addEventListener("change", () => {
    const chosen = select("preset").value as PresetId | "custom";
    if (chosen !== "custom") {
      select("start").value = presets[chosen].start;
      select("end").value = presets[chosen].end;
    }
    validate();
  });
  for (const name of ["start", "end"])
    select(name).addEventListener("change", () => {
      select("preset").value = matching();
      validate();
    });
  select("compare").addEventListener("change", () => {
    const chosen = select("compare").value;
    field<HTMLElement>("[data-baseline]").hidden = chosen !== "baseline";
    field<HTMLElement>("[data-compare-help]").textContent =
      compareHelp[chosen as keyof typeof compareHelp];
    validate();
  });
  for (const name of ["baseline_start", "baseline_end"])
    select(name).addEventListener("change", validate);
  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!validate()) return;
    submit.disabled = true;
    say("Generating the report…");
    const chosen = comparison();
    try {
      const result = generated.parse(
        await call(form.dataset.api!, {
          start_month: period().start,
          end_month: period().end,
          comparison: comparisonBody(chosen),
        }),
      );
      window.location.assign(
        reportHref(form.dataset.clientSlug!, period(), chosen, {
          revision: result.report.revision,
        }),
      );
    } catch (error) {
      say(reportFailureText(codeOf(error)), true);
      submit.disabled = false;
    }
  });
  validate();
}
function bindPage() {
  const page = document.querySelector<HTMLElement>("[data-report-page]");
  if (!page) return;
  const api = page.dataset.api!;
  const one = `${api}${page.dataset.period}/${page.dataset.comparison}/${page.dataset.revision}/`;
  const client = page.dataset.client!;
  const period: PeriodRef = {
    start: page.dataset.start!,
    end: page.dataset.end!,
  };
  const field = (name: string) =>
    page.querySelector<HTMLTextAreaElement>(`textarea[name="${name}"]`);
  const body = () => ({
    what_changed: field("what_changed")?.value ?? "",
    next_work: field("next_work")?.value ?? "",
  });
  const buttons = (selector: string) =>
    page.querySelectorAll<HTMLButtonElement>(selector);
  buttons("[inert]").forEach((button) => button.removeAttribute("inert"));
  buttons("[data-report-save]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      say("Saving…");
      try {
        await call(`${one}narrative/`, body(), "PUT");
        say("Narrative saved.");
      } catch (error) {
        say(reportFailureText(codeOf(error)), true);
      }
      button.disabled = false;
    }),
  );
  buttons("[data-report-draft]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      say("Drafting with Hermes…");
      try {
        const result = drafted.parse(await call(`${one}draft-narrative/`, {}));
        if (result.outcome === "drafted") window.location.reload();
        else {
          say(
            result.failure
              ? draftFailureText[result.failure]
              : draftFailureText.draft_failed,
            true,
          );
          button.disabled = false;
        }
      } catch (error) {
        say(reportFailureText(codeOf(error)), true);
        button.disabled = false;
      }
    }),
  );
  buttons("[data-report-regenerate]").forEach((button) =>
    button.addEventListener("click", async () => {
      button.disabled = true;
      say("Recomputing from the latest data…");
      try {
        const result = generated.parse(
          await call(`${api}generate/`, {
            start_month: period.start,
            end_month: period.end,
            comparison: JSON.parse(page.dataset.comparisonBody!),
          }),
        );
        window.location.assign(
          reportHref(
            page.dataset.clientSlug!,
            period,
            comparisonFromQuery(page.dataset.vs!) ?? PREVIOUS,
            { revision: result.report.revision },
          ),
        );
      } catch (error) {
        say(reportFailureText(codeOf(error)), true);
        button.disabled = false;
      }
    }),
  );
  const dialog = confirmDialog("report-confirm");
  if (!dialog) return;
  buttons("[data-report-approve]").forEach((button) =>
    button.addEventListener("click", () =>
      openConfirm(
        dialog,
        { ...approveCopy(client, period), tone: "normal" },
        {
          work: async () => {
            // A narrative typed but not yet saved is approved as shown on screen.
            await call(`${one}narrative/`, body(), "PUT").catch(
              () => undefined,
            );
            await call(`${one}approve/`, {});
          },
          failure: (error) => reportFailureText(codeOf(error)),
        },
      ),
    ),
  );
  buttons("[data-report-send]").forEach((button) =>
    button.addEventListener("click", () => {
      const sentOn =
        page.querySelector<HTMLInputElement>("input[name=sent_on]")?.value ??
        "";
      if (!sentOn) {
        say("Choose the day you sent it first.", true);
        return;
      }
      openConfirm(
        dialog,
        { ...sendCopy(client, period, sentOn), tone: "normal" },
        {
          work: async () => {
            await call(`${one}mark-sent/`, { sent_on: sentOn });
          },
          failure: (error) => reportFailureText(codeOf(error)),
        },
      );
    }),
  );
}
bindNewReport();
bindPage();
