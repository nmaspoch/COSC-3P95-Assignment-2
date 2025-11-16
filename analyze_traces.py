import json
import sys
from typing import Dict, List, Tuple
from collections import defaultdict
import statistics

class JaegerTraceAnalyzer:
    def __init__(self, client_json_path: str, server_json_path: str = None):
        """
        Initialize the analyzer with paths to Jaeger JSON exports
        
        Args:
            client_json_path: Path to client traces JSON file
            server_json_path: Path to server traces JSON file (optional)
        """
        self.client_data = self._load_json(client_json_path)
        self.server_data = self._load_json(server_json_path) if server_json_path else None
        
    def _load_json(self, filepath: str) -> dict:
        """Load JSON file"""
        try:
            with open(filepath, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"Error: File {filepath} not found")
            sys.exit(1)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON in {filepath}: {e}")
            sys.exit(1)
    
    def _extract_traces(self, data: dict) -> List[dict]:
        """Extract traces from Jaeger JSON format"""
        if 'data' in data:
            return data['data']
        elif isinstance(data, list):
            return data
        else:
            print("Warning: Unexpected JSON structure")
            return []
    
    def _get_span_duration_ms(self, span: dict) -> float:
        """Get span duration in milliseconds"""
        # Jaeger stores duration in microseconds
        return span.get('duration', 0) / 1000.0
    
    def _get_span_attribute(self, span: dict, key: str, default=None):
        """Extract attribute/tag value from span"""
        tags = span.get('tags', [])
        for tag in tags:
            if tag.get('key') == key:
                value = tag.get('value', default)
                # Handle different types
                if tag.get('type') == 'bool':
                    return value
                elif tag.get('type') in ['int64', 'float64']:
                    return value
                return value
        return default
    
    def _get_all_spans_by_name(self, traces: List[dict], span_name: str) -> List[dict]:
        """Find all spans with a specific operation name across all traces"""
        matching_spans = []
        for trace in traces:
            for span in trace.get('spans', []):
                if span.get('operationName') == span_name:
                    matching_spans.append(span)
        return matching_spans
    
    def _get_root_spans(self, traces: List[dict]) -> List[dict]:
        """Get root spans (spans without parents) from traces"""
        root_spans = []
        for trace in traces:
            trace_id = trace.get('traceID')
            spans = trace.get('spans', [])
            
            # Build parent-child relationship
            span_ids = {s['spanID'] for s in spans}
            for span in spans:
                # Check if this span has a parent in the same trace
                has_parent = False
                refs = span.get('references', [])
                for ref in refs:
                    if ref.get('refType') == 'CHILD_OF' and ref.get('spanID') in span_ids:
                        has_parent = True
                        break
                
                if not has_parent:
                    root_spans.append(span)
        
        return root_spans
    
    def analyze_client_performance(self) -> Dict:
        """Analyze client-side performance metrics"""
        print("\n" + "="*80)
        print("CLIENT PERFORMANCE ANALYSIS")
        print("="*80)
        
        traces = self._extract_traces(self.client_data)
        
        if not traces:
            print("No traces found!")
            return {}
        
        # Find client_span (main span for each client execution)
        client_spans = self._get_all_spans_by_name(traces, "client_span")
        
        if not client_spans:
            print("Warning: No 'client_span' found. Trying to use root spans...")
            client_spans = self._get_root_spans(traces)
        
        if not client_spans:
            print("No suitable spans found for analysis!")
            return {}
        
        print(f"\nFound {len(client_spans)} client execution(s)")
        
        # Extract latency data
        latencies = []
        total_files_list = []
        total_bytes_list = []
        latency_seconds_list = []
        
        for span in client_spans:
            duration_ms = self._get_span_duration_ms(span)
            latencies.append(duration_ms)
            
            # Try to get total_latency_seconds attribute if available
            latency_sec = self._get_span_attribute(span, "total_latency_seconds")
            if latency_sec:
                latency_seconds_list.append(float(latency_sec))
            
            total_files = self._get_span_attribute(span, "total_files", 0)
            total_bytes = self._get_span_attribute(span, "total_bytes", 0)
            
            if total_files:
                total_files_list.append(int(total_files))
            if total_bytes:
                total_bytes_list.append(int(total_bytes))
        
        # Calculate statistics
        results = {
            'num_runs': len(client_spans),
            'latency_ms': {
                'average': statistics.mean(latencies),
                'min': min(latencies),
                'max': max(latencies),
                'median': statistics.median(latencies),
                'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0
            }
        }
        
        # Calculate throughput if we have the necessary data
        if total_files_list and total_bytes_list:
            throughput_files_per_sec = []
            throughput_bytes_per_sec = []
            throughput_mbps = []
            
            for i, latency in enumerate(latencies):
                if latency > 0 and i < len(total_files_list):
                    latency_sec = latency / 1000.0
                    files_per_sec = total_files_list[i] / latency_sec
                    bytes_per_sec = total_bytes_list[i] / latency_sec
                    mbps = (bytes_per_sec * 8) / (1024 * 1024)  # Convert to Mbps
                    
                    throughput_files_per_sec.append(files_per_sec)
                    throughput_bytes_per_sec.append(bytes_per_sec)
                    throughput_mbps.append(mbps)
            
            if throughput_files_per_sec:
                results['throughput'] = {
                    'files_per_second': {
                        'average': statistics.mean(throughput_files_per_sec),
                        'min': min(throughput_files_per_sec),
                        'max': max(throughput_files_per_sec)
                    },
                    'bytes_per_second': {
                        'average': statistics.mean(throughput_bytes_per_sec),
                        'min': min(throughput_bytes_per_sec),
                        'max': max(throughput_bytes_per_sec)
                    },
                    'mbps': {
                        'average': statistics.mean(throughput_mbps),
                        'min': min(throughput_mbps),
                        'max': max(throughput_mbps)
                    }
                }
                
                results['total_files'] = {
                    'total': sum(total_files_list),
                    'average_per_run': statistics.mean(total_files_list)
                }
                
                results['total_bytes'] = {
                    'total': sum(total_bytes_list),
                    'average_per_run': statistics.mean(total_bytes_list)
                }
        
        # Print results
        print(f"\nNumber of Client Runs: {results['num_runs']}")
        
        if 'total_files' in results:
            print(f"Total Files Transferred: {results['total_files']['total']}")
            print(f"Average Files per Run: {results['total_files']['average_per_run']:.1f}")
            print(f"Total Bytes Transferred: {results['total_bytes']['total']:,} bytes ({results['total_bytes']['total']/1024/1024:.2f} MB)")
        
        print(f"\n--- LATENCY (milliseconds) ---")
        print(f"  Average: {results['latency_ms']['average']:.2f} ms ({results['latency_ms']['average']/1000:.2f} seconds)")
        print(f"  Minimum: {results['latency_ms']['min']:.2f} ms ({results['latency_ms']['min']/1000:.2f} seconds)")
        print(f"  Maximum: {results['latency_ms']['max']:.2f} ms ({results['latency_ms']['max']/1000:.2f} seconds)")
        print(f"  Median:  {results['latency_ms']['median']:.2f} ms ({results['latency_ms']['median']/1000:.2f} seconds)")
        if results['num_runs'] > 1:
            print(f"  Std Dev: {results['latency_ms']['stdev']:.2f} ms")
        
        if 'throughput' in results:
            print(f"\n--- THROUGHPUT ---")
            print(f"  Files per Second:")
            print(f"    Average: {results['throughput']['files_per_second']['average']:.2f} files/sec")
            print(f"    Min:     {results['throughput']['files_per_second']['min']:.2f} files/sec")
            print(f"    Max:     {results['throughput']['files_per_second']['max']:.2f} files/sec")
            
            print(f"\n  Bytes per Second:")
            print(f"    Average: {results['throughput']['bytes_per_second']['average']:,.0f} bytes/sec ({results['throughput']['bytes_per_second']['average']/1024/1024:.2f} MB/sec)")
            print(f"    Min:     {results['throughput']['bytes_per_second']['min']:,.0f} bytes/sec ({results['throughput']['bytes_per_second']['min']/1024/1024:.2f} MB/sec)")
            print(f"    Max:     {results['throughput']['bytes_per_second']['max']:,.0f} bytes/sec ({results['throughput']['bytes_per_second']['max']/1024/1024:.2f} MB/sec)")
            
            print(f"\n  Network Throughput:")
            print(f"    Average: {results['throughput']['mbps']['average']:.2f} Mbps")
            print(f"    Min:     {results['throughput']['mbps']['min']:.2f} Mbps")
            print(f"    Max:     {results['throughput']['mbps']['max']:.2f} Mbps")
        
        return results
    
    def analyze_server_performance(self) -> Dict:
        """Analyze server-side performance metrics"""
        if not self.server_data:
            print("\nNo server data provided, skipping server analysis")
            return {}
        
        print("\n" + "="*80)
        print("SERVER PERFORMANCE ANALYSIS")
        print("="*80)
        
        traces = self._extract_traces(self.server_data)
        
        # Find client handling spans
        client_handling_spans = self._get_all_spans_by_name(traces, "client_span")
        
        if not client_handling_spans:
            print("No 'client_span' traces found in server data!")
            return {}
        
        # Extract latency data
        latencies = []
        num_files_list = []
        
        for span in client_handling_spans:
            duration_ms = self._get_span_duration_ms(span)
            latencies.append(duration_ms)
            
            num_files = self._get_span_attribute(span, "num_files_expected", 0)
            if num_files:
                num_files_list.append(int(num_files))
        
        # Calculate statistics
        results = {
            'num_client_connections': len(client_handling_spans),
            'latency_ms': {
                'average': statistics.mean(latencies),
                'min': min(latencies),
                'max': max(latencies),
                'median': statistics.median(latencies),
                'stdev': statistics.stdev(latencies) if len(latencies) > 1 else 0
            }
        }
        
        # Print results
        print(f"\nNumber of Client Connections Handled: {results['num_client_connections']}")
        if num_files_list:
            print(f"Total Files Received: {sum(num_files_list)}")
        
        print(f"\n--- SERVER LATENCY (milliseconds) ---")
        print(f"  Average: {results['latency_ms']['average']:.2f} ms ({results['latency_ms']['average']/1000:.2f} seconds)")
        print(f"  Minimum: {results['latency_ms']['min']:.2f} ms ({results['latency_ms']['min']/1000:.2f} seconds)")
        print(f"  Maximum: {results['latency_ms']['max']:.2f} ms ({results['latency_ms']['max']/1000:.2f} seconds)")
        print(f"  Median:  {results['latency_ms']['median']:.2f} ms ({results['latency_ms']['median']/1000:.2f} seconds)")
        if len(latencies) > 1:
            print(f"  Std Dev: {results['latency_ms']['stdev']:.2f} ms")
        
        return results
    
    def analyze_file_operations(self):
        """Analyze individual file operations"""
        print("\n" + "="*80)
        print("FILE OPERATION ANALYSIS")
        print("="*80)
        
        traces = self._extract_traces(self.client_data)
        
        # Find sent_file spans (client-side)
        sent_file_spans = self._get_all_spans_by_name(traces, "sent_file")
        
        if sent_file_spans:
            file_latencies = [self._get_span_duration_ms(span) for span in sent_file_spans]
            
            print(f"\n--- FILE SEND OPERATIONS (Client) ---")
            print(f"  Total files sent: {len(sent_file_spans)}")
            print(f"  Average time per file: {statistics.mean(file_latencies):.2f} ms")
            print(f"  Min time: {min(file_latencies):.2f} ms")
            print(f"  Max time: {max(file_latencies):.2f} ms")
            print(f"  Median time: {statistics.median(file_latencies):.2f} ms")
            
            # Analyze compression ratios
            compression_ratios = []
            compressed_count = 0
            uncompressed_count = 0
            
            for span in sent_file_spans:
                is_compressed = self._get_span_attribute(span, "is_compressed")
                if is_compressed:
                    compressed_count += 1
                    ratio = self._get_span_attribute(span, "compression_ratio")
                    if ratio is not None:
                        compression_ratios.append(float(ratio))
                else:
                    uncompressed_count += 1
            
            print(f"\n  Compression Statistics:")
            print(f"    Files compressed: {compressed_count}")
            print(f"    Files not compressed: {uncompressed_count}")
            
            if compression_ratios:
                print(f"    Average compression ratio: {statistics.mean(compression_ratios):.2%}")
                print(f"    Min compression ratio: {min(compression_ratios):.2%}")
                print(f"    Max compression ratio: {max(compression_ratios):.2%}")
            
            # Analyze file sizes
            original_sizes = []
            encrypted_sizes = []
            
            for span in sent_file_spans:
                orig_size = self._get_span_attribute(span, "original_size")
                enc_size = self._get_span_attribute(span, "encrypted_size")
                
                if orig_size:
                    original_sizes.append(int(orig_size))
                if enc_size:
                    encrypted_sizes.append(int(enc_size))
            
            if original_sizes:
                print(f"\n  File Sizes (Original):")
                print(f"    Average: {statistics.mean(original_sizes)/1024/1024:.2f} MB")
                print(f"    Min: {min(original_sizes)/1024:.2f} KB")
                print(f"    Max: {max(original_sizes)/1024/1024:.2f} MB")
                print(f"    Total: {sum(original_sizes)/1024/1024:.2f} MB")
        
        # Analyze server-side file operations
        if self.server_data:
            server_traces = self._extract_traces(self.server_data)
            file_spans = self._get_all_spans_by_name(server_traces, "file_span")
            
            if file_spans:
                file_latencies = [self._get_span_duration_ms(span) for span in file_spans]
                
                print(f"\n--- FILE RECEIVE OPERATIONS (Server) ---")
                print(f"  Total files received: {len(file_spans)}")
                print(f"  Average time per file: {statistics.mean(file_latencies):.2f} ms")
                print(f"  Min time: {min(file_latencies):.2f} ms")
                print(f"  Max time: {max(file_latencies):.2f} ms")
                print(f"  Median time: {statistics.median(file_latencies):.2f} ms")
    
    def analyze_tracing_overhead(self):
        """Analyze tracing overhead and span counts"""
        print("\n" + "="*80)
        print("TRACING OVERHEAD ANALYSIS")
        print("="*80)
        
        traces = self._extract_traces(self.client_data)
        
        total_spans = sum(len(trace.get('spans', [])) for trace in traces)
        
        print(f"\nTotal traces collected: {len(traces)}")
        print(f"Total spans collected: {total_spans}")
        print(f"Average spans per trace: {total_spans/len(traces):.1f}")
        
        # Count span types
        span_types = defaultdict(int)
        for trace in traces:
            for span in trace.get('spans', []):
                op_name = span.get('operationName', 'unknown')
                span_types[op_name] += 1
        
        print(f"\nSpan distribution:")
        for span_type, count in sorted(span_types.items(), key=lambda x: x[1], reverse=True):
            print(f"  {span_type}: {count}")
    
    def compare_sampling_rates(self, other_analyzer: 'JaegerTraceAnalyzer', 
                              label1: str = "Configuration 1", label2: str = "Configuration 2"):
        """Compare performance between two different sampling configurations"""
        print("\n" + "="*80)
        print(f"COMPARISON: {label1} vs {label2}")
        print("="*80)
        
        traces1 = self._extract_traces(self.client_data)
        traces2 = self._extract_traces(other_analyzer.client_data)
        
        total_spans1 = sum(len(t.get('spans', [])) for t in traces1)
        total_spans2 = sum(len(t.get('spans', [])) for t in traces2)
        
        print(f"\n{label1}:")
        print(f"  Traces collected: {len(traces1)}")
        print(f"  Total spans: {total_spans1}")
        
        print(f"\n{label2}:")
        print(f"  Traces collected: {len(traces2)}")
        print(f"  Total spans: {total_spans2}")
        
        if len(traces1) > 0 and len(traces2) > 0:
            reduction = ((total_spans1 - total_spans2) / total_spans1) * 100
            print(f"\nSpan reduction: {reduction:.1f}%")
        
        # Compare client spans
        client_spans1 = self._get_all_spans_by_name(traces1, "client_span")
        client_spans2 = self._get_all_spans_by_name(traces2, "client_span")
        
        if client_spans1 and client_spans2:
            lat1 = [self._get_span_duration_ms(s) for s in client_spans1]
            lat2 = [self._get_span_duration_ms(s) for s in client_spans2]
            
            print(f"\nLatency Comparison:")
            print(f"  {label1} - Average: {statistics.mean(lat1):.2f} ms")
            print(f"  {label2} - Average: {statistics.mean(lat2):.2f} ms")
            print(f"  Difference: {abs(statistics.mean(lat1) - statistics.mean(lat2)):.2f} ms")
            
            if statistics.mean(lat2) > 0:
                overhead_pct = ((statistics.mean(lat1) - statistics.mean(lat2)) / statistics.mean(lat2)) * 100
                print(f"  Overhead: {overhead_pct:.2f}%")


def main():
    if len(sys.argv) < 2:
        print("Usage: python analyze_traces.py <client_traces.json> [server_traces.json]")
        print("\nExamples:")
        print("  # Analyze client and server traces:")
        print("  python analyze_traces.py client_traces.json server_traces.json")
        print("\n  # Analyze only client traces:")
        print("  python analyze_traces.py client_traces.json")
        print("\n  # Compare two configurations (e.g., different sampling rates):")
        print("  python analyze_traces.py --compare client_always_on.json client_25_percent.json")
        print("\n  # Compare with custom labels:")
        print("  python analyze_traces.py --compare client_always_on.json client_25_percent.json \"AlwaysOn (100%)\" \"Probability (25%)\"")
        sys.exit(1)
    
    if sys.argv[1] == "--compare" and len(sys.argv) >= 4:
        # Comparison mode
        analyzer1 = JaegerTraceAnalyzer(sys.argv[2])
        analyzer2 = JaegerTraceAnalyzer(sys.argv[3])
        
        # Use custom labels if provided
        label1 = sys.argv[4] if len(sys.argv) > 4 else sys.argv[2]
        label2 = sys.argv[5] if len(sys.argv) > 5 else sys.argv[3]
        
        print("Analyzing first configuration...")
        analyzer1.analyze_client_performance()
        analyzer1.analyze_file_operations()
        analyzer1.analyze_tracing_overhead()
        
        print("\n\nAnalyzing second configuration...")
        analyzer2.analyze_client_performance()
        analyzer2.analyze_file_operations()
        analyzer2.analyze_tracing_overhead()
        
        analyzer1.compare_sampling_rates(analyzer2, label1=label1, label2=label2)
    else:
        # Normal analysis mode
        client_json = sys.argv[1]
        server_json = sys.argv[2] if len(sys.argv) > 2 else None
        
        analyzer = JaegerTraceAnalyzer(client_json, server_json)
        
        # Run all analyses
        analyzer.analyze_client_performance()
        analyzer.analyze_server_performance()
        analyzer.analyze_file_operations()
        analyzer.analyze_tracing_overhead()
        
        print("\n" + "="*80)
        print("Analysis complete!")
        print("="*80)


if __name__ == "__main__":
    main()