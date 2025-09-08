"""This module provides the MetricsLoggerProcessor for logging and aggregating metrics frames."""

import os
import json
import datetime
import statistics
from typing import List, Dict, Any

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, MetricsFrame


class MetricsLoggerProcessor(FrameProcessor):
    """Logs and aggregates metrics frames during a session."""

    def __init__(self, session_dir: str):
        """Initialize the metrics logger with paths and previous logs (if any)."""
        super().__init__()

        self.session_dir = session_dir
        self.summary_path = os.path.join(session_dir, "metrics_summary.json")
        self.metrics_log_path = os.path.join(session_dir, "metrics_log.json")

        os.makedirs(session_dir, exist_ok=True)

        if os.path.exists(self.metrics_log_path):
            try:
                with open(self.metrics_log_path, "r", encoding="utf-8") as f:
                    self.metrics: List[Dict[str, Any]] = json.load(f)
            except Exception:
                self.metrics = []
        else:
            self.metrics = []

    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Intercept MetricsFrame and log relevant values."""
        await super().process_frame(frame, direction)

        if isinstance(frame, MetricsFrame):
            timestamp = datetime.datetime.now().isoformat()

            for item in frame.data:
                processor = self._get_clean_processor_name(
                    getattr(item, "processor", None)
                )
                base_info = {
                    "timestamp": timestamp,
                    "type": type(item).__name__,
                    "processor": processor,
                    "model": getattr(item, "model", None),
                }

                metric_values = self._extract_metric_values(item)
                self.metrics.append({**base_info, **metric_values})

            with open(self.metrics_log_path, "w", encoding="utf-8") as f:
                json.dump(self.metrics, f, indent=2)

        await self.push_frame(frame, direction)

    async def aggregate_and_save(self):
        """Aggregate all recorded metrics and write a summary JSON file."""
        if not self.metrics:
            return

        aggregation: Dict[str, Dict[str, Dict[str, List[float]]]] = {}

        for entry in self.metrics:
            processor = entry.get("processor", "unknownProcessor")
            metric_type = entry.get("type", "UnknownMetric")

            aggregation.setdefault(processor, {}).setdefault(metric_type, {})

            for key, val in entry.items():
                if isinstance(val, (int, float)) and key != "timestamp":
                    aggregation[processor][metric_type].setdefault(key, []).append(val)

        summary = {
            "timestamp": datetime.datetime.now().isoformat(),
            "processors": {
                proc: {
                    metric_type: {
                        field: self._aggregate_metric_values(values)
                        for field, values in fields.items()
                    }
                    for metric_type, fields in types.items()
                }
                for proc, types in aggregation.items()
            },
        }

        with open(self.summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    def _get_clean_processor_name(self, raw_processor: Any) -> Any:
        """Remove fragment identifiers (e.g., #id) from processor name."""
        if isinstance(raw_processor, str) and "#" in raw_processor:
            return raw_processor.split("#")[0]
        return raw_processor

    def _extract_metric_values(self, item: Any) -> Dict[str, Any]:
        """Extract metric values from item."""
        value = getattr(item, "value", None)
        if isinstance(value, (int, float)):
            return {"value": value}
        if hasattr(value, "__dict__"):
            return value.__dict__
        return {"value": value}

    def _aggregate_metric_values(self, values: List[float]) -> Dict[str, float]:
        """Compute statistics from a list of float values."""
        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values) if values else 0.0,
            "std": statistics.stdev(values) if len(values) > 1 else 0.0,
            "min": min(values) if values else 0.0,
            "max": max(values) if values else 0.0,
        }
