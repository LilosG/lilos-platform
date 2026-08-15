import { statusLabel, statusTone } from "../status-language";

export type ActionName =
  | "approve"
  | "configure"
  | "connect"
  | "map"
  | "open"
  | "publish"
  | "resolve"
  | "retry"
  | "review"
  | "save"
  | "sync";

export type ActionPhase = "idle" | "working" | "complete";

export interface ActionLanguage {
  idle: string;
  working: string;
  complete: string;
}

export interface EmptyStateContent {
  heading: string;
  situation: string;
  action?: {
    label: string;
    href: string;
  };
}

export interface ErrorContent {
  title: string;
  description: string;
  recovery: {
    label: string;
    href?: string;
  };
}

export const ACTION_LANGUAGE: Record<ActionName, ActionLanguage> = {
  approve: { idle: "Approve", working: "Approving…", complete: "Approved" },
  configure: {
    idle: "Configure",
    working: "Configuring…",
    complete: "Configured",
  },
  connect: { idle: "Connect", working: "Connecting…", complete: "Connected" },
  map: { idle: "Map", working: "Mapping…", complete: "Mapped" },
  open: { idle: "Open", working: "Opening…", complete: "Opened" },
  publish: { idle: "Publish", working: "Publishing…", complete: "Published" },
  resolve: { idle: "Resolve", working: "Resolving…", complete: "Resolved" },
  retry: { idle: "Retry", working: "Retrying…", complete: "Retried" },
  review: { idle: "Review", working: "Opening review…", complete: "Reviewed" },
  save: { idle: "Save", working: "Saving…", complete: "Saved" },
  sync: { idle: "Sync", working: "Syncing…", complete: "Synced" },
};

export function actionLabel(
  action: ActionName,
  phase: ActionPhase = "idle",
): string {
  return ACTION_LANGUAGE[action][phase];
}

export function statusPresentation(status: string | null | undefined): {
  label: string;
  tone: string;
} {
  return { label: statusLabel(status), tone: statusTone(status) };
}

export function emptyStateContent(
  content: EmptyStateContent,
): EmptyStateContent {
  if (!content.heading.trim() || !content.situation.trim()) {
    throw new Error(
      "Empty states require one heading and one situation statement.",
    );
  }
  if (
    content.action &&
    (!content.action.label.trim() || !content.action.href.trim())
  ) {
    throw new Error(
      "Empty-state actions require both a label and destination.",
    );
  }
  return content;
}

export function errorContent(args: {
  operation: string;
  happened: string;
  recovery: string;
  recoveryLabel: string;
  recoveryHref?: string;
}): ErrorContent {
  const operation = args.operation.trim();
  const happened = args.happened.trim();
  const recovery = args.recovery.trim();
  if (!operation || !happened || !recovery || !args.recoveryLabel.trim()) {
    throw new Error(
      "Errors require an operation, explanation, recovery instruction, and recovery action.",
    );
  }
  return {
    title: `Could not ${operation}`,
    description: `${happened} ${recovery}`,
    recovery: {
      label: args.recoveryLabel,
      href: args.recoveryHref,
    },
  };
}
