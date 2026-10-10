import { z } from "zod";
import type { components } from "@lilos/contracts/api";
const repository = z.object({
  repository_id: z.string().min(1),
  name: z.string().min(1),
  default_branch: z.string().min(1),
  private: z.boolean(),
  format_verified: z.boolean(),
  suggested: z.boolean(),
});
export type PublishingRepository =
  components["schemas"]["PublishingRepository"];
export type PublishingSetup = components["schemas"]["PublishingSetup"];
/** The repositories a client's GitHub installation can reach; anything malformed fails closed. */
export function adaptRepositories(payload: unknown): PublishingRepository[] {
  const parsed = z
    .object({ repositories: z.array(repository) })
    .parse(payload).repositories;
  if (new Set(parsed.map((r) => r.repository_id)).size !== parsed.length)
    throw new Error("REPOSITORY_DUPLICATED");
  if (parsed.filter((r) => r.suggested).length > 1)
    throw new Error("SUGGESTION_AMBIGUOUS");
  return parsed;
}
