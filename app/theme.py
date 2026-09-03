from __future__ import annotations


# Phase 10 light visual system.
# Keep these values centralized so pages/components do not grow their own
# unrelated color systems.
COLORS = {
    "app_background": "#F6F7F9",
    "sidebar": "#F1F3F6",
    "surface": "#FFFFFF",
    "surface_subtle": "#FAFBFC",
    "border": "#E2E5EA",
    "border_strong": "#D5DAE2",
    "text_primary": "#181B20",
    "text_secondary": "#717784",
    "text_muted": "#9299A6",
    "accent": "#4F46E5",
    "accent_hover": "#4338CA",
    "accent_pressed": "#3730A3",
    "accent_soft": "#EEF2FF",
    "focus": "#6366F1",
    "recorded": "#22C55E",
    "recorded_soft": "#DCFCE7",
    "ready_to_stem": "#4F46E5",
    "ready_to_stem_soft": "#EEF2FF",
    "stemmed": "#0F766E",
    "stemmed_soft": "#CCFBF1",
    "attention": "#F59E0B",
    "attention_soft": "#FEF3C7",
    "source_revised": "#F97316",
    "source_revised_soft": "#FFEDD5",
    "revision": "#8B5CF6",
    "revision_soft": "#EDE9FE",
    "delivered": "#3B82F6",
    "delivered_soft": "#DBEAFE",
    "error": "#EF4444",
    "error_soft": "#FEE2E2",
    "neutral": "#94A3B8",
    "neutral_soft": "#F1F5F9",
    # Dark semantic foregrounds for text rendered on the corresponding
    # soft status backgrounds. Accent colors stay available for borders/icons.
    "recorded_text": "#166534",
    "ready_to_stem_text": "#4338CA",
    "stemmed_text": "#115E59",
    "attention_text": "#92400E",
    "source_revised_text": "#9A3412",
    "revision_text": "#6D28D9",
    "delivered_text": "#1D4ED8",
    "error_text": "#B91C1C",
    "neutral_text": "#475569",
}

SPACING = {
    "xs": 4,
    "sm": 8,
    "md": 12,
    "lg": 16,
    "xl": 24,
    "xxl": 32,
}

RADII = {
    "sm": 6,
    "md": 8,
    "lg": 12,
}

CONTROL_HEIGHT = 34
COMPACT_CONTROL_HEIGHT = 30
SIDEBAR_WIDTH = 184


APP_STYLESHEET = f"""
QMainWindow {{
    background: {COLORS["app_background"]};
}}

QWidget {{
    color: {COLORS["text_primary"]};
    font-family: "Segoe UI";
    font-size: 10pt;
}}

/* ------------------------------------------------------------------
   Phase 10 application shell
   ------------------------------------------------------------------ */

#AppShell {{
    background: {COLORS["app_background"]};
}}

#AppSidebar {{
    background: {COLORS["sidebar"]};
    border-right: 1px solid {COLORS["border"]};
}}

#SidebarBrand {{
    background: transparent;
}}

#SidebarBrandMark {{
    background: {COLORS["accent"]};
    color: #FFFFFF;
    border-radius: 9px;
    font-size: 11pt;
    font-weight: 800;
}}

#SidebarBrandTitle {{
    color: {COLORS["text_primary"]};
    font-size: 11pt;
    font-weight: 700;
}}

#SidebarBrandVersion {{
    color: {COLORS["text_muted"]};
    font-size: 8pt;
}}

QPushButton[sidebarNav="true"] {{
    background: transparent;
    color: {COLORS["text_secondary"]};
    border: 0px;
    border-radius: {RADII["md"]}px;
    min-height: 38px;
    padding: 0px 12px;
    text-align: left;
    font-weight: 600;
}}

QPushButton[sidebarNav="true"]:hover {{
    background: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
}}

QPushButton[sidebarNav="true"]:checked {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["accent"]};
    font-weight: 700;
}}

QPushButton[sidebarNav="true"]:focus {{
    border: 1px solid {COLORS["focus"]};
}}

#SidebarDivider {{
    background: {COLORS["border"]};
    max-height: 1px;
}}

#SidebarFooter {{
    color: {COLORS["text_muted"]};
    font-size: 8pt;
    padding: 8px 12px 12px 12px;
}}

#PageHeader {{
    background: {COLORS["surface"]};
    border-bottom: 1px solid {COLORS["border"]};
}}

#HeaderTitle {{
    color: {COLORS["text_primary"]};
    font-size: 20pt;
    font-weight: 700;
}}

#HeaderSubtitle {{
    color: {COLORS["text_secondary"]};
    font-size: 9.5pt;
}}

QPushButton[headerPrimary="true"] {{
    background: {COLORS["accent"]};
    color: #FFFFFF;
    border: 1px solid {COLORS["accent"]};
    border-radius: {RADII["md"]}px;
    min-height: {CONTROL_HEIGHT}px;
    padding: 0px 14px;
    font-weight: 700;
}}

QPushButton[headerPrimary="true"]:hover {{
    background: {COLORS["accent_hover"]};
    border-color: {COLORS["accent_hover"]};
}}

QPushButton[headerPrimary="true"]:pressed {{
    background: {COLORS["accent_pressed"]};
    border-color: {COLORS["accent_pressed"]};
}}

QPushButton[headerSecondary="true"],
QToolButton[headerOverflow="true"] {{
    background: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_strong"]};
    border-radius: {RADII["md"]}px;
    min-height: {CONTROL_HEIGHT}px;
    padding: 0px 12px;
    font-weight: 600;
}}

QPushButton[headerSecondary="true"]:hover,
QToolButton[headerOverflow="true"]:hover {{
    background: {COLORS["surface_subtle"]};
    border-color: {COLORS["focus"]};
}}

QPushButton[headerPrimary="true"]:focus,
QPushButton[headerSecondary="true"]:focus,
QToolButton[headerOverflow="true"]:focus {{
    border: 2px solid {COLORS["focus"]};
}}

QMenu {{
    background: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["md"]}px;
    padding: 6px;
}}

QMenu::item {{
    border-radius: {RADII["sm"]}px;
    padding: 7px 20px 7px 10px;
}}

QMenu::item:selected {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["accent"]};
}}

/* ------------------------------------------------------------------
   Existing page components, normalized to the new visual system
   ------------------------------------------------------------------ */

#ContextPanel {{
    background: {COLORS["surface"]};
    border-right: 1px solid {COLORS["border"]};
}}

#ContextPanel QLabel {{
    padding-left: 7px;
    padding-right: 4px;
}}

#Workspace {{
    background: {COLORS["surface"]};
}}

#SectionTitle {{
    font-size: 9pt;
    font-weight: 700;
    color: {COLORS["text_secondary"]};
    padding-left: 7px;
    padding-right: 5px;
    padding-top: 2px;
    padding-bottom: 2px;
}}

#PageTitle {{
    font-size: 18pt;
    font-weight: 650;
    color: {COLORS["text_primary"]};
    padding-left: 7px;
    padding-right: 5px;
}}

#PageSubtitle {{
    color: {COLORS["text_secondary"]};
    padding-left: 7px;
    padding-right: 5px;
}}

#DashboardCard {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["lg"]}px;
}}

#CardValue {{
    font-size: 23pt;
    font-weight: 650;
    color: {COLORS["accent"]};
}}

#CardLabel {{
    color: {COLORS["text_secondary"]};
}}

QLineEdit,
QComboBox,
QSpinBox,
QDateEdit {{
    background: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_strong"]};
    border-radius: {RADII["sm"]}px;
    padding: 5px 8px;
    min-height: 24px;
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text_primary"]};
}}

QLineEdit:focus,
QComboBox:focus,
QSpinBox:focus,
QDateEdit:focus {{
    border: 1px solid {COLORS["focus"]};
}}

QPushButton[primary="true"] {{
    background: {COLORS["accent"]};
    color: #FFFFFF;
    border: 1px solid {COLORS["accent"]};
    border-radius: {RADII["sm"]}px;
    padding: 7px 12px;
    font-weight: 700;
}}

QPushButton[primary="true"]:hover {{
    background: {COLORS["accent_hover"]};
}}

QPushButton[secondary="true"] {{
    background: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border_strong"]};
    border-radius: {RADII["sm"]}px;
    padding: 7px 12px;
}}

QPushButton[secondary="true"]:hover {{
    background: {COLORS["surface_subtle"]};
    border-color: {COLORS["focus"]};
}}

QCheckBox {{
    min-width: 31px;
    max-width: 31px;
    min-height: 30px;
    max-height: 30px;
    spacing: 0px;
    padding-left: 6px;
}}

QCheckBox::indicator {{
    width: 19px;
    height: 19px;
}}

QCheckBox::indicator:unchecked {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["neutral"]};
    border-radius: 4px;
}}

QCheckBox::indicator:unchecked:hover {{
    background: {COLORS["accent_soft"]};
    border: 2px solid {COLORS["accent"]};
}}

QTableWidget,
QTableView {{
    background: {COLORS["surface"]};
    alternate-background-color: {COLORS["surface_subtle"]};
    border: 1px solid {COLORS["border"]};
    gridline-color: {COLORS["border"]};
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text_primary"]};
}}

QHeaderView::section {{
    background: {COLORS["surface_subtle"]};
    color: {COLORS["text_secondary"]};
    border: none;
    border-right: 1px solid {COLORS["border"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 7px;
    font-weight: 700;
}}

QStatusBar {{
    background: {COLORS["surface"]};
    color: {COLORS["text_secondary"]};
    border-top: 1px solid {COLORS["border"]};
    min-height: 25px;
    max-height: 25px;
    font-weight: 500;
}}

QStatusBar QLabel {{
    color: {COLORS["text_secondary"]};
    padding: 0px 6px;
}}

QProgressBar {{
    background: {COLORS["neutral_soft"]};
    border: 0px;
    border-radius: 5px;
    min-height: 10px;
    max-height: 10px;
    text-align: center;
    color: transparent;
}}

QProgressBar::chunk {{
    background: {COLORS["accent"]};
    border-radius: 5px;
}}

/* ------------------------------------------------------------------
   Phase 10 PROJECT workspace
   ------------------------------------------------------------------ */

#ProjectWorkspace,
#ProjectScrollArea,
#ProjectScrollArea > QWidget > QWidget,
#ProjectBody {{
    background: {COLORS["app_background"]};
}}

#ProjectIdentityCard,
#ProjectPanel,
#ProjectMetricCard,
#ProjectEmptyActions {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["lg"]}px;
}}

#ProjectIdentityName {{
    color: {COLORS["text_primary"]};
    font-size: 16pt;
    font-weight: 700;
}}

#ProjectIdentityMeta {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
}}

#ProjectMetaKey {{
    color: {COLORS["text_muted"]};
    font-size: 8pt;
    font-weight: 700;
}}

#ProjectMetaValue {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
}}

#ProjectSectionTitle {{
    color: {COLORS["text_primary"]};
    font-size: 9pt;
    font-weight: 800;
    padding: 0px;
}}

#ProjectSectionHelper,
#ProjectEmptyHint {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
}}

#ProjectMetricCard {{
    min-width: 118px;
}}

#ProjectMetricValue {{
    color: {COLORS["text_primary"]};
    font-size: 21pt;
    font-weight: 700;
}}

#ProjectMetricLabel {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
    font-weight: 650;
}}

#ProjectMetricDetail {{
    color: {COLORS["text_muted"]};
    font-size: 8pt;
}}

#ProjectHealthBadge {{
    border-radius: 10px;
    padding: 4px 9px;
    font-size: 8pt;
    font-weight: 800;
}}

#ProjectHealthBadge[healthState="NEUTRAL"] {{
    background: {COLORS["neutral_soft"]};
    color: {COLORS["neutral_text"]};
}}

#ProjectHealthBadge[healthState="HEALTHY"] {{
    background: {COLORS["recorded_soft"]};
    color: {COLORS["recorded_text"]};
}}

#ProjectHealthBadge[healthState="ATTENTION"] {{
    background: {COLORS["attention_soft"]};
    color: {COLORS["attention_text"]};
}}

#ProjectHealthBadge[healthState="ERROR"] {{
    background: {COLORS["error_soft"]};
    color: {COLORS["error_text"]};
}}

#ProjectHealthBanner {{
    background: {COLORS["surface_subtle"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["md"]}px;
}}

#ProjectHealthTitle {{
    color: {COLORS["text_primary"]};
    font-weight: 700;
}}

#ProjectHealthText {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
}}

QPushButton[attentionAction="true"] {{
    background: {COLORS["surface_subtle"]};
    color: {COLORS["text_primary"]};
    border: 1px solid {COLORS["border"]};
    border-left: 4px solid {COLORS["neutral"]};
    border-radius: {RADII["md"]}px;
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
}}

QPushButton[attentionAction="true"]:hover {{
    background: {COLORS["accent_soft"]};
    border-color: {COLORS["focus"]};
}}

QPushButton[attentionAction="true"][dashboardSeverity="ERROR"] {{
    border-left-color: {COLORS["error"]};
}}

QPushButton[attentionAction="true"][dashboardSeverity="WARNING"] {{
    border-left-color: {COLORS["attention"]};
}}

QPushButton[attentionAction="true"][dashboardSeverity="INFO"] {{
    border-left-color: {COLORS["delivered"]};
}}

#ProjectCleanState {{
    background: {COLORS["recorded_soft"]};
    color: {COLORS["recorded"]};
    border-radius: {RADII["md"]}px;
    padding: 10px 12px;
    font-weight: 700;
}}

#ProjectActivityRow {{
    border-bottom: 1px solid {COLORS["border"]};
}}

#ProjectActivitySummary {{
    color: {COLORS["text_primary"]};
    font-size: 9pt;
    font-weight: 600;
}}

#ProjectActivityMeta {{
    color: {COLORS["text_muted"]};
    font-size: 8pt;
}}

/* ------------------------------------------------------------------
   Phase 10 DIALOG recording workspace
   ------------------------------------------------------------------ */

#DialogWorkspace {{
    background: {COLORS["app_background"]};
}}

#DialogFilterBar,
#DialogSessionFooter {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["lg"]}px;
}}

#DialogFilterLabel,
#DialogFooterLabel {{
    color: {COLORS["text_secondary"]};
    font-size: 8pt;
    font-weight: 700;
}}

#DialogTalentFilter,
#DialogCharacterFilter,
#DialogEpisodeFilter,
#DialogSearch {{
    min-height: {COMPACT_CONTROL_HEIGHT}px;
    max-height: {COMPACT_CONTROL_HEIGHT}px;
}}

QPushButton[dialogNav="true"] {{
    background: {COLORS["surface"]};
    color: {COLORS["text_secondary"]};
    border: 1px solid {COLORS["border_strong"]};
    border-radius: {RADII["sm"]}px;
    min-height: {COMPACT_CONTROL_HEIGHT}px;
    max-height: {COMPACT_CONTROL_HEIGHT}px;
    padding: 0px 9px;
    font-weight: 600;
}}

QPushButton[dialogNav="true"]:hover {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["accent"]};
    border-color: {COLORS["focus"]};
}}

QPushButton[dialogNav="true"]:disabled {{
    background: {COLORS["surface_subtle"]};
    color: {COLORS["text_muted"]};
    border-color: {COLORS["border"]};
}}

#DialogTable {{
    background: {COLORS["surface"]};
    alternate-background-color: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["lg"]}px;
    selection-background-color: {COLORS["accent_soft"]};
    selection-color: {COLORS["text_primary"]};
}}

#DialogTable::item {{
    border-bottom: 1px solid {COLORS["border"]};
    padding: 5px 8px;
}}

#DialogTable::item:selected {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["text_primary"]};
}}

#DialogTable QCheckBox[source_revised="true"] {{
    background: {COLORS["source_revised_soft"]};
    border: 1px solid {COLORS["source_revised"]};
    border-radius: {RADII["sm"]}px;
}}

#DialogSessionSummary {{
    color: {COLORS["text_primary"]};
    font-size: 9pt;
    font-weight: 650;
}}

#DialogCastTable {{
    background: {COLORS["surface_subtle"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["md"]}px;
    gridline-color: transparent;
}}

#DialogCastTable::item {{
    border-bottom: 1px solid {COLORS["border"]};
    padding: 3px 7px;
}}

/* ------------------------------------------------------------------
   Phase 10 TRACKING production workspace
   ------------------------------------------------------------------ */

#TrackingFilterBar,
#TrackingLegendBar,
#TrackingWorkspaceTabs,
#TrackingQueuePanel,
#TrackingHealthStrip {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["lg"]}px;
}}

#TrackingFilterLabel,
#TrackingFooterTitle {{
    color: {COLORS["text_secondary"]};
    font-size: 8pt;
    font-weight: 800;
}}

#TrackingTalentFilter,
#TrackingEpisodeFilter {{
    min-height: {COMPACT_CONTROL_HEIGHT}px;
    max-height: {COMPACT_CONTROL_HEIGHT}px;
}}

#TrackingSummary {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
    font-weight: 600;
}}

QPushButton[trackingNav="true"] {{
    background: {COLORS["surface"]};
    color: {COLORS["text_secondary"]};
    border: 1px solid {COLORS["border_strong"]};
    border-radius: {RADII["sm"]}px;
    min-height: {COMPACT_CONTROL_HEIGHT}px;
    max-height: {COMPACT_CONTROL_HEIGHT}px;
    padding: 0px 9px;
    font-weight: 600;
}}

QPushButton[trackingNav="true"]:hover {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["accent"]};
    border-color: {COLORS["focus"]};
}}

QPushButton[trackingNav="true"]:disabled {{
    background: {COLORS["surface_subtle"]};
    color: {COLORS["text_muted"]};
    border-color: {COLORS["border"]};
}}

QPushButton[trackingWorkspaceTab="true"] {{
    background: transparent;
    color: {COLORS["text_secondary"]};
    border: 0px;
    border-radius: {RADII["sm"]}px;
    padding: 6px 11px;
    font-weight: 650;
}}

QPushButton[trackingWorkspaceTab="true"]:hover {{
    background: {COLORS["surface_subtle"]};
    color: {COLORS["text_primary"]};
}}

QPushButton[trackingWorkspaceTab="true"]:checked {{
    background: {COLORS["accent_soft"]};
    color: {COLORS["accent"]};
    font-weight: 750;
}}

#TrackingWorkspaceStack,
#TrackingGridWorkspace,
#TrackingScroll,
#TrackingScroll > QWidget > QWidget,
#TrackingRows {{
    background: {COLORS["app_background"]};
    border: 0px;
}}

#TrackingCharacterName {{
    background: {COLORS["surface"]};
    color: {COLORS["text_primary"]};
    border-bottom: 1px solid {COLORS["border"]};
    padding: 4px 8px;
    font-weight: 650;
}}

#TrackingEmptyState {{
    color: {COLORS["text_secondary"]};
    padding: 18px;
}}

#TrackingCharacterQueue {{
    background: {COLORS["surface_subtle"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["md"]}px;
    gridline-color: transparent;
}}

#TrackingCharacterQueue::item {{
    border-bottom: 1px solid {COLORS["border"]};
    padding: 3px 7px;
}}

#TrackingHealthLabel {{
    color: {COLORS["text_secondary"]};
    font-size: 8.5pt;
}}

#TrackingHealthValue {{
    color: {COLORS["text_primary"]};
    font-weight: 750;
}}

#TrackingDetailBar {{
    background: {COLORS["surface"]};
    border: 1px solid {COLORS["border"]};
    border-radius: {RADII["lg"]}px;
}}

#TrackingDetailPrimary {{
    color: {COLORS["text_primary"]};
    font-weight: 750;
}}

#TrackingDetailText {{
    color: {COLORS["text_secondary"]};
    font-size: 9pt;
}}

QPushButton[trackingRevisionAction="true"] {{
    background: {COLORS["revision_soft"]};
    color: {COLORS["revision_text"]};
    border: 1px solid {COLORS["revision"]};
    border-radius: {RADII["sm"]}px;
    min-height: {COMPACT_CONTROL_HEIGHT}px;
    padding: 0px 10px;
    font-weight: 700;
}}

QPushButton[trackingRevisionAction="true"]:hover {{
    background: {COLORS["surface"]};
    border: 2px solid {COLORS["revision"]};
}}

/* Legacy ribbon selectors retained only while page-local references/tests are
   migrated during Phase 10. The production MainWindow no longer uses Ribbon. */
#RibbonRoot,
#RibbonTabBar,
#RibbonContent,
#RibbonGroup {{
    background: {COLORS["surface"]};
    border-color: {COLORS["border"]};
}}
"""
