"""端到端自检:离线加载 ParamNet 权重 → 推理 → 打印输出键与重力场语义。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import numpy as np
import torch

from paramnet_yolo import GravityEstimator

print("torch", torch.__version__, "| cuda:", torch.cuda.is_available())

# 随机噪声图只验证管线跑通,roll/pitch 数值无物理意义
frame = (np.random.default_rng(0).random((480, 640, 3)) * 255).astype("uint8")

est = GravityEstimator()
pred = est.infer(frame)
print("输出键:", sorted(pred.keys()))
print("pred_gravity_original 形状:", tuple(pred["pred_gravity_original"].shape))
print(
    "roll/pitch/vfov(度):",
    round(float(pred["pred_roll"]), 2),
    round(float(pred["pred_pitch"]), 2),
    round(float(pred["pred_vfov"]), 2),
)

est.calibrate([frame] * 3)
print("缓存重力场形状:", est.field.shape)
up = est.up_at(320, 240)
print("图中心 up 向量 (dx, dy):", up.round(3), "| dy 为负 = 指向图像上方")
print("OK: 权重离线加载、推理、查表全部通过")
