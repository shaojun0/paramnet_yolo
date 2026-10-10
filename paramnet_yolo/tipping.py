import math

import numpy as np


def mask_long_axis(mask):
    """从分割 mask 估计瓶子长轴方向(2D 单位向量,图像坐标)。

    用 mask 像素坐标的主成分方向,避免 minAreaRect 的角度约定。
    """
    ys, xs = np.nonzero(mask)
    if len(xs) < 10:
        return None
    pts = np.stack((xs, ys), axis=1).astype(np.float64)
    cov = np.cov((pts - pts.mean(axis=0)).T)
    eigval, eigvec = np.linalg.eigh(cov)
    axis = eigvec[:, int(np.argmax(eigval))]
    return axis / np.linalg.norm(axis)


class TippingJudge:
    """倒伏判断。

    seg 模式:mask 长轴与该处重力向上向量的夹角 > angle_thresh 判倒伏(最稳)。
    OBB 模式:旋转框长轴与重力向量夹角(标注量小于 seg,同样免受俯拍角影响)。
    bbox 模式:只有水平检测框时,用框高/宽比做启发式;相机俯仰较大时需重调阈值。
    """

    def __init__(self, gravity, angle_thresh=45.0, aspect_thresh=1.2):
        self.gravity = gravity
        self.angle_thresh = angle_thresh
        self.aspect_thresh = aspect_thresh

    def judge_by_mask(self, mask):
        """返回 (是否倒伏, 夹角角度, mask 质心);mask 太小无法判断时返回 (None, None, None)。"""
        ys, xs = np.nonzero(mask)
        if len(xs) < 10:
            return None, None, None
        axis = mask_long_axis(mask)
        if axis is None:
            return None, None, None
        center = (float(xs.mean()), float(ys.mean()))
        up = self.gravity.up_at(*center)
        cos = abs(float(np.dot(axis, up)))
        angle = float(np.degrees(np.arccos(np.clip(cos, 0.0, 1.0))))
        return angle > self.angle_thresh, angle, center

    def judge_by_obb(self, cx, cy, w, h, r):
        """OBB 模式:旋转框长轴与该处重力向上向量的夹角。r 为 xywhr 的旋转角(弧度)。

        射影几何保证:直立瓶的轴向投影必过竖直消失点,与局部 up 向量共线;
        倒伏则偏离。2D 夹角数值不等于 3D 倾角,阈值按图像空间经验调。
        ultralytics 的 xywhr 已归一到 w>=h(长边为 w),此处仍按通用公式兜底。
        """
        long_dir = (
            np.array([math.cos(r), math.sin(r)])
            if w >= h
            else np.array([-math.sin(r), math.cos(r)])
        )
        up = self.gravity.up_at(cx, cy)
        cos = abs(float(np.dot(long_dir, up)))
        angle = float(np.degrees(np.arccos(np.clip(cos, 0.0, 1.0))))
        return angle > self.angle_thresh, angle

    def judge_by_3d(self, bottle_points, elongation_min=2.0):
        """3D 模式:瓶身点云 PCA 长轴与 3D 重力向量夹角(度)。免疫 2D 投影盲区。

        返回 (是否倒伏, 夹角角度, 伸长比)。伸长比 = 点云协方差前两大特征值之比,
        低于 elongation_min 说明点太"团"(mask 泄漏到背景或瓶子几乎正对镜头),结果仅供参考。
        """
        pts = np.asarray(bottle_points, dtype=np.float64)
        if len(pts) < 50:
            return None, None, None
        c = pts.mean(axis=0)
        cov = np.cov((pts - c).T)
        eigval, eigvec = np.linalg.eigh(cov)
        axis = eigvec[:, int(np.argmax(eigval))]
        elong = float(eigval[-1] / max(eigval[-2], 1e-12))
        up = self.gravity.gravity3d
        cos = abs(float(np.dot(axis, up)))
        angle = float(np.degrees(np.arccos(np.clip(cos, 0.0, 1.0))))
        return angle > self.angle_thresh, angle, elong

    def judge_by_bbox(self, bbox):
        """bbox 模式:返回 (是否倒伏, 框高/宽比)。"""
        x1, y1, x2, y2 = bbox
        aspect = (y2 - y1) / max(x2 - x1, 1e-6)
        return aspect < self.aspect_thresh, aspect
