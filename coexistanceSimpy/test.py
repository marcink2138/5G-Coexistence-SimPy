from PyQt5 import QtCore, QtGui, QtWidgets

txt_browser_global_ref = None

sample_standard_fbe_config = {
    "name": 'GNB_FBE {}',
    "offset": "0",
    "cot": "5000",
    "ffp": "10000"
}
sample_random_muting_fbe_config = {
    "name": 'GNB_FBE {}',
    "offset": "0",
    "cot": "5000",
    "ffp": "10000",
    "max_muted_periods": "5",
    "max_frames_in_row": "5"
}
sample_fixed_muting_fbe_config = {
    "name": 'GNB_FBE {}',
    "offset": "0",
    "cot": "5000",
    "ffp": "10000",
    "max_muted_periods": "1",
}
sample_floating_fbe_config = {
    "name": 'GNB_FBE {}',
    "offset": "0",
    "cot": "5000",
    "ffp": "10000"
}
sample_db_fbe_config = {
    "name": 'GNB_FBE {}',
    "offset": "0",
    "cot": "5000",
    "ffp": "10000",
    "max_retransmissions": "5",
    "init_backoff": "3",
    "threshold": "4"
}


def create_reset_table_button(tab):
    reset_button = QtWidgets.QPushButton(tab)
    reset_button.setGeometry(QtCore.QRect(30, 500, 75, 23))
    font = QtGui.QFont()
    font.setBold(True)
    font.setWeight(75)
    reset_button.setFont(font)
    return reset_button


def create_delete_rows_button(tab, obj_name):
    button = QtWidgets.QPushButton(tab)
    button.setGeometry(QtCore.QRect(595, 500, 75, 23))
    button.setObjectName(obj_name)
    return button


def create_base_table(table):
    table.setRowCount(0)
    item = QtWidgets.QTableWidgetItem()
    table.setHorizontalHeaderItem(0, item)
    item = QtWidgets.QTableWidgetItem()
    table.setHorizontalHeaderItem(1, item)
    item = QtWidgets.QTableWidgetItem()
    table.setHorizontalHeaderItem(2, item)
    item = QtWidgets.QTableWidgetItem()
    table.setHorizontalHeaderItem(3, item)


def translate_base_table(_translate, table):
    item = table.horizontalHeaderItem(0)
    item.setText(_translate("MainWindow", "Name"))
    item = table.horizontalHeaderItem(1)
    item.setText(_translate("MainWindow", "Offset"))
    item = table.horizontalHeaderItem(2)
    item.setText(_translate("MainWindow", "COT length"))
    item = table.horizontalHeaderItem(3)
    item.setText(_translate("MainWindow", "FFP length"))


def set_base_table_rows(row, fbe_table, sample_data):
    fbe_table.setItem(row, 0, QtWidgets.QTableWidgetItem(sample_data["name"].format(row + 1)))
    fbe_table.setItem(row, 1, QtWidgets.QTableWidgetItem(sample_data["offset"]))
    fbe_table.setItem(row, 2, QtWidgets.QTableWidgetItem(sample_data["cot"]))
    fbe_table.setItem(row, 3, QtWidgets.QTableWidgetItem(sample_data["ffp"]))


def set_random_muting_fbe_rows(row, fbe_table, sample_data):
    set_base_table_rows(row, fbe_table, sample_data)
    fbe_table.setItem(row, 4, QtWidgets.QTableWidgetItem(sample_data["max_muted_periods"]))
    fbe_table.setItem(row, 5, QtWidgets.QTableWidgetItem(sample_data["max_frames_in_row"]))


def set_fixed_muting_fbe_rows(row, fbe_table, sample_data):
    set_base_table_rows(row, fbe_table, sample_data)
    fbe_table.setItem(row, 4, QtWidgets.QTableWidgetItem(sample_data["max_muted_periods"]))


def set_floating_fbe_rows(row, fbe_table, sample_data):
    set_base_table_rows(row, fbe_table, sample_data)


def set_db_fbe_rows(row, fbe_table, sample_data):
    set_base_table_rows(row, fbe_table, sample_data)
    fbe_table.setItem(row, 4, QtWidgets.QTableWidgetItem(sample_data["max_retransmissions"]))
    fbe_table.setItem(row, 5, QtWidgets.QTableWidgetItem(sample_data["init_backoff"]))
    fbe_table.setItem(row, 6, QtWidgets.QTableWidgetItem(sample_data["threshold"]))


def fill_fbe_table(spinbox, table, fill_fun, sample_fbe_config):
    number = spinbox.value()
    table.setRowCount(number)
    for row in range(0, number):
        fill_fun(row, table, sample_fbe_config)


def set_standard_fbe_rows(row, table, sample_fbe_config):
    set_base_table_rows(row, table, sample_fbe_config)


def handle_accept_station_button_click(spinbox, table, fun, sample_config):
    fill_fbe_table(spinbox, table, fun, sample_config)


def clear_table(table):
    table.clearContents()
    table.setRowCount(0)


def handle_reset_single_table_button_click(tab):
    clear_table(tab)


def handle_add_station_button_click(tab, sample_fbe_config, set_fun):
    row = tab.rowCount()
    tab.setRowCount(row + 1)
    set_fun(row, tab, sample_fbe_config)


def handle_delete_rows_button_click(table):
    rows = set()
    for index in table.selectedIndexes():
        rows.add(index.row())
    for row in sorted(rows, reverse=True):
        table.removeRow(row)


class Ui_MainWindow(object):
    def __init__(self):
        self.delete_db_fbe_rows_button = None
        self.delete_floating_fbe_rows_button = None
        self.delete_fixed_muting_fbe_rows_button = None
        self.delete_random_muting_fbe_rows_button = None
        self.textBrowser = None
        self.reset_all_settings_button = None
        self.run_simulation_button = None
        self.label_8 = None
        self.simulation_time_input = None
        self.enable_logging_checkbox = None
        self.label_7 = None
        self.label_6 = None
        self.number_of_runs_spinbox = None
        self.frame = None
        self.add_db_fbe_button = None
        self.reset_db_fbe_button = None
        self.db_fbe_table = None
        self.db_fbe_tab = None
        self.add_floating_fbe_button = None
        self.reset_floating_fbe_button = None
        self.floating_fbe_table = None
        self.floating_fbe_tab = None
        self.add_fixed_muting_fbe_button = None
        self.reset_fixed_muting_fbe_button = None
        self.fixed_muting_fbe_table = None
        self.fixed_muting_fbe_tab = None
        self.add_random_muting_fbe_button = None
        self.reset_random_muting_fbe_button = None
        self.random_muting_fbe_table = None
        self.random_muting_fbe_tab = None
        self.add_standard_fbe_station = None
        self.reset_standard_fbe_button = None
        self.standard_fbe_table = None
        self.standard_fbe_tab = None
        self.tabWidget = None
        self.accept_station_number_button = None
        self.standard_fbe_spinbox = None
        self.label_3 = None
        self.statusbar = None
        self.label_2 = None
        self.label_4 = None
        self.db_fbe_spinbox = None
        self.fixed_muting_fbe_spinbox = None
        self.floating_point_fbe_spinbox = None
        self.random_muting_fbe_spinbox = None
        self.label = None
        self.label_5 = None
        self.centralwidget = None
        self.scrollArea = None
        self.scrollAreaWidgetContents = None
        self.delete_standard_fbe_rows_button = None

    def setupUi(self, MainWindow):
        MainWindow.setObjectName("MainWindow")
        MainWindow.resize(1025, 757)
        self.centralwidget = QtWidgets.QWidget(MainWindow)
        self.centralwidget.setObjectName("centralwidget")
        self.scrollArea = QtWidgets.QScrollArea(self.centralwidget)
        self.scrollArea.setGeometry(QtCore.QRect(30, 40, 140, 511))
        self.scrollArea.setWidgetResizable(True)
        self.scrollArea.setObjectName("scrollArea")
        self.scrollAreaWidgetContents = QtWidgets.QWidget()
        self.scrollAreaWidgetContents.setGeometry(QtCore.QRect(0, 0, 138, 509))
        self.scrollAreaWidgetContents.setObjectName("scrollAreaWidgetContents")
        self.label_5 = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_5.setGeometry(QtCore.QRect(10, 360, 120, 40))
        self.label_5.setAlignment(QtCore.Qt.AlignCenter)
        self.label_5.setObjectName("label_5")
        self.label = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label.setGeometry(QtCore.QRect(10, 10, 120, 40))
        self.label.setAlignment(QtCore.Qt.AlignCenter)
        self.label.setObjectName("label")

        # Station number spinboxes
        self.standard_fbe_spinbox = QtWidgets.QSpinBox(self.scrollAreaWidgetContents)
        self.standard_fbe_spinbox.setGeometry(QtCore.QRect(50, 60, 40, 20))
        self.standard_fbe_spinbox.setObjectName("standard_fbe_spinbox")

        self.random_muting_fbe_spinbox = QtWidgets.QSpinBox(self.scrollAreaWidgetContents)
        self.random_muting_fbe_spinbox.setGeometry(QtCore.QRect(50, 150, 40, 20))
        self.random_muting_fbe_spinbox.setObjectName("random_muting_fbe_spinbox")

        self.floating_point_fbe_spinbox = QtWidgets.QSpinBox(self.scrollAreaWidgetContents)
        self.floating_point_fbe_spinbox.setGeometry(QtCore.QRect(50, 320, 40, 20))
        self.floating_point_fbe_spinbox.setObjectName("floating_point_fbe_spinbox")

        self.fixed_muting_fbe_spinbox = QtWidgets.QSpinBox(self.scrollAreaWidgetContents)
        self.fixed_muting_fbe_spinbox.setGeometry(QtCore.QRect(50, 230, 40, 20))
        self.fixed_muting_fbe_spinbox.setObjectName("fixed_muting_fbe_spinbox")

        self.db_fbe_spinbox = QtWidgets.QSpinBox(self.scrollAreaWidgetContents)
        self.db_fbe_spinbox.setGeometry(QtCore.QRect(50, 410, 40, 20))
        self.db_fbe_spinbox.setObjectName("db_fbe_spinbox")

        # Labels
        self.label_4 = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_4.setGeometry(QtCore.QRect(10, 270, 120, 40))
        self.label_4.setAlignment(QtCore.Qt.AlignCenter)
        self.label_4.setObjectName("label_4")
        self.label_2 = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_2.setGeometry(QtCore.QRect(10, 100, 120, 40))
        self.label_2.setAlignment(QtCore.Qt.AlignCenter)
        self.label_2.setObjectName("label_2")
        self.label_3 = QtWidgets.QLabel(self.scrollAreaWidgetContents)
        self.label_3.setGeometry(QtCore.QRect(10, 180, 120, 40))
        self.label_3.setAlignment(QtCore.Qt.AlignCenter)
        self.label_3.setObjectName("label_3")

        self.accept_station_number_button = QtWidgets.QPushButton(self.scrollAreaWidgetContents)
        self.accept_station_number_button.setGeometry(QtCore.QRect(30, 460, 75, 23))
        self.accept_station_number_button.setObjectName("accept_station_number_button")

        self.scrollArea.setWidget(self.scrollAreaWidgetContents)
        self.tabWidget = QtWidgets.QTabWidget(self.centralwidget)
        self.tabWidget.setGeometry(QtCore.QRect(200, 40, 801, 561))
        self.tabWidget.setObjectName("tabWidget")

        # Standard FBE page
        self.standard_fbe_tab = QtWidgets.QWidget()
        self.standard_fbe_tab.setObjectName("standard_fbe_tab")
        self.standard_fbe_table = QtWidgets.QTableWidget(self.standard_fbe_tab)
        self.standard_fbe_table.setGeometry(QtCore.QRect(10, 10, 771, 461))
        self.standard_fbe_table.setObjectName("standard_fbe_table")
        self.standard_fbe_table.setColumnCount(4)
        create_base_table(self.standard_fbe_table)
        self.standard_fbe_table.horizontalHeader().setCascadingSectionResizes(False)
        self.standard_fbe_table.horizontalHeader().setStretchLastSection(True)
        self.standard_fbe_table.verticalHeader().setCascadingSectionResizes(False)
        self.standard_fbe_table.verticalHeader().setStretchLastSection(False)
        self.reset_standard_fbe_button = create_reset_table_button(self.standard_fbe_tab)
        self.reset_standard_fbe_button.setObjectName("reset_standard_fbe_button")
        self.add_standard_fbe_station = QtWidgets.QPushButton(self.standard_fbe_tab)
        self.add_standard_fbe_station.setGeometry(QtCore.QRect(700, 500, 75, 23))
        self.add_standard_fbe_station.setObjectName("add_standard_fbe_station")
        self.tabWidget.addTab(self.standard_fbe_tab, "")
        self.delete_standard_fbe_rows_button = create_delete_rows_button(self.standard_fbe_tab,
                                                                         "delete_standard_fbe_rows_button")

        # Random muting FBE page
        self.random_muting_fbe_tab = QtWidgets.QWidget()
        self.random_muting_fbe_tab.setObjectName("random_muting_fbe_tab")
        self.random_muting_fbe_table = QtWidgets.QTableWidget(self.random_muting_fbe_tab)
        self.random_muting_fbe_table.setGeometry(QtCore.QRect(10, 10, 771, 461))
        self.random_muting_fbe_table.setObjectName("random_muting_fbe_table")
        self.random_muting_fbe_table.setColumnCount(6)
        create_base_table(self.random_muting_fbe_table)
        item = QtWidgets.QTableWidgetItem()
        self.random_muting_fbe_table.setHorizontalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        self.random_muting_fbe_table.setHorizontalHeaderItem(5, item)
        self.random_muting_fbe_table.horizontalHeader().setCascadingSectionResizes(True)
        self.random_muting_fbe_table.horizontalHeader().setDefaultSectionSize(120)
        self.random_muting_fbe_table.horizontalHeader().setStretchLastSection(True)
        self.random_muting_fbe_table.verticalHeader().setCascadingSectionResizes(False)
        self.reset_random_muting_fbe_button = create_reset_table_button(self.random_muting_fbe_tab)
        self.reset_random_muting_fbe_button.setObjectName("reset_random_muting_fbe_button")
        self.add_random_muting_fbe_button = QtWidgets.QPushButton(self.random_muting_fbe_tab)
        self.add_random_muting_fbe_button.setGeometry(QtCore.QRect(700, 500, 75, 23))
        self.add_random_muting_fbe_button.setObjectName("add_random_muting_fbe_button")
        self.tabWidget.addTab(self.random_muting_fbe_tab, "")
        self.delete_random_muting_fbe_rows_button = create_delete_rows_button(self.random_muting_fbe_tab,
                                                                              "delete_random_muting_fbe_rows_button")

        # Fixed muting FBE page
        self.fixed_muting_fbe_tab = QtWidgets.QWidget()
        self.fixed_muting_fbe_tab.setObjectName("fixed_muting_fbe_tab")
        self.fixed_muting_fbe_table = QtWidgets.QTableWidget(self.fixed_muting_fbe_tab)
        self.fixed_muting_fbe_table.setGeometry(QtCore.QRect(10, 10, 771, 461))
        self.fixed_muting_fbe_table.setObjectName("fixed_muting_fbe_table")
        self.fixed_muting_fbe_table.setColumnCount(5)
        create_base_table(self.fixed_muting_fbe_table)
        self.fixed_muting_fbe_table.setHorizontalHeaderItem(4, item)
        self.fixed_muting_fbe_table.horizontalHeader().setDefaultSectionSize(120)
        self.fixed_muting_fbe_table.horizontalHeader().setStretchLastSection(True)
        self.reset_fixed_muting_fbe_button = create_reset_table_button(self.fixed_muting_fbe_tab)
        self.reset_fixed_muting_fbe_button.setObjectName("reset_fixed_muting_fbe_button")
        self.add_fixed_muting_fbe_button = QtWidgets.QPushButton(self.fixed_muting_fbe_tab)
        self.add_fixed_muting_fbe_button.setGeometry(QtCore.QRect(700, 500, 75, 23))
        self.add_fixed_muting_fbe_button.setObjectName("add_fixed_muting_fbe_button")
        self.tabWidget.addTab(self.fixed_muting_fbe_tab, "")
        self.delete_fixed_muting_fbe_rows_button = create_delete_rows_button(self.fixed_muting_fbe_tab,
                                                                             "delete_fixed_muting_fbe_rows_button")

        # Floating FBE page
        self.floating_fbe_tab = QtWidgets.QWidget()
        self.floating_fbe_tab.setObjectName("floating_fbe_tab")
        self.floating_fbe_table = QtWidgets.QTableWidget(self.floating_fbe_tab)
        self.floating_fbe_table.setGeometry(QtCore.QRect(10, 10, 771, 461))
        self.floating_fbe_table.setObjectName("floating_fbe_table")
        self.floating_fbe_table.setColumnCount(4)
        create_base_table(self.floating_fbe_table)
        self.floating_fbe_table.horizontalHeader().setStretchLastSection(True)
        self.reset_floating_fbe_button = create_reset_table_button(self.floating_fbe_tab)
        self.reset_floating_fbe_button.setObjectName("reset_floating_fbe_button")
        self.add_floating_fbe_button = QtWidgets.QPushButton(self.floating_fbe_tab)
        self.add_floating_fbe_button.setGeometry(QtCore.QRect(700, 500, 75, 23))
        self.add_floating_fbe_button.setObjectName("add_floating_fbe_button")
        self.tabWidget.addTab(self.floating_fbe_tab, "")
        self.delete_floating_fbe_rows_button = create_delete_rows_button(self.floating_fbe_tab,
                                                                         "delete_floating_fbe_rows_button")
        # DB FBE page
        self.db_fbe_tab = QtWidgets.QWidget()
        self.db_fbe_tab.setObjectName("db_fbe_tab")
        self.db_fbe_table = QtWidgets.QTableWidget(self.db_fbe_tab)
        self.db_fbe_table.setGeometry(QtCore.QRect(10, 10, 771, 461))
        self.db_fbe_table.setObjectName("db_fbe_table")
        self.db_fbe_table.setColumnCount(7)
        create_base_table(self.db_fbe_table)
        self.db_fbe_table.setHorizontalHeaderItem(4, item)
        item = QtWidgets.QTableWidgetItem()
        self.db_fbe_table.setHorizontalHeaderItem(5, item)
        item = QtWidgets.QTableWidgetItem()
        self.db_fbe_table.setHorizontalHeaderItem(6, item)
        self.db_fbe_table.horizontalHeader().setDefaultSectionSize(120)
        self.reset_db_fbe_button = create_reset_table_button(self.db_fbe_tab)
        self.reset_db_fbe_button.setObjectName("reset_db_fbe_button")
        self.add_db_fbe_button = QtWidgets.QPushButton(self.db_fbe_tab)
        self.add_db_fbe_button.setGeometry(QtCore.QRect(700, 500, 75, 23))
        self.add_db_fbe_button.setObjectName("add_db_fbe_button")
        self.tabWidget.addTab(self.db_fbe_tab, "")
        self.delete_db_fbe_rows_button = create_delete_rows_button(self.db_fbe_tab,
                                                                   "delete_db_fbe_rows_button")

        # Simulation options
        self.frame = QtWidgets.QFrame(self.centralwidget)
        self.frame.setGeometry(QtCore.QRect(200, 620, 431, 111))
        self.frame.setFrameShape(QtWidgets.QFrame.StyledPanel)
        self.frame.setFrameShadow(QtWidgets.QFrame.Raised)
        self.frame.setLineWidth(1)
        self.frame.setObjectName("frame")
        self.number_of_runs_spinbox = QtWidgets.QSpinBox(self.frame)
        self.number_of_runs_spinbox.setGeometry(QtCore.QRect(230, 60, 42, 22))
        self.number_of_runs_spinbox.setMinimum(1)
        self.number_of_runs_spinbox.setMaximum(10)
        self.number_of_runs_spinbox.setObjectName("number_of_runs_spinbox")
        self.label_6 = QtWidgets.QLabel(self.frame)
        self.label_6.setGeometry(QtCore.QRect(10, 10, 121, 31))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.label_6.setFont(font)
        self.label_6.setAlignment(QtCore.Qt.AlignCenter)
        self.label_6.setObjectName("label_6")
        self.label_7 = QtWidgets.QLabel(self.frame)
        self.label_7.setGeometry(QtCore.QRect(60, 30, 101, 31))
        self.label_7.setAlignment(QtCore.Qt.AlignCenter)
        self.label_7.setObjectName("label_7")
        self.enable_logging_checkbox = QtWidgets.QCheckBox(self.frame)
        self.enable_logging_checkbox.setGeometry(QtCore.QRect(20, 90, 91, 17))
        self.enable_logging_checkbox.setObjectName("enable_logging_checkbox")
        self.simulation_time_input = QtWidgets.QLineEdit(self.frame)
        self.simulation_time_input.setGeometry(QtCore.QRect(70, 60, 91, 20))
        self.simulation_time_input.setObjectName("simulation_time_input")
        self.label_8 = QtWidgets.QLabel(self.frame)
        self.label_8.setGeometry(QtCore.QRect(190, 30, 131, 31))
        self.label_8.setAlignment(QtCore.Qt.AlignCenter)
        self.label_8.setObjectName("label_8")
        self.run_simulation_button = QtWidgets.QPushButton(self.frame)
        self.run_simulation_button.setGeometry(QtCore.QRect(310, 30, 101, 61))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.run_simulation_button.setFont(font)
        self.run_simulation_button.setObjectName("run_simulation_button")
        self.reset_all_settings_button = QtWidgets.QPushButton(self.centralwidget)
        self.reset_all_settings_button.setGeometry(QtCore.QRect(60, 620, 75, 61))
        font = QtGui.QFont()
        font.setBold(True)
        font.setWeight(75)
        self.reset_all_settings_button.setFont(font)
        self.reset_all_settings_button.setLayoutDirection(QtCore.Qt.LeftToRight)
        self.reset_all_settings_button.setStyleSheet("white-space: normal;")
        self.reset_all_settings_button.setAutoExclusive(False)
        self.reset_all_settings_button.setObjectName("reset_all_settings_button")
        self.textBrowser = QtWidgets.QTextBrowser(self.centralwidget)
        self.textBrowser.setGeometry(QtCore.QRect(650, 620, 361, 111))
        self.textBrowser.setObjectName("textBrowser")
        MainWindow.setCentralWidget(self.centralwidget)
        self.statusbar = QtWidgets.QStatusBar(MainWindow)
        self.statusbar.setObjectName("statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.retranslateUi(MainWindow)
        self.tabWidget.setCurrentIndex(1)
        QtCore.QMetaObject.connectSlotsByName(MainWindow)

    def retranslateUi(self, MainWindow):
        _translate = QtCore.QCoreApplication.translate
        MainWindow.setWindowTitle(_translate("MainWindow", "MainWindow"))
        self.label_5.setText(_translate("MainWindow", "DB-FBE"))
        self.label.setText(_translate("MainWindow", "Standard FBE"))
        self.label_4.setText(_translate("MainWindow", "Floating point FBE"))
        self.label_2.setText(_translate("MainWindow", "Random muting FBE"))
        self.label_3.setText(_translate("MainWindow", "Fixed muting FBE"))
        self.accept_station_number_button.setText(_translate("MainWindow", "OK"))
        translate_base_table(_translate, self.standard_fbe_table)
        self.reset_standard_fbe_button.setText(_translate("MainWindow", "Reset"))
        self.add_standard_fbe_station.setText(_translate("MainWindow", "Add station"))

        self.delete_standard_fbe_rows_button.setText(_translate("MainWindow", "Delete rows"))
        self.delete_random_muting_fbe_rows_button.setText(_translate("MainWindow", "Delete rows"))
        self.delete_fixed_muting_fbe_rows_button.setText(_translate("MainWindow", "Delete rows"))
        self.delete_floating_fbe_rows_button.setText(_translate("MainWindow", "Delete rows"))
        self.delete_db_fbe_rows_button.setText(_translate("MainWindow", "Delete rows"))

        self.tabWidget.setTabText(self.tabWidget.indexOf(self.standard_fbe_tab),
                                  _translate("MainWindow", "Standard FBE"))
        translate_base_table(_translate, self.random_muting_fbe_table)
        item = self.random_muting_fbe_table.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "Max muted periodes"))
        item = self.random_muting_fbe_table.horizontalHeaderItem(5)
        item.setText(_translate("MainWindow", "Max frames in a row"))
        self.reset_random_muting_fbe_button.setText(_translate("MainWindow", "Reset"))
        self.add_random_muting_fbe_button.setText(_translate("MainWindow", "Add station"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.random_muting_fbe_tab),
                                  _translate("MainWindow", "Random muting FBE"))
        translate_base_table(_translate, self.fixed_muting_fbe_table)
        item = self.fixed_muting_fbe_table.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "Max muted periodes"))
        self.reset_fixed_muting_fbe_button.setText(_translate("MainWindow", "Reset"))
        self.add_fixed_muting_fbe_button.setText(_translate("MainWindow", "Add station"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.fixed_muting_fbe_tab),
                                  _translate("MainWindow", "Fixed muting FBE"))
        translate_base_table(_translate, self.floating_fbe_table)
        self.reset_floating_fbe_button.setText(_translate("MainWindow", "Reset"))
        self.add_floating_fbe_button.setText(_translate("MainWindow", "Add station"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.floating_fbe_tab),
                                  _translate("MainWindow", "Floating point FBE"))
        translate_base_table(_translate, self.db_fbe_table)
        item = self.db_fbe_table.horizontalHeaderItem(4)
        item.setText(_translate("MainWindow", "Max retransmissions"))
        item = self.db_fbe_table.horizontalHeaderItem(5)
        item.setText(_translate("MainWindow", "Init backoff"))
        item = self.db_fbe_table.horizontalHeaderItem(6)
        item.setText(_translate("MainWindow", "Threshold"))
        self.reset_db_fbe_button.setText(_translate("MainWindow", "Reset"))
        self.add_db_fbe_button.setText(_translate("MainWindow", "Add station"))
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.db_fbe_tab), _translate("MainWindow", "DB-FBE"))
        self.label_6.setText(_translate("MainWindow", "Simulation options"))
        self.label_7.setText(_translate("MainWindow", "Simulation time"))
        self.enable_logging_checkbox.setText(_translate("MainWindow", "Enable logging"))
        self.simulation_time_input.setText(_translate("MainWindow", "1000000"))
        self.simulation_time_input.setPlaceholderText(_translate("MainWindow", "[μs]"))
        self.label_8.setText(_translate("MainWindow", "Number of runs"))
        self.run_simulation_button.setText(_translate("MainWindow", "Run simulation"))
        self.reset_all_settings_button.setText(_translate("MainWindow", "Reset \n"
                                                                        " all settings"))
        self.attach_event_handlers_to_buttons()

    def attach_event_handlers_to_buttons(self):
        self.accept_station_number_button.clicked.connect(self.handle_accept_station_button_click_wrapper)
        self.reset_all_settings_button.clicked.connect(self.handle_reset_all_settings_button_click)
        self.reset_standard_fbe_button.clicked.connect(
            lambda: handle_reset_single_table_button_click(self.standard_fbe_table))
        self.reset_random_muting_fbe_button.clicked.connect(
            lambda: handle_reset_single_table_button_click(self.random_muting_fbe_table))
        self.reset_fixed_muting_fbe_button.clicked.connect(
            lambda: handle_reset_single_table_button_click(self.fixed_muting_fbe_table))
        self.reset_floating_fbe_button.clicked.connect(
            lambda: handle_reset_single_table_button_click(self.floating_fbe_table))
        self.reset_db_fbe_button.clicked.connect(
            lambda: handle_reset_single_table_button_click(self.db_fbe_table))
        self.add_standard_fbe_station.clicked.connect(
            lambda: handle_add_station_button_click(self.standard_fbe_table,
                                                    sample_standard_fbe_config, set_standard_fbe_rows))
        self.add_random_muting_fbe_button.clicked.connect(
            lambda: handle_add_station_button_click(self.random_muting_fbe_table, sample_random_muting_fbe_config,
                                                    set_random_muting_fbe_rows))
        self.add_fixed_muting_fbe_button.clicked.connect(
            lambda: handle_add_station_button_click(self.fixed_muting_fbe_table, sample_fixed_muting_fbe_config,
                                                    set_fixed_muting_fbe_rows))
        self.add_floating_fbe_button.clicked.connect(
            lambda: handle_add_station_button_click(self.floating_fbe_table, sample_floating_fbe_config,
                                                    set_floating_fbe_rows))
        self.add_db_fbe_button.clicked.connect(
            lambda: handle_add_station_button_click(self.db_fbe_table, sample_db_fbe_config, set_db_fbe_rows)
        )
        self.delete_standard_fbe_rows_button.clicked.connect(
            lambda: self.handle_delete_rows_button_click(self.standard_fbe_table))
        self.delete_random_muting_fbe_rows_button.clicked.connect(
            lambda: self.handle_delete_rows_button_click(self.random_muting_fbe_table))
        self.delete_fixed_muting_fbe_rows_button.clicked.connect(
            lambda: self.handle_delete_rows_button_click(self.fixed_muting_fbe_table))
        self.delete_floating_fbe_rows_button.clicked.connect(
            lambda: self.handle_delete_rows_button_click(self.floating_fbe_table))
        self.delete_db_fbe_rows_button.clicked.connect(lambda: self.handle_delete_rows_button_click(self.db_fbe_table))

    def handle_accept_station_button_click_wrapper(self):
        handle_accept_station_button_click(self.standard_fbe_spinbox, self.standard_fbe_table,
                                           set_standard_fbe_rows,
                                           sample_standard_fbe_config)
        handle_accept_station_button_click(self.random_muting_fbe_spinbox, self.random_muting_fbe_table,
                                           set_random_muting_fbe_rows, sample_random_muting_fbe_config)
        handle_accept_station_button_click(self.fixed_muting_fbe_spinbox, self.fixed_muting_fbe_table,
                                           set_fixed_muting_fbe_rows, sample_fixed_muting_fbe_config)
        handle_accept_station_button_click(self.floating_point_fbe_spinbox, self.floating_fbe_table,
                                           set_floating_fbe_rows, sample_floating_fbe_config)
        handle_accept_station_button_click(self.db_fbe_spinbox, self.db_fbe_table, set_db_fbe_rows,
                                           sample_db_fbe_config)

    def handle_reset_all_settings_button_click(self):
        clear_table(self.standard_fbe_table)
        clear_table(self.random_muting_fbe_table)
        clear_table(self.fixed_muting_fbe_table)
        clear_table(self.floating_fbe_table)
        clear_table(self.db_fbe_table)
        self.standard_fbe_spinbox.setValue(0)
        self.random_muting_fbe_spinbox.setValue(0)
        self.fixed_muting_fbe_spinbox.setValue(0)
        self.floating_point_fbe_spinbox.setValue(0)
        self.db_fbe_spinbox.setValue(0)
        self.number_of_runs_spinbox.setValue(0)
        self.simulation_time_input.setText('1000000')
        self.enable_logging_checkbox.setChecked(False)
        self.debug('Init values set')

    def debug(self, info):
        text = self.textBrowser.toPlainText()
        self.textBrowser.setText(info + '\n' + text)

    def handle_delete_rows_button_click(self, table):
        rows = set()
        for index in table.selectedIndexes():
            rows.add(index.row())
        for row in sorted(rows, reverse=True):
            table.removeRow(row)
            self.debug(f'Row {row} deleted')


if __name__ == "__main__":
    import sys

    app = QtWidgets.QApplication(sys.argv)
    MainWindow = QtWidgets.QMainWindow()
    ui = Ui_MainWindow()
    ui.setupUi(MainWindow)
    MainWindow.show()
    sys.exit(app.exec_())
