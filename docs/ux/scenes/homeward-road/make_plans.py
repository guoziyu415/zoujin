# Draws docs/ux/scenes/homeward-road/plans.svg from the coordinates in docs/ux/scenes/homeward-road.md.
# Usage: python3 -I make_plans.py plans.svg   (change a coordinate here and in homeward-road.md together)
import math, sys
out = sys.argv[1]
W = 1240
parts = []
FONT = "font-family=\"'Noto Sans CJK SC','PingFang SC','Hiragino Sans','Microsoft YaHei',sans-serif\""
C = dict(bg='#fbfaf6', ink='#2b2a26', mute='#6d6a60', road='#e6d9b9', roadedge='#c9b98f',
         grass='#e9e3c4', rock='#bdb7aa', rockedge='#8f897b', tree='#7d8f5c', treeedge='#55663b',
         calm='#7d9bb3', flood='#a98a5c', bar='#d3cbb8', wood='#8a7458', melos='#a8742c',
         player='#2f4f7a', cam='#8c8c8c', sun='#c99700', shadow='#9a9686', bandit='#5b5248')

def text(x, y, s, size=12, color=None, anchor='start', weight='normal'):
    parts.append(f'<text x="{x:.1f}" y="{y:.1f}" font-size="{size}" fill="{color or C["ink"]}" text-anchor="{anchor}" font-weight="{weight}" {FONT}>{s}</text>')

class Plan:
    def __init__(self, ox, oy, s, x0, x1, y0, y1, az, title):
        self.ox, self.oy, self.s = ox, oy, s
        self.x0, self.x1, self.y0, self.y1, self.az = x0, x1, y0, y1, az
        w, h = (x1 - x0) * s, (y1 - y0) * s
        parts.append(f'<rect x="{ox}" y="{oy}" width="{w}" height="{h}" fill="{C["grass"]}" stroke="{C["mute"]}" stroke-width="1"/>')
        text(ox, oy - 10, title, 15, weight='bold')
    def P(self, x, y):
        return self.ox + (x - self.x0) * self.s, self.oy + (self.y1 - y) * self.s
    def poly(self, pts, fill, stroke='none', sw=1, dash=None, op=1):
        d = ' '.join(f'{a:.1f},{b:.1f}' for a, b in (self.P(x, y) for x, y in pts))
        da = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<polygon points="{d}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}"{da} fill-opacity="{op}"/>')
    def line(self, pts, stroke, sw=1.5, dash=None, op=1):
        d = ' '.join(f'{a:.1f},{b:.1f}' for a, b in (self.P(x, y) for x, y in pts))
        da = f' stroke-dasharray="{dash}"' if dash else ''
        parts.append(f'<polyline points="{d}" fill="none" stroke="{stroke}" stroke-width="{sw}"{da} stroke-opacity="{op}" stroke-linecap="round" stroke-linejoin="round"/>')
    def rect(self, xa, ya, xb, yb, fill, stroke='none', sw=1, dash=None, op=1):
        self.poly([(xa, ya), (xb, ya), (xb, yb), (xa, yb)], fill, stroke, sw, dash, op)
    def circle(self, x, y, r_m, fill, stroke='none', sw=1, op=1, r_px=None):
        a, b = self.P(x, y)
        r = r_px if r_px else r_m * self.s
        parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="{r:.1f}" fill="{fill}" stroke="{stroke}" stroke-width="{sw}" fill-opacity="{op}"/>')
    def label(self, x, y, s, dx=6, dy=4, size=11, color=None, anchor='start'):
        a, b = self.P(x, y)
        text(a + dx, b + dy, s, size, color, anchor)
    def spot(self, x, y, name, who, facing=None, dx=7, dy=4, anchor='start'):
        col = C['melos'] if who == 'm' else C['player'] if who == 'p' else C['mute']
        a, b = self.P(x, y)
        if facing is not None:
            fx, fy = facing
            a2, b2 = self.P(x + fx * 2.2, y + fy * 2.2)
            parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b2:.1f}" stroke="{col}" stroke-width="2"/>')
        if who == 'p':
            parts.append(f'<rect x="{a-4.5:.1f}" y="{b-4.5:.1f}" width="9" height="9" fill="{col}"/>')
        else:
            parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="4.5" fill="{col}"/>')
        text(a + dx, b + dy, name, 10.5, col, anchor)
    def cam(self, x, y, fx, fy):
        a, b = self.P(x, y)
        ang = math.atan2(-fy, fx)
        pts = []
        for da, r in ((0, 8), (2.5, 6), (-2.5, 6)):
            pts.append((a + r * math.cos(ang + da), b + r * math.sin(ang + da)))
        parts.append('<polygon points="' + ' '.join(f'{p:.1f},{q:.1f}' for p, q in pts) + f'" fill="{C["cam"]}"/>')
    def vec(self, theta):  # compass bearing -> plan unit vector
        d = math.radians(theta - self.az)
        return math.cos(d), -math.sin(d)
    def compass(self, x, y):
        nx, ny = self.vec(0)
        a, b = self.P(x, y); a2, b2 = self.P(x + nx * 4, y + ny * 4)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b2:.1f}" stroke="{C["ink"]}" stroke-width="1.5" marker-end="url(#ah)"/>')
        a3, b3 = self.P(x + nx * 5.6, y + ny * 5.6)
        text(a3, b3 + 4, 'N', 11, anchor='middle', weight='bold')
        text(a, b + 22, f'+x = {self.az}°', 10, C['mute'], 'middle')
    def sun(self, x, y, theta, label):
        vx, vy = self.vec(theta)
        a, b = self.P(x + vx * 5, y + vy * 5); a2, b2 = self.P(x, y)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b2:.1f}" stroke="{C["sun"]}" stroke-width="2" marker-end="url(#sh)"/>')
        parts.append(f'<circle cx="{a:.1f}" cy="{b:.1f}" r="5" fill="{C["sun"]}"/>')
        text(a, b - 8, label, 10, C['sun'], 'middle')
    def tree(self, x, y, r, label=None):
        self.circle(x, y, r, C['tree'], C['treeedge'], 1, 0.55)
        self.circle(x, y, 0, C['treeedge'], r_px=2)
        if label: self.label(x, y, label, dx=r * self.s * 0.7 + 2, size=10, color=C['treeedge'])
    def scalebar(self, x, y, m=10):
        a, b = self.P(x, y); a2, _ = self.P(x + m, y)
        parts.append(f'<line x1="{a:.1f}" y1="{b:.1f}" x2="{a2:.1f}" y2="{b:.1f}" stroke="{C["ink"]}" stroke-width="2"/>')
        text((a + a2) / 2, b - 5, f'{m} m', 10, anchor='middle')

def road(p, xa, xb, y, w):
    p.rect(xa, y - w / 2, xb, y + w / 2, C['road'], C['roadedge'], 1)

# ---------- River ----------
R = Plan(30, 64, 9, -30, 30, -20, 20, 90, '1 · 川と橋（两个包：第二幕 calm／第四幕 flood）')
R.rect(-5, -20, 11, 20, '#d9d2b9')                     # channel bed / low terraces
R.rect(-5, -20, 11, 20, C['flood'], op=0.55)            # act 4 flood bank to bank
R.poly([(-6, 9), (13, 9), (13, 16), (-6, 16)], C['flood'], op=0.55)
R.poly([(-1, -20), (7, -20), (7, 9), (10, 9), (10, 16), (7, 16), (7, 20), (-1, 20), (-1, 16), (-2, 16), (-2, 9), (-1, 9)], C['calm'], C['calm'], 1.5, '5 3', 0.75)
R.rect(3, 10, 7, 15, C['bar'], C['rockedge'], 1, '3 2')
for (x, y) in ((4, 12), (5.5, 13.5), (6.2, 11), (4.6, 14.4)):
    R.circle(x, y, 0.45, C['rock'], C['rockedge'])
R.line([(-5, -20), (-5, 9), (-6, 9), (-6, 16), (-5, 16), (-5, 20)], C['ink'], 1.5)
R.line([(11, -20), (11, 9), (13, 9), (13, 16), (11, 16), (11, 20)], C['ink'], 1.5)
road(R, -30, -5, 0, 3); road(R, 11, 30, 0, 3)
R.rect(-5, -1.1, 11, 1.1, C['wood'], C['ink'], 1, '4 2', 0.35)
for x in (-1, 3, 7):
    for y in (-1.1, 1.1):
        R.circle(x, y, 0, C['ink'], r_px=2.6)
R.rect(-5, -10.6, -1, -9.4, C['wood'], C['ink'], 0.8, '3 2', 0.35)
R.circle(-5.5, -9, 0, C['ink'], r_px=2.2); R.circle(-5.5, -11.5, 0, C['ink'], r_px=2.2)
R.rect(-12.5, -13.5, -9.5, -10.5, '#cdbf98', C['rockedge'])
R.label(-11, -14.2, '船夫小屋', dx=0, dy=10, anchor='middle', size=10)
R.label(-3, -10, '栈桥·系船桩', dx=0, dy=-8, anchor='middle', size=10)
for (x, y) in ((-8, 7), (-9, 13), (-7, -17), (13, 5), (14, 11), (13, -17)):
    R.tree(x, y, 2.2)
R.label(-7, -17, '白杨', dx=-22, dy=4, size=10, color=C['treeedge'], anchor='end')
R.tree(11.5, -12, 2.8)
R.label(11.5, -12, '柳（抓住的树）', dx=12, dy=22, size=10, color=C['treeedge'])
R.label(4.5, 16.8, '浅滩', dx=0, dy=-2, anchor='middle', size=10)
R.label(3, -17.5, '河', dx=0, dy=0, anchor='middle', size=12, color='#3f5a70')
R.spot(-16, -1, 'road-west 第四幕落地', 'p', (1, 0), dx=-4, dy=30)
R.cam(-25, -1, 1, 0)
R.spot(-6, 0.8, 'melos-bridgehead', 'm', (1, 0), dx=-8, dy=-8, anchor='end')
R.spot(-5.6, -2.5, 'melos-pray', 'm', (1, 0), dx=-8, dy=4, anchor='end')
R.spot(11, -12, '', 'm')
R.label(11, -12, 'swim-out', dx=6, dy=-10, size=10, color=C['melos'])
R.line([(-5, -1), (0, -4), (5, -8), (11, -12)], C['melos'], 1.2, '4 3')
R.spot(-5.5, 12, '', 'm'); R.spot(12.5, 13, '', 'm')
R.line([(-5.5, 12), (3, 12.6), (12.5, 13)], C['melos'], 1.2, '4 3')
R.label(-5.5, 12, 'shallows-in', dx=6, dy=-6, size=10, color=C['melos'])
R.spot(15, -4, 'far-bank', 'm', (1, 0), dy=14)
R.spot(17, 1, 'road-east 第二幕落地', 'p', (-1, 0), dx=-10, dy=-9)
R.cam(26, 1, -1, 0)
R.spot(6.6, -2.5, 'melos-wash（第二幕）', 'm', (-1, 0), dx=8, dy=-4)
R.label(-24, 0, 'way.west', dx=0, dy=24, size=10, color=C['mute'], anchor='middle')
R.label(24, 0, 'way.east', dx=0, dy=24, size=10, color=C['mute'], anchor='middle')
R.compass(-26, 14)
R.sun(-25, -15, 180, '12:00 第四幕')
R.sun(25, 15, 67.5, '05:10 第二幕')
R.scalebar(18, -18.5)
lx = 30 + 60 * 9 + 24
ly = 70
def legend_item(y, kind, label):
    if kind == 'flood':
        parts.append(f'<rect x="{lx}" y="{y-10}" width="22" height="12" fill="{C["flood"]}" fill-opacity="0.55"/>')
    elif kind == 'calm':
        parts.append(f'<rect x="{lx}" y="{y-10}" width="22" height="12" fill="{C["calm"]}" fill-opacity="0.75" stroke="{C["calm"]}" stroke-dasharray="5 3"/>')
    elif kind == 'road':
        parts.append(f'<rect x="{lx}" y="{y-10}" width="22" height="12" fill="{C["road"]}" stroke="{C["roadedge"]}"/>')
    elif kind == 'p':
        parts.append(f'<rect x="{lx+6}" y="{y-9}" width="9" height="9" fill="{C["player"]}"/>')
    elif kind == 'm':
        parts.append(f'<circle cx="{lx+11}" cy="{y-4.5}" r="4.5" fill="{C["melos"]}"/>')
    elif kind == 'cam':
        parts.append(f'<polygon points="{lx+16},{y-4} {lx+6},{y-9} {lx+6},{y+1}" fill="{C["cam"]}"/>')
    elif kind == 'sun':
        parts.append(f'<circle cx="{lx+11}" cy="{y-4.5}" r="5" fill="{C["sun"]}"/>')
    elif kind == 'tree':
        parts.append(f'<circle cx="{lx+11}" cy="{y-4.5}" r="7" fill="{C["tree"]}" fill-opacity="0.55" stroke="{C["treeedge"]}"/>')
    elif kind == 'bandit':
        parts.append(f'<text x="{lx+11}" y="{y}" font-size="14" text-anchor="middle" fill="{C["bandit"]}" {FONT}>×</text>')
    text(lx + 30, y, label, 12)
items = [('road', '路（土路）'), ('calm', '第二幕的水（平静，约 8 m 宽）'), ('flood', '第四幕的濁流（岸到岸 16 m）'),
         ('p', '玩家落地点，短线是朝向'), ('m', '梅洛斯的位置点（演出用的多为 auto: false）'),
         ('cam', '落地时默认镜头的位置（背后 9 m）'), ('sun', '太阳从这个方向来'), ('tree', '树冠'), ('bandit', '山贼藏的地方')]
for i, (k, l) in enumerate(items):
    legend_item(ly + 24 * i, k, l)
notes = ['坐标单位米。+x 是往锡拉库萨去的方向（第四幕跑的方向），',
         '+y 是它的左手边；N 箭头是正北，每张图不同。',
         '第四幕只能走西岸；东岸在 beat.18 的演出以后到。',
         '第二幕两岸、桥面、栈桥都能走，往西过桥进幕末。',
         '第四幕桥面没了：三对木桩，x = 7 那对挂着树枝。',
         '游的路线：虚线。选了浅滩改走上游那条。',
         '细节和理由见 homeward-road.md 第 1 节。']
for i, n in enumerate(notes):
    text(lx, ly + 24 * len(items) + 14 + 18 * i, n, 11.5, C['mute'])

# ---------- Pass ----------
top2 = 64 + 40 * 9 + 70
S2 = 8
Pp = Plan(30, top2, S2, -32, 20, -12, 20, 80, '2 · 峠（第四幕 13:40〜14:00）')
Pp.rect(-32, -12, 20, -6, '#d8d2c0', op=0.9)
Pp.label(-20, -9, '陡的碎石坡（软边界）', dx=0, dy=4, size=10, color=C['mute'], anchor='middle')
Pp.rect(-32, 9, -6, 20, '#d4cebd', op=0.9)
Pp.label(-20, 15, '岩壁和灌木', dx=0, dy=4, size=10, color=C['mute'], anchor='middle')
road(Pp, -32, -16, -1, 2.5)
Pp.rect(-16, -5, -4, 5, '#e2dbc2', C['roadedge'], 1)
Pp.label(-10, -5, '平台（z ≈ 1.2）', dx=0, dy=14, size=10, anchor='middle', color=C['mute'])
Pp.line([(-4, 0), (3, -4), (7, 1), (11, 0), (16, 0)], C['roadedge'], 9)
Pp.line([(-4, 0), (3, -4), (7, 1), (11, 0), (16, 0)], C['road'], 7)
Pp.label(3, -4, '之字路（z 1.2 → 7）', dx=0, dy=16, size=10, anchor='middle', color=C['mute'])
Pp.line([(-5, 2), (-1, 8), (4, 13), (8, 16)], C['roadedge'], 3.5, '6 3')
Pp.label(4, 13, '羊肠小道（脇道）', dx=-8, dy=-6, size=10, anchor='end', color=C['mute'])
Pp.circle(-5.5, 3, 0, C['rockedge'], r_px=4)
Pp.label(-5.5, 3, '石堆', dx=6, dy=12, size=10, color=C['mute'])
Pp.rect(8, 2, 14, 6, C['rock'], C['rockedge'], 1.2)
Pp.rect(8.5, -5.8, 13.5, -2.2, C['rock'], C['rockedge'], 1.2)
Pp.label(11, 6, '北岩 +5 m', dx=0, dy=-4, size=10, anchor='middle')
Pp.label(11, -5.8, '南岩 +4 m', dx=0, dy=13, size=10, anchor='middle')
Pp.line([(13, -2), (13, 2)], C['ink'], 1, '3 2')
Pp.label(13, 2, '鞍部', dx=4, dy=-4, size=10)
for (x, y) in ((15.5, 5.5), (17, 7.5), (18, 5), (15.5, -5.5), (16.8, -7)):
    a, b = Pp.P(x, y)
    text(a, b + 5, '×', 15, C['bandit'], 'middle', 'bold')
vx, vy = Pp.vec(64)
for (x, y) in ((14, 6), (14, 2), (13.5, -2.2), (13.5, -5.8)):
    Pp.line([(x, y), (x + vx * 4, y + vy * 4)], C['shadow'], 1, '2 2')
Pp.circle(8, 3.2, 0, C['ink'], r_px=2)
Pp.label(8, 3.2, '岩缝', dx=-5, dy=-4, size=10, anchor='end')
Pp.tree(-11, 4.5, 2.5)
Pp.label(-11, 4.5, '小圣栎', dx=-24, dy=4, size=10, color=C['treeedge'], anchor='end')
Pp.spot(-20, -1, 'shelf-west 落地', 'p', (1, 0), dx=-4, dy=16)
Pp.cam(-29, -1, 1, 0)
Pp.spot(-9.2, 5.2, 'melos-breath', 'm', (1, 0), dx=6, dy=-6)
Pp.spot(12, 0, 'saddle', 'm', (1, 0), dx=-4, dy=14, anchor='end')
Pp.spot(-1, 8, 'side-path', 'n', dx=6, dy=4)
Pp.compass(-28, 14)
Pp.sun(-25, -5, 244, '14:00')
Pp.scalebar(-2, -10.5)

S3 = 8
ox3 = 30 + 52 * S2 + 40
Sp = Plan(ox3, top2, S3, -28, 24, -10, 18, 100, '3 · 泉（第四幕 14:55〜16:30）')
Sp.rect(-28, -10, 24, -6.5, '#e7d68f', op=0.8)
Sp.label(10, -8.5, '麦田', dx=0, dy=4, size=10, anchor='middle', color=C['mute'])
Sp.line([(-18, -6.5), (16, -6.5)], C['rockedge'], 3)
Sp.label(-18, -6.5, '干砌石墙', dx=-4, dy=4, size=10, anchor='end', color=C['mute'])
road(Sp, -28, 24, -4, 3)
Sp.line([(0.3, 4.8), (2.5, 2.5), (5, 0), (6.5, -2.5), (7, -6)], '#5f87a6', 2)
Sp.rect(-3.5, 6.2, 1.5, 8.4, C['rock'], C['rockedge'], 1.2)
Sp.label(-1, 8.4, '岩石（高 1.3 m）', dx=0, dy=-5, size=10, anchor='middle')
Sp.circle(0, 5.3, 0.6, '#9cc0d6', '#5f87a6')
Sp.label(0, 5.3, '泉', dx=-7, dy=4, size=11, anchor='end', color='#3f5a70')
for (x, y, r, h) in ((-13, 6, 6, 16), (-16, 10.5, 6.5, 18), (-11, 12, 5, 14)):
    Sp.tree(x, y, r)
Sp.label(-14, 9, '悬铃木 ×3', dx=0, dy=4, size=10.5, anchor='middle', color=C['treeedge'])
for theta, k, col in ((78, 0.93, '#8f8a73'), (93, 1.8, '#b5ae94')):
    vx, vy = Sp.vec(theta)
    for (x, y, r, h) in ((-13, 6, 6, 16), (-16, 10.5, 6.5, 18), (-11, 12, 5, 14)):
        L = k * h
        Sp.line([(x, y), (x + vx * L, y + vy * L)], col, 1, '2 3')
Sp.label(20, 13, '树影 15:00 / 16:30', dx=0, dy=-2, size=9.5, anchor='end', color=C['mute'])
Sp.spot(-12, -4, 'road-spring 落地', 'p', (1, 0), dx=-4, dy=16)
Sp.cam(-21, -4, 1, 0)
Sp.spot(-5, -3.5, 'melos-stagger', 'm', (1, 0), dx=-3, dy=-8)
Sp.spot(2.5, 3.8, 'melos-down（头朝东南）', 'm', None, dx=7, dy=4)
Sp.spot(-0.2, 4.7, '', 'm', (0, 1))
Sp.label(-0.2, 4.7, 'melos-drink', dx=-8, dy=14, size=10, color=C['melos'], anchor='end')
Sp.spot(3.3, 2.6, '', 'p', Sp.vec(0))
Sp.cam(3.45, 1.7, *Sp.vec(0))
Sp.label(3.3, 2.6, 'player-crouch（低机位）', dx=8, dy=16, size=10, color=C['player'])
Sp.compass(18, 13)
Sp.sun(-22, 16.5, 258, '15:00')
Sp.sun(-20, -1.2, 273, '16:30')
Sp.scalebar(-4, -8.8)

# ---------- Timeline ----------
top3 = top2 + 32 * S2 + 80
text(30, top3 - 10, '4 · 第四幕跟着梅洛斯：停留点和跑的路段（排定时刻；推迟、提前时整段跟着移）', 15, weight='bold')
t0, t1 = 11 * 60, 19 * 60 + 10
x0, x1 = 40, W - 40
def tx(m): return x0 + (m - t0) / (t1 - t0) * (x1 - x0)
segs = [(11*60+20, 12*60+10, '川', 'stop'), (12*60+10, 13*60+40, 'R1 湿的坡', 'run'),
        (13*60+40, 14*60+5, '峠', 'stop'), (14*60+5, 14*60+55, 'R2 石的下坡', 'run'),
        (14*60+55, 16*60+30, '泉', 'stop'), (16*60+30, 17*60+20, 'R3 草原', 'run'),
        (17*60+20, 18*60+55, '野の道（整段跑，能说话）', 'field'), (18*60+55, 19*60+10, '广场', 'plaza')]
fills = dict(stop='#d9cfae', run='#eadfc4', field='#f0d38a', plaza='#cfc8b8')
for a, b, lab, k in segs:
    xa, xb = tx(a), tx(b)
    dash = ' stroke-dasharray="4 3"' if k == 'run' else ''
    parts.append(f'<rect x="{xa:.1f}" y="{top3}" width="{xb-xa:.1f}" height="30" fill="{fills[k]}" stroke="{C["mute"]}"{dash}/>')
    text((xa + xb) / 2, top3 + 20, lab, 12 if k != 'plaza' else 10, anchor='middle', weight='bold' if k != 'run' else 'normal')
for m in range(11*60, 19*60+1, 60):
    parts.append(f'<line x1="{tx(m):.1f}" y1="{top3+30}" x2="{tx(m):.1f}" y2="{top3+36}" stroke="{C["ink"]}"/>')
    text(tx(m), top3 + 48, f'{m//60}:00', 10, C['mute'], 'middle')
beats = [(12*60, 'beat.18 游'), (14*60, 'beat.19 山贼'), (15*60, 'beat.20 倒下'), (16*60+30, 'beat.21 泉水'),
         (17*60+30, 'beat.22 酒宴'), (18*60+30, 'beat.23 フィロストラトス'), (19*60, 'beat.24 日没')]
for i, (m, lab) in enumerate(beats):
    parts.append(f'<line x1="{tx(m):.1f}" y1="{top3-4}" x2="{tx(m):.1f}" y2="{top3+30}" stroke="{C["melos"]}" stroke-width="1.5"/>')
    text(tx(m), top3 + 64 + (i % 2) * 14, lab, 10.5, C['melos'], 'middle')
text(40, top3 + 104, '野の道里按时钟出现：17:30 酒宴、狗、小川 · 约 17:45 旅人「いまごろは、あの男も、磔にかかっているよ」 · 约 17:50 坡顶看见城楼', 11.5, C['mute'])
text(40, top3 + 122, '18:30 フィロストラトス迎面跑来、反打镜头里又红又大的落日 · 约 18:45 墓和柏树 · 约 18:55 城门，影子先伸进门洞 → 换到广场', 11.5, C['mute'])
text(40, top3 + 140, '梅洛斯的衣服：第 1 级（到川）→ 第 2 级（游过以后，湿）→ 第 3 级（打完山贼，左肩带断、擦伤）→ 第 4 级（17:30 以后 = 结局版）', 11, C['mute'])
top4 = top3 + 180
text(30, top4 - 10, '第二幕的夜路（能说话，每句 10 分；往西走）', 13, weight='bold')
n0, n1 = 2*60+45, 5*60+10
def nx(m): return x0 + (m - n0) / (n1 - n0 + 40) * (x1 - x0) * 0.55
parts.append(f'<rect x="{nx(n0):.1f}" y="{top4}" width="{nx(n1)-nx(n0):.1f}" height="26" fill="#c9d2df" stroke="{C["mute"]}" stroke-dasharray="4 3"/>')
parts.append(f'<rect x="{nx(n1):.1f}" y="{top4}" width="{nx(n1+40)-nx(n1):.1f}" height="26" fill="#d9cfae" stroke="{C["mute"]}"/>')
text(nx(n1) + (nx(n1+40)-nx(n1))/2, top4 + 18, '川', 12, anchor='middle', weight='bold')
for m, lab in ((2*60+45, '02:45 泉水声，悬铃木剪影'), (3*60+30, '03:30 岩门衬着银河'), (4*60+30, '04:30 背后发白'), (4*60+55, '粉色带')):
    parts.append(f'<line x1="{nx(m):.1f}" y1="{top4}" x2="{nx(m):.1f}" y2="{top4+26}" stroke="{C["player"]}"/>')
    text(nx(m) + 3, top4 + 42, lab, 10.5, C['player'])
text(nx(n1) + (nx(n1+40)-nx(n1)) + 14, top4 + 18, '05:10 到川（桥还在），过桥 → 第二幕幕末', 11, C['mute'])
H = top4 + 70
svg = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">'
       '<defs><marker id="ah" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#2b2a26"/></marker>'
       '<marker id="sh" markerWidth="8" markerHeight="8" refX="6" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#c99700"/></marker></defs>'
       f'<rect width="{W}" height="{H}" fill="{C["bg"]}"/>'
       f'<text x="30" y="28" font-size="19" font-weight="bold" fill="{C["ink"]}" {FONT}>归途的停留点平面（UX v0.1，2026-10-10）</text>'
       + ''.join(parts) + '</svg>')
open(out, 'w', encoding='utf-8').write(svg)
print('ok', W, H)
