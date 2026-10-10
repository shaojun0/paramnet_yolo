from .gravity import GravityEstimator, MoGeGravity
from .tipping import TippingJudge

__all__ = ["GravityEstimator", "MoGeGravity", "TippingJudge"]


def __getattr__(name):
    # sam3_seg 惰性导入:SAM3 加载较重,不用 --sam3 时不付出 import 代价
    if name == "Sam3Segmenter":
        from .sam3_seg import Sam3Segmenter

        return Sam3Segmenter
    raise AttributeError(name)
