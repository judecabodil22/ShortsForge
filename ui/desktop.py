#!/usr/bin/env python3
"""
ShortsForge Desktop Application
Side-by-side button/terminal interface for pipeline control.
"""
import os
import sys
import glob
import shutil
import subprocess
from datetime import datetime

WORKSPACE = os.path.expanduser("~/ShortsForge")
if WORKSPACE not in sys.path:
    sys.path.insert(0, WORKSPACE)

try:
    from PyQt6.QtWidgets import (
        QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
        QPushButton, QTextEdit, QLabel, QFrame, QGroupBox,
        QStatusBar, QMenuBar, QMenu, QMessageBox, QSplitter, QTextBrowser,
        QInputDialog, QRadioButton, QScrollArea
    )
    from PyQt6.QtCore import Qt, QTimer
    from PyQt6.QtGui import QFont, QAction
    PYQT6_AVAILABLE = True
except ImportError:
    PYQT6_AVAILABLE = False


class ShortsForgeDesktop(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ShortsForge Desktop v2.0.0")
        self.setMinimumSize(1000, 700)
        self.pipeline_running = False
        
        self.init_ui()
        self.load_styles()
        self.start_status_timer()

    def init_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        
        main_layout = QHBoxLayout()
        central.setLayout(main_layout)
        
        left_panel = self.create_button_panel()
        right_panel = self.create_terminal_panel()
        
        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left_panel)
        splitter.addWidget(right_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 2)
        splitter.setSizes([350, 650])
        
        main_layout.addWidget(splitter)
        
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
        
        self.create_menu_bar()

    def create_button_panel(self):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout()
        layout.setSpacing(5)
        layout.setContentsMargins(5, 5, 5, 5)
        frame.setLayout(layout)
        
        title = QLabel("ShortsForge Desktop\nv2.0.0")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(title)
        
        pipeline_group = QGroupBox("PIPELINE CONTROL")
        pipeline_layout = QVBoxLayout()
        pipeline_layout.setSpacing(5)
        
        btn_run = QPushButton("Run Full Pipeline")
        btn_run.clicked.connect(self.run_full_pipeline)
        pipeline_layout.addWidget(btn_run)
        
        btn_stop = QPushButton("Stop Pipeline")
        btn_stop.clicked.connect(self.stop_pipeline)
        pipeline_layout.addWidget(btn_stop)
        
        btn_restart = QPushButton("Restart Listener")
        btn_restart.clicked.connect(self.start_listener)
        pipeline_layout.addWidget(btn_restart)
        
        pipeline_group.setLayout(pipeline_layout)
        layout.addWidget(pipeline_group)
        
        source_group = QGroupBox("SOURCE")
        source_layout = QVBoxLayout()
        source_layout.setSpacing(5)
        
        self.source_youtube = QRadioButton("YouTube Playlist")
        self.source_youtube.setChecked(True)
        self.source_local = QRadioButton("Local Recordings")
        source_layout.addWidget(self.source_youtube)
        source_layout.addWidget(self.source_local)
        
        source_group.setLayout(source_layout)
        layout.addWidget(source_group)
        
        phases_group = QGroupBox("SEQUENCE PHASES")
        phases_layout = QVBoxLayout()
        phases_layout.setSpacing(5)
        
        for label, phase in [
            ("Phase 1 (YT-DLP)", "1"), 
            ("Phase 1 (Local)", "1"), 
            ("Phase 2 (Transcribe)", "2"), 
            ("Phase 2.5 (Context)", "2.5"), 
            ("Phase 3 (Scripts)", "3"), 
            ("Phase 4 (Clips)", "4"), 
            ("Phase 5 (TTS)", "5")
        ]:
            btn = QPushButton(label)
            btn.clicked.connect(lambda _, p=phase: self.run_phase(p))
            phases_layout.addWidget(btn)
        
        phases_group.setLayout(phases_layout)
        layout.addWidget(phases_group)
        
        cs_group = QGroupBox("CONTENT STUDIO")
        cs_layout = QVBoxLayout()
        cs_layout.setSpacing(5)
        
        btn_cs = QPushButton("Open Content Studio")
        btn_cs.clicked.connect(self.open_content_studio)
        cs_layout.addWidget(btn_cs)
        
        btn_ctx = QPushButton("View Context")
        btn_ctx.clicked.connect(self.view_context)
        cs_layout.addWidget(btn_ctx)
        
        btn_clear = QPushButton("Clear Context")
        btn_clear.clicked.connect(self.clear_context)
        cs_layout.addWidget(btn_clear)
        
        cs_group.setLayout(cs_layout)
        layout.addWidget(cs_group)
        
        tools_group = QGroupBox("SYSTEM TOOLS")
        tools_layout = QVBoxLayout()
        tools_layout.setSpacing(5)
        
        btn_cfg = QPushButton("View Configuration")
        btn_cfg.clicked.connect(self.show_config)
        tools_layout.addWidget(btn_cfg)
        
        btn_set_voice = QPushButton("Set Voice")
        btn_set_voice.clicked.connect(self.set_voice)
        tools_layout.addWidget(btn_set_voice)
        
        btn_set_game = QPushButton("Set Game Title")
        btn_set_game.clicked.connect(self.set_game)
        tools_layout.addWidget(btn_set_game)
        
        btn_set_clips = QPushButton("Set Clips/Hour")
        btn_set_clips.clicked.connect(self.set_clips)
        tools_layout.addWidget(btn_set_clips)
        
        btn_listen = QPushButton("Start Listener")
        btn_listen.clicked.connect(self.start_listener)
        tools_layout.addWidget(btn_listen)
        
        btn_stop_listen = QPushButton("Stop Listener")
        btn_stop_listen.clicked.connect(self.stop_listener)
        tools_layout.addWidget(btn_stop_listen)
        
        btn_cleanup = QPushButton("Cleanup Files")
        btn_cleanup.clicked.connect(self.cleanup_files)
        tools_layout.addWidget(btn_cleanup)
        
        btn_ver = QPushButton("Version")
        btn_ver.clicked.connect(self.show_version)
        tools_layout.addWidget(btn_ver)
        
        tools_group.setLayout(tools_layout)
        layout.addWidget(tools_group)
        
        layout.addStretch()
        
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setWidget(frame)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        return scroll

    def create_terminal_panel(self):
        frame = QFrame()
        frame.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QVBoxLayout()
        frame.setLayout(layout)
        
        title = QLabel("TERMINAL")
        
        layout.addWidget(title)
        
        self.status_display = QTextBrowser()
        self.status_display.setReadOnly(True)
        
        layout.addWidget(self.status_display)
        
        log_label = QLabel("LOG STREAM")
        
        layout.addWidget(log_label)
        
        self.log_display = QTextEdit()
        self.log_display.setReadOnly(True)
        
        layout.addWidget(self.log_display)
        
        return frame

    def create_menu_bar(self):
        menubar = self.menuBar()
        
        file_menu = menubar.addMenu("File")
        refresh_action = QAction("Refresh Status", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self.refresh_status)
        file_menu.addAction(refresh_action)
        file_menu.addSeparator()
        quit_action = QAction("Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)
        
        view_menu = menubar.addMenu("View")
        clear_log_action = QAction("Clear Log", self)
        clear_log_action.triggered.connect(self.clear_log)
        view_menu.addAction(clear_log_action)
        
        help_menu = menubar.addMenu("Help")
        about_action = QAction("About", self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)

    def load_styles(self):
        black = "#0A0A0A"
        dark_brown = "#2E1C15"
        light_brown = "#8B5A2B"
        caramel = "#CD853F"
        cream = "#F5DEB3"
        sepia = "#704214"
        
        self.setStyleSheet(f"""
            QMainWindow {{
                background-color: {black};
            }}
            QWidget {{
                background-color: {black};
                color: {cream};
                font-family: "Courier New", monospace;
                font-size: 14px;
            }}
            QGroupBox {{
                color: {caramel};
                font-weight: bold;
                border: 2px solid {sepia};
                border-radius: 5px;
                margin-top: 25px;
                padding-top: 15px;
                background-color: {dark_brown};
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                subcontrol-position: top center;
                top: 5px;
                padding: 2px 10px;
                background-color: {black};
                color: {caramel};
                border: 1px solid {sepia};
                border-radius: 4px;
            }}
            QScrollArea {{
                background: transparent;
                border: none;
            }}
            QScrollBar:vertical {{
                background: {black};
                width: 14px;
                margin: 0px;
                border-left: 1px solid {sepia};
            }}
            QScrollBar::handle:vertical {{
                background: {light_brown};
                min-height: 20px;
                border: 1px solid {black};
            }}
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {{
                height: 0px;
            }}
            QPushButton {{
                background-color: {dark_brown};
                color: {cream};
                border: 1px solid {light_brown};
                border-radius: 4px;
                padding: 6px 15px;
                min-height: 30px;
                text-align: left;
                font-weight: bold;
            }}
            QPushButton:hover {{
                background-color: {sepia};
                color: {cream};
            }}
            QPushButton:pressed {{
                background-color: {light_brown};
                color: {black};
            }}
            QPushButton:disabled {{
                background-color: {black};
                color: {sepia};
                border-color: {sepia};
            }}
            QLabel {{
                color: {cream};
            }}
            QFrame {{
                background-color: transparent;
                border: none;
            }}
            QSplitter::handle {{
                background-color: {sepia};
                width: 4px;
            }}
            QTextEdit, QTextBrowser {{
                background-color: {black};
                color: {caramel};
                border: 2px solid {sepia};
                padding: 8px;
                font-family: "Courier New", monospace;
                font-size: 13px;
                border-radius: 0px;
            }}
            QStatusBar {{
                background-color: {black};
                color: {caramel};
                border-top: 1px solid {sepia};
            }}
            QMenuBar {{
                background-color: {black};
                color: {caramel};
                border-bottom: 1px solid {sepia};
            }}
            QMenuBar::item:selected {{
                background-color: {sepia};
                color: {cream};
            }}
            QMenu {{
                background-color: {black};
                color: {caramel};
                border: 1px solid {sepia};
            }}
            QMenu::item:selected {{
                background-color: {sepia};
                color: {cream};
            }}
        """)

    def start_status_timer(self):
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_status)
        self.status_timer.start(3000)
        self.refresh_status()

    def refresh_status(self):
        try:
            version_file = os.path.join(WORKSPACE, "VERSION")
            version = "Unknown"
            if os.path.exists(version_file):
                with open(version_file) as f:
                    version = f.read().strip()
            
            sc = len(glob.glob(os.path.join(WORKSPACE, "scripts", "*.txt")))
            cc = len(glob.glob(os.path.join(WORKSPACE, "shorts", "*.mp4")))
            wc = len(glob.glob(os.path.join(WORKSPACE, "tts", "*.wav")))
            tc = len(glob.glob(os.path.join(WORKSPACE, "transcripts", "*.json")))
            
            game = "Not set"
            env_file = os.path.join(WORKSPACE, ".env")
            if os.path.exists(env_file):
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("GAME_TITLE="):
                            game = line.split("=", 1)[1].strip() or "Not set"
                            break
            
            status = "Idle"
            if self.pipeline_running:
                status = "Running"
            
            
            voice = "Not set"
            if os.path.exists(env_file):
                with open(env_file) as f:
                    for line in f:
                        if line.startswith("TTS_VOICE="):
                            cream = "#F5DEB3"
            caramel = "#CD853F"
            sepia = "#704214"
            dark_brown = "#2E1C15"

            html = f"""
            <div style="font-family: 'Courier New', monospace; font-size: 14px; color: {cream}; padding: 15px; background-color: #0A0A0A; border: 1px solid {sepia};">
                <h2 style="color: {caramel}; margin-top: 0; border-bottom: 1px solid {sepia}; padding-bottom: 8px;">SHORTSFORGE TERMINAL v{version}</h2>
                <table style="width: 100%; margin-top: 15px;">
                    <tr><td style="color: {sepia}; width: 140px;">Pipeline Status:</td><td style="color: {cream}; font-weight: bold;">{status}</td></tr>
                </table>
                <h3 style="color: {caramel}; margin-top: 25px; border-bottom: 1px solid {sepia}; display: inline-block;">Storage Statistics</h3>
                <table style="width: 100%;">
                    <tr><td style="color: {sepia}; width: 140px;">Scripts Generated:</td><td style="color: {cream};">{sc} files</td></tr>
                    <tr><td style="color: {sepia};">Clips Generated:</td><td style="color: {cream};">{cc} files</td></tr>
                    <tr><td style="color: {sepia};">Audio Tracks:</td><td style="color: {cream};">{wc} files</td></tr>
                    <tr><td style="color: {sepia};">Transcripts:</td><td style="color: {cream};">{tc} files</td></tr>
                </table>
                <h3 style="color: {caramel}; margin-top: 25px; border-bottom: 1px solid {sepia}; display: inline-block;">System Configuration</h3>
                <table style="width: 100%;">
                    <tr><td style="color: {sepia}; width: 140px;">Target Game:</td><td style="color: {cream};">"{game}"</td></tr>
                    <tr><td style="color: {sepia};">Voice Model:</td><td style="color: {cream};">"{voice}"</td></tr>
                </table>
            </div>
            """
            self.status_display.setHtml(html)
        except Exception as e:
            self.log(f"Error refreshing status: {e}")

    def log(self, msg):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_display.append(f"[{timestamp}] {msg}")

    def clear_log(self):
        self.log_display.clear()

    def run_full_pipeline(self):
        if self.pipeline_running:
            self.log("Pipeline already running!")
            return
        
        is_local = self.source_local.isChecked()
        recording_path = os.path.join(WORKSPACE, "recordings")
        
        if is_local:
            if not os.path.exists(recording_path):
                os.makedirs(recording_path, exist_ok=True)
                self.log(f"Created recordings directory: {recording_path}")
                self.log("Please add video files to this directory and run again.")
                return
            
            video_files = []
            for ext in ['*.mp4', '*.mkv', '*.avi', '*.mov', '*.webm']:
                video_files.extend(glob.glob(os.path.join(recording_path, ext)))
            
            if not video_files:
                self.log(f"No video files found in {recording_path}")
                return
            
            self.log(f"Starting local recordings pipeline ({len(video_files)} files)...")
            self.pipeline_running = True
            self.status_bar.showMessage(f"Processing {len(video_files)} local recording(s)...")
            subprocess.Popen([sys.executable, "workflows/shortsforge.py", "run_local", recording_path], cwd=WORKSPACE)
        else:
            self.log("Starting full pipeline (YouTube)...")
            self.pipeline_running = True
            self.status_bar.showMessage("Running pipeline...")
            subprocess.Popen([sys.executable, "workflows/shortsforge.py", "run"], cwd=WORKSPACE)

    def run_phase(self, phase):
        if self.pipeline_running:
            self.log("Pipeline already running!")
            return
        
        is_local = self.source_local.isChecked()
        
        if is_local and int(phase) == 1:
            self.log("Phase 1 for local recordings: copy videos to streams/")
            recording_path = os.path.join(WORKSPACE, "recordings")
            
            if not os.path.exists(recording_path):
                self.log("Recordings directory not found.")
                return
            
            video_files = []
            for ext in ['*.mp4', '*.mkv', '*.avi', '*.mov', '*.webm']:
                video_files.extend(glob.glob(os.path.join(recording_path, ext)))
            
            if not video_files:
                self.log("No video files found.")
                return
            
            streams_dir = os.path.join(WORKSPACE, "streams")
            os.makedirs(streams_dir, exist_ok=True)
            
            copied = 0
            for vf in video_files:
                fname = os.path.basename(vf)
                dest = os.path.join(streams_dir, fname)
                if not os.path.exists(dest):
                    shutil.copy2(vf, dest)
                    self.log(f"Copied: {fname}")
                    copied += 1
                else:
                    self.log(f"Already exists: {fname}")
            
            self.log(f"Phase 1 complete. {copied} new file(s) copied to streams/")
            return
        
        if is_local:
            self.log(f"Note: Local recording phases require full run. Use 'Run Local Recordings' instead.")
            self.log("Local recordings pipeline processes all phases (2-5) in sequence.")
            return
        
        self.log(f"Starting phase {phase} (YouTube)...")
        self.pipeline_running = True
        self.status_bar.showMessage(f"Running phase {phase}...")
        subprocess.Popen([sys.executable, "workflows/shortsforge.py", "run", "-phase", phase], cwd=WORKSPACE)

    def run_local_recordings(self):
        if self.pipeline_running:
            self.log("Pipeline already running!")
            return
        
        recording_path = os.path.join(WORKSPACE, "recordings")
        if not os.path.exists(recording_path):
            os.makedirs(recording_path, exist_ok=True)
            self.log(f"Created recordings directory: {recording_path}")
            self.log("Please add video files to this directory and run again.")
            return
        
        video_files = []
        for ext in ['*.mp4', '*.mkv', '*.avi', '*.mov', '*.webm']:
            video_files.extend(glob.glob(os.path.join(recording_path, ext)))
        
        if not video_files:
            self.log(f"No video files found in {recording_path}")
            self.log("Supported formats: mp4, mkv, avi, mov, webm")
            return
        
        self.log(f"Found {len(video_files)} local recording(s)")
        self.log("Starting local recordings pipeline...")
        self.pipeline_running = True
        self.status_bar.showMessage(f"Processing {len(video_files)} local recording(s)...")
        subprocess.Popen([sys.executable, "workflows/shortsforge.py", "run_local", recording_path], cwd=WORKSPACE)

    def stop_pipeline(self):
        self.log("Stop requested...")
        self.pipeline_running = False
        self.status_bar.showMessage("Pipeline stopped")

    def open_content_studio(self):
        self.log("Opening Content Studio...")
        cs_dir = os.path.join(WORKSPACE, "content_studio")
        transcripts = len(glob.glob(os.path.join(cs_dir, "transcripts", "*.json")))
        shorts = len(glob.glob(os.path.join(cs_dir, "shorts", "*.mp4")))
        scripts = len(glob.glob(os.path.join(cs_dir, "scripts", "*.txt")))
        self.log(f"Content Studio: {transcripts} transcripts, {shorts} shorts, {scripts} scripts")

    def view_context(self):
        import json
        ctx_file = os.path.join(WORKSPACE, "Context", "verified_context.json")
        if not os.path.exists(ctx_file):
            self.log("No verified context found.")
            return
        try:
            with open(ctx_file) as f:
                data = json.load(f)
            game = "tell me why"
            if game in data:
                ctx = data[game].get("context", {})
                chars = ctx.get("characters", [])
                self.log(f"Context: {len(chars)} characters loaded")
            else:
                self.log("No context for current game.")
        except Exception as e:
            self.log(f"Error reading context: {e}")

    def clear_context(self):
        reply = QMessageBox.question(self, "Clear Context", "Clear all context?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            ctx_file = os.path.join(WORKSPACE, "Context", "verified_context.json")
            if os.path.exists(ctx_file):
                os.remove(ctx_file)
                self.log("Context cleared.")
            else:
                self.log("No context to clear.")

    def show_config(self):
        env_file = os.path.join(WORKSPACE, ".env")
        if not os.path.exists(env_file):
            self.log("No .env file found.")
            return
        config = {}
        with open(env_file) as f:
            for line in f:
                if "=" in line:
                    k, v = line.strip().split("=", 1)
                    config[k] = v
        self.log("=" * 40)
        self.log("⚙️ Configuration")
        for k in ["GAME_TITLE", "TTS_VOICE", "TTS_STYLE", "PLAYLIST_URL", "PLAYLIST_INDEX", "CLIPS_PER_HOUR", "SOURCE_TYPE"]:
            self.log(f"{k}: {config.get(k, '(not set)')}")
        self.log("=" * 40)

    def set_voice(self):
        voice, ok = QInputDialog.getText(self, "Set Voice", "Enter TTS voice name:\n(e.g., Vindemiatrix, Puck, Aoede)")
        if ok and voice:
            self.update_env("TTS_VOICE", voice)
            self.log(f"TTS voice set to: {voice}")

    def set_game(self):
        game, ok = QInputDialog.getText(self, "Set Game", "Enter game title:")
        if ok and game:
            self.update_env("GAME_TITLE", game)
            self.log(f"Game title set to: {game}")
        elif ok and not game:
            self.update_env("GAME_TITLE", "")
            self.log("Game title cleared")

    def set_clips(self):
        clips, ok = QInputDialog.getInt(self, "Set Clips", "Clips per hour (1-20):", 5, 1, 20)
        if ok:
            self.update_env("CLIPS_PER_HOUR", str(clips))
            self.log(f"Clips per hour set to: {clips}")

    def update_env(self, key, value):
        env_file = os.path.join(WORKSPACE, ".env")
        config = {}
        if os.path.exists(env_file):
            with open(env_file) as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        config[k] = v
        
        config[key] = value
        
        with open(env_file, "w") as f:
            for k, v in config.items():
                f.write(f"{k}={v}\n")

    def start_listener(self):
        self.log("Starting Telegram listener...")
        subprocess.Popen([sys.executable, "workflows/shortsforge.py", "listen"], cwd=WORKSPACE)
        self.log("Listener started in background")

    def stop_listener(self):
        self.log("Stopping Telegram listener...")
        subprocess.run([sys.executable, "workflows/shortsforge.py", "stop"], cwd=WORKSPACE)
        self.log("Listener stopped")

    def cleanup_files(self):
        reply = QMessageBox.question(self, "Cleanup", "Delete all generated files?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if reply == QMessageBox.StandardButton.Yes:
            for d in ["scripts", "shorts", "tts", "transcripts"]:
                path = os.path.join(WORKSPACE, d)
                files = glob.glob(os.path.join(path, "*"))
                for f in files:
                    try:
                        os.remove(f) if os.path.isfile(f) else None
                    except:
                        pass
            self.log("Files cleaned up.")

    def show_version(self):
        version_file = os.path.join(WORKSPACE, "VERSION")
        version = "Unknown"
        if os.path.exists(version_file):
            with open(version_file) as f:
                version = f.read().strip()
        self.log(f"ShortsForge v{version}")

    def show_about(self):
        QMessageBox.about(self, "About ShortsForge", "ShortsForge Desktop\nVersion 2.0.0\n\nYouTube Shorts Pipeline")

    def closeEvent(self, event):
        if self.pipeline_running:
            reply = QMessageBox.question(self, "Running Pipeline", "Pipeline is running. Quit anyway?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.No:
                event.ignore()
                return
        event.accept()


def main():
    if not PYQT6_AVAILABLE:
        print("PyQt6 not installed. Install with: pip install PyQt6")
        sys.exit(1)
    
    app = QApplication(sys.argv)
    app.setApplicationName("ShortsForge")
    window = ShortsForgeDesktop()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()