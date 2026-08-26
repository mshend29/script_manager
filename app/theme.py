APP_STYLESHEET = """
QMainWindow, QWidget {
    background: #f5f6f7;
    color: #202124;
    font-family: "Segoe UI";
    font-size: 10pt;
}
#RibbonRoot { background: #ffffff; border-bottom: 1px solid #d8d8d8; }
#RibbonTabBar { background: #f3f3f3; border-bottom: 1px solid #d6d6d6; }
QPushButton[ribbonTab="true"] {
    background: transparent; border: none;
    padding: 9px 18px 8px 18px; font-weight: 600;
}
QPushButton[ribbonTab="true"]:hover { background: #e9ecef; }
QPushButton[ribbonTab="true"]:checked {
    color: #217346; background: #ffffff;
    border-bottom: 3px solid #217346;
}
#RibbonContent { background: #ffffff; min-height: 82px; }
#RibbonGroup { background: #ffffff; border-right: 1px solid #dedede; }
#RibbonGroupTitle { color: #6b6b6b; font-size: 8pt; }
QPushButton[ribbonAction="true"] {
    background: #ffffff; border: 1px solid transparent;
    border-radius: 3px; padding: 6px 10px; min-height: 28px;
}
QPushButton[ribbonAction="true"]:hover {
    background: #edf5f0; border-color: #c4ddcd;
}
#ContextPanel { background: #ffffff; border-right: 1px solid #dadce0; }
#ContextPanel QLabel {
    padding-left: 7px;
    padding-right: 4px;
}
#Workspace { background: #ffffff; }
#SectionTitle {
    font-size: 9pt; font-weight: 700; color: #5f6368;
    padding-left: 7px; padding-right: 5px;
    padding-top: 2px; padding-bottom: 2px;
}
#PageTitle {
    font-size: 18pt; font-weight: 600; color: #202124;
    padding-left: 7px; padding-right: 5px;
}
#PageSubtitle {
    color: #6b7075;
    padding-left: 7px; padding-right: 5px;
}
#DashboardCard { background: #ffffff; border: 1px solid #dadce0; border-radius: 7px; }
#CardValue { font-size: 23pt; font-weight: 600; color: #217346; }
#CardLabel { color: #5f6368; }
QLineEdit, QComboBox {
    background: #ffffff; border: 1px solid #c8cdd1;
    border-radius: 4px; padding: 6px 8px; min-height: 22px;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #217346; }
QPushButton[primary="true"] {
    background: #217346; color: #ffffff; border: 1px solid #217346;
    border-radius: 4px; padding: 7px 12px; font-weight: 600;
}
QPushButton[secondary="true"] {
    background: #ffffff; border: 1px solid #c8cdd1;
    border-radius: 4px; padding: 7px 12px;
}
QCheckBox {
    min-width: 31px;
    max-width: 31px;
    min-height: 30px;
    max-height: 30px;
    spacing: 0px;
    padding-left: 6px;
}
QCheckBox::indicator {
    width: 19px;
    height: 19px;
}
QCheckBox::indicator:unchecked {
    background: #ffffff;
    border: 1px solid #9aa0a6;
    border-radius: 3px;
}
QCheckBox::indicator:unchecked:hover {
    background: #f2f8f4;
    border: 2px solid #217346;
}
QTableWidget, QTableView {
    background: #ffffff; alternate-background-color: #fafafa;
    border: 1px solid #dadce0; gridline-color: #e5e5e5;
    selection-background-color: #dcece2; selection-color: #202124;
}
QHeaderView::section {
    background: #f3f4f5; border: none;
    border-right: 1px solid #dadce0; border-bottom: 1px solid #dadce0;
    padding: 7px; font-weight: 600;
}
QStatusBar {
    background: #eef6f1; color: #234c35;
    border-top: 1px solid #b8d5c2;
    min-height: 34px;
    font-weight: 600;
}
QStatusBar QLabel {
    color: #234c35;
    padding: 2px 6px;
}
QProgressBar {
    background: #ffffff;
    border: 1px solid #8ab79a;
    border-radius: 6px;
    min-height: 20px;
    text-align: center;
    color: #173d28;
    font-weight: 700;
}
QProgressBar::chunk {
    background: #217346;
    border-radius: 5px;
}
"""
