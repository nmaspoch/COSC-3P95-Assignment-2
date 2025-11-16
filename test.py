import subprocess, time, json, os

def start_server(tracing_enabled, sampling_rate):
    """Start the server with specified configuration"""
    print(f"Starting server (tracing={tracing_enabled}, sampling={sampling_rate})...")
    
    env = os.environ.copy()
    env["TRACING_ENABLED"] = tracing_enabled
    env["SAMPLING_RATE"] = sampling_rate
    
    server_process = subprocess.Popen(
        ["python3", "server.py"],
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    time.sleep(3)  # Give server time to start
    print("✅ Server started\n")
    return server_process

def stop_server(server_process):
    """Stop the server gracefully"""
    print("Stopping server...")
    server_process.terminate()
    try:
        server_process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        server_process.kill()
    print("✅ Server stopped\n")

configs = [
    {"name": "No Tracing", "tracing": "false", "sampling": "1.0", "runs": 5},
    {"name": "Full Tracing", "tracing": "true", "sampling": "1.0", "runs": 5},
    {"name": "25% Sampling", "tracing": "true", "sampling": "0.25", "runs": 20},
]

results = []

try:
    for config in configs:
        print(f"\n{'='*60}")
        print(f"Testing: {config['name']}")
        print(f"{'='*60}")
        
        # Start server with this configuration
        server_process = start_server(config['tracing'], config['sampling'])
        
        try:
            for run in range(config['runs']):
                print(f"Run {run+1}/{config['runs']}...", end=" ")
                
                env = os.environ.copy()
                env["TRACING_ENABLED"] = config['tracing']
                env["SAMPLING_RATE"] = config['sampling']
                
                start = time.time()
                result = subprocess.run(
                    ["python3", "client.py"],
                    env=env,
                    capture_output=True,
                    text=True
                )
                elapsed = time.time() - start
                
                if result.returncode != 0:
                    print(f"❌ FAILED")
                    print(f"Error: {result.stderr}")
                else:
                    print(f"✅ {elapsed:.2f}s")
                    results.append({
                        "config": config['name'],
                        "run": run + 1,
                        "time": elapsed
                    })
                
                time.sleep(2)  # Brief pause between runs
        
        finally:
            # Stop server after this config's runs
            stop_server(server_process)
            time.sleep(2)  # Pause before next config

    # Save results
    with open("performance_results.json", "w") as f:
        json.dump(results, f, indent=2)

    print("\n" + "="*60)
    print("✅ All tests complete! Results saved to performance_results.json")
    print("="*60)
    
    # Print summary
    print("\nSummary:")
    for config in configs:
        config_results = [r['time'] for r in results if r['config'] == config['name']]
        if config_results:
            avg = sum(config_results) / len(config_results)
            min_time = min(config_results)
            max_time = max(config_results)
            print(f"{config['name']:<20}: {avg:.2f}s avg (min: {min_time:.2f}s, max: {max_time:.2f}s)")

except KeyboardInterrupt:
    print("\n\n⚠️  Test interrupted by user")
except Exception as e:
    print(f"\n\n❌ Error: {e}")