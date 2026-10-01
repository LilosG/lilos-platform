export type ProductArea =
  | "Overview"
  | "Local Search"
  | "Reviews"
  | "Website & Content"
  | "Leads"
  | "Opportunities"
  | "Automations"
  | "Reports"
  | "Integrations"
  | "Settings";
export type MetricSource =
  | "GA4"
  | "Search Console"
  | "GBP"
  | "GBP Reviews"
  | "Local ranking scan"
  | "Website health check"
  | "Client monitoring";
export interface ReportingPeriod {
  days: "7" | "30" | "90";
  label: string;
  multiplier: number;
}
export interface Metric {
  label: string;
  value: string | number;
  description: string;
  source?: MetricSource;
  unit?:
    | "sessions"
    | "events"
    | "clicks"
    | "impressions"
    | "rank"
    | "percent"
    | "rating"
    | "count";
}
export interface Location {
  id: string;
  clientId: string;
  name: string;
  address: string;
}
export interface Client {
  id: string;
  slug: string;
  workspaceProfile: "standard" | "hospitality";
  name: string;
  location: string;
  category: string;
  locations: number;
  visibility: number;
  change: number;
  rank: number;
  traffic: number;
  leads: number;
  rating: number;
  reviews: number;
  newReviews: number;
  gbp: string;
  website: string;
  integration: string;
  status: string;
  activity: string;
  next: string;
  organic: number;
  health: number;
  top3: number;
  notfound: number;
  leadChange?: number;
  tasks?: string[];
  postCopy?: string;
  contactEmail?: string;
  responsePreference?: "direct" | "review" | "auto";
  timezone?: string;
  requestCopy?: string;
  requestCount?: number;
  leadStatuses?: Record<number, string>;
  sourceSync?: Record<number, string>;
}
export interface Evidence {
  headline: string;
  metrics: [string, string][];
  sources: string[];
  detected: string;
  period: string;
}
export interface Opportunity {
  id: number;
  client: number;
  type: string;
  kind: "Issue" | "Growth Opportunity" | "Optimization" | "Data & Tracking";
  title: string;
  impact: "High" | "Medium";
  why: string;
  discovered?: string;
  evidence: string;
  metrics: [string, string][];
  sources: string[];
  detected: string;
  detail: string;
  next: string;
  effort: string;
  gain: string;
  area: ProductArea;
  section: string;
  started?: boolean;
}
export interface Attention {
  opportunityId?: number;
  workspaceTitle?: string;
  id: number;
  client: number;
  title: string;
  severity: string;
  time: string;
  type: string;
  next: string;
  impact: string;
  button: string;
  done?: boolean;
}
export interface Review {
  id: string;
  client: string;
  author: string;
  stars: number;
  text: string;
  sentiment: string;
  date: string;
  status: string;
  response: string;
}
export interface Ranking {
  query: string;
  rank: number;
  prior: number;
  top3: number;
  top10: number;
}
export interface SearchQuery extends Ranking {
  clicks: number;
  impressions: number;
  position: number;
  page: string;
}
export interface Lead {
  id: string;
  clientId: string;
  contact: string;
  inquiry: string;
  message: string;
  source: string;
  displaySource: string;
  received: string;
  status: string;
}
export interface ConversionEvent {
  name: string;
  label: string;
  description: string;
  source: string;
  count: number;
  completedOutcome: boolean;
}
export interface Report {
  id: number;
  client: number;
  status: string;
  period: string;
  date: string;
  note: string;
}
export interface HistoricalReport {
  client: string;
  period: string;
  sent: string;
  leads: number;
  visibility: number;
}
export interface Automation {
  id: string;
  client: string;
  def: number;
  status: string;
  lastStatus: string;
  last: string;
  next: string;
  detail: string;
}
export interface AutomationDefinition {
  name: string;
  frequency: string;
  next: string;
  last: string;
  source: string;
}
export type Integration = [
  name: string,
  abbreviation: string,
  status: string,
  connectedClients: number,
  note: string,
  capabilities: string,
];
export interface Activity {
  client: number;
  text: string;
  time: string;
}
export interface Insight {
  title: string;
  description: string;
  area: ProductArea;
  section: string;
  opportunityId?: number;
}
export interface WebsitePage {
  id: string;
  client: string;
  name: string;
  url: string;
  status: string;
  clicks: number;
  sessions?: number;
  health: number;
  last: string;
  content?: string;
}
export interface ViewState {
  page: string;
  client: string | null;
  tab: string;
  subtab: string;
  filter: string;
  query: string;
  sort: string;
  range: "7" | "30" | "90";
  oppType: string;
  reportFilter: string;
  systemFilter: string;
  role: "owner" | "manager";
  adminTab: string;
  automationFilter: string;
  reviewFilter: string;
  oppPriority: string;
  oppClient: string;
  automationView: string;
  automationStatus: string;
  automationClient: string;
  automationType: string;
  oppKind: string;
}
export interface ViewContext {
  state: ViewState;
  client?: Client;
}
export type DisplayValue = string | number | { base: number; format?: string };

export type MetricPresentation = readonly [
  label: DisplayValue,
  value: DisplayValue,
  description: DisplayValue,
];
