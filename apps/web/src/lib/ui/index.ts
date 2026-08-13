export { badgeKindFor, badgeLabel, statusBadge, type BadgeKind } from "./badge";
export { describeFailure } from "./errors";
export {
  errorAlert,
  infoAlert,
  successAlert,
  emptyState,
  loadingState,
} from "./states";
export { showOnly, goToLogin, createRegions } from "./regions";
export {
  bootWorkspace,
  applyBootResult,
  populateSwitcher,
  setActiveOrganization,
  applyShellPrincipal,
  applyShellAudience,
  setPlatformNavigationVisible,
  setPlatformAdminStatus,
  isPlatformAdmin,
  hasPlatformAdminGrant,
  meetsPlatformAdminRequiredAssurance,
  canUsePlatformAdministration,
  setProductNavigationVisibility,
  onOrganizationChanged,
  type BootRegions,
  type BootContext,
  type BootResult,
  type PlatformAdminCapability,
} from "./boot";
export {
  buildDataTable,
  cellText,
  cellBadge,
  cellMeta,
  formatTimestamp,
  formatDate,
  relativeTime,
  type TableColumn,
} from "./table";
export {
  card,
  cardBody,
  sectionCard,
  detailFact,
  liveStatus,
  metricCard,
  metricGrid,
  sectionHeader,
  actionButton,
  linkButton,
} from "./components";
export {
  formField,
  textInput,
  selectInput,
  textArea,
  formActions,
  formSection,
  confirmInline,
} from "./forms";
export { setupTabs } from "./tabs";
