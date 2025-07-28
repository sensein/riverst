"""Enhanced profiling system for bot pipeline performance analysis."""

import asyncio
import time
import json
import os
import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Union
from collections import defaultdict
from datetime import datetime
from contextlib import asynccontextmanager

from pipecat.processors.frame_processor import FrameProcessor, FrameDirection
from pipecat.frames.frames import Frame, MetricsFrame


@dataclass
class ProfileEvent:
    """Individual profiling event."""
    timestamp: float
    event_type: str  # 'start', 'end', 'milestone'
    component: str
    operation: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    duration: Optional[float] = None


@dataclass
class ComponentStats:
    """Statistics for a pipeline component."""
    total_calls: int = 0
    total_duration: float = 0.0
    avg_duration: float = 0.0
    min_duration: float = float('inf')
    max_duration: float = 0.0
    std_duration: float = 0.0
    durations: List[float] = field(default_factory=list)
    error_count: int = 0
    throughput_per_second: float = 0.0


class PipelineProfiler:
    """Comprehensive profiler for the entire bot pipeline."""
    
    def __init__(self, session_dir: str):
        self.session_dir = session_dir
        self.events: List[ProfileEvent] = []
        self.active_operations: Dict[str, ProfileEvent] = {}
        self.component_stats: Dict[str, ComponentStats] = defaultdict(ComponentStats)
        
        # Pipeline stages to track
        self.pipeline_stages = {
            'user_speech_start': 'User starts speaking',
            'user_speech_end': 'User stops speaking', 
            'stt_start': 'Speech-to-text processing starts',
            'stt_complete': 'Speech-to-text processing complete',
            'llm_request': 'LLM request sent',
            'llm_first_token': 'LLM first token received',
            'llm_complete': 'LLM response complete',
            'tts_start': 'Text-to-speech processing starts', 
            'tts_first_audio': 'First TTS audio chunk generated',
            'tts_complete': 'Text-to-speech processing complete',
            'audio_playback_start': 'Audio playback starts',
            'audio_playback_end': 'Audio playback ends',
            'turn_complete': 'Complete conversation turn finished'
        }
        
        self.session_start = time.time()
        
    def start_operation(self, component: str, operation: str, metadata: Dict[str, Any] = None) -> str:
        """Start timing an operation."""
        key = f"{component}:{operation}"
        
        event = ProfileEvent(
            timestamp=time.time(),
            event_type='start',
            component=component,
            operation=operation,
            metadata=metadata or {}
        )
        
        self.events.append(event)
        self.active_operations[key] = event
        return key
    
    def end_operation(self, key: str, metadata: Dict[str, Any] = None) -> Optional[float]:
        """End timing an operation and return duration."""
        if key not in self.active_operations:
            return None
            
        start_event = self.active_operations.pop(key)
        end_time = time.time()
        duration = end_time - start_event.timestamp
        
        end_event = ProfileEvent(
            timestamp=end_time,
            event_type='end',
            component=start_event.component,
            operation=start_event.operation,
            metadata=metadata or {},
            duration=duration
        )
        
        self.events.append(end_event)
        
        # Update component statistics
        stats = self.component_stats[start_event.component]
        stats.total_calls += 1
        stats.total_duration += duration
        stats.durations.append(duration)
        stats.min_duration = min(stats.min_duration, duration)
        stats.max_duration = max(stats.max_duration, duration)
        stats.avg_duration = stats.total_duration / stats.total_calls
        
        if len(stats.durations) > 1:
            stats.std_duration = statistics.stdev(stats.durations)
        
        return duration
    
    def log_milestone(self, component: str, milestone: str, metadata: Dict[str, Any] = None):
        """Log a milestone event."""
        event = ProfileEvent(
            timestamp=time.time(),
            event_type='milestone', 
            component=component,
            operation=milestone,
            metadata=metadata or {}
        )
        self.events.append(event)
    
    def log_error(self, component: str, operation: str, error: str):
        """Log an error event."""
        self.component_stats[component].error_count += 1
        self.log_milestone(component, f"{operation}_error", {"error": str(error)})
    
    @asynccontextmanager
    async def profile_operation(self, component: str, operation: str, metadata: Dict[str, Any] = None):
        """Context manager for profiling operations."""
        key = self.start_operation(component, operation, metadata)
        try:
            yield
        except Exception as e:
            self.log_error(component, operation, str(e))
            raise
        finally:
            self.end_operation(key)
    
    def get_pipeline_latency_breakdown(self) -> Dict[str, Any]:
        """Analyze end-to-end latency breakdown."""
        breakdown = {}
        
        # Find conversation turns by grouping events
        turns = self._group_events_by_turns()
        
        if not turns:
            return {"error": "No complete conversation turns found"}
            
        turn_latencies = []
        stage_latencies = defaultdict(list)
        
        for turn in turns:
            turn_start = turn[0].timestamp
            turn_end = turn[-1].timestamp
            total_latency = turn_end - turn_start
            turn_latencies.append(total_latency)
            
            # Calculate stage latencies within this turn
            stage_times = {}
            for event in turn:
                stage_key = f"{event.component}_{event.event_type}"
                stage_times[stage_key] = event.timestamp
            
            # Calculate specific stage durations
            if 'stt_start' in stage_times and 'stt_end' in stage_times:
                stage_latencies['stt'].append(stage_times['stt_end'] - stage_times['stt_start'])
            
            if 'llm_start' in stage_times and 'llm_end' in stage_times:
                stage_latencies['llm'].append(stage_times['llm_end'] - stage_times['llm_start'])
                
            if 'tts_start' in stage_times and 'tts_end' in stage_times:
                stage_latencies['tts'].append(stage_times['tts_end'] - stage_times['tts_start'])
        
        breakdown['total_turns'] = len(turns)
        breakdown['avg_turn_latency'] = statistics.mean(turn_latencies) if turn_latencies else 0
        breakdown['turn_latency_std'] = statistics.stdev(turn_latencies) if len(turn_latencies) > 1 else 0
        
        for stage, latencies in stage_latencies.items():
            if latencies:
                breakdown[f'{stage}_avg'] = statistics.mean(latencies)
                breakdown[f'{stage}_std'] = statistics.stdev(latencies) if len(latencies) > 1 else 0
                breakdown[f'{stage}_min'] = min(latencies)
                breakdown[f'{stage}_max'] = max(latencies)
        
        return breakdown
    
    def _group_events_by_turns(self) -> List[List[ProfileEvent]]:
        """Group events into conversation turns."""
        turns = []
        current_turn = []
        
        for event in sorted(self.events, key=lambda e: e.timestamp):
            if event.component == 'user' and event.event_type == 'start':
                if current_turn:
                    turns.append(current_turn)
                current_turn = [event]
            elif current_turn:
                current_turn.append(event)
                if (event.component == 'audio_playback' and event.event_type == 'end') or \
                   (event.operation == 'turn_complete'):
                    turns.append(current_turn)
                    current_turn = []
        
        if current_turn:
            turns.append(current_turn)
            
        return turns
    
    def get_component_performance(self) -> Dict[str, Dict[str, Any]]:
        """Get detailed performance stats for each component."""
        performance = {}
        
        for component, stats in self.component_stats.items():
            session_duration = time.time() - self.session_start
            stats.throughput_per_second = stats.total_calls / session_duration if session_duration > 0 else 0
            
            performance[component] = {
                'total_calls': stats.total_calls,
                'total_duration': stats.total_duration,
                'avg_duration': stats.avg_duration,
                'min_duration': stats.min_duration if stats.min_duration != float('inf') else 0,
                'max_duration': stats.max_duration,
                'std_duration': stats.std_duration,
                'error_count': stats.error_count,
                'error_rate': stats.error_count / stats.total_calls if stats.total_calls > 0 else 0,
                'throughput_per_second': stats.throughput_per_second
            }
        
        return performance
    
    def get_bottleneck_analysis(self) -> Dict[str, Any]:
        """Identify performance bottlenecks."""
        performance = self.get_component_performance()
        
        # Identify slowest components
        slowest_avg = max(performance.items(), key=lambda x: x[1]['avg_duration']) if performance else None
        slowest_max = max(performance.items(), key=lambda x: x[1]['max_duration']) if performance else None
        highest_error = max(performance.items(), key=lambda x: x[1]['error_rate']) if performance else None
        
        bottlenecks = {
            'slowest_average': {
                'component': slowest_avg[0] if slowest_avg else None,
                'avg_duration': slowest_avg[1]['avg_duration'] if slowest_avg else 0
            },
            'slowest_peak': {
                'component': slowest_max[0] if slowest_max else None, 
                'max_duration': slowest_max[1]['max_duration'] if slowest_max else 0
            },
            'highest_error_rate': {
                'component': highest_error[0] if highest_error else None,
                'error_rate': highest_error[1]['error_rate'] if highest_error else 0
            }
        }
        
        return bottlenecks
    
    async def save_profile_report(self):
        """Save comprehensive profiling report."""
        report = {
            'session_metadata': {
                'session_dir': self.session_dir,
                'session_start': self.session_start,
                'session_end': time.time(),
                'total_duration': time.time() - self.session_start,
                'total_events': len(self.events)
            },
            'pipeline_latency': self.get_pipeline_latency_breakdown(),
            'component_performance': self.get_component_performance(),
            'bottleneck_analysis': self.get_bottleneck_analysis(),
            'raw_events': [
                {
                    'timestamp': event.timestamp,
                    'relative_time': event.timestamp - self.session_start,
                    'event_type': event.event_type,
                    'component': event.component,
                    'operation': event.operation,
                    'duration': event.duration,
                    'metadata': event.metadata
                }
                for event in self.events
            ]
        }
        
        profile_path = os.path.join(self.session_dir, "pipeline_profile.json")
        with open(profile_path, 'w') as f:
            json.dump(report, f, indent=2, default=str)
        
        # Also save a summary report
        summary = {
            'session_summary': report['session_metadata'],
            'performance_summary': {
                'total_components': len(self.component_stats),
                'total_operations': sum(stats.total_calls for stats in self.component_stats.values()),
                'total_errors': sum(stats.error_count for stats in self.component_stats.values()),
                'avg_turn_latency': report['pipeline_latency'].get('avg_turn_latency', 0)
            },
            'top_bottlenecks': report['bottleneck_analysis']
        }
        
        summary_path = os.path.join(self.session_dir, "profile_summary.json")
        with open(summary_path, 'w') as f:
            json.dump(summary, f, indent=2, default=str)
            
        print(f"Pipeline profiling report saved to {profile_path}")
        print(f"Profile summary saved to {summary_path}")


class ProfiledFrameProcessor(FrameProcessor):
    """Frame processor wrapper that adds profiling capabilities."""
    
    def __init__(self, wrapped_processor: FrameProcessor, profiler: PipelineProfiler, component_name: str):
        super().__init__()
        self.wrapped = wrapped_processor
        self.profiler = profiler
        self.component_name = component_name
        
    async def process_frame(self, frame: Frame, direction: FrameDirection):
        """Profile frame processing."""
        frame_type = type(frame).__name__
        
        async with self.profiler.profile_operation(
            self.component_name, 
            f"process_{frame_type}", 
            {"frame_type": frame_type, "direction": direction.value}
        ):
            return await self.wrapped.process_frame(frame, direction)