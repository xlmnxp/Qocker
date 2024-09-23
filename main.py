import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QTabWidget, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QHBoxLayout, QWidget, QToolBar, QAction, QMenu,
                             QHeaderView, QLabel, QLineEdit, QCheckBox, QMessageBox, QInputDialog)
from PyQt5.QtGui import QIcon, QColor
from PyQt5.QtCore import Qt, QTimer, QThread, pyqtSignal
import subprocess
import platform

class StatusDelegate(QWidget):
    def __init__(self, status, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 4, 4, 4)
        layout.setSpacing(8)
        
        self.status_circle = QWidget()
        self.status_circle.setFixedSize(12, 12)
        color = QColor('green') if 'Up' in status else QColor('red')
        self.status_circle.setStyleSheet(f"background-color: {color.name()}; border-radius: 6px;")
        
        self.status_label = QLabel(status)
        
        layout.addWidget(self.status_circle)
        layout.addWidget(self.status_label)
        layout.addStretch()

class TerminalOpener(QThread):
    error = pyqtSignal(str)

    def __init__(self, container_id):
        super().__init__()
        self.container_id = container_id

    def run(self):
        docker_command = f"docker exec -it {self.container_id} sh -c '[ -x /bin/bash ] && exec /bin/bash || exec /bin/sh'"
        system = platform.system()

        try:
            if system == "Darwin":  # macOS
                subprocess.Popen(['open', '-a', 'Terminal', '--', 'sh', '-c', f"{docker_command}"])
            elif system == "Linux":
                subprocess.Popen(['x-terminal-emulator', '-e', f'sh -c "{docker_command}"'])
            elif system == "Windows":
                subprocess.Popen(['start', 'cmd', '/k', docker_command], shell=True)
            else:
                self.error.emit(f"Opening a terminal is not supported on {system}")
        except Exception as e:
            self.error.emit(f"Failed to open terminal: {str(e)}")

class DockerGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Qocker - Docker Graphical User Interface")
        self.setGeometry(100, 100, 1000, 600)

        # Create central widget and layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        # Create toolbar
        self.create_toolbar()

        # Create tab widget
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)

        # Create tabs
        self.containers_tab = QWidget()
        self.networks_tab = QWidget()
        self.volumes_tab = QWidget()

        self.tab_widget.addTab(self.containers_tab, "Containers")
        self.tab_widget.addTab(self.networks_tab, "Networks")
        self.tab_widget.addTab(self.volumes_tab, "Volumes")

        # Connect tab change to toolbar update
        self.tab_widget.currentChanged.connect(self.update_toolbar_buttons)

        # Create tree widgets for each tab
        self.containers_tree = self.create_tree_widget(["ID", "Name", "Image", "Status", "Ports"])
        self.networks_tree = self.create_tree_widget(["ID", "Name", "Driver"])
        self.volumes_tree = self.create_tree_widget(["Name", "Driver", "Mountpoint"])
        
        self.containers_tree.itemDoubleClicked.connect(self.open_terminal)

        # Add tree widgets to tabs
        self.setup_tab(self.containers_tab, self.containers_tree, "Search containers...")
        self.setup_tab(self.networks_tab, self.networks_tree, "Search networks...")
        self.setup_tab(self.volumes_tab, self.volumes_tree, "Search volumes...")

        # Create menu bar
        self.create_menu_bar()

        # Setup auto-refresh
        self.setup_auto_refresh()

        # Populate data
        self.refresh_data()

        # Update toolbar buttons for initial state
        self.update_toolbar_buttons(0)

    def create_tree_widget(self, headers):
        tree = QTreeWidget()
        tree.setHeaderLabels(headers)
        tree.setContextMenuPolicy(Qt.CustomContextMenu)
        tree.customContextMenuRequested.connect(self.show_context_menu)
        tree.header().setSectionResizeMode(QHeaderView.Interactive)
        return tree

    def setup_tab(self, tab, tree, search_placeholder):
        layout = QVBoxLayout(tab)
        
        # Add search bar
        search_bar = QLineEdit()
        search_bar.setPlaceholderText(search_placeholder)
        search_bar.textChanged.connect(lambda text: self.filter_tree(tree, text))
        layout.addWidget(search_bar)
        
        layout.addWidget(tree)

    def filter_tree(self, tree, text):
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            match = any(text.lower() in item.text(j).lower() for j in range(item.columnCount()))
            item.setHidden(not match)

    def create_toolbar(self):
        self.toolbar = QToolBar()
        self.toolbar.setMovable(False)  # Make toolbar fixed
        self.addToolBar(Qt.TopToolBarArea, self.toolbar)

        # Common actions
        self.refresh_action = QAction(QIcon.fromTheme("view-refresh"), "Refresh", self)
        self.refresh_action.triggered.connect(self.refresh_data)
        self.toolbar.addAction(self.refresh_action)

        # Add auto-refresh checkbox
        self.auto_refresh_checkbox = QCheckBox("Auto-refresh")
        self.auto_refresh_checkbox.setChecked(True)
        self.auto_refresh_checkbox.stateChanged.connect(self.toggle_auto_refresh)
        self.toolbar.addWidget(self.auto_refresh_checkbox)

        # Add separator
        self.toolbar.addSeparator()

        # Container-specific actions
        self.start_action = QAction(QIcon.fromTheme("media-playback-start"), "Start", self)
        self.start_action.triggered.connect(self.start_container)
        self.toolbar.addAction(self.start_action)

        self.stop_action = QAction(QIcon.fromTheme("media-playback-stop"), "Stop", self)
        self.stop_action.triggered.connect(self.stop_container)
        self.toolbar.addAction(self.stop_action)

        self.remove_action = QAction(QIcon.fromTheme("edit-delete"), "Remove", self)
        self.remove_action.triggered.connect(self.remove_container)
        self.toolbar.addAction(self.remove_action)

        # Network-specific actions
        self.create_network_action = QAction(QIcon.fromTheme("list-add"), "Create Network", self)
        self.create_network_action.triggered.connect(self.create_network)
        self.toolbar.addAction(self.create_network_action)

        self.remove_network_action = QAction(QIcon.fromTheme("edit-delete"), "Remove Network", self)
        self.remove_network_action.triggered.connect(self.remove_network)
        self.toolbar.addAction(self.remove_network_action)
        
        # Volume-specific actions
        self.create_volume_action = QAction(QIcon.fromTheme("list-add"), "Create Volume", self)
        self.create_volume_action.triggered.connect(self.create_volume)
        self.toolbar.addAction(self.create_volume_action)

        self.remove_volume_action = QAction(QIcon.fromTheme("edit-delete"), "Remove Volume", self)
        self.remove_volume_action.triggered.connect(self.remove_volume)
        self.toolbar.addAction(self.remove_volume_action)
        
        # Add terminal action
        self.terminal_action = QAction(QIcon.fromTheme("utilities-terminal"), "Open Terminal", self)
        self.terminal_action.triggered.connect(self.open_terminal)
        self.toolbar.addAction(self.terminal_action)

    def update_toolbar_buttons(self, index):
        # Hide all specific actions
        self.start_action.setVisible(False)
        self.stop_action.setVisible(False)
        self.remove_action.setVisible(False)
        self.create_network_action.setVisible(False)
        self.remove_network_action.setVisible(False)
        self.create_volume_action.setVisible(False)
        self.remove_volume_action.setVisible(False)
        self.terminal_action.setVisible(False)

        # Show actions based on the current tab
        if index == 0:  # Containers tab
            self.start_action.setVisible(True)
            self.stop_action.setVisible(True)
            self.remove_action.setVisible(True)
            self.terminal_action.setVisible(True)
        elif index == 1:  # Networks tab
            self.create_network_action.setVisible(True)
            self.remove_network_action.setVisible(True)
        elif index == 2:  # Volumes tab
            self.create_volume_action.setVisible(True)
            self.remove_volume_action.setVisible(True)

    def update_visible_tabs(self, index):
        for i in range(self.tab_widget.count()):
            if i == index:
                self.tab_widget.tabBar().setTabVisible(i, True)
            else:
                self.tab_widget.tabBar().setTabVisible(i, False)

    def create_menu_bar(self):
        menubar = self.menuBar()

        file_menu = menubar.addMenu("File")
        exit_action = QAction("Exit", self)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)

        docker_menu = menubar.addMenu("Docker")
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_data)
        docker_menu.addAction(refresh_action)

    def show_context_menu(self, position):
        context_menu = QMenu()
        current_tab = self.tab_widget.currentWidget()

        # Add refresh action to context menu
        refresh_action = QAction("Refresh", self)
        refresh_action.triggered.connect(self.refresh_data)
        context_menu.addAction(refresh_action)

        context_menu.addSeparator()

        if current_tab == self.containers_tab:
            terminal_action = QAction("Terminal", self)
            terminal_action.triggered.connect(lambda: self.handle_action("Terminal"))
            start_action = QAction("Start", self)
            start_action.triggered.connect(lambda: self.handle_action("Start"))
            stop_action = QAction("Stop", self)
            stop_action.triggered.connect(lambda: self.handle_action("Stop"))
            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(lambda: self.handle_action("Remove"))
            context_menu.addAction(terminal_action)            
            context_menu.addAction(start_action)
            context_menu.addAction(stop_action)
            context_menu.addAction(remove_action)
        elif current_tab == self.networks_tab:
            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(lambda: self.handle_action("Remove"))
            context_menu.addAction(remove_action)
        elif current_tab == self.volumes_tab:
            remove_action = QAction("Remove", self)
            remove_action.triggered.connect(lambda: self.handle_action("Remove"))
            context_menu.addAction(remove_action)

        context_menu.exec_(current_tab.mapToGlobal(position))
        
        # Connect the triggered signal of the context menu actions to a handler

    def setup_auto_refresh(self):
        self.refresh_timer = QTimer(self)
        self.refresh_timer.timeout.connect(self.refresh_data)
        if self.auto_refresh_checkbox.isChecked():
            self.refresh_timer.start(1000)  # 1000 ms = 1 second

    def toggle_auto_refresh(self, state):
        if state == Qt.Checked:
            self.refresh_timer.start(1000)
        else:
            self.refresh_timer.stop()

    def handle_action(self, action):
        current_tab = self.tab_widget.currentWidget()
        selected_items = current_tab.findChild(QTreeWidget).selectedItems()

        if not selected_items:
            return

        if current_tab == self.containers_tab:
            container_id = selected_items[0].text(0)
            if action == "Terminal":
                self.open_terminal()
            elif action == "Start":
                subprocess.run(["docker", "start", container_id])
            elif action == "Stop":
                subprocess.run(["docker", "stop", container_id])
            elif action == "Remove":
                subprocess.run(["docker", "rm", "-f", container_id])
        elif current_tab == self.networks_tab:
            network_id = selected_items[0].text(0)
            if action == "Remove":
                subprocess.run(["docker", "network", "rm", network_id])
        elif current_tab == self.volumes_tab:
            volume_name = selected_items[0].text(0)
            if action == "Remove":
                subprocess.run(["docker", "volume", "rm", volume_name])

        self.refresh_data()

        self.volumes_tree.clear()
        try:
            output = subprocess.check_output(["docker", "volume", "ls", "--format", "{{.Name}}\\t{{.Driver}}\\t{{.Mountpoint}}"], stderr=subprocess.STDOUT)
            volumes = output.decode().strip().split("\n")
            for volume in volumes:
                name, driver, mountpoint = volume.split("\t")
                item = QTreeWidgetItem([name, driver, mountpoint])
                self.volumes_tree.addTopLevelItem(item)
        except subprocess.CalledProcessError as e:
            print(f"Error refreshing volumes: {e.output.decode()}")
        except Exception as e:
            print(f"Unexpected error refreshing volumes: {str(e)}")

    def refresh_data(self):
        self.refresh_containers()
        self.refresh_networks()
        self.refresh_volumes()

    def refresh_containers(self):
        scroll_position = self.containers_tree.verticalScrollBar().value()
        selected_items = self.get_selected_items(self.containers_tree)
        self.containers_tree.clear()
        try:
            output = subprocess.check_output(["docker", "ps", "-a", "--format", "{{.ID}}\\t{{.Names}}\\t{{.Image}}\\t{{.Status}}\\t{{.Ports}}"], stderr=subprocess.STDOUT)
            if output.strip():
                containers = output.decode().strip().split("\n")
                for container in containers:
                    parts = container.split("\t")
                    id, name, image, status = parts[:4]
                    ports = parts[4] if len(parts) > 4 else ""
                    item = QTreeWidgetItem([id, name, image, "", ports])  # Empty string for status column
                    status_widget = StatusDelegate(status)
                    self.containers_tree.addTopLevelItem(item)
                    self.containers_tree.setItemWidget(item, 3, status_widget)
            self.restore_selection(self.containers_tree, selected_items)
        except subprocess.CalledProcessError as e:
            print(f"Error refreshing containers: {e.output.decode()}")
        except ValueError as e:
            print(f"Error parsing container list {repr(containers)}")
        except Exception as e:
            print(f"Unexpected error refreshing containers: {str(e)}")
        QTimer.singleShot(0, lambda: self.containers_tree.verticalScrollBar().setValue(scroll_position))

    def refresh_networks(self):
        scroll_position = self.networks_tree.verticalScrollBar().value()
        selected_items = self.get_selected_items(self.networks_tree)
        self.networks_tree.clear()
        try:
            output = subprocess.check_output(["docker", "network", "ls", "--format", "{{.ID}}\\t{{.Name}}\\t{{.Driver}}"], stderr=subprocess.STDOUT)
            networks = output.decode().strip().split("\n")
            for network in networks:
                id, name, driver = network.split("\t")
                item = QTreeWidgetItem([id, name, driver])
                self.networks_tree.addTopLevelItem(item)
            self.restore_selection(self.networks_tree, selected_items)
        except subprocess.CalledProcessError as e:
            print(f"Error refreshing networks: {e.output.decode()}")
        except Exception as e:
            print(f"Unexpected error refreshing networks: {str(e)}")
        QTimer.singleShot(0, lambda: self.networks_tree.verticalScrollBar().setValue(scroll_position))

    def refresh_volumes(self):
        scroll_position = self.volumes_tree.verticalScrollBar().value()
        selected_items = self.get_selected_items(self.volumes_tree)
        self.volumes_tree.clear()
        try:
            output = subprocess.check_output(["docker", "volume", "ls", "--format", "{{.Name}}\\t{{.Driver}}\\t{{.Mountpoint}}"], stderr=subprocess.STDOUT)
            volumes = output.decode().strip().split("\n")
            for volume in volumes:
                name, driver, mountpoint = volume.split("\t")
                item = QTreeWidgetItem([name, driver, mountpoint])
                self.volumes_tree.addTopLevelItem(item)
            self.restore_selection(self.volumes_tree, selected_items)
        except subprocess.CalledProcessError as e:
            print(f"Error refreshing volumes: {e.output.decode()}")
        except Exception as e:
            print(f"Unexpected error refreshing volumes: {str(e)}")
        QTimer.singleShot(0, lambda: self.volumes_tree.verticalScrollBar().setValue(scroll_position))

    def get_selected_items(self, tree):
        return [item.text(0) for item in tree.selectedItems()]

    def restore_selection(self, tree, selected_items):
        for i in range(tree.topLevelItemCount()):
            item = tree.topLevelItem(i)
            if item.text(0) in selected_items:
                item.setSelected(True)

    def start_container(self):
        selected_items = self.containers_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a container to start.")
            return

        for item in selected_items:
            container_id = item.text(0)
            try:
                subprocess.run(["docker", "start", container_id], check=True)
                print(f"Started container: {container_id}")
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self, "Error", f"Failed to start container {container_id}: {e}")

        self.refresh_containers()

    def stop_container(self):
        selected_items = self.containers_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a container to stop.")
            return

        for item in selected_items:
            container_id = item.text(0)
            try:
                subprocess.run(["docker", "stop", container_id], check=True)
                print(f"Stopped container: {container_id}")
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self, "Error", f"Failed to stop container {container_id}: {e}")

        self.refresh_containers()

    def remove_container(self):
        selected_items = self.containers_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a container to remove.")
            return

        for item in selected_items:
            container_id = item.text(0)
            reply = QMessageBox.question(self, "Confirm Removal", 
                                         f"Are you sure you want to remove container {container_id}?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    subprocess.run(["docker", "rm", "-f", container_id], check=True)
                    print(f"Removed container: {container_id}")
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self, "Error", f"Failed to remove container {container_id}: {e}")

        self.refresh_containers()

    def create_network(self):
        network_name, ok = QInputDialog.getText(self, "Create Network", "Enter network name:")
        if ok and network_name:
            try:
                subprocess.run(["docker", "network", "create", network_name], check=True)
                print(f"Created network: {network_name}")
                QMessageBox.information(self, "Success", f"Network '{network_name}' created successfully.")
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self, "Error", f"Failed to create network: {e}")

        self.refresh_networks()
        
    def remove_network(self):
        selected_items = self.networks_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a network to remove.")
            return

        for item in selected_items:
            network_name = item.text(1)  # Assuming the network name is in the second column
            reply = QMessageBox.question(self, "Confirm Removal", 
                                         f"Are you sure you want to remove network {network_name}?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    subprocess.run(["docker", "network", "rm", network_name], check=True)
                    print(f"Removed network: {network_name}")
                    QMessageBox.information(self, "Success", f"Network '{network_name}' removed successfully.")
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self, "Error", f"Failed to remove network {network_name}: {e}")

        self.refresh_networks()

    def create_volume(self):
        volume_name, ok = QInputDialog.getText(self, "Create Volume", "Enter volume name:")
        if ok and volume_name:
            try:
                subprocess.run(["docker", "volume", "create", volume_name], check=True)
                print(f"Created volume: {volume_name}")
                QMessageBox.information(self, "Success", f"Volume '{volume_name}' created successfully.")
            except subprocess.CalledProcessError as e:
                QMessageBox.critical(self, "Error", f"Failed to create volume: {e}")

        self.refresh_volumes()

    def remove_volume(self):
        selected_items = self.volumes_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a volume to remove.")
            return

        for item in selected_items:
            volume_name = item.text(0)  # Assuming the volume name is in the first column
            reply = QMessageBox.question(self, "Confirm Removal", 
                                         f"Are you sure you want to remove volume {volume_name}?",
                                         QMessageBox.Yes | QMessageBox.No, QMessageBox.No)
            if reply == QMessageBox.Yes:
                try:
                    subprocess.run(["docker", "volume", "rm", volume_name], check=True)
                    print(f"Removed volume: {volume_name}")
                    QMessageBox.information(self, "Success", f"Volume '{volume_name}' removed successfully.")
                except subprocess.CalledProcessError as e:
                    QMessageBox.critical(self, "Error", f"Failed to remove volume {volume_name}: {e}")

        self.refresh_volumes()
        
    def open_terminal(self):
        selected_items = self.containers_tree.selectedItems()
        if not selected_items:
            QMessageBox.warning(self, "No Selection", "Please select a container to open terminal.")
            return

        container_id = selected_items[0].text(0)
        
        self.terminal_opener = TerminalOpener(container_id)
        self.terminal_opener.error.connect(self.show_terminal_error)
        self.terminal_opener.start()

    def show_terminal_error(self, error_message):
        QMessageBox.critical(self, "Error", error_message)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DockerGUI()
    window.show()
    sys.exit(app.exec_())