"""
Statistical Debugging Analysis Script

Analyzes OpenTelemetry trace data from Jaeger to identify predicates
that correlate with failures using Statistical Debugging metrics.

Usage:
    python3 analyze_traces.py <jaeger_json_file>
    
Or for simulated data:
    python3 analyze_traces.py --simulate
"""

import json
import sys
from collections import defaultdict
import random

class StatisticalDebugger:
    def __init__(self):
        self.runs = []
        self.predicate_stats = defaultdict(lambda: {'success': 0, 'failure': 0})
        
    def add_run(self, run_id, success, predicates):
        """
        Add a run with its success status and predicate values
        
        Args:
            run_id: Unique identifier for this run
            success: Boolean indicating if run was successful
            predicates: Dict of predicate_name -> boolean value
        """
        self.runs.append({
            'id': run_id,
            'success': success,
            'predicates': predicates
        })
        
        status = 'success' if success else 'failure'
        for predicate, value in predicates.items():
            if value:  # Only count when predicate is true
                self.predicate_stats[predicate][status] += 1
    
    def calculate_metrics(self):
        """Calculate Failure and Increase metrics for each predicate"""
        total_success = sum(1 for r in self.runs if r['success'])
        total_failure = sum(1 for r in self.runs if not r['success'])
        
        if total_failure == 0:
            print("WARNING: No failures detected in the data!")
            print("The bug may not have been triggered in any runs.")
            return []
        
        results = []
        
        for predicate, stats in self.predicate_stats.items():
            s_true = stats['success']  # Success runs where predicate is true
            f_true = stats['failure']  # Failure runs where predicate is true
            
            # Calculate F(p) - Failure metric
            # P(predicate | failure)
            failure_metric = f_true / total_failure if total_failure > 0 else 0
            
            # Calculate Context metric
            # P(predicate | success)  
            context_metric = s_true / total_success if total_success > 0 else 0
            
            # Calculate Increase metric
            # Increase(p) = F(p) - Context(p)
            increase_metric = failure_metric - context_metric
            
            results.append({
                'predicate': predicate,
                'failure_metric': failure_metric,
                'context_metric': context_metric,
                'increase_metric': increase_metric,
                'failure_count': f_true,
                'success_count': s_true,
                'total_true': f_true + s_true
            })
        
        # Sort by increase metric (descending)
        results.sort(key=lambda x: x['increase_metric'], reverse=True)
        return results
    
    def print_analysis(self):
        """Print detailed analysis of predicates"""
        results = self.calculate_metrics()
        
        print("\n" + "="*80)
        print("STATISTICAL DEBUGGING ANALYSIS")
        print("="*80)
        print(f"\nTotal runs: {len(self.runs)}")
        print(f"Successful runs: {sum(1 for r in self.runs if r['success'])}")
        print(f"Failed runs: {sum(1 for r in self.runs if not r['success'])}")
        
        if not results:
            print("\nNo predicate data to analyze!")
            return
        
        print("\n" + "-"*80)
        print(f"{'Rank':<6} {'Predicate':<40} {'F(p)':<8} {'C(p)':<8} {'Increase':<10}")
        print("-"*80)
        
        for rank, result in enumerate(results, 1):
            print(f"{rank:<6} {result['predicate']:<40} "
                  f"{result['failure_metric']:<8.3f} "
                  f"{result['context_metric']:<8.3f} "
                  f"{result['increase_metric']:<10.3f}")
        
        print("-"*80)
        
        print("\n" + "="*80)
        print("TOP 5 SUSPICIOUS PREDICATES (by Increase metric)")
        print("="*80)
        
        for i, result in enumerate(results[:5], 1):
            print(f"\n{i}. {result['predicate']}")
            print(f"   - Appears in {result['failure_count']} failures and {result['success_count']} successes")
            print(f"   - Failure probability: {result['failure_metric']:.1%}")
            print(f"   - Success probability: {result['context_metric']:.1%}")
            print(f"   - Increase: {result['increase_metric']:.3f}")
            
            if result['increase_metric'] > 0.5:
                print(f"   ⚠️  VERY STRONG CORRELATION WITH FAILURE")
            elif result['increase_metric'] > 0.3:
                print(f"   ⚠️  STRONG CORRELATION WITH FAILURE")
            elif result['increase_metric'] > 0.1:
                print(f"   ⚠️  MODERATE CORRELATION WITH FAILURE")
            else:
                print(f"   ℹ️  Weak or no correlation")
        
        print("\n" + "="*80)
        print("INTERPRETATION")
        print("="*80)
        print("""
The Increase metric shows how much more likely a predicate is to be true
in failing runs compared to successful runs.

High positive Increase values indicate predicates that are strongly 
associated with failures and should be investigated as potential bug causes.

For this bug injection:
- 'bug_triggered' should have the highest Increase (it's the actual bug)
- 'is_large_file' should correlate (bug only affects large files)
- 'compression_effective=false' should correlate (bug causes poor compression)
- 'large_encrypted_payload' should correlate (symptom of no compression)
- File size predicates help narrow down which files are affected
        """)

def extract_predicates_from_span(span):
    """Extract predicate values from a span's attributes"""
    tags = {tag['key']: tag['value'] for tag in span.get('tags', [])}
    
    # Extract boolean predicates
    predicates = {}
    
    # Direct boolean attributes (8 predicates for SD)
    bool_attrs = [
        'is_large_file',
        'bug_triggered',
        'encryption_overhead_high',
        'compression_skipped',
        'is_compressed',
        'file_size_huge',
        'file_size_medium',
        'file_size_small',
    ]
    
    for attr in bool_attrs:
        if attr in tags:
            predicates[attr] = tags[attr] == True or tags[attr] == 'true'
    
    return predicates

def determine_success(span):
    """
    Determine if a span represents a successful operation
    
    For this bug: failures occur when bug is triggered AND compression is poor
    """
    tags = {tag['key']: tag['value'] for tag in span.get('tags', [])}
    
    # Check for explicit error flags from server
    had_error = (tags.get('had_decompression_error') == True or 
                 tags.get('had_decryption_error') == True or
                 tags.get('had_timeout') == True)
    
    if had_error:
        return False
    
    # Bug triggered with poor compression is a failure
    bug_triggered = tags.get('bug_triggered') == True or tags.get('bug_triggered') == 'true'
    compression_ratio = float(tags.get('compression_ratio', 1.0))
    
    # Failure condition: bug triggered causes very poor compression
    if bug_triggered and compression_ratio < 0.15:
        return False
    
    return True

def parse_jaeger_json(json_file):
    """Parse Jaeger JSON export and extract trace data"""
    with open(json_file, 'r') as f:
        data = json.load(f)
    
    debugger = StatisticalDebugger()
    
    # Jaeger JSON structure from API: {data: [{traceID: ..., spans: [...}]}
    traces = data.get('data', [])
    
    for trace in traces:
        trace_id = trace.get('traceID')
        spans = trace.get('spans', [])
        
        # Look for 'sent_file' spans (where the bug manifests)
        for span in spans:
            operation_name = span.get('operationName', '')
            
            if operation_name == 'sent_file':
                predicates = extract_predicates_from_span(span)
                success = determine_success(span)
                
                debugger.add_run(f"{trace_id}_{span.get('spanID')}", success, predicates)
    
    return debugger

def simulate_data():
    """Simulate trace data for testing (when no Jaeger export available)"""
    debugger = StatisticalDebugger()
    
    print("Simulating 20 runs with bug injection...\n")
    
    for run_id in range(20):
        # Simulate random file characteristics
        is_large = random.random() < 0.33  # ~33% large files
        bug_triggered = is_large and random.random() < 0.3  # 30% of large files trigger bug
        
        if bug_triggered:
            compression_ratio = random.uniform(0.0, 0.15)  # Very poor compression when bug hits
        elif is_large:
            compression_ratio = random.uniform(0.5, 0.7)  # Good compression normally
        else:
            compression_ratio = random.uniform(0.6, 0.8)  # Small files compress well
        
        original_size = random.randint(50*1024*1024, 100*1024*1024) if is_large else random.randint(5*1024, 5*1024*1024)
        
        predicates = {
            # Direct predicates from client.py (10 main predicates)
            'is_large_file': is_large,
            'bug_triggered': bug_triggered,
            'encryption_overhead_high': random.random() < 0.1,
            'file_size_huge': original_size > 50 * 1024 * 1024,
            'file_size_medium': 1024 * 1024 < original_size <= 10 * 1024 * 1024,
            'file_size_small': original_size <= 1024 * 1024,
            'is_compressed': compression_ratio > 0.01,
            'compression_skipped': compression_ratio < 0.01,
            'compression_effective': compression_ratio > 0.3,
            'large_encrypted_payload': original_size > 15 * 1024 * 1024,
            
            # Server-side error predicates
            'had_timeout': False,
            'had_decompression_error': False,
            'had_decryption_error': False,
            'is_compressible': original_size > 50000,
        }
        
        success = not (bug_triggered and compression_ratio < 0.15)
        
        debugger.add_run(run_id, success, predicates)
    
    return debugger

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--simulate':
        print("Running with simulated data...\n")
        debugger = simulate_data()
    elif len(sys.argv) > 1:
        json_file = sys.argv[1]
        print(f"Parsing Jaeger JSON export: {json_file}\n")
        debugger = parse_jaeger_json(json_file)
    else:
        print("No Jaeger export provided, using simulated data...\n")
        debugger = simulate_data()
    
    debugger.print_analysis()

if __name__ == "__main__":
    main()