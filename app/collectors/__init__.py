from .crowdworks import CrowdWorksCollector
from .coconala import CoconalaCollector

COLLECTORS = {
    "crowdworks": CrowdWorksCollector,
    "coconala": CoconalaCollector,
}

__all__ = ["COLLECTORS", "CrowdWorksCollector", "CoconalaCollector"]
