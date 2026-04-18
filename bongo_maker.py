import sys, os, json, math, subprocess, importlib.util, time

# --- TỰ ĐỘNG CÀI ĐẶT THƯ VIỆN ---
def setup_env():
    for p in ['PyQt5', 'keyboard', 'pynput']:
        if importlib.util.find_spec(p) is None:
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", p, "--break-system-packages"])
            except: pass
setup_env()

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from pynput import mouse

CONFIG_FILE = "vam_keyboard_v16.json"

# [Phần LanguageSelect, ImportWindow, MouseTracker giữ nguyên logic chuẩn của ông]
class LanguageSelect(QDialog):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("vâm keyboard"); self.setFixedSize(300, 150); self.choice = "VN"
        layout = QVBoxLayout(); layout.addWidget(QLabel("CHỌN NGÔN NGỮ / SELECT LANGUAGE", alignment=Qt.AlignCenter))
        vn = QPushButton("Tiếng Việt"); vn.clicked.connect(lambda: self.done_with("VN"))
        en = QPushButton("English"); en.clicked.connect(lambda: self.done_with("EN"))
        layout.addWidget(vn); layout.addWidget(en); self.setLayout(layout)
    def done_with(self, l): self.choice = l; self.accept()

class ImportWindow(QDialog):
    def __init__(self, lang):
        super().__init__()
        self.lang, self.paths = lang, {}
        self.setWindowTitle("Import Files"); self.setFixedSize(400, 500); layout = QVBoxLayout()
        self.txt = {"VN": ["Nền", "Tay trái", "Chuột", "Tay phải(trên)", "Tay phải(dưới)", "TIẾP TỤC"],
                    "EN": ["Background", "Leftarm", "Mouse", "Rightarm(up)", "Rightarm(down)", "NEXT"]}[self.lang]
        self.btns = []
        for i in range(5):
            b = QPushButton(self.txt[i]); b.clicked.connect(lambda _, x=i: self.get_p(x))
            layout.addWidget(b); self.btns.append(b)
        btn_ok = QPushButton(self.txt[5]); btn_ok.setStyleSheet("height:60px; background: #2ecc71; color: white; font-weight: bold;")
        btn_ok.clicked.connect(self.accept); layout.addWidget(btn_ok); self.setLayout(layout)
    def get_p(self, i):
        k = ['background', 'leftarm', 'mouse', 'rightarm_up', 'rightarm_down']
        p, _ = QFileDialog.getOpenFileName(self, "Chọn ảnh PNG", "", "Images (*.png *.jpg)")
        if p: self.paths[k[i]] = p; self.btns[i].setStyleSheet("background: #bcffbc;")

class MouseTracker(QThread):
    move_signal = pyqtSignal(float, float)
    def run(self):
        self.last_x, self.last_y = None, None
        screen = QApplication.primaryScreen().size()
        self.cx, self.cy = screen.width() // 2, screen.height() // 2
        with mouse.Listener(on_move=self.on_move) as listener: listener.join()
    def on_move(self, x, y):
        if self.last_x is None: self.last_x, self.last_y = x, y; return
        dx, dy = x - self.last_x, y - self.last_y
        if abs(x - self.cx) < 2 and abs(y - self.cy) < 2 and (abs(dx) > 5 or abs(dy) > 5):
            self.last_x, self.last_y = x, y; return
        if dx != 0 or dy != 0: self.move_signal.emit(float(dx), float(dy))
        self.last_x, self.last_y = x, y

class VamEditor(QWidget):
    def __init__(self, paths, lang, tuning=None, profile_name=None):
        super().__init__(); self.paths, self.lang, self.profile_name = paths, lang, profile_name
        self.setFixedSize(1400, 900); self.sel = 'background'; self.drag = False; self.act_area = None; self.act_pivot = None
        default = {'background': {'pos': QPoint(450, 350), 'w': 900, 'h': 700, 'rot': 0},
                   'rightarm_up': {'pos': QPoint(650, 450), 'w': 250, 'h': 350, 'rot': 0},
                   'leftarm': {'pos': QPoint(300, 450), 'w': 350, 'h': 180, 'rot': 0},
                   'mouse': {'pos': QPoint(200, 450), 'w': 80, 'h': 80, 'rot': 0},
                   'mouse_area': [QPoint(100, 400), QPoint(400, 400), QPoint(400, 600), QPoint(100, 600)],
                   'hand_pivots': [[0.9, 0.5], [0.1, 0.5]]}
        self.tuning = tuning if tuning else default
        self.initUI()
    def initUI(self):
        main = QHBoxLayout(); side = QFrame(); side.setFixedWidth(320); sl = QVBoxLayout(side)
        txt = {"VN": ["Nền", "Tay trái", "Chuột", "Rigging", "Vùng Pad", "Tay phải", "RỘNG:", "CAO:", "XOAY:", "LƯU & CHẠY 🚀"],
               "EN": ["Background", "Leftarm", "Mouse", "2-Point Rig", "Mouse Area", "Rightarm", "WIDTH:", "HEIGHT:", "ROTATION:", "SAVE & LIVE 🚀"]}[self.lang]
        keys = ['background', 'leftarm', 'mouse', 'hand_rig', 'mouse_area', 'rightarm_up']
        for i, k in enumerate(keys):
            b = QPushButton(txt[i]); b.clicked.connect(lambda _, x=k: self.set_sel(x)); sl.addWidget(b)
        self.sl_w = QSlider(Qt.Horizontal); self.sl_w.setRange(10, 2500); self.sl_w.sliderMoved.connect(self.upd)
        self.sl_h = QSlider(Qt.Horizontal); self.sl_h.setRange(10, 2500); self.sl_h.sliderMoved.connect(self.upd)
        self.sl_r = QSlider(Qt.Horizontal); self.sl_r.setRange(-180, 180); self.sl_r.sliderMoved.connect(self.upd)
        sl.addSpacing(20); sl.addWidget(QLabel(txt[6])); sl.addWidget(self.sl_w); sl.addWidget(QLabel(txt[7])); sl.addWidget(self.sl_h); sl.addWidget(QLabel(txt[8])); sl.addWidget(self.sl_r)
        btn_go = QPushButton(txt[9]); btn_go.setStyleSheet("height:80px; background: #3498db; color: white; font-weight: bold;"); btn_go.clicked.connect(self.ask_save_and_live)
        sl.addStretch(); sl.addWidget(btn_go)
        self.cv = self.Canvas(self); main.addWidget(side); main.addWidget(self.cv); self.setLayout(main); self.sync_sliders()
    def set_sel(self, k): self.sel = k; self.sync_sliders(); self.cv.update()
    def sync_sliders(self):
        if self.sel in self.tuning and 'w' in self.tuning[self.sel]:
            obj = self.tuning[self.sel]; self.sl_w.setValue(obj['w']); self.sl_h.setValue(obj['h']); self.sl_r.setValue(obj['rot'])
    def upd(self):
        if self.sel in self.tuning and 'w' in self.tuning[self.sel]:
            self.tuning[self.sel]['w'], self.tuning[self.sel]['h'], self.tuning[self.sel]['rot'] = self.sl_w.value(), self.sl_h.value(), self.sl_r.value()
        self.cv.update()
    def ask_save_and_live(self):
        if not self.profile_name:
            name, ok = QInputDialog.getText(self, "Save", "Tên profile:"); self.profile_name = name if ok else "NewProfile"
        s_t = {}
        for k, v in self.tuning.items():
            if k == 'mouse_area': s_t[k] = [[p.x(), p.y()] for p in v]
            elif k in ['background', 'rightarm_up', 'leftarm', 'mouse']: s_t[k] = {'x': v['pos'].x(), 'y': v['pos'].y(), 'w': v['w'], 'h': v['h'], 'rot': v['rot']}
            else: s_t[k] = v
        data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
            except: pass
        data[self.profile_name] = {'paths': self.paths, 'lang': self.lang, 'tuning': s_t}
        with open(CONFIG_FILE, 'w', encoding='utf-8') as f: json.dump(data, f, indent=4)
        self.live = LiveApp(self.paths, self.tuning, self.lang); self.live.show(); self.hide()

    class Canvas(QWidget):
        def __init__(self, ed): super().__init__(); self.ed = ed; self.setFixedSize(1000, 850)
        def paintEvent(self, e):
            p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); t = self.ed.tuning
            for k in ['background', 'rightarm_up', 'mouse']:
                obj = t[k]; p.save(); p.translate(obj['pos']); p.rotate(obj['rot'])
                p.drawPixmap(int(-obj['w']//2), int(-obj['h']//2), int(obj['w']), int(obj['h']), QPixmap(self.ed.paths[k])); p.restore()
            tl = t['leftarm']; p.save(); p.translate(tl['pos']); p.rotate(tl['rot'])
            p.drawPixmap(int(-tl['w']//2), int(-tl['h']//2), int(tl['w']), int(tl['h']), QPixmap(self.ed.paths['leftarm'])); p.restore()
            p.setPen(QPen(Qt.cyan, 2)); p.drawPolygon(QPolygonF(t['mouse_area']))
            r_l = QRect(int(tl['pos'].x()-tl['w']//2), int(tl['pos'].y()-tl['h']//2), int(tl['w']), int(tl['h']))
            p.setBrush(Qt.yellow)
            for rel in t['hand_pivots']:
                pt = QPoint(int(r_l.left() + rel[0]*r_l.width()), int(r_l.top() + rel[1]*r_l.height())); p.drawEllipse(pt, 8, 8)
        def mousePressEvent(self, e):
            pos, t = e.pos(), self.ed.tuning
            if self.ed.sel == 'hand_rig':
                r_l = QRect(int(t['leftarm']['pos'].x()-t['leftarm']['w']//2), int(t['leftarm']['pos'].y()-t['leftarm']['h']//2), int(t['leftarm']['w']), int(t['leftarm']['h']))
                for i, rel in enumerate(t['hand_pivots']):
                    v_pt = QPoint(int(r_l.left() + rel[0]*r_l.width()), int(r_l.top() + rel[1]*r_l.height()))
                    if (v_pt - pos).manhattanLength() < 15: self.ed.act_pivot = i; return
            for i, pt in enumerate(t['mouse_area']):
                if (pt - pos).manhattanLength() < 15: self.ed.act_area = i; return
            if self.ed.sel in t and 'pos' in t[self.ed.sel]: self.ed.drag = True; self.ed.off = pos - t[self.ed.sel]['pos']
        def mouseMoveEvent(self, e):
            t = self.ed.tuning
            if self.ed.act_pivot is not None:
                r_l = QRect(int(t['leftarm']['pos'].x()-t['leftarm']['w']//2), int(t['leftarm']['pos'].y()-t['leftarm']['h']//2), int(t['leftarm']['w']), int(t['leftarm']['h']))
                t['hand_pivots'][self.ed.act_pivot] = [(e.x()-r_l.left())/r_l.width(), (e.y()-r_l.top())/r_l.height()]
            elif self.ed.act_area is not None: t['mouse_area'][self.ed.act_area] = e.pos()
            elif self.ed.drag: t[self.ed.sel]['pos'] = e.pos() - self.ed.off
            self.update()
        def mouseReleaseEvent(self, e): self.ed.drag = False; self.ed.act_area = None; self.ed.act_pivot = None

class LiveApp(QWidget):
    def __init__(self, paths, tuning, lang):
        super().__init__()
        self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool); self.setAttribute(Qt.WA_TranslucentBackground)
        self.paths, self.tuning, self.lang, self.hold, self.scale, self.drag_pos = paths, tuning, lang, False, 1.0, None
        
        # --- QUAY LẠI CÁCH LOAD ẢNH CŨ CHO CHUẨN KHỚP ---
        self.pix_cache = {k: QPixmap(v) for k, v in paths.items()}
        
        tl = tuning['leftarm']; p1, p_last = tuning['hand_pivots'][0], tuning['hand_pivots'][-1]
        r_l = QRect(int(tl['pos'].x()-tl['w']//2), int(tl['pos'].y()-tl['h']//2), int(tl['w']), int(tl['h']))
        self.origin = QPointF(r_l.left() + p1[0]*r_l.width(), r_l.top() + p1[1]*r_l.height())
        self.v_orig = QPointF((p_last[0]-p1[0])*tl['w'], (p_last[1]-p1[1])*tl['h']); self.base_len = math.sqrt(self.v_orig.x()**2 + self.v_orig.y()**2)
        
        area = self.tuning['mouse_area']
        self.min_x, self.max_x = min(p.x() for p in area), max(p.x() for p in area)
        self.min_y, self.max_y = min(p.y() for p in area), max(p.y() for p in area)
        self.mx, self.my = (self.min_x + self.max_x)/2, (self.min_y + self.max_y)/2
        self.target_mx, self.target_my = self.mx, self.my
        
        self.sens = 0.65 
        self.last_move_time = time.time()
        self.tracker = MouseTracker(); self.tracker.move_signal.connect(self.update_target); self.tracker.start()
        
        self.setFixedSize(2560, 1440)
        self.timer = QTimer(); self.timer.timeout.connect(self.smooth_sync); self.timer.start(25) # Vẫn để 25ms để nhẹ máy
        import keyboard; keyboard.hook(self.k_evt)

    def update_target(self, dx, dy):
        self.target_mx = max(self.min_x, min(self.max_x, self.target_mx + dx * self.sens))
        self.target_my = max(self.min_y, min(self.max_y, self.target_my + dy * self.sens))
        self.last_move_time = time.time()

    def smooth_sync(self):
        old_mx, old_my = self.mx, self.my
        if time.time() - self.last_move_time > 0.1:
            cx, cy = (self.min_x + self.max_x)/2, (self.min_y + self.max_y)/2
            self.target_mx += (cx - self.target_mx) * 0.08
            self.target_my += (cy - self.target_my) * 0.08
        self.mx += (self.target_mx - self.mx) * 0.35; self.my += (self.target_my - self.my) * 0.35
        # Chỉ vẽ lại khi có di chuyển (Tối ưu FPS game tại đây)
        if abs(self.mx - old_mx) > 0.1 or abs(self.my - old_my) > 0.1: self.update()

    def paintEvent(self, e):
        p = QPainter(self); p.setRenderHint(QPainter.Antialiasing); p.scale(self.scale, self.scale); t = self.tuning
        p.drawPixmap(int(t['background']['pos'].x()-t['background']['w']//2), int(t['background']['pos'].y()-t['background']['h']//2), int(t['background']['w']), int(t['background']['h']), self.pix_cache['background'])
        tm = t['mouse']; p.save(); p.translate(self.mx, self.my); p.rotate(tm['rot']); p.drawPixmap(int(-tm['w']//2), int(-tm['h']//2), int(tm['w']), int(tm['h']), self.pix_cache['mouse']); p.restore()
        
        # LOGIC TAY TRÁI (QUAY LẠI CÔNG THỨC CHUẨN BẢN ĐẦU)
        tl = t['leftarm']; pix_l = self.pix_cache['leftarm']; p1 = t['hand_pivots'][0]
        v_c = QPointF(self.mx - self.origin.x(), self.my - self.origin.y()); d = math.sqrt(v_c.x()**2 + v_c.y()**2)
        ang = math.atan2(v_c.y(), v_c.x())*180/math.pi; o_ang = math.atan2(self.v_orig.y(), self.v_orig.x())*180/math.pi
        p.save(); p.translate(self.origin); p.rotate(ang-o_ang); s = d/self.base_len if self.base_len > 0 else 1
        p.drawPixmap(int(-p1[0]*tl['w']*s), int(-p1[1]*tl['h']), int(tl['w']*s), int(tl['h']), pix_l); p.restore()
        
        tr = t['rightarm_up']; img = self.pix_cache['rightarm_down' if self.hold else 'rightarm_up']
        p.save(); p.translate(tr['pos']); p.rotate(tr['rot']); p.drawPixmap(int(-tr['w']//2), int(-tr['h']//2), int(tr['w']), int(tr['h']), img); p.restore()

    def mousePressEvent(self, e):
        if e.button() == Qt.LeftButton: self.drag_pos = e.globalPos() - self.frameGeometry().topLeft()
    def mouseMoveEvent(self, e):
        if self.drag_pos: self.move(e.globalPos() - self.drag_pos)
    def mouseReleaseEvent(self, e): self.drag_pos = None
    def wheelEvent(self, e):
        self.scale = max(0.1, min(4.0, self.scale + (0.05 if e.angleDelta().y() > 0 else -0.05))); self.update()
    def contextMenuEvent(self, e):
        menu = QMenu(self); exit_act = menu.addAction("Thoát" if self.lang=="VN" else "Exit")
        if menu.exec_(self.mapToGlobal(e.pos())) == exit_act: QApplication.quit()
    def k_evt(self, e):
        old = self.hold; self.hold = (e.event_type == "down")
        if old != self.hold: self.update()

if __name__ == '__main__':
    app = QApplication(sys.argv); ls = LanguageSelect()
    if ls.exec_():
        data = {}
        if os.path.exists(CONFIG_FILE):
            try:
                with open(CONFIG_FILE, 'r', encoding='utf-8') as f: data = json.load(f)
            except: pass
        items = list(data.keys()) + ["+ NEW PROFILE"]
        name, ok = QInputDialog.getItem(None, "vâm keyboard", "Chọn Profile:", items, 0, False)
        if ok:
            if name == "+ NEW PROFILE":
                iw = ImportWindow(ls.choice)
                if iw.exec_(): ed = VamEditor(iw.paths, ls.choice); ed.show()
            else:
                p = data[name]; t = p['tuning']
                for k in ['background', 'rightarm_up', 'leftarm', 'mouse']: t[k]['pos'] = QPoint(t[k]['x'], t[k]['y'])
                t['mouse_area'] = [QPoint(x[0], x[1]) for x in t['mouse_area']]
                ed = VamEditor(p['paths'], p['lang'], t, name); ed.show()
    sys.exit(app.exec_())
