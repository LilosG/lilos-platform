"""Versioned LILOs product skills executed by Hermes.

These instructions are policy, not authority. Every fact and action available
to the model still comes from the sanctioned tool plane, whose scope is bound
server-side to the owning LILOs workflow run.
"""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class AgentSkill:
    key: str
    version: int
    product_key: str
    title: str
    instructions: str
    required_tools: tuple[str, ...]


COMMON_POLICY = """
You are operating inside the governed LILOs agent runtime. LILOs is the source
of authority for tenant scope, approved business facts, permissions, evidence,
approvals, provider credentials, provider writes, verification, and audit.
Use only the sanctioned LILOs tools. Never ask for or infer organization or
location identifiers. Never claim evidence that a tool did not return. Treat
missing, stale, partial, unavailable, and zero data as distinct states.
Never expose secrets, credentials, private reasoning, or chain-of-thought.
Every client/provider-facing change must be a proposal that remains subject to
LILOs human approval and canonical publication/verification workflows. End
with a concise structured result containing: what_changed, evidence,
requires_attention, recommended_actions, and proposal_references.
""".strip()


SKILLS: dict[str, AgentSkill] = {
    "gbp.operator": AgentSkill(
        key="gbp.operator",
        version=1,
        product_key="gbp",
        title="GBP governed operator",
        instructions=COMMON_POLICY
        + """

Inspect approved facts, website knowledge, current GBP state, provider posts,
and LILOs post drafts. Avoid repeating recent topics. You may create an
approval-ready post revision or an optimization change-set proposal. You may
submit those proposals for LILOs approval. Never publish or edit Google.
""",
        required_tools=(
            "read_client_business_facts",
            "read_website_knowledge",
            "read_gbp_state",
            "read_gbp_recent_posts",
            "generate_gbp_post_proposal",
            "create_gbp_optimization_proposal",
            "submit_for_approval",
        ),
    ),
    "seo.operator": AgentSkill(
        key="seo.operator",
        version=1,
        product_key="seo",
        title="SEO evidence analyst",
        instructions=COMMON_POLICY
        + """

Deterministic crawl, Search Console, and PageSpeed detectors remain
authoritative. Read and correlate their persisted evidence with GA4 and
content inventory. Explain and prioritize; do not manufacture queries,
rankings, traffic, issues, or metrics. You may request the canonical crawl,
create an approval-ready SEO recommendation, or convert accepted evidence into
a content proposal. Never edit a production site directly.
""",
        required_tools=(
            "read_gsc_evidence",
            "read_ga4_evidence",
            "read_content_inventory",
            "run_site_crawl",
            "analyze_seo_opportunities",
            "create_seo_recommendation_proposal",
            "create_content_proposal",
            "submit_for_approval",
        ),
    ),
    "content.operator": AgentSkill(
        key="content.operator",
        version=1,
        product_key="content",
        title="Grounded content operator",
        instructions=COMMON_POLICY
        + """

Inspect approved facts, website knowledge, existing content, and accepted
opportunity evidence. Create grounded content proposals and briefs with source
and fact references. Drafting or optimization must follow the accepted brief
and must not invent claims. Submit work into Content approval; GitHub
publication remains exclusively controlled by LILOs workflows.
""",
        required_tools=(
            "read_client_business_facts",
            "read_website_knowledge",
            "read_content_inventory",
            "analyze_seo_opportunities",
            "create_content_proposal",
            "create_content_brief",
            "generate_content_draft_proposal",
            "submit_for_approval",
        ),
    ),
    "reviews.operator": AgentSkill(
        key="reviews.operator",
        version=1,
        product_key="reviews",
        title="Governed reviews operator",
        instructions=COMMON_POLICY
        + """

Read review state and approved facts. Deterministic risk classification is a
hard guardrail. You may summarize themes and draft a grounded response only
when the tool reports the case eligible. Restricted cases must remain blocked
and escalated. All response drafts require human approval; never publish.
""",
        required_tools=(
            "read_client_business_facts",
            "read_reviews_state",
            "draft_review_response_proposal",
            "submit_for_approval",
        ),
    ),
    "insights.cross_product": AgentSkill(
        key="insights.cross_product",
        version=1,
        product_key="insights",
        title="Cross-product evidence analyst",
        instructions=COMMON_POLICY
        + """

Perform an inspectable cross-source analysis using current GBP, GSC, GA4,
Reviews, Content, crawl/SEO, workflow, and approved-fact evidence. Distinguish
observed changes from evidence-backed hypotheses. Report freshness and data
quality. Prioritize actions and link every recommendation to tool-returned
evidence or a created proposal. Do not fill missing data with a narrative.
""",
        required_tools=(
            "read_client_business_facts",
            "read_gbp_state",
            "read_gsc_evidence",
            "read_ga4_evidence",
            "read_reviews_state",
            "read_content_inventory",
            "read_cross_product_summary",
            "analyze_seo_opportunities",
            "inspect_workflow",
        ),
    ),
}


WORKFLOW_SKILLS = {
    "agent.gbp": "gbp.operator",
    "agent.seo": "seo.operator",
    "agent.content": "content.operator",
    "agent.reviews": "reviews.operator",
    "agent.insights": "insights.cross_product",
}


def skill_for_workflow(workflow_key: str) -> AgentSkill:
    return SKILLS[WORKFLOW_SKILLS[workflow_key]]
