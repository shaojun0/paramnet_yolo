import contextlib

import cv2
import numpy as np
import torch

SAM3_CKPT = r"E:\modelscope\hub\models\sam3\sam3.pt"


class Sam3Segmenter:
    """SAM3 图像分割封装:YOLO 框作 box prompt,输出贴身 mask 用于过滤点云背景。"""

    def __init__(self, ckpt=SAM3_CKPT, device=None, confidence=0.5):
        from sam3 import build_sam3_image_model
        from sam3.model.sam3_image_processor import Sam3Processor

        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        self.model = build_sam3_image_model(
            checkpoint_path=ckpt, load_from_HF=False, device=self.device
        )
        self.processor = Sam3Processor(self.model, confidence_threshold=confidence)
        self.state = None
        self.size = None

    def _autocast(self):
        # 官方 checkpoint 混有 bf16 权重,官方示例在 bf16 autocast 下运行
        if self.device.startswith("cuda"):
            return torch.autocast("cuda", dtype=torch.bfloat16)
        return contextlib.nullcontext()

    def set_image(self, frame_bgr):
        from PIL import Image

        rgb = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB)
        pil = Image.fromarray(rgb)
        self.size = pil.size  # (W, H)
        with self._autocast():
            self.state = self.processor.set_image(pil)
        return self

    def mask_from_box(self, x1, y1, x2, y2):
        """框(x1,y1,x2,y2) → SAM3 mask (H,W) bool;无输出时返回 None。"""
        from sam3.model.box_ops import box_xywh_to_cxcywh

        xywh = torch.tensor(
            [float(x1), float(y1), float(x2 - x1), float(y2 - y1)]
        ).view(-1, 4)
        cxcywh = box_xywh_to_cxcywh(xywh)
        w, h = self.size
        norm_box = (cxcywh / torch.tensor([w, h, w, h])).flatten().tolist()

        self.processor.reset_all_prompts(self.state)
        with self._autocast():
            self.state = self.processor.add_geometric_prompt(
                box=norm_box, label=True, state=self.state
            )
        masks = self.state.get("masks")
        if masks is None or len(masks) == 0:
            return None
        return masks[0, 0].float().cpu().numpy() > 0.5
