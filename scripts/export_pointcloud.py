"""把 MoGe 3D 点云导出为可交互查看的文件。

输出两种格式:
  <名称>.ply   标准点云格式,可用 Blender / MeshLab / CloudCompare 打开
  <名称>.html  自包含交互式网页(内嵌 three.js,离线可用,双击即开)

用法:
  uv run python scripts/export_pointcloud.py --image path/to/img.jpg [--image b.jpg ...]
  可选: --yolo models/yolo.pt --out docs/pointclouds --max-html-points 250000
"""

import argparse
import base64
import struct
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import cv2
import numpy as np

from paramnet_yolo import MoGeGravity, Sam3Segmenter

THREE_DIR = Path(__file__).resolve().parents[1] / "docs" / "_three"

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="utf-8">
<title>MoGe 3D 点云查看器 - __NAME__</title>
<style>
  html,body{margin:0;height:100%;overflow:hidden;background:#111;font-family:"Microsoft YaHei",sans-serif}
  #legend{position:fixed;top:10px;left:10px;background:rgba(0,0,0,.55);color:#eee;
          padding:10px 14px;border-radius:8px;font-size:13px;line-height:1.8;z-index:10}
  #legend b{color:#fff}
  .sw{display:inline-block;width:10px;height:10px;border-radius:2px;margin-right:6px}
</style>
</head>
<body>
<div id="legend">
  <b>__NAME__</b> — 拖动旋转 / 滚轮缩放 / 右键平移<br>
  <span class="sw" style="background:#ff00ff"></span>瓶身点(SAM3 mask 内)<br>
  <span class="sw" style="background:#3388cc"></span>场景点(原始颜色)<br>
  <span class="sw" style="background:#00ff44"></span>重力方向(地面法向)<br>
  <span class="sw" style="background:#ffa500"></span>瓶身三维轴向(PCA)<br>
  <span class="sw" style="background:#00ffff"></span>拟合地面平面(半透明)
</div>
<script>__THREE_JS__</script>
<script>__ORBIT_JS__</script>
<script>
const B64 = "__POINT_B64__";
const N = __N_POINTS__, PT_SIZE = __PT_SIZE__;
const CENTER = __CENTER__, CAM_DIST = __CAM_DIST__;
const G0 = __G0__, G1 = __G1__, G2 = __G2__;
const A0 = __A0__, A1 = __A1__, A2 = __A2__;
const QUAD = __QUAD__;  // 4x3 地面平面角点

const raw = atob(B64);
const u8 = new Uint8Array(raw.length);
for (let i = 0; i < raw.length; i++) u8[i] = raw.charCodeAt(i);
const pos = new Float32Array(u8.buffer, 0, N * 3);
const col = new Uint8Array(u8.buffer, N * 12, N * 3);

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(60, innerWidth / innerHeight, 0.01, 200);
camera.position.set(CENTER[0], CENTER[1], CENTER[2] + CAM_DIST);

const renderer = new THREE.WebGLRenderer({antialias: true});
renderer.setSize(innerWidth, innerHeight);
document.body.appendChild(renderer.domElement);

const geo = new THREE.BufferGeometry();
geo.setAttribute("position", new THREE.BufferAttribute(pos, 3));
geo.setAttribute("color", new THREE.BufferAttribute(col, 3, true));
scene.add(new THREE.Points(geo, new THREE.PointsMaterial({size: PT_SIZE, vertexColors: true})));

const mkLine = (p, q, hex) => {
  const g = new THREE.BufferGeometry().setFromPoints(
    [new THREE.Vector3(...p), new THREE.Vector3(...q)]);
  scene.add(new THREE.Line(g, new THREE.LineBasicMaterial({color: hex})));
};
const c = CENTER;
mkLine(c, [c[0] + G0 * CAM_DIST, c[1] + G1 * CAM_DIST, c[2] + G2 * CAM_DIST], 0x00ff44);
mkLine([c[0] - A0 * CAM_DIST, c[1] - A1 * CAM_DIST, c[2] - A2 * CAM_DIST],
       [c[0] + A0 * CAM_DIST, c[1] + A1 * CAM_DIST, c[2] + A2 * CAM_DIST], 0xffa500);
if (QUAD.length === 12) {
  const gq = new THREE.BufferGeometry().setFromPoints(QUAD.map(q => new THREE.Vector3(...q)));
  scene.add(new THREE.Mesh(gq, new THREE.MeshBasicMaterial({
    color: 0x00ffff, transparent: true, opacity: 0.12, side: THREE.DoubleSide, depthWrite: false})));
}

const controls = new THREE.OrbitControls(camera, renderer.domElement);
controls.target.set(...CENTER);
controls.update();
addEventListener("resize", () => {
  camera.aspect = innerWidth / innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(innerWidth, innerHeight);
});
(function loop(){ requestAnimationFrame(loop); controls.update(); renderer.render(scene, camera); })();
</script>
</body>
</html>
"""


def flip(points):
    """相机坐标(x右,y下,z前) → 视图坐标(y 上, z 朝观察者)。"""
    p = np.asarray(points, dtype=np.float64).copy()
    single = p.ndim == 1
    if single:
        p = p[None, :]
    p[:, 1] *= -1.0
    p[:, 2] *= -1.0
    return p[0] if single else p


def write_ply(path, xyz, rgb):
    """二进制小端 PLY(浮点 xyz + uint8 rgb),Blender/MeshLab/CloudCompare 通吃。"""
    n = len(xyz)
    arr = np.empty(
        n, dtype=[("x", "<f4"), ("y", "<f4"), ("z", "<f4"),
                  ("r", "u1"), ("g", "u1"), ("b", "u1")]
    )
    arr["x"], arr["y"], arr["z"] = xyz[:, 0], xyz[:, 1], xyz[:, 2]
    arr["r"], arr["g"], arr["b"] = rgb[:, 0], rgb[:, 1], rgb[:, 2]
    header = (
        "ply\nformat binary_little_endian 1.0\n"
        f"element vertex {n}\nproperty float x\nproperty float y\nproperty float z\n"
        "property uchar red\nproperty uchar green\nproperty uchar blue\nend_header\n"
    )
    with open(path, "wb") as fh:
        fh.write(header.encode("ascii"))
        fh.write(arr.tobytes())


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--image", required=True, nargs="+")
    ap.add_argument("--yolo", default="models/yolo.pt")
    ap.add_argument("--conf", type=float, default=0.35)
    ap.add_argument("--out", default="docs/pointclouds")
    ap.add_argument("--max-html-points", type=int, default=250000)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    three_js = (THREE_DIR / "package" / "build" / "three.min.js").read_text(encoding="utf-8")
    orbit_js = (THREE_DIR / "package" / "examples" / "js" / "controls" / "OrbitControls.js").read_text(encoding="utf-8")

    from ultralytics import YOLO

    model = YOLO(args.yolo)
    seg = Sam3Segmenter()
    est = None

    def imread_unicode(path):
        return cv2.imdecode(np.fromfile(path, dtype=np.uint8), cv2.IMREAD_COLOR)

    for img_path in args.image:
        frame = imread_unicode(img_path)
        if frame is None:
            print(f"[跳过] 读不到: {img_path}")
            continue
        name = Path(img_path).stem

        if est is None:
            est = MoGeGravity().calibrate([frame])
        else:
            est.refresh(frame)
        pts, valid = est.points, est.valid

        bottle_mask = np.zeros_like(valid)
        result = model.predict(frame, conf=args.conf, retina_masks=True, verbose=False)[0]
        seg.set_image(frame)
        boxes = result.obb.xyxyxyxy if result.obb is not None else result.boxes.xyxy
        for i in range(len(boxes)):
            q = boxes[i].tolist()
            if result.obb is not None:
                x1, y1, x2, y2 = (int(min(p[0] for p in q)), int(min(p[1] for p in q)),
                                  int(max(p[0] for p in q)), int(max(p[1] for p in q)))
            else:
                x1, y1, x2, y2 = map(int, q)
            m = seg.mask_from_box(x1, y1, x2, y2)
            if m is not None:
                bottle_mask |= m

        view = flip(pts[valid])
        rgb = frame[valid][:, ::-1][:, ::-1].copy()  # BGR→RGB
        is_bottle = bottle_mask[valid]
        rgb[is_bottle] = (0.45 * rgb[is_bottle] + 0.55 * np.array([255, 0, 255])).astype(np.uint8)

        # PLY: 全量
        ply_path = out_dir / f"{name}.ply"
        write_ply(ply_path, view, rgb)

        # HTML: 降采样
        n_all = len(view)
        idx = np.linspace(0, n_all - 1, min(args.max_html_points, n_all)).astype(int)
        v_sub, rgb_sub, bottle_sub = view[idx], rgb[idx], is_bottle[idx]

        med_z = float(np.median(v_sub[:, 2]))
        center = v_sub.mean(axis=0)
        cam_dist = float(np.abs(med_z) * 1.6 + 1e-3)

        g = est.gravity.copy()
        g_flip = np.array([g[0], -g[1], -g[2]])
        if bottle_sub.sum() > 50:
            bp = v_sub[bottle_sub]
            c3 = bp.mean(axis=0)
            _, _, vt = np.linalg.svd(bp - c3, full_matrices=False)
            a = vt[0] * abs(med_z) * 0.35  # 方向指示线:固定场景相对长度,抗 mask 离群点
            c3 = c3 * 1.0
        else:
            a = np.array([cam_dist * 0.3, 0.0, 0.0])
            c3 = center
        else:
            a = np.array([cam_dist * 0.3, 0.0, 0.0])
            c3 = center

        # 地面平面四角(以画面下部点质心为心,跨度约 2 倍中位深度)
        h, w = valid.shape
        ys, xs = np.nonzero(valid)
        low = ys > int(h * 0.55)
        cg = flip(pts[valid][low].mean(axis=0)) if low.sum() else center
        n_up = g_flip
        e1 = np.cross(n_up, [0.0, 0.0, 1.0])
        e1 = e1 / max(np.linalg.norm(e1), 1e-9)
        e2 = np.cross(n_up, e1)
        s = abs(med_z) * 1.2
        quad = [cg + e1 * s + e2 * s, cg - e1 * s + e2 * s,
                cg - e1 * s - e2 * s, cg + e1 * s - e2 * s]

        blob = v_sub.astype("<f4").tobytes() + rgb_sub.astype(np.uint8).tobytes()
        b64 = base64.b64encode(blob).decode("ascii")

        html = (HTML_TEMPLATE
                .replace("__NAME__", name)
                .replace("__THREE_JS__", three_js)
                .replace("__ORBIT_JS__", orbit_js)
                .replace("__POINT_B64__", b64)
                .replace("__N_POINTS__", str(len(v_sub)))
                .replace("__PT_SIZE__", f"{max(abs(med_z) * 0.004, 0.002):.4f}")
                .replace("__CENTER__", repr([round(x, 4) for x in center]))
                .replace("__CAM_DIST__", f"{cam_dist:.4f}")
                .replace("__G0__", f"{g_flip[0]:.4f}").replace("__G1__", f"{g_flip[1]:.4f}")
                .replace("__G2__", f"{g_flip[2]:.4f}")
                .replace("__A0__", f"{a[0]:.4f}").replace("__A1__", f"{a[1]:.4f}")
                .replace("__A2__", f"{a[2]:.4f}")
                .replace("__QUAD__", repr([[round(x, 3) for x in q] for q in quad])))
        html_path = out_dir / f"{name}.html"
        html_path.write_text(html, encoding="utf-8")

        print(f"{name}: PLY {n_all // 1000}k 点 -> {pl