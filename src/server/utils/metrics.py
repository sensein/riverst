import os
import json
import datetime
import statistics
from typing import List, Dict, Any

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, MetricsFrame


class MetricsLoggerProcessor(FrameProcessor):
    def __init__(self, session_dir: str):
        print("Initializing MetricsLoggerProcessor...")
        super().__init__()

        self.session_dir = session_dir
        self.summary_path = os.path.join(session_dir, "metrics_summary.json")
        self.metrics_log_path = os.path.join(session_dir, "metrics_log.json")
        if os.path.exists(self.metrics_log_path):
            with open(self.metrics_log_path, "r", encoding="utf-8") as f:
                try:
                    self.metrics: List[dict] = json.load(f)
                except Exception:
                    self.metrics: List[dict] = []
        else:
            self.metrics: List[dict] = []
        print(f"Metrics: {self.metrics}")
        os.makedirs(session_dir, exist_ok=True)

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        await super().process_frame(frame, direction)

        if isinstance(frame, MetricsFrame):
            timestamp = datetime.datetime.now().isoformat()
            for item in frame.data:
                base = {
                    "timestamp": timestamp,
                    "type": type(item).__name__,
                    "processor": getattr(item, "processor", None),
                    "model": getattr(item, "model", None),
                }

                metrics = self._extract_metric_values(item)
                record = {**base, **metrics}
                self.metrics.append(record)

            with open(self.metrics_log_path, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, indent=2)

        await self.push_frame(frame, direction)

    def _extract_metric_values(self, item: Any) -> Dict[str, Any]:
        value = getattr(item, "value", None)
        if isinstance(value, (int, float)):
            return {"value": value}
        elif hasattr(value, "__dict__"):
            return value.__dict__
        return {"value": value}

    def _aggregate_metric_values(self, values: List[float]) -> Dict[str, float]:
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values) if values else 0,
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values) if values else 0,
            "max": max(values) if values else 0,
        }

    async def aggregate_and_save(self):
        if not self.metrics:
            return

        aggregation: Dict[str, Dict[str, Dict[str, List[float]]]] = {}

        for entry in self.metrics:
            processor = entry.get("processor", "unknownProcessor")
            metric_type = entry.get("type", "UnknownMetric")

            if processor not in aggregation:
                aggregation[processor] = {}

            if metric_type not in aggregation[processor]:
                aggregation[processor][metric_type] = {}

            for key, val in entry.items():
                if isinstance(val, (int, float)) and key not in ["timestamp"]:
                    values = aggregation[processor][metric_type].setdefault(key, [])
                    values.append(val)

        summary = {
            "timestamp": datetime.datetime.now().isoformat(),
            "processors": {}
        }

        for proc, metrics in aggregation.items():
            summary["processors"][proc] = {}
            for metric_type, fields in metrics.items():
                summary["processors"][proc][metric_type] = {
                    field: self._aggregate_metric_values(values)
                    for field, values in fields.items()
                }

        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
