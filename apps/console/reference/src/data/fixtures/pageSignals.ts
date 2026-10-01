import type { Client, WebsitePage } from "../../types/domain";
export function pageSignals(page: WebsitePage, client: Client): string {
  if (client.workspaceProfile === "hospitality")
    return page.status === "Issue"
      ? "Four internal links use a legacy private-events URL. Update the centralized link data."
      : page.status === "Draft"
        ? "Brunch content is drafted. There are no measured sessions or search clicks before publication."
        : "Canonical and indexing signals are healthy. Review query coverage and the next guest action.";
  return page.status === "Issue"
    ? "Four internal links point to retired service URLs. Update the shared link data."
    : page.status === "Draft"
      ? "Content is drafted and ready for editing. Publishing is optional when the page is ready."
      : "Canonical and index signals are healthy. Review internal links and relevant query coverage at the next content update.";
}
export function legacyLinkFinding(client: Client) {
  return client.website === "SEO issue"
    ? {
        title: "Private-event links pass through two redirects",
        description:
          "Four shared links point to a retired event URL. Update centralized content links.",
        status: "Issue",
      }
    : {
        title: "Private-event links are direct",
        description:
          "The shared links were updated and their destinations checked.",
        status: "Healthy",
      };
}
