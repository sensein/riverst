"""Tool for analyzing pipeline profiling results."""

import json
import os
from typing import Dict, Any
from datetime import datetime


class ProfileAnalyzer:
    """Analyze and visualize pipeline profiling results."""

    def __init__(self, session_dir: str):
        self.session_dir = session_dir
        self.profile_path = os.path.join(session_dir, "pipeline_profile.json")
        self.metrics_path = os.path.join(session_dir, "metrics_summary.json")

    def load_profile_data(self) -> Dict[str, Any]:
        """Load pipeline profile data."""
        if not os.path.exists(self.profile_path):
            raise FileNotFoundError(f"Profile data not found at {self.profile_path}")

        with open(self.profile_path, "r") as f:
            return json.load(f)

    def print_session_summary(self):
        """Print high-level session summary."""
        data = self.load_profile_data()
        meta = data["session_metadata"]

        print("=" * 60)
        print("PIPELINE PROFILING SUMMARY")
        print("=" * 60)
        print(f"Session Duration: {meta['total_duration_seconds']:.2f} seconds")
        print(f"Total Turns: {meta['total_turns']}")
        print(f"Total Frames Processed: {meta['total_frames_processed']:,}")
        print()

    def print_latency_analysis(self):
        """Print detailed latency analysis."""
        data = self.load_profile_data()
        analysis = data.get("turn_analysis", {})

        print("LATENCY BREAKDOWN")
        print("-" * 40)

        key_metrics = [
            ("total_turn_latency", "Total Turn Latency"),
            ("stt_duration", "Speech-to-Text"),
            ("llm_duration", "LLM Processing"),
            ("tts_duration", "Text-to-Speech"),
            ("time_to_first_token", "Time to First Token"),
            ("time_to_first_audio", "Time to First Audio"),
        ]

        for metric_key, metric_name in key_metrics:
            if metric_key in analysis:
                stats = analysis[metric_key]
                if stats["count"] > 0:
                    print(
                        f"{metric_name:20} | Avg: {stats['avg']:.3f}s | "
                        f"Min: {stats['min']:.3f}s | Max: {stats['max']:.3f}s | "
                        f"Std: {stats['std']:.3f}s | Count: {stats['count']}"
                    )
                else:
                    print(f"{metric_name:20} | No data available")
        print()

    def print_bottleneck_analysis(self):
        """Print bottleneck analysis."""
        data = self.load_profile_data()
        bottlenecks = data.get("bottleneck_analysis", {})

        print("BOTTLENECK ANALYSIS")
        print("-" * 40)

        if "slowest_stage" in bottlenecks:
            slowest = bottlenecks["slowest_stage"]
            print(
                f"Slowest Stage: {slowest['name']} ({slowest['avg_duration']:.3f}s avg)"
            )
            print()

        if "stage_percentages" in bottlenecks:
            print("Processing Time Breakdown:")
            for stage, percentage in bottlenecks["stage_percentages"].items():
                print(f"  {stage:15} : {percentage:.1f}%")
        print()

    def print_frame_statistics(self):
        """Print frame processing statistics."""
        data = self.load_profile_data()
        frame_stats = data.get("frame_analysis", {})

        print("FRAME PROCESSING STATISTICS")
        print("-" * 40)

        # Sort by frame count descending
        sorted_frames = sorted(
            frame_stats.items(), key=lambda x: x[1]["count"], reverse=True
        )

        print(f"{'Frame Type':25} | {'Count':>8} | {'Avg Size':>10} | {'Total MB':>10}")
        print("-" * 70)

        for frame_type, stats in sorted_frames:
            count = stats["count"]
            avg_size = stats.get("avg_size_bytes", 0)
            total_mb = stats.get("total_bytes", 0) / (1024 * 1024)

            print(
                f"{frame_type:25} | {count:8,} | {avg_size:8,.0f}B | {total_mb:8.2f}MB"
            )
        print()

    def print_turn_details(self, max_turns: int = 5):
        """Print detailed information for recent turns."""
        data = self.load_profile_data()
        turns = data.get("detailed_turns", [])

        print(f"TURN DETAILS (Last {min(max_turns, len(turns))} turns)")
        print("-" * 60)

        for turn in turns[-max_turns:]:
            turn_num = turn["turn_number"]
            durations = turn["durations"]

            print(f"Turn {turn_num}:")
            if durations.get("total_turn_latency"):
                print(f"  Total Latency: {durations['total_turn_latency']:.3f}s")

            stages = [
                ("stt_duration", "STT"),
                ("llm_duration", "LLM"),
                ("tts_duration", "TTS"),
                ("time_to_first_token", "First Token"),
                ("time_to_first_audio", "First Audio"),
            ]

            for dur_key, stage_name in stages:
                if durations.get(dur_key):
                    print(f"    {stage_name:12}: {durations[dur_key]:.3f}s")
            print()

    def generate_performance_report(self) -> str:
        """Generate a comprehensive performance report."""
        data = self.load_profile_data()

        report_lines = []
        report_lines.append("PIPELINE PERFORMANCE REPORT")
        report_lines.append("=" * 50)
        report_lines.append(f"Generated: {datetime.now().isoformat()}")
        report_lines.append(f"Session: {self.session_dir}")
        report_lines.append("")

        # Session overview
        meta = data["session_metadata"]
        report_lines.append("SESSION OVERVIEW:")
        report_lines.append(f"  Duration: {meta['total_duration_seconds']:.2f} seconds")
        report_lines.append(f"  Turns: {meta['total_turns']}")
        report_lines.append(f"  Frames: {meta['total_frames_processed']:,}")
        report_lines.append("")

        # Key performance metrics
        analysis = data.get("turn_analysis", {})
        if "total_turn_latency" in analysis:
            total_stats = analysis["total_turn_latency"]
            if total_stats["count"] > 0:
                report_lines.append("KEY PERFORMANCE METRICS:")
                report_lines.append(
                    f"  Average Turn Latency: {total_stats['avg']:.3f}s"
                )
                report_lines.append(f"  Best Turn: {total_stats['min']:.3f}s")
                report_lines.append(f"  Worst Turn: {total_stats['max']:.3f}s")
                report_lines.append(f"  Consistency (std): {total_stats['std']:.3f}s")
                report_lines.append("")

        # Bottlenecks
        bottlenecks = data.get("bottleneck_analysis", {})
        if "slowest_stage" in bottlenecks:
            slowest = bottlenecks["slowest_stage"]
            report_lines.append("PERFORMANCE BOTTLENECKS:")
            report_lines.append(
                f"  Primary bottleneck: {slowest['name']} ({slowest['avg_duration']:.3f}s)"
            )

            if "stage_percentages" in bottlenecks:
                report_lines.append("  Time distribution:")
                for stage, pct in bottlenecks["stage_percentages"].items():
                    report_lines.append(f"    {stage}: {pct:.1f}%")
            report_lines.append("")

        # Recommendations
        report_lines.append("OPTIMIZATION RECOMMENDATIONS:")
        if bottlenecks and "slowest_stage" in bottlenecks:
            slowest_name = bottlenecks["slowest_stage"]["name"]
            if "llm" in slowest_name:
                report_lines.append("  - Consider using a faster LLM model")
                report_lines.append("  - Optimize prompts to reduce token count")
                report_lines.append(
                    "  - Enable streaming for faster perceived response"
                )
            elif "tts" in slowest_name:
                report_lines.append("  - Consider using a faster TTS service")
                report_lines.append("  - Pre-generate common responses")
            elif "stt" in slowest_name:
                report_lines.append("  - Consider using a faster STT service")
                report_lines.append("  - Optimize audio processing pipeline")

        return "\n".join(report_lines)

    def save_report(self, output_file: str = None):
        """Save performance report to file."""
        if output_file is None:
            output_file = os.path.join(self.session_dir, "performance_report.txt")

        report = self.generate_performance_report()
        with open(output_file, "w") as f:
            f.write(report)

        print(f"Performance report saved to: {output_file}")

    def compare_sessions(self, other_session_dir: str):
        """Compare performance between two sessions."""
        other_analyzer = ProfileAnalyzer(other_session_dir)

        data1 = self.load_profile_data()
        data2 = other_analyzer.load_profile_data()

        print("SESSION COMPARISON")
        print("=" * 50)
        print(f"Session A: {os.path.basename(self.session_dir)}")
        print(f"Session B: {os.path.basename(other_session_dir)}")
        print()

        # Compare key metrics
        analysis1 = data1.get("turn_analysis", {})
        analysis2 = data2.get("turn_analysis", {})

        metrics_to_compare = [
            ("total_turn_latency", "Total Turn Latency"),
            ("stt_duration", "STT Duration"),
            ("llm_duration", "LLM Duration"),
            ("tts_duration", "TTS Duration"),
        ]

        print(
            f"{'Metric':20} | {'Session A':>10} | {'Session B':>10} | {'Difference':>12}"
        )
        print("-" * 65)

        for metric_key, metric_name in metrics_to_compare:
            if metric_key in analysis1 and metric_key in analysis2:
                avg1 = analysis1[metric_key].get("avg", 0)
                avg2 = analysis2[metric_key].get("avg", 0)
                diff = avg2 - avg1
                diff_pct = ((avg2 - avg1) / avg1 * 100) if avg1 > 0 else 0

                print(
                    f"{metric_name:20} | {avg1:8.3f}s | {avg2:8.3f}s | {diff:+7.3f}s ({diff_pct:+.1f}%)"
                )


def analyze_session(session_dir: str):
    """Quick analysis of a session."""
    analyzer = ProfileAnalyzer(session_dir)

    try:
        analyzer.print_session_summary()
        analyzer.print_latency_analysis()
        analyzer.print_bottleneck_analysis()
        analyzer.print_frame_statistics()
        analyzer.print_turn_details()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("Make sure to run a bot session first to generate profiling data.")


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        session_path = sys.argv[1]
        analyze_session(session_path)
    else:
        print("Usage: python profile_analyzer.py <session_directory>")
